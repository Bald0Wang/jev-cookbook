"""Run Sudoku episodes against a judge: local constraint reader or the real Jev.

Judge contract: given a rendered request (``{'state', 'questions', 'cell',
'candidates'}``) return ``{'digit': str}``.  The local judge reads only published facts —
the board, the constraint exclusions, the candidate list — and answers with the same
naked-single / hidden-single reasoning a careful human applies.  It never touches
``state['solution']``; that is what makes its mistakes informative.

With ``--judge jev`` (and ``TYPESAFE_API_KEY`` set) the same requests go to the real API
through ``typesafe_sdk``, one ``system_one`` call per cell with the 9-way ``choice`` plus
nine ``boolean`` questions, mirroring the snake request shape.

Run:  .venv/bin/python jev_sudoku.py --episodes 10 --holes 40
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sudoku_game as S

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts" / "sudoku"


# --------------------------------------------------------------------- local judge
def _peer_cells(row: int, col: int):
    box_r, box_c = 3 * (row // 3), 3 * (col // 3)
    cells = [(row, c) for c in range(9) if c != col]
    cells += [(r, col) for r in range(9) if r != row]
    cells += [(r, c) for r in range(box_r, box_r + 3) for c in range(box_c, box_c + 3)
              if (r, c) != (row, col)]
    return cells


def local_judge(request: dict) -> dict:
    """Naked single first, then hidden single; otherwise the lowest surviving candidate.

    Deterministic and solution-blind.  When neither rule fires the guess can be wrong —
    exactly where a stronger judge (Jev) could do better with the same published facts.
    """
    grid = S.make_record  # noqa: F841  (documentation anchor: gold lives only in records)
    row, col = request['cell']
    candidates = list(request['candidates'])
    if not candidates:
        return {'digit': '1'}

    def other_candidates(r, c):
        return S._candidates

    # hidden single: a candidate that fits nowhere else in its row, column, or box
    for digit in candidates:
        for unit_cells in _unit_cells_of(row, col):
            others = [cell for cell in unit_cells if cell != (row, col)]
            if all(digit not in _cands_for(request, r, c) for r, c in others):
                return {'digit': str(digit)}

    # Guess fallback: skip digits already tried and proven wrong at this cell.  The
    # runner publishes `wrong_digits`; without this exclusion a deterministic judge
    # repeats the same wrong answer until the mistake budget runs out (see EXPERIMENT).
    tried = set(request.get('wrong_digits', {}).get(f'{row},{col}', []))
    survivors = [c for c in candidates if c not in tried]
    if not survivors:
        survivors = candidates  # every candidate disproven — doomed either way
    return {'digit': str(survivors[0])}


def _unit_cells_of(row: int, col: int):
    box_r, box_c = 3 * (row // 3), 3 * (col // 3)
    row_cells = [(row, c) for c in range(9)]
    col_cells = [(r, col) for r in range(9)]
    box_cells = [(r, c) for r in range(box_r, box_r + 3) for c in range(box_c, box_c + 3)]
    return row_cells, col_cells, box_cells


def _cands_for(request, r, c):
    """Surviving candidates for any empty cell, derived from the published board only."""
    state = request['_grid']  # the runner attaches the live grid for the local judge
    if state[r][c]:
        return []
    return S._candidates(state, r, c)


# --------------------------------------------------------------------- jev judge
def jev_judge_factory(client):
    def judge(request: dict) -> dict:
        questions = {k: v for k, v in request['questions'].items()}
        started = time.perf_counter()
        response = client.system_one(state=request['state'], questions=questions)
        latency_ms = (time.perf_counter() - started) * 1000
        answer = response.answers['digit']
        request.setdefault('_latency_ms', []).append(latency_ms)
        return {'digit': str(answer.choice)}
    return judge


# --------------------------------------------------------------------- episode loop
def run_episode(seed: int, holes: int, judge, split: str = 'dev',
                trial_memory: bool = False):
    """One episode.  With ``trial_memory``, wrong guesses are remembered per cell and
    published back into the next request (state text + ``wrong_digits``), so the judge
    never repeats a disproven answer — the same information a human solver gets by
    noticing a pencil mark failed."""
    state = S.make_sudoku(seed=seed, holes=holes)
    steps = []
    wrong: dict[tuple[int, int], list[int]] = {}
    while not state['done']:
        request = S.render_request(state)
        request['_grid'] = [row[:] for row in state['grid']]  # public facts for the reader
        if trial_memory:
            request['wrong_digits'] = {f'{r},{c}': ds for (r, c), ds in wrong.items()}
            here = wrong.get(tuple(request['cell']))
            if here:
                request['state'] += (
                    '\nDigits already tried and proven wrong at this cell: '
                    + ', '.join(str(d) for d in sorted(here))
                    + '. Do not repeat them.'
                )
        record = S.make_record(state, split)
        answer = judge(request)
        digit = int(answer['digit'])
        row, col = request['cell']
        correct = digit == record['gold']['digit']
        steps.append({
            'cell': [row, col],
            'candidates': request['candidates'],
            'answered': digit,
            'gold': record['gold']['digit'],
            'correct': correct,
        })
        state = S.step(state, digit)
        if trial_memory and not correct:
            wrong.setdefault((row, col), []).append(digit)
    return {
        'seed': seed,
        'holes': holes,
        'outcome': state['outcome'],
        'score': state['score'],
        'mistakes': state['mistakes'],
        'steps': state['steps'],
        'steps_detail': steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=int, default=10)
    parser.add_argument('--holes', type=int, default=40)
    parser.add_argument('--judge', choices=('local', 'jev'), default='local')
    parser.add_argument('--trial-memory', action='store_true',
                        help='remember wrong guesses per cell and publish them back')
    parser.add_argument('--first-seed', type=int, default=1)
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    judge = None
    if args.judge == 'jev':
        key = os.environ.get('TYPESAFE_API_KEY')
        if not key:
            print('TYPESAFE_API_KEY 未设置 —— 无法使用真 Jev，退出')
            return 1
        import typesafe_sdk

        client = typesafe_sdk.TypeSafeClient()
        judge = jev_judge_factory(client)
        label = 'jev (real API)'
    else:
        judge = local_judge
        label = 'local constraint reader (naked/hidden single, solution-blind)'

    print(f'judge: {label}')
    print(f'episodes: {args.episodes}, holes: {args.holes}, seeds: '
          f'{args.first_seed}..{args.first_seed + args.episodes - 1}')
    print()

    outcomes = []
    log_path = ARTIFACTS / f'sudoku_{args.judge}_{args.holes}h_{args.episodes}ep.jsonl'
    with log_path.open('w', encoding='utf-8') as log:
        for index in range(args.episodes):
            seed = args.first_seed + index
            result = run_episode(seed, args.holes, judge,
                                 trial_memory=args.trial_memory)
            outcomes.append(result)
            log.write(json.dumps(result) + '\n')
            mark = 'WIN ' if result['outcome'] == 'win' else 'FAIL'
            print(f"  seed {seed:>4}: {mark} score={result['score']:<2} "
                  f"mistakes={result['mistakes']} steps={result['steps']}")

    wins = sum(1 for r in outcomes if r['outcome'] == 'win')
    scores = [r['score'] for r in outcomes]
    mistakes = [r['mistakes'] for r in outcomes]
    print()
    print(f"win rate : {wins}/{len(outcomes)}")
    print(f"mean fill: {sum(scores) / len(scores):.1f} correct digits "
          f"(of {args.holes} per puzzle)")
    print(f"mistakes : mean {sum(mistakes) / len(mistakes):.2f}, max {max(mistakes)}")
    print(f"log      : {log_path}")

    summary = {
        'judge': label,
        'episodes': len(outcomes),
        'holes': args.holes,
        'wins': wins,
        'mean_score': sum(scores) / len(scores),
        'max_mistakes': max(mistakes),
        'outcomes': outcomes,
    }
    (ARTIFACTS / f'sudoku_{args.judge}_summary.json').write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary  : {ARTIFACTS / f'sudoku_{args.judge}_summary.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
