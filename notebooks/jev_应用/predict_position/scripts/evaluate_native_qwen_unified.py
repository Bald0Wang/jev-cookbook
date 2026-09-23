#!/usr/bin/env python3
"""Untuned Qwen3 native-LM action probabilities across the frozen unified games.

Uses the frozen navigation baseline's full prompt, official chat template and
original vocabulary head. A-D identify all offered actions in lexicographic
order. Probabilities condition on the next token being one of those letters;
they are not probabilities of task success. No tokens are generated.
"""
import argparse
import copy
import math
from pathlib import Path
import random
import shutil
import time

from evaluate_native_qwen_navigation import (
    MODEL, REVISION, BACKEND, NativeQwenPredictor, load_tokenizer,
)
from evaluate_appo_doom import sample_with_receipt
from unified_game_pipeline import (
    SPLITS, LocalEnvironments, behavior_distribution, digest, encode, file_digest,
    policy_request, read_rows, summarize, write_json,
)

from evaluate_native_qwen_shooting import ORIGINAL_WEIGHT_SHA256, validate_native_answer
from unified_game_pipeline import validate_cases, source_hashes


def select_unified_cases(cases, splits):
    """Validate all source cases before filtering; never filter on outcomes."""
    if not cases or not splits or len(splits) != len(set(splits)) or not set(splits) <= set(SPLITS):
        raise ValueError('Expected nonempty cases and distinct known splits')
    for case in cases:
        spec = case['spec']
        if spec['task'] not in ('maze', 'snake', 'shooting'):
            raise ValueError('Unsupported unified task')
        if spec['task'] == 'shooting' and spec.get('scenario') not in ('basic', 'predict_position'):
            raise ValueError('Only Basic and Predict Position are registered shooting tasks')
    validate_cases(cases)
    selected = [c for c in cases if c['split'] in splits]
    if not selected:
        raise ValueError('No cases match the explicit splits')
    return selected


def validate_observation(obs, info):
    """Reject absent decisions and inconsistent finite-deadline flags."""
    if obs.get('task') not in ('maze', 'snake', 'shooting') or not isinstance(obs.get('state'), str):
        raise ValueError('Invalid public unified observation')
    candidates = obs.get('candidates')
    if not isinstance(candidates, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in candidates.items()):
        raise ValueError('Expected explicit nonempty action IDs and descriptions')
    for field in ('step', 'remaining_steps'):
        if type(obs.get(field)) is not int or obs[field] < 0:
            raise ValueError('Invalid public step or deadline')
    if type(info.get('terminated')) is not bool or info.get('truncated') is not False or type(info.get('success')) is not bool:
        raise ValueError('Invalid unified terminal flags')
    if info['terminated']:
        if candidates:
            raise ValueError('Terminal observations cannot offer actions')
    elif not 1 <= len(candidates) <= 4 or obs['remaining_steps'] <= 0:
        raise ValueError('Live observations need one to four actions and remaining budget')
    elif info['success']:
        raise ValueError('Task success must terminate the episode immediately')


