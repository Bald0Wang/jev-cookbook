#!/usr/bin/env python3
"""Run parallel mixed SFT arms, select on dev games, then evaluate the winner."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from train_unified_games import file_sha256, read_unified_dataset
from unified_game_pipeline import read_rows, validate_cases


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def score_episodes(path, expected_cases, weights):
    episodes = read_rows(path)
    actual = [e['case']['id'] for e in episodes]
    expected = {c['id']: c for c in expected_cases}
    if len(set(actual)) != len(actual) or set(actual) != set(expected):
        raise ValueError('Evaluation does not cover exactly the declared cases')
    cells, split_cells = defaultdict(list), defaultdict(lambda: defaultdict(list))
    for episode in episodes:
        if episode['case'] != expected[episode['case']['id']]:
            raise ValueError('Evaluation case was modified')
        if episode.get('complete') is not True or type(episode.get('success')) is not bool:
            raise ValueError('Incomplete or non-Boolean game result')
        spec = episode['case']['spec']
        key = spec['task'] + '/policy'
        if spec['task'] == 'shooting':
            key += '/' + spec['scenario']
        cells[key].append(episode['success'])
        split_cells[episode['case']['split']][key].append(episode['success'])
    if set(cells) != set(weights):
        raise ValueError('Every comparison must contain all four policy pools')
    rates = {k: sum(v) / len(v) for k, v in cells.items()}
    return {'weighted_success': sum(weights[k] * rates[k] for k in weights),
            'rates': rates, 'counts': {k: {'successes': sum(v), 'episodes': len(v)}
                                      for k, v in cells.items()},
            'by_split': {split: {k: {'successes': sum(v), 'episodes': len(v),
                                     'success_rate': sum(v) / len(v)}
                                for k, v in groups.items()}
                         for split, groups in split_cells.items()},
            'episodes_sha256': file_sha256(path)}


def select_winner(results, arms, include_initial=True):
    order = (['initial'] if include_initial else []) + [arm['name'] for arm in arms]
    if set(results) != set(order):
        raise ValueError('Every declared arm and initialization must finish dev evaluation')
    return max(order, key=lambda name: (
        results[name]['weighted_success'],
        results[name]['rates']['shooting/policy/predict_position'],
        results[name]['rates']['shooting/policy/basic'],
        -order.index(name)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--expert-protocol', type=Path, required=True)
    parser.add_argument('--datasets', type=Path, required=True)
    parser.add_argument('--init-checkpoint', type=Path, required=True)
    parser.add_argument('--dev-cases', type=Path, required=True)
    parser.add_argument('--test-cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gpus', default='0,1,2,3')
    parser.add_argument('--baseline-gpu', default='4')
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    cfg, evaluation, arms = protocol['training'], protocol['evaluation'], protocol['arms']
    weights = protocol['population_weights']
    gpus = args.gpus.split(',')
    if len(gpus) != len(arms) or len(set(gpus + [args.baseline_gpu])) != len(gpus) + 1:
        parser.error('Use one distinct GPU per arm and another for the baseline')
    if args.output.exists():
        parser.error('Use a new output directory')
    if file_sha256(args.init_checkpoint / 'best.safetensors') != protocol['initial_weights_sha256']:
        raise ValueError('Initialization weights differ from the frozen protocol')
    dev_cases, test_cases = read_rows(args.dev_cases), read_rows(args.test_cases)
    validate_cases(dev_cases + test_cases)
    if not dev_cases or any(c['split'] != 'dev' for c in dev_cases):
        raise ValueError('Dev selection only accepts dev cases')
    if not test_cases or any(c['split'] not in ('test', 'ood') for c in test_cases):
        raise ValueError('Final evaluation only accepts test/OOD cases')
    data_hashes = {}
    for target in ('hard', 'soft'):
        _, manifest, files, _ = read_unified_dataset(args.datasets / target)
        if manifest['protocol_sha256'] != file_sha256(args.expert_protocol):
            raise ValueError('Dataset expert protocol differs from the frozen collection')
        data_hashes[target] = {str(p.relative_to(args.datasets)): file_sha256(p) for p in files}
        for split, expected in manifest['split_sha256'].items():
            if file_sha256(args.datasets / target / (split + '.jsonl')) != expected:
                raise ValueError('Dataset changed after preparation')
    args.output.mkdir(parents=True)
    (args.output / 'logs').mkdir()
    weights_path = args.output / 'population_weights.json'
    write_json(weights_path, weights)
    jobs, results = [], {}
    lock = threading.Lock()
    manifest = {'protocol': protocol, 'protocol_sha256': file_sha256(args.protocol),
                'expert_protocol_sha256': file_sha256(args.expert_protocol),
                'dev_cases_sha256': file_sha256(args.dev_cases),
                'test_cases_sha256': file_sha256(args.test_cases),
                'dataset_sha256': data_hashes, 'jobs': jobs, 'finished': False,
                'checkpoint_uploads': False, 'api_calls': 0}
    manifest_path = args.output / 'experiment.json'
    write_json(manifest_path, manifest)
    scripts = Path(__file__).resolve().parent

    def execute(name, command, gpu=None):
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   MKL_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1')
        if gpu is not None:
            env['CUDA_VISIBLE_DEVICES'] = gpu
        started = time.monotonic()
        with (args.output / 'logs' / (name + '.log')).open('x') as log:
            code = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        job = {'name': name, 'command': command, 'gpu': gpu, 'returncode': code,
               'seconds': time.monotonic() - started}
        with lock:
            jobs.append(job)
            write_json(manifest_path, manifest)
        print(json.dumps(job), flush=True)
        if code:
            raise RuntimeError(f'{name} failed; inspect its log')

    def evaluate(name, checkpoint, cases_path, cases, gpu):
        path = args.output / (name + '.jsonl')
        command = [sys.executable, str(scripts / 'unified_game_pipeline.py'), 'rollout',
                   '--cases', str(cases_path), '--output', str(path), '--engine', 'checkpoint',
                   '--checkpoint', str(checkpoint), '--controller', evaluation['controller'],
                   '--epsilon', str(evaluation['epsilon']), '--seed', str(evaluation['sampling_seed']),
                   '--splits', ','.join(sorted({c['split'] for c in cases})),
                   '--env-batch', str(evaluation['env_batch']),
                   '--batch-questions', str(evaluation['batch_questions']),
                   '--max-length', str(cfg['max_length'])]
        execute(name, command, gpu)
        execute(name + '_replay', [sys.executable, str(scripts / 'replay_unified_episodes.py'),
                '--episodes', str(path), '--output', str(args.output / (name + '_replay.json'))])
        return score_episodes(path, cases, weights)

    def train(arm, gpu):
        name = arm['name']
        checkpoint = args.output / name
        command = [sys.executable, str(scripts / 'train_unified_games.py'), '--stage', 'sft',
                   '--loss', 'ce', '--input', str(args.datasets / arm['target']),
                   '--init-checkpoint', str(args.init_checkpoint), '--output-dir', str(checkpoint),
                   '--policy-pool-weights', str(weights_path), '--seed', str(arm['seed']),
                   '--backbone-lr', str(arm['backbone_lr']), '--head-lr', str(arm['head_lr']),
                   '--precision', cfg['precision'], '--disable-native-triton']
        for key in ('steps', 'head_steps', 'batch_questions', 'microbatch_questions',
                    'max_microbatch_tokens', 'max_length', 'eval_every', 'weight_decay'):
            command.extend(['--' + key.replace('_', '-'), str(cfg[key])])
        if cfg['gradient_checkpointing']:
            command.append('--gradient-checkpointing')
        execute(name + '_train', command, gpu)
        return name, evaluate(name + '_dev', checkpoint, args.dev_cases, dev_cases, gpu)

    errors = []
    with ThreadPoolExecutor(max_workers=len(arms) + 1) as pool:
        futures = {pool.submit(train, arm, gpu): arm['name'] for arm, gpu in zip(arms, gpus)}
        baseline = pool.submit(evaluate, 'initial_dev', args.init_checkpoint,
                               args.dev_cases, dev_cases, args.baseline_gpu)
        futures[baseline] = 'initial'
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results[name] = result if name == 'initial' else result[1]
            except Exception as error:
                errors.append({'name': name, 'error': str(error)})
            with lock:
                manifest.update(dev_results=results, errors=errors)
                write_json(manifest_path, manifest)
    if errors:
        raise SystemExit('Some declared jobs failed; no model was selected')
    selected = select_winner(results, arms)
    best_new = select_winner({k: v for k, v in results.items() if k != 'initial'},
                             arms, include_initial=False)
    checkpoint = args.init_checkpoint if selected == 'initial' else args.output / selected
    selection = {'selected': selected, 'best_new_arm': best_new, 'checkpoint': str(checkpoint),
                 'weights_sha256': file_sha256(checkpoint / 'best.safetensors'),
                 'dev_results': results, 'test_results_used': False,
                 'selection_rule': evaluation['between_arm_selection']}
    write_json(args.output / 'selection.json', selection)
    print(json.dumps(selection), flush=True)
    initial_test = evaluate('initial_test', args.init_checkpoint, args.test_cases,
                            test_cases, args.baseline_gpu)
    final = (initial_test if selected == 'initial' else
             evaluate('selected_test', checkpoint, args.test_cases, test_cases, args.baseline_gpu))
    new_test = (evaluate('best_new_test', args.output / best_new, args.test_cases,
                         test_cases, args.baseline_gpu) if selected == 'initial' else final)
    manifest.update(finished=True, selection=selection, final_results=final,
                    initial_test_results=initial_test, best_new_test_results=new_test)
    write_json(manifest_path, manifest)
    print(json.dumps({'finished': True, 'selected': selected, 'final': final,
                      'initial': initial_test}), flush=True)


if __name__ == '__main__':
    main()
