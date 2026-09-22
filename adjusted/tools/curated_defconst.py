"""Exact source-span guards for the two curated Batch 6 defconst modules."""
from __future__ import annotations

import re
from dataclasses import dataclass


class CuratedDefconstError(ValueError):
    pass


_STRATEGY_NAMES = frozenset({
    "number-barracks", "number-stables", "number-archery-ranges",
    "ig-food", "ig-wood", "ig-gold", "ig-stone",
})
MODULE_PROFILES = {
    "merge1b.per": _STRATEGY_NAMES,
    "customConstants.per": _STRATEGY_NAMES,
}
_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
_INTEGER = re.compile(r"-?[0-9]+")
_NON_CODE = re.compile(r';[^\r\n]*|"(?:\\.|[^"\\])*"')
_TOKEN = re.compile(r"\(|\)|[^\s()]+")
_LOAD_IF = re.compile(r"#load-if-(defined|not-defined)\s+([A-Za-z0-9_-]+)")
_CIV = re.compile(r"[A-Z0-9_-]+-CIV")


@dataclass(frozen=True)
class DefconstSpan:
    start: int
    end: int
    name: str
    value: str
    civ: str


def eligible_defconst_spans(module: str, source_text: str) -> list[DefconstSpan]:
    """Return approved integer-token offsets in the unchanged official source.

    Only a top-level literal defconst inside a single positive CIV condition is
    eligible. WEI duplicates in customConstants and disabled building counts
    remain fixed. Strings/comments are masked without changing character offsets.
    """
    if module not in MODULE_PROFILES:
        raise CuratedDefconstError(f"{module}: no curated defconst profile")
    code = _NON_CODE.sub(
        lambda match: re.sub(r"[^\r\n]", " ", match.group()), source_text,
    )
    conditions: list[tuple[str, str, bool]] = []
    spans = []
    offset = 0
    depth = 0
    for line in code.splitlines(keepends=True):
        directive = line.strip()
        load = _LOAD_IF.fullmatch(directive)
        if load:
            conditions.append((load.group(1), load.group(2), False))
        elif directive == "#else":
            if not conditions or conditions[-1][2]:
                raise CuratedDefconstError(f"{module}: unmatched/repeated #else")
            kind, symbol, _ = conditions[-1]
            conditions[-1] = (kind, symbol, True)
        elif directive == "#end-if":
            if not conditions:
                raise CuratedDefconstError(f"{module}: unmatched #end-if")
            conditions.pop()
        else:
            tokens = list(_TOKEN.finditer(line))
            for index, token in enumerate(tokens):
                word = token.group()
                if depth == 0 and word == "(" and index + 4 < len(tokens):
                    expression = tokens[index:index + 5]
                    _, command, name, value, closing = [item.group() for item in expression]
                    context = conditions[0] if len(conditions) == 1 else None
                    if (
                        command == "defconst" and closing == ")"
                        and name in MODULE_PROFILES[module]
                        and _INTEGER.fullmatch(value)
                        and context is not None
                        and context[0] == "defined" and not context[2]
                        and _CIV.fullmatch(context[1])
                        and not (module == "customConstants.per" and context[1] == "WEI-CIV")
                        and not (name.startswith("number-") and int(value) <= 0)
                    ):
                        spans.append(DefconstSpan(
                            offset + expression[3].start(),
                            offset + expression[3].end(), name, value, context[1],
                        ))
                if word == "(":
                    depth += 1
                elif word == ")":
                    depth -= 1
        offset += len(line)
    if conditions:
        raise CuratedDefconstError(f"{module}: unclosed conditional")
    if depth:
        raise CuratedDefconstError(f"{module}: unbalanced source parentheses")
    return spans


def validate_curated_defconst(module: str, source_text: str, template_text: str) -> None:
    """Require exactly one unique placeholder per eligible token; fix all else.

    Validation is independent of placeholder prefixes and official-defaults.
    Even a forbidden edit whose defaults restore the source exactly is rejected.
    Both inputs must be decoded without newline normalization.
    """
    source_pos = template_pos = 0
    seen = set()
    for span in eligible_defconst_spans(module, source_text):
        fixed = source_text[source_pos:span.start]
        if not template_text.startswith(fixed, template_pos):
            raise CuratedDefconstError(f"{module}: changed fixed text or non-curated placeholder")
        template_pos += len(fixed)
        placeholder = _PLACEHOLDER.match(template_text, template_pos)
        if placeholder is None:
            raise CuratedDefconstError(f"{module}: missing whole-token placeholder for {span.civ}/{span.name}")
        key = placeholder.group(1)
        if key in seen:
            raise CuratedDefconstError(f"{module}: repeated placeholder {key}")
        seen.add(key)
        source_pos = span.end
        template_pos = placeholder.end()
    if template_text[template_pos:] != source_text[source_pos:]:
        raise CuratedDefconstError(f"{module}: changed fixed text or non-curated placeholder")
