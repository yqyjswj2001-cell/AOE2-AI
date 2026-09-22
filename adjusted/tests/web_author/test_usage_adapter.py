import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web-author"))
from meter_adapter import MeterAdapter
from usage import UsageClient

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.identity = {"project_id": "fixture", "source_sha256": "source", "auto_capture": False}
        self.adapter = MeterAdapter(self.project, self.identity)

    def test_disabled_automatic_capture_preserves_unknown(self):
        report = self.adapter.report()
        self.assertEqual(report["auto_capture"]["status"], "DISABLED")
        self.assertIsNone(report["tokens"]["total_tokens"])
        self.assertEqual(report["coverage"], "NOT_CONNECTED")

    def test_phase_aliases_and_no_brief_phase(self):
        self.assertEqual(self.adapter.phase("researching")["phase"], "1")
        self.assertEqual(self.adapter.phase("authoring")["phase"], "3")
        self.assertEqual(self.adapter.phase("repairing")["phase"], "4")
        with self.assertRaises(ValueError):
            self.adapter.phase("2.5")

    def test_delivery_export_and_second_close_preserve_completeness(self):
        self.adapter.handle("source", {"source_id": "fixture", "format": "openai-responses"})
        self.adapter.handle("events", {"source_id": "fixture", "events": [
            {"event_id": "response-1", "usage": {"input_tokens": 10, "output_tokens": 2}}]})
        self.adapter.handle("seal", {"source_id": "fixture", "expected_records": 1})
        self.adapter.phase("packaging")
        build = {"build_id": "synthetic-build", "sha256": "synthetic-hash"}
        result = self.adapter.complete(build, True)
        self.assertEqual(result["coverage"], "HOST_REPORTED_COMPLETE")
        self.assertEqual(self.adapter.complete(build, False)["coverage"], "HOST_REPORTED_COMPLETE")
        closed = self.adapter.close()
        self.assertEqual(closed["state"], "COMPLETED")
        saved = json.loads((self.project / result["report_directory"] / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["auto_capture"]["status"], "DISABLED")
        self.assertEqual(saved["capture_gaps"], [])

    def test_missing_automatic_source_blocks_full_declaration(self):
        class FakeAuto:
            def sync(self, phase):
                return {"status": "CONNECTED_PARTIAL", "gaps": [{"code": "BOUND_SESSION_NOT_OBSERVED"}]}
        self.adapter.auto = FakeAuto()
        self.adapter.phase("packaging")
        with self.assertRaises(ValueError):
            self.adapter.complete({"build_id": "fixture"}, True)
        result = self.adapter.complete({"build_id": "fixture"})
        saved = json.loads((self.project / result["report_directory"] / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["capture_gaps"])

    def test_usage_client_reads_local_credentials_and_current_revision(self):
        (self.project / ".author-web-session.json").write_text(json.dumps({
            "url": "http://127.0.0.1:12345", "host_token": "synthetic-secret", "project_id": "fixture"}), encoding="utf-8")
        calls = []
        def fake(url, route, data=None, **kwargs):
            calls.append((route, data, kwargs))
            if route.endswith("/usage"):
                return {"run_id": "run-fixture"}
            if route.endswith("/next"):
                return {"project_id": "fixture", "revision": 7}
            return {"status": "RECORDED"}
        with patch("usage.request", side_effect=fake):
            client = UsageClient(project=self.project)
            client.register("source-1", "openai-responses")
        body = calls[-1][1]
        self.assertEqual(body["expected_revision"], 7)
        self.assertEqual(body["project_id"], "fixture")
        self.assertEqual(body["run_id"], "run-fixture")
        self.assertEqual(calls[-1][2]["headers"]["X-Author-Token"], "synthetic-secret")
        self.assertNotIn("runtime_base", sys.modules)

    def test_import_has_no_studio_or_game_dependencies(self):
        self.assertIsNotNone(importlib.import_module("http_client"))
        self.assertNotIn("author_studio_server", sys.modules)

if __name__ == "__main__":
    unittest.main()
