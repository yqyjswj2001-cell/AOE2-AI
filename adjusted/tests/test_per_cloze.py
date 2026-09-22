#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "adjusted/tools/render_per_cloze.py"
TEMPLATES = ROOT / "adjusted/cloze/Promisory"
DEFAULTS = ROOT / "adjusted/cloze/official-defaults"
OFFICIAL = ROOT / "official/raw/Promisory"

sys.path.insert(0, str(TOOL.parent))

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


    def test_linked_values_rejected_before_any_output_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            templates, answers, defaults, out = [tmp / name for name in ("templates", "answers", "defaults", "out")]
            for directory in (templates, answers, defaults, out):
                directory.mkdir()
            for name in (p.name.removesuffix(".per.tpl") for p in sorted(TEMPLATES.glob("*.per.tpl"))):
                shutil.copyfile(TEMPLATES / f"{name}.per.tpl", templates / f"{name}.per.tpl")
                shutil.copyfile(DEFAULTS / f"{name}.json", defaults / f"{name}.json")
                values = json.loads((DEFAULTS / f"{name}.json").read_text(encoding="utf-8"))["answers"]
                if name == "orb":
                    values["ORB_ATTACK_GROUP_005"] += 1
                (answers / f"{name}.json").write_text(json.dumps(values), encoding="utf-8")
            sentinel = out / "boarhunting.per"
            sentinel.write_bytes(b"existing output stays intact")
            argv = ["--templates", str(templates), "--defaults", str(defaults), "--answers-dir", str(answers), "--out", str(out)]
            self.assertEqual(renderer.main(argv), 2)
            self.assertEqual(list(out.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b"existing output stays intact")
            new_out = tmp / "new-out"
            self.assertEqual(renderer.main(argv[:-1] + [str(new_out)]), 2)
            self.assertFalse(new_out.exists())

    def test_consistent_nondefault_orb_answers_are_substituted_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            answers = Path(td) / "orb.json"
            values = json.loads((DEFAULTS / "orb.json").read_text(encoding="utf-8"))["answers"]
            for n in (1, 5, 7, 9):
                values[f"ORB_ATTACK_GROUP_{n:03}"] = 12
            for n in (2, 6, 8, 10):
                values[f"ORB_ATTACK_GROUP_{n:03}"] = 20
            values["ORB_ATTACK_GROUP_003"] = 6
            values["ORB_ATTACK_GROUP_004"] = 75
            answers.write_text(json.dumps(values), encoding="utf-8")
            template = TEMPLATES / "orb.per.tpl"
            actual = renderer.render_one(template, answers, DEFAULTS / "orb.json")
            expected = renderer.PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template.read_bytes().decode("utf-8"))
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
