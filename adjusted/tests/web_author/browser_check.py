"""Synthetic browser check. Never invokes a model or installs a game AI."""
from pathlib import Path
import json, os, subprocess, sys, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "adjusted/.local/web-author-migration"
PROJECT = TASK / "tmp/browser-check"
EVIDENCE = TASK / "evidence"
CLI = ROOT / "adjusted/web-author/web_session.py"

def main():
    if PROJECT.exists():
        raise RuntimeError("Use a fresh browser fixture; previous evidence must not be overwritten")
    EVIDENCE.mkdir(exist_ok=True, parents=True)
    env = dict(os.environ, AOE2_USAGE_DISABLE_AUTO="1")
    env.pop("CODEX_THREAD_ID", None)
    checks = []
    errors = []
    def cli(command):
        p = subprocess.run([sys.executable,"-X","utf8","-B",str(CLI),command,
                            "--project",str(PROJECT),"--test-project"] +
                           (["--no-browser"] if command=="launch" else []),
                           env=env,capture_output=True,text=True,encoding="utf-8")
        if p.returncode:
            raise RuntimeError(p.stderr or p.stdout)
        return json.loads(p.stdout)
    meta = None
    try:
        cli("launch")
        meta = json.loads((PROJECT/".author-web-session.json").read_text(encoding="utf-8"))
        base = meta["url"]
        def call(route, body=None, auth=False, raw=False):
            headers={}
            if auth:
                headers["X-Author-Token"]=meta["host_token"]
            if body is not None:
                headers["Content-Type"]="application/json"
            req=urllib.request.Request(base+route,
                json.dumps(body).encode() if body is not None else None, headers)
            with urllib.request.urlopen(req,timeout=30) as response:
                data=response.read()
                return (data,response.headers.get("Content-Type")) if raw else json.loads(data)
        def post_usage(action, fields):
            state=call("/api/author/next",auth=True)
            meter=call("/api/author/usage")
            return call("/api/author/usage/"+action,dict(fields,project_id=meta["project_id"],
                expected_revision=state["revision"],run_id=meter["run_id"]),auth=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,channel="msedge")
            try:
                page=browser.new_page(viewport={"width":1280,"height":960})
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(base,wait_until="networkidle")
                page.wait_for_selector("select")
                page.wait_for_function("document.querySelector('#civilization').options.length === 43")
                body=page.locator("body").inner_text()
                assert "生成简报" not in body and "批准简报" not in body
                assert "未采集" in body or "未接入" in body
                checks.append("initial_unknown_and_no_brief")
                page.locator('input[name="mode"][value="ffa8"]').check()
                page.locator("#civilization").select_option("Portuguese")
                page.locator("#scriptName").fill("BrowserFixture")
                page.locator('input[type=range]').first.fill("64")
                page.reload(wait_until="networkidle")
                assert page.locator('input[name="mode"]:checked').input_value()=="ffa8"
                assert page.locator("#civilization").input_value()=="Portuguese"
                assert page.locator("#scriptName").input_value()=="BrowserFixture"
                checks.append("draft_survives_refresh")
                page.get_by_role("button",name="开始创作",exact=True).click()
                page.wait_for_function("fetch('/api/state').then(r=>r.json()).then(s=>s.status==='authoring')",timeout=30000)
                state=call("/api/state")
                assert state["progress"]["total"]==1715 and state["progress"]["filled"]==0
                assert state["request"]["mode"]=="ffa8"
                assert "brief" not in state
                assert not state["build"]
                checks.append("start_directly_enters_parameter_authoring")
                try:
                    call("/api/author/next")
                    raise AssertionError("Host API accepted unauthenticated request")
                except urllib.error.HTTPError as e:
                    assert e.code==403
                checks.append("host_action_binding")
                post_usage("source",{"source_id":"synthetic-browser","format":"openai-responses"})
                event={"event_id":"synthetic-event-1","model":"synthetic-test","phase":"3",
                       "outcome":"succeeded","usage":{"input_tokens":100,"output_tokens":20,
                       "input_tokens_details":{"cached_tokens":15},
                       "output_tokens_details":{"reasoning_tokens":5},"total_tokens":120}}
                post_usage("events",{"source_id":"synthetic-browser","events":[event]})
                post_usage("events",{"source_id":"synthetic-browser","events":[event]})
                report=call("/api/author/usage")
                assert report["tokens"]["total_tokens"]==120,report["tokens"]
                assert report["coverage"]=="PARTIAL"
                exported=call("/api/author/usage/export?format=json")
                assert exported["tokens"]==report["tokens"]
                assert "auto_capture" in exported
                for kind in ("stages","calls"):
                    raw,mime=call("/api/author/usage/export?format="+kind,raw=True)
                    assert "csv" in mime and raw.startswith(b"\xef\xbb\xbf"),(kind,mime)
                    assert b"run_id" in raw
                checks.append("usage_deduplicated_and_json_csv_consistent")
                page.reload(wait_until="networkidle")
                page.wait_for_timeout(1200)
                assert "120" in page.locator("body").inner_text()
                assert not page.locator("#startButton").is_enabled()
                page.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
                page.screenshot(path=str(EVIDENCE/"web-desktop.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                page.wait_for_timeout(200)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                page.screenshot(path=str(EVIDENCE/"web-mobile.png"),full_page=True)
                checks.append("meter_visible_and_mobile_layout")
                current=call("/api/author/next",auth=True)
                try:
                    call("/api/host/validate",{"project_id":meta["project_id"],
                         "expected_revision":current["revision"]},auth=True)
                    raise AssertionError("Null answers passed validation")
                except urllib.error.HTTPError as e:
                    assert e.code==409
                assert call("/api/state")["status"]=="invalid"
                assert not (PROJECT/"delivery").exists()
                checks.append("null_answers_rejected_without_output")
                assert not errors,errors
                checks.append("no_browser_script_errors")
            finally:
                browser.close()
    finally:
        if meta and (PROJECT/".author-web-session.json").exists():
            cli("finish")
    result={"ok":True,"checks":checks,"javascript_errors":errors,
            "synthetic_usage":True,"real_host_full_coverage":"Unverified",
            "model_invocations":0,"game_installations":0}
    (EVIDENCE/"browser-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
