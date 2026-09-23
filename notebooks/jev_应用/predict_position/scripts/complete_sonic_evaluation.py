#!/usr/bin/env python3
"""Finish a stopped Sonic runner with two concurrent, unchanged full-cohort runs.

Only scheduling changes. Both model identities and the dev-only selection are
verified before any heldout inference. Existing outputs are never replaced.
A failed evaluation leaves experiment.finished false and retains its receipt.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from run_sonic_supervision import score_episodes, select_winner
from summarize_unified_games import load_run
from unified_game_pipeline import digest, file_digest, read_rows, source_hashes, validate_cases

CHECKPOINT_FILES = ('config.json', 'best.safetensors', 'tokenizer/tokenizer.json', 'backbone_config/config.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.completion.tmp')
    with temporary.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def launcher_exited(pid):
    require(type(pid) is int and pid > 0 and pid != os.getpid(), 'Specify the actual former launcher PID')
    proc = Path('/proc')/str(pid)
    if Path('/proc').is_dir():
        if not proc.exists():
            return {'pid': pid, 'status': 'absent', 'checked_at': datetime.now(timezone.utc).isoformat()}
        stat = (proc/'stat').read_text()
        state = stat.rsplit(')', 1)[1].split()[0]
        require(state in ('Z', 'X'), 'Former launcher is still live or only paused; terminate it before takeover')
        return {'pid': pid, 'status': state, 'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        os.kill(pid, 0)  # Liveness check only, not a delivered signal.
    except ProcessLookupError:
        return {'pid': pid, 'status': 'absent', 'checked_at': datetime.now(timezone.utc).isoformat()}
    except PermissionError:
        raise ValueError('Cannot prove that the former launcher has exited') from None
    raise ValueError('Former launcher still exists; require an exited process')


def expected_jobs(arms):
    return ([a['name']+'_train' for a in arms]
            + [name+'_dev' for name in ['initial']+[a['name'] for a in arms]]
            + [name+'_dev_replay' for name in ['initial']+[a['name'] for a in arms]])


def verify_job_history(experiment, arms):
    require(experiment.get('finished') is False and not experiment.get('errors'),
            'Only an unfinished experiment with no train/dev failures can be completed')
    require(len(arms) == 4 and len({a['name'] for a in arms}) == 4, 'Exactly four declared training arms are required')
    jobs = experiment.get('jobs', [])
    for name in expected_jobs(arms):
        found = [job for job in jobs if job.get('name') == name]
        require(len(found) == 1 and type(found[0].get('returncode')) is int and found[0]['returncode'] == 0,
                'Missing, duplicated or unsuccessful prerequisite job: '+name)
        require(isinstance(found[0].get('command'), list) and found[0]['command'], 'Missing original job command: '+name)
    return copy.deepcopy(jobs)


def checkpoint_hashes(path):
    return {name: file_digest(Path(path)/name) for name in CHECKPOINT_FILES}


def verify_replay(path, episode_path, manifest_path, expected_cases, sources):
    replay = read_json(path)
    ids = [case['id'] for case in expected_cases]
    require(replay.get('schema') == 'nanojev-unified-replay-v1' and replay.get('passed') is True
            and replay.get('errors') == [], 'Replay did not pass: '+str(path))
    require(replay.get('episodes_sha256') == file_digest(episode_path)
            and replay.get('collection_manifest_sha256') == file_digest(manifest_path),
            'Replay is stale relative to its exact episode/manifest bytes')
    require(replay.get('replay_source_sha256') == sources
            and replay.get('collection_declared_source_sha256') == sources, 'Replay source versions differ')
    rows = replay.get('episodes', [])
    require([row['id'] for row in rows] == ids and all(row.get('passed') is True for row in rows),
            'Replay coverage or per-episode completion differs')
    totals = replay.get('summary', {})
    require(totals.get('episodes') == len(ids) and totals.get('passed_episodes') == len(ids)
            and totals.get('failed_episodes') == 0 and totals.get('mismatches') == 0,
            'Replay aggregate counts differ')
    return file_digest(path)


def verify_evaluation(name, path, case_path, cases, checkpoint, evaluation, weights, sources, replay_path):
    run = load_run(name, path)
    manifest_path = Path(path).with_suffix('.manifest.json')
    manifest = read_json(manifest_path)
    declaration = run['policy']
    require(run['cases_sha256'] == file_digest(case_path), 'Rollout case-file SHA differs')
    require(manifest['selected_cases'] == [case['id'] for case in cases], 'Rollout case order differs')
    require(declaration.get('engine') == 'checkpoint' and declaration.get('source_sha256') == sources
            and digest(declaration) == run['continuation_policy_id'], 'Rollout engine/source/policy identity differs')
    for key, expected in (('controller', evaluation['controller']), ('epsilon', evaluation['epsilon']),
                          ('sampling_seed', evaluation['sampling_seed']), ('temperature', 1.),
                          ('tie_break', 'lexicographic_first'), ('environment_contract', 'finite_task_deadline_v1')):
        require(declaration.get(key) == expected, 'Rollout controller differs: '+key)
    require(declaration.get('checkpoint_sha256') == checkpoint_hashes(checkpoint),
            'Actual checkpoint bundle differs from rollout identity')
    snapshot = Path(path).parent/manifest['source_snapshot']
    require(all(file_digest(snapshot/name) == sha for name, sha in sources.items()), 'Rollout source snapshot differs')
    replay_sha = verify_replay(replay_path, path, manifest_path, cases, sources)
    score = score_episodes(path, cases, weights)
    return score, {'episodes_sha256': file_digest(path), 'manifest_sha256': file_digest(manifest_path),
                   'replay_sha256': replay_sha, 'checkpoint_sha256': declaration['checkpoint_sha256']}


def verify_selection(selection, experiment, dev_results, arms, initial_weights, arm_weights):
    require(selection.get('test_results_used') is False, 'Selection must be declared dev-only')
    require(selection.get('dev_results') == dev_results and experiment.get('dev_results') == dev_results,
            'Recorded selection/dev scores differ from actual replay-verified dev episodes')
    selected = select_winner(dev_results, arms)
    best_new = select_winner({k:v for k,v in dev_results.items() if k != 'initial'}, arms, include_initial=False)
    require(selection.get('selected') == selected and selection.get('best_new_arm') == best_new,
            'Selection differs from the predeclared dev rule')
    expected_sha = initial_weights if selected == 'initial' else arm_weights[selected]
    require(selection.get('weights_sha256') == expected_sha, 'Selection weight SHA differs')
    require('selection' not in experiment or experiment['selection'] == selection,
            'Experiment contains a different selection receipt')
    return selected, best_new


def outputs_for(root, name):
    episode = root/(name+'.jsonl')
    return [episode, episode.with_suffix('.manifest.json'), episode.with_suffix('.sources'),
            root/(name+'_replay.json'), root/'logs'/(name+'.log'), root/'logs'/(name+'_replay.log')]


def require_fresh(paths):
    for path in paths:
        require(not Path(path).exists(), 'Archive the existing output first; refusing to replace: '+str(path))


def commands(root, name, checkpoint, case_path, cases, protocol):
    scripts = Path(__file__).resolve().parent
    evaluation, cfg = protocol['evaluation'], protocol['training']
    path = root/(name+'.jsonl')
    rollout = [sys.executable, str(scripts/'unified_game_pipeline.py'), 'rollout',
        '--cases', str(case_path), '--output', str(path), '--engine', 'checkpoint',
        '--checkpoint', str(checkpoint), '--controller', evaluation['controller'],
        '--epsilon', str(evaluation['epsilon']), '--seed', str(evaluation['sampling_seed']),
        '--splits', ','.join(sorted({case['split'] for case in cases})),
        '--env-batch', str(evaluation['env_batch']), '--batch-questions', str(evaluation['batch_questions']),
        '--max-length', str(cfg['max_length'])]
    replay = [sys.executable, str(scripts/'replay_unified_episodes.py'), '--episodes', str(path),
              '--output', str(root/(name+'_replay.json'))]
    return rollout, replay


def preflight(args):
    root = Path(args.experiment).resolve()
    launcher = launcher_exited(args.original_launcher_pid)
    experiment_path, selection_path = root/'experiment.json', root/'selection.json'
    experiment, selection = read_json(experiment_path), read_json(selection_path)
    protocol = read_json(args.protocol)
    require(experiment.get('protocol') == protocol and experiment.get('protocol_sha256') == file_digest(args.protocol),
            'Original training protocol or hash differs')
    require(experiment.get('expert_protocol_sha256') == file_digest(args.expert_protocol), 'Expert protocol SHA differs')
    arms, weights, evaluation = protocol['arms'], protocol['population_weights'], protocol['evaluation']
    old_jobs = verify_job_history(experiment, arms)
    require(evaluation['controller'] == 'greedy' and evaluation['epsilon'] == .1
            and evaluation['sampling_seed'] == 17 and evaluation['env_batch'] == 16,
            'Frozen evaluation controller or environment batch differs')
    dev_cases, test_cases = read_rows(args.dev_cases), read_rows(args.test_cases)
    require(len(dev_cases) == 146 and all(c['split'] == 'dev' for c in dev_cases), 'Expected all 146 original dev cases')
    require(len(test_cases) == 548 and all(c['split'] in ('test','ood') for c in test_cases), 'Expected all 548 heldout cases')
    validate_cases(dev_cases+test_cases)
    require(experiment['dev_cases_sha256'] == file_digest(args.dev_cases)
            and experiment['test_cases_sha256'] == file_digest(args.test_cases), 'Frozen case file hash differs')
    sources = source_hashes()
    initial = Path(args.init_checkpoint).resolve()
    initial_sha = file_digest(initial/'best.safetensors')
    require(initial_sha == protocol['initial_weights_sha256'], 'Initialization weights changed')
    snapshots, arm_weights = {'initial': initial}, {}
    train_audit = {}
    for arm in arms:
        name = arm['name']
        checkpoint = root/name
        config, summary = read_json(checkpoint/'config.json'), read_json(checkpoint/'summary.json')
        sha = file_digest(checkpoint/'best.safetensors')
        require(summary.get('completed_steps') == protocol['training']['steps'] + protocol['training']['head_steps']
                and summary.get('weights_sha256') == sha and summary.get('selected_on') == 'dev only',
                'Training incomplete or selected checkpoint differs: '+name)
        require(config.get('init_weights_sha256') == initial_sha and config.get('stage') == 'sft'
                and config.get('loss') == 'ce' and config.get('population_weights') == weights,
                'Training initialization, objective or population weights differ: '+name)
        for key, expected in {**protocol['training'], 'seed': arm['seed'],
                               'backbone_lr': arm['backbone_lr'], 'head_lr': arm['head_lr']}.items():
            require(config.get(key) == expected, 'Training setting differs: '+name+'/'+key)
        require(config.get('implementation_sha256') == file_digest(Path(__file__).with_name('train_unified_games.py')),
                'Training implementation changed after the run')
        expected_data = experiment['dataset_sha256'][arm['target']]
        declared_data = config.get('data_sha256', {})
        require(len(declared_data) == len(expected_data) and
                {Path(k).name: v for k, v in declared_data.items()} ==
                {Path(k).name: v for k, v in expected_data.items()},
                'Training dataset hashes differ from the frozen experiment: '+name)
        arm_weights[name], snapshots[name] = sha, checkpoint
        train_audit[name] = {'weights_sha256': sha, 'config_sha256': file_digest(checkpoint/'config.json'),
                             'summary_sha256': file_digest(checkpoint/'summary.json')}
    dev_results, dev_audit = {}, {}
    for name in ['initial']+[arm['name'] for arm in arms]:
        result, audit = verify_evaluation(name, root/(name+'_dev.jsonl'), args.dev_cases, dev_cases,
            snapshots[name], evaluation, weights, sources, root/(name+'_dev_replay.json'))
        dev_results[name], dev_audit[name] = result, audit
    selected, best_new = verify_selection(selection, experiment, dev_results, arms, initial_sha, arm_weights)
    require(selection.get('selection_rule') == evaluation['between_arm_selection'], 'Selection-rule declaration differs')
    require(Path(selection['checkpoint']).resolve() == snapshots[selected].resolve(), 'Selected checkpoint path differs')
    gpu_ids = args.gpus.split(',')
    require(len(gpu_ids) == 2 and len(set(gpu_ids)) == 2 and all(g.isdigit() for g in gpu_ids), 'Use two distinct GPU indices')
    second_name = 'best_new_test' if selected == 'initial' else 'selected_test'
    second_checkpoint = snapshots[best_new if selected == 'initial' else selected]
    jobs = [{'name': 'initial_test', 'checkpoint': str(initial), 'gpu': gpu_ids[0]},
            {'name': second_name, 'checkpoint': str(second_checkpoint), 'gpu': gpu_ids[1]}]
    receipt_path = root/'evaluation_completion.json'
    archive_path = root/'evaluation_completion.original_experiment.json'
    paths = [receipt_path, archive_path]
    for job in jobs:
        paths.extend(outputs_for(root, job['name']))
        job['rollout_command'], job['replay_command'] = commands(root, job['name'], job['checkpoint'], args.test_cases, test_cases, protocol)
    require_fresh(paths)
    return {'root': root, 'experiment': experiment, 'experiment_sha256': file_digest(experiment_path),
        'selection': selection, 'selection_sha256': file_digest(selection_path), 'protocol': protocol,
        'sources': sources, 'launcher': launcher, 'old_jobs': old_jobs, 'jobs': jobs,
        'dev_audit': dev_audit, 'training_audit': train_audit, 'test_cases': test_cases,
        'test_cases_path': str(args.test_cases), 'receipt_path': receipt_path, 'archive_path': archive_path}


def finish_manifest(plan, results, new_jobs, receipt_sha):
    expected = {job['name'] for job in plan['jobs']}
    require(set(results) == expected and len(new_jobs) == 4 and all(job['returncode'] == 0 for job in new_jobs),
            'Both complete rollouts and replays must succeed before finalization')
    require(file_digest(plan['root']/'experiment.json') == plan['experiment_sha256'],
            'Original experiment changed during takeover; refusing to overwrite another writer')
    selected_initial = plan['selection']['selected'] == 'initial'
    initial = results['initial_test']
    final = initial if selected_initial else results['selected_test']
    best_new = results['best_new_test'] if selected_initial else final
    updated = copy.deepcopy(plan['experiment'])
    updated['jobs'] = plan['old_jobs']+new_jobs
    updated.setdefault('runtime_overrides', []).append({
        'reason': 'Original launcher exited after dev-only selection; run the two complete final evaluations concurrently on separate GPUs. No cohort, model, controller, batch, or environment change.',
        'completion_receipt': plan['receipt_path'].name, 'completion_receipt_sha256': receipt_sha,
        'original_experiment_sha256': plan['experiment_sha256'], 'original_launcher': plan['launcher'],
        'gpus': [j['gpu'] for j in plan['jobs']]})
    updated.update(finished=True, selection=plan['selection'], final_results=final,
                   initial_test_results=initial, best_new_test_results=best_new)
    atomic_json(plan['root']/'experiment.json', updated)
    return updated


def complete(plan, executor=subprocess.run):
    root, receipt_path = plan['root'], plan['receipt_path']
    # Snapshot before any result writing. This file is new and contains no new test results.
    with plan['archive_path'].open('x') as handle:
        json.dump(plan['experiment'], handle, indent=2, allow_nan=False)
        handle.write('\n')
    receipt = {'schema_version': 'nanojev-sonic-evaluation-completion-v1', 'finished': False, 'passed': False,
        'created_at': datetime.now(timezone.utc).isoformat(), 'script_sha256': file_digest(__file__),
        'original_experiment_sha256': plan['experiment_sha256'], 'selection_sha256': plan['selection_sha256'],
        'source_sha256': plan['sources'], 'original_launcher': plan['launcher'],
        'training_audit': plan['training_audit'], 'dev_replay_audit': plan['dev_audit'],
        'execution_plan': plan['jobs'], 'jobs': [], 'errors': [], 'results': {},
        'test_results_used_for_selection': False, 'api_calls': 0,
        'scheduling_change': 'Two full-cohort evaluations in parallel; each preserves original case order and env_batch=16.'}
    lock = threading.Lock()
    atomic_json(receipt_path, receipt)

    def execute(name, command, gpu):
        env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1', CUDA_VISIBLE_DEVICES=gpu)
        started = time.monotonic()
        logfile = root/'logs'/(name+'.log')
        with logfile.open('x') as log:
            process = executor(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        job = {'name': name, 'command': command, 'gpu': gpu, 'returncode': process.returncode,
               'seconds': time.monotonic()-started, 'log_sha256': file_digest(logfile),
               'job_origin': 'complete_sonic_evaluation.py', 'source_sha256': plan['sources']}
        with lock:
            receipt['jobs'].append(job)
            atomic_json(receipt_path, receipt)
        require(process.returncode == 0, 'Completion job failed: '+name)

    def evaluate(job):
        name = job['name']
        execute(name, job['rollout_command'], job['gpu'])
        execute(name+'_replay', job['replay_command'], '')
        result, audit = verify_evaluation(name, root/(name+'.jsonl'), plan['test_cases_path'],
            plan['test_cases'], job['checkpoint'], plan['protocol']['evaluation'],
            plan['protocol']['population_weights'], plan['sources'], root/(name+'_replay.json'))
        with lock:
            receipt['results'][name] = result
            receipt.setdefault('evaluation_audit', {})[name] = audit
            atomic_json(receipt_path, receipt)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(evaluate, job): job['name'] for job in plan['jobs']}
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as error:
                with lock:
                    receipt['errors'].append({'name': futures[future], 'type': type(error).__name__, 'message': str(error)})
                    atomic_json(receipt_path, receipt)
    receipt['finished'] = True
    if receipt['errors']:
        atomic_json(receipt_path, receipt)
        raise RuntimeError('At least one completion job failed; original experiment remains unfinished')
    try:
        require(source_hashes() == plan['sources'], 'Source implementation changed during evaluation')
        require(file_digest(root/'selection.json') == plan['selection_sha256'], 'Selection changed during evaluation')
        receipt['passed'] = True
        atomic_json(receipt_path, receipt)
        updated = finish_manifest(plan, receipt['results'], receipt['jobs'], file_digest(receipt_path))
    except BaseException as error:
        receipt.update(passed=False, finalization_error={'type': type(error).__name__, 'message': str(error)})
        atomic_json(receipt_path, receipt)
        raise
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('experiment', 'protocol', 'expert-protocol', 'dev-cases', 'test-cases', 'init-checkpoint'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--original-launcher-pid', type=int, required=True)
    parser.add_argument('--gpus', default='4,5')
    args = parser.parse_args()
    plan = preflight(args)
    lockpath = plan['root']/'.evaluation_completion.lock'
    with lockpath.open('x') as handle:
        handle.write(str(os.getpid())+'\n')
    try:
        launcher_exited(args.original_launcher_pid)
        require_fresh([plan['receipt_path'], plan['archive_path']]+[p for job in plan['jobs'] for p in outputs_for(plan['root'], job['name'])])
        complete(plan)
        print(json.dumps({'finished': True, 'receipt': str(plan['receipt_path']),
                          'selected': plan['selection']['selected'], 'evaluations': [j['name'] for j in plan['jobs']]}))
    finally:
        lockpath.unlink()


if __name__ == '__main__':
    main()
