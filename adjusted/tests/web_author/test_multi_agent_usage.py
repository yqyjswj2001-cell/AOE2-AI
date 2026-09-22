from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web-author"))
from metering import Meter
from multi_agent_usage import MultiAgentUsage, _norm_usage

MAIN = "00000000-0000-4000-8000-000000000001"
CHILD = "00000000-0000-4000-8000-000000000002"
OTHER = "00000000-0000-4000-8000-000000000003"

def stamp(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()

def token(t, inp, out):
    return {"timestamp": stamp(t), "type": "event_msg", "payload": {"type": "token_count",
        "info": {"total_token_usage": {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out}}}}

class MultiHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.meter = Meter(self.project, "fixture", "source")
        self.start = self.meter.meta["started_at"]
        self.env = {"CODEX_HOME": str(self.root / ".codex")}
        self.find = patch("multi_agent_usage._ccusage_binary", return_value=None)
        self.find.start()
        self.addCleanup(self.find.stop)

    def rollout(self, session, rows):
        folder = self.root / ".codex/sessions/2026/09/22"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ("rollout-fixture-" + session + ".jsonl")
        metadata = {"timestamp": stamp(self.start - 50), "type": "session_meta", "payload": {"id": session}}
        model = {"type": "turn_context", "payload": {"model": "synthetic-model"}}
        path.write_text("\n".join(json.dumps(r) for r in [metadata, model, *rows]) + "\n", encoding="utf-8")
        return path

    def auto(self, bindings):
        return MultiAgentUsage(self.meter, self.project, self.root, environ=self.env,
                               home=self.root, bindings=bindings)

    def test_only_bound_rollout_and_cumulative_delta_are_charged(self):
        self.rollout(MAIN, [token(self.start - 10, 100, 20), token(self.start + 1, 150, 30),
                            token(self.start + 2, 150, 30)])
        self.rollout(OTHER, [token(self.start - 10, 0, 0), token(self.start + 1, 9000, 9000)])
        auto = self.auto({"codex": [MAIN]})
        auto.sync("1")
        auto.sync("4")
        report = self.meter.report(True)
        self.assertEqual(report["tokens"]["total_tokens"], 60)
        self.assertEqual(report["tokens"]["cached_input_tokens"], None)
        self.assertEqual(len(report["records"]), 1)
        self.assertEqual(report["records"][0]["outcome"], "unknown")
        self.assertEqual(report["records"][0]["unit"], "usage_interval")
        self.assertIsNone(report["tokens"]["failed_or_cancelled_tokens"])
        self.assertEqual(report["records"][0]["phase"], "unattributed")
        self.assertEqual(auto.status()["bound_session_count"], 1)

    def test_children_require_explicit_binding(self):
        self.rollout(MAIN, [token(self.start - 2, 0, 0), token(self.start + 1, 10, 10)])
        self.rollout(CHILD, [token(self.start - 2, 0, 0), token(self.start + 2, 5, 5)])
        auto = self.auto({"codex": [MAIN]})
        auto.sync()
        self.assertEqual(self.meter.report()["tokens"]["total_tokens"], 20)
        auto.bind({"codex": [CHILD]})
        auto.sync()
        self.assertEqual(self.meter.report()["tokens"]["total_tokens"], 30)

    def test_reset_and_missing_baseline_are_persistent_gaps(self):
        self.rollout(MAIN, [token(self.start + 1, 100, 10), token(self.start + 2, 50, 5)])
        auto = self.auto({"codex": [MAIN]})
        status = auto.sync()
        self.assertEqual(status["reset_gaps"], 1)
        self.assertIn("NO_PROJECT_START_BASELINE", {g["code"] for g in status["gaps"]})
        self.assertIsNone(self.meter.report()["tokens"]["total_tokens"])

    def test_no_binding_does_not_scan_or_charge_private_logs(self):
        self.rollout(OTHER, [token(self.start + 1, 500, 20)])
        with patch("multi_agent_usage._codex_events", side_effect=AssertionError("must not read")):
            status = self.auto({}).sync()
        self.assertEqual(status["status"], "NO_BOUND_SESSIONS")
        self.assertIsNone(self.meter.report()["tokens"]["total_tokens"])

    def test_claude_bound_session_and_unknown_cache(self):
        folder = self.root / ".claude/projects"
        folder.mkdir(parents=True)
        path = folder / "owned-session.jsonl"
        row = {"timestamp": stamp(self.start + 1), "message": {"id": "msg-1", "model": "fixture",
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_input_tokens": 20, "cache_creation_input_tokens": 0}}}
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        auto = self.auto({"claude": ["owned-session"]})
        auto.sync()
        self.assertEqual(self.meter.report()["tokens"]["total_tokens"], 35)
        self.assertIsNone(_norm_usage(None, 10))

    def test_truncated_rollout_keeps_prior_counts_and_records_gap(self):
        path = self.rollout(MAIN, [token(self.start - 10, 0, 0), token(self.start + 1, 10, 2)])
        auto = self.auto({"codex": [MAIN]})
        auto.sync()
        path.write_text("{}\\n", encoding="utf-8")
        status = auto.sync()
        self.assertEqual(self.meter.report()["tokens"]["total_tokens"], 12)
        self.assertIn("LOG_REPLACED_OR_TRUNCATED", {gap["code"] for gap in status["gaps"]})

    def test_state_persists_metadata_not_response_text(self):
        path = self.rollout(MAIN, [token(self.start - 10, 0, 0), token(self.start + 1, 10, 2),
            {"type": "response_item", "payload": {"content": "SYNTHETIC_PRIVATE_TEXT"}}])
        auto = self.auto({"codex": [MAIN]})
        auto.sync()
        text = auto.path.read_text(encoding="utf-8") + json.dumps(self.meter.report(True))
        self.assertNotIn("SYNTHETIC_PRIVATE_TEXT", text)
        self.assertNotIn(str(path), text)

if __name__ == "__main__":
    unittest.main()
