#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = json.loads(
    (ROOT / "adjusted/examples/franks.dynamic-strategy.v1.json").read_text(encoding="utf-8")
)
SCHEMA = json.loads(
    (ROOT / "adjusted/schema/dynamic-strategy.v1.schema.json").read_text(encoding="utf-8")
)

AGES = ("dark", "feudal", "castle", "imperial")
FIXED_FORBIDDEN_KEYS = {
    "enabled",
    "civilian_exploration",
    "start_villager_count",
    "maximum_hunt_drop_distance",
    "idle_fishing_ship_stops_exploration",
    "minimum_game_time",
    "enemy_buildings_in_town_trigger",
    "faster_resign",
    "enable_resign",
    "enable_building_walling",
    "force_old_micro",
}


def fail(msg: str) -> None:
    raise SystemExit(msg)


def walk_keys(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key
            yield from walk_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_keys(child, f"{path}[{i}]")


def check_mix(mix: dict, where: str) -> None:
    total = sum(mix[k] for k in ("food", "wood", "gold", "stone"))
    if total != 100:
        fail(f"{where}: resource mix totals {total}, expected 100")


def check_military(plan: dict, where: str) -> None:
    target = plan["target_military_population"]
    composition = plan["composition"]
    if target == 0:
        if composition:
            fail(f"{where}: zero military target requires empty composition")
        return
    if not composition:
        fail(f"{where}: positive military target requires composition")
    if sum(x["share_percent"] for x in composition) != 100:
        fail(f"{where}: composition shares must total 100")
    if sum(1 for x in composition if x["role"] == "primary") != 1:
        fail(f"{where}: exactly one primary unit is required")
    units = [x["unit"] for x in composition]
    if len(units) != len(set(units)):
        fail(f"{where}: duplicate unit in composition")
    if target < len(composition):
        fail(f"{where}: target military population is smaller than composition size")


def check_combat(plan: dict, where: str) -> None:
    start = plan["attack_start_military_population"]
    stop = plan["attack_stop_military_population"]
    group = plan["attack_group_size"]
    percent = plan["attack_soldier_percent"]
    if start == 0:
        if any((stop, group, percent)):
            fail(f"{where}: zero attack start requires stop/group/percent all zero")
        return
    if stop >= start:
        fail(f"{where}: attack stop must be below attack start")
    if group <= 0:
        fail(f"{where}: active combat requires positive attack group size")
    if percent <= 0:
        fail(f"{where}: active combat requires positive attack soldier percent")


def check_buildings(plan: dict, where: str) -> None:
    names = [x["building"] for x in plan["desired"]]
    if len(names) != len(set(names)):
        fail(f"{where}: duplicate building target")


if STRATEGY.get("schema_version") != "1.0":
    fail("example: schema_version must be 1.0")

# Fixed/runtime fields may not re-enter the strategy payload.
for path, key in walk_keys(STRATEGY):
    if key in FIXED_FORBIDDEN_KEYS:
        fail(f"{path}: fixed/runtime field leaked into dynamic strategy: {key}")

base = STRATEGY["base_plan"]
for age in AGES:
    check_mix(base["economy"][age], f"base_plan.economy.{age}")
    check_military(base["military"][age], f"base_plan.military.{age}")
    check_combat(base["combat"][age], f"base_plan.combat.{age}")
    check_buildings(base["buildings"][age], f"base_plan.buildings.{age}")

if base["threat_response"]["enemy_units_in_town_clear"] >= base["threat_response"]["enemy_units_in_town_trigger"]:
    fail("base_plan.threat_response: clear threshold must be below trigger threshold")

sell = {x["resource"]: x for x in base["market"]["sell_rules"]}
buy = {x["resource"]: x for x in base["market"]["buy_rules"]}
if len(sell) != len(base["market"]["sell_rules"]):
    fail("base_plan.market: duplicate sell resource")
if len(buy) != len(base["market"]["buy_rules"]):
    fail("base_plan.market: duplicate buy resource")
for resource in sell.keys() & buy.keys():
    if buy[resource]["stock_below"] >= sell[resource]["stock_above"]:
        fail(f"base_plan.market: {resource} buy threshold must be below sell threshold")

ids = [x["id"] for x in STRATEGY["reactions"]]
priorities = [x["priority"] for x in STRATEGY["reactions"]]
if len(ids) != len(set(ids)):
    fail("reactions: ids must be unique")
if len(priorities) != len(set(priorities)):
    fail("reactions: priorities must be unique in v1")

allowed_triggers = {
    "enemy_unit_pressure",
    "resource_shortage",
    "under_attack",
    "military_disadvantage",
    "enemy_fortification",
}
allowed_overrides = {"scouting", "economy", "military", "combat", "target_priority"}

for reaction in STRATEGY["reactions"]:
    rid = reaction["id"]
    if not reaction["ages"] or not set(reaction["ages"]) <= set(AGES):
        fail(f"reaction {rid}: invalid ages")
    if reaction["when"]["type"] not in allowed_triggers:
        fail(f"reaction {rid}: unsupported trigger")
    override = reaction["override"]
    if not override:
        fail(f"reaction {rid}: override must not be empty")
    if not set(override) <= allowed_overrides:
        fail(f"reaction {rid}: unsupported override domain")
    if "economy" in override:
        check_mix(override["economy"], f"reaction {rid}.economy")
    if "military" in override:
        check_military(override["military"], f"reaction {rid}.military")
    if "combat" in override:
        check_combat(override["combat"], f"reaction {rid}.combat")

# Guard the schema itself against accidentally exposing known fixed fields.
schema_text = json.dumps(SCHEMA, ensure_ascii=False)
for key in FIXED_FORBIDDEN_KEYS:
    quoted = json.dumps(key)
    if quoted in schema_text:
        fail(f"schema exposes fixed/runtime field: {key}")

print("dynamic strategy v1 PASS")
