"""Synthetic browser regression. No real project, account or paid model is used."""
from pathlib import Path
import copy
import json
import mimetypes
import os
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / 'adjusted/web-author/web'
OUT = Path(os.environ.get('AOE2_UI_TEST_OUTPUT', ROOT / 'adjusted/.local/studio-review'))
sys.path.insert(0, str(WEB.parent))
from civilization_catalog import catalog
from agent_catalog import agent_catalog


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    civs, agents = catalog(), agent_catalog()
    usage = {'state':'RUNNING', 'coverage':'NOT_CONNECTED', 'tokens':{'total_tokens':None},
             'time':{'elapsed_seconds':17}, 'auto_capture':{'selected_agent':'auto'}, 'stages':[]}
    state = {'project_id':'synthetic-studio-a','revision':0,'status':'configuring','host_agent':'auto',
             'civilizations':civs['civilizations'],'request':None,'build':None,'usage_authorization':None,
             'usage':usage,'progress':{'filled':0,'total':1715},
             'usage_connection':{'status':'NOT_AUTHORIZED','can_revoke':False}}
    posts, consents, errors, checks, downloads = [], [], [], [], []
    flags = {'offline':False}

    def route(req):
        path = urlsplit(req.request.url).path
        if path == '/api/state':
            if flags['offline']: req.abort('connectionrefused')
            else: req.fulfill(json=copy.deepcopy(state))
            return
        if path == '/api/author/usage': req.fulfill(json=copy.deepcopy(usage)); return
        if path == '/api/civilizations': req.fulfill(json=civs); return
        if path == '/api/agents': req.fulfill(json={'agents':agents}); return
        if path == '/api/usage/authorize':
            body = req.request.post_data_json
            assert body['expected_revision'] == state['revision']
            consents.append(body)
            previous = state['usage_authorization'] or {}
            auth = {'agent':body['agent'],'authorized':body['usage_authorized'],'authorization_id':'synthetic-consent','decided_at':1}
            if previous.get('authorized') and not body['usage_authorized']: auth['revoked_at'] = 2
            code = 'CONNECTING' if body['usage_authorized'] else 'REVOKED' if auth.get('revoked_at') else 'DISABLED'
            state.update(revision=state['revision']+1,usage_authorization=auth,
                usage_connection={'status':code,'can_revoke':body['usage_authorized']})
            req.fulfill(json=copy.deepcopy(state)); return
        if path == '/api/start':
            body = req.request.post_data_json
            assert body['expected_revision'] == state['revision']
            posts.append(body)
            state.update(status='authoring',revision=state['revision']+1,request=body)
            req.fulfill(json=copy.deepcopy(state)); return
        if path == '/api/report/generate':
            req.fulfill(json={'markdown':'# Synthetic report\nNot game tested.', 'issue_count':1,'feedback_count':1,
                'download_url':'/api/report/download?id=test&format=main','details_url':'/api/report/download?id=test&format=details'})
            return
        if path in ('/api/author/usage/export','/api/report/download'):
            req.fulfill(body=json.dumps(usage),headers={'Content-Type':'application/json','Content-Disposition':'attachment; filename=synthetic.json'})
            return
        target = WEB / ('index.html' if path == '/' else path.lstrip('/'))
        if target.is_file() and target.resolve().is_relative_to(WEB.resolve()):
            req.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        else: req.fulfill(status=404,body='not found')

    def no_overflow(page, label):
        for width in (320,390,768,1280,1440):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{label} overflow at {width}'
        page.set_viewport_size({'width':1440,'height':1000})

    with sync_playwright() as pw:
        opts = {'headless':True}
        if os.environ.get('AOE2_BROWSER_EXECUTABLE'): opts['executable_path'] = os.environ['AOE2_BROWSER_EXECUTABLE']
        browser = pw.chromium.launch(**opts)
        try:
            page = browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
            page.route('http://127.0.0.1:9999/**',route)
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.on('download',lambda download: downloads.append(download))
            page.goto('http://127.0.0.1:9999/',wait_until='networkidle')
            assert page.locator('#wizardPanel0').is_visible()
            assert page.locator('#agent').input_value() == 'auto'
            assert page.locator('#nextStep').is_enabled()
            assert not consents and not posts
            assert not page.locator('#usagePanel').is_visible()
            page.locator('#agent').focus(); page.keyboard.press('Enter')
            assert not consents and not posts
            assert not page.locator('#preflightNotice').count()
            assert not consents and not posts
            no_overflow(page,'authorization')
            page.screenshot(path=str(OUT/'01-authorization-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(OUT/'01-authorization-mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('#nextStep').click()
            page.locator('#wizardPanel1').wait_for(state='visible')
            assert page.locator('#wizardPanel1').is_visible()
            assert len(consents) == 1 and consents[0]['usage_authorized'] is True
            assert page.locator('#meterStatus').inner_text() == 'Agent 正在接入'
            assert page.locator('#revokeUsage').is_visible()
            assert not page.locator('input[name=mode]:checked').count()
            assert not posts
            no_overflow(page,'modes')
            page.screenshot(path=str(OUT/'02-mode-desktop.png'),full_page=True)
            page.locator('input[name=mode][value="2v2"]').check()
            page.locator('#nextStep').click()
            assert page.locator('#civilizationGrid button').count() == 44
            assert page.locator('#civilizationGrid button').nth(0).get_attribute('data-civilization') == 'auto'
            assert page.locator('#civilizationGrid button').nth(1).get_attribute('data-civilization') == 'random'
            assert page.locator('.special-civ-shield').count() == 2
            page.wait_for_function("[...document.querySelectorAll('#civilizationGrid img')].every(i => i.complete && i.naturalWidth > 0)")
            assert page.locator('#civilizationGrid img').evaluate_all('(xs)=>xs.every(x=>getComputedStyle(x).objectFit === "contain")')
            first, second = civs['civilizations'][:2]
            page.locator('[data-civilization="auto"]').click()
            assert page.locator('#civilization').input_value() == 'auto'
            page.locator('[data-civilization="random"]').click()
            random_choice = page.locator('#civilization').input_value()
            assert random_choice in {c['id'] for c in civs['civilizations']}
            page.locator(f'[data-civilization="{first["id"]}"]').hover()
            assert page.locator('#detailName').inner_text() == first['name']
            assert page.locator('#civilization').input_value() == random_choice
            page.locator('#civilizationSearch').fill(first['name'])
            assert page.locator('#civilizationGrid button:visible').count() >= 1
            page.locator(f'[data-civilization="{first["id"]}"]').click()
            page.locator('#civilizationSearch').fill('no-such-civilization')
            assert page.locator('#civilizationGrid button:visible').count() == 2
            assert not page.locator('#civilizationEmpty').is_visible()
            page.locator('#civilizationSearch').fill('')
            page.locator(f'[data-civilization="{second["id"]}"]').focus()
            assert page.locator('#civilization').input_value() == first['id']
            no_overflow(page,'civilizations')
            page.screenshot(path=str(OUT/'03-civilizations-desktop.png'),full_page=True)
            page.reload(wait_until='networkidle')
            assert page.locator('#wizardPanel2').is_visible()
            assert page.locator('#civilization').input_value() == first['id']
            assert len(consents) == 1
            page.locator('#nextStep').click()
            assert page.locator('#wizardPanel3').is_visible()
            assert page.locator('#scriptName').input_value()
            assert not page.locator('input[name=output_mode]:checked').count()
            assert page.locator('#startButton').is_disabled()
            name = page.locator('#scriptName').input_value()
            page.locator('#suggestName').click()
            assert page.locator('#scriptName').input_value() != name
            page.locator('#scriptName').fill('Bad Name')
            assert page.locator('#startButton').is_disabled()
            page.locator('#scriptName').fill('Studio_Test')
            assert page.locator('input[name=preference_mode][value="manual"]').is_checked()
            page.locator('input[name=preference_mode][value="auto"]').check()
            assert not page.locator('#manualPreferences').is_visible()
            page.locator('input[name=preference_mode][value="manual"]').check()
            assert page.locator('#manualPreferences').is_visible()
            page.locator('#imperial').fill('83')
            assert page.locator('#startButton').is_disabled()
            page.locator('input[name=output_mode][value="share_package"]').check()
            assert page.locator('#startButton').is_enabled()
            no_overflow(page,'preferences')
            page.screenshot(path=str(OUT/'04-preferences-desktop.png'),full_page=True)
            flags['offline'] = True
            page.reload(wait_until='networkidle')
            assert page.locator('#nextStep').is_disabled()
            assert not posts
            flags['offline'] = False
            page.reload(wait_until='networkidle')
            assert page.locator('#wizardPanel3').is_visible()
            assert page.locator('#scriptName').input_value() == 'Studio_Test'
            assert page.locator('input[name=output_mode][value="share_package"]').is_checked()
            assert page.locator('#startButton').is_enabled()
            page.locator('#startButton').click()
            page.wait_for_function("document.querySelector('#generationDashboard').hidden === false")
            assert len(posts) == 1 and posts[0]['preferences']['imperial'] == 83
            assert posts[0]['preference_mode'] == 'manual'
            assert posts[0]['output_mode'] == 'share_package'
            assert not page.locator('#authorForm').is_visible()
            assert page.locator('#progressPanel').is_visible()
            assert not page.locator('#usagePanel').is_visible()
            assert not page.locator('#reportPanel').is_visible()
            assert page.locator('#wizardNav1').is_disabled()
            page.reload(wait_until='networkidle')
            assert len(posts) == 1
            state['progress'] = {'filled':1029,'total':1715}
            page.locator('#refreshButton').click()
            page.wait_for_function("document.querySelector('#progressPercent').textContent === '60%'")
            no_overflow(page,'progress')
            page.screenshot(path=str(OUT/'05-progress-desktop.png'),full_page=True)
            page.locator('[data-result=usage]').click()
            assert page.locator('#usageTokens').inner_text() == '未采集'
            assert page.locator('#inputTokens').inner_text() == '未提供'
            assert not page.locator('#progressPanel').is_visible()
            # The screenshots below use explicitly synthetic data, never claimed as actual token usage.
            usage.update(coverage='PARTIAL',tokens={'total_tokens':42680,'input_tokens':38200,'output_tokens':4480,
                'cached_input_tokens':21000,'reasoning_tokens':1200,'usage_interval_records':9,'request_records':3,
                'turn_records':0,'unknown_outcome_records':2,'missing_usage_records':1,'retry_records':0,'retry_tokens':0},
                time={'elapsed_seconds':383,'workflow_seconds':341,'unobserved_seconds':None},
                capture_gaps=[{'message':'合成测试：一个子代理来源未覆盖；此数字仅用于界面测试。'}],
                by_model=[{'model':'synthetic-model','total_tokens':42680}],
                stages=[{'label':'设置与授权','total_tokens':1200,'elapsed_seconds':42,'action_attempts':1,'action_failures':0},
                        {'label':'策略创作','total_tokens':41480,'elapsed_seconds':341,'action_attempts':8,'action_failures':1}])
            state['usage_connection']={'status':'RECORDING','can_revoke':True,'reason':'合成界面测试数据，不代表实际调用。'}
            page.reload(wait_until='networkidle'); page.locator('[data-result=usage]').click()
            no_overflow(page,'usage')
            assert page.locator('#usageTokens').inner_text() == '42,680'
            assert page.locator('#cacheWriteTokens').inner_text() == '未提供'
            page.screenshot(path=str(OUT/'06-usage-desktop-synthetic.png'),full_page=True)
            page.locator('[data-result=report]').click()
            page.locator('#reportFeedback').fill('Synthetic UI observation')
            page.locator('#generateReportButton').click()
            page.locator('#reportOutput').wait_for(state='visible')
            assert page.locator('#reportOutput').input_value().startswith('# Synthetic')
            assert not downloads, 'Generating a report must not force a download'
            no_overflow(page,'report')
            page.locator('#revokeUsage').click()
            page.wait_for_function("document.querySelector('#meterStatus').textContent === '计量已停止'")
            assert page.locator('#meterStatus').inner_text() == '计量已停止'
            assert not page.locator('#revokeUsage').is_visible()
            page.locator('[data-result=usage]').click()
            assert page.locator('#usageTokens').inner_text() == '42,680', 'Keep previously recorded totals after revocation'
            with page.expect_download(): page.locator('.export-links a').first.click()
            # Fresh project: one opt-out click, no source selection, no accidental grant.
            state.update(project_id='synthetic-studio-b',status='configuring',revision=0,request=None,
                usage_authorization=None,usage_connection={'status':'NOT_AUTHORIZED','can_revoke':False})
            usage['tokens']={'total_tokens':None}
            page.reload(wait_until='networkidle')
            assert page.locator('#wizardPanel0').is_visible()
            assert not page.locator('input[name=mode]:checked').count()
            page.locator('#skipMetering').click()
            page.locator('#wizardPanel1').wait_for(state='visible')
            assert page.locator('#wizardPanel1').is_visible()
            assert consents[-1]['usage_authorized'] is False
            assert page.locator('#meterStatus').inner_text() == '本轮不计量'
            assert len(posts) == 1
            assert not errors, errors
            checks = ['explicit one-click authorization and opt-out; no consent via Enter',
                'no default game mode; AI/random special shields plus 42 real shields; search, hover and keyboard selection',
                'project-scoped draft and offline recovery; required raw/share output choice; direct start exactly once',
                'progress, usage, report are separate flat views; disabled past steps',
                'unknown counters stay unknown; synthetic totals and revocation retain data',
                'report preview does not auto-download; explicit download works',
                'no horizontal overflow in every view at 320/390/768/1280/1440px']
            report={'status':'PASS','checks':checks,'page_errors':errors,'synthetic_start_requests':len(posts),
                    'real_projects_accessed':False,'screenshots_use_synthetic_usage':True}
            (OUT/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
        finally: browser.close()


if __name__ == '__main__': main()
