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
DEFAULTS = ROOT / "adjusted/cloze/official-defaults"
OFFICIAL = ROOT / "official/raw/Promisory"

spec = importlib.util.spec_from_file_location("cloze_renderer", TOOL)
renderer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = renderer
spec.loader.exec_module(renderer)


class OfficialDerivedClozeTests(unittest.TestCase):
    def test_renderer_with_official_defaults_restores_exact_source(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            answers = tmp / "answers"
            out = tmp / "out"
            answers.mkdir()

            for defaults_path in DEFAULTS.glob("*.json"):
                doc = json.loads(defaults_path.read_text(encoding="utf-8"))
                (answers / defaults_path.name).write_text(
                    json.dumps(doc["answers"], indent=2) + "\n",
                    encoding="utf-8",
                )

            rc = renderer.main([
                "--answers-dir", str(answers),
                "--out", str(out),
            ])
            self.assertEqual(rc, 0)

            rendered = sorted(out.glob("*.per"))
            templates = sorted(TEMPLATES.glob("*.per.tpl"))
            self.assertEqual(len(rendered), len(templates))

            for path in rendered:
                self.assertEqual(
                    path.read_bytes(),
                    (OFFICIAL / path.name).read_bytes(),
                    path.name,
                )

    def test_blank_answers_are_rejected(self):
        template = TEMPLATES / "orb.per.tpl"
        answers = ROOT / "adjusted/cloze/answers/orb.json"
        defaults = DEFAULTS / "orb.json"
        with self.assertRaises(renderer.ClozeError):
            renderer.render_one(template, answers, defaults)


if __name__ == "__main__":
    unittest.main()
