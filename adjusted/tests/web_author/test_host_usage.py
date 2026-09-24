"""Synthetic host schemas: ownership, real counters, and actionable missing usage."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web-author'))
from host_usage import cursor_metadata, project_candidates
from cursor_admin_usage import active_project_path, collect_cursor_admin_usage, collect_cursor_hook_usage, hook_db_path, record_hook_payload
from meter_adapter import MeterAdapter
from metering import Meter
from multi_agent_usage import MultiAgentUsage, detect_agents
from usage_formats import normalize, response_event
from usage import read_usage_lines


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class HostUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir()
        self.meter = Meter(self.project, 'synthetic', 'source')
        self.start = self.meter.meta['started_at']
        self.env = {'APPDATA': str(self.root / 'roaming')}

    def auto(self, agent, sessions):
        return MultiAgentUsage(self.meter, self.project, self.root, environ=self.env,
            home=self.root, selected_agent=agent, workspace_root=self.workspace,
            bindings={agent: sessions} if sessions else {})

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def cursor(self, rows):
        base = self.root / 'roaming/Cursor/User'
        self.write('roaming/Cursor/User/workspaceStorage/own/workspace.json', {'folder': self.workspace.as_uri()})
        self.write('roaming/Cursor/User/workspaceStorage/other/workspace.json', {'folder': (self.root / 'other').as_uri()})
        path = base / 'globalStorage/state.vscdb'
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE composerHeaders(composerId TEXT,workspaceId TEXT,createdAt INTEGER,lastUpdatedAt INTEGER,isSubagent INTEGER)')
        db.executemany('INSERT INTO composerHeaders VALUES (?,?,?,?,?)',
            [('own-session', 'own', int((self.start-30)*1000), int((self.start+1)*1000), 0),
             ('other-session', 'other', int((self.start+1)*1000), int((self.start+1)*1000), 0)])
        db.execute('CREATE TABLE cursorDiskKV(key TEXT PRIMARY KEY,value TEXT)')
        db.execute('INSERT INTO cursorDiskKV VALUES (?,?)', ('composerData:own-session', '{"usageData":{},"text":"PRIVATE_CONTENT"}'))
        for key, data in rows:
            db.execute('INSERT INTO cursorDiskKV VALUES (?,?)', (key, json.dumps(data)))
        db.commit(); db.close()
        return path

    def test_codex_spawn_edges_identify_and_auto_bind_owned_children(self):
        codex=self.root/'.codex'
        self.env['CODEX_HOME']=str(codex)
        dbpath=codex/'state_5.sqlite'
        codex.mkdir()
        db=sqlite3.connect(dbpath)
        db.execute('CREATE TABLE threads(id TEXT,cwd TEXT,created_at REAL,updated_at REAL)')
        db.execute('CREATE TABLE thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT,status TEXT)')
        db.executemany('INSERT INTO threads VALUES (?,?,?,?)',[
            ('main',str(self.workspace),self.start-5,self.start+4),
            ('child',str(self.workspace),self.start+1,self.start+3),
            ('grandchild',str(self.workspace),self.start+2,self.start+3),
            ('unrelated',str(self.workspace),self.start+1,self.start+3)])
        db.executemany('INSERT INTO thread_spawn_edges VALUES (?,?,?)',[
            ('main','child','running'),('child','grandchild','completed')])
        db.commit();db.close()
        sessions=codex/'sessions/2026/09/23';sessions.mkdir(parents=True)
        def rollout(sid,when,total):
            rows=[
                {'timestamp':iso(self.start-10),'type':'session_meta','payload':{'id':sid}},
                {'type':'turn_context','payload':{'model':'fixture'}},
                {'timestamp':iso(self.start-1),'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}}},
                {'timestamp':iso(when),'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':total,'output_tokens':0,'total_tokens':total}}}},
            ]
            (sessions/f'rollout-fixture-{sid}.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        rollout('main',self.start+1,10)
        rollout('child',self.start+2,5)
        rollout('grandchild',self.start+3,3)
        rollout('unrelated',self.start+2,999)
        candidates=project_candidates('codex',self.workspace,[codex],self.root,self.env)
        by_id={r['session_id']:r for r in candidates}
        self.assertEqual(by_id['child']['parent_session_id'],'main')
        self.assertTrue(by_id['child']['is_child'])
        auto=self.auto('codex',['main'])
        status=auto.sync('3')
        self.assertEqual(auto.state['bindings']['codex'],['child','grandchild','main'])
        self.assertEqual(status['auto_bound_child_count'],2)
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],18)

    def test_reused_codex_session_auto_binds_from_unique_current_activity(self):
        codex=self.root/'.codex';self.env['CODEX_HOME']=str(codex)
        codex.mkdir()
        db=sqlite3.connect(codex/'state_5.sqlite')
        db.execute('CREATE TABLE threads(id TEXT,cwd TEXT,created_at REAL,updated_at REAL)')
        db.executemany('INSERT INTO threads VALUES (?,?,?,?)',[
            ('current',str(self.workspace),self.start-100,self.start+2),
            ('inactive',str(self.workspace),self.start-100,self.start-20)])
        db.commit();db.close()
        sessions=codex/'sessions/2026/09/23';sessions.mkdir(parents=True)
        rows=[
            {'timestamp':iso(self.start-100),'type':'session_meta','payload':{'id':'current'}},
            {'type':'turn_context','payload':{'model':'fixture'}},
            {'timestamp':iso(self.start-1),'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':10,'output_tokens':0,'total_tokens':10}}}},
            {'timestamp':iso(self.start+1),'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':25,'output_tokens':0,'total_tokens':25}}}},
        ]
        (sessions/'rollout-fixture-current.jsonl').write_text(
            '\n'.join(json.dumps(row) for row in rows)+'\n',encoding='utf-8')
        auto=self.auto('codex',[])
        status=auto.sync('3')
        self.assertEqual(auto.state['bindings']['codex'],['current'])
        self.assertEqual(auto.state['auto_bound_main']['codex'],'current')
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],15)
        self.assertNotEqual(status['connection']['code'],'AUTO_SESSION_AMBIGUOUS')

    def test_cursor_ide_local_token_count_is_not_used_as_usage(self):
        self.cursor([('bubbleId:own-session:b1', {'type': 2, 'createdAt': iso(self.start+1),
            'tokenCount': {'inputTokens': 9000, 'outputTokens': 9000}, 'text': 'PRIVATE_CONTENT'})])
        auto = self.auto('cursor', [])
        status = auto.sync()
        self.assertIsNone(self.meter.report()['tokens']['total_tokens'])
        self.assertEqual(status['connection']['code'], 'CURSOR_HOOK_PROJECT_WAITING')
        self.assertEqual([r['session_id'] for r in status['session_candidates']], ['own-session'])
        self.assertFalse(auto.state.get('bindings', {}).get('cursor'))
        self.assertIn('CURSOR_HOOK_PROJECT_WAITING', {g['code'] for g in status['gaps']})
        self.assertNotIn('PRIVATE_CONTENT', auto.path.read_text())

    def test_cursor_hook_does_not_record_before_usage_authorization(self):
        active=active_project_path(self.workspace);active.parent.mkdir(parents=True,exist_ok=True)
        active.write_text(json.dumps({'schema':'aoe2-cursor-active-project-v1','project_id':'synthetic',
            'project':str(self.project),'agent':'cursor','usage_authorized':False}),encoding='utf-8')
        recorded=record_hook_payload({'conversation_id':'cursor-denied','hook_event_name':'stop',
            'generation_id':'gen-denied','workspace_roots':[str(self.workspace)],'user_email':'dev@example.com',
            'text':'PRIVATE','input_tokens':9,'output_tokens':1},
            self.workspace,observed_at=self.start+1)
        self.assertTrue(recorded)
        self.assertNotIn(b'PRIVATE',hook_db_path(self.workspace).read_bytes())
        candidates=project_candidates('cursor',self.workspace,[],self.root,self.env)
        row=next(r for r in candidates if r['session_id']=='cursor-denied')
        self.assertIsNone(row['project_id'])
        self.auto('cursor',[]).sync()
        self.assertIsNone(self.meter.report()['tokens']['total_tokens'])

    def test_cursor_hook_identity_and_admin_events_are_exactly_scoped(self):
        active=active_project_path(self.workspace);active.parent.mkdir(parents=True,exist_ok=True)
        active.write_text(json.dumps({'schema':'aoe2-cursor-active-project-v1','project_id':'synthetic',
            'project':str(self.project),'agent':'cursor','usage_authorized':True}),encoding='utf-8')
        payload={'conversation_id':'cursor-conv-1','generation_id':'gen-1',
            'hook_event_name':'afterAgentResponse','workspace_roots':[str(self.workspace)],
            'user_email':'dev@example.com','model':'fixture-model','text':'PRIVATE_RESPONSE'}
        self.assertTrue(record_hook_payload(payload,self.workspace,observed_at=self.start+1))
        candidates=project_candidates('cursor',self.workspace,[],self.root,self.env)
        row=next(r for r in candidates if r['session_id']=='cursor-conv-1')
        self.assertTrue(row['hook_verified'])
        self.assertTrue(row['has_user_email'])
        self.assertEqual(row['project_id'],'synthetic')
        self.assertNotIn(b'PRIVATE_RESPONSE',hook_db_path(self.workspace).read_bytes())

        def transport(api_key,body):
            self.assertEqual(api_key,'secret-key')
            self.assertEqual(body['email'],'dev@example.com')
            return {'usageEvents':[
                {'timestamp':str(int((self.start+2)*1000)),'userEmail':'dev@example.com',
                 'conversationId':'cursor-conv-1','model':'fixture-model','kind':'Usage-based',
                 'isTokenBasedCall':True,'tokenUsage':{'inputTokens':10,'outputTokens':5,
                    'cacheReadTokens':2,'cacheWriteTokens':1},'chargedCents':1.25},
                {'timestamp':str(int((self.start+2)*1000)),'userEmail':'dev@example.com',
                 'conversationId':'another-conversation','model':'fixture-model','kind':'Usage-based',
                 'isTokenBasedCall':True,'tokenUsage':{'inputTokens':999,'outputTokens':999,
                    'cacheReadTokens':0,'cacheWriteTokens':0},'chargedCents':99},
            ],'pagination':{'hasNextPage':False}}
        result=collect_cursor_admin_usage(self.workspace,self.workspace,['cursor-conv-1'],self.start,
            api_key='secret-key',end_at=self.start+10,transport=transport)
        self.assertEqual(result['matched_sessions'],['cursor-conv-1'])
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['usage']['input_tokens'],13)
        self.assertEqual(result['items'][0]['usage']['output_tokens'],5)
        self.assertEqual(result['items'][0]['usage']['total_tokens'],18)

    def test_cursor_admin_refresh_records_official_usage_without_persisting_key(self):
        self.cursor([])
        active=active_project_path(self.workspace);active.parent.mkdir(parents=True,exist_ok=True)
        active.write_text(json.dumps({'schema':'aoe2-cursor-active-project-v1','project_id':'synthetic',
            'project':str(self.project),'agent':'cursor','usage_authorized':True}),encoding='utf-8')
        record_hook_payload({'conversation_id':'cursor-conv-1','hook_event_name':'sessionStart',
            'workspace_roots':[str(self.workspace)],'user_email':'dev@example.com'},self.workspace,
            observed_at=self.start+1)
        env={**self.env,'CURSOR_ADMIN_API_KEY':'secret-key'}
        auto=MultiAgentUsage(self.meter,self.project,self.root,environ=env,home=self.root,
            selected_agent='cursor',workspace_root=self.workspace,bindings={})
        self.assertEqual(auto.sync()['connection']['code'],'CURSOR_ADMIN_READY')
        self.assertEqual(auto.state['bindings']['cursor'],['cursor-conv-1'])
        item={'agent':'cursor','session':'cursor-conv-1','key':'cursor-admin:event-1',
            'timestamp':self.start+2,'model':'fixture-model','usage':{
                'input_tokens':13,'output_tokens':5,'total_tokens':18,
                'cached_input_tokens':2,'cache_write_tokens':1,'reasoning_output_tokens':None}}
        with patch('multi_agent_usage.collect_cursor_admin_usage',return_value={
            'items':[item],'gaps':[],'matched_sessions':['cursor-conv-1'],'range_truncated':False}):
            status=auto.ingest_cursor_admin()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],18)
        self.assertEqual(status['connection']['code'],'RECORDED_PARTIAL')
        self.assertNotIn('secret-key',auto.path.read_text(encoding='utf-8'))

    def test_cursor_stop_hook_tokens_are_counted_once(self):
        active=active_project_path(self.workspace);active.parent.mkdir(parents=True,exist_ok=True)
        active.write_text(json.dumps({'schema':'aoe2-cursor-active-project-v1','project_id':'synthetic',
            'project':str(self.project),'agent':'auto','usage_authorized':True}),encoding='utf-8')
        root=self.workspace.resolve()
        cursor_root='/' + root.drive + root.as_posix().split(':',1)[1]
        common={'conversation_id':'cursor-conv-1','generation_id':'gen-1',
            'workspace_roots':[cursor_root],'model':'fixture-model','text':'PRIVATE_RESPONSE',
            'input_tokens':13,'output_tokens':5,'cache_read_tokens':2,'cache_write_tokens':1}
        self.assertTrue(record_hook_payload({**common,'hook_event_name':'afterAgentResponse'},self.workspace,observed_at=self.start+1))
        self.assertTrue(record_hook_payload({**common,'hook_event_name':'stop'},self.workspace,observed_at=self.start+2))
        self.assertNotIn(b'PRIVATE_RESPONSE',hook_db_path(self.workspace).read_bytes())
        result=collect_cursor_hook_usage(self.workspace,self.workspace,['cursor-conv-1'],self.start)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['usage']['input_tokens'],13)
        self.assertEqual(result['items'][0]['usage']['cached_input_tokens'],2)
        self.assertEqual(result['items'][0]['usage']['total_tokens'],18)
        auto=self.auto('auto',[])
        status=auto.sync()
        self.assertEqual(auto.state['bindings']['cursor'],['cursor-conv-1'])
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],18)
        self.assertEqual(status['connection']['code'],'RECORDED_PARTIAL')
        auto.sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],18)

    def test_selected_cursor_does_not_inherit_codex_environment(self):
        with patch.dict(os.environ, {'CODEX_THREAD_ID': 'unrelated-codex-thread', 'AOE2_USAGE_DISABLE_AUTO': '0'}):
            meter = MeterAdapter(self.project, {'project_id': 'synthetic', 'source_sha256': 'source',
                'agent': 'cursor', 'workspace_root': str(self.workspace)})
        self.assertNotIn('codex', meter.auto.state['bindings'])

    def test_claude_never_opens_unbound_transcript(self):
        path = self.write('.claude/projects/project/owned.jsonl', {'timestamp': iso(self.start+1),
            'message': {'id': 'msg1', 'usage': {'input_tokens': 10, 'output_tokens': 5,
                'cache_read_input_tokens': 20, 'cache_creation_input_tokens': 0}}})
        other = self.write('.claude/projects/project/private.jsonl', {'text': 'PRIVATE_CONTENT'})
        real_open = Path.open
        def guarded(path, *a, **kw):
            if path == other:
                raise AssertionError('unbound transcript read')
            return real_open(path, *a, **kw)
        with patch.object(Path, 'open', guarded):
            self.auto('claude', ['owned']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'], 35)

    def test_gemini_session_id_and_cache_are_not_double_counted(self):
        self.write('.gemini/tmp/hash/chats/owned.json', {'sessionId': 'owned', 'messages': [
            {'id': 'm1', 'type': 'gemini', 'timestamp': iso(self.start+1),
             'tokens': {'input': 100, 'output': 20, 'cached': 30, 'thoughts': 10, 'tool': 5, 'total': 135}}]})
        self.auto('gemini', ['owned']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'], 135)
        self.assertEqual(self.meter.report()['tokens']['cached_input_tokens'], 30)

    def test_kimi_counts_step_usage_not_context(self):
        self.write('.kimi/sessions/group/owned/wire.jsonl', {'timestamp': self.start+1, 'message': {
            'type': 'StatusUpdate', 'payload': {'message_id': 'm1', 'context_tokens': 99999,
            'token_usage': {'input_other': 10, 'output': 5, 'input_cache_read': 20, 'input_cache_creation': 2}}}})
        self.auto('kimi', ['owned']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'], 37)

    def test_kimi_code_verified_usage_scope_and_millisecond_time(self):
        path=self.root/'.kimi-code/sessions/workspace/owned/agents/a1/wire.jsonl'
        path.parent.mkdir(parents=True)
        rows=[{'type':'usage.record','usageScope':scope,'time':int((self.start+1)*1000),
            'model':'kimi-code/model','usage':{'inputOther':10,'output':5,'inputCacheRead':20,'inputCacheCreation':2}}
            for scope in ['turn','session']]
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        self.auto('kimi',['owned:a1']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],37)

    def test_opencode_sql_selects_only_bound_session(self):
        folder = self.root / '.local/share/opencode'; folder.mkdir(parents=True)
        db = sqlite3.connect(folder/'opencode.db')
        db.execute('CREATE TABLE message(id TEXT,session_id TEXT,data TEXT,time_created INTEGER)')
        for sid, inp in [('owned',10), ('private',99999)]:
            db.execute('INSERT INTO message VALUES (?,?,?,?)', ('m'+sid,sid,json.dumps({'id':'m'+sid,'sessionID':sid,
                'tokens':{'input':inp,'output':5,'reasoning':0,'cache':{'read':2,'write':0},'total':inp+7}}),int((self.start+1)*1000)))
        db.commit();db.close()
        self.auto('opencode', ['owned']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'], 17)

    def test_copilot_chat_and_parent_do_not_double_count(self):
        path = self.root/'dedicated.jsonl'
        rows=[]
        for kind in ['chat','invoke_agent']:
            rows.append({'timestamp':iso(self.start+1),'spanId':kind,'attributes':{
                'gen_ai.operation.name':kind,'gen_ai.conversation.id':'owned',
                'gen_ai.usage.input_tokens':10,'gen_ai.usage.output_tokens':5}})
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        self.env['AOE2_COPILOT_USAGE_FILE']=str(path)
        self.auto('copilot',['owned']).sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],15)
        self.assertIsNone(self.meter.report()['tokens']['cache_write_tokens'])

    def test_cline_task_ui_usage_and_idempotence(self):
        storage=self.root/'cline';self.env['AOE2_CLINE_STORAGE']=str(storage)
        self.write('cline/tasks/owned/ui_messages.json',[{'type':'say','say':'api_req_started','ts':int((self.start+1)*1000),
            'text':json.dumps({'tokensIn':10,'tokensOut':5,'cacheReads':20,'cacheWrites':0})}])
        auto=self.auto('cline',['owned']);auto.sync();auto.sync()
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],35)

    def test_ccusage_old_session_baseline_and_repeat_are_safe(self):
        auto=self.auto('kimi',['owned'])
        row={'sessionId':'owned','inputTokens':100,'outputTokens':20,'cacheReadTokens':0,'cacheCreationTokens':0,
             'totalTokens':120,'firstActivity':iso(self.start-20),'lastActivity':iso(self.start+1)}
        auto.ingest_ccusage('kimi','owned',{'sessions':[row]})
        self.assertIsNone(self.meter.report()['tokens']['total_tokens'])
        self.assertEqual(auto.status()['connection']['code'],'BASELINE_CAPTURED')
        self.assertEqual(auto.status()['status'],'WAITING_FOR_USAGE')
        row.update(inputTokens=130,totalTokens=150,lastActivity=iso(self.start+2))
        auto.ingest_ccusage('kimi','owned',{'sessions':[row]})
        auto.ingest_ccusage('kimi','owned',{'sessions':[row]})
        self.assertEqual(self.meter.report()['tokens']['total_tokens'],30)
        self.assertEqual(auto.status()['connection']['code'],'RECORDED_PARTIAL')
        self.assertIn('NO_PROJECT_START_BASELINE',{g['code'] for g in auto.status()['gaps']})
        with self.assertRaises(ValueError):
            auto.ingest_ccusage('kimi','owned',{'sessions':[row,{**row,'sessionId':'other'}]})

    def test_cursor_sdk_and_unified_real_usage_import(self):
        raw={'inputTokens':10,'outputTokens':8,'cacheReadTokens':20,'cacheWriteTokens':3,'totalTokens':41,'reasoningTokens':5}
        usage=normalize('cursor-sdk',raw)
        self.assertEqual(usage['total_tokens'],41)
        self.assertEqual(usage['reasoning_tokens'],5)
        with self.assertRaises(ValueError):
            response_event('cursor-sdk',{'id':'run','status':'running','usage':raw})
        row={'event_id':'actual-response','usage':{'input_tokens':12,'output_tokens':4,'total_tokens':16}}
        self.assertEqual(len(list(read_usage_lines([json.dumps(row)],'agent-usage','own'))),1)

    def test_reopen_codex_preserves_bindings_without_attaching_maintenance_host(self):
        project=self.root/'reopen-project';project.mkdir()
        identity={'project_id':'reopen','source_sha256':'source','agent':'codex','workspace_root':str(self.workspace)}
        def factory(meter, target, root, **kwargs):
            return MultiAgentUsage(meter,target,root,home=self.root,environ=self.env,**kwargs)
        with patch('meter_adapter.MultiAgentUsage', side_effect=factory), patch.dict(os.environ,
                {'CODEX_THREAD_ID':'original-author','AOE2_AUTHOR_CODEX_THREAD_ID':'','AOE2_USAGE_DISABLE_AUTO':'0'}):
            first=MeterAdapter(project,identity)
            self.assertEqual(first.auto.state['bindings'],{'codex':['original-author']})
            with patch.dict(os.environ,{'CODEX_THREAD_ID':'maintenance-host'}):
                second=MeterAdapter(project,identity)
                self.assertEqual(second.auto.state['bindings'],{'codex':['original-author']})
                second.bind_sessions({'codex':['explicit-child']})
                third=MeterAdapter(project,identity)
                self.assertEqual(third.auto.state['bindings'],{'codex':['explicit-child','original-author']})

    def test_unknown_usage_is_not_reported_as_recorded_tokens(self):
        self.write('.claude/projects/project/owned.jsonl',{'timestamp':iso(self.start+1),
            'message':{'id':'missing-cache-fields','usage':{'input_tokens':10,'output_tokens':5}}})
        status=self.auto('claude',['owned']).sync()
        self.assertIsNone(self.meter.report()['tokens']['total_tokens'])
        self.assertEqual(status['connection']['code'],'WAITING_FOR_USAGE')
        self.assertEqual(status['status'],'WAITING_FOR_USAGE')

    def test_empty_agent_directory_is_not_detection(self):
        (self.root/'.kimi').mkdir()
        (self.root/'.codex').mkdir()
        self.assertFalse(any(r['detected'] for r in detect_agents(self.root,self.env)))

if __name__=='__main__':
    unittest.main()
