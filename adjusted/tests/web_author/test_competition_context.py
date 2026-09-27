"""Match-condition handoff checks using synthetic answers, never AI implementations."""
import json
from pathlib import Path
import tempfile
import unittest

from test_workflow import Controller, FakeEngine, FakeMeter, digest, json_bytes

ROOT = Path(__file__).resolve().parents[3]


class RulesEngine(FakeEngine):
    def export(self, out):
        super().export(out)
        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        for name in ("README.md", "rules.json"):
            target = out / "competition" / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes((ROOT / "adjusted/knowledge/competition" / name).read_bytes())
            manifest["files"]["competition/" + name] = digest(target.read_bytes())
        manifest_path.write_bytes(json_bytes(manifest))


class CompetitionContextTests(unittest.TestCase):
    def task(self, mode, engine):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = Controller(Path(tmp.name) / "fixture", engine=engine, meter_factory=FakeMeter)
        app.start({"expected_revision": 0, "mode": mode, "civilization": "Synthetic",
                   "script_name": "Test_AI", "output_mode": "raw_scripts"})
        return app, json.loads((app.project / "author-session/task.json").read_bytes())

    def test_new_ffa_handoff_contains_frozen_rules(self):
        app, task = self.task("ffa8", RulesEngine())
        context = task["competition_context"]
        self.assertTrue(context["policy_applies_to_selected_mode"])
        self.assertIsNone(context["selected_map"])
        path = Path(context["rules_file"])
        self.assertEqual(context["rules_sha256"], digest(path.read_bytes()))
        rules = json.loads(path.read_bytes())
        self.assertEqual(len(rules["map_pool"]["maps"]), 7)
        self.assertEqual(rules["endgame"]["first_pressure_at"], 3600)
        sudden = rules["endgame"]["sudden_death"]
        self.assertEqual((sudden["entry_at"], sudden["elimination_threshold"]), (5400, 100))
        self.assertEqual(sudden["timeout_policy"]["deadline_game_seconds"], 7200)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            app._input()

    def test_other_modes_do_not_inherit_policy(self):
        for mode in ("3v3", "ffa4"):
            _, task = self.task(mode, RulesEngine())
            self.assertFalse(task["competition_context"]["policy_applies_to_selected_mode"])

    def test_legacy_package_is_not_rewritten(self):
        app, task = self.task("ffa8", FakeEngine())
        self.assertFalse(task["competition_context"]["available"])
        self.assertIsNone(task["competition_context"]["read_first"])
        self.assertFalse((app.project / "author-input/competition").exists())


if __name__ == "__main__":
    unittest.main()
