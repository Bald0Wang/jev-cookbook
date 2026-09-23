"""Small source/coverage/controller fixtures; no model or gameplay claims."""
import copy
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import summarize_sonic_supervision as summary
from test_native_qwen_unified import FakeNative
from unified_game_pipeline import behavior_distribution, choose, digest, encode, policy_request


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def write_rows(path, rows):
    Path(path).write_text(''.join(encode(row)+'\n' for row in rows))


def policy(engine='checkpoint', weights='initial'):
    value = {'engine': engine, 'controller': 'greedy', 'epsilon': .1, 'sampling_seed': 17,
        'temperature': 1., 'tie_break': 'lexicographic_first', 'environment_contract': 'finite_task_deadline_v1',
        'source_sha256': {'unified_grid_envs.py': 'a'*64, 'unified_doom_env.py': 'b'*64}}
    if engine == 'checkpoint':
        value['checkpoint_sha256'] = {'best.safetensors': weights}
    elif engine == 'jev':
        value['model'] = 'typesafe-ai/jev'
    else:
        value.update(original_weight_files_sha256={'model.safetensors': summary.ORIGINAL_WEIGHT_SHA256},
                     generated_tokens=0, project_training_steps=0)
    return value


def episode(case, declaration, success):
    task = case['spec']['task']
    candidates = {k: k+' in this public state' for k in (
        ('left','noop','right','shoot') if task == 'shooting' else ('north','east','west'))}
    obs = {'task': task, 'state': 'Visible state only', 'candidates': candidates, 'step': 0, 'remaining_steps': 2}
    answer = FakeNative().predict({'states': [policy_request(obs, case['id'])]})['states'][0]['answers']['action']
    scores = answer['probabilities']
    behavior = behavior_distribution(scores, 'greedy', .1)
    rng = random.Random(int(digest([case['id'],17])[:16],16))
    saved = rng.getstate()
    draw = rng.random()
    rng.setstate(saved)
    action = choose(behavior,rng)
    outcome = ('goal_reached' if success else 'deadline') if task == 'maze' else ('target_food_reached' if success else 'deadline')
    metric = {'success': success, 'outcome': outcome}
    info = {'success': success, 'terminated': True, 'truncated': False, 'episode_metrics': metric}
    if task == 'shooting':
        metric.update(kills=int(success), native_reward=-1., ammo_consumed=0., physical_ticks=1, decisions=1)
        info.update(action_id=action, requested_ticks=4, actual_ticks=1)
        reward = -1.
    else:
        metric.update(physical_steps=1, decision_steps=1, collisions=0)
        info.update(physical_steps_this_action=1)
        reward = float(success)
        if task == 'snake':
            metric.update(food_collected=int(success), target_food=1)
    step = {'observation': obs, 'scores': scores, 'answers': {'action': answer}, 'action': action,
            'sampling_draw': draw, 'behavior_probs': behavior, 'reward': reward,
            'terminated': True, 'truncated': False, 'info': info}
    return {'case': copy.deepcopy(case), 'complete': True, 'success': success,
            'continuation_policy_id': digest(declaration), 'steps': [step], 'final_info': info}


def accounting(case_ids):
    children = []
    for shard in range(2):
        cell = {'journal_sha256': str(shard)*64, 'reported_cost_usd': '.02',
            'unknown_reserved_usd': '.002', 'accounted_usd': '.022',
            'started_calls': 3, 'succeeded_calls': 2, 'failed_calls': 1,
            'unresolved_started_ids': [], 'unknown_cost_ids': ['same-call-id-in-different-shards'],
            'zero_reported_cost_calls': 0}
        children.append({'shard': shard, 'manifest_sha256': 'c'*64, 'episode_sha256': 'd'*64,
            'cases_sha256': 'e'*64, 'budget_usd': '1.5', 'accounting': cell})
    return {'parallel_children': children,
        'episode_journal_shards': {cid: i%2 for i,cid in enumerate(case_ids)},
        'reported_cost_usd': '.04', 'unknown_reserved_usd': '.004', 'unknown_reservation_count': 2,
        'accounting_scope': 'Fixture-only accounting'}


