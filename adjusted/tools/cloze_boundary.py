"""Guards for the current frozen official-derived cloze boundary.

The scout profile is intentionally specific to one byte-exact official file.
A source update requires a separate review of every span; it is never learned
from template keys or expanded automatically.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import NamedTuple


class BoundaryError(ValueError):
    """A template or answer crosses the reviewed strategy boundary."""


class ScoutSpan(NamedTuple):
    key: str
    line: int       # One-based line in the frozen official source.
    column: int     # Zero-based character offset; these numeric lines are ASCII.
    original: str
    meaning: str


SCOUT_SOURCE_SHA256 = "1c4e2ab1e6cdc41319b7d2369834c5714affa0c7dca1554eb37d15342a959205"
SCOUT_ALLOWED_SPANS = (
    ScoutSpan("SCOUT_001", 11, 16, "1800", "Scout tactic game-time window"),
    ScoutSpan("SCOUT_002", 13, 41, "2", "Scout count enabling the tactic"),
    ScoutSpan("SCOUT_003", 16, 34, "1", "Knight count ending the scout tactic"),
    ScoutSpan("SCOUT_008", 120, 36, "2", "Scout count permitting regrouping"),
    ScoutSpan("SCOUT_009", 127, 19, "15", "Regroup retreat duration"),
    ScoutSpan("SCOUT_010", 133, 41, "1", "Count enabling group candidate search"),
    ScoutSpan("SCOUT_012", 145, 41, "1", "Count enabling group creation from search"),
    ScoutSpan("SCOUT_024", 376, 47, "1", "Count enabling direct reinforcement"),
    ScoutSpan("SCOUT_026", 392, 47, "1", "Count enabling group-13 reinforcement"),
    ScoutSpan("SCOUT_028", 408, 47, "1", "Count enabling reinforcement via pivot"),
    ScoutSpan("SCOUT_033", 747, 19, "25", "Retreat duration for low superiority"),
    ScoutSpan("SCOUT_035", 771, 19, "15", "Retreat duration near an enemy town center"),
    ScoutSpan("SCOUT_037", 849, 19, "8", "Retreat duration while awaiting more scouts"),
    ScoutSpan("SCOUT_038", 859, 19, "40", "Second low-superiority retreat duration"),
    ScoutSpan("SCOUT_039", 939, 19, "11", "Small distant-group retreat duration"),
    ScoutSpan("SCOUT_040", 951, 19, "10", "Near-enemy waypoint retreat duration"),
    ScoutSpan("SCOUT_041", 964, 19, "30", "Far-enemy waypoint retreat duration"),
    ScoutSpan("SCOUT_042", 1012, 19, "3", "Obstacle-response retreat duration"),
)
SCOUT_KEYS = frozenset(span.key for span in SCOUT_ALLOWED_SPANS)
ORB_KEYS = frozenset(f"ORB_ATTACK_GROUP_{i:03d}" for i in range(1, 11))
ORB_MIN_KEYS = tuple(f"ORB_ATTACK_GROUP_{i:03d}" for i in (1, 5, 7, 9))
ORB_MAX_KEYS = tuple(f"ORB_ATTACK_GROUP_{i:03d}" for i in (2, 6, 8, 10))
_PLACEHOLDER = re.compile(r"\{\{[^{}\r\n]+\}\}")


def validate_no_noncode_placeholders(module: str, template_text: str) -> None:
    """Reject placeholders inside PER semicolon comments or quoted strings.

A semicolon in a quoted string is not a comment. Backslash-escaped quotes
stay inside the string. Scanning resumes after the closing quote, including
when legitimate code and a placeholder follow on the same line.
    """
    state = "code"
    escaped = False
    line = 1
    i = 0
    while i < len(template_text):
        char = template_text[i]
        if char == "{" and _PLACEHOLDER.match(template_text, i):
            if state != "code":
                raise BoundaryError(
                    f"{module}:{line}: placeholder in {state} must remain fixed"
                )
        if char == "\n":
            line += 1
        if state == "comment":
            if char in "\r\n":
                state = "code"
        elif state == "string":
            # Inspect every character: a backslash before {{ must not hide it.
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                state = "code"
        elif char == ";":
            state = "comment"
        elif char == '"':
            state = "string"
        i += 1


def validate_scout_template(source_text: str, template_text: str) -> None:
    """Allow exactly the 18 reviewed numeric spans, preserving all other text.

