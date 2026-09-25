"""Direct game install tests; all game directories are synthetic temporary fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import sys

HERE = Path(__file__).resolve().parents[2] / "web-author"
sys.path.insert(0, str(HERE))

import game_install
from game_install import GameInstallError, install_project
from web_session import main as web_session_main


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class GameInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aoe2-game-install-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.baseline = self.root / "official"
        self.baseline.mkdir()
        self.game = self.root / "AoE2DE"
        self.ai_root = self.game / "resources/_common/ai"
        self.promisory = self.ai_root / "Promisory"
        self.promisory.mkdir(parents=True)
        self.promide = self.game / "resources/_common/drs/gamedata_x2/PromiDE.per2"
        self.promide.parent.mkdir(parents=True)

        for index in range(36):
            name = f"module{index}.per"
            official = f"; OFFICIAL {index}\n".encode()
            (self.baseline / name).write_bytes(official)
            (self.promisory / name).write_bytes(official)

        self.promide.write_text(
            "".join(f'(load "Promisory\\module{index}")\n' for index in range(10))
            + "; synthetic official loader\n",
            encoding="utf-8",
        )

    def raw_build(self, script_name="SYNTHETIC"):
        output = self.project / "delivery/build-raw"
        scripts = output / script_name
        scripts.mkdir(parents=True)
        hashes = {}
        for index in range(36):
            path = scripts / f"module{index}.per"
            path.write_text(f"; GENERATED {index}\n", encoding="utf-8")
            hashes[path.relative_to(output).as_posix()] = digest(path.read_bytes())
        state = {
            "status": "completed",
            "build": {
                "script_name": script_name,
                "output_mode": "raw_scripts",
                "path": str(output),
                "script_root": str(scripts),
                "artifact_hashes": hashes,
            },
        }
        (self.project / "project.json").write_text(json.dumps(state), encoding="utf-8")

    def share_build(self, script_name="SHARE_AI"):
        output = self.project / "delivery/build-share"
        output.mkdir(parents=True)
        package = output / f"{script_name}.zip"
        files_sha = {}
        with zipfile.ZipFile(package, "w") as archive:
            for index in range(36):
                name = f"module{index}.per"
                data = f"; SHARED GENERATED {index}\n".encode()
                archive.writestr(f"{script_name}/{name}", data)
                files_sha[name] = digest(data)
            archive.writestr("manifest.json", json.dumps({
                "schema": "aoe2-share-script-package-v1",
                "script_name": script_name,
                "script_files": 36,
                "files_sha256": files_sha,
                "installable": False,
            }))
            archive.writestr("README.txt", "synthetic")
        state = {
            "status": "completed",
            "build": {
                "script_name": script_name,
                "output_mode": "share_package",
                "path": str(output),
                "package_file": str(package),
                "artifact_hashes": {package.name: digest(package.read_bytes())},
            },
        }
        (self.project / "project.json").write_text(json.dumps(state), encoding="utf-8")

    def install(self):
        with patch.object(game_install, "OFFICIAL_BASELINE", self.baseline):
            return install_project(self.project, game_root=self.game)

    def test_raw_build_creates_named_game_ai_entrypoint(self):
        self.raw_build("GROK_FFA8")
        result = self.install()
        self.assertTrue(result["installed"])
        self.assertEqual(result["verification"], "PASS")
        self.assertEqual(result["expected_ai_type_name"], "GROK_FFA8")
        self.assertEqual(Path(result["ai_root"]), self.ai_root.resolve())
        self.assertEqual((self.ai_root / "GROK_FFA8.ai").read_bytes(), b"")
        entry = (self.ai_root / "GROK_FFA8.per").read_text(encoding="utf-8")
        self.assertIn('(load "GROK_FFA8\\module0")', entry)
        self.assertNotIn("Promisory", entry)
        modules = list((self.ai_root / "GROK_FFA8").glob("*.per"))
        self.assertEqual(len(modules), 36)
        self.assertEqual((self.ai_root / "GROK_FFA8/module35.per").read_text(), "; GENERATED 35\n")
        self.assertTrue((self.promide).is_file(), "Official loader must remain in place")
        self.assertEqual(result["official_files_modified"], False)

    def test_share_package_can_be_installed_without_changing_normal_build_format(self):
        self.share_build()
        result = self.install()
        self.assertEqual(result["source_output_mode"], "share_package")
        self.assertEqual(len(list((self.ai_root / "SHARE_AI").glob("*.per"))), 36)
        self.assertTrue((self.ai_root / "SHARE_AI.ai").is_file())
        self.assertTrue((self.ai_root / "SHARE_AI.per").is_file())

    def test_existing_same_name_is_backed_up_before_replacement(self):
        self.raw_build("SYNTHETIC")
        old_dir = self.ai_root / "SYNTHETIC"
        old_dir.mkdir()
        (old_dir / "old.per").write_text("; OLD\n")
        (self.ai_root / "SYNTHETIC.per").write_text("; OLD ENTRY\n")
        (self.ai_root / "SYNTHETIC.ai").write_bytes(b"")
        result = self.install()
        backup = Path(result["backup"])
        self.assertTrue((backup / "SYNTHETIC/old.per").is_file())
        self.assertEqual((backup / "SYNTHETIC.per").read_text(), "; OLD ENTRY\n")
        self.assertEqual(len(list((self.ai_root / "SYNTHETIC").glob("*.per"))), 36)

    def test_game_baseline_mismatch_refuses_install(self):
        self.raw_build()
        (self.promisory / "module4.per").write_text("; DIFFERENT GAME VERSION\n")
        with patch.object(game_install, "OFFICIAL_BASELINE", self.baseline):
            with self.assertRaisesRegex(GameInstallError, "baseline differs"):
                install_project(self.project, game_root=self.game)
        self.assertFalse((self.ai_root / "SYNTHETIC.ai").exists())
        self.assertFalse((self.ai_root / "SYNTHETIC.per").exists())
        self.assertFalse((self.ai_root / "SYNTHETIC").exists())

    def test_non_game_directory_is_not_accepted_as_install_root(self):
        self.raw_build()
        personal = self.root / "personal-profile-ai"
        personal.mkdir()
        with patch.object(game_install, "OFFICIAL_BASELINE", self.baseline):
            with self.assertRaisesRegex(GameInstallError, "Not a usable AoE2DE install root"):
                install_project(self.project, game_root=personal)

    def test_cli_requires_explicit_install_confirmation(self):
        self.raw_build()
        result = web_session_main([
            "install", "--project", str(self.project), "--test-project",
            "--game-root", str(self.game),
        ])
        self.assertEqual(result, 2)
        self.assertFalse((self.ai_root / "SYNTHETIC.ai").exists())
        self.assertFalse((self.ai_root / "SYNTHETIC.per").exists())

    def test_skill_locks_install_to_verified_game_directory(self):
        skill = (Path(__file__).resolve().parents[2] / "skills/aoe2-web-author/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("web_session.py install", skill)
        self.assertIn("--confirm-install", skill)
        self.assertIn("<AoE2DE>/resources/_common/ai", skill)
        self.assertIn("installed=true", skill)
        self.assertIn("verification=PASS", skill)
        self.assertIn("不要先把异常解释成", skill)


if __name__ == "__main__":
    unittest.main()