def save_run(path, cases, case_sha, declaration, success):
    episodes = [episode(c, declaration, success(c)) for c in cases]
    write_rows(path, episodes)
    manifest = {'schema_version': 'nanojev-unified-episodes-v1', 'finished': True,
        'episode_sha256': summary.sha256_file(path), 'cases_sha256': case_sha,
        'selected_cases': [c['id'] for c in cases], 'policy': declaration,
        'continuation_policy_id': digest(declaration)}
    if declaration['engine'] == 'jev':
        manifest.update(accounting(manifest['selected_cases']))
    write_json(path.with_suffix('.manifest.json'), manifest)
    return episodes, manifest


class SonicSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases = []
        for si, split in enumerate(('test','ood')):
            for ti, task in enumerate(summary.WEIGHTS):
                for number in range(2 if task in ('basic','predict_position') else 1):
                    spec = {'task': task, 'size': 8, 'max_steps': 8}
                    if task in ('basic','predict_position'):
                        spec = {'task': 'shooting', 'scenario': task, 'frame_skip': 4, 'max_steps': 75}
                    self.cases.append({'id': f'{split}-{task}-{number}', 'split': split,
                        'seed': 10000+1000*si+100*ti+number, 'variant': task, 'spec': spec})
        self.case_path = self.root/'cases.jsonl'
        write_rows(self.case_path, self.cases)
        self.case_sha = summary.sha256_file(self.case_path)
        self.cases_by_id = {c['id']: c for c in self.cases}
        self.path = self.root/'initial_test.jsonl'
        self.episodes, self.manifest = save_run(self.path, self.cases, self.case_sha, policy(), lambda c: c['spec']['task']=='shooting')

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, episodes=None, manifest=None):
        episodes = self.episodes if episodes is None else episodes
        manifest = self.manifest if manifest is None else manifest
        write_rows(self.path, episodes)
        manifest['episode_sha256'] = summary.sha256_file(self.path)
        write_json(self.path.with_suffix('.manifest.json'), manifest)

    def load(self):
        return summary.load_primary('initial', self.path, self.cases_by_id, self.case_sha, 'checkpoint', 'initial')

    def test_valid_run_and_weighted_macro_do_not_microaverage(self):
        result = summary.statistics(self.load(), self.cases_by_id)
        self.assertEqual(len(self.cases),12)
        self.assertAlmostEqual(result['macro_by_split']['test']['success_rate'],1/3)
        self.assertNotAlmostEqual(result['macro_by_split']['test']['success_rate'],4/6)
        self.assertEqual(result['by_split_category']['test/maze']['n'],1)

    def test_missing_case_rejected_even_if_its_manifest_is_consistent(self):
        episodes, manifest = copy.deepcopy(self.episodes[:-1]), copy.deepcopy(self.manifest)
        manifest['selected_cases'] = [e['case']['id'] for e in episodes]
        self.rewrite(episodes,manifest)
        with self.assertRaisesRegex(ValueError,'missing or extra'):
            self.load()

    def test_changed_spec_or_seed_cannot_hide_behind_same_case_id(self):
        for field in ('seed','spec'):
            episodes = copy.deepcopy(self.episodes)
            if field == 'seed':
                episodes[0]['case']['seed'] += 1
            else:
                episodes[0]['case']['spec']['max_steps'] += 1
            self.rewrite(episodes,copy.deepcopy(self.manifest))
            with self.assertRaisesRegex(ValueError,'definition/spec/seed'):
                self.load()

    def test_changed_controller_rejected_after_consistent_policy_rehash(self):
        episodes, manifest = copy.deepcopy(self.episodes), copy.deepcopy(self.manifest)
        manifest['policy']['epsilon'] = .15
        manifest['continuation_policy_id'] = digest(manifest['policy'])
        for e in episodes:
            e['continuation_policy_id'] = manifest['continuation_policy_id']
        self.rewrite(episodes,manifest)
        with self.assertRaisesRegex(ValueError,'controller/engine'):
            self.load()

    def test_behavior_or_terminal_corruption_rejected(self):
        for mutate in (lambda e: e['steps'][0]['behavior_probs'].update(north=1.),
                       lambda e: e['steps'][0].update(action='unsupported'),
                       lambda e: e['steps'][0].update(truncated=True),
                       lambda e: e['final_info']['episode_metrics'].update(outcome='goal_reached')):
            episodes = copy.deepcopy(self.episodes)
            mutate(episodes[0])
            self.rewrite(episodes,copy.deepcopy(self.manifest))
            with self.assertRaises(ValueError):
                self.load()

    def test_incomplete_or_hash_mismatch_is_not_a_result(self):
        self.manifest['finished'] = False
        self.rewrite()
        with self.assertRaisesRegex(ValueError,'not finished'):
            self.load()
        self.manifest['finished'] = True
        self.manifest['episode_sha256'] = 'f'*64
        write_json(self.path.with_suffix('.manifest.json'),self.manifest)
        with self.assertRaisesRegex(ValueError,'does not match'):
            self.load()

    def test_native_original_identity_and_probability_receipts(self):
        save_run(self.path,self.cases,self.case_sha,policy('native_qwen_original_lm'),lambda c: False)
        run = summary.load_primary('native',self.path,self.cases_by_id,self.case_sha,'native_qwen_original_lm')
        self.assertEqual(run['validation']['matched_episodes'],12)
        man = summary.read_json(self.path.with_suffix('.manifest.json'))
        man['policy']['original_weight_files_sha256']['model.safetensors'] = 'wrong'
        man['continuation_policy_id'] = digest(man['policy'])
        episodes = summary.read_rows(self.path)
        for ep in episodes:
            ep['continuation_policy_id'] = man['continuation_policy_id']
        self.rewrite(episodes,man)
        with self.assertRaisesRegex(ValueError,'original vocabulary'):
            summary.load_primary('native',self.path,self.cases_by_id,self.case_sha,'native_qwen_original_lm')

    def test_pairing_direction_is_model_wins_minus_jev_wins(self):
        a = [{'id':'a','success':False},{'id':'b','success':True},{'id':'c','success':False}]
        b = [{'id':'a','success':True},{'id':'b','success':True},{'id':'c','success':True}]
        result = summary.paired(a,b)
        self.assertEqual((result['wins_vs_jev'],result['losses_vs_jev']),(2,0))
        self.assertEqual(result['success_rate_delta_vs_jev'],2/3)
        with self.assertRaises(ValueError):
            summary.paired(a,b[:-1])

    def test_accounting_keeps_shard_namespaces_and_unknown_reservations(self):
        man = accounting(self.cases_by_id)
        result = summary.api_accounting(man,self.cases_by_id)
        self.assertEqual(result['reported_cost_usd'],'0.04')
        self.assertEqual(result['unknown_reserved_usd'],'0.004')
        self.assertEqual(result['accounted_usd'],'0.044')
        for mutate in (lambda m: m.update(reported_cost_usd='.01'),
                       lambda m: m['parallel_children'][1].update(shard=0),
                       lambda m: m['episode_journal_shards'].pop(next(iter(self.cases_by_id)))):
            broken = copy.deepcopy(man)
            mutate(broken)
            with self.assertRaises(ValueError):
                summary.api_accounting(broken,self.cases_by_id)

    def test_schema_requires_all_tasks_and_splits(self):
        write_rows(self.case_path,[c for c in self.cases if c['spec']['task']!='maze'])
        with self.assertRaisesRegex(ValueError,'all four'):
            summary.registry(self.case_path)

    def test_recovery_attempt_directories_do_not_duplicate_cumulative_fees(self):
        manifest = accounting(self.cases_by_id)
        expected = summary.api_accounting(manifest, self.cases_by_id)
        for child in manifest['parallel_children']:
            prefix = f"/backup/run/shard_{child['shard']:02d}"
            child['manifest'] = prefix + '/attempt_02/episodes.manifest.json'
            child['journal'] = f"/backup/journals/shard_{child['shard']:02d}"
            child['attempts'] = [
                {'attempt': 1, 'episodes': prefix+'/attempt_01/episodes.jsonl',
                 'returncode': 1, 'started_elapsed_seconds': 0., 'finished_elapsed_seconds': 10.},
                {'attempt': 2, 'episodes': prefix+'/attempt_02/episodes.jsonl',
                 'returncode': 0, 'started_elapsed_seconds': 40., 'finished_elapsed_seconds': 50.}]
        actual = summary.api_accounting(manifest, self.cases_by_id)
        for key in ('reported_cost_usd', 'unknown_reserved_usd', 'accounted_usd',
                    'successful_requests', 'failed_requests'):
            self.assertEqual(actual[key], expected[key])
        self.assertEqual(actual['reported_cost_usd'], '0.04')

    def test_prior_interrupted_requests_remain_reserved_after_recovery(self):
        manifest = accounting(self.cases_by_id)
        cell = manifest['parallel_children'][0]['accounting']
        cell['unresolved_started_ids'] = ['prior-interrupted-call']
        cell['unknown_cost_ids'].append('prior-interrupted-call')
        cell['unknown_reserved_usd'] = '.004'
        cell['accounted_usd'] = '.024'
        manifest['unknown_reserved_usd'] = '.006'
        manifest['unknown_reservation_count'] = 3
        result = summary.api_accounting(manifest, self.cases_by_id)
        self.assertEqual(result['reported_cost_usd'], '0.04')
        self.assertEqual(result['unknown_reserved_usd'], '0.006')
        self.assertEqual(result['accounted_usd'], '0.046')

    def test_end_to_end_outputs_are_complete_and_expert_is_separate(self):
        selected = self.root/'selected_test.jsonl'
        save_run(selected,self.cases,self.case_sha,policy(weights='trained'),lambda c: True)
        jev, native = self.root/'jev.jsonl', self.root/'native.jsonl'
        save_run(jev,self.cases,self.case_sha,policy('jev'),lambda c: False)
        save_run(native,self.cases,self.case_sha,policy('native_qwen_original_lm'),lambda c: False)
        pools = {'maze/policy':1/3,'snake/policy':1/3,'shooting/policy/basic':1/6,'shooting/policy/predict_position':1/6}
        dev = {name:{'rates':{k:rate for k in pools},'weighted_success':rate} for name,rate in [('initial',.1),('trained',.2)]}
        selection = {'selected':'trained','best_new_arm':'trained','weights_sha256':'trained',
            'dev_results':dev,'test_results_used':False}
        experiment = {'finished':True,'test_cases_sha256':self.case_sha,'selection':selection,
            'protocol':{'arms':[{'name':'trained'}],'initial_weights_sha256':'initial','population_weights':pools}}
        write_json(self.root/'experiment.json',experiment)
        write_json(self.root/'selection.json',selection)
        args = SimpleNamespace(cases=self.case_path,experiment=self.root,jev=jev,native=native,
                               expert='fixture',expert_protocol='fixture')
        expert = {'comparison_scope':'Separate RGB expert, greedy epsilon=0.', 'by_split':{}}
        with patch.object(summary,'expert_reference',return_value=expert):
            report = summary.build(args)
        self.assertTrue(report['passed'])
        self.assertEqual(report['cases']['episodes'],12)
        self.assertNotIn('visual_expert_reference',report['runs'])
        self.assertIn('greedy epsilon=0',summary.markdown(report))
        self.assertEqual(report['runs']['selected']['macro_by_split']['test']['success_rate'],1.)
        self.assertTrue(all(x['wins_vs_jev'] == x['n'] for x in report['runs']['selected']['paired_vs_jev'].values()))


if __name__ == '__main__':
    unittest.main()
