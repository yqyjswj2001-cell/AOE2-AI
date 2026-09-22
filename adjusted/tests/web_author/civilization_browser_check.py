"""Browser/host integration with synthetic choices and usage; no strategy creation."""
from pathlib import Path
import os,json,subprocess,sys,urllib.request,urllib.error
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/"adjusted/.local/civilization-selection"
PROJECT=TASK/"tmp/browser-check"
CLI=ROOT/"adjusted/web-author/web_session.py"

def main():
    assert not PROJECT.exists(),"Fixture must be fresh"
    env=dict(os.environ,AOE2_USAGE_DISABLE_AUTO="1");env.pop("CODEX_THREAD_ID",None)
    errors=[];checks=[];meta=None
    def cli(action,*extra,allow_error=False):
        p=subprocess.run([sys.executable,"-X","utf8","-B",str(CLI),action,
            "--project",str(PROJECT),"--test-project",*extra],env=env,capture_output=True,text=True,encoding="utf-8")
        if not allow_error:assert p.returncode==0,p.stderr or p.stdout
        return p
    try:
        cli("launch","--no-browser")
        meta=json.loads((PROJECT/".author-web-session.json").read_text(encoding="utf-8"))
        base=meta["url"]
        def call(path,body=None,auth=False):
            headers={}
            if auth:headers["X-Author-Token"]=meta["host_token"]
            if body is not None:headers["Content-Type"]="application/json"
            req=urllib.request.Request(base+path,json.dumps(body).encode() if body is not None else None,headers)
            with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
        def usage(action,fields):
            state=call("/api/author/next",auth=True); report=call("/api/author/usage")
            return call("/api/author/usage/"+action,dict(fields,project_id=meta["project_id"],
                expected_revision=state["revision"],run_id=report["run_id"]),auth=True)
        def choose(civ,revision,filename):
            path=PROJECT/"tmp"/filename;path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"civilization":civ,"expected_revision":revision,
                "reason":"合成接口验收：研究文明特色如何影响资源与兵力安排；本轮没有实际创作脚本。"},ensure_ascii=False),encoding="utf-8")
            return cli("choose-civilization","--choice",str(path),allow_error=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,channel="msedge")
            try:
                page=browser.new_page(viewport={"width":1280,"height":960})
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(base,wait_until="networkidle")
                page.wait_for_function("document.querySelector('#civilization').options.length===43")
                assert page.locator("#civilization").input_value()=="auto"
                values=page.locator("#civilization option").evaluate_all("(xs)=>xs.map(x=>x.value)")
                assert "Gurjaras" in values and "Bengalis" in values and "Bohemians" in values
                assert not set(values)&{"Romans","Armenians","Georgians","Jurchens","Khitans","Shu","Wei","Wu","Mapuche","Muisca","Tupi"}
                assert "42" in page.locator("#contentScope").inner_text()
                checks.append("default_auto_and_standard_42_filter")
                page.locator('input[name="mode"][value="ffa8"]').check()
                page.locator("#scriptName").fill("DiversityFixture")
                page.locator("#startButton").click()
                page.wait_for_function("fetch('/api/state').then(r=>r.json()).then(s=>s.status==='selecting')",timeout=30000)
                initial=call("/api/author/next",auth=True)
                assert initial["status"]=="selecting"
                assert len(initial["civilization_selection"]["eligible_ids"])==42
                assert len(initial["civilization_selection"]["suggested"])==6
                assert len(list((PROJECT/"answers").glob("*.json")))==15
                assert all(v is None for p in (PROJECT/"answers").glob("*.json") for v in json.loads(p.read_text()).values())
                before=call("/api/author/usage")
                assert cli("validate",allow_error=True).returncode!=0
                assert call("/api/state")["status"]=="selecting"
                checks.append("selection_before_parameters_without_brief")
                usage("source",{"source_id":"synthetic-selection","format":"openai-responses"})
                usage("events",{"source_id":"synthetic-selection","events":[{"event_id":"selection-usage",
                    "model":"synthetic","usage":{"input_tokens":200,"output_tokens":40},"phase":"1"}]})
                assert choose("Shu",initial["revision"],"invalid-dlc.json").returncode!=0
                assert choose("Gurjaras",initial["revision"]-1,"stale-choice.json").returncode!=0
                assert call("/api/state")["status"]=="selecting"
                chosen=choose("Gurjaras",initial["revision"],"choice.json")
                assert chosen.returncode==0,chosen.stderr
                state=call("/api/state");after=call("/api/author/usage")
                assert state["status"]=="authoring" and state["request"]["civilization"]=="Gurjaras"
                assert after["run_id"]==before["run_id"]
                assert after["context"]["task_sha256"]==before["context"]["task_sha256"]
                assert after["context"]["civilization"]=="Gurjaras"
                assert after["tokens"]["total_tokens"]==240
                assert choose("Britons",state["revision"],"second-choice.json").returncode!=0
                checks.append("dlc_stale_and_second_choices_rejected")
                usage("events",{"source_id":"synthetic-selection","events":[{"event_id":"parameter-usage",
                    "model":"synthetic","usage":{"input_tokens":30,"output_tokens":12},"phase":"3"}]})
                assert call("/api/author/usage")["tokens"]["total_tokens"]==282
                checks.append("token_ledger_continues_across_choice")
                page.reload(wait_until="networkidle")
                page.wait_for_function("document.querySelector('#civilization').value==='Gurjaras'")
                assert "合成接口验收" in page.locator("#civilizationDecisionReason").inner_text()
                assert not page.locator("#civilization").is_enabled()
                assert "282" in page.locator("#usageTokens").inner_text()
                assert "生成简报" not in page.locator("body").inner_text()
                page.evaluate("document.activeElement.blur();window.scrollTo(0,0)")
                page.screenshot(path=str(TASK/"evidence/selection-desktop.png"),full_page=True)
                page.set_viewport_size({"width":390,"height":844})
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
                assert not errors,errors
                checks.append("choice_reason_persists_and_ui_has_no_errors")
            finally:browser.close()
    finally:
        if meta and (PROJECT/".author-web-session.json").exists():cli("finish")
    result={"ok":True,"checks":checks,"javascript_errors":errors,"synthetic_choices":True,
            "synthetic_tokens":282,"actual_strategy_creations":0,"game_runs":0,
            "diversity_behavior_across_real_authors":"Unverified"}
    (TASK/"evidence/browser-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
