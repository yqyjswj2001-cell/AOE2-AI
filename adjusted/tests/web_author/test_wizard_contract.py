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
 def test_agent_and_usage_authorization_are_frozen_and_passed_to_meter(self):
  auth=self.app.authorize_usage(self.payload(agent='cursor',usage_authorized=True))
  self.assertEqual(auth['usage_authorization']['agent'],'cursor')
  self.assertTrue(auth['usage_authorization']['authorized'])
  state=self.app.start(self.payload(agent='cursor',usage_authorized=True))
  self.assertEqual(state['request']['agent'],'cursor')
  self.assertTrue(state['request']['usage_authorized'])
  self.assertEqual(self.app.meter.identity['agent'],'cursor')
  self.assertTrue(self.app.meter.identity['auto_capture'])
  self.assertEqual(self.app.meter.identity['workspace_root'],str(ROOT))
  self.assertEqual(self.app.next()['usage_connection']['agent'],'cursor')
 def test_start_rejects_unconfirmed_automatic_usage_choice(self):
  with self.assertRaises(ValueError):
   self.app.start(self.payload(agent='cursor',usage_authorized=True))
  self.assertFalse((self.project/'author-input').exists())
 def test_usage_authorization_requires_boolean(self):
  with self.assertRaises(ValueError):self.app.start(self.payload(agent='codex',usage_authorized='yes'))
  self.assertFalse((self.project/'author-input').exists())
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
 def test_skill_keeps_browser_interaction_user_owned(self):
  root=(ROOT/'SKILL.md').read_text(encoding='utf-8')
  detail=(ROOT/'adjusted/skills/aoe2-web-author/SKILL.md').read_text(encoding='utf-8')
  agent=(ROOT/'adjusted/skills/aoe2-web-author/agents/openai.yaml').read_text(encoding='utf-8')
  self.assertIn('网页设置默认由用户完成',root)
  self.assertIn('不得因为流程出现“网页、选择、点击”等描述就自行调用 Computer Use',root)
  self.assertIn('网页设置默认由用户操作',detail)
  self.assertIn('只有用户明确要求代理代为操作网页时',detail)
  self.assertIn('主代理负责网页服务，不负责网页交互',detail)
  self.assertIn('等待我完成设置',agent)
  self.assertIn('我点击开始生成后',agent)
 def test_final_step_owns_flat_usage_and_report_layout(self):
  html=(ROOT/'adjusted/web-author/web/index.html').read_text(encoding='utf-8')
  js=(ROOT/'adjusted/web-author/web/app.js').read_text(encoding='utf-8')
  self.assertNotIn('<details',html)
  self.assertIn('id="generationDashboard"',html)
  self.assertIn('id="usagePanel"',html)
  self.assertGreater(html.index('id="usagePanel"'),html.index('id="generationDashboard"'))
  self.assertGreater(html.index('id="developerReportTitle"'),html.index('id="usagePanel"'))
  self.assertNotIn('progressColumn',html+js)
  self.assertIn("$('authorForm').classList.toggle('hidden', !!finalRunning)",js)
  self.assertIn("$('generationDashboard').hidden = !finalRunning",js)
 def test_usage_authorization_is_first_and_session_selection_is_not_user_ui(self):
  html=(ROOT/'adjusted/web-author/web/index.html').read_text(encoding='utf-8')
  js=(ROOT/'adjusted/web-author/web/app.js').read_text(encoding='utf-8')
  hooks=json.loads((ROOT/'.cursor/hooks.json').read_text(encoding='utf-8'))
  hook_py=(ROOT/'.cursor/hooks/aoe2-usage.py').read_text(encoding='utf-8')
  self.assertIn('<span>01</span><span class="step-copy">授权',html)
  self.assertIn('name="usage_auth"',html)
  self.assertIn('授权并继续',html)
  self.assertNotIn('sessionBinding',html+js)
  self.assertNotIn('usageSession',html+js)
  self.assertNotIn('bindSessionButton',html+js)
  self.assertNotIn('/api/usage/bind-session',js)
  self.assertIn("usage_authorized: usageConsent() === 'allow'",js)
  self.assertEqual(hooks['version'],1)
  self.assertIn('beforeSubmitPrompt',hooks['hooks'])
  self.assertIn('afterAgentResponse',hooks['hooks'])
  self.assertIn('record_hook_payload',hook_py)
  self.assertNotIn('prompt',hook_py.lower())
  self.assertNotIn('response text',hook_py.lower())
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
