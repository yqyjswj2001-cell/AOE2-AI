#!/usr/bin/env python3
"""Compile Dynamic Strategy v1 into strategy-owned Promisory modules.

This compiler never generates or overwrites Fixed Runtime modules. It consumes
the bounded JSON strategy contract and produces only strategy-owned behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXED = ROOT / "adjusted/config/fixed-parameters.v1.json"

AGE_SYMBOL = {
    "dark": "dark-age",
    "feudal": "feudal-age",
    "castle": "castle-age",
    "imperial": "imperial-age",
}

AGE_ORDER = ("dark", "feudal", "castle", "imperial")

REACTION_UNIT_SYMBOL = {
    "infantry": "infantry-class",
    "spearman": "spearman-line",
    "cavalry": "cavalry-class",
    "archer": "archer-line",
    "skirmisher": "skirmisher-line",
    "cavalry-archer": "cavalry-archer-class",
    "siege": "siege-weapon-class",
    "monk": "monk",
}

DYNAMIC_MODULES = (
    "scoutcontrol.per",
    "gatherers.per",
    "units.per",
    "buildings.per",
    "escrow.per",
    "trade.per",
    "threats.per",
    "tsa.per",
    "orb.per",
)


class CompileError(ValueError):
    pass


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).strip().casefold()).strip("-")


def unit_symbol(name: str) -> str:
    value = slug(name)
    if not value:
        raise CompileError(f"invalid unit name: {name!r}")
    return value


def building_symbol(name: str) -> str:
    value = slug(name)
    if not value:
        raise CompileError(f"invalid building name: {name!r}")
    return value


def header(module: str, strategy_sha: str) -> list[str]:
    return [
        "; GENERATED DYNAMIC STRATEGY - DO NOT EDIT BY HAND",
        f"; official module boundary: Promisory/{module}",
        f"; dynamic strategy sha256: {strategy_sha}",
        "; fixed runtime values are owned by adjusted/config/fixed-parameters.v1.json",
        "",
    ]


def rule(conditions: list[str], actions: list[str]) -> list[str]:
    return ["(defrule", *[f"\t{x}" for x in conditions], "=>", *[f"\t{x}" for x in actions], ")", ""]


def validate_strategy(doc: dict) -> None:
    if doc.get("schema_version") != "1.0":
        raise CompileError("schema_version must be 1.0")
    base = doc["base_plan"]

    priorities = [r["priority"] for r in doc["reactions"]]
    if len(priorities) != len(set(priorities)):
        raise CompileError("reaction priorities must be unique")

    ids = [r["id"] for r in doc["reactions"]]
    if len(ids) != len(set(ids)):
        raise CompileError("reaction ids must be unique")

    for age in AGE_ORDER:
        mix = base["economy"][age]
        if sum(mix[k] for k in ("food", "wood", "gold", "stone")) != 100:
            raise CompileError(f"economy.{age} must total 100")
        validate_military(base["military"][age], f"military.{age}")
        validate_combat(base["combat"][age], f"combat.{age}")
        validate_buildings(base["buildings"][age], f"buildings.{age}")

    threat = base["threat_response"]
    if threat["enemy_units_in_town_clear"] >= threat["enemy_units_in_town_trigger"]:
        raise CompileError("threat clear threshold must be below trigger threshold")

    for reaction in doc["reactions"]:
        override = reaction["override"]
        if "economy" in override:
            mix = override["economy"]
            if sum(mix[k] for k in ("food", "wood", "gold", "stone")) != 100:
                raise CompileError(f"reaction {reaction['id']} economy must total 100")
        if "military" in override:
            validate_military(override["military"], f"reaction {reaction['id']} military")
        if "combat" in override:
            validate_combat(override["combat"], f"reaction {reaction['id']} combat")


def validate_military(plan: dict, where: str) -> None:
    target = plan["target_military_population"]
    comp = plan["composition"]
    if target == 0:
        if comp:
            raise CompileError(f"{where}: zero target requires empty composition")
        return
    if not comp:
        raise CompileError(f"{where}: positive target requires composition")
    if sum(x["share_percent"] for x in comp) != 100:
        raise CompileError(f"{where}: shares must total 100")
    if sum(1 for x in comp if x["role"] == "primary") != 1:
        raise CompileError(f"{where}: exactly one primary unit required")
    units = [unit_symbol(x["unit"]) for x in comp]
    if len(units) != len(set(units)):
        raise CompileError(f"{where}: duplicate unit")


def validate_combat(plan: dict, where: str) -> None:
    start = plan["attack_start_military_population"]
    stop = plan["attack_stop_military_population"]
    group = plan["attack_group_size"]
    percent = plan["attack_soldier_percent"]
    if start == 0:
        if any((stop, group, percent)):
            raise CompileError(f"{where}: inactive combat must use all-zero values")
        return
    if stop >= start:
        raise CompileError(f"{where}: stop must be below start")
    if group <= 0 or percent <= 0:
        raise CompileError(f"{where}: active combat requires positive group and percent")


def validate_buildings(plan: dict, where: str) -> None:
    names = [building_symbol(x["building"]) for x in plan["desired"]]
    if len(names) != len(set(names)):
        raise CompileError(f"{where}: duplicate building target")


def allocate_caps(composition: list[dict], target: int) -> list[int]:
    if not composition:
        return []
    raw = [target * row["share_percent"] / 100.0 for row in composition]
    caps = [int(x) for x in raw]
    remaining = target - sum(caps)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - caps[i]), i))
    for i in order[:remaining]:
        caps[i] += 1
    for i, cap in enumerate(caps):
        if cap:
            continue
        donors = sorted(range(len(caps)), key=lambda j: (-caps[j], j))
        donor = next((j for j in donors if caps[j] > 1), None)
        if donor is None:
            raise CompileError("cannot allocate at least one slot to each selected unit")
        caps[donor] -= 1
        caps[i] = 1
    return caps


def trigger_condition(trigger: dict, active: bool = True) -> str:
    t = trigger["type"]
    if t == "enemy_unit_pressure":
        symbol = REACTION_UNIT_SYMBOL[trigger["category"]]
        n = trigger["minimum_count"]
        op = ">=" if active else "<"
        return f"(players-unit-type-count target-player {symbol} {op} {n})"
    if t == "resource_shortage":
        resource = trigger["resource"]
        n = trigger["stock_below"]
        op = "<" if active else ">="
        return f"({resource}-amount {op} {n})"
    if t == "under_attack":
        n = trigger["minimum_enemy_units_in_town"]
        op = ">=" if active else "<"
        return f"(up-enemy-units-in-town {op} {n})"
    if t == "military_disadvantage":
        n = trigger["minimum_enemy_advantage"]
        threshold = -n
        op = "<=" if active else ">"
        return f"(strategic-number sn-military-superiority {op} {threshold})"
    if t == "enemy_fortification":
        building = building_symbol(trigger["building"])
        n = trigger["minimum_count"]
        op = ">=" if active else "<"
        return f"(players-building-type-count target-player {building} {op} {n})"
    raise CompileError(f"unsupported reaction trigger: {t}")


def domain_reactions(doc: dict, domain: str, age: str) -> list[dict]:
    rows = [
        r for r in doc["reactions"]
        if age in r["ages"] and domain in r["override"]
    ]
    return sorted(rows, key=lambda r: (-r["priority"], r["id"]))


def reaction_conditions(rows: list[dict], index: int, age: str) -> list[str]:
    current = rows[index]
    conditions = [f"(current-age == {AGE_SYMBOL[age]})"]
    conditions.extend(trigger_condition(r["when"], active=False) for r in rows[:index])
    conditions.append(trigger_condition(current["when"], active=True))
    return conditions


def base_conditions(rows: list[dict], age: str) -> list[str]:
    return [
        f"(current-age == {AGE_SYMBOL[age]})",
        *[trigger_condition(r["when"], active=False) for r in rows],
    ]


def compile_scoutcontrol(doc: dict, fixed: dict, sha: str) -> str:
    out = header("scoutcontrol.per", sha)
    seconds = fixed["fixed"]["scouting"]["scout_reissue_seconds"]
    out += rule(["(true)"], [f"(enable-timer fifteensec {seconds})", "(disable-self)"])

    for age in AGE_ORDER:
        rows = domain_reactions(doc, "scouting", age)
        plans = [(reaction_conditions(rows, i, age), r["override"]["scouting"]) for i, r in enumerate(rows)]
        plans.append((base_conditions(rows, age), doc["base_plan"]["scouting"][age]))
        for conditions, plan in plans:
            land = plan["land_explorers"]
            boat = plan["boat_explorers"]
            out += rule(conditions, [
                f"(set-strategic-number sn-number-explore-groups {land})",
                f"(set-strategic-number sn-total-number-explorers {land})",
                f"(set-strategic-number sn-number-boat-explore-groups {boat})",
            ])
            if land > 0:
                out += rule(
                    [*conditions, "(timer-triggered fifteensec)", "(military-population >= 1)"],
                    ["(up-send-scout group-type-land-explore scout-center)", f"(enable-timer fifteensec {seconds})"],
                )
    out += rule(["(timer-triggered fifteensec)"], [f"(enable-timer fifteensec {seconds})"])
    return "\n".join(out)


def economy_actions(mix: dict) -> list[str]:
    return [
        f"(set-strategic-number sn-food-gatherer-percentage {mix['food']})",
        f"(set-strategic-number sn-wood-gatherer-percentage {mix['wood']})",
        f"(set-strategic-number sn-gold-gatherer-percentage {mix['gold']})",
        f"(set-strategic-number sn-stone-gatherer-percentage {mix['stone']})",
    ]


def compile_gatherers(doc: dict, sha: str) -> str:
    out = header("gatherers.per", sha)
    for age in AGE_ORDER:
        rows = domain_reactions(doc, "economy", age)
        for i, reaction in enumerate(rows):
            out += rule(reaction_conditions(rows, i, age), economy_actions(reaction["override"]["economy"]))
        out += rule(base_conditions(rows, age), economy_actions(doc["base_plan"]["economy"][age]))
    return "\n".join(out)


def emit_military_plan(out: list[str], conditions: list[str], plan: dict) -> None:
    target = plan["target_military_population"]
    if target <= 0:
        return
    caps = allocate_caps(plan["composition"], target)
    for row, cap in zip(plan["composition"], caps):
        unit = unit_symbol(row["unit"])
        out.extend(rule(
            [*conditions, f"(military-population < {target})", f"(unit-type-count-total {unit} < {cap})", f"(can-train {unit})"],
            [f"(train {unit})"],
        ))


def compile_units(doc: dict, sha: str) -> str:
    out = header("units.per", sha)
    for age in AGE_ORDER:
        rows = domain_reactions(doc, "military", age)
        for i, reaction in enumerate(rows):
            emit_military_plan(out, reaction_conditions(rows, i, age), reaction["override"]["military"])
        emit_military_plan(out, base_conditions(rows, age), doc["base_plan"]["military"][age])
    return "\n".join(out)


def compile_buildings(doc: dict, sha: str) -> str:
    out = header("buildings.per", sha)
    for age in AGE_ORDER:
        plan = doc["base_plan"]["buildings"][age]
        age_condition = f"(current-age == {AGE_SYMBOL[age]})"
        out += rule(
            [age_condition, f"(housing-headroom < {plan['housing_headroom']})", "(population-headroom > 0)",
             "(up-pending-objects c: house <= 0)", "(can-build house)"],
            ["(build house)"],
        )
        for row in plan["desired"]:
            building = building_symbol(row["building"])
            target = row["target_count"]
            out += rule(
                [age_condition, f"(building-type-count-total {building} < {target})",
                 f"(up-pending-objects c: {building} <= 0)", f"(can-build {building})"],
                [f"(build {building})"],
            )
    return "\n".join(out)


def compile_escrow(doc: dict, sha: str) -> str:
    out = header("escrow.per", sha)
    mapping = (
        ("feudal", "dark-age", "feudal-age"),
        ("castle", "feudal-age", "castle-age"),
        ("imperial", "castle-age", "imperial-age"),
    )
    for key, current_age, target_age in mapping:
        plan = doc["base_plan"]["age_up"][key]
        pop = plan["start_civilian_population"]
        food = plan["food_percent"]
        gold = plan["gold_percent"]
        out += rule(
            [f"(current-age == {current_age})", f"(civilian-population >= {pop})",
             f"(not (can-research-with-escrow {target_age}))"],
            [f"(set-escrow-percentage food {food})", "(set-escrow-percentage wood 0)",
             f"(set-escrow-percentage gold {gold})", "(set-escrow-percentage stone 0)"],
        )
        out += rule(
            [f"(current-age == {current_age})", f"(civilian-population >= {pop})",
             f"(can-research-with-escrow {target_age})"],
            [f"(research {target_age})", "(set-escrow-percentage food 0)", "(set-escrow-percentage wood 0)",
             "(set-escrow-percentage gold 0)", "(set-escrow-percentage stone 0)"],
        )
    return "\n".join(out)


def compile_trade(doc: dict, sha: str) -> str:
    out = header("trade.per", sha)
    market = doc["base_plan"]["market"]
    floor = market["gold_floor"]
    for row in market["sell_rules"]:
        resource = row["resource"]
        out += rule(
            ["(building-type-count-total market >= 1)", f"({resource}-amount > {row['stock_above']})",
             f"(gold-amount < {floor})", f"(commodity-selling-price {resource} >= {row['minimum_price']})",
             f"(can-sell-commodity {resource})"],
            [f"(sell-commodity {resource})"],
        )
    for row in market["buy_rules"]:
        resource = row["resource"]
        out += rule(
            ["(building-type-count-total market >= 1)", f"({resource}-amount < {row['stock_below']})",
             f"(gold-amount > {row['gold_above']})", f"(commodity-buying-price {resource} <= {row['maximum_price']})",
             f"(can-buy-commodity {resource})"],
            [f"(buy-commodity {resource})"],
        )
    return "\n".join(out)


def compile_threats(doc: dict, sha: str) -> str:
    out = header("threats.per", sha)
    plan = doc["base_plan"]["threat_response"]
    trigger = plan["enemy_units_in_town_trigger"]
    clear = plan["enemy_units_in_town_clear"]
    out += rule(
        [f"(up-enemy-units-in-town >= {trigger})", "(town-under-attack)"],
        ["(set-goal defend yes)", "(set-goal underattack yes)"],
    )
    out += rule(
        ["(enemy-buildings-in-town)"],
        ["(set-goal defend yes)", "(set-goal underattack yes)"],
    )
    out += rule(
        [f"(up-enemy-units-in-town <= {clear})", "(not (town-under-attack))", "(not (enemy-buildings-in-town))"],
        ["(set-goal underattack no)", "(set-goal defend no)"],
    )
    return "\n".join(out)


def emit_tsa_plan(out: list[str], conditions: list[str], plan: dict) -> None:
    start = plan["attack_start_military_population"]
    stop = plan["attack_stop_military_population"]
    if start <= 0:
        out.extend(rule([*conditions, "(goal attacking yes)"], ["(set-goal attacking no)"]))
        return
    out.extend(rule(
        [*conditions, "(goal underattack no)", "(goal attacking no)", f"(military-population >= {start})",
         "(players-building-count any-enemy >= 1)"],
        ["(set-goal attacking yes)"],
    ))
    out.extend(rule(
        [*conditions, "(goal attacking yes)", "(or", f"\t(military-population <= {stop})", "\t(goal underattack yes))"],
        ["(set-goal attacking no)"],
    ))


def compile_tsa(doc: dict, sha: str) -> str:
    out = header("tsa.per", sha)
    for age in AGE_ORDER:
        rows = domain_reactions(doc, "combat", age)
        for i, reaction in enumerate(rows):
            emit_tsa_plan(out, reaction_conditions(rows, i, age), reaction["override"]["combat"])
        emit_tsa_plan(out, base_conditions(rows, age), doc["base_plan"]["combat"][age])
    return "\n".join(out)


def emit_orb_plan(out: list[str], conditions: list[str], plan: dict, active_groups: int) -> None:
    if plan["attack_start_military_population"] <= 0:
        return
    size = plan["attack_group_size"]
    percent = plan["attack_soldier_percent"]
    out.extend(rule(
        [*conditions, "(goal attacking yes)"],
        [f"(set-strategic-number sn-number-attack-groups {active_groups})",
         f"(set-strategic-number sn-percent-attack-soldiers {percent})",
         f"(set-strategic-number sn-minimum-attack-group-size {size})",
         f"(set-strategic-number sn-maximum-attack-group-size {size})"],
    ))


def compile_orb(doc: dict, fixed: dict, sha: str) -> str:
    out = header("orb.per", sha)
    combat_fixed = fixed["fixed"]["combat_runtime"]
    active_groups = combat_fixed["active_attack_groups"]
    baseline = combat_fixed["baseline_attack_group_size"]
    for age in AGE_ORDER:
        rows = domain_reactions(doc, "combat", age)
        for i, reaction in enumerate(rows):
            emit_orb_plan(out, reaction_conditions(rows, i, age), reaction["override"]["combat"], active_groups)
        emit_orb_plan(out, base_conditions(rows, age), doc["base_plan"]["combat"][age], active_groups)
    out += rule(
        ["(goal attacking no)"],
        ["(set-strategic-number sn-number-attack-groups 0)", "(set-strategic-number sn-percent-attack-soldiers 0)",
         f"(set-strategic-number sn-minimum-attack-group-size {baseline['minimum']})",
         f"(set-strategic-number sn-maximum-attack-group-size {baseline['maximum']})"],
    )
    return "\n".join(out)


def compile_document(doc: dict, fixed: dict) -> tuple[dict[str, str], dict]:
    validate_strategy(doc)
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()

    files = {
        "scoutcontrol.per": compile_scoutcontrol(doc, fixed, sha),
        "gatherers.per": compile_gatherers(doc, sha),
        "units.per": compile_units(doc, sha),
        "buildings.per": compile_buildings(doc, sha),
        "escrow.per": compile_escrow(doc, sha),
        "trade.per": compile_trade(doc, sha),
        "threats.per": compile_threats(doc, sha),
        "tsa.per": compile_tsa(doc, sha),
        "orb.per": compile_orb(doc, fixed, sha),
    }
    manifest = {
        "schema_version": doc["schema_version"],
        "civilization": doc["civilization"],
        "strategy_sha256": sha,
        "fixed_schema_version": fixed["schema_version"],
        "generated_modules": {},
        "not_yet_compiled": ["research", "target_priority"],
    }
    for name, content in files.items():
        data = content.encode("utf-8")
        manifest["generated_modules"][name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    return files, manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("strategy", type=Path)
    parser.add_argument("--fixed", type=Path, default=DEFAULT_FIXED)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        doc = load_json(args.strategy)
        fixed = load_json(args.fixed)
        files, manifest = compile_document(doc, fixed)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, CompileError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8", newline="\n")
    (args.out / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"ok": True, "out": str(args.out), "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
