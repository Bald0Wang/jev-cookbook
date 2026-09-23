#!/usr/bin/env python3
"""V3 fixed navigation-controller ablation on held-out source maps.

Policies: student greedy argmax, student categorical sampling at T=1, uniform
random, and an explicit shortest-path oracle upper bound. No visit penalty,
epsilon, temperature tuning, cycle cutoff, or oracle fallback for students.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from functools import partial
import hashlib
import json
import math
from pathlib import Path
import random
import time
import unittest

from game_tasks import source_group_id, solve, step, valid_actions


SEED = 20260917
POLICIES = ('greedy', 'sample', 'random', 'oracle')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def hash_file(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def checked_map_group(row):
    state = row['metadata']['environment_state']
    if state['game'] != 'grid_navigation':
        raise ValueError('Navigation V3 accepts grid-navigation states only')
    group = source_group_id(state)
    if row['metadata']['source_group_id'] != group:
        raise ValueError('Declared source map differs from the canonical environment map')
    return state, group


def select_episodes(data_dir, per_split=20):
    """First reachable state of each previously unseen map, in frozen file order."""
    if type(per_split) is not int or per_split <= 0:
        raise ValueError('per_split must be a positive integer')
    data_dir = Path(data_dir)
    train_groups = {checked_map_group(row)[1] for row in read_rows(data_dir / 'train.jsonl')}
    episodes, cohort_counts, selected_groups = [], {}, set()
    for split in ('test', 'ood'):
        count = 0
        skipped_duplicate_maps = 0
        skipped_unreachable_or_terminal = 0
        for row in read_rows(data_dir / f'{split}.jsonl'):
            state, group = checked_map_group(row)
            if group in train_groups:
                raise ValueError('Held-out source map overlaps training, including different agent starts')
            if group in selected_groups:
                skipped_duplicate_maps += 1
                continue
            answer = solve(state)
            if not answer['reachable'] or answer['terminal']:
                skipped_unreachable_or_terminal += 1
                continue
            episodes.append({'id': row['id'], 'game': 'grid_navigation', 'split': split,
                             'source_map_group_id': group, 'initial_state': copy.deepcopy(state)})
            selected_groups.add(group)
            count += 1
            if count == per_split:
                break
        if count != per_split:
            raise ValueError(f'{split}: need {per_split} distinct reachable held-out maps; found {count}')
        cohort_counts[split] = {'episodes': count, 'independent_source_maps': count,
                               'skipped_duplicate_map_starts_before_cutoff': skipped_duplicate_maps,
                               'skipped_unreachable_or_terminal_before_cutoff': skipped_unreachable_or_terminal}
    cohort = {
        'selection': 'First reachable nonterminal state from each distinct canonical source map in each frozen test/ood file; no selection on model outcomes.',
        'per_split': per_split, 'by_split': cohort_counts,
        'unique_source_maps': len(selected_groups), 'training_map_overlap': 0,
        'initial_episode_ids': [episode['id'] for episode in episodes],
        'initial_states_sha256': hashlib.sha256(canonical_json(episodes).encode()).hexdigest(),
        'data_sha256': {name: hash_file(data_dir / name) for name in ['train.jsonl', 'test.jsonl', 'ood.jsonl']},
    }
    return episodes, train_groups, cohort


def episode_rng(seed, map_id, initial_state):
    state = copy.deepcopy(initial_state)
    state['walls'] = sorted(state['walls'])
    payload = {'seed': seed, 'map_id': map_id, 'initial_state': state}
    hexadecimal = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    return random.Random(int(hexadecimal, 16)), hexadecimal


def validate_distribution(probabilities, actions):
    if not isinstance(probabilities, dict) or set(probabilities) != set(actions):
        raise ValueError('Distribution must cover exactly the legal actions')
    if any(type(p) not in {float, int} or not math.isfinite(p) or not 0 <= p <= 1
           for p in probabilities.values()):
        raise ValueError('Nonfinite or out-of-range action probability')
    total = math.fsum(probabilities.values())
    if abs(total - 1) > 1e-6:
        raise ValueError('Action probabilities do not sum to one')
    return total


def categorical(probabilities, rng):
    """Raw probabilities are retained; divide only by their floating-point sum."""
    actions = sorted(probabilities)
    total = validate_distribution(probabilities, actions)
    draw = rng.random()
    cutoff = draw * total
    cumulative = 0.0
    for action in actions:
        cumulative += probabilities[action]
        if cutoff < cumulative and probabilities[action] > 0:
            return action, draw, probabilities[action] / total
    # Handle only a last-bit cumulative-sum discrepancy; never choose zero support.
    action = next(action for action in reversed(actions) if probabilities[action] > 0)
    return action, draw, probabilities[action] / total


def rollout(episodes, policy, engine=None, renderer=None, train_groups=None, seed=SEED,
            validation_only=False, progress_every=0):
    if policy not in POLICIES:
        raise ValueError(f'Unknown policy: {policy}')
    uses_student = policy in {'greedy', 'sample'}
    if uses_student and (engine is None or renderer is None):
        raise ValueError('Student controllers require a prediction engine and the V3 pure-geometric renderer')
    if not episodes:
        raise ValueError('Empty rollout cohort')
    train_groups = set() if train_groups is None else set(train_groups)
    states, rngs = [], {}
    seen_ids, seen_maps = set(), set()
    for episode in episodes:
        initial = copy.deepcopy(episode['initial_state'])
        group = source_group_id(initial)
        if group != episode['source_map_group_id'] or group in train_groups:
            raise ValueError('Initial environment map identity or training overlap mismatch')
        if episode['id'] in seen_ids or group in seen_maps:
            raise ValueError('Each benchmark episode must represent a distinct source map')
        seen_ids.add(episode['id']); seen_maps.add(group)
        answer = solve(initial)
        if initial['game'] != 'grid_navigation' or not answer['reachable'] or answer['terminal']:
            raise ValueError('Benchmark requires reachable nonterminal grid starts')
        rng, seed_hex = episode_rng(seed, group, initial)
        rngs[episode['id']] = rng
        states.append({**episode, 'state': initial, 'rng_seed_sha256': seed_hex,
                       'max_steps': 2 * initial['size'] ** 2, 'shortest_path_length': answer['distance'],
                       'steps': [], 'model_decisions': 0, 'validation_engine_decisions': 0,
                       'forced_decisions': 0, 'active': True,
                       '_visits': Counter({tuple(initial['position']): 1})})
    batches, batch_examples = [], []
    inference_seconds, total_forwards, tick = 0.0, 0, 0
    while any(episode['active'] for episode in states):
        choices, pending, mapping = {}, [], []
        for index, episode in enumerate(states):
            if not episode['active']:
                continue
            state = episode['state']
            actions = sorted(valid_actions(state))
            if state['position'] == state['goal'] or len(episode['steps']) >= episode['max_steps'] or not actions:
                episode['active'] = False
                continue
            if len(actions) == 1:
                choices[index] = {'action': actions[0], 'probabilities': {actions[0]: 1.0},
                                  'actor': 'forced_legal_action', 'draw': None, 'sampling_probability': 1.0,
                                  'answers': None, 'request_id': None}
                episode['forced_decisions'] += 1
            elif uses_student:
                public = renderer(state, split=episode['split'], candidate_order=actions)
                if set(public) != {'state', 'questions'}:
                    raise ValueError('V3 renderer must return only state and questions')
                if set(public['questions']['action']['criteria']) != set(actions):
                    raise ValueError('Rendered candidates differ from the legal environment actions')
                request_id = f"{episode['id']}::step{len(episode['steps'])}"
                pending.append({'id': request_id, **public})
                mapping.append(index)
            else:
                if policy == 'random':
                    probabilities = {action: 1 / len(actions) for action in actions}
                    action, draw, chosen_probability = categorical(probabilities, rngs[episode['id']])
                else:
                    action = sorted(solve(state)['optimal_actions'])[0]
                    probabilities = {candidate: float(candidate == action) for candidate in actions}
                    draw, chosen_probability = None, 1.0
                choices[index] = {'action': action, 'probabilities': probabilities, 'actor': policy,
                                  'draw': draw, 'sampling_probability': chosen_probability,
                                  'answers': None, 'request_id': None}
        if pending:
            started = time.perf_counter()
            response = engine.predict({'states': pending}, batch_questions=0, temperature=1.0)
            elapsed = time.perf_counter() - started
            inference_seconds += elapsed
            execution = response['execution']
            if validation_only:
                if execution.get('validation_engine') != 'exact_oracle_control_flow_only' or execution.get('forward_passes') != 0:
                    raise ValueError('CPU validation must explicitly declare its non-model oracle engine')
            elif execution.get('forward_passes') != 1:
                raise ValueError('Every active-state batch must use exactly one real student forward')
            if execution.get('network_model_calls', 0) != 0 or execution.get('autoregressive_decode_steps', 0) != 0:
                raise ValueError('No external model calls or autoregressive decoding are allowed')
            temperature = response.get('temperature', {}).get('value')
            if temperature != 1.0:
                raise ValueError('Controller ablation requires the original T=1 model distribution')
            ids = [row['id'] for row in response['states']]
            if len(ids) != len(set(ids)) or set(ids) != {row['id'] for row in pending}:
                raise ValueError('Prediction response does not map one-to-one to the requested states')
            by_id = {row['id']: row['answers'] for row in response['states']}
            batch_id = len(batches)
            batch = {'id': f'batch_{batch_id}', 'tick': tick, 'state_ids': [row['id'] for row in pending],
                     'execution': execution, 'inference_seconds': elapsed}
            batches.append(batch)
            total_forwards += execution['forward_passes']
            if len(batch_examples) < 3:
                batch_examples.append({**batch, 'states': [{**row, 'answers': by_id[row['id']]} for row in pending]})
            for index, public in zip(mapping, pending):
                episode = states[index]
                answers = by_id[public['id']]
                probabilities = answers['action']['probabilities']
                actions = sorted(valid_actions(episode['state']))
                total = validate_distribution(probabilities, actions)
                if policy == 'greedy':
                    action = max(actions, key=probabilities.__getitem__)
                    draw, chosen_probability = None, probabilities[action] / total
                else:
                    action, draw, chosen_probability = categorical(probabilities, rngs[episode['id']])
                if probabilities[action] <= 0:
                    raise ValueError('Executed action must have positive support under the original distribution')
                if validation_only:
                    episode['validation_engine_decisions'] += 1
                else:
                    episode['model_decisions'] += 1
                choices[index] = {'action': action, 'probabilities': copy.deepcopy(probabilities),
                                  'actor': 'cpu_oracle_validation' if validation_only else 'student',
                                  'draw': draw, 'sampling_probability': chosen_probability,
                                  'answers': answers, 'request_id': public['id'], 'batch_id': batch_id,
                                  'public_request_sha256': hashlib.sha256(canonical_json(public).encode()).hexdigest()}
        for index, chosen in choices.items():
            episode = states[index]
            before = episode['state']
            probabilities = chosen['probabilities']
            total = validate_distribution(probabilities, valid_actions(before))
            after = step(before, chosen['action'])
            if source_group_id(after) != episode['source_map_group_id'] or source_group_id(after) in train_groups:
                raise ValueError('Rollout escaped its held-out source map')
            optimal = solve(before)['optimal_actions']  # Evaluation only; never modifies a student choice.
            actual_optimal = chosen['action'] in optimal
            p_optimal = math.fsum(probabilities[action] for action in optimal) / total
            controller_expected = (p_optimal if policy in {'sample', 'random'} else float(actual_optimal))
            coordinate = tuple(after['position'])
            revisited = episode['_visits'][coordinate] > 0
            episode['_visits'][coordinate] += 1
            episode['steps'].append({
                'state': before, 'action': chosen['action'], 'next_state': after,
                'actor': chosen['actor'], 'controller': policy, 'probabilities': probabilities,
                'raw_probability_sum': total, 'distribution_argmax': max(sorted(probabilities), key=probabilities.__getitem__),
                'sample_uniform_draw': chosen['draw'], 'selected_action_probability': chosen['sampling_probability'],
                'p_optimal': p_optimal, 'controller_expected_optimal': controller_expected,
                'optimal_action': actual_optimal, 'revisited_position': revisited,
                'visits_to_destination_after_step': episode['_visits'][coordinate],
                'model_forward': chosen['actor'] == 'student', 'forced': chosen['actor'] == 'forced_legal_action',
                'training_map_overlap': False, 'answers': chosen['answers'], 'request_id': chosen['request_id'],
                'batch_id': chosen.get('batch_id'), 'public_request_sha256': chosen.get('public_request_sha256'),
            })
            episode['state'] = after
            if after['position'] == after['goal'] or len(episode['steps']) == episode['max_steps']:
                episode['active'] = False
        tick += 1
        if progress_every and tick % progress_every == 0:
            print(json.dumps({'policy': policy, 'tick': tick, 'active_episodes': sum(row['active'] for row in states),
                              'student_forwards': total_forwards}), flush=True)
    for episode in states:
        episode['final_state'] = episode.pop('state')
        episode.pop('active')
        visits = episode.pop('_visits')
        n = len(episode['steps'])
        success = episode['final_state']['position'] == episode['final_state']['goal']
        episode.update(success=success, outcome='goal' if success else 'horizon_exhausted', steps_count=n,
                       path_efficiency=episode['shortest_path_length'] / n if success else 0.0,
                       steps_to_goal=n if success else None, unique_positions_visited=len(visits),
                       revisit_steps=sum(row['revisited_position'] for row in episode['steps']),
                       repeated_visit_rate=sum(row['revisited_position'] for row in episode['steps']) / n,
                       source_map_training_overlap=False)
    summaries = {}
    for split in sorted({episode['split'] for episode in states}):
        group = [episode for episode in states if episode['split'] == split]
        decisions = [transition for episode in group for transition in episode['steps'] if not transition['forced']]
        steps_count = sum(episode['steps_count'] for episode in group)
        summaries[split] = {
            'episodes': len(group), 'distinct_source_maps': len({row['source_map_group_id'] for row in group}),
            'outcomes': dict(Counter(row['outcome'] for row in group)),
            'completion_rate': sum(row['success'] for row in group) / len(group),
            'mean_path_efficiency': sum(row['path_efficiency'] for row in group) / len(group),
            'total_steps': steps_count, 'mean_steps': steps_count / len(group),
            'nonforced_decisions': len(decisions), 'model_decisions': sum(row['model_decisions'] for row in group),
            'forced_decisions': sum(row['forced_decisions'] for row in group),
            'actual_optimal_action_rate': sum(row['optimal_action'] for row in decisions) / len(decisions) if decisions else None,
            'mean_p_optimal': math.fsum(row['p_optimal'] for row in decisions) / len(decisions) if decisions else None,
            'mean_controller_expected_optimal': math.fsum(row['controller_expected_optimal'] for row in decisions) / len(decisions) if decisions else None,
            'step_weighted_repeated_visit_rate': sum(row['revisit_steps'] for row in group) / steps_count,
            'episode_mean_repeated_visit_rate': sum(row['repeated_visit_rate'] for row in group) / len(group),
            'training_source_map_overlap': 0,
        }
    return {
        'schema_version': 'openjev-navigation-v3-controller-v1', 'policy': policy, 'seed': seed,
        'student_measurement': uses_student and not validation_only, 'validation_only': validation_only,
        'episodes': states, 'summary': summaries, 'batches': batches, 'parallel_batches': batch_examples,
        'execution': {'forward_passes': total_forwards, 'teacher_calls': 0, 'autoregressive_decode_steps': 0,
                      'end_to_end_inference_seconds': inference_seconds,
                      'engine': 'cpu_exact_oracle_control_flow_only' if validation_only else ('local_student' if uses_student else policy)},
        'protocol': {'temperature': 1.0, 'horizon': '2*size^2', 'all_successes_and_failures_retained': True,
                     'candidate_order': 'lexicographic action IDs; no shortest-path information',
                     'greedy_tie_break': 'lexicographically first maximum',
                     'sampling': 'categorical from original T=1 probabilities; only their floating-point sum is used as normalization',
                     'rng': 'independent Random seeded by SHA256(global_seed, canonical_source_map_id, initial_state); forced steps consume no draw',
                     'rng_limit': 'Random draws do not depend on batch scheduling; the same trajectory additionally requires the same per-state probabilities, which floating-point kernels may affect.',
                     'revisit': 'destination previously visited in this episode, including the initial position; never used to change action selection',
                     'optimal_metrics': 'Nonforced decisions only; p_optimal is the original distribution mass on the exact BFS-optimal action set, while actual_optimal measures the executed action.',
                     'oracle_use': 'Only explicit oracle policy, cohort reachability, and post-decision evaluation; never a student fallback',
                     'not_enabled': ['visit_penalty', 'epsilon_exploration', 'temperature_tuning', 'cycle_early_stop', 'oracle_student_fallback']},
    }


def self_test():
    def test_renderer(state, split='rollout', candidate_order=None):
        actions = candidate_order or sorted(valid_actions(state))
        return {'state': canonical_json(state), 'questions': {'action': {'type': 'choice',
                'instructions': 'CPU test fixture; this is not a trained student.', 'criteria': {a: a for a in actions}}}}

    class CpuOracleValidationEngine:
        def __init__(self):
            self.calls = 0

        def predict(self, payload, batch_questions=0, temperature=1.0):
            assert batch_questions == 0 and temperature == 1.0
            self.calls += 1
            states = []
            for public in payload['states']:
                assert set(public) == {'id', 'state', 'questions'}
                state = json.loads(public['state'])
                optimal = solve(state)['optimal_actions']
                probabilities = {action: (1/len(optimal) if action in optimal else 0.0)
                                 for action in sorted(valid_actions(state))}
                states.append({'id': public['id'], 'answers': {'action': {
                    'type': 'choice', 'choice': max(probabilities, key=probabilities.__getitem__),
                    'probabilities': probabilities}}})
            return {'states': states, 'temperature': {'value': 1.0},
                    'execution': {'forward_passes': 0, 'network_model_calls': 0,
                                  'autoregressive_decode_steps': 0, 'validation_engine': 'exact_oracle_control_flow_only'}}

    examples = [
        {'game': 'grid_navigation', 'size': 3, 'walls': [], 'position': [2, 0], 'goal': [0, 2]},
        {'game': 'grid_navigation', 'size': 3, 'walls': [[0, 1], [1, 1]], 'position': [0, 0], 'goal': [0, 2]},
        {'game': 'grid_navigation', 'size': 4, 'walls': [[1, 1]], 'position': [3, 3], 'goal': [0, 0]},
    ]
    episodes = [{'id': f'cpu_validation_{i}', 'game': state['game'], 'split': 'test',
                 'initial_state': state, 'source_map_group_id': source_group_id(state)} for i, state in enumerate(examples)]

    class ControllerTests(unittest.TestCase):
        def test_categorical_support_and_draw(self):
            class Fixed:
                def random(self):
                    return 0.0
            self.assertEqual(categorical({'a': 0.0, 'b': 1.0}, Fixed())[0], 'b')
            with self.assertRaises(ValueError):
                validate_distribution({'a': .4, 'b': .4}, ['a', 'b'])

        def test_cpu_oracle_control_flow(self):
            for policy in ['greedy', 'sample']:
                result = rollout(episodes, policy, CpuOracleValidationEngine(), test_renderer, validation_only=True)
                self.assertFalse(result['student_measurement'])
                self.assertEqual(result['execution']['forward_passes'], 0)
                self.assertTrue(all(row['success'] and row['path_efficiency'] == 1 for row in result['episodes']))
                self.assertTrue(any(row['forced_decisions'] > 0 for row in result['episodes']))
                self.assertTrue(all(not transition['model_forward'] for row in result['episodes'] for transition in row['steps']))

        def test_rng_independent_of_episode_order_and_completion(self):
            for policy in ['sample', 'random']:
                kwargs = {'engine': CpuOracleValidationEngine(), 'renderer': test_renderer, 'validation_only': True} if policy == 'sample' else {}
                first = rollout(episodes, policy, **kwargs)
                if policy == 'sample':
                    kwargs['engine'] = CpuOracleValidationEngine()
                second = rollout(list(reversed(episodes)), policy, **kwargs)
                def choices(result):
                    return {row['id']: [(s['action'], s['sample_uniform_draw']) for s in row['steps']] for row in result['episodes']}
                self.assertEqual(choices(first), choices(second))
                for episode in episodes:
                    if policy == 'sample':
                        kwargs['engine'] = CpuOracleValidationEngine()
                    alone = rollout([episode], policy, **kwargs)
                    self.assertEqual(choices(first)[episode['id']], choices(alone)[episode['id']])

        def test_oracle_cannot_be_published_as_student(self):
            with self.assertRaises(ValueError):
                rollout(episodes, 'sample', CpuOracleValidationEngine(), test_renderer)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ControllerTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {'tests': result.testsRun, 'passed': True, 'student_measurement': False,
            'note': 'CPU exact-oracle fixtures validate control flow only; no learned model or benchmark result was produced.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('research/private_navigation_v3'))
    parser.add_argument('--checkpoint-dir', type=Path)
    parser.add_argument('--policy', choices=POLICIES, default='greedy')
    parser.add_argument('--name', default='navigation_v3')
    parser.add_argument('--per-split', type=int, default=20)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--precision', choices=['fp32', 'bf16'], default='bf16')
    parser.add_argument('--representation', choices=['ascii', 'coords'], default='coords',
                        help='Student input presentation only; the frozen evaluation maps and controller are unchanged.')
    parser.add_argument('--disable-native-triton', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--progress-every', type=int, default=12)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False))
        return
    if args.output is None:
        parser.error('--output is required for actual evaluation')
    episodes, train_groups, cohort = select_episodes(args.data_dir, args.per_split)
    engine, renderer = None, None
    if args.policy in {'greedy', 'sample'}:
        if args.checkpoint_dir is None:
            parser.error('Student controllers require --checkpoint-dir')
        from predict_toy_decisions import DecisionPredictor
        from assemble_navigation_v3_views import render_view_request
        renderer = partial(render_view_request, representation=args.representation)
        engine = DecisionPredictor(args.checkpoint_dir, precision=args.precision,
                                   disable_native_triton=args.disable_native_triton)
    result = rollout(episodes, args.policy, engine, renderer, train_groups, args.seed,
                     progress_every=args.progress_every)
    result.update(name=args.name, cohort=cohort, script_sha256=hash_file(__file__),
                  representation=args.representation if engine is not None else None,
                  checkpoint_sha256=hash_file(args.checkpoint_dir / 'best.safetensors') if engine is not None else None,
                  renderer_sha256=hash_file(Path(__file__).with_name('assemble_navigation_v3_views.py')) if renderer is not None else None,
                  base_renderer_sha256=hash_file(Path(__file__).with_name('build_navigation_v3.py')) if renderer is not None else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'output': str(args.output), 'policy': args.policy, 'summary': result['summary'],
                      'execution': result['execution']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
