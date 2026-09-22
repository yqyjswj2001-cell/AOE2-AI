from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "cloze_boundary", ROOT / "adjusted/tools/cloze_boundary.py",
)
boundary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = boundary
spec.loader.exec_module(boundary)


def scout_answers():
    return {span.key: int(span.original) for span in boundary.SCOUT_ALLOWED_SPANS}


def orb_answers(minimum=8, maximum=8):
    answers = {key: minimum for key in boundary.ORB_MIN_KEYS}
    answers.update({key: maximum for key in boundary.ORB_MAX_KEYS})
    answers.update(ORB_ATTACK_GROUP_003=1000, ORB_ATTACK_GROUP_004=100)
    return answers


class ClozeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only this explicitly reviewed official file is a source fixture.
        cls.scout_source = (ROOT / "official/raw/Promisory/scoutcontrol.per").read_bytes().decode("utf-8")
        lines = cls.scout_source.splitlines(keepends=True)
        for span in reversed(boundary.SCOUT_ALLOWED_SPANS):
            line = lines[span.line - 1]
            lines[span.line - 1] = (
                line[:span.column] + "{{" + span.key + "}}"
                + line[span.column + len(span.original):]
            )
        cls.scout_template = "".join(lines)

    def test_comments_strings_and_code_after_semicolon_string(self):
        good = '(chat-local-to-self "text; still a string") (game-time > {{TIME}})\r\n'
        boundary.validate_no_noncode_placeholders("example.per", good)
        boundary.validate_no_noncode_placeholders(
            "example.per", '; harmless comment\n(game-time > {{TIME}})\n',
        )
        for bad in (
            '; (game-time > {{RENAMED}})\n',
            '(chat-local-to-self "{{RENAMED}}")\n',
            '(chat-local-to-self "semi; {{RENAMED}}")\n',
            r'(chat-local-to-self "\{{RENAMED}}")',
            r'(chat-local-to-self "escaped \" quote {{RENAMED}}")',
            good.rstrip() + '; {{COMMENT}}\n',
        ):
            with self.subTest(template=bad):
                with self.assertRaises(boundary.BoundaryError):
                    boundary.validate_no_noncode_placeholders("example.per", bad)

    def test_scout_exact_18_spans_and_fixed_boundary(self):
        self.assertEqual(len(boundary.SCOUT_ALLOWED_SPANS), 18)
        boundary.validate_scout_template(self.scout_source, self.scout_template)
        for original, edited in (
            ('(strategic-number sn-five-turns == 2)',
             '(strategic-number sn-five-turns == {{TOTALLY_NEW_NAME}})'),
            ('(game-time > 5)', '(game-time > {{LOAD_CHECK_TIME}})'),
            ('(strategic-number sn-focus-player-number > -1)',
             '(strategic-number sn-focus-player-number > {{PLAYER_FILTER}})'),
            ('(players-building-type-count target-player town-center < 1)',
             '(players-building-type-count target-player town-center < {{TC_FILTER}})'),
            ('{{SCOUT_001}}', '{{RENAMED_ALLOWED_LOCATION}}'),
            ('{{SCOUT_001}}', '1800'),
        ):
            with self.subTest(edit=edited):
                self.assertIn(original, self.scout_template)
                bad = self.scout_template.replace(original, edited, 1)
                with self.assertRaises(boundary.BoundaryError):
                    boundary.validate_scout_template(self.scout_source, bad)
        with self.assertRaises(boundary.BoundaryError):
            boundary.validate_scout_template(self.scout_source, self.scout_template + ' ')
        with self.assertRaises(boundary.BoundaryError):
            boundary.validate_scout_template(self.scout_source + ' ', self.scout_template + ' ')

    def test_orb_repeated_configuration_and_disabled_sentinel(self):
        boundary.validate_strategy_answers("orb.per", orb_answers())
        boundary.validate_strategy_answers("orb.per", orb_answers(1, 2))
        for key in boundary.ORB_MIN_KEYS + boundary.ORB_MAX_KEYS:
            with self.subTest(key=key):
                answers = orb_answers()
                answers[key] += 1
                with self.assertRaises(boundary.BoundaryError):
                    boundary.validate_strategy_answers("orb.per", answers)
        for minimum, maximum in ((1, 1), (9, 8), (0, 8)):
            with self.subTest(minimum=minimum, maximum=maximum):
                with self.assertRaises(boundary.BoundaryError):
                    boundary.validate_strategy_answers("orb.per", orb_answers(minimum, maximum))

    def test_orb_answer_domains_and_key_renaming(self):
        for key, value in (
            ('ORB_ATTACK_GROUP_003', -1),
            ('ORB_ATTACK_GROUP_003', True),
            ('ORB_ATTACK_GROUP_004', -1),
            ('ORB_ATTACK_GROUP_004', 101),
        ):
            with self.subTest(key=key, value=value):
                answers = orb_answers()
                answers[key] = value
                with self.assertRaises(boundary.BoundaryError):
                    boundary.validate_strategy_answers("orb.per", answers)
        answers = orb_answers()
        answers['RENAMED'] = answers.pop('ORB_ATTACK_GROUP_001')
        with self.assertRaises(boundary.BoundaryError):
            boundary.validate_strategy_answers("orb.per", answers)
        answers = orb_answers()
        answers['ORB_ATTACK_GROUP_003'] = 0
        answers['ORB_ATTACK_GROUP_004'] = 0
        boundary.validate_strategy_answers("orb.per", answers)

    def test_scout_search_must_run_before_its_consumer(self):
        answers = scout_answers()
        boundary.validate_strategy_answers("scoutcontrol.per", answers)
        answers['SCOUT_012'] = answers['SCOUT_010'] + 1
        boundary.validate_strategy_answers("scoutcontrol.per", answers)
        answers['SCOUT_010'] = answers['SCOUT_012'] + 1
        with self.assertRaises(boundary.BoundaryError):
            boundary.validate_strategy_answers("scoutcontrol.per", answers)
        answers = scout_answers()
        answers['RENAMED'] = answers.pop('SCOUT_024')
        with self.assertRaises(boundary.BoundaryError):
            boundary.validate_strategy_answers("scoutcontrol.per", answers)


if __name__ == "__main__":
    unittest.main()
