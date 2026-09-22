import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web-author"))
from metering import Meter
from usage_formats import normalize

class MeterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.meter = Meter(Path(self.tmp.name), "synthetic-project", "synthetic-source")

    def add(self, event_id="response-1", usage=None):
        self.meter.register("synthetic", "openai-responses")
        return self.meter.ingest("synthetic", [{"event_id": event_id, "usage": usage}])

    def test_unknown_and_explicit_zero_are_distinct(self):
        self.assertIsNone(self.meter.report()["tokens"]["total_tokens"])
        self.add(usage=None)
        self.add("response-2", {"input_tokens": 0, "output_tokens": 0})
        report = self.meter.report()
        self.assertEqual(report["tokens"]["total_tokens"], 0)
        self.assertEqual(report["tokens"]["missing_usage_records"], 1)
        self.assertEqual(report["coverage"], "PARTIAL")

    def test_normalization_cache_and_reasoning_are_subsets(self):
        value = normalize("openai-responses", {"input_tokens": 100, "output_tokens": 20,
            "input_tokens_details": {"cached_tokens": 80},
            "output_tokens_details": {"reasoning_tokens": 10}})
        self.assertEqual(value["total_tokens"], 120)
        value = normalize("anthropic-messages", {"input_tokens": 10, "output_tokens": 20,
            "cache_read_input_tokens": 30, "cache_creation_input_tokens": 40})
        self.assertEqual(value["total_tokens"], 100)
        self.assertIsNone(value["reasoning_tokens"])

    def test_duplicate_conflict_and_closed_run(self):
        value = {"input_tokens": 10, "output_tokens": 5}
        self.add(usage=value)
        self.assertEqual(self.add(usage=value)["duplicates"], 1)
        with self.assertRaises(ValueError):
            self.add(usage={"input_tokens": 11, "output_tokens": 5})
        self.meter.close()
        self.assertEqual(self.add(usage=value)["duplicates"], 1)
        with self.assertRaises(ValueError):
            self.add("new-call", value)

    def test_complete_requires_sealing_and_keeps_capture_gaps(self):
        self.add(usage={"input_tokens": 10, "output_tokens": 5})
        with self.assertRaises(ValueError):
            self.meter.close("COMPLETED", delivery={"build_id": "fixture"}, all_sources_declared=True)
        self.meter.seal_source("synthetic", 1)
        self.meter.capture({"status": "ERROR"}, [{"code": "GAP"}])
        with self.assertRaises(ValueError):
            self.meter.close("COMPLETED", delivery={"build_id": "fixture"}, all_sources_declared=True)
        self.meter.close("COMPLETED", delivery={"build_id": "fixture"})
        folder = self.meter.export()
        saved = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["capture_gaps"], [{"code": "GAP"}])
        self.assertEqual(saved["auto_capture"]["status"], "ERROR")
        self.assertTrue((folder / "calls.csv").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_sealed_complete_is_host_report_not_game_pass(self):
        self.add(usage={"input_tokens": 10, "output_tokens": 5})
        self.meter.seal_source("synthetic", 1)
        self.meter.close("COMPLETED", delivery={"build_id": "fixture"}, all_sources_declared=True)
        self.meter.close()
        report = self.meter.report()
        self.assertEqual(report["coverage"], "HOST_REPORTED_COMPLETE")
        self.assertEqual(report["game_validation"], "NOT_RUN")

    def test_restart_retains_usage_and_marks_unobserved_time(self):
        self.add(usage={"input_tokens": 10, "output_tokens": 5})
        again = Meter(Path(self.tmp.name), "synthetic-project", "synthetic-source")
        self.assertEqual(again.report()["tokens"]["total_tokens"], 15)
        self.assertEqual(again.report()["restart_count"], 1)
        self.assertIn("unobserved_seconds", again.report()["time"])
        with self.assertRaises(ValueError):
            Meter(Path(self.tmp.name), "another-project", "synthetic-source")

if __name__ == "__main__":
    unittest.main()
