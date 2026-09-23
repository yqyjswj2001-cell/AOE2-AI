# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/tests/web_author/test_consent_lifecycle.py', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '9986885d27a713496c9c68d912d540aeda0ee7964387e6d7541a1dc27fd0dfda', [
(0, 0, r'''"""Consent, host handoff and independent collection regressions; synthetic sources only."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from test_workflow import Controller, FakeEngine, FakeMeter, WorkflowError
from meter_adapter import MeterAdapter
from server import make_server
from web_session import wait_for_agent


class MemoryMeter(FakeMeter):
    def __init__(self, project, identity):
        super().__init__(project, identity)
        self.revoked = False
        self.connections = []
    def revoke(self): self.revoked = True
    def connect(self, agent, ids): self.connections.append((agent, ids))


class ConsentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.app = Controller(self.project, engine=FakeEngine(), meter_factory=MemoryMeter)
    def payload(self, **extra):
        return {'project_id':self.app.data['project_id'],'expected_revision':self.app.data['revision'],**extra}
    def consent(self, value=True, agent='auto'):
        return self.app.authorize_usage(self.payload(agent=agent,usage_authorized=value))
    def start(self, **extra):
        return self.app.start(self.payload(mode='1v1',civilization='Synthetic',agent='auto',usage_authorized=True,
            script_name='Test_AI',preferences=dict.fromkeys(('dark','feudal','castle','imperial'),50),**extra))

    def test_no_meter_before_explicit_consent_and_no_generation_on_grant(self):
        self.app.state(); self.app.next()
        self.assertIsNone(self.app.meter)
        state = self.consent()
        self.assertIsNotNone(self.app.meter)
        self.assertTrue(self.app.meter.identity['auto_capture'])
        self.assertEqual(state['status'], 'configuring')
        self.assertFalse((self.project/'author-input').exists())
        self.assertEqual(state['usage_connection']['status'], 'CONNECTING')
        self.assertIsNone(state['usage']['tokens']['total_tokens'])

    def test_decline_does_not_create_collector(self):
        state = self.consent(False)
        self.assertIsNone(self.app.meter)
        self.assertIsNone(self.app.next()['usage_task'])
        self.assertEqual(state['usage_connection']['status'], 'DISABLED')

    def test_repeated_grant_and_start_keep_one_run(self):
        self.consent(); meter = self.app.meter; revision = self.app.data['revision']
        self.consent()
        self.assertEqual(self.app.data['revision'],revision)
        self.assertIs(self.app.meter,meter)
        result = self.start()
        self.assertIs(self.app.meter,meter)
        self.assertEqual(result['status'],'authoring')
        self.assertEqual(meter.identity['script_name'],'Test_AI')

    def test_early_host_handoff_is_not_creation_permission(self):
        self.consent()
        meta = {'project_id':self.app.data['project_id'],'instance_id':'test','url':'http://127.0.0.1:1'}
        def read(meta, path, **kw):
            return {'project_id':meta['project_id'],'instance_id':'test'} if path.endswith('/session') else self.app.next()
        result = wait_for_agent(meta, timeout=0, read=read)
        self.assertEqual(result['web_event'],'USAGE_CONNECTION_REQUIRED')
        self.assertEqual(result['status'],'configuring')
        self.assertFalse(result['usage_task']['user_action_required'])
        self.assertFalse((self.project/'answers').exists())

    def test_host_connect_acks_exact_consent_without_user_session_selection(self):
        self.consent(); task = self.app.next()['usage_task']
        result = self.app.usage_action('connect',self.payload(authorization_id=task['authorization_id'],
            agent='codex',session_ids=['synthetic-owned-main']))
        self.assertIsNone(result['usage_task'])
        self.assertEqual(self.app.meter.connections,[('codex',['synthetic-owned-main'])])
        self.assertTrue(result['usage_connection']['host_acknowledged'])
        self.assertEqual(result['status'],'configuring')

    def test_unavailable_host_is_honest_and_does_not_block_game_settings(self):
        self.consent(); task = self.app.next()['usage_task']
        result = self.app.usage_action('connect',self.payload(authorization_id=task['authorization_id'],
            agent='auto',status='unavailable',reason='No verifiable usage source in this synthetic host'))
        self.assertEqual(result['usage_connection']['status'],'LIMITED')
        self.assertIsNone(result['usage_task'])
        self.assertEqual(self.start()['status'],'authoring')

    def test_stale_consent_and_host_mismatch_are_rejected(self):
        self.consent(agent='codex'); task = self.app.next()['usage_task']
        for kwargs in ({'authorization_id':'old','agent':'codex','session_ids':['main']},
                       {'authorization_id':task['authorization_id'],'agent':'cursor','session_ids':['main']},
                       {'authorization_id':task['authorization_id'],'agent':'codex','session_ids':[]}):
            with self.assertRaises(WorkflowError): self.app.usage_action('connect',self.payload(**kwargs))
        self.assertFalse(self.app.meter.connections)

    def test_revocation_retains_run_blocks_ingestion_and_cannot_be_bypassed(self):
        self.consent(); meter = self.app.meter; self.start()
        result = self.consent(False)
        self.assertIs(self.app.meter,meter); self.assertTrue(meter.revoked)
        self.assertEqual(result['usage_connection']['status'],'REVOKED')
        for action in ('bind','connect','source','events','ccusage','cursor-admin'):
            with self.assertRaises(WorkflowError): self.app.usage_action(action,self.payload())
        with self.assertRaises(WorkflowError): self.consent(False,'cursor')
        with self.assertRaises(WorkflowError): self.consent(True)

    def test_reload_migrates_legacy_consent_and_revocation_remains_durable(self):
        self.app.data['usage_authorization']={'agent':'auto','authorized':True,'decided_at':1}; self.app._save()
        self.app = Controller(self.project,engine=FakeEngine(),meter_factory=MemoryMeter)
        self.assertIsNotNone(self.app.meter)
        self.assertTrue(self.app.next()['usage_task']['authorization_id'])
        self.consent(False)
        self.app = Controller(self.project,engine=FakeEngine(),meter_factory=MemoryMeter)
        self.assertFalse(self.app.meter.identity['auto_capture'])
        self.assertEqual(self.app.state()['usage_connection']['status'],'REVOKED')
        with self.assertRaises(WorkflowError): self.consent()

    def test_existing_consent_cannot_be_overridden_by_legacy_start(self):
        self.consent()
        with self.assertRaises(WorkflowError):
            self.app.start(self.payload(mode='1v1',civilization='Synthetic',script_name='Old',
                preferences=dict.fromkeys(('dark','feudal','castle','imperial'),50)))
        self.assertFalse((self.project/'author-input').exists())

    def test_connect_endpoint_requires_host_authentication(self):
        self.consent(); task = self.app.next()['usage_task']
        meta = {'host_token':'synthetic-secret','project_id':self.app.data['project_id'],'instance_id':'fixture'}
        server = make_server(self.app,meta,0)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        body = json.dumps(self.payload(authorization_id=task['authorization_id'],run_id='synthetic-run',agent='codex',session_ids=['owned']))
        def send(token=None,origin=None):
            c = http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers = {'Content-Type':'application/json','Origin':origin or f'http://127.0.0.1:{server.server_port}'}
            if token: headers['X-Author-Token']=token
            c.request('POST','/api/author/usage/connect',body,headers)
            response=c.getresponse();status=response.status;response.read();c.close();return status
        self.assertEqual(send(),403)
        self.assertEqual(send('synthetic-secret','https://evil.invalid'),403)
        self.assertEqual(send('synthetic-secret'),200)


class CollectorTests(unittest.TestCase):
    def test_collector_runs_without_browser_and_stops_on_revoke(self):
        class CounterAuto:
            def __init__(self,*args,**kw):
                self.selected_agent='codex'; self.state={'bindings':{}}; self.calls=0; self.observed=threading.Event()
            def sync(self,phase):
                self.calls+=1
                if self.calls>1:self.observed.set()
                return {'status':'NO_BOUND_SESSIONS','active_sessions':[],'gaps':[]}
        with tempfile.TemporaryDirectory() as directory, patch('meter_adapter.MultiAgentUsage',CounterAuto), patch.dict('os.environ',{'AOE2_USAGE_DISABLE_AUTO':'0','CURSOR_ADMIN_API_KEY':''}):
            meter = MeterAdapter(Path(directory),{'project_id':'test','source_sha256':'source','agent':'codex','auto_capture':True})
            auto=meter.auto
            try:
                self.assertTrue(auto.observed.wait(5), 'No HTTP report was requested; background collector must still run')
                meter.revoke(); count=auto.calls
                meter.report(); meter.phase('authoring'); meter.close()
                self.assertEqual(auto.calls,count)
                self.assertIsNone(meter.report()['tokens']['total_tokens'])
                self.assertTrue(any(g['code']=='CONSENT_REVOKED' for g in meter.report()['capture_gaps']))
            finally: meter._cursor_stop.set()

    def test_saved_ledger_survives_configuration_restart_and_does_not_attach_new_host(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{'AOE2_USAGE_DISABLE_AUTO':'1'}):
            project=Path(directory)
            identity={'project_id':'test','source_sha256':'source','auto_capture':False}
            first=MeterAdapter(project,identity)
            first.handle('source',{'source_id':'fixture','format':'openai-responses'})
            first.handle('events',{'source_id':'fixture','events':[{'event_id':'r1','usage':{'input_tokens':10,'output_tokens':2}}]})
            first._cursor_stop.set()
            again=MeterAdapter(project,identity)
            self.assertEqual(first.report()['run_id'],again.report()['run_id'])
            self.assertEqual(again.report()['tokens']['total_tokens'],12)
            again.update_context({'task_sha256':'task','game_mode':'1v1','script_name':'Test','civilization':'Synthetic'})
            self.assertEqual(again.report()['tokens']['total_tokens'],12)
            again.revoke(); again.close()
            third=MeterAdapter(project,identity)
            self.assertEqual(third.report()['tokens']['total_tokens'],12)
            self.assertIsNone(third.auto)


if __name__ == '__main__': unittest.main()
'''),
])