Callers must decode read_bytes() as UTF-8 rather than normalize line endings.
The fingerprint plus full reconstruction keeps even unexposed comments and
whitespace fixed, and rejects relocated or renamed placeholders.
    """
    module = "scoutcontrol.per"
    if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != SCOUT_SOURCE_SHA256:
        raise BoundaryError(
            f"{module}: source differs from frozen SHA-256; review required"
        )
    validate_no_noncode_placeholders(module, template_text)
    lines = source_text.splitlines(keepends=True)
    # Reverse order also supports multiple reviewed spans on one source line.
    for span in reversed(SCOUT_ALLOWED_SPANS):
        original_line = lines[span.line - 1]
        end = span.column + len(span.original)
        if original_line[span.column:end] != span.original:
            raise BoundaryError(f"{module}: frozen span mismatch for {span.key}")
        lines[span.line - 1] = (
            original_line[:span.column]
            + "{{" + span.key + "}}"
            + original_line[end:]
        )
    expected = "".join(lines)
    if template_text != expected:
        offset = next(
            (i for i, pair in enumerate(zip(expected, template_text)) if pair[0] != pair[1]),
            min(len(expected), len(template_text)),
        )
        line = expected.count("\n", 0, offset) + 1
        raise BoundaryError(
            f"{module}:{line}: only the 18 frozen numeric spans may be placeholders; "
            "all other text and approved key names must remain exact"
        )


def _require_keys(module: str, answers: Mapping[str, object], expected: frozenset[str]) -> None:
    actual = set(answers)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected, key=str)
        raise BoundaryError(f"{module}: answer keys differ; missing={missing}, extra={extra}")


def _integer(module: str, key: str, answers: Mapping[str, object]) -> int:
    value = answers[key]
    if type(value) is not int:
        raise BoundaryError(f"{module}: {key} must be an integer (not bool)")
    return value


def validate_strategy_answers(module: str, answers: Mapping[str, object]) -> None:
    """Check only the reviewed cross-rule relationships, not game strength."""
    if module not in {"orb.per", "scoutcontrol.per"}:
        return
    if not isinstance(answers, Mapping):
        raise BoundaryError(f"{module}: answers must be a mapping")
    if module == "scoutcontrol.per":
        _require_keys(module, answers, SCOUT_KEYS)
        values = {key: _integer(module, key, answers) for key in SCOUT_KEYS}
        if values["SCOUT_010"] > values["SCOUT_012"]:
            raise BoundaryError(
                f"{module}: SCOUT_010 must be <= SCOUT_012 so candidate search "
                "runs whenever group creation consumes its result"
            )
        return

    _require_keys(module, answers, ORB_KEYS)
    values = {key: _integer(module, key, answers) for key in ORB_KEYS}
    for label, keys in (("minimum", ORB_MIN_KEYS), ("maximum", ORB_MAX_KEYS)):
        if len({values[key] for key in keys}) != 1:
            raise BoundaryError(f"{module}: {label} group configuration must agree: {keys}")
    minimum = values[ORB_MIN_KEYS[0]]
    maximum = values[ORB_MAX_KEYS[0]]
    if minimum < 1 or maximum < 1:
        raise BoundaryError(f"{module}: minimum and maximum group sizes must be positive")
    if minimum > maximum:
        raise BoundaryError(f"{module}: minimum group size must be <= maximum group size")
    if (minimum, maximum) == (1, 1):
        raise BoundaryError(f"{module}: (1, 1) is the fixed disabled-group sentinel")
    if values["ORB_ATTACK_GROUP_003"] < 0:
        raise BoundaryError(f"{module}: ORB_ATTACK_GROUP_003 must be nonnegative")
    if not 0 <= values["ORB_ATTACK_GROUP_004"] <= 100:
        raise BoundaryError(f"{module}: ORB_ATTACK_GROUP_004 must be within 0..100")
