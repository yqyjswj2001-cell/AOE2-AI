"""38-module baseline migration: spans, fixed modules, missing answers, loader includes."""
from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "adjusted/tools"))
sys.path.insert(0, str(ROOT / "adjusted/web-author"))

from official_baseline import official_module_count, official_module_names
from strategy_catalog import load_catalog
import game_install
from game_install import GameInstallError, install_project, _parse_promide
from controller import RealEngine
import render_per_cloze

GAME = Path(r"S:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\ai\Promisory")
PROMIDE = Path(r"S:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\drs\gamedata_x2\PromiDE.per2")
REQUIRES = {
    "BUILDINGS_LUMBER_CAMP_013",
    "BUILDINGS_LUMBER_CAMP_014",
    "BUILDINGS_LUMBER_CAMP_015",
    "BUILDINGS_MINING_CAMP_017",
    "BUILDINGS_MINING_CAMP_019",
    "BUILDINGS_MILL_022",
    "BUILDINGS_MILL_025",
    "BUILDINGS_MILL_028",
    "BUILDINGS_MILL_030",
    "BUILDINGS_MILL_032",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def answer_dir_from_defaults(dest: Path, null_keys=()):
    dest.mkdir(parents=True)
    for path in (ROOT / "adjusted/cloze/official-defaults").glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        answers = document["answers"]
        for key in null_keys:
            if key in answers:
                answers[key] = None
        (dest / path.name).write_text(json.dumps(answers), encoding="utf-8")


class BaselineMigrationTests(unittest.TestCase):
    def test_frozen_baseline_is_the_current_38_modules(self):
        names = official_module_names()
        self.assertEqual(len(names), 38)
        self.assertEqual(official_module_count(), 38)
        self.assertIn("extremebuildings3.per", names)
        self.assertIn("extremebuildings4.per", names)
        official = ROOT / "official/raw/Promisory"
        adjusted = ROOT / "adjusted/Promisory"
        for name in names:
            official_bytes = (official / name).read_bytes()
            self.assertEqual((adjusted / name).read_bytes(), official_bytes)
            self.assertEqual((GAME / name).read_bytes(), official_bytes)
        for name in ("extremebuildings3.per", "extremebuildings4.per"):
            text = (official / name).read_bytes().decode("utf-8")
            self.assertNotIn("{{", text)
            self.assertFalse((ROOT / "adjusted/cloze/Promisory" / (name + ".tpl")).exists())

    def test_old_dynamic_parameters_moved_and_ten_need_new_answers(self):
        catalog = load_catalog()
        rows = [row for module in catalog["modules"].values() for row in module["parameters"]]
        dynamic = [row for row in rows if row["decision"] == "dynamic"]
        flagged = [row for row in dynamic if row.get("migration_requires_answer") is True]
        self.assertEqual(len(rows), 2295)
        self.assertEqual(len(dynamic), 1715)
        self.assertEqual({row["key"] for row in flagged}, REQUIRES)
        settlement = next(row for row in dynamic if row["key"] == "BUILDINGS_SETTLEMENT_004")
        self.assertEqual(settlement["official_value"], 4)
        self.assertNotIn("migration_requires_answer", settlement)
        supplement = json.loads((ROOT / "adjusted/cloze/migration/requires-answer.json").read_text(encoding="utf-8"))
        self.assertEqual(supplement["count"], 10)
        self.assertEqual({row["key"] for row in supplement["parameters"]}, REQUIRES)
        self.assertTrue(all(row["author_answer"] is None for row in supplement["parameters"]))
        blanks = json.loads((ROOT / "adjusted/cloze/answers/buildings.json").read_text(encoding="utf-8"))
        for key in REQUIRES:
            self.assertIsNone(blanks[key])
        self.assertIsNone(blanks["BUILDINGS_SETTLEMENT_004"])
        review = json.loads((ROOT / "review/migration-audit/semantic-review.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(review["new_dynamic"]), 404)
        self.assertEqual(len(catalog["modules"]), 17)

    def test_official_defaults_render_and_missing_ten_stop_the_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            answers = root / "answers"
            answer_dir_from_defaults(answers)
            rendered = root / "rendered"
            engine = RealEngine()
            engine.render(answers, rendered)
            names = sorted(path.name for path in rendered.glob("*.per"))
            self.assertEqual(names, official_module_names())
            official = ROOT / "official/raw/Promisory"
            for name in ("extremebuildings3.per", "extremebuildings4.per", "buildings.per"):
                self.assertEqual((rendered / name).read_bytes(), (official / name).read_bytes())

            blocked = root / "blocked-answers"
            answer_dir_from_defaults(blocked, REQUIRES)
            output = root / "must-not-exist"
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = render_per_cloze.main(["--answers-dir", str(blocked), "--out", str(output)])
            self.assertEqual(code, 2)
            payload = json.loads(buffer.getvalue())
            for key in sorted(REQUIRES):
                self.assertIn(key, payload["error"])
            self.assertFalse(output.exists())
            self.assertNotIn("BUILDINGS_SETTLEMENT_004", payload["error"])

    def test_current_loader_parses_and_install_leaves_official_files_unchanged(self):
        before_loader = PROMIDE.read_bytes()
        before_game = {name: digest((GAME / name).read_bytes()) for name in official_module_names()}
        text, loads = _parse_promide(before_loader)
        self.assertGreaterEqual(len(loads), 10)
        self.assertIn('(include "ailib/GoalArrayOps.xs")', text)
        self.assertIn('(include "ailib/Geometry.xs")', text)
        self.assertTrue(all("ailib" not in load for load in loads))
        with self.assertRaises(GameInstallError):
            _parse_promide(b'(load "Promisory\\buildings")\n' * 10 + b'(include "../secret.xs")\n')

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "AoE2DE"
            promisory = game / "resources/_common/ai/Promisory"
            promisory.mkdir(parents=True)
            for name in official_module_names():
                shutil.copyfile(ROOT / "official/raw/Promisory" / name, promisory / name)
            promide = game / "resources/_common/drs/gamedata_x2/PromiDE.per2"
            promide.parent.mkdir(parents=True)
            promide.write_bytes(before_loader)
            project = root / "project"
            output = project / "delivery"
            scripts = output / "MIGRATION38"
            scripts.mkdir(parents=True)
            hashes = {}
            for name in official_module_names():
                path = scripts / name
                path.write_bytes(b"; migration fixture\n")
                hashes[path.relative_to(output).as_posix()] = digest(path.read_bytes())
            (project / "project.json").write_text(json.dumps({
                "status": "completed",
                "build": {
                    "script_name": "MIGRATION38",
                    "output_mode": "raw_scripts",
                    "path": str(output),
                    "script_root": str(scripts),
                    "artifact_hashes": hashes,
                },
            }), encoding="utf-8")
            result = install_project(project, game_root=game)
            self.assertEqual(result["module_files"], 38)
            self.assertFalse(result["official_files_modified"])
            entry = (game / "resources/_common/ai/MIGRATION38.per").read_text(encoding="utf-8")
            self.assertIn('(include "ailib/GoalArrayOps.xs")', entry)
            self.assertIn('(include "ailib/Geometry.xs")', entry)
            self.assertNotIn("Promisory", entry)
            self.assertEqual(promide.read_bytes(), before_loader)
            for name in official_module_names():
                self.assertEqual((promisory / name).read_bytes(), (ROOT / "official/raw/Promisory" / name).read_bytes())

            (promisory / "buildings.per").write_bytes(b"; different\n")
            with self.assertRaises(GameInstallError):
                install_project(project, game_root=game)
            custom = game / "resources/_common/ai/MIGRATION38/buildings.per"
            self.assertEqual(custom.read_bytes(), b"; migration fixture\n")
            self.assertEqual(promide.read_bytes(), before_loader)

        self.assertEqual(PROMIDE.read_bytes(), before_loader)
        for name, expected in before_game.items():
            self.assertEqual(digest((GAME / name).read_bytes()), expected)

    def test_registry_fingerprint_uses_the_frozen_module_set(self):
        fingerprint = RealEngine().source_digest()
        self.assertEqual(len(fingerprint), 64)
        int(fingerprint, 16)
