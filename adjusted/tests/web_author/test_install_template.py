"""Synthetic loaders only; no actual game installation or strategy is claimed."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'adjusted/web-author')]
from install_template import capture, preflight, load_template
from installable_ai import package_installable_ai, InstallableAIError, parse_promide


class InstallTemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root/'baseline'; self.baseline.mkdir()
        self.game = self.root/'game'
        self.game_modules = self.game/'resources/_common/ai/Promisory'; self.game_modules.mkdir(parents=True)
        self.loader = self.game/'resources/_common/drs/gamedata_x2/PromiDE.per2'; self.loader.parent.mkdir(parents=True)
        for i in range(36):
            data = f'; SYNTHETIC MODULE {i}\n'.encode()
            (self.baseline/f'module{i}.per').write_bytes(data)
            (self.game_modules/f'module{i}.per').write_bytes(data)
        self.loader.write_text('; SYNTHETIC LOADER ONLY\n#load-if-not-defined BATTLE-ROYALE\n'+
                               ''.join(f'(load "Promisory\\module{i}")\n' for i in range(12))+'#end-if\n',encoding='utf-8')
        self.template = self.root/'template'
    def test_capture_preserves_loader_and_enables_offline_build(self):
        original = self.loader.read_bytes()
        capture(self.loader, self.template, self.baseline)
        self.assertEqual((self.template/'PromiDE.per2').read_bytes(), original)
        shutil.rmtree(self.game)
        check = preflight(self.baseline, template_dir=self.template, environ={}, home=self.root)
        self.assertTrue(check['ready']); self.assertEqual(check['source'], 'repository_template')
        out = self.root/'package'
        result = package_installable_ai(self.baseline,'Offline_AI',out,self.baseline,
                                       template_dir=self.template,environ={},home=self.root)
        self.assertEqual(result['entrypoint_source_kind'], 'repository_template')
        self.assertEqual((out/'resources/_common/ai/Offline_AI.ai').read_bytes(), b'')
        self.assertIn('#load-if-not-defined', (out/'resources/_common/ai/Offline_AI.per').read_text())
        self.assertEqual(len(list((out/'resources/_common/ai/Offline_AI').glob('*.per'))),36)
    def test_capture_checks_all_modules_before_writing(self):
        (self.game_modules/'module35.per').write_text('; mismatch outside loaded branch')
        with self.assertRaises(InstallableAIError): capture(self.loader,self.template,self.baseline)
        self.assertFalse(self.template.exists())
    def test_corrupt_registered_template_never_silently_falls_back(self):
        capture(self.loader,self.template,self.baseline)
        (self.template/'PromiDE.per2').write_bytes(b'; changed')
        check = preflight(self.baseline,template_dir=self.template,environ={},home=self.root)
        self.assertFalse(check['ready'])
        out = self.root/'package'
        with self.assertRaises(InstallableAIError):
            package_installable_ai(self.baseline,'Test',out,self.baseline,template_dir=self.template,environ={},home=self.root)
        self.assertFalse(out.exists())
    def test_baseline_and_load_order_are_both_pinned(self):
        capture(self.loader,self.template,self.baseline)
        manifest = self.template/'manifest.json'; doc = json.loads(manifest.read_bytes())
        doc['loads'].reverse(); manifest.write_text(json.dumps(doc))
        with self.assertRaises(InstallableAIError): load_template(self.template,self.baseline)
        (self.baseline/'module1.per').write_text('; changed')
        with self.assertRaises(InstallableAIError): load_template(self.template,self.baseline)
    def test_missing_template_is_not_reported_as_ready(self):
        check = preflight(self.baseline,template_dir=self.template,environ={},home=self.root)
        self.assertFalse(check['ready']); self.assertTrue(check['parameter_authoring_available'])
    def test_invalid_control_flow_and_manifest_types_are_rejected(self):
        valid = self.loader.read_bytes()
        for raw in (valid.replace(b'#end-if', b''), b'#else\n'+valid, valid.replace(b'#end-if', b'#else\n#else\n#end-if')):
            with self.assertRaises(InstallableAIError): parse_promide(raw)
        self.template.mkdir(); (self.template/'manifest.json').write_text('[]')
        self.assertFalse(preflight(self.baseline,template_dir=self.template,environ={},home=self.root)['ready'])

    def test_ready_template_cannot_be_overwritten(self):
        capture(self.loader,self.template,self.baseline)
        with self.assertRaises(InstallableAIError): capture(self.loader,self.template,self.baseline)


if __name__ == '__main__': unittest.main()
