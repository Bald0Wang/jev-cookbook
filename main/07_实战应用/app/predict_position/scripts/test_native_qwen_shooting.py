"""Native-LM shooting prompt, probability and rollout contracts without a GPU."""
import copy
import hashlib
import math
import random
import unittest

from evaluate_native_qwen_shooting import (
    BACKEND, build_prompt, digest, iter_episodes, validate_native_answer,
)
from evaluate_appo_doom import sample_with_receipt
from replay_unified_episodes import replay_episode
import test_appo_basic_data as mirror_fixtures
from unified_game_pipeline import behavior_distribution, policy_request


class FakeNative:
    """Only a mock vocabulary result; no model-performance claim."""
    def __init__(self):
        self.calls = 0
        self.requests = []

    def predict(self, payload, batch_questions=0, temperature=1.0):
        assert batch_questions == 0 and temperature == 1
        self.calls += 1
        self.requests.extend(copy.deepcopy(payload['states']))
        results = []
        for request in payload['states']:
            prompt, labels = build_prompt(request)
            probs = dict(zip(labels, [.1, .2, .3, .4]))
            answer = {'type': 'choice', 'backend': BACKEND,
                      'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                      'candidate_to_token': {key: {'text': label, 'id': 32+i}
                                             for i, (key, label) in enumerate(labels.items())},
                      'probabilities': probs,
                      'native_option_logits': {key: math.log(p) for key, p in probs.items()},
                      'native_option_unconditional_probs': {key: .2*p for key, p in probs.items()},
                      'offered_token_mass': .2}
            results.append({'id': request['id'], 'answers': {'action': answer}})
        return {'states': results, 'execution': {'forward_passes': 1, 'generated_tokens': 0,
                                                'inference_call_index': self.calls}}


class NativeShootingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = mirror_fixtures.MirrorTests()
        self.fixture.setUp()
        self.cases = []
        for i in range(6):
            case = copy.deepcopy(self.fixture.case)
            case.update(id=f'basic-{i}', seed=73+i, split='test' if i < 3 else 'ood')
            if i >= 3:
                case['spec']['frame_skip'] = 8
            self.cases.append(case)

    def tearDown(self):
        self.fixture.tearDown()

    def test_prompt_keeps_full_standard_request_and_all_actions(self):
        predictor = FakeNative()
        episodes = list(iter_episodes(self.cases[:1], predictor, 'fixture', epsilon=0))
        request = predictor.requests[0]
        self.assertEqual(request, policy_request(episodes[0]['steps'][0]['observation'], self.cases[0]['id']))
        prompt, labels = build_prompt(request)
        self.assertIn(request['state'], prompt)
        self.assertIn(request['questions']['action']['instructions'], prompt)
        self.assertEqual(labels, {'left': 'A', 'noop': 'B', 'right': 'C', 'shoot': 'D'})
        for text in request['questions']['action']['criteria'].values():
            self.assertIn(text, prompt)

    def test_conditional_mass_and_logits_are_checked_separately(self):
        predictor = FakeNative()
        episodes = list(iter_episodes(self.cases[:1], predictor, 'fixture'))
        step = episodes[0]['steps'][0]
        answer = step['answers']['action']
        self.assertEqual(answer['offered_token_mass'], .2)
        self.assertAlmostEqual(sum(step['scores'].values()), 1.)
        validate_native_answer(answer, step['request'])
        for mutate in (lambda a: a['candidate_to_token']['left'].update(text='D'),
                       lambda a: a['native_option_logits'].update(left=100.),
                       lambda a: a.update(offered_token_mass=1.),
                       lambda a: a.update(prompt_sha256='wrong'),
                       lambda a: a['probabilities'].update(left=float('nan'))):
            broken = copy.deepcopy(answer)
            mutate(broken)
            with self.assertRaises(ValueError):
                validate_native_answer(broken, step['request'])

    def test_batch_order_and_rng_match_independent_episodes(self):
        for controller in ('greedy', 'sample'):
            serial = list(iter_episodes(self.cases, FakeNative(), 'fixture', controller, .1, batch_states=1))
            batched = list(iter_episodes(self.cases, FakeNative(), 'fixture', controller, .1, batch_states=4))
            self.assertEqual([e['case'] for e in batched], self.cases)
            for first, second in zip(serial, batched):
                self.assertEqual(first['final_info'], second['final_info'])
                rng = random.Random(int(digest([second['case']['id'], 17])[:16], 16))
                for a, b in zip(first['steps'], second['steps']):
                    for key in ('observation', 'action', 'scores', 'behavior_probs', 'sampling_draw', 'info'):
                        self.assertEqual(a[key], b[key])
                    distribution = behavior_distribution(b['scores'], controller, .1)
                    self.assertEqual((b['action'], b['sampling_draw']), sample_with_receipt(distribution, rng))

    def test_standard_replay_and_partial_final_tick_duration(self):
        episodes = list(iter_episodes(self.cases, FakeNative(), 'fixture'))
        for episode in episodes:
            audit = replay_episode(episode)
            self.assertTrue(audit['passed'], audit)
            self.assertEqual(episode['final_observation']['candidates'], {})
            self.assertEqual(episode['final_info']['episode_metrics']['physical_ticks'], 5)
            expected = [4, 1] if episode['case']['split'] == 'test' else [5]
            self.assertEqual([step['info']['actual_ticks'] for step in episode['steps']], expected)


if __name__ == '__main__':
    unittest.main()
