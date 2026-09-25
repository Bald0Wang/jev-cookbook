"""Sudoku experiment: difficulty curve + judge ablation.

Question: does publishing constraint facts actually help a fuzzy judge, and where does
constraint reasoning alone stop being enough?

Two solution-blind judges over the same puzzles:

* ``local``    — naked/hidden single from the published candidates (the shipped judge);
* ``random``   — uniform pick among the same published candidates (seeded, deterministic),
                 i.e. a judge that ignores the semantics of the facts it is given.

Grid: holes in {40, 45, 50, 55} x 10 episodes each.  Metrics: win rate, mean correct
fills, mean mistakes.

Run:  python3 experiment.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sudoku_game as S
from jev_sudoku import run_episode

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
HOLES = (40, 45, 50, 55)
EPISODES = 10


def random_judge_factory():
    """Uniform pick among published candidates; deterministic overall."""
    rng = random.Random(20260922)

    def judge(request: dict) -> dict:
        cands = list(request['candidates'])
        tried = set(request.get('wrong_digits', {}).get(
            f"{request['cell'][0]},{request['cell'][1]}", []))
        survivors = [c for c in cands if c not in tried] or cands
        return {'digit': str(rng.choice(survivors)) if survivors else '1'}

    return judge


def local_judge(request: dict) -> dict:
    row, col = request['cell']
    cands = list(request['candidates'])

    def unit_cells():
        box_r, box_c = 3 * (row // 3), 3 * (col // 3)
        return (
            [(row, c) for c in range(9)],
            [(r, col) for r in range(9)],
            [(r, c) for r in range(box_r, box_r + 3) for c in range(box_c, box_c + 3)],
        )

    # hidden single: a candidate that fits no other empty cell in its row/column/box
    for digit in cands:
        for unit in unit_cells():
            others = [cell for cell in unit if cell != (row, col)]
            if all(
                digit not in S._candidates(request['_grid'], r, c) for r, c in others
            ):
                return {'digit': str(digit)}
    # guess fallback: never repeat a digit already proven wrong at this cell
    tried = set(request.get('wrong_digits', {}).get(f'{row},{col}', []))
    survivors = [c for c in cands if c not in tried] or cands
    return {'digit': str(survivors[0])}


# ------------------------------------------------------- switch-cell variant
def make_avoiding_next_cell(avoid: set):
    """MRV that skips cells already guessed wrong (until they collapse to a naked
    single via correct fills elsewhere, at which point they are played for free)."""
    def patched(state):
        best = None
        for r in range(9):
            for c in range(9):
                if state['grid'][r][c] == 0:
                    cands = S._candidates(state['grid'], r, c)
                    if (r, c) in avoid and len(cands) > 1:
                        continue
                    key = (len(cands), r, c)
                    if best is None or key < (len(best[2]), best[0], best[1]):
                        best = (r, c, cands)
        return best
    return patched


def switch_episode(seed: int, holes: int, judge) -> dict:
    """Trial-and-error by *moving*: after a wrong guess at a cell, park it and work
    elsewhere; return when other fills reduce it to a forced play.  Solution-blind."""
    avoid: set[tuple[int, int]] = set()
    original = S.next_cell
    S.next_cell = make_avoiding_next_cell(avoid)
    try:
        state = S.make_sudoku(seed=seed, holes=holes)
        while not state['done']:
            try:
                request = S.render_request(state)
            except Exception:
                # only ambiguous parked cells remain and the mistake budget is intact:
                # unsolvable within this episode's rules — count as a loss
                state['done'], state['outcome'] = True, 'three_mistakes'
                break
            request['_grid'] = [row[:] for row in state['grid']]
            answer = judge(request)
            cell = tuple(request['cell'])
            mistakes_before = state['mistakes']
            state = S.step(state, int(answer['digit']))
            if state['mistakes'] == mistakes_before + 1:
                avoid.add(cell)  # this cell just cost a mistake — park it
        return {'seed': seed, 'holes': holes, 'outcome': state['outcome'],
                'score': state['score'], 'mistakes': state['mistakes'],
                'steps': state['steps'], 'steps_detail': []}
    finally:
        S.next_cell = original


def run_switch_arm(holes_list, episodes: int) -> dict:
    out = {}
    print('--- 换格对照组（同一裁判：hidden single + 猜最小；猜错后换格）---')
    for holes in holes_list:
        results = [switch_episode(seed=1000 + holes * 10 + i, holes=holes,
                                  judge=local_judge) for i in range(episodes)]
        wins = sum(1 for r in results if r['outcome'] == 'win')
        mean_fill = sum(r['score'] for r in results) / len(results)
        mean_mist = sum(r['mistakes'] for r in results) / len(results)
        out[f'{holes}_换格'] = {
            'holes': holes, 'judge': '约束推理 + 换格', 'wins': wins,
            'mean_fill': round(mean_fill, 1), 'mean_mistakes': round(mean_mist, 2)}
        print(f"{holes:>6}  {disp('约束推理 + 换格')} {wins:>3}/{episodes} {mean_fill:>7.1f} {mean_mist:>9.2f}")
    return out


def disp(name: str) -> str:
    """Pad a (possibly Chinese) name to a fixed display width."""
    return name + ' ' * max(0, 34 - sum(2 if ord(ch) > 127 else 1 for ch in name))


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    judges = {
        'local_constraint': local_judge,
        'random_candidate': random_judge_factory(),
    }
    report = {'holes_grid': list(HOLES), 'episodes_per_cell': EPISODES, 'cells': {}}

    # 四组对照：(名称, 裁判函数, 是否开试错记忆)
    arms = [
        ("约束推理", local_judge, False),
        ("约束推理 + 试错记忆", local_judge, True),
        ('随机', judges['random_candidate'], False),
        ('随机 + 试错记忆', judges['random_candidate'], True),
    ]
    print(f"{'空格':>6}  组别{'':<20} 胜     平均填对   平均失误")
    for holes in HOLES:
        for name, judge, memory in arms:
            results = [
                run_episode(seed=1000 + holes * 10 + i, holes=holes, judge=judge,
                            trial_memory=memory)
                for i in range(EPISODES)
            ]
            wins = sum(1 for r in results if r['outcome'] == 'win')
            mean_fill = sum(r['score'] for r in results) / len(results)
            mean_mist = sum(r['mistakes'] for r in results) / len(results)
            key = name.replace(' ', '_')
            report['cells'][f'{holes}_{key}'] = {
                'holes': holes, 'judge': name, 'wins': wins,
                'mean_fill': round(mean_fill, 1), 'mean_mistakes': round(mean_mist, 2),
            }
            print(f"{holes:>6}  {disp(name)} {wins:>3}/{EPISODES} {mean_fill:>7.1f} {mean_mist:>9.2f}")

    report['switch_arm'] = run_switch_arm(HOLES, EPISODES)

    (ARTIFACTS / 'experiment_difficulty.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {ARTIFACTS / 'experiment_difficulty.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
