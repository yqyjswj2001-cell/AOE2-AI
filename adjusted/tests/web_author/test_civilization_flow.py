"""Synthetic selection checks: no game, model call or AI source access."""
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[2] / "web-author"
sys.path[:0] = [str(HERE), str(Path(__file__).resolve().parent)]
from civilizations import PROFILE_FILE, selection_context
from controller import Controller, RealEngine, WorkflowError, digest, json_bytes, project_path
from meter_adapter import MeterAdapter
from server import make_server
from test_workflow import FakeEngine
from web_session import SessionError, host_action


class SelectionEngine(FakeEngine):
    def civilizations(self):
        return [{"id": name, "name": name} for name in ("Portuguese", "Mongols", "Vikings")]


class CivilizationFlowTests(unittest.TestCase):
    def setUp(self):
        temporary = HERE.parent / ".local/civilization-selection/tmp"
        temporary.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="flow-", dir=temporary)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.engine = SelectionEngine()
        env = patch.dict(os.environ, {"AOE2_USAGE_DISABLE_AUTO": "1"})
        env.start()
        self.addCleanup(env.stop)
        history = patch("controller.selection_context", side_effect=lambda rows, identity:
                        selection_context(rows, identity, history_root=Path(self.temp.name) / "history"))
        history.start()
        self.addCleanup(history.stop)
        self.app = Controller(self.project, engine=self.engine, meter_factory=MeterAdapter)

    def payload(self, **extra):
        state = self.app.state()
        return {"project_id": state["project_id"], "expected_revision": state["revision"], **extra}

    def start(self, civilization="auto"):
        if not self.app.data.get("usage_authorization"):
            self.app.authorize_usage(self.payload(agent="auto", usage_authorized=True))
        return self.app.start(self.payload(mode="ffa8", civilization=civilization, script_name="Fixture",
                                           agent="auto", usage_authorized=True))

    def choose(self, civilization="Mongols"):
        return self.app.choose_civilization(self.payload(civilization=civilization,
                            reason="Use mobile mounted units to keep pressure while preserving the economy."))

    def reopen(self):
        self.app = Controller(self.project, engine=self.engine, meter_factory=MeterAdapter)
        return self.app.state()

    def test_auto_choice_keeps_one_meter_and_frozen_task(self):
        state = self.start()
        before = self.app.usage()
        frozen = dict(self.app.data["task_request"])
        self.assertEqual((state["status"], before["phase"]), ("selecting", "1"))
        self.assertIsNone(state["civilization_selection"]["choice"])
        self.assertEqual(self.app.next()["next_action"], "choose_civilization")
        self.assertTrue(self.app.next()["choice_contract"]["answers_must_remain_null"])
        self.assertTrue((self.project / "author-input/manifest.json").exists())
        for path in (self.project / "answers").glob("*.json"):
            self.assertTrue(all(v is None for v in json.loads(path.read_bytes()).values()))
        for action in (self.app.validate, self.app.build):
            with self.assertRaises(WorkflowError):
                action(self.payload())
        self.assertEqual((self.app.state()["status"], self.app.usage()["phase"]), ("selecting", "1"))
        self.app.meter.handle("source", {"source_id": "synthetic", "format": "openai-responses"})
        self.app.meter.handle("events", {"source_id": "synthetic", "events": [
            {"event_id": "selection-call", "phase": "1", "usage": {"input_tokens": 9, "output_tokens": 2}}]})
        self.choose()
        self.app.meter.handle("events", {"source_id": "synthetic", "events": [
            {"event_id": "author-call", "phase": "3", "usage": {"input_tokens": 5, "output_tokens": 1}}]})
        after = self.app.usage(include_records=True)
        self.assertEqual((after["run_id"], after["source_sha256"]), (before["run_id"], before["source_sha256"]))
        self.assertEqual(after["context"]["task_sha256"], before["context"]["task_sha256"])
        self.assertEqual(after["context"]["civilization"], "Mongols")
        self.assertEqual(after["tokens"]["total_tokens"], 17)
        self.assertEqual({r["phase"]: r["total_tokens"] for r in after["stages"] if r["total_tokens"] is not None},
                         {"1": 11, "3": 6})
        self.assertEqual(self.app.data["task_request"], frozen)
        self.assertEqual(self.app.data["task_sha256"], digest(json_bytes(frozen)))
        with self.assertRaises(WorkflowError):
            self.choose("Portuguese")
        reopened = self.reopen()
        self.assertEqual(reopened["status"], "authoring")
        self.assertEqual(reopened["civilization_selection"]["choice"]["civilization"], "Mongols")
        self.assertEqual(reopened["usage"]["run_id"], before["run_id"])
        self.assertEqual(reopened["usage"]["context"]["task_sha256"], before["context"]["task_sha256"])
        self.assertEqual(reopened["usage"]["tokens"]["total_tokens"], 17)

    def test_selection_recovers_after_all_answers_are_null_and_meter_failure_propagates(self):
        self.start()
        before = self.app.usage()
        state = self.reopen()
        self.assertEqual((state["status"], state["usage"]["run_id"]), ("selecting", before["run_id"]))
        path = self.project / "answers/0.json"
        nulls = json.loads(path.read_bytes())
        changed = dict(nulls)
        changed[next(iter(changed))] = 3
        path.write_bytes(json_bytes(changed))
        self.assertEqual(self.app.state()["status"], "invalid")
        with self.assertRaises(WorkflowError):
            self.choose()
        path.write_bytes(json_bytes(nulls))
        self.assertEqual(self.app.state()["status"], "selecting")
        with patch.object(self.app.meter, "update_context", side_effect=ValueError("synthetic persistence failure")):
            with self.assertRaisesRegex(ValueError, "persistence failure"):
                self.choose()
        self.assertIsNone(self.app.data["civilization_choice"])
        self.assertEqual(self.app.data["request"]["civilization"], "auto")
        self.choose()

    def test_dlc_rejection_and_legacy_manual_compatibility(self):
        profile = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        names = profile["allowed_internal_names"] + [
            n for group in profile["excluded_by_required_dlc"].values() for n in group]
        facts = {"civilizations": [{"internal_name": n, "display_name_zh": n} for n in names]}
        with patch("controller.run_tool", return_value=facts):
            allowed = RealEngine().civilizations()
        self.assertEqual(len(allowed), 42)
        self.assertNotIn("Romans", {row["id"] for row in allowed})
        with self.assertRaises(WorkflowError):
            self.start("Romans")
        state = self.start("Portuguese")
        self.assertEqual(state["status"], "authoring")
        self.assertEqual(state["civilization_selection"]["choice"]["selected_by"], "user")
        with self.assertRaises(WorkflowError):
            self.choose()
        for key in ("task_request", "task_sha256", "civilization_selection", "civilization_choice"):
            self.app.data.pop(key)
        self.app._save()
        legacy = self.reopen()
        self.assertEqual(legacy["status"], "authoring")
        self.assertEqual(legacy["civilization_selection"]["choice"]["civilization"], "Portuguese")
        self.assertEqual(legacy["usage"]["run_id"], state["usage"]["run_id"])
        self.assertEqual(project_path(self.project, test_project=True), self.project)
        with self.assertRaises(WorkflowError):
            project_path(self.project, test_project=False)

    def test_host_auth_stale_revision_and_cli_decision_snapshot(self):
        self.start()
        revision = self.app.next()["revision"]
        decision = self.payload(civilization="Vikings", reason="Use a strong economy to sustain infantry pressure.")
        with self.assertRaises(WorkflowError):
            self.app.choose_civilization({**decision, "expected_revision": revision - 1})
        with self.assertRaises(WorkflowError):
            self.app.choose_civilization({**decision, "civilization": "Romans"})
        meta = {"instance_id": "synthetic", "project_id": self.app.data["project_id"], "host_token": "synthetic-secret"}
        server = make_server(self.app, meta)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def post(body, token=False):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server.server_port}"}
            if token:
                headers["X-Author-Token"] = meta["host_token"]
            conn.request("POST", "/api/host/choose-civilization", json.dumps(body), headers)
            response = conn.getresponse()
            status = response.status
            response.read()
            conn.close()
            return status
        try:
            self.assertEqual(post(decision), 403)
            self.assertEqual(post({**decision, "project_id": "other"}, True), 409)
            self.assertEqual(post({**decision, "expected_revision": revision - 1}, True), 409)
            self.assertEqual(post(decision, True), 200)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        with patch("web_session.request", return_value={"status": "authoring"}) as request:
            host_action(meta, "choose-civilization", decision)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[1], "/api/host/choose-civilization")
            self.assertEqual(request.call_args.args[2]["expected_revision"], revision)
            with self.assertRaises(SessionError):
                host_action(meta, "choose-civilization", {"civilization": "Mongols"})
            self.assertEqual(request.call_count, 1)

    def test_meter_context_preserves_existing_fields_and_frozen_identity(self):
        self.start()
        before = self.app.usage()
        adapter = self.app.meter
        adapter.meter.context({**adapter.meter.meta["context"], "existing_marker": "preserve"})
        adapter.update_context({"civilization": "Vikings"})
        after = adapter.report()
        self.assertEqual(after["context"]["existing_marker"], "preserve")
        self.assertEqual(after["context"]["task_sha256"], before["context"]["task_sha256"])
        self.assertEqual((after["run_id"], after["source_sha256"]), (before["run_id"], before["source_sha256"]))
        with self.assertRaises(ValueError):
            adapter.update_context({"task_sha256": "different"})
        with self.assertRaises(ValueError):
            adapter.update_context({"run_id": "different"})
        reopened = self.reopen()
        self.assertEqual(reopened["usage"]["context"]["existing_marker"], "preserve")
        self.assertEqual(reopened["usage"]["context"]["civilization"], "auto")


if __name__ == "__main__":
    unittest.main()
