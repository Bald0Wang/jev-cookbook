"""Small takeover/transaction checks; no model, simulator, server, or API."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import complete_sonic_evaluation as completion


def write(path, value):
    Path(path).write_text(json.dumps(value)+'\n')


def arms():
    return [{'name': name} for name in ('hard_high','soft_high','hard_low','soft_low')]


def jobs():
    return [{'name': name, 'returncode': 0, 'command': ['fixture',name]}
            for name in completion.expected_jobs(arms())]


def scores():
    result = {}
    for name, value in [('initial',.1),('hard_high',.3),('soft_high',.2),('hard_low',.3),('soft_low',.2)]:
        result[name] = {'weighted_success': value, 'rates': {
            'shooting/policy/predict_position': .4, 'shooting/policy/basic': .5}}
    return result


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'logs').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, selected='hard_high'):
        initial = selected == 'initial'
        selection = {'selected': selected, 'best_new_arm':'hard_high', 'test_results_used':False}
        original = {'finished':False, 'jobs':jobs(), 'dev_results':scores(), 'retained':'unchanged'}
        write(self.root/'experiment.json',original)
        write(self.root/'selection.json',selection)
        names = ['initial_test','best_new_test' if initial else 'selected_test']
        scheduled = [{'name':name,'checkpoint':'fixture-checkpoint','gpu':str(4+i),
                      'rollout_command':['fixture','rollout',name],
                      'replay_command':['fixture','replay',name]} for i,name in enumerate(names)]
        return {'root':self.root,'experiment':original,'experiment_sha256':completion.file_digest(self.root/'experiment.json'),
            'selection':selection,'selection_sha256':completion.file_digest(self.root/'selection.json'),
            'protocol':{'evaluation':{},'population_weights':{}},'sources':{'fixture':'hash'},
            'launcher':{'pid':123,'status':'absent'},'old_jobs':copy.deepcopy(original['jobs']),
            'jobs':scheduled,'training_audit':{},'dev_audit':{},'test_cases':[],
            'test_cases_path':'fixture-cases', 'receipt_path':self.root/'evaluation_completion.json',
            'archive_path':self.root/'evaluation_completion.original_experiment.json'}

    def test_exact_four_train_five_dev_five_replay_success_records(self):
        original = {'finished':False,'jobs':jobs()}
        self.assertEqual(len(completion.verify_job_history(original,arms())),14)
        for mutate in (lambda e:e['jobs'].pop(),
                       lambda e:e['jobs'].append(copy.deepcopy(e['jobs'][0])),
                       lambda e:e['jobs'][0].update(returncode=1),
                       lambda e:e.update(finished=True)):
            broken = copy.deepcopy(original)
            mutate(broken)
            with self.assertRaises(ValueError):
                completion.verify_job_history(broken,arms())

    def test_dev_selection_recomputed_and_weight_hash_bound(self):
        dev = scores()
        selection = {'test_results_used':False,'dev_results':dev,'selected':'hard_high',
                     'best_new_arm':'hard_high','weights_sha256':'sha-hard_high'}
        experiment = {'dev_results':dev}
        weights = {a['name']:'sha-'+a['name'] for a in arms()}
        self.assertEqual(completion.verify_selection(selection,experiment,dev,arms(),'initial',weights),
                         ('hard_high','hard_high'))
        for field, value in (('test_results_used',True),('selected','hard_low'),('weights_sha256','other')):
            broken = copy.deepcopy(selection)
            broken[field] = value
            with self.assertRaises(ValueError):
                completion.verify_selection(broken,experiment,dev,arms(),'initial',weights)

    def test_original_cli_preserves_full_case_order_and_environment_batch(self):
        protocol = {'evaluation':{'controller':'greedy','epsilon':.1,'sampling_seed':17,
                                'env_batch':16,'batch_questions':16},'training':{'max_length':8192}}
        cases = [{'id':str(i),'split':'test' if i%2 else 'ood'} for i in range(548)]
        before = copy.deepcopy(cases)
        command, replay = completion.commands(self.root,'initial_test','weights','all_cases.jsonl',cases,protocol)
        self.assertEqual(command[command.index('--cases')+1],'all_cases.jsonl')
        self.assertEqual(command[command.index('--env-batch')+1],'16')
        self.assertEqual(command[command.index('--splits')+1],'ood,test')
        self.assertNotIn('--limit',command)
        self.assertEqual(cases,before)
        self.assertIn('initial_test_replay.json',replay[-1])

    def test_existing_partial_or_log_is_never_replaced(self):
        for target in completion.outputs_for(self.root,'initial_test'):
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text('existing')
            with self.assertRaises(ValueError):
                completion.require_fresh([target])
            self.assertEqual(target.read_text(),'existing')
            target.unlink()

    def test_replay_must_bind_exact_bytes_and_all_successful_case_checks(self):
        episodes, manifest, audit = self.root/'dev.jsonl', self.root/'dev.manifest.json', self.root/'dev_replay.json'
        episodes.write_text('fixture source bytes\n')
        manifest.write_text('fixture manifest bytes\n')
        sources = {'environment.py':'fixed'}
        report = {'schema':'nanojev-unified-replay-v1','passed':True,'errors':[],
            'episodes_sha256':completion.file_digest(episodes),
            'collection_manifest_sha256':completion.file_digest(manifest),
            'replay_source_sha256':sources,'collection_declared_source_sha256':sources,
            'episodes':[{'id':'a','passed':True},{'id':'b','passed':True}],
            'summary':{'episodes':2,'passed_episodes':2,'failed_episodes':0,'mismatches':0}}
        cases = [{'id':'a'},{'id':'b'}]
        write(audit,report)
        self.assertEqual(completion.verify_replay(audit,episodes,manifest,cases,sources),completion.file_digest(audit))
        for mutate in (lambda r:r.update(episodes_sha256='wrong'),
                       lambda r:r['episodes'][0].update(passed=False),
                       lambda r:r['episodes'].pop(),
                       lambda r:r['summary'].update(mismatches=1)):
            broken = copy.deepcopy(report)
            mutate(broken)
            write(audit,broken)
            with self.assertRaises(ValueError):
                completion.verify_replay(audit,episodes,manifest,cases,sources)

    def test_a_live_current_process_cannot_be_accepted_as_exited_launcher(self):
        with self.assertRaises(ValueError):
            completion.launcher_exited(os.getpid())

    def fake_evaluation(self, name, *args):
        return {'name':name,'fixture_only':True}, {'verified_fixture':True}

    def test_parallel_completion_retains_history_and_finalizes_only_after_both(self):
        plan = self.plan()
        barrier = threading.Barrier(2)
        seen, guard = [], threading.Lock()
        def executor(command, **kwargs):
            if command[1] == 'rollout':
                barrier.wait(timeout=3)
                self.assertIn(kwargs['env']['CUDA_VISIBLE_DEVICES'],('4','5'))
            else:
                self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'],'')
            with guard:
                seen.append(tuple(command))
            kwargs['stdout'].write('fixture job completed\n')
            return SimpleNamespace(returncode=0)
        with patch.object(completion,'verify_evaluation',side_effect=self.fake_evaluation), \
             patch.object(completion,'source_hashes',return_value=plan['sources']):
            result = completion.complete(plan,executor)
        self.assertTrue(result['finished'])
        self.assertEqual(result['jobs'][:14],plan['old_jobs'])
        self.assertEqual(len(result['jobs']),18)
        self.assertEqual(len(seen),4)
        self.assertEqual(result['final_results']['name'],'selected_test')
        self.assertEqual(result['best_new_test_results'],result['final_results'])
        self.assertEqual(completion.read_json(plan['archive_path']),plan['experiment'])
        self.assertTrue(completion.read_json(plan['receipt_path'])['passed'])

    def test_initial_selection_preserves_initial_as_final_and_new_arm_separately(self):
        plan = self.plan('initial')
        with patch.object(completion,'verify_evaluation',side_effect=self.fake_evaluation), \
             patch.object(completion,'source_hashes',return_value=plan['sources']):
            result = completion.complete(plan,lambda *args,**kwargs:SimpleNamespace(returncode=0))
        self.assertEqual(result['final_results'],result['initial_test_results'])
        self.assertEqual(result['best_new_test_results']['name'],'best_new_test')

    def test_failed_job_leaves_original_unfinished_and_keeps_error_receipt(self):
        plan = self.plan()
        original_sha = plan['experiment_sha256']
        def executor(command, **kwargs):
            return SimpleNamespace(returncode=1 if command[2]=='selected_test' else 0)
        with patch.object(completion,'verify_evaluation',side_effect=self.fake_evaluation):
            with self.assertRaisesRegex(RuntimeError,'remains unfinished'):
                completion.complete(plan,executor)
        self.assertEqual(completion.file_digest(self.root/'experiment.json'),original_sha)
        receipt = completion.read_json(plan['receipt_path'])
        self.assertFalse(receipt['passed'])
        self.assertTrue(receipt['finished'])
        self.assertEqual(len(receipt['errors']),1)

    def test_concurrent_experiment_writer_is_not_overwritten(self):
        plan = self.plan()
        write(self.root/'experiment.json',{'finished':False,'external_change':True})
        changed = completion.file_digest(self.root/'experiment.json')
        with patch.object(completion,'verify_evaluation',side_effect=self.fake_evaluation), \
             patch.object(completion,'source_hashes',return_value=plan['sources']):
            with self.assertRaisesRegex(ValueError,'changed during takeover'):
                completion.complete(plan,lambda *args,**kwargs:SimpleNamespace(returncode=0))
        self.assertEqual(completion.file_digest(self.root/'experiment.json'),changed)
        self.assertFalse(completion.read_json(plan['receipt_path'])['passed'])


if __name__ == '__main__':
    unittest.main()
