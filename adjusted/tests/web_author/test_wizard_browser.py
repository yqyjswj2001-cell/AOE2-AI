"""Synthetic browser regression; routes never read or mutate real author projects."""
from pathlib import Path
import copy
import json
import mimetypes
import sys
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "adjusted/web-author/web"
OUT = ROOT / "adjusted/.local/ui-token-revision"
sys.path.insert(0, str(WEB.parent))
from civilization_catalog import catalog
from agent_catalog import agent_catalog

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    civs = catalog()
    agent_rows = agent_catalog()
    project = {"project_id": "synthetic-wizard-a", "status": "configuring", "revision": 1,
               "civilizations": [{"id": c["id"], "name": c["name"]} for c in civs["civilizations"]],
               "content_profile": civs["content_profile"], "request": None, "usage_authorization": None,
               "usage_access": {"cursor_admin_configured": False, "copilot_telemetry_configured": False},
               "progress": {"filled": None, "total": 1715}}
    usage = {"state": "RUNNING", "coverage": "NOT_CONNECTED",
             "tokens": {"total_tokens": None}, "time": {"elapsed_seconds": 17},
             "auto_capture": {"status": "NO_BINDINGS", "selected_agent": None,
                              "connection": {"code": "NO_BINDINGS", "message": "尚未绑定本轮会话。", "action": "请宿主绑定本轮真实会话 ID。"}},
             "capture_gaps": [], "stages": [], "by_model": []}
    flags = {"catalog_failure": False, "submit_timeout": False}
    posts, errors, checks = [], [], []
    def route(req):
        parsed = urlsplit(req.request.url)
        path = parsed.path
        if path == "/api/state": req.fulfill(json=copy.deepcopy(project)); return
        if path == "/api/author/usage": req.fulfill(json=copy.deepcopy(usage)); return
        if path in ("/api/civilizations", "/api/agents"):
            if flags["catalog_failure"]: req.fulfill(status=404, json={"error":"synthetic old server"}); return
            req.fulfill(json=civs if path.endswith("civilizations") else {"agents": agent_rows}); return
        if path == "/api/usage/authorize":
            body = req.request.post_data_json
            project.update(revision=project["revision"]+1,
                usage_authorization={"agent":body["agent"],"authorized":body["usage_authorized"],"decided_at":1})
            req.fulfill(json=copy.deepcopy(project)); return
        if path == "/api/start":
            body = req.request.post_data_json
            posts.append(body)
            project.update(status="authoring", revision=project["revision"]+1,
                request={k:v for k,v in body.items() if k != "expected_revision"})
            req.fulfill(json={"ok":True}); return
        if path == "/api/author/usage/export":
            req.fulfill(status=200, body=json.dumps(usage), headers={"Content-Type":"application/json","Content-Disposition":"attachment; filename=synthetic-usage.json"}); return
        target = WEB / ("index.html" if path == "/" else path.lstrip("/"))
        if target.is_file() and target.resolve().is_relative_to(WEB.resolve()):
            req.fulfill(body=target.read_bytes(), content_type=mimetypes.guess_type(str(target))[0] or "application/octet-stream"); return
        req.fulfill(status=404, body="Not found")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="msedge")
        try:
            context = browser.new_context(viewport={"width":1440,"height":1000}, reduced_motion="reduce")
            context.route("**/*", route)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://wizard.test/", wait_until="networkidle")
            page.wait_for_selector("#agent", state="attached")
            assert page.locator("#wizardPanel0").is_visible()
            assert page.locator("#nextStep").is_disabled()
            assert not page.locator("#generationDashboard").is_visible()
            assert not page.locator("#usagePanel").is_visible()
            page.locator("#agent").select_option("cursor")
            assert "Cursor" in page.locator("#agentHelp").inner_text()
            page.locator("#agent").select_option("codex")
            page.locator('input[name="usage_auth"][value="allow"]').check()
            assert page.locator("#nextStep").is_enabled()
            page.locator("#nextStep").click()
            assert page.locator("#wizardPanel1").is_visible()
            page.locator('input[name="mode"][value="ffa8"]').check()
            page.locator("#nextStep").click()
            assert page.locator("#wizardPanel2").is_visible()
            assert page.locator("#civilizationGrid button").count() == 42
            assert page.locator("#civilizationGrid img").evaluate_all("(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0&&getComputedStyle(x).objectFit==='contain')")
            first, second = civs["civilizations"][:2]
            page.locator(f'[data-civilization="{first["id"]}"]').hover()
            assert page.locator("#detailName").inner_text() == first["name"]
            assert page.locator("#civilization").input_value() == ""
            assert not posts
            page.locator(f'[data-civilization="{first["id"]}"]').click()
            assert page.locator("#wizardPanel2").is_visible()
            assert page.locator("#civilization").input_value() == first["id"]
            page.locator(f'[data-civilization="{second["id"]}"]').focus()
            assert page.locator("#detailName").inner_text() == second["name"]
            assert page.locator("#civilization").input_value() == first["id"]
            page.keyboard.press("ArrowRight")
            assert page.locator("#civilization").input_value() == first["id"]
            page.mouse.move(2, 2)
            page.screenshot(path=str(OUT / "wizard-civilizations-desktop.png"), full_page=True)
            page.reload(wait_until="networkidle")
            assert page.locator("#wizardPanel2").is_visible()
            assert page.locator("#civilization").input_value() == first["id"]
            assert not posts
            checks.append("42 real shields; hover/focus preview without selection; click selects without submitting; project draft restores step")
            for width in (320,375,414,768):
                page.set_viewport_size({"width":width,"height":900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"overflow at {width}"
                assert page.locator("#civilizationGrid img").evaluate_all("(xs)=>xs.every(x=>getComputedStyle(x).objectFit==='contain')")
                if width in (375,768): page.screenshot(path=str(OUT / f"wizard-civilizations-{width}.png"), full_page=True)
            checks.append("civilization layout has no page overflow at 320/375/414/768/1440; no shield cropping")
            page.set_viewport_size({"width":1440,"height":1000})
            page.locator("#nextStep").click()
            assert page.locator("#wizardPanel4").is_visible()
            page.locator("#scriptName").fill("Synthetic_Wizard")
            page.locator("#dark").fill("25")
            page.locator("#imperial").fill("83")
            page.locator("#scriptName").press("Enter")
            assert not posts
            page.locator("#nextStep").click()
            assert page.locator("#wizardPanel3").is_visible()
            assert not page.locator("#generationDashboard").is_visible()
            assert not posts
            assert "OpenAI Codex" in page.locator("#selectionSummary").inner_text()
            page.locator("#wizardNav3").click()
            page.reload(wait_until="networkidle")
            assert page.locator("#wizardPanel3").is_visible()
            assert page.locator("#agent").input_value() == "codex"
            assert page.locator('input[name="usage_auth"][value="allow"]').is_checked()
            assert page.locator("#scriptName").input_value() == "Synthetic_Wizard"
            for width in (320,375,414,768):
                page.set_viewport_size({"width":width,"height":900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"settings overflow at {width}"
            page.set_viewport_size({"width":1440,"height":1000})
            page.screenshot(path=str(OUT / "wizard-settings-desktop.png"), full_page=True)
            page.locator("#nextStep").click()
            page.locator("#startButton").click()
            page.wait_for_function("document.querySelector('#statusBadge').textContent==='生成中'")
            assert page.locator("#generationDashboard").is_visible()
            assert page.locator("#usagePanel").is_visible()
            assert not page.locator("#authorForm").is_visible()
            assert len(posts) == 1 and posts[0]["agent"] == "codex" and posts[0]["usage_authorized"] is True
            assert posts[0]["civilization"] == first["id"] and posts[0]["preferences"]["imperial"] == 83
            assert page.locator("#startButton").is_disabled()
            page.reload(wait_until="networkidle")
            assert len(posts) == 1 and page.locator("#generationDashboard").is_visible()
            page.screenshot(path=str(OUT / "wizard-progress-desktop.png"), full_page=True)
            checks.append("agent required; help says selection is not connection; settings restored; Enter cannot start from settings; final start sends once and reload never resubmits")
            project.update(project_id="synthetic-wizard-b",status="configuring",revision=1,request=None,usage_authorization=None)
            page.reload(wait_until="networkidle")
            assert page.locator("#wizardPanel0").is_visible()
            assert not page.locator('input[name="mode"]:checked').count()
            assert page.locator("#civilization").input_value() == ""
            assert page.locator("#agent").input_value() == ""
            assert not page.locator('input[name="usage_auth"]:checked').count()
            page.locator("#agent").select_option("codex")
            page.locator('input[name="usage_auth"][value="decline"]').check()
            page.locator("#nextStep").click()
            page.locator('input[name="mode"][value="1v1"]').check()
            page.locator("#nextStep").click()
            page.locator("#autoCivilization").click()
            assert page.locator("#civilization").input_value() == "auto"
            assert len(posts) == 1
            checks.append("draft isolated by project; automatic civilization is an explicit selectable option")
            project.update(status="completed", revision=9,
                request={"mode":"1v1","civilization":first["id"],"script_name":"Legacy_Test","preferences":dict.fromkeys(("dark","feudal","castle","imperial"),50)},
                progress={"filled":1715,"total":1715,"errors":[]},
                build={"installable":False,"script_name":"Legacy_Test","build_id":"synthetic-only"})
            flags["catalog_failure"] = True
            page.reload(wait_until="networkidle")
            assert page.locator("#statusBadge").inner_text() == "文件已生成"
            assert page.locator("#generationDashboard").is_visible()
            assert "暂不能直接安装" in page.locator("#buildDetails").inner_text()
            assert len(posts) == 1
            export_links = page.locator(".export-links a").evaluate_all("(xs)=>xs.map(x=>x.getAttribute('href'))")
            assert export_links == ["/api/author/usage/export?format=json", "/api/author/usage/export?format=stages", "/api/author/usage/export?format=calls"]
            checks.append("legacy project with no agent and catalog 404 retains state, progress, build details and all three export links")
            assert not errors, errors
            (OUT / "wizard-browser-report.json").write_text(json.dumps({"status":"PASS","checks":checks,"page_errors":errors,"synthetic_start_requests":len(posts),"real_projects_accessed":False,"limits":["Browser-native download transport is not established by the intercepted synthetic fixture."]},ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({"status":"PASS","checks":checks,"page_errors":errors},ensure_ascii=False))
        finally:
            browser.close()


def binding_preview():
    """One focused synthetic binding POST and requested desktop viewport previews."""
    OUT.mkdir(parents=True, exist_ok=True)
    civs, agents = catalog(), agent_catalog()
    project_id = "synthetic-desktop-and-binding"
    selected = {"mode":"ffa8","civilization":civs["civilizations"][0]["id"],"agent":"codex","script_name":"Synthetic_Only","preferences":dict.fromkeys(("dark","feudal","castle","imperial"),50)}
    state = {"project_id":project_id,"status":"authoring","revision":7,"request":selected,"civilizations":civs["civilizations"],"progress":{"filled":420,"total":1715,"errors":[]}}
    usage = {"run_id":"synthetic-meter-run","state":"RUNNING","coverage":"NOT_CONNECTED","tokens":{"total_tokens":None},"time":{"elapsed_seconds":17},
        "auto_capture":{"selected_agent":"codex","status":"WAITING_FOR_USAGE","bound_session_count":0,"session_candidates":[{"session_id":"synthetic-current-session-12345678","updated_at":"2026-09-22T03:20:00Z","is_child":False,"workspace_match":True}],
            "connection":{"code":"AUTO_SESSION_DISCOVERY","message":"正在自动确认本轮宿主会话；无需手动选择。","action":"wait_for_usage","action_label":"等待用量记录。"}}}
    posts, errors, dimensions = [], [], []
    def route(request):
        path=urlsplit(request.request.url).path
        if path=="/api/state": request.fulfill(json=state); return
        if path=="/api/author/usage": request.fulfill(json=usage); return
        if path=="/api/civilizations": request.fulfill(json=civs); return
        if path=="/api/agents": request.fulfill(json={"agents":agents}); return
        target=WEB/("index.html" if path=="/" else path.lstrip("/"))
        if target.is_file() and target.resolve().is_relative_to(WEB.resolve()):
            request.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0] or "application/octet-stream"); return
        request.fulfill(status=404,body="not found")
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,channel="msedge")
        try:
            context=browser.new_context(viewport={"width":1440,"height":1080},reduced_motion="reduce")
            context.route("**/*",route)
            draft={"schema":"aoe2-parameter-web-draft-v2","project_id":project_id,"step":1,"value":selected}
            context.add_init_script("localStorage.setItem("+json.dumps("aoe2.web-author.draft."+project_id)+","+json.dumps(json.dumps(draft))+");")
            page=context.new_page()
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.goto("http://wizard.test/",wait_until="networkidle")
            page.wait_for_function("document.querySelector('#generationDashboard') && !document.querySelector('#generationDashboard').hidden")
            for width in (1440,1920):
                page.set_viewport_size({"width":width,"height":1080})
                page.evaluate("scrollTo(0,0)")
                page.screenshot(path=str(OUT/f"wizard-civilizations-{width}x1080.png"),full_page=False)
                dimensions.append(page.evaluate("""()=>({viewport:innerWidth,gridTop:document.querySelector('#civilizationGrid').getBoundingClientRect().top,gridBottom:document.querySelector('#civilizationGrid').getBoundingClientRect().bottom,lastShieldBottom:[...document.querySelectorAll('#civilizationGrid img')].at(-1).getBoundingClientRect().bottom,horizontalOverflow:document.documentElement.scrollWidth>innerWidth})"""))
            assert all(row["lastShieldBottom"]<1080 and not row["horizontalOverflow"] for row in dimensions),dimensions
            assert "无需手动选择" in page.locator("#usageCapture").inner_text()
            assert page.locator("#sessionBinding").count() == 0
            assert page.locator("#usageSession").count() == 0
            assert page.locator("#bindSessionButton").count() == 0
            assert not posts
            assert not errors,errors
            report={"status":"PASS","scope":"automatic session discovery UI and two desktop visual previews","real_projects_accessed":False,"binding_requests":posts,"page_errors":errors,"dimensions":dimensions}
            (OUT/"wizard-binding-visual-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(report,ensure_ascii=False))
        finally:
            browser.close()

if __name__ == "__main__":
    binding_preview() if "--binding-preview" in sys.argv else main()

