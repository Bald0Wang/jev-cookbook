"""Blackjack experiment: basic strategy vs dealer-mimic ablation.

Question: does publishing the precomputed facts plus following basic strategy actually
change outcomes, or is any reasonable policy equivalent?

Two solution-blind, hole-blind judges over the same shoes:

* ``basic``       — the shipped judge: basic strategy read from published hand value,
                    dealer upcard, legal actions (identical to the gold policy);
* ``dealer_mimic`` — a plausible naive player: mimic the dealer rule (hit below 17,
                    stand on 17+), never double.

10 shoes each, bank 100, bet 10, run until bankrupt or 400 rounds.  Metrics: rounds
survived, final/peak bank, per-round outcome rates (win / lose / push / player bust).

Run:  python3 experiment.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blackjack_game as B

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
SEEDS = list(range(1, 11))
ROUND_CAP = 400


def basic_judge(request: dict) -> dict:
    return {'action': B.basic_strategy({'player': _cards_of(request),
                                        'dealer': [0, _upcard_id(request)],
                                        'bank': 10 ** 6, 'bet': B.BET})}


def _cards_of(request):
    """Rebuild card ids from the published names (rank + suit text)."""
    text = request['state']
    hand = text.split('Your hand: ')[1].split(' = ')[0]
    out = []
    for token in hand.split():
        rank = B.RANKS.index(token[:-1])
        suit = B.SUITS.index(token[-1])
        out.append(suit * 13 + rank)
    return out


def _upcard_id(request):
    import re
    match = re.search(r'Dealer shows (\S+)', request['state'])
    token = match.group(1)
    return B.SUITS.index(token[-1]) * 13 + B.RANKS.index(token[:-1])


def dealer_mimic_judge(request: dict) -> dict:
    total = request['hand_value']
    action = 'hit' if total < 17 else 'stand'
    if action not in request['legal']:
        action = 'stand'
    return {'action': action}


def play(seed: int, judge) -> dict:
    state = B.make_blackjack(seed=seed)
    rounds = 0
    peak = state['bank']
    counts = {'win': 0, 'lose': 0, 'push': 0, 'bust': 0, 'player_blackjack': 0,
              'dealer_bust': 0}
    doubles = 0
    while not state['done'] and rounds < ROUND_CAP:
        request = B.render_request(state)
        answer = judge(request)
        action = answer.get('action')
        if action not in B.legal_actions(state):
            action = 'stand'
        if action == 'double':
            doubles += 1
        state = B.step(state, action)
        rounds += 1
        peak = max(peak, state['bank'])
        outcome = state['history'][-1]['outcome'] if state['history'] else 'push'
        key = outcome if outcome in counts else ('bust' if outcome == 'bust' else 'push')
        counts[key] = counts.get(key, 0) + 1
    return {
        'seed': seed, 'rounds': rounds, 'final_bank': state['bank'], 'peak_bank': peak,
        'doubles': doubles,
        'rates': {k: round(v / max(1, rounds), 3) for k, v in counts.items()},
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    judges = {'basic': basic_judge, 'dealer_mimic': dealer_mimic_judge}
    report = {'seeds': SEEDS, 'round_cap': ROUND_CAP, 'strategies': {}}

    print(f"{'strategy':<14} {'rounds':>7} {'final bank':>11} {'peak':>6} {'win%':>6} "
          f"{'lose%':>6} {'bust%':>6}")
    for name, judge in judges.items():
        results = [play(seed, judge) for seed in SEEDS]
        mean_rounds = sum(r['rounds'] for r in results) / len(results)
        mean_bank = sum(r['final_bank'] for r in results) / len(results)
        mean_peak = sum(r['peak_bank'] for r in results) / len(results)
        win_rate = sum(r['rates'].get('win', 0) + r['rates'].get('player_blackjack', 0)
                       for r in results) / len(results)
        lose_rate = sum(r['rates'].get('lose', 0) for r in results) / len(results)
        bust_rate = sum(r['rates'].get('bust', 0) for r in results) / len(results)
        report['strategies'][name] = {'results': results,
                                      'mean_rounds': round(mean_rounds, 1),
                                      'mean_final_bank': round(mean_bank, 1),
                                      'mean_peak_bank': round(mean_peak, 1),
                                      'win_rate': round(win_rate, 3),
                                      'lose_rate': round(lose_rate, 3),
                                      'bust_rate': round(bust_rate, 3)}
        print(f"{name:<14} {mean_rounds:>7.1f} {mean_bank:>11.1f} {mean_peak:>6.1f} "
              f"{win_rate*100:>5.1f} {lose_rate*100:>5.1f} {bust_rate*100:>5.1f}")

    (ARTIFACTS / 'experiment_strategy.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {ARTIFACTS / 'experiment_strategy.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
