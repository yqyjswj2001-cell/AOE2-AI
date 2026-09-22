#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "adjusted/tools/render_per_cloze.py"
TEMPLATES = ROOT / "adjusted/cloze/Promisory"
BLANKS = ROOT / "adjusted/cloze/answers"
FIXTURE = ROOT / "adjusted/tests/fixtures/cloze-franks"

spec = importlib.util.spec_from_file_location("cloze_renderer", TOOL)
renderer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = renderer
spec.loader.exec_module(renderer)


class ClozeTests(unittest.TestCase):
    def load_answers_dir(self, root: Path):
        merged = {}
        for path in sorted(root.glob("*.json")):
            part = json.loads(path.read_text(encoding="utf-8"))
            for key, value in part.items():
                if key in merged:
                    self.assertEqual(merged[key], value, key)
                merged[key] = value
        return merged

    def test_blank_answer_sheets_cover_every_placeholder(self):
        expected = renderer.collect_placeholders(TEMPLATES)
        supplied = set(self.load_answers_dir(BLANKS))
        self.assertEqual(supplied, expected)

    def test_fixture_renders_all_templates_without_rewriting_structure(self):
        answers = self.load_answers_dir(FIXTURE)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            renderer.render(TEMPLATES, answers, out)
            expected = {p.name.removesuffix(".tpl") for p in TEMPLATES.glob("*.per.tpl")}
            actual = {p.name for p in out.glob("*.per")}
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual), 10)
            for path in out.glob("*.per"):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("{{", text)
                self.assertNotIn("}}", text)

    def test_dynamic_reaction_slots_render(self):
        answers = self.load_answers_dir(FIXTURE)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            renderer.render(TEMPLATES, answers, out)

            gather = (out / "gatherers.per").read_text()
            self.assertIn("(gold-amount < 150)", gather)
            self.assertIn("sn-gold-gatherer-percentage 35", gather)

            units = (out / "units.per").read_text()
            self.assertIn("(players-unit-type-count target-player spearman-line >= 6)", units)
            self.assertIn("(players-building-type-count target-player castle >= 1)", units)

            tsa = (out / "tsa.per").read_text()
            self.assertIn("(strategic-number sn-military-superiority <= -3)", tsa)
            self.assertIn("(military-population >= 25)", tsa)

            orb = (out / "orb.per").read_text()
            self.assertIn("sn-minimum-attack-group-size 6", orb)
            self.assertIn("sn-percent-attack-soldiers 60", orb)

    def test_renderer_rejects_inverted_threat_hysteresis(self):
        answers = self.load_answers_dir(FIXTURE)
        answers["THREAT_CLEAR"] = answers["THREAT_TRIGGER"]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(renderer.ClozeError):
                renderer.render(TEMPLATES, answers, Path(td))


if __name__ == "__main__":
    unittest.main()
