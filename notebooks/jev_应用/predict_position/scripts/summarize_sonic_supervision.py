#!/usr/bin/env python3
"""Summarize the frozen Sonic mixed-SFT comparison, with no inference or network.

Complete matched case sets are mandatory. Expert collection is a separate
RGB/greedy-zero-exploration reference, never a same-controller primary run.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import random

from summarize_unified_games import group_stats, is_num, load_run, sha256_file
from summarize_appo_supervision import mcnemar_exact
from unified_game_pipeline import behavior_distribution, digest, policy_request, read_rows, validate_cases
from evaluate_native_qwen_shooting import ORIGINAL_WEIGHT_SHA256, validate_native_answer

WEIGHTS = {'maze': 1/3, 'snake': 1/3, 'basic': 1/6, 'predict_position': 1/6}
SPLITS = ('test', 'ood')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def category(case):
    spec = case['spec']
    value = spec['scenario'] if spec['task'] == 'shooting' else spec['task']
    require(value in WEIGHTS, 'Unexpected task or shooting scenario')
    return value


def registry(path):
    cases = read_rows(path)
    require(cases, 'Case registry cannot be empty')
    validate_cases(cases)
    require(all(c['split'] in SPLITS for c in cases), 'Primary cases must be test/OOD only')
    cells = Counter((c['split'], category(c)) for c in cases)
    require(set(cells) == {(s, t) for s in SPLITS for t in WEIGHTS},
            'Primary cohort must cover all four categories in both splits')
    return {c['id']: c for c in cases}


def money(value):
    require(not isinstance(value, bool), 'Boolean accounting amount')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid accounting amount') from None
    require(result.is_finite() and result >= 0, 'Negative or nonfinite accounting amount')
    return result


def api_accounting(manifest, case_ids):
    children = manifest.get('parallel_children')
    require(isinstance(children, list) and children, 'Jev needs the completed parallel accounting manifest')
    shards, journal_hashes = set(), set()
    reported, reserved, successes, failures = Decimal(0), Decimal(0), 0, 0
    records = []
    for child in children:
        shard = child['shard']
        require(type(shard) is int and shard >= 0 and shard not in shards, 'Repeated or invalid journal shard')
        shards.add(shard)
        accounting = child['accounting']
        journal_sha = accounting['journal_sha256']
        require(isinstance(journal_sha, str) and len(journal_sha) == 64, 'Missing journal hash')
        require(journal_sha not in journal_hashes, 'One journal appears in multiple budget shards')
        journal_hashes.add(journal_sha)
        cost, unknown = money(accounting['reported_cost_usd']), money(accounting['unknown_reserved_usd'])
        require(money(accounting['accounted_usd']) == cost + unknown, 'Child accounting sum differs')
        require(cost + unknown <= money(child['budget_usd']) + Decimal('0.000000001'),
                'Child accounting exceeds its application allocation')
        reported += cost
        reserved += unknown
        successes += accounting['succeeded_calls']
        failures += accounting['failed_calls']
        records.append({'shard': shard, 'manifest_sha256': child['manifest_sha256'],
                        'episode_sha256': child['episode_sha256'], 'cases_sha256': child['cases_sha256'],
                        'budget_usd': child['budget_usd'], 'accounting': accounting})
    require(set(manifest.get('episode_journal_shards', {})) == set(case_ids), 'Missing episode-to-journal assignment')
    require(set(manifest['episode_journal_shards'].values()) <= shards, 'Unknown episode journal shard')
    require(reported == money(manifest['reported_cost_usd']) and
            reserved == money(manifest['unknown_reserved_usd']), 'Merged API accounting differs from shards')
    require(manifest['unknown_reservation_count'] == sum(len(c['accounting']['unknown_cost_ids']) for c in children),
            'Unknown-cost reservation count differs')
    require(sum((money(c['budget_usd']) for c in children), Decimal(0)) <= Decimal('3.000000001'),
            'Parallel allocations exceed the frozen $3 application cap')
    return {'reported_cost_usd': str(reported), 'unknown_reserved_usd': str(reserved),
            'accounted_usd': str(reported+reserved), 'successful_requests': successes,
            'failed_requests': failures, 'children': records,
            'receipt_identity': '(journal shard, call ID)',
            'scope': manifest.get('accounting_scope'),
            'verification': 'Recomputed from the completed parallel manifest; not a live gateway balance or independent billing audit.'}


def verify_episode(episode, case, policy):
    """Recompute the executed seeded controller and physical-counter consistency."""
    require(episode['case'] == case, 'Case definition/spec/seed differs from the frozen registry')
    require(episode.get('complete') is True and type(episode.get('success')) is bool, 'Incomplete or non-Boolean outcome')
    steps, final = episode['steps'], episode['final_info']
    require(final.get('terminated') is True and final.get('truncated') is False and
            final.get('success') is episode['success'], 'Invalid final terminal status')
    require(steps, 'This registered cohort requires a nonempty trajectory')
    require(final == steps[-1]['info'], 'Final info differs from the actual terminal transition')
    rng = random.Random(int(digest([case['id'], policy['sampling_seed']])[:16], 16))
    physical, rewards = 0, []
    for index, step in enumerate(steps):
        where = f"{case['id']} decision {index}"
        obs, info = step['observation'], step['info']
        require(obs['task'] == case['spec']['task'] and isinstance(obs['state'], str), where + ': invalid public input')
        require(type(obs['remaining_steps']) is int and obs['remaining_steps'] > 0, where + ': exhausted live deadline')
        candidates, scores = obs['candidates'], step['scores']
        require(1 <= len(candidates) <= 4 and set(scores) == set(candidates), where + ': action support differs')
        require(all(is_num(x) and 0 <= x <= 1 for x in scores.values()) and
                abs(math.fsum(scores.values())-1) <= 1e-6, where + ': malformed Choice probabilities')
        forced = len(candidates) == 1
        require(bool(step.get('forced', False)) == forced, where + ': forced-action declaration differs')
        if forced:
            require(step['answers'] == {} and next(iter(scores.values())) == 1., where + ': forced inference receipt differs')
        else:
            require(step['answers']['action']['probabilities'] == scores, where + ': model probabilities differ from scores')
            if policy['engine'] == 'native_qwen_original_lm':
                validate_native_answer(step['answers']['action'], policy_request(obs, case['id']))
        if 'request' in step:
            require(step['request'] == policy_request(obs, case['id']), where + ': full request differs')
        expected = behavior_distribution(scores, 'greedy', .1)
        require(set(step['behavior_probs']) == set(expected) and all(
            is_num(step['behavior_probs'][k]) and abs(step['behavior_probs'][k]-v) <= 1e-12
            for k, v in expected.items()), where + ': epsilon behavior differs')
        draw, cumulative, action = rng.random(), 0., sorted(expected)[-1]
        for key in sorted(expected):
            cumulative += expected[key]
            if draw < cumulative:
                action = key
                break
        require(step['action'] == action, where + ': executed action differs from seeded behavior')
        if 'sampling_draw' in step:
            require(step['sampling_draw'] == draw, where + ': RNG receipt differs')
        require(step['truncated'] is False and step['terminated'] is (index == len(steps)-1), where + ': terminal chain differs')
        require(info['terminated'] is step['terminated'] and info['truncated'] is False, where + ': transition flags differ')
        reward = step['reward']
        require(is_num(reward), where + ': nonfinite reward')
        rewards.append(reward)
        metric = info['episode_metrics']
        if obs['task'] == 'shooting':
            duration = info['actual_ticks']
            require(type(duration) is int and 1 <= duration <= info['requested_ticks'] <= case['spec']['frame_skip'], where + ': invalid physical ticks')
            physical += duration
            require(obs['step'] == index and metric['decisions'] == index+1 and metric['physical_ticks'] == physical,
                    where + ': physical/decision clock differs')
            require(info['action_id'] == action, where + ': physical action differs')
        else:
            duration = info['physical_steps_this_action']
            require(type(duration) is int and duration >= 1, where + ': invalid physical movement count')
            require(obs['step'] == physical, where + ': pre-action physical clock differs')
            physical += duration
            require(metric['physical_steps'] == physical and metric['decision_steps'] == index+1,
                    where + ': macro/decision counter differs')
            require(physical <= case['spec']['max_steps'], where + ': task deadline exceeded')
    metric = final['episode_metrics']
    require(metric['success'] is episode['success'], 'Final metric success differs')
    if case['spec']['task'] == 'shooting':
        require(is_num(metric['kills']) and (metric['kills'] > 0) is episode['success'], 'Doom success differs from actual kills')
        require(abs(math.fsum(rewards)-metric['native_reward']) <= 1e-9 and metric['ammo_consumed'] >= 0,
                'Doom reward/ammo accounting differs')
    elif case['spec']['task'] == 'snake':
        expected_success = metric['food_collected'] >= metric['target_food'] and metric['collisions'] == 0
        require(expected_success is episode['success'], 'Snake food/collision success differs')
    else:
        require((metric['outcome'] == 'goal_reached') is episode['success'], 'Maze goal outcome differs')
    if 'final_observation' in episode:
        require(episode['final_observation']['candidates'] == {}, 'Terminal observation still offers actions')
    return len(steps)


def load_primary(name, path, cases, case_sha, engine, checkpoint_sha=None):
    run = load_run(name, path)
    require(run['cases_sha256'] == case_sha, name + ': original complete case-file hash differs')
    require(set(run['cases']) == set(cases), name + ': primary cohort missing or extra cases')
    policy = run['policy']
    require(digest(policy) == run['continuation_policy_id'], name + ': policy identity hash differs')
    expected = {'engine': engine, 'controller': 'greedy', 'epsilon': .1, 'sampling_seed': 17,
                'temperature': 1., 'tie_break': 'lexicographic_first', 'environment_contract': 'finite_task_deadline_v1'}
    require(all(policy.get(k) == v for k, v in expected.items()), name + ': primary controller/engine contract differs')
    if engine == 'checkpoint':
        require(isinstance(policy.get('checkpoint_sha256'), dict) and
                policy['checkpoint_sha256'].get('best.safetensors') == checkpoint_sha,
                name + ': learned checkpoint differs from selection receipt')
    elif engine == 'native_qwen_original_lm':
        require(policy.get('original_weight_files_sha256') == {'model.safetensors': ORIGINAL_WEIGHT_SHA256}
                and policy.get('project_training_steps') == 0 and policy.get('generated_tokens') == 0,
                'Untuned baseline must use the verified original vocabulary head and weights')
    else:
        require(policy.get('model') == 'typesafe-ai/jev', 'Jev model identity differs')
    checked = 0
    for episode in read_rows(path):
        require(episode['case']['id'] in cases, name + ': unknown episode')
        checked += verify_episode(episode, cases[episode['case']['id']], policy)
    run['validation'] = {'matched_episodes': len(run['episodes']), 'controller_transitions_checked': checked,
                         'physical_replay_performed_by_this_script': False}
    return run


def paired(reference, other):
    a, b = {e['id']: e for e in reference}, {e['id']: e for e in other}
    require(a and a.keys() == b.keys(), 'Paired comparison requires identical case IDs')
    wins = sorted(k for k in a if b[k]['success'] and not a[k]['success'])
    losses = sorted(k for k in a if a[k]['success'] and not b[k]['success'])
    both = sum(a[k]['success'] and b[k]['success'] for k in a)
    return {'n': len(a), 'wins_vs_jev': len(wins), 'losses_vs_jev': len(losses),
            'both_success': both, 'both_failure': len(a)-len(wins)-len(losses)-both,
            'success_rate_delta_vs_jev': (len(wins)-len(losses))/len(a),
            'exact_mcnemar_two_sided_p': mcnemar_exact(len(wins), len(losses)),
            'p_adjustment': 'none; descriptive planned comparisons',
            'win_case_ids': wins, 'loss_case_ids': losses}


def statistics(run, cases):
    cells = {f'{s}/{t}': group_stats([e for e in run['episodes'] if e['split'] == s and category(cases[e['id']]) == t])
             for s in SPLITS for t in WEIGHTS}
    return {'by_split_category': cells, 'macro_by_split': {
        s: {'success_rate': math.fsum(WEIGHTS[t]*cells[f'{s}/{t}']['success_rate'] for t in WEIGHTS),
            'weights': WEIGHTS, 'interval': None} for s in SPLITS}}


def expert_reference(path, protocol_path):
    from prepare_sonic_supervision import load_protocol, validate_collection, validate_episode
    protocol, cases, protocol_sha = load_protocol(protocol_path)
    run = load_run('visual_expert_reference', path)
    manifest = read_json(Path(path).with_suffix('.manifest.json'))
    validate_collection(manifest, protocol, cases, protocol_sha)
    count = 0
    with Path(path).open() as handle:
        for line in handle:
            if not line.strip():
                continue
            require(count < len(cases), 'Extra expert episode')
            validate_episode(json.loads(line), cases[count], manifest)
            count += 1
    require(count == len(cases), 'Missing expert episodes')
    require(run['policy']['controller'] == 'greedy' and run['policy']['epsilon'] == 0.,
            'Expected separate zero-exploration expert reference')
    return {'source': provenance(run), 'episodes': count,
            'by_split': {s: group_stats([e for e in run['episodes'] if e['split'] == s])
                         for s in protocol['case_counts']},
            'comparison_scope': 'PP RGB expert collection, greedy epsilon=0. Uses old-material synchronized rendering and recurrent pixel inputs. Not a same-observation or same-controller primary comparison.'}


def provenance(run):
    return {k: run[k] for k in ('episodes_path', 'manifest_path', 'episodes_sha256', 'manifest_sha256',
                                'cases_sha256', 'continuation_policy_id', 'policy')}


def build(args):
    case_path = Path(args.cases)
    cases, case_sha = registry(case_path), sha256_file(case_path)
    root = Path(args.experiment)
    experiment, selection = read_json(root/'experiment.json'), read_json(root/'selection.json')
    protocol = experiment['protocol']
    require(experiment.get('finished') is True and not experiment.get('errors'), 'Experiment is not completely finished')
    require(experiment.get('test_cases_sha256') == case_sha, 'Experiment case file differs')
    require(experiment.get('selection') == selection and selection.get('test_results_used') is False,
            'Selection receipt differs or used heldout results')
    require(protocol['population_weights'] == {
        'maze/policy': 1/3, 'snake/policy': 1/3, 'shooting/policy/basic': 1/6,
        'shooting/policy/predict_position': 1/6}, 'Population weighting changed')
    # Check the declared dev-only selection, without using any heldout outcome.
    names = ['initial'] + [a['name'] for a in protocol['arms']]
    dev = selection['dev_results']
    require(set(dev) == set(names), 'Missing declared dev arm')
    def rank(name):
        result = dev[name]
        require(set(result['rates']) == set(protocol['population_weights']) and
                all(is_num(v) and 0 <= v <= 1 for v in result['rates'].values()) and
                is_num(result['weighted_success']), 'Invalid declared dev rates')
        expected = math.fsum(protocol['population_weights'][k]*result['rates'][k] for k in protocol['population_weights'])
        require(abs(expected-result['weighted_success']) <= 1e-12, 'Dev weighted score differs')
        return (result['weighted_success'], result['rates']['shooting/policy/predict_position'],
                result['rates']['shooting/policy/basic'], -names.index(name))
    require(max(names, key=rank) == selection['selected'], 'Dev selected arm differs from the frozen rule')
    require(max(names[1:], key=rank) == selection['best_new_arm'], 'Dev best-new arm differs')
    selected_initial = selection['selected'] == 'initial'
    initial_sha = protocol['initial_weights_sha256']
    paths = {'initial': root/'initial_test.jsonl',
             'selected': root/('initial_test.jsonl' if selected_initial else 'selected_test.jsonl'),
             'jev': Path(args.jev), 'untuned_qwen': Path(args.native)}
    shas = {'initial': initial_sha, 'selected': selection['weights_sha256']}
    if selected_initial:
        require(shas['selected'] == initial_sha, 'Selected initialization SHA differs')
        paths['best_new'] = root/'best_new_test.jsonl'
        summary = read_json(root/selection['best_new_arm']/'summary.json')
        shas['best_new'] = summary['weights_sha256']
    runs = {name: load_primary(name, path, cases, case_sha,
            'jev' if name == 'jev' else 'native_qwen_original_lm' if name == 'untuned_qwen' else 'checkpoint',
            shas.get(name)) for name, path in paths.items()}
    env_fields = ('unified_grid_envs.py', 'unified_doom_env.py')
    for field in env_fields:
        require(all(r['policy'].get('source_sha256', {}).get(field) for r in runs.values()), 'Missing environment source hash')
        require(len({r['policy']['source_sha256'][field] for r in runs.values()}) == 1,
                'Primary environment source implementations differ: '+field)
    summaries = {}
    for name, run in runs.items():
        summary = {'source': provenance(run), 'validation': run['validation'], **statistics(run, cases)}
        if name != 'jev':
            summary['paired_vs_jev'] = {f'{s}/{t}': paired(
                [e for e in runs['jev']['episodes'] if e['split'] == s and category(cases[e['id']]) == t],
                [e for e in run['episodes'] if e['split'] == s and category(cases[e['id']]) == t])
                for s in SPLITS for t in WEIGHTS}
            summary['macro_delta_vs_jev'] = {s: math.fsum(
                WEIGHTS[t]*summary['paired_vs_jev'][f'{s}/{t}']['success_rate_delta_vs_jev'] for t in WEIGHTS)
                for s in SPLITS}
        summaries[name] = summary
    return {'schema_version': 'nanojev-sonic-supervision-summary-v1', 'passed': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'cases': {'path': str(case_path), 'sha256': case_sha, 'episodes': len(cases),
                      'counts': dict(Counter(f"{c['split']}/{category(c)}" for c in cases.values()))},
            'experiment': {'path': str(root/'experiment.json'), 'sha256': sha256_file(root/'experiment.json'),
                           'selection_sha256': sha256_file(root/'selection.json'), 'selection': selection,
                           'dev_selection_note': 'Rule recomputed from recorded dev scores; no heldout outcomes used. This script does not rerun dev models.'},
            'primary_controller': {'controller': 'greedy', 'epsilon': .1, 'sampling_seed': 17, 'temperature': 1.},
            'runs': summaries,
            'api_accounting': api_accounting(read_json(Path(args.jev).with_suffix('.manifest.json')), cases),
            'expert_reference': expert_reference(args.expert, args.expert_protocol),
            'notes': ['All primary runs cover the exact same complete frozen cases; no result-dependent filtering.',
                      'Macro weights are Maze 1/3, Snake 1/3, Basic 1/6 and PP 1/6; no 548-case micro-average headline.',
                      'Wilson intervals describe episode-level rates; exact McNemar tests use paired episode outcomes.',
                      'Expert-action fit is not eventual-success calibration. No probability-calibration claim is made here.',
                      'Controller and recorded physical counters are verified; independent simulator replay is a separate artifact.']}


def markdown(report):
    lines = ['# Sonic mixed-SFT evaluation', '',
             f"Complete matched cohort: {report['cases']['episodes']} episodes. Primary controller: greedy, epsilon 0.1, seed 17.", '',
             'Models are selected from dev results. Test and OOD results remain separate.', '']
    labels = {'maze': 'Maze', 'snake': 'Snake', 'basic': 'Basic', 'predict_position': 'Predict Position'}
    for split in SPLITS:
        lines.extend([f'## {split.upper()}', '', '| Run | Maze | Snake | Basic | Predict Position | Weighted macro |',
                      '|---|---:|---:|---:|---:|---:|'])
        for name, run in report['runs'].items():
            cells = run['by_split_category']
            values = [f"{cells[f'{split}/{t}']['successes']}/{cells[f'{split}/{t}']['n']}" for t in WEIGHTS]
            lines.append('| '+name+' | '+' | '.join(values)+f" | {run['macro_by_split'][split]['success_rate']:.2%} |")
        lines.extend(['', 'Macro: Maze 1/3, Snake 1/3, Basic 1/6, Predict Position 1/6.', '',
                      '| Run vs Jev | Task | Wins | Losses | Rate difference | Exact paired p |',
                      '|---|---|---:|---:|---:|---:|'])
        for name, run in report['runs'].items():
            for task in WEIGHTS if name != 'jev' else []:
                pair = run['paired_vs_jev'][f'{split}/{task}']
                lines.append(f"| {name} | {labels[task]} | {pair['wins_vs_jev']} | {pair['losses_vs_jev']} | {pair['success_rate_delta_vs_jev']:+.2%} | {pair['exact_mcnemar_two_sided_p']:.4g} |")
        lines.append('')
    expert = report['expert_reference']
    lines.extend(['## Visual expert reference', '', expert['comparison_scope'], '', '| Split | PP successes |', '|---|---:|'])
    for split, cell in expert['by_split'].items():
        lines.append(f"| {split} | {cell['successes']}/{cell['n']} |")
    fees = report['api_accounting']
    lines.extend(['', '## Provenance and accounting', '',
        f"Cases SHA256: `{report['cases']['sha256']}`.",
        f"Selected weights SHA256: `{report['experiment']['selection']['weights_sha256']}`.",
        f"API reported cost: ${fees['reported_cost_usd']}; unknown-cost reservations: ${fees['unknown_reserved_usd']}.",
        fees['verification'], '', 'Detailed Wilson intervals, physical counters, source hashes and paired case IDs are in `summary.json`.', ''])
    lines.extend('- '+note for note in report['notes'])
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cases', 'experiment', 'jev', 'native', 'expert', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--expert-protocol', type=Path, default=Path('configs/sonic_predict_supervision_v1.json'))
    args = parser.parse_args()
    require(not args.output.exists(), 'Use a fresh output directory')
    report = build(args)
    args.output.mkdir(parents=True)
    (args.output/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (args.output/'summary.md').write_text(markdown(report))
    print(json.dumps({'passed': True, 'episodes': report['cases']['episodes'], 'runs': list(report['runs']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
