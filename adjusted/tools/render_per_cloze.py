#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from cloze_boundary import (
    BoundaryError, validate_no_noncode_placeholders,
    validate_strategy_answers,
)

from strategy_catalog import load_catalog, validate_classified_template, validate_classified_answers

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATES = ROOT / "adjusted/cloze/Promisory"
DEFAULT_DEFAULTS = ROOT / "adjusted/cloze/official-defaults"
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
SAFE_SYMBOL = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ClozeError(ValueError):
    pass


def placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


def validate_value(key: str, value, official_default):
    if isinstance(official_default, int) and not isinstance(official_default, bool):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ClozeError(f"{key}: integer required")
        return str(value)
    if isinstance(official_default, str):
        if not isinstance(value, str) or not SAFE_SYMBOL.fullmatch(value):
            raise ClozeError(f"{key}: safe PER symbol required")
        return value
    raise ClozeError(f"{key}: unsupported official default type")


def render_one(template: Path, answers_path: Path, defaults_path: Path) -> str:
    source = template.read_bytes().decode("utf-8")
    answers = json.loads(answers_path.read_text(encoding="utf-8-sig")) if answers_path.exists() else {}
    defaults_doc = json.loads(defaults_path.read_text(encoding="utf-8-sig"))
    defaults = defaults_doc["answers"]

    expected = placeholders(source)
    if set(answers) != expected:
        missing = sorted(expected - set(answers))
        extra = sorted(set(answers) - expected)
        raise ClozeError(f"{template.name}: answer keys differ; missing={missing} extra={extra}")
    if set(defaults) != expected:
        raise ClozeError(f"{template.name}: official defaults do not match placeholders")

    values = {}
    for key in sorted(expected):
        if answers[key] is None:
            raise ClozeError(f"{template.name}: unanswered blank {key}")
        values[key] = validate_value(key, answers[key], defaults[key])

    module = template.name.removesuffix(".tpl")
    try:
        validate_no_noncode_placeholders(module, source)
        catalog = load_catalog()
        official = (ROOT / "official/raw/Promisory" / module).read_bytes().decode("utf-8")
        validate_classified_template(module, official, source, catalog)
        validate_classified_answers(module, answers, catalog)
    except BoundaryError as exc:
        raise ClozeError(str(exc)) from exc

    rendered = PLACEHOLDER.sub(lambda m: values[m.group(1)], source)
    if PLACEHOLDER.search(rendered):
        raise ClozeError(f"{template.name}: unresolved placeholder")
    return rendered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--defaults", type=Path, default=DEFAULT_DEFAULTS)
    parser.add_argument("--answers-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        templates = sorted(args.templates.glob("*.per.tpl"))
        if not templates:
            raise ClozeError("no templates found")
        catalog = load_catalog()
        if {p.name.removesuffix(".tpl") for p in templates} != set(catalog["modules"]):
            raise ClozeError("complete reviewed template set is required; missing or extra module")
        rendered_modules = {}
        for template in templates:
            module = template.name.removesuffix(".tpl")
            answer_file = args.answers_dir / f"{module.removesuffix('.per')}.json"
            defaults_file = args.defaults / f"{module.removesuffix('.per')}.json"
            rendered = render_one(template, answer_file, defaults_file)
            rendered_modules[module] = rendered.encode("utf-8")
        # Validate the whole answer bundle before creating or changing output.
        args.out.mkdir(parents=True, exist_ok=True)
        for module, data in rendered_modules.items():
            (args.out / module).write_bytes(data)
    except (OSError, json.JSONDecodeError, ClozeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({"ok": True, "modules": len(templates), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
