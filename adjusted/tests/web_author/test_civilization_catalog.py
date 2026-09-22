"""Catalog fidelity and shield integrity; no game/AI source is read."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web-author"))
from civilization_catalog import ASSET_DIR, FACTS_FILE, catalog
from civilizations import _profile


class CivilizationCatalogTests(unittest.TestCase):
    def test_exact_standard_pool_and_indian_alias(self):
        result = catalog()
        self.assertEqual([item["id"] for item in result["civilizations"]],
                         _profile()["allowed_internal_names"])
        self.assertEqual(len(result["civilizations"]), 42)
        indian = next(row for row in result["civilizations"] if row["id"] == "Indians")
        self.assertEqual((indian["name"], indian["name_en"]), ("印度斯坦", "Hindustanis"))
        self.assertFalse(result["content_profile"]["ownership_verified"])

    def test_displayed_facts_are_exact_frozen_values(self):
        frozen = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
        source = {row["internal_name"]: row for row in frozen["civilizations"]}
        result = catalog()
        self.assertEqual(result["source"]["game_version"], frozen["game_version"])
        mapping = {"bonuses": "civilization_bonuses", "unique_units": "unique_units",
                   "unique_techs": "unique_technologies", "team_bonus": "team_bonus"}
        for row in result["civilizations"]:
            with self.subTest(civilization=row["id"]):
                facts = source[row["id"]]["official_facts_zh"]
                self.assertEqual(row["description"], facts["archetype"])
                for key, source_key in mapping.items():
                    self.assertEqual(row[key], facts[source_key])

    def test_all_shields_match_pinned_manifest_and_original_canvas(self):
        manifest = json.loads((ASSET_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({row["id"] for row in manifest["assets"]},
                         set(_profile()["allowed_internal_names"]))
        self.assertEqual({path.name for path in ASSET_DIR.glob("*.png")},
                         {row["path"] for row in manifest["assets"]})
        for item in manifest["assets"]:
            with self.subTest(civilization=item["id"]):
                data = (ASSET_DIR / item["path"]).read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", data[16:24]), (104, 104))
                self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])


if __name__ == "__main__":
    unittest.main()
