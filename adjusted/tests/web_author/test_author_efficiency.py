"""Synthetic regression for incremental answers, complete handoff and quiet waiting."""
import concurrent.futures
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'adjusted/web-author'), str(Path(__file__).parent)]
from controller import Controller, WorkflowError, digest, json_bytes
from server import make_server
from submit_answers import submit_patch, complete_answers, load
from web_session import watch_for_agent, SessionError
from test_workflow import FakeEngine, FakeMeter


class WriterEngine(FakeEngine):
    def export(self, out):
        super().export(out)
        contract = {'schema': 'aoe2-author-parameter-contracts-v1', 'constraints': [
            {'module': '0.per', 'kind': 'minimum', 'keys': ['K_0_0'], 'value': 1, 'reason': 'positive'},
            {'module': '0.per', 'kind': 'sum_equal', 'keys': ['K_0_0', 'K_0_1'], 'value': 5, 'reason': 'sum five'}]}
        target = out / 'PARAMETER_CONSTRAINTS.json'; target.write_bytes(json_bytes(contract))
        path = out / 'manifest.json'; doc = json.loads(path.read_bytes())
        doc['files'][target.name] = digest(target.read_bytes()); path.write_bytes(json_bytes(doc))


class AnswerWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / 'fixture'
        self.app = Controller(self.project, engine=WriterEngine(), meter_factory=FakeMeter)
        self.app.start({'expected_revision': 0, 'mode': '1v1', 'civilization': 'Synthetic',
                        'script_name': 'Test_AI', 'preferences': dict.fromkeys(('dark', 'feudal', 'castle', 'imperial'), 50)})
        self.path = self.project / 'answers/0.json'
        self.original = (self.project / 'author-input/answers/0.json').read_bytes()
    def write(self, **changes):
        return submit_patch(self.project, {'module': '0', 'answers': changes})
    def test_handoff_is_complete_without_fixed_sources_or_host_token(self):
        task = json.loads((self.project / 'author-session/task.json').read_bytes())
        self.assertEqual(task['eligible_civilizations'], self.app.civilizations)
        self.assertEqual(task['request'], self.app.data['request'])
        self.assertEqual(task['dynamic_slots'], 1715)
        self.assertEqual(len(task['answer_modules']), 15)
        self.assertNotIn('host_token', task)
        self.assertNotIn('official_value', json.dumps(task))
        self.assertTrue(Path(task['writer']).is_file())
        self.assertNotEqual(task['submissions'], task['input_read_only'])
    def test_partial_save_preserves_all_other_nulls_and_input(self):
        receipt = self.write(K_0_0=2)
        values = json.loads(self.path.read_bytes())
        self.assertEqual(len(values), 1701)
        self.assertEqual(sum(v is None for v in values.values()), 1700)
        self.assertEqual(receipt['changed'], 1)
        self.assertEqual(receipt['deferred_constraints'], 1)
        self.assertEqual((self.project / 'author-input/answers/0.json').read_bytes(), self.original)
        self.assertEqual(self.app.state()['progress']['filled'], 1)
        self.assertEqual(len(list((self.project / 'answers').iterdir())), 15)
    def test_invalid_patch_is_all_or_nothing(self):
        before = self.path.read_bytes()
        for data in ({'K_0_0': True}, {'K_0_0': 1.5}, {'K_0_0': None}, {'K_0_0': '1'},
                     {'K_0_0': 2, 'invented': 3}, {'K_0_0': 0}, {'K_0_0': 2, 'K_0_1': 4}):
            with self.assertRaises(ValueError): self.write(**data)
            self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(ValueError): load(b'{"module":"0","module":"1"}')
        with self.assertRaises(ValueError): submit_patch(self.project, {'module': '../0', 'answers': {'K_0_0': 2}})
    def test_group_completed_then_edits_require_current_hash(self):
        self.write(K_0_0=2, K_0_1=3)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError): self.write(K_0_0=1, K_0_1=4)
        self.assertEqual(self.path.read_bytes(), before)
        receipt = submit_patch(self.project, {'module': '0'}, status_only=True)
        submit_patch(self.project, {'module': '0', 'answers': {'K_0_0': 1, 'K_0_1': 4}, 'expected_sha256': receipt['sha256']})
        self.assertEqual(json.loads(self.path.read_bytes())['K_0_1'], 4)
        with self.assertRaises(ValueError):
            submit_patch(self.project, {'module': '0', 'answers': {'K_0_0': 2, 'K_0_1': 3}, 'expected_sha256': receipt['sha256']})
    def test_retry_identical_patch_is_idempotent(self):
        a = self.write(K_0_0=2); b = self.write(K_0_0=2)
        self.assertEqual(a['sha256'], b['sha256']); self.assertEqual(b['changed'], 0)
    def test_concurrent_distinct_groups_do_not_lose_updates(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.write, **{f'K_0_{i}': i}) for i in (2, 3)]
            for future in futures: future.result(timeout=5)
        self.assertEqual(self.app.state()['progress']['filled'], 2)
    def test_stale_or_unfrozen_task_is_rejected(self):
        self.app.data['request']['civilization'] = 'auto'; self.app._save()
        with self.assertRaises(ValueError): self.write(K_0_0=2)
    def test_tampered_constraints_and_symlink_output_are_rejected(self):
        target = self.project / 'author-input/PARAMETER_CONSTRAINTS.json'; target.write_text('{}')
        with self.assertRaises(ValueError): self.write(K_0_0=2)
        self.path.unlink()
        try: self.path.symlink_to(self.project / 'author-input/answers/0.json')
        except OSError: return
        with self.assertRaises(ValueError): self.write(K_0_0=2)
        self.assertEqual((self.project / 'author-input/answers/0.json').read_bytes(), self.original)
    def test_project_local_cli_runs_without_repo_imports(self):
        patch = self.project / 'submissions/group.json'
        patch.write_bytes(json_bytes({'module': '0', 'answers': {'K_0_0': 2}}))
        result = subprocess.run([sys.executable, '-I', '-B', str(self.project / 'author-session/submit_answers.py'),
                                 '--patch', str(patch)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['changed'], 1)
    def test_diagnostics_replaced_after_success_not_stale_missing_count(self):
        with self.assertRaises(WorkflowError):
            self.app.validate({'expected_revision': self.app.data['revision']})
        for path in (self.project / 'answers').glob('*.json'):
            path.write_bytes(json_bytes(dict.fromkeys(json.loads(path.read_bytes()), 2)))
        state = self.app.state()
        self.app.validate({'expected_revision': state['revision']})
        diag = json.loads((self.project / 'tmp/answer-diagnostics.json').read_bytes())
        self.assertEqual(diag['filled'], 1715); self.assertEqual(diag['missing_count'], 0)
        self.assertEqual(diag['errors'], [])
    def test_full_fields_do_not_interrupt_author_review(self):
        with self.assertRaises(ValueError): complete_answers(self.project)
        for path in (self.project / 'answers').glob('*.json'):
            values = dict.fromkeys(json.loads(path.read_bytes()), 2)
            if path.stem == '0': values['K_0_1'] = 3
            path.write_bytes(json_bytes(values))
        self.assertEqual(self.app.signal()['next_action'], 'wait_for_answers')
        receipt = complete_answers(self.project)
        self.assertEqual(self.app.signal()['next_action'], 'validate')
        self.assertEqual(receipt['answers_sha256'], self.app.data['answers_sha256'])
        status = submit_patch(self.project, {'module': '0'}, status_only=True)
        submit_patch(self.project, {'module':'0','answers':{'K_0_2':3},'expected_sha256':status['sha256']})
        self.assertEqual(self.app.signal()['next_action'], 'wait_for_answers')

    def test_signal_is_small_and_private(self):
        signal = self.app.signal()
        self.assertEqual(signal['next_action'], 'wait_for_answers')
        self.assertLess(len(json.dumps(signal)), 400)
        self.assertFalse({'civilizations', 'request', 'usage', 'civilization_selection'} & signal.keys())
        meta = {'host_token': 'test-token', 'instance_id': 'test', 'project_id': self.app.data['project_id']}
        server = make_server(self.app, meta, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            for token, expected in ((None, 403), ('test-token', 200)):
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
                conn.request('GET', '/api/author/signal', headers={'X-Author-Token': token} if token else {})
                response = conn.getresponse(); self.assertEqual(response.status, expected); response.read(); conn.close()
        finally: server.shutdown(); server.server_close(); thread.join(timeout=3)


class RealContractTests(unittest.TestCase):
    def test_incremental_writer_preserves_existing_roundtrip_contract(self):
        # Host-side regression fixture only. These reference values are never handed to an author.
        from controller import RealEngine
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'real-contract-fixture'
            app = Controller(project, engine=RealEngine(), meter_factory=FakeMeter)
            app.start({'expected_revision':0,'mode':'1v1','civilization':'Mayans','script_name':'Contract_Test',
                       'preferences':dict.fromkeys(('dark','feudal','castle','imperial'),50)})
            catalog = json.loads((ROOT/'adjusted/cloze/classification/parameters.json').read_bytes())
            count = 0
            for module, profile in catalog['modules'].items():
                answers = {r['key']:r['official_value'] for r in profile['parameters'] if r['decision']=='dynamic'}
                if not answers: continue
                result = submit_patch(project, {'module':module.removesuffix('.per'),'answers':answers})
                count += result['changed']
            self.assertEqual(count,1715)
            complete_answers(project)
            self.assertEqual(app.signal()['next_action'],'validate')
            app.validate({'expected_revision':app.data['revision']})
            self.assertEqual(app.data['status'],'ready')
            self.assertTrue(all(v is None for p in (project/'author-input/answers').glob('*.json')
                                for v in json.loads(p.read_bytes()).values()))


class WatchTests(unittest.TestCase):
    meta = {'project_id': 'test', 'instance_id': 'instance'}
    def watch(self, states, until='answers', timeout=100):
        counter = {'n': 0, 'clock': 0}
        def read(meta, path, **kwargs):
            if path.endswith('/session'): return meta
            self.assertEqual(path, '/api/author/signal')
            state = states[min(counter['n'], len(states)-1)]; counter['n'] += 1
            return {'project_id': 'test', 'status': 'authoring', **state}
        def sleep(seconds): counter['clock'] += seconds
        result = watch_for_agent(self.meta, timeout, until=until, read=read, sleep=sleep, clock=lambda:counter['clock'])
        return result, counter
    def test_many_progress_changes_stay_inside_one_wait(self):
        states = [{'next_action':'wait_for_answers', 'progress':{'filled':i, 'total':100}} for i in range(25)]
        states.append({'next_action':'validate'})
        result, count = self.watch(states)
        self.assertEqual(result['next_action'], 'validate'); self.assertEqual(count['n'], 26)
    def test_timeout_does_not_dump_context(self):
        result, _ = self.watch([{'next_action':'wait_for_answers','request':{'large':'private'}}], timeout=0)
        self.assertEqual(result['web_event'], 'WATCH_TIMEOUT'); self.assertNotIn('request', result)
    def test_authorization_interrupts_wait_even_before_start(self):
        result, count = self.watch([{'status':'configuring','usage_task':{'action':'connect_usage'}}], until='start')
        self.assertEqual(result['web_event'], 'USAGE_CONNECTION_REQUIRED'); self.assertEqual(count['n'], 1)
    def test_error_returns_without_waiting_for_complete(self):
        result, _ = self.watch([{'status':'invalid','next_action':'repair_answers'}])
        self.assertEqual(result['status'], 'invalid')
    def test_identity_change_and_unbounded_wait_are_rejected(self):
        with self.assertRaises(SessionError):
            watch_for_agent(self.meta, read=lambda *a,**k: {'instance_id':'other','project_id':'test'})
        for timeout in (float('inf'), -1, 3601):
            with self.assertRaises(SessionError): watch_for_agent(self.meta, timeout)


if __name__ == '__main__': unittest.main()
