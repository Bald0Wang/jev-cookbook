"""Selection tests use episode outcomes, never heldout label-fit metrics."""
import json
from pathlib import Path
import tempfile
import unittest

from run_sonic_supervision import score_episodes, select_winner

WEIGHTS = {'maze/policy': 1/3, 'snake/policy': 1/3,
           'shooting/policy/basic': 1/6, 'shooting/policy/predict_position': 1/6}


class SelectionTests(unittest.TestCase):
    def test_population_weighting_and_split_reporting(self):
        cases, rows = [], []
        for split in ('test', 'ood'):
            for pool in WEIGHTS:
                spec = {'task': pool.split('/')[0]}
                if spec['task'] == 'shooting':
                    spec['scenario'] = pool.split('/')[-1]
                case = {'id': split + pool, 'split': split, 'spec': spec}
                cases.append(case)
                rows.append({'case': case, 'complete': True,
                             'success': split == 'test' and spec['task'] == 'shooting'})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'episodes.jsonl'
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            score = score_episodes(path, cases, WEIGHTS)
            self.assertAlmostEqual(score['weighted_success'], 1/6)
            self.assertEqual(score['by_split']['test']['shooting/policy/basic']['successes'], 1)
            self.assertEqual(score['by_split']['ood']['shooting/policy/basic']['successes'], 0)
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows[:-1] + [rows[0]]))
            with self.assertRaises(ValueError):
                score_episodes(path, cases, WEIGHTS)

    def test_initialization_can_win_and_best_new_is_retained(self):
        def result(score, pp=.5, basic=.5):
            return {'weighted_success': score, 'rates': {
                'shooting/policy/predict_position': pp, 'shooting/policy/basic': basic}}
        arms = [{'name': 'hard'}, {'name': 'soft'}]
        scores = {'initial': result(.9), 'hard': result(.8), 'soft': result(.7)}
        self.assertEqual(select_winner(scores, arms), 'initial')
        self.assertEqual(select_winner({k:v for k,v in scores.items() if k != 'initial'},
                                        arms, include_initial=False), 'hard')
        scores['hard'] = result(.9)
        self.assertEqual(select_winner(scores, arms), 'initial')
        scores['soft'] = result(.9, pp=.6)
        self.assertEqual(select_winner(scores, arms), 'soft')
        with self.assertRaises(ValueError):
            select_winner({'initial': result(.9), 'hard': result(.8)}, arms)


if __name__ == '__main__':
    unittest.main()
