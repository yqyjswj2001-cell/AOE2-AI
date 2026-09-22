#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "adjusted/tools/compile_dynamic_strategy.py"
EXAMPLE = json.loads((ROOT / "adjusted/examples/franks.dynamic-strategy.v1.json").read_text(encoding="utf-8"))
FIXED = json.loads((ROOT / "adjusted/config/fixed-parameters.v1.json").read_text(encoding="utf-8"))

spec = importlib.util.spec_from_file_location("dynamic_compiler", TOOL)
compiler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = compiler
spec.loader.exec_module(compiler)


class DynamicCompilerTests(unittest.TestCase):
    def compile(self, doc=None):
        return compiler.compile_document(copy.deepcopy(doc or EXAMPLE), FIXED)

    def test_generates_only_strategy_owned_modules(self):
        files, manifest = self.compile()
        self.assertEqual(
            set(files),
            {
                "scoutcontrol.per",
                "gatherers.per",
                "units.per",
                "buildings.per",
                "escrow.per",
                "trade.per",
                "threats.per",
                "tsa.per",
                "orb.per",
            },
        )
        self.assertEqual(set(manifest["generated_modules"]), set(files))
        self.assertEqual(manifest["not_yet_compiled"], ["research", "target_priority"])

    def test_output_is_deterministic(self):
        self.assertEqual(self.compile(), self.compile())

    def test_fixed_runtime_fields_are_not_emitted(self):
        files, _ = self.compile()
        joined = "\n".join(files.values())
        self.assertNotIn("sn-cap-civilian-explorers", joined)
        self.assertNotIn("sn-percent-civilian-explorers", joined)
        self.assertNotIn("sn-maximum-hunt-drop-distance", joined)
        self.assertNotIn("enable-building-walling", joined)
        self.assertNotIn("faster-resign", joined)

    def test_scouting_is_age_scoped_and_dynamic(self):
        files, _ = self.compile()
        text = files["scoutcontrol.per"]
        self.assertIn("(current-age == dark-age)", text)
        self.assertIn("(set-strategic-number sn-number-explore-groups 1)", text)
        self.assertIn("(current-age == imperial-age)", text)
        self.assertIn("(set-strategic-number sn-number-explore-groups 0)", text)
        self.assertIn("(enable-timer fifteensec 15)", text)

    def test_economy_reaction_overrides_base(self):
        files, _ = self.compile()
        text = files["gatherers.per"]
        self.assertIn("(gold-amount < 150)", text)
        self.assertIn("(set-strategic-number sn-gold-gatherer-percentage 35)", text)
        self.assertIn("(gold-amount >= 150)", text)

    def test_castle_anti_spear_composition_is_compiled(self):
        files, _ = self.compile()
        text = files["units.per"]
        self.assertIn("(players-unit-type-count target-player spearman-line >= 6)", text)
        self.assertIn("(unit-type-count-total knight < 15)", text)
        self.assertIn("(unit-type-count-total skirmisher < 13)", text)

    def test_combat_reaction_priority_is_encoded(self):
        files, _ = self.compile()
        tsa = files["tsa.per"]
        # Priority 100 base-under-attack.
        self.assertIn("(up-enemy-units-in-town >= 5)", tsa)
        self.assertIn("(military-population >= 40)", tsa)
        # Priority 80 anti-spears must exclude the higher-priority trigger.
        self.assertIn("(up-enemy-units-in-town < 5)", tsa)
        self.assertIn("(players-unit-type-count target-player spearman-line >= 6)", tsa)
        self.assertIn("(military-population >= 22)", tsa)
        # Base Castle combat is used only when neither reaction is active.
        self.assertIn("(players-unit-type-count target-player spearman-line < 6)", tsa)
        self.assertIn("(military-population >= 18)", tsa)

    def test_orb_uses_dynamic_group_sizes(self):
        files, _ = self.compile()
        text = files["orb.per"]
        self.assertIn("(set-strategic-number sn-number-attack-groups 1000)", text)
        self.assertIn("(set-strategic-number sn-minimum-attack-group-size 4)", text)
        self.assertIn("(set-strategic-number sn-minimum-attack-group-size 7)", text)
        self.assertIn("(set-strategic-number sn-minimum-attack-group-size 8)", text)
        self.assertIn("(set-strategic-number sn-minimum-attack-group-size 15)", text)

    def test_buildings_and_feudal_age_up_compile(self):
        files, _ = self.compile()
        buildings = files["buildings.per"]
        escrow = files["escrow.per"]
        self.assertIn("(housing-headroom < 4)", buildings)
        self.assertIn("(building-type-count-total stable < 2)", buildings)
        self.assertIn("(current-age == dark-age)", escrow)
        self.assertIn("(can-research-with-escrow feudal-age)", escrow)
        self.assertIn("(set-escrow-percentage food 80)", escrow)

    def test_market_and_threat_rules_compile(self):
        files, _ = self.compile()
        trade = files["trade.per"]
        threats = files["threats.per"]
        self.assertIn("(commodity-selling-price wood >= 90)", trade)
        self.assertIn("(commodity-buying-price wood <= 180)", trade)
        self.assertIn("(up-enemy-units-in-town >= 5)", threats)
        self.assertIn("(enemy-buildings-in-town)", threats)
        self.assertIn("(up-enemy-units-in-town <= 3)", threats)

    def test_generated_parentheses_are_balanced(self):
        files, _ = self.compile()
        for name, content in files.items():
            depth = 0
            for raw in content.splitlines():
                line = raw.split(";", 1)[0]
                depth += line.count("(") - line.count(")")
                self.assertGreaterEqual(depth, 0, name)
            self.assertEqual(depth, 0, name)


if __name__ == "__main__":
    unittest.main()
