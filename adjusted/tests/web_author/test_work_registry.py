"""Completed-work registry recognition and deduplication tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys

HERE = Path(__file__).resolve().parents[2] / "web-author"
sys.path.insert(0, str(HERE))

import work_registry
from work_registry import RegistryError, list_works, recognize_artifact, record_game, register_artifact, show_work
from web_session import main as web_session_main


class WorkRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aoe2-work-registry-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "registry.sqlite3"
        self.modules = {f"module{i}.per": f"; GENERATED {i}\n".encode() for i in range(36)}

    def share_zip(self, name="OLD_AI", filename="old-ai.zip"):
        package = self.root / filename
        hashes = {key: work_registry.sha256(value) for key, value in self.modules.items()}
        with zipfile.ZipFile(package, "w") as archive:
            for module, data in self.modules.items():
                archive.writestr(f"{name}/{module}", data)
            archive.writestr("manifest.json", json.dumps({
                "schema": "aoe2-share-script-package-v1",
                "script_name": name,
                "script_files": 36,
                "files_sha256": hashes,
            }))
            archive.writestr("README.txt", "legacy")
        return package

    def plain_zip(self, name="LEGACY_AI"):
        package = self.root / f"{name}.zip"
        with zipfile.ZipFile(package, "w") as archive:
            for module, data in self.modules.items():
                archive.writestr(f"{name}/{module}", data)
        return package

    def installable_zip(self, name="INSTALLED_AI"):
        package = self.root / "installable.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr(f"resources/_common/ai/{name}.ai", b"")
            archive.writestr(f"resources/_common/ai/{name}.per", b"; entry\n")
            for module, data in self.modules.items():
                archive.writestr(f"resources/_common/ai/{name}/{module}", data)
        return package

    def test_current_share_package_registers_and_preserves_unknowns(self):
        package = self.share_zip()
        result = register_artifact(package, db_path=self.db)
        self.assertTrue(result["registered"])
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["script_name"], "OLD_AI")
        self.assertEqual(result["artifact_kind"], "share_package")
        self.assertTrue(result["manifest_present"])
        self.assertEqual(result["module_files"], 36)
        self.assertIn("model", result["unknown_fields"])
        rows = list_works(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["script_name"], "OLD_AI")

    def test_same_script_content_is_deduplicated_even_when_rezipped(self):
        first = self.share_zip("OLD_AI", "first.zip")
        second = self.share_zip("OLD_AI", "second.zip")
        one = register_artifact(first, db_path=self.db)
        two = register_artifact(second, db_path=self.db, metadata={"agent": "grok"})
        self.assertEqual(one["work_id"], two["work_id"])
        self.assertTrue(two["duplicate"])
        self.assertEqual(two["artifact_count"], 2)
        rows = list_works(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent"], "grok")

    def test_plain_legacy_zip_without_manifest_is_recognized(self):
        found = recognize_artifact(self.plain_zip())
        self.assertEqual(found["script_name"], "LEGACY_AI")
        self.assertEqual(found["artifact_kind"], "legacy_zip")
        self.assertFalse(found["manifest_present"])
        self.assertEqual(found["module_files"], 36)

    def test_old_installable_zip_is_recognized(self):
        found = recognize_artifact(self.installable_zip())
        self.assertEqual(found["script_name"], "INSTALLED_AI")
        self.assertEqual(found["artifact_kind"], "installable_zip")
        self.assertEqual(found["module_files"], 36)

    def test_raw_script_directory_is_recognized(self):
        root = self.root / "RAW_AI"
        root.mkdir()
        for module, data in self.modules.items():
            (root / module).write_bytes(data)
        found = recognize_artifact(root)
        self.assertEqual(found["script_name"], "RAW_AI")
        self.assertEqual(found["artifact_kind"], "raw_scripts")

    def test_game_records_append_without_overwriting_work(self):
        registered = register_artifact(self.share_zip(), db_path=self.db, metadata={"agent": "grok"})
        first = record_game({
            "played_at": "2026-09-26T20:15:00+08:00",
            "mode": "ffa8",
            "map": "Arabia",
            "civilization": "Magyars",
            "outcome": "win",
            "placement": 1,
            "players": 8,
            "duration_seconds": 3120,
            "score": 18432,
            "notes": "Scout pressure worked; late-game food floated.",
            "issues": ["Castle-age army production paused once."],
            "evidence": ["post-game screenshot supplied in the test conversation"],
        }, name="OLD_AI", db_path=self.db)
        second = record_game({
            "outcome": "loss", "placement": 5, "players": 8,
            "notes": "Lost the forward base early.",
        }, work_id=registered["work_id"], db_path=self.db)
        view = show_work(name="OLD_AI", db_path=self.db)
        self.assertEqual(first["script_name"], "OLD_AI")
        self.assertEqual(second["work_id"], registered["work_id"])
        self.assertEqual(view["work"]["agent"], "grok")
        self.assertEqual(view["match_summary"], {"total": 2, "wins": 1, "losses": 1, "draws": 0})
        self.assertEqual(len(view["matches"]), 2)
        self.assertEqual(view["matches"][1]["record"]["map"], "Arabia")
        self.assertIn("Castle-age army production paused once.", view["matches"][1]["issues"])

    def test_identical_game_record_is_deduplicated(self):
        register_artifact(self.share_zip(), db_path=self.db)
        record = {"outcome": "win", "placement": 1, "players": 8, "score": 10000}
        one = record_game(record, name="OLD_AI", db_path=self.db)
        two = record_game(record, name="OLD_AI", db_path=self.db)
        self.assertFalse(one["duplicate"])
        self.assertTrue(two["duplicate"])
        self.assertEqual(one["match_id"], two["match_id"])
        self.assertEqual(show_work(name="OLD_AI", db_path=self.db)["match_summary"]["total"], 1)

    def test_same_script_name_with_multiple_versions_requires_work_id(self):
        first = self.share_zip("SAME_AI", "v1.zip")
        register_artifact(first, db_path=self.db)
        changed = dict(self.modules)
        changed["module0.per"] = b"; VERSION TWO\n"
        old_modules = self.modules
        try:
            self.modules = changed
            second = self.share_zip("SAME_AI", "v2.zip")
            second_registered = register_artifact(second, db_path=self.db)
        finally:
            self.modules = old_modules
        with self.assertRaisesRegex(RegistryError, "Multiple registered versions"):
            show_work(name="SAME_AI", db_path=self.db)
        view = show_work(work_id=second_registered["work_id"], db_path=self.db)
        self.assertEqual(view["work"]["script_name"], "SAME_AI")

    def test_game_record_rejects_guessed_or_unstructured_fields(self):
        register_artifact(self.share_zip(), db_path=self.db)
        with self.assertRaisesRegex(RegistryError, "unsupported fields"):
            record_game({"made_up_rating": "S"}, name="OLD_AI", db_path=self.db)
        with self.assertRaisesRegex(RegistryError, "placement cannot exceed"):
            record_game({"placement": 9, "players": 8}, name="OLD_AI", db_path=self.db)

    def test_web_session_has_standalone_registration_entry(self):
        sentinel = {"ok": True, "registered": True, "script_name": "OLD_AI"}
        with patch.object(work_registry, "register_artifact", return_value=sentinel) as mocked:
            code = web_session_main(["register-existing", "--artifact", str(self.root / "missing.zip")])
        self.assertEqual(code, 0)
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.args[0], self.root / "missing.zip")

    def test_skill_documents_existing_package_entry(self):
        skill = (Path(__file__).resolve().parents[2] / "skills/aoe2-web-author/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("register-existing", skill)
        self.assertIn("已有作品登记", skill)
        self.assertIn("不重新创作", skill)
        self.assertIn("registry-show", skill)
        self.assertIn("record-game", skill)
        self.assertIn("结算截图", skill)
        self.assertIn("看不出来的字段不要猜", skill)


if __name__ == "__main__":
    unittest.main()
