from __future__ import annotations

import importlib.util
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "curated_defconst", ROOT / "adjusted/tools/curated_defconst.py",
)
curated = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = curated
spec.loader.exec_module(curated)


class CuratedDefconstTests(unittest.TestCase):
    def test_crlf_and_unrelated_same_line_expression_stay_exact(self):
        source = (
            "#load-if-defined TUPI-CIV\r\n"
            "(defconst number-barracks 4) (defconst unit-id 74); cost 75\r\n"
            "(defconst ig-food 42)\r\n"
            '#end-if\r\n'
        )
        template = source.replace("number-barracks 4", "number-barracks {{BUILD_001}}")
        template = template.replace("ig-food 42", "ig-food {{FOOD_001}}")
        curated.validate_curated_defconst("merge1b.per", source, template)
        with self.assertRaises(curated.CuratedDefconstError):
            curated.validate_curated_defconst("merge1b.per", source, template.replace("\r\n", "\n"))

    def test_round_trip_does_not_authorize_id_cost_comment_or_symbol(self):
        source = (
            "#load-if-defined TUPI-CIV\n"
            "(defconst number-barracks 4) (defconst unit-id 74); note 99\n"
            "(defconst unique-unit-food 75)\n"
            '; (defconst number-stables 8)\n'
            '(defconst text-civ "(defconst ig-wood 31)")\n'
            "#end-if\n"
        )
        good = source.replace("number-barracks 4", "number-barracks {{ALLOWED}}")
        curated.validate_curated_defconst("merge1b.per", source, good)
        cases = [
            ("unit-id 74", "unit-id {{OTHER}}", "74"),
            ("unique-unit-food 75", "unique-unit-food {{OTHER}}", "75"),
            ("note 99", "note {{OTHER}}", "99"),
            ("number-stables 8", "number-stables {{OTHER}}", "8"),
            ("ig-wood 31", "ig-wood {{OTHER}}", "31"),
            ("number-barracks {{ALLOWED}}", "{{OTHER}} {{ALLOWED}}", "number-barracks"),
        ]
        for original, replacement, default in cases:
            with self.subTest(original=original):
                bad = good.replace(original, replacement)
                # All these forbidden edits satisfy the normal round-trip check.
                restored = bad.replace("{{ALLOWED}}", "4").replace("{{OTHER}}", default)
                self.assertEqual(restored, source)
                with self.assertRaises(curated.CuratedDefconstError):
                    curated.validate_curated_defconst("merge1b.per", source, bad)

    def test_duplicate_names_and_incomplete_integer_tokens_are_rejected(self):
        source = (
            "#load-if-defined TUPI-CIV\n"
            "(defconst number-barracks 4)\n"
            "(defconst number-stables 4)\n"
            "#end-if\n"
        )
        valid = source.replace("number-barracks 4", "number-barracks {{FIRST}}")
        valid = valid.replace("number-stables 4", "number-stables {{SECOND}}")
        duplicate = valid.replace("{{SECOND}}", "{{FIRST}}")
        self.assertEqual(duplicate.replace("{{FIRST}}", "4"), source)
        for bad in (
            duplicate,
            valid.replace("{{FIRST}}", "{{FIRST}}0"),
            valid.replace("{{FIRST}}", "{{lowercase}}"),
            valid.replace("{{FIRST}}", "4"),
        ):
            with self.subTest(template=bad):
                with self.assertRaises(curated.CuratedDefconstError):
                    curated.validate_curated_defconst("merge1b.per", source, bad)

    def test_duplicate_wei_and_disabled_buildings_remain_fixed(self):
        source = (
            "#load-if-defined WEI-CIV\n(defconst ig-food 42)\n#end-if\n"
            "#load-if-defined WEI-CIV\n(defconst ig-food 42)\n#end-if\n"
            "#load-if-defined AZTEC-CIV\n"
            "(defconst number-stables 0)\n(defconst number-barracks -1)\n"
            "(defconst ig-food 42)\n#end-if\n"
        )
        # Explicitly open only the final, non-WEI gathering value.
        prefix, tail = source.rsplit("ig-food 42", 1)
        template = prefix + "ig-food {{AZTEC_FOOD}}" + tail
        spans = curated.eligible_defconst_spans("customConstants.per", source)
        self.assertEqual([(s.civ, s.name, s.value) for s in spans], [("AZTEC-CIV", "ig-food", "42")])
        curated.validate_curated_defconst("customConstants.per", source, template)
        for original in ("ig-food 42", "number-stables 0", "number-barracks -1"):
            name, value = original.rsplit(" ", 1)
            bad = template.replace(original, name + " {{FORBIDDEN}}", 1)
            with self.subTest(original=original):
                with self.assertRaises(curated.CuratedDefconstError):
                    curated.validate_curated_defconst("customConstants.per", source, bad)

    def test_civ_context_is_required_and_no_profile_is_inferred(self):
        sources = [
            "(defconst ig-food 42)\n",
            "#load-if-not-defined TUPI-CIV\n(defconst ig-food 42)\n#end-if\n",
            "#load-if-defined TUPI-CIV\n#else\n(defconst ig-food 42)\n#end-if\n",
            "#load-if-defined TUPI-CIV\n#load-if-defined DE-AVAILABLE\n"
            "(defconst ig-food 42)\n#end-if\n#end-if\n",
        ]
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(curated.eligible_defconst_spans("merge1b.per", source), [])
                with self.assertRaises(curated.CuratedDefconstError):
                    curated.validate_curated_defconst("merge1b.per", source, source.replace("42", "{{VALUE}}"))
        with self.assertRaises(curated.CuratedDefconstError):
            curated.eligible_defconst_spans("defaultConstants.per", sources[0])

    def test_real_merge1b_has_only_the_reviewed_twenty_one_positions(self):
        source = (ROOT / "official/raw/Promisory/merge1b.per").read_bytes().decode("utf-8")
        spans = curated.eligible_defconst_spans("merge1b.per", source)
        self.assertEqual(len(spans), 21)
        self.assertEqual(Counter(span.name for span in spans), {
            "number-barracks": 3, "number-stables": 3, "number-archery-ranges": 3,
            "ig-food": 3, "ig-wood": 3, "ig-gold": 3, "ig-stone": 3,
        })
        for span in spans:
            self.assertEqual(source[span.start:span.end], span.value)


if __name__ == "__main__":
    unittest.main()
