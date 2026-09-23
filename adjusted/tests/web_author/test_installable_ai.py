from pathlib import Path
import os
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[2] / "web-author"
sys.path.insert(0, str(HERE))
from installable_ai import InstallableAIError, package_installable_ai


class InstallableAITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aoe2-installable-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.modules = self.root / "modules"
        self.baseline = self.root / "official"
        self.output = self.root / "out"
        self.modules.mkdir()
        self.baseline.mkdir()
        for index in range(36):
            data = ("; module " + str(index) + "\n").encode()
            (self.modules / f"module{index}.per").write_bytes(data)
            (self.baseline / f"module{index}.per").write_bytes(data)
        self.game = self.root / "AoE2DE"
        self.promisory = self.game / "resources/_common/ai/Promisory"
        self.promisory.mkdir(parents=True)
        for index in range(10):
            (self.promisory / f"module{index}.per").write_bytes((self.baseline / f"module{index}.per").read_bytes())
        self.promide = self.game / "resources/_common/drs/gamedata_x2/PromiDE.per2"
        self.promide.parent.mkdir(parents=True)
        self.promide.write_text(
            '(load "Promisory\\module0")\n'
            '#load-if-not-defined BATTLE-ROYALE\n'
            '(load "Promisory\\module1")\n'
            '#end-if\n'
            '; official loader fixture\n' + ''.join(f'(load "Promisory\\module{i}")\n' for i in range(2, 10)),
            encoding="utf-8")

    def test_package_rewrites_official_loader_and_is_installable(self):
        result = package_installable_ai(
            self.modules, "My_AI", self.output, self.baseline,
            promide=self.promide, game_promisory=self.promisory)
        ai = self.output / "resources/_common/ai"
        self.assertEqual((ai / "My_AI.ai").read_bytes(), b"")
        entry = (ai / "My_AI.per").read_text(encoding="utf-8")
        self.assertIn('(load "My_AI\\module0")', entry)
        self.assertIn('(load "My_AI\\module1")', entry)
        self.assertNotIn("Promisory", entry)
        self.assertEqual(len(list((ai / "My_AI").glob("*.per"))), 36)
        self.assertEqual(result["entrypoint_validation"], "PASS")
        self.assertEqual(result["loaded_modules"], [f"module{i}.per" for i in range(10)])
        self.assertEqual(len(result["unreferenced_modules"]), 26)

    def test_baseline_mismatch_refuses_package(self):
        (self.promisory / "module1.per").write_text("; changed game baseline\n", encoding="utf-8")
        with self.assertRaisesRegex(InstallableAIError, "baseline differs"):
            package_installable_ai(
                self.modules, "My_AI", self.output, self.baseline,
                promide=self.promide, game_promisory=self.promisory)
        self.assertFalse(self.output.exists())

    def test_explicit_promide_environment_is_supported(self):
        env = {**os.environ, "AOE2DE_PROMIDE_PER2": str(self.promide)}
        result = package_installable_ai(
            self.modules, "My_AI", self.output, self.baseline,
            game_promisory=self.promisory, environ=env, home=self.root)
        self.assertEqual(result["entrypoint_validation"], "PASS")


if __name__ == "__main__":
    unittest.main()
