"""Integration contracts for the wizard endpoints and project-scoped host selection."""
import http.client,json,threading,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'adjusted/web-author'),str(Path(__file__).parent)]
from controller import Controller,digest,json_bytes
from server import make_server
from test_workflow import FakeEngine,FakeMeter

class WizardContractTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.project=Path(self.temp.name)/'project';self.app=Controller(self.project,engine=FakeEngine(),meter_factory=FakeMeter)
 def payload(self,**extra):
  s=self.app.state();return dict(project_id=s['project_id'],expected_revision=s['revision'],mode='ffa8',civilization=self.app.civilizations[0]['id'],script_name='Fixture',preferences=dict(dark=50,feudal=50,castle=50,imperial=50),**extra)
 def test_agent_frozen_and_passed_to_meter(self):
  state=self.app.start(self.payload(agent='cursor'))
  self.assertEqual(state['request']['agent'],'cursor')
  self.assertEqual(self.app.meter.identity['agent'],'cursor')
  self.assertEqual(self.app.meter.identity['workspace_root'],str(ROOT))
  self.assertEqual(self.app.next()['usage_connection']['agent'],'cursor')
 def test_unknown_agent_rejected_before_export(self):
  with self.assertRaises(ValueError):self.app.start(self.payload(agent='made-up-host'))
  self.assertFalse((self.project/'author-input').exists())
 def test_legacy_task_identity_preserved(self):
  self.app.start(self.payload())
  for key in ('request','task_request'):self.app.data[key].pop('agent',None)
  self.app.data['task_sha256']=digest(json_bytes(self.app.data['task_request']));old=self.app.data['task_sha256'];self.app._save()
  again=Controller(self.project,engine=FakeEngine(),meter_factory=FakeMeter)
  self.assertEqual(again.data['task_sha256'],old)
  self.assertNotIn('agent',again.data['request'])
  self.assertEqual(again.meter.identity['agent'],'auto')
 def test_browser_bind_rejects_foreign_session_and_preserves_task(self):
  class ScopedMeter(FakeMeter):
   def report(self,include_records=False):
    return {"state":"RUNNING","run_id":"fixture-run","auto_capture":{"selected_agent":"cursor","session_candidates":[{"agent":"cursor","session_id":"owned-session","workspace_match":True}]}}
   def bind_sessions(self,sessions):self.bound=sessions;return self.report()
  self.app=Controller(self.project,engine=FakeEngine(),meter_factory=ScopedMeter)
  state=self.app.start(self.payload(agent='cursor'));frozen=self.app.data['task_sha256']
  base={'project_id':state['project_id'],'expected_revision':state['revision'],'run_id':'fixture-run','agent':'cursor'}
  with self.assertRaises(ValueError):self.app.bind_usage_candidate({**base,'session_id':'other-project'})
  with self.assertRaises(ValueError):self.app.bind_usage_candidate({**base,'session_id':'owned-session','run_id':'another-run'})
  self.app.bind_usage_candidate({**base,'session_id':'owned-session'})
  self.assertEqual(self.app.data['usage_sessions'],{'cursor':['owned-session']})
  self.assertEqual(self.app.data['task_sha256'],frozen)
 def test_public_catalogs_and_only_allowlisted_icons(self):
  meta={'host_token':'fixture-token','instance_id':'fixture','project_id':self.app.data['project_id']}
  server=make_server(self.app,meta,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def get(path):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10);c.request('GET',path);r=c.getresponse();status=r.status;raw=r.read();c.close();return status,raw
  try:
   status,raw=get('/api/civilizations');self.assertEqual(status,200);data=json.loads(raw);self.assertEqual(len(data['civilizations']),42)
   status,raw=get('/api/agents');self.assertEqual(status,200);self.assertIn('cursor',{a['id'] for a in json.loads(raw)['agents']})
   status,raw=get('/assets/civilizations/Chinese.png');self.assertEqual(status,200);self.assertTrue(raw.startswith(b'\x89PNG'))
   for path in ['/assets/civilizations/Shu.png','/assets/civilizations/../app.js','/assets/civilizations/README.md']:
    self.assertEqual(get(path)[0],404)
  finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':unittest.main()
