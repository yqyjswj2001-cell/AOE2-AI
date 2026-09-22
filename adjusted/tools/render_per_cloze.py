#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATES = ROOT / "adjusted/cloze/Promisory"
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
SAFE_SYMBOL = re.compile(r"^[a-z0-9][a-z0-9-]*$")

AGES = ("DARK", "FEUDAL", "CASTLE", "IMPERIAL")


class ClozeError(ValueError):
    pass


def template_files(root: Path) -> list[Path]:
    return sorted(root.glob("*.per.tpl"))


def collect_placeholders(root: Path) -> set[str]:
    keys: set[str] = set()
    for path in template_files(root):
        keys.update(PLACEHOLDER.findall(path.read_text(encoding="utf-8")))
    return keys


def validate_value(key: str, value) -> str:
    if isinstance(value, bool):
        raise ClozeError(f"{key}: booleans are not allowed")
    if isinstance(value, int):
        if value < 0 or value > 100000:
            raise ClozeError(f"{key}: integer out of range")
        return str(value)
    if isinstance(value, str) and SAFE_SYMBOL.fullmatch(value):
        return value
    raise ClozeError(f"{key}: must be an integer or safe PER symbol")


def require_int(answers: dict, key: str, low: int, high: int) -> int:
    value = answers[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ClozeError(f"{key}: integer required")
    if not low <= value <= high:
        raise ClozeError(f"{key}: expected {low}..{high}, got {value}")
    return value


def semantic_checks(answers: dict) -> None:
    if answers["SHORTAGE_RESOURCE"] not in ("food", "wood", "gold", "stone"):
        raise ClozeError("SHORTAGE_RESOURCE must be food, wood, gold, or stone")
    require_int(answers, "SHORTAGE_STOCK", 0, 10000)
    require_int(answers, "PRESSURE_COUNT", 1, 200)
    require_int(answers, "FORT_COUNT", 1, 30)
    require_int(answers, "MILITARY_DISADVANTAGE", 1, 100)

    for age in AGES:
        total = sum(require_int(answers, f"{age}_{r}", 0, 100) for r in ("FOOD", "WOOD", "GOLD", "STONE"))
        if total != 100:
            raise ClozeError(f"{age} economy totals {total}, expected 100")

        shortage_total = sum(require_int(answers, f"{age}_SHORTAGE_{r}", 0, 100) for r in ("FOOD", "WOOD", "GOLD", "STONE"))
        if shortage_total != 100:
            raise ClozeError(f"{age} shortage economy totals {shortage_total}, expected 100")

        require_int(answers, f"{age}_LAND_EXPLORERS", 0, 5)
        require_int(answers, f"{age}_BOAT_EXPLORERS", 0, 3)

        target = require_int(answers, f"{age}_MILITARY_TARGET", 0, 200)
        caps = [require_int(answers, f"{age}_UNIT_{i}_CAP", 0, 200) for i in range(1, 4)]
        if sum(caps) != target:
            raise ClozeError(f"{age} unit caps total {sum(caps)}, military target is {target}")

        for prefix in ("PRESSURE", "FORT"):
            reaction_target = require_int(answers, f"{prefix}_{age}_MILITARY_TARGET", 0, 200)
            reaction_caps = [require_int(answers, f"{prefix}_{age}_UNIT_{i}_CAP", 0, 200) for i in range(1, 4)]
            if sum(reaction_caps) != reaction_target:
                raise ClozeError(
                    f"{prefix} {age} unit caps total {sum(reaction_caps)}, military target is {reaction_target}"
                )

        start = require_int(answers, f"{age}_ATTACK_START", 1, 200)
        stop = require_int(answers, f"{age}_ATTACK_STOP", 0, 199)
        if stop >= start:
            raise ClozeError(f"{age}: attack stop must be below attack start")
        require_int(answers, f"{age}_ATTACK_GROUP_SIZE", 1, 60)
        require_int(answers, f"{age}_ATTACK_PERCENT", 0, 100)

        dstart = require_int(answers, f"DISADV_{age}_ATTACK_START", 1, 200)
        dstop = require_int(answers, f"DISADV_{age}_ATTACK_STOP", 0, 199)
        if dstop >= dstart:
            raise ClozeError(f"DISADV {age}: attack stop must be below attack start")
        require_int(answers, f"DISADV_{age}_ATTACK_GROUP_SIZE", 1, 60)
        require_int(answers, f"DISADV_{age}_ATTACK_PERCENT", 0, 100)

        require_int(answers, f"{age}_HOUSING_HEADROOM", 2, 20)

        for i in range(1, 9):
            require_int(answers, f"{age}_BUILDING_{i}_COUNT", 0, 30)

    trigger = require_int(answers, "THREAT_TRIGGER", 1, 60)
    clear = require_int(answers, "THREAT_CLEAR", 0, 59)
    if clear >= trigger:
        raise ClozeError("THREAT_CLEAR must be below THREAT_TRIGGER")

    require_int(answers, "MARKET_GOLD_FLOOR", 0, 10000)
    for resource in ("FOOD", "WOOD", "STONE"):
        require_int(answers, f"SELL_{resource}_STOCK_ABOVE", 0, 10000)
        require_int(answers, f"SELL_{resource}_MIN_PRICE", 0, 1000)
        require_int(answers, f"BUY_{resource}_STOCK_BELOW", 0, 10000)
        require_int(answers, f"BUY_{resource}_GOLD_ABOVE", 0, 10000)
        require_int(answers, f"BUY_{resource}_MAX_PRICE", 0, 1000)
        if answers[f"BUY_{resource}_STOCK_BELOW"] >= answers[f"SELL_{resource}_STOCK_ABOVE"]:
            raise ClozeError(f"{resource}: buy stock threshold must be below sell threshold")

    for age in ("FEUDAL", "CASTLE", "IMPERIAL"):
        require_int(answers, f"{age}_AGEUP_POP", 0, 200)
        require_int(answers, f"{age}_AGEUP_FOOD_PCT", 0, 100)
        require_int(answers, f"{age}_AGEUP_GOLD_PCT", 0, 100)

    for i in range(1, 8 + 1):
        require_int(answers, f"MIL_TECH_{i}_MIN_COUNT", 0, 999)


def render(templates: Path, answers: dict, out: Path) -> None:
    expected = collect_placeholders(templates)
    supplied = set(answers)
    missing = expected - supplied
    extra = supplied - expected
    if missing:
        raise ClozeError(f"missing answers: {sorted(missing)}")
    if extra:
        raise ClozeError(f"unknown answers: {sorted(extra)}")

    semantic_checks(answers)
    rendered_values = {key: validate_value(key, answers[key]) for key in expected}

    out.mkdir(parents=True, exist_ok=True)
    for path in template_files(templates):
        source = path.read_text(encoding="utf-8")
        result = PLACEHOLDER.sub(lambda m: rendered_values[m.group(1)], source)
        if PLACEHOLDER.search(result):
            raise ClozeError(f"{path.name}: unresolved placeholder")
        depth = 0
        for raw in result.splitlines():
            line = raw.split(";", 1)[0]
            depth += line.count("(") - line.count(")")
            if depth < 0:
                raise ClozeError(f"{path.name}: invalid parentheses")
        if depth != 0:
            raise ClozeError(f"{path.name}: unbalanced parentheses")
        target = out / path.name.removesuffix(".tpl")
        target.write_text(result, encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--make-blank", type=Path)
    args = parser.parse_args(argv)

    if args.make_blank:
        blank = {key: None for key in sorted(collect_placeholders(args.templates))}
        args.make_blank.parent.mkdir(parents=True, exist_ok=True)
        args.make_blank.write_text(json.dumps(blank, indent=2) + "\n", encoding="utf-8")
        return 0

    if args.answers is None or args.out is None:
        parser.error("--answers and --out are required unless --make-blank is used")

    try:
        answers = json.loads(args.answers.read_text(encoding="utf-8-sig"))
        if not isinstance(answers, dict):
            raise ClozeError("answers must be a JSON object")
        render(args.templates, answers, args.out)
    except (OSError, json.JSONDecodeError, ClozeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({"ok": True, "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
