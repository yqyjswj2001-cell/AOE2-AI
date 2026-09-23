# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/tests/web_author/test_wizard_browser.py', '7590a0b2785aa754454bc8a7602134c90f19ef5ba1145f5d0bbc142af7679ee4', '41e5cb759ba1a65d2888fdefe4cdf0792d886a753e3d1b26a01cbe66c8bd915b', [
(0, 1, r'''"""Synthetic browser regression. No real project, account or paid model is used."""
'''),
(5, 5, r'''import os
'''),
(7, 8, r''''''),
(10, 12, r'''WEB = ROOT / 'adjusted/web-author/web'
OUT = Path(os.environ.get('AOE2_UI_TEST_OUTPUT', ROOT / 'adjusted/.local/studio-review'))
'''),
(16, 16, r'''
'''),
(17, 17, r'''    from playwright.sync_api import sync_playwright
'''),
(18, 32, r'''    civs, agents = catalog(), agent_catalog()
    usage = {'state':'RUNNING', 'coverage':'NOT_CONNECTED', 'tokens':{'total_tokens':None},
             'time':{'elapsed_seconds':17}, 'auto_capture':{'selected_agent':'auto'}, 'stages':[]}
    state = {'project_id':'synthetic-studio-a','revision':0,'status':'configuring','host_agent':'auto',
             'civilizations':civs['civilizations'],'request':None,'build':None,'usage_authorization':None,
             'usage':usage,'progress':{'filled':0,'total':1715},
             'usage_connection':{'status':'NOT_AUTHORIZED','can_revoke':False}}
    posts, consents, errors, checks, downloads = [], [], [], [], []
    flags = {'offline':False}

'''),
(33, 41, r'''        path = urlsplit(req.request.url).path
        if path == '/api/state':
            if flags['offline']: req.abort('connectionrefused')
            else: req.fulfill(json=copy.deepcopy(state))
            return
        if path == '/api/author/usage': req.fulfill(json=copy.deepcopy(usage)); return
        if path == '/api/civilizations': req.fulfill(json=civs); return
        if path == '/api/agents': req.fulfill(json={'agents':agents}); return
        if path == '/api/usage/authorize':
'''),
(42, 46, r'''            assert body['expected_revision'] == state['revision']
            consents.append(body)
            previous = state['usage_authorization'] or {}
            auth = {'agent':body['agent'],'authorized':body['usage_authorized'],'authorization_id':'synthetic-consent','decided_at':1}
            if previous.get('authorized') and not body['usage_authorized']: auth['revoked_at'] = 2
            code = 'CONNECTING' if body['usage_authorized'] else 'REVOKED' if auth.get('revoked_at') else 'DISABLED'
            state.update(revision=state['revision']+1,usage_authorization=auth,
                usage_connection={'status':code,'can_revoke':body['usage_authorized']})
            req.fulfill(json=copy.deepcopy(state)); return
        if path == '/api/start':
'''),
(47, 47, r'''            assert body['expected_revision'] == state['revision']
'''),
(48, 54, r'''            state.update(status='authoring',revision=state['revision']+1,request=body)
            req.fulfill(json=copy.deepcopy(state)); return
        if path == '/api/report/generate':
            req.fulfill(json={'markdown':'# Synthetic report\nNot game tested.', 'issue_count':1,'feedback_count':1,
                'download_url':'/api/report/download?id=test&format=main','details_url':'/api/report/download?id=test&format=details'})
            return
        if path in ('/api/author/usage/export','/api/report/download'):
            req.fulfill(body=json.dumps(usage),headers={'Content-Type':'application/json','Content-Disposition':'attachment; filename=synthetic.json'})
            return
        target = WEB / ('index.html' if path == '/' else path.lstrip('/'))
'''),
(55, 57, r'''            req.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        else: req.fulfill(status=404,body='not found')

    def no_overflow(page, label):
        for width in (320,390,768,1280,1440):
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{label} overflow at {width}'
        page.set_viewport_size({'width':1440,'height':1000})

'''),
(58, 59, r'''        opts = {'headless':True}
        if os.environ.get('AOE2_BROWSER_EXECUTABLE'): opts['executable_path'] = os.environ['AOE2_BROWSER_EXECUTABLE']
        browser = pw.chromium.launch(**opts)
'''),
(60, 83, r'''            page = browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
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
            assert page.locator('#civilizationGrid button').count() == 42
            page.wait_for_function("[...document.querySelectorAll('#civilizationGrid img')].every(i => i.complete && i.naturalWidth > 0)")
            assert page.locator('#civilizationGrid img').evaluate_all('(xs)=>xs.every(x=>getComputedStyle(x).objectFit === "contain")')
            first, second = civs['civilizations'][:2]
'''),
(84, 86, r'''            assert page.locator('#detailName').inner_text() == first['name']
            assert page.locator('#civilization').input_value() == ''
            page.locator('#civilizationSearch').fill(first['name'])
            assert page.locator('#civilizationGrid button:visible').count() >= 1
            page.locator(f'[data-civilization="{first["id"]}"]').click()
            page.locator('#civilizationSearch').fill('no-such-civilization')
            assert page.locator('#civilizationEmpty').is_visible()
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
            name = page.locator('#scriptName').input_value()
            page.locator('#suggestName').click()
            assert page.locator('#scriptName').input_value() != name
            page.locator('#scriptName').fill('Bad Name')
            assert page.locator('#startButton').is_disabled()
            page.locator('#scriptName').fill('Studio_Test')
            page.locator('#imperial').fill('83')
            no_overflow(page,'preferences')
            page.screenshot(path=str(OUT/'04-preferences-desktop.png'),full_page=True)
            flags['offline'] = True
            page.reload(wait_until='networkidle')
            assert page.locator('#nextStep').is_disabled()
'''),
(87, 159, r'''            flags['offline'] = False
            page.reload(wait_until='networkidle')
            assert page.locator('#wizardPanel3').is_visible()
            assert page.locator('#scriptName').input_value() == 'Studio_Test'
            assert page.locator('#startButton').is_enabled()
            page.locator('#startButton').click()
            page.wait_for_function("document.querySelector('#generationDashboard').hidden === false")
            assert len(posts) == 1 and posts[0]['preferences']['imperial'] == 83
            assert not page.locator('#authorForm').is_visible()
            assert page.locator('#progressPanel').is_visible()
            assert not page.locator('#usagePanel').is_visible()
            assert not page.locator('#reportPanel').is_visible()
            assert page.locator('#wizardNav1').is_disabled()
            page.reload(wait_until='networkidle')
'''),
(160, 170, r'''            state['progress'] = {'filled':1029,'total':1715}
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
'''),
(171, 174, r''''''),
(175, 179, r'''            checks = ['explicit one-click authorization and opt-out; no consent via Enter',
                'no default game mode; 42 real shields; search, hover and keyboard selection',
                'project-scoped draft and offline recovery; direct start exactly once',
                'progress, usage, report are separate flat views; disabled past steps',
                'unknown counters stay unknown; synthetic totals and revocation retain data',
                'report preview does not auto-download; explicit download works',
                'no horizontal overflow in every view at 320/390/768/1280/1440px']
            report={'status':'PASS','checks':checks,'page_errors':errors,'synthetic_start_requests':len(posts),
                    'real_projects_accessed':False,'screenshots_use_synthetic_usage':True}
            (OUT/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
        finally: browser.close()
'''),
(181, 234, r'''if __name__ == '__main__': main()
'''),
])