def iter_episodes(cases, predictor, policy_id, controller='greedy', epsilon=.1,
                  seed=17, batch_states=4, environments_factory=LocalEnvironments):
    if controller not in ('greedy', 'sample') or not 0 <= epsilon <= 1 or batch_states < 1:
        raise ValueError('Invalid native action controller or state batch size')
    validate_cases(cases)
    for offset in range(0, len(cases), batch_states):
        batch = cases[offset:offset + batch_states]
        envs = environments_factory()
        try:
            current = envs.reset(batch)
            episodes = {case['id']: {'case': copy.deepcopy(case), 'continuation_policy_id': policy_id,
                                    'steps': [], 'complete': False, 'success': None} for case in batch}
            rngs = {case['id']: random.Random(int(digest([case['id'], seed])[:16], 16)) for case in batch}
            active = set(episodes)
            while active:
                requests, decisions = [], {}
                for key in sorted(active):
                    obs, info = current[key]['observation'], current[key]['info']
                    validate_observation(obs, info)
                    if info['terminated']:
                        if obs['candidates'] or info.get('truncated') or type(info['success']) is not bool:
                            raise ValueError('Invalid unified reset terminal')
                        episodes[key].update(complete=True, success=info['success'], final_info=info,
                                             final_observation=obs)
                        continue
                    if len(obs['candidates']) == 1:
                        action = next(iter(obs['candidates']))
                        decisions[key] = {'request': policy_request(obs, key),
                            'scores': {action: 1.0}, 'policy_probs': {action: 1.0},
                            'answers': {}, 'forced': True, 'model_forward': False,
                            'decision_source': 'forced_single_available_action',
                            'prediction_execution': None}
                    else:
                        requests.append(policy_request(obs, key))
                active = {key for key in active if not episodes[key]['complete']}
                if requests:
                    before_calls = predictor.calls
                    response = predictor.predict({'states': requests}, batch_questions=0, temperature=1.0)
                    if predictor.calls != before_calls + 1:
                        raise ValueError('Native actor must execute one forward per requested batch')
                    execution = response['execution']
                    if execution.get('forward_passes') != 1 or execution.get('generated_tokens') != 0:
                        raise ValueError('Native actor unexpectedly decoded or changed forward contract')
                    returned = response['states']
                    returned_ids = [r['id'] for r in returned]
                    if len(set(returned_ids)) != len(returned_ids) or set(returned_ids) != {r['id'] for r in requests}:
                        raise ValueError('Native response does not cover the requested nonforced states exactly')
                    answers = {r['id']: r['answers'] for r in returned}
                    for request in requests:
                        key = request['id']
                        scores = validate_native_answer(answers[key]['action'], request)
                        decisions[key] = {'request': request, 'scores': scores, 'policy_probs': scores,
                            'answers': answers[key], 'forced': False, 'model_forward': True,
                            'decision_source': 'untuned_qwen_original_lm_head',
                            'prediction_execution': copy.deepcopy(execution)}
                actions = {}
                for key in sorted(active):
                    behavior = behavior_distribution(decisions[key]['scores'], controller, epsilon)
                    # Match the unified collector: even forced moves consume one RNG draw.
                    action, draw = sample_with_receipt(behavior, rngs[key])
                    decisions[key].update(behavior_probs=behavior, sampling_draw=draw)
                    actions[key] = action
                if not actions:
                    break
                following = envs.step(actions)
                for key, action in actions.items():
                    transition = following[key]
                    validate_observation(transition['observation'], transition['info'])
                    if transition['terminated'] is not transition['info']['terminated'] or transition['truncated'] is not transition['info']['truncated']:
                        raise ValueError('Transition and info terminal flags differ')
                    if type(transition['reward']) not in (int, float) or not math.isfinite(transition['reward']):
                        raise ValueError('Nonfinite transition reward')
                    if transition['truncated']:
                        raise RuntimeError('External truncation is not a unified task failure label')
                    episodes[key]['steps'].append({'observation': copy.deepcopy(current[key]['observation']),
                        'action': action, **decisions[key], 'reward': transition['reward'],
                        'terminated': transition['terminated'], 'truncated': transition['truncated'],
                        'info': copy.deepcopy(transition['info'])})
                    if transition['terminated']:
                        if transition['observation']['candidates'] or type(transition['info']['success']) is not bool:
                            raise ValueError('Invalid native-run terminal outcome')
                        episodes[key].update(complete=True, success=transition['info']['success'],
                            final_info=copy.deepcopy(transition['info']),
                            final_observation=copy.deepcopy(transition['observation']))
                        active.remove(key)
                current.update(following)
            for case in batch:
                yield episodes[case['id']]
        finally:
            envs.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--splits', default='test,ood')
    parser.add_argument('--controller', choices=('greedy', 'sample'), default='greedy')
    parser.add_argument('--epsilon', type=float, default=.1)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--batch-states', type=int, default=4)
    parser.add_argument('--max-length', type=int, default=8192)
    parser.add_argument('--precision', choices=('bf16', 'fp32'), default='bf16')
    parser.add_argument('--limit', type=int, default=0, help='Explicit first-N smoke subset; zero keeps every selected case')
    args = parser.parse_args()
    manifest_path, sources = args.output.with_suffix('.manifest.json'), args.output.with_suffix('.sources')
    if any(path.exists() for path in (args.output, manifest_path, sources)):
        parser.error('Use fresh episode, manifest and source-snapshot paths')
    if args.limit < 0 or args.batch_states < 1 or args.max_length < 1 or not 0 <= args.epsilon <= 1:
        parser.error('Invalid limit, batch size, context budget or epsilon')
    cases = select_unified_cases(read_rows(args.cases), args.splits.split(','))
    cases = cases[:args.limit] if args.limit else cases
    tokenizer, snapshot, token_ids = load_tokenizer()
    weight_hashes = {p.name: file_digest(p) for p in sorted(snapshot.glob('*.safetensors'))}
    if weight_hashes != {'model.safetensors': ORIGINAL_WEIGHT_SHA256}:
        raise ValueError('Cached weights differ from the verified original Qwen checkpoint')
    implementation = source_hashes()
    implementation.update({name: file_digest(Path(__file__).with_name(name)) for name in (
        'evaluate_native_qwen_unified.py', 'evaluate_native_qwen_shooting.py',
        'evaluate_native_qwen_navigation.py', 'evaluate_appo_doom.py',
        'assemble_navigation_v3_views.py', 'evaluate_navigation_v3.py')})
    policy = {'engine': 'native_qwen_original_lm', 'display_name': 'Untuned Qwen',
        'model': MODEL, 'revision': REVISION, 'backend': BACKEND,
        'checkpoint_sha256': weight_hashes, 'original_weight_files_sha256': weight_hashes,
        'config_sha256': file_digest(snapshot / 'config.json'),
        'tokenizer_files_sha256': {name: file_digest(snapshot / name) for name in (
            'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja', 'special_tokens_map.json')
            if (snapshot / name).is_file()},
        'source_sha256': implementation, 'controller': args.controller, 'epsilon': args.epsilon,
        'sampling_seed': args.seed, 'temperature': 1.0, 'tie_break': 'lexicographic_first',
        'environment_contract': 'finite_task_deadline_v1', 'project_training_steps': 0,
        'head': 'unchanged original vocabulary output embeddings; no project decision head',
        'probability_semantics': 'next-token distribution conditional on an offered A-D token; not task-success probability',
        'prompt': 'unchanged full standard policy_request rendered by the existing native baseline prompt; official chat template, enable_thinking=False',
        'token_ids': token_ids, 'precision': args.precision, 'max_length': args.max_length,
        'truncation': False, 'generated_tokens': 0,
        'forced_singletons': 'Code action; no model forward; consumes one controller RNG draw'}
    policy_id = digest(policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sources.mkdir()
    for name in implementation:
        shutil.copy2(Path(__file__).with_name(name), sources / name)
    manifest = {'schema_version': 'nanojev-unified-episodes-v1', 'policy': policy,
        'continuation_policy_id': policy_id, 'cases_sha256': file_digest(args.cases),
        'selected_cases': [case['id'] for case in cases], 'source_snapshot': sources.name,
        'finished': False, 'limit': args.limit, 'batch_states': args.batch_states,
        'api_calls': 0, 'model_downloads': 0, 'model_training_steps': 0,
        'input_comparison': 'same standard visible-state text, question and action descriptions; native LM letter prompt differs from the learned DecisionModel input encoding'}
    write_json(manifest_path, manifest)
    engine = NativeQwenPredictor(tokenizer, snapshot, token_ids, args.max_length,
                                  args.precision, disable_native_triton=True)
    episodes, started = [], time.monotonic()
    try:
        with args.output.open('x') as handle:
            for episode in iter_episodes(cases, engine, policy_id, args.controller, args.epsilon,
                                         args.seed, args.batch_states):
                handle.write(encode(episode) + '\n')
                handle.flush()
                episodes.append(episode)
                print(encode({'case': episode['case']['id'], 'success': episode['success'],
                              'decisions': len(episode['steps']), 'completed': len(episodes)}), flush=True)
    except BaseException as error:
        manifest.update(error_type=type(error).__name__, completed_episodes=len(episodes))
        write_json(manifest_path, manifest)
        raise
    manifest.update(finished=True, episode_sha256=file_digest(args.output),
        elapsed_seconds=time.monotonic()-started, summary=summarize(episodes),
        native_forward_calls=engine.calls, native_action_questions=sum(not s['forced'] for e in episodes for s in e['steps']),
        forced_actions=sum(s['forced'] for e in episodes for s in e['steps']),
        generated_tokens=0, parameter_count=engine.parameter_count,
        max_gpu_allocated_gb=engine.torch.cuda.max_memory_allocated()/1e9)
    write_json(manifest_path, manifest)
    print(encode({'finished': True, 'episodes': len(episodes), 'summary': manifest['summary']}), flush=True)


if __name__ == '__main__':
    main()
