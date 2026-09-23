"""Synthetic workflow and origin checks; no strategy authoring or game launch."""
from __future__ import annotations
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import zipfile

HERE = Path(__file__).resolve().parents[2] / "web-author"
sys.path.insert(0, str(HERE))
from controller import Controller, WorkflowError, digest, json_bytes, project_path
from server import make_server
from web_session import ActiveLock, SESSION_SCHEMA, SessionError, wait_for_agent


class FakeMeter:
    def __init__(self, project, identity):
        self.identity = identity
        self.closed = False
    def report(self, include_records=False):
        return {"run_id": "synthetic-run", "state": "ACTIVE", "tokens": {"total_tokens": None},
                "time": {"elapsed_seconds": 0}, "coverage": "NOT_CONNECTED", "stages": [], "calls": []}
    def phase(self, value):
        return self.report()
    def complete(self, build, all_sources_declared=False):
        self.closed = True
        return self.report()
    def close(self):
        self.closed = True
        return self.report()
    def handle(self, action, payload):
        return self.report()


class FakeEngine:
    fingerprint = "synthetic-fixed-input"
    def civilizations(self):
        return [{"id": "Synthetic", "name": "合成文明"}]
    def source_digest(self):
        return self.fingerprint
    def export(self, out):
        out.mkdir()
        files = {}
        for index in range(15):
            count = 1701 if index == 0 else 1
            for directory, payload in [
                    ("answers", {f"K_{index}_{key}": None for key in range(count)}),
                    ("strategy", {"kind": "synthetic", "module": str(index)})]:
                target = out / directory / (str(index) + ".json")
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(json_bytes(payload))
                files[target.relative_to(out).as_posix()] = digest(target.read_bytes())
        manifest = {"schema": "synthetic-test-input", "files": files, "dynamic_slots": 1715,
                    "fixed_source_included": False, "official_answers_included": False}
        (out / "manifest.json").write_bytes(json_bytes(manifest))
        return {"ok": True}
    def render(self, answers, out):
        for path in answers.glob("*.json"):
            if any(type(value) is not int or value < 1 for value in json.loads(path.read_bytes()).values()):
                raise WorkflowError("Synthetic constraint: positive integers")
        for index in range(36):
            (out / f"module{index}.per").write_text("; SYNTHETIC FIXTURE ONLY\n", encoding="utf-8")
    def package(self, modules, script_name, output):
        ai_root = output / "resources/_common/ai"
        module_root = ai_root / script_name
        module_root.mkdir(parents=True)
        for source in modules.glob("*.per"):
            (module_root / source.name).write_bytes(source.read_bytes())
        (ai_root / (script_name + ".ai")).write_bytes(b"")
        (ai_root / (script_name + ".per")).write_text(
            '(load "' + script_name + '\\\\module0")\n', encoding="utf-8")
        return {"entrypoint_validation": "PASS", "official_entrypoint_sha256": "synthetic",
                "loaded_modules": ["module0.per"],
                "unreferenced_modules": [f"module{i}.per" for i in range(1, 36)],
                "ai_root": "resources/_common/ai",
                "entrypoint": "resources/_common/ai/" + script_name + ".per"}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aoe2-web-workflow-")
        self.project = Path(self.temp.name) / "synthetic-project"
        self.engine = FakeEngine()
        self.app = Controller(self.project, engine=self.engine, meter_factory=FakeMeter)
    def tearDown(self):
        self.temp.cleanup()
    def payload(self, **extra):
        return {"expected_revision": self.app.state()["revision"], "project_id": self.app.data["project_id"], **extra}
    def start(self):
        return self.app.start(self.payload(mode="ffa8", civilization="Synthetic",
                             script_name="SYNTHETIC", preferences={age: 50 for age in ("dark", "feudal", "castle", "imperial")}))
    def fill(self, value=2):
        for path in (self.project / "answers").glob("*.json"):
            data = json.loads(path.read_bytes())
            path.write_bytes(json_bytes({key: value for key in data}))

    def test_start_is_explicit_and_input_remains_null(self):
        self.assertEqual(self.app.state()["status"], "configuring")
        self.assertFalse((self.project / "author-input").exists())
        state = self.start()
        self.assertEqual(state["status"], "authoring")
        self.assertEqual(state["progress"]["total"], 1715)
        with self.assertRaises(WorkflowError):
            self.start()
        self.fill()
        self.app.state()
        for path in (self.project / "author-input/answers").glob("*.json"):
            self.assertTrue(all(value is None for value in json.loads(path.read_bytes()).values()))
        with self.assertRaises(WorkflowError):
            self.app.validate({"expected_revision": 0, "project_id": state["project_id"]})

    def test_validation_build_and_answer_invalidation(self):
        self.start()
        with self.assertRaisesRegex(WorkflowError, "1715 missing") as raised:
            self.app.validate(self.payload())
        report_path = self.project / "tmp" / "answer-diagnostics.json"
        self.assertIn(str(report_path), str(raised.exception))
        diagnostics = json.loads(report_path.read_bytes())
        self.assertEqual(diagnostics["missing_count"], 1715)
        self.assertIn("K_0_0", diagnostics["missing"]["0.json"])
        self.assertEqual(diagnostics["invalid_count"], 0)
        self.fill()
        self.app.validate(self.payload())
        result = self.app.build(self.payload())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["build"]["modules"], 36)
        self.assertTrue(result["build"]["installable"])
        self.assertEqual(result["build"]["artifact_kind"], "aoe2de_ai_package")
        self.assertEqual(result["build"]["entrypoint_validation"], "PASS")
        self.assertTrue((Path(result["build"]["path"]) / "resources/_common/ai/SYNTHETIC.ai").is_file())
        self.assertTrue((Path(result["build"]["path"]) / "resources/_common/ai/SYNTHETIC.per").is_file())
        self.assertEqual(result["build"]["parser_load"], "Unverified")
        self.assertFalse(self.app.meter.closed, "Build must leave time for usage backfill")
        old_path = Path(result["build"]["path"])
        self.fill(3)
        state = self.app.state()
        self.assertEqual(state["status"], "authoring")
        self.assertIsNone(state["build"])
        self.assertTrue(old_path.is_dir(), "Earlier deliveries must be preserved")
        with self.assertRaises(WorkflowError):
            self.app.build(self.payload())

    def test_development_report_collects_failures_feedback_and_evidence(self):
        self.start()
        with self.assertRaises(WorkflowError):
            self.app.validate(self.payload())
        self.app.feedback(self.payload(kind="issue", source="author", message="参数卡有一处语义需要开发复核。"))
        self.fill()
        self.app.validate(self.payload())
        self.app.build(self.payload())
        result = self.app.development_report({
            "project_id": self.app.data["project_id"],
            "feedback": "网页复盘补充：检查报告下载链路。",
            "browser_observations": [{"kind":"synthetic_browser","message":"合成浏览器观察。","count":2}],
        })
        bundle = Path(result["bundle"])
        self.assertTrue(bundle.is_file())
        self.assertGreaterEqual(result["issue_count"], 2)
        self.assertGreaterEqual(result["feedback_count"], 2)
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            self.assertTrue({"report.md","report.json","usage.json","events.json","usage-stages.csv","usage-calls.csv"} <= names)
            report = json.loads(archive.read("report.json"))
            self.assertEqual(report["schema"], "aoe2-development-report-v1")
            self.assertTrue(any(event["kind"] == "validation_failed" for event in report["events"]))
            self.assertTrue(any(event["kind"] == "feedback_issue" for event in report["feedback"]))
            self.assertTrue(any(issue["source"] == "browser" for issue in report["issues"]))
            self.assertIn("AOE2 AI 创作报告", archive.read("report.md").decode("utf-8"))

    def test_source_delivery_input_and_boolean_guards(self):
        self.start()
        self.fill()
        self.app.validate(self.payload())
        build = self.app.build(self.payload())["build"]
        file = next((Path(build["path"]) / "resources/_common/ai/SYNTHETIC").glob("*.per"))
        file.write_text("altered", encoding="utf-8")
        self.assertEqual(self.app.state()["status"], "invalid")
        self.assertIsNone(self.app.state()["build"])
        self.engine.fingerprint = "changed"
        with self.assertRaises(WorkflowError):
            self.app.validate(self.payload())
        self.engine.fingerprint = FakeEngine.fingerprint
        self.fill(True)
        self.assertTrue(self.app.state()["progress"]["errors"])
        with self.assertRaises(WorkflowError):
            self.app.validate(self.payload())
        card = self.project / "author-input/strategy/0.json"
        card.write_text("{}", encoding="utf-8")
        with self.assertRaises(WorkflowError):
            self.app.validate(self.payload())

    def test_delivery_receipt_and_extra_file_guards(self):
        self.start()
        self.fill()
        self.app.validate(self.payload())
        receipt_build = self.app.build(self.payload())["build"]
        Path(receipt_build["receipt"]).write_text("{}", encoding="utf-8")
        self.assertEqual(self.app.state()["status"], "invalid")
        self.app.validate(self.payload())
        extra_build = self.app.build(self.payload())["build"]
        (Path(extra_build["path"]) / "unexpected.txt").write_text("extra", encoding="utf-8")
        self.assertEqual(self.app.state()["status"], "invalid")

    def test_persisted_identity_and_project_boundary(self):
        self.start()
        reopened = Controller(self.project, engine=self.engine, meter_factory=FakeMeter)
        self.assertEqual(reopened.data["project_id"], self.app.data["project_id"])
        self.assertEqual(reopened.state()["status"], "authoring")
        self.assertEqual(project_path("Example").name, "Example")
        self.assertEqual(project_path(self.project, True), self.project)
        with self.assertRaises(WorkflowError):
            project_path(self.project, False)
        with self.assertRaises(WorkflowError):
            project_path("../../outside")
        lock = Path(self.temp.name) / "active.lock"
        with ActiveLock(lock):
            with self.assertRaises(SessionError):
                with ActiveLock(lock):
                    pass

    def test_origin_host_identity_and_no_arbitrary_files(self):
        meta = {"instance_id": "instance", "project_id": self.app.data["project_id"], "host_token": "test-secret"}
        server = make_server(self.app, meta)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def request(method, route, payload=None, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            body = None if payload is None else json.dumps(payload)
            given = {"Content-Type": "application/json", **(headers or {})}
            connection.request(method, route, body, given)
            response = connection.getresponse()
            raw = response.read()
            connection.close()
            return response.status, raw
        try:
            self.assertEqual(request("GET", "/api/state")[0], 200)
            self.assertEqual(request("GET", "/api/author/next")[0], 403)
            self.assertEqual(request("GET", "/api/author/next", headers={"X-Author-Token": "test-secret"})[0], 200)
            self.assertEqual(request("GET", "/api/state", headers={"Origin": "http://evil.example"})[0], 403)
            self.assertEqual(request("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)
            self.assertEqual(request("GET", "/../../official/raw/Promisory/units.per")[0], 404)
            task = self.payload(mode="1v1", civilization="Synthetic", script_name="Fixture",
                                preferences={age: 50 for age in ("dark", "feudal", "castle", "imperial")})
            self.assertEqual(request("POST", "/api/start", task)[0], 403)
            self.assertEqual(request("POST", "/api/start", task, {"Origin": f"http://127.0.0.1:{server.server_port}"})[0], 200)
            report_status, report_raw = request("POST", "/api/report/generate",
                {"project_id": self.app.data["project_id"], "feedback": "synthetic browser feedback"},
                {"Origin": f"http://127.0.0.1:{server.server_port}"})
            self.assertEqual(report_status, 200)
            report_info = json.loads(report_raw)
            download_status, download_raw = request("GET", report_info["download_url"])
            self.assertEqual(download_status, 200)
            self.assertTrue(download_raw.startswith(b"PK"))
            self.assertEqual(request("POST", "/api/host/build", self.payload(), {"Origin": f"http://127.0.0.1:{server.server_port}"})[0], 403)
            public = json.loads(request("GET", "/api/state")[1])
            self.assertNotIn("host_token", public)
            self.assertNotIn("author_input", public)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_wait_has_a_twenty_second_ceiling(self):
        meta = {"project_id": "p", "instance_id": "i", "url": "http://127.0.0.1:1"}
        def read(meta, route, **kwargs):
            return {"schema": SESSION_SCHEMA, "project_id": "p", "instance_id": "i", "status": "configuring"}
        with self.assertRaises(SessionError):
            wait_for_agent(meta, 21, read=read)
        with self.assertRaises(SessionError):
            wait_for_agent(meta, float("inf"), read=read)
        result = wait_for_agent(meta, 0, read=read)
        self.assertEqual(result["web_event"], "WAIT_TIMEOUT")
        self.assertTrue(result["continue_waiting"])


if __name__ == "__main__":
    unittest.main()
