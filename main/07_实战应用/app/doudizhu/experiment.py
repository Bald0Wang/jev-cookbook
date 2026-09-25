"""Dou Dizhu experiment: reference-policy baselines + peasant-cooperation ablation.

Questions:
1. What is the baseline balance between landlord (20 cards, leading) and the two
   peasants (17+17) under the reference policy?
2. How much is peasant cooperation worth?  The shipped policy has peasant seats never
   outbid their partner's strong play; the ablation removes that rule (peasants treat
   everyone as an opponent) while everything else stays identical.

40 deals per arm, identical seeds.  Metrics: win rate by side, mean plays, bombs per
game, multiplier distribution.

Run:  python3 experiment.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import doudizhu_game as D

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
GAMES = 40


def policy(state, moves, trick, cooperate: bool) -> dict:
    """Reference policy with a switch on peasant cooperation."""
    non_pass = [m for m in moves if m['type'] != 'pass']
    seat = state['turn']
    landlord = state['landlord']

    if trick is None:
        empties = [m for m in non_pass if len(m['cards']) == len(state['hands'][seat])]
        if empties:
            return empties[0]
        pool = [m for m in non_pass if m['type'] not in ('bomb', 'rocket')] or non_pass
        return min(pool, key=lambda m: (len(m['cards']) * 4 + m['rank']))

    owner = trick['owner']
    same_team = cooperate and seat != landlord and owner != landlord
    if same_team and (trick['rank'] >= 10 or len(state['hands'][owner]) <= 4):
        return moves[0] if moves[0]['type'] == 'pass' else \
            {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}
    plain = [m for m in non_pass if m['type'] not in ('bomb', 'rocket')]
    if plain:
        return min(plain, key=lambda m: m['rank'])
    danger = len(state['hands'][owner]) <= 2 or trick['rank'] >= 11
    explosives = [m for m in non_pass if m['type'] in ('bomb', 'rocket')]
    if explosives and danger:
        return min(explosives, key=lambda m: (m['type'] != 'bomb', m['rank']))
    return moves[0] if moves[0]['type'] == 'pass' else \
        {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}


def play(seed: int, cooperate: bool) -> dict:
    state = D.make_doudizhu(seed=seed)
    bombs = 0
    plays = 0
    while not state['done']:
        moves = D.gen_moves(state['hands'][state['turn']], state['trick'])
        move = policy(state, moves, state['trick'], cooperate)
        if move['type'] in ('bomb', 'rocket'):
            bombs += 1
        state = D.step(state, move)
        plays += 1
    return {
        'seed': seed, 'outcome': state['outcome'], 'plays': plays,
        'bombs': bombs, 'multiplier': state['multiplier'],
    }


def summarise(results) -> dict:
    landlord_wins = sum(1 for r in results if r['outcome'] == 'landlord_win')
    return {
        'games': len(results),
        'landlord_win_rate': round(landlord_wins / len(results), 3),
        'peasant_win_rate': round(1 - landlord_wins / len(results), 3),
        'mean_plays': round(sum(r['plays'] for r in results) / len(results), 1),
        'mean_bombs': round(sum(r['bombs'] for r in results) / len(results), 2),
        'x2_multiplier_games': sum(1 for r in results if r['multiplier'] >= 2),
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    seeds = list(range(1, GAMES + 1))
    report = {'games_per_arm': GAMES, 'arms': {}}

    print(f"{'arm':<22} {'landlord win':>13} {'peasant win':>12} {'plays':>7} {'bombs':>7}")
    for name, cooperate in (('cooperative (shipped)', True),
                            ('no_cooperation (ablated)', False)):
        results = [play(seed, cooperate) for seed in seeds]
        summary = summarise(results)
        summary['results'] = results
        report['arms'][name] = summary
        print(f"{name:<22} {summary['landlord_win_rate']:>10.0%} "
              f"{summary['peasant_win_rate']:>11.0%} "
              f"{summary['mean_plays']:>7.1f} {summary['mean_bombs']:>7.2f}")

    (ARTIFACTS / 'experiment_cooperation.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {ARTIFACTS / 'experiment_cooperation.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
