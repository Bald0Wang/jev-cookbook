#!/usr/bin/env python3
"""Untuned Qwen3 native-LM action probabilities in the standard Basic simulator.

Uses the frozen navigation baseline's full prompt, official chat template and
original vocabulary head. A-D identify all offered actions in lexicographic
order. Probabilities condition on the next token being one of those letters;
they are not probabilities of task success. No tokens are generated.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import time

from evaluate_native_qwen_navigation import (
    MODEL, REVISION, BACKEND, NativeQwenPredictor, build_prompt, load_tokenizer,
)
from evaluate_appo_doom import sample_with_receipt, select_cases
from unified_game_pipeline import (
    SPLITS, LocalEnvironments, behavior_distribution, digest, encode, file_digest,
    policy_request, read_rows, summarize, write_json,
)

ORIGINAL_WEIGHT_SHA256 = 'f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b'


def validate_native_answer(answer, request):
    prompt, labels = build_prompt(request)
    keys = set(labels)
    if answer.get('type') != 'choice' or answer.get('backend') != BACKEND:
        raise ValueError('Expected the original native vocabulary action head')
    if answer.get('prompt_sha256') != hashlib.sha256(prompt.encode()).hexdigest():
        raise ValueError('Native prompt does not match the complete standard request')
    mappings = answer.get('candidate_to_token', {})
    if set(mappings) != keys or any(mappings[k].get('text') != labels[k] for k in keys):
        raise ValueError('Native option letters differ from lexicographic action mapping')
    ids = [mappings[k].get('id') for k in keys]
    if any(type(i) is not int or i < 0 for i in ids) or len(set(ids)) != len(keys):
        raise ValueError('Option letters require distinct native token IDs')
    probs, logits = answer.get('probabilities', {}), answer.get('native_option_logits', {})
    unconditional = answer.get('native_option_unconditional_probs', {})
    for field in (probs, logits, unconditional):
        if set(field) != keys or any(type(v) not in (float, int) or not math.isfinite(v) for v in field.values()):
            raise ValueError('Native score keys or finite values are invalid')
    if any(not 0 <= v <= 1 for field in (probs, unconditional) for v in field.values()):
        raise ValueError('Native probabilities are outside [0,1]')
    if abs(math.fsum(probs.values()) - 1) > 1e-6:
        raise ValueError('Native conditional probabilities do not sum to one')
    maximum = max(logits.values())
    denominator = math.fsum(math.exp(v - maximum) for v in logits.values())
    if any(abs(probs[k] - math.exp(logits[k] - maximum) / denominator) > 1e-6 for k in keys):
        raise ValueError('Conditional probabilities differ from offered-token softmax')
    mass = math.fsum(unconditional.values())
    if type(answer.get('offered_token_mass')) not in (float, int) or not math.isfinite(answer['offered_token_mass']):
        raise ValueError('Missing finite offered-token mass')
    if mass > 1 + 1e-6 or abs(mass - answer['offered_token_mass']) > 1e-6:
        raise ValueError('Recorded unconditional option-token mass differs')
    # Extremely small float32 probabilities can underflow, while the stable
    # offered-logit softmax remains defined; retain such observations verbatim.
    if mass > 1e-20 and any(abs(unconditional[k] / mass - probs[k]) > 2e-5 for k in keys):
        raise ValueError('Unconditional and conditional option probabilities disagree')
    return dict(probs)


def iter_episodes(cases, predictor, policy_id, controller='greedy', epsilon=.1,
                  seed=17, batch_states=4, environments_factory=LocalEnvironments):
    if controller not in ('greedy', 'sample') or not 0 <= epsilon <= 1 or batch_states < 1:
        raise ValueError('Invalid native action controller or state batch size')
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
                requests = []
                for key in sorted(active):
                    obs, info = current[key]['observation'], current[key]['info']
                    if info['terminated']:
                        if obs['candidates'] or info.get('truncated') or type(info['success']) is not bool:
                            raise ValueError('Invalid Basic reset terminal')
                        episodes[key].update(complete=True, success=info['success'], final_info=info,
                                             final_observation=obs)
                        continue
                    if obs['task'] != 'shooting' or set(obs['candidates']) != {'left', 'right', 'shoot', 'noop'}:
                        raise ValueError('Standard Basic must offer exactly its original four actions')
                    payload = json.loads(obs['state'])
                    if payload['scenario'] != 'basic' or payload['screen_size'] != [320, 240]:
                        raise ValueError('Use the standard Basic 320x240 observation')
                    requests.append(policy_request(obs, key))
                active = {key for key in active if not episodes[key]['complete']}
                if not requests:
                    break
                before_calls = predictor.calls
                response = predictor.predict({'states': requests}, batch_questions=0, temperature=1.0)
                if predictor.calls != before_calls + 1:
                    raise ValueError('The native actor must execute one forward per active-state batch')
                execution = response['execution']
                if execution.get('forward_passes') != 1 or execution.get('generated_tokens') != 0:
                    raise ValueError('Native baseline unexpectedly decoded tokens or changed its forward contract')
                returned = response['states']
                returned_ids = [r['id'] for r in returned]
                if len(set(returned_ids)) != len(returned_ids) or set(returned_ids) != active:
                    raise ValueError('Native response does not cover every active state exactly once')
                answers = {r['id']: r['answers'] for r in returned}
                decisions, actions = {}, {}
                for request in requests:
                    key = request['id']
                    scores = validate_native_answer(answers[key]['action'], request)
                    behavior = behavior_distribution(scores, controller, epsilon)
                    action, draw = sample_with_receipt(behavior, rngs[key])
                    decisions[key] = {'request': request, 'scores': scores, 'policy_probs': scores,
                        'answers': answers[key], 'behavior_probs': behavior, 'sampling_draw': draw,
                        'forced': False, 'decision_source': 'untuned_qwen_original_lm_head',
                        'prediction_execution': copy.deepcopy(execution)}
                    actions[key] = action
                following = envs.step(actions)
                for key, action in actions.items():
                    transition = following[key]
                    if transition['truncated']:
                        raise RuntimeError('External truncation is not a Basic task failure label')
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
    parser.add_argument('--limit', type=int, default=0, help='Explicit first-N smoke subset; zero keeps every selected Basic case')
    args = parser.parse_args()
    manifest_path, sources = args.output.with_suffix('.manifest.json'), args.output.with_suffix('.sources')
    if any(path.exists() for path in (args.output, manifest_path, sources)):
        parser.error('Use fresh episode, manifest and source-snapshot paths')
    if args.limit < 0 or args.batch_states < 1 or args.max_length < 1 or not 0 <= args.epsilon <= 1:
        parser.error('Invalid limit, batch size, context budget or epsilon')
    cases = select_cases(read_rows(args.cases), args.splits.split(','))
    cases = cases[:args.limit] if args.limit else cases
    tokenizer, snapshot, token_ids = load_tokenizer()
    weight_hashes = {p.name: file_digest(p) for p in sorted(snapshot.glob('*.safetensors'))}
    if weight_hashes != {'model.safetensors': ORIGINAL_WEIGHT_SHA256}:
        raise ValueError('Cached weights differ from the verified original Qwen checkpoint')
    implementation = {name: file_digest(Path(__file__).with_name(name)) for name in (
        'evaluate_native_qwen_shooting.py', 'evaluate_native_qwen_navigation.py',
        'evaluate_appo_doom.py', 'unified_game_pipeline.py', 'unified_doom_env.py')}
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
        'truncation': False, 'generated_tokens': 0}
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
        native_forward_calls=engine.calls, native_action_questions=sum(len(e['steps']) for e in episodes),
        generated_tokens=0, parameter_count=engine.parameter_count,
        max_gpu_allocated_gb=engine.torch.cuda.max_memory_allocated()/1e9)
    write_json(manifest_path, manifest)
    print(encode({'finished': True, 'episodes': len(episodes), 'summary': manifest['summary']}), flush=True)


if __name__ == '__main__':
    main()
