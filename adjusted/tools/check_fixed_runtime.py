#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "adjusted/config/fixed-parameters.v1.json").read_text(encoding="utf-8"))
P = ROOT / "adjusted/Promisory"


def text(name: str) -> str:
    return (P / name).read_text(encoding="utf-8")


def require(haystack: str, needle: str, where: str) -> None:
    if needle not in haystack:
        raise SystemExit(f"{where}: missing {needle}")


def forbid(haystack: str, needle: str, where: str) -> None:
    if needle in haystack:
        raise SystemExit(f"{where}: forbidden {needle}")


def balanced_per(name: str) -> None:
    depth = 0
    for raw in text(name).splitlines():
        line = raw.split(";", 1)[0]
        depth += line.count("(") - line.count(")")
        if depth < 0:
            raise SystemExit(f"{name}: closing parenthesis before opening")
    if depth != 0:
        raise SystemExit(f"{name}: unbalanced parentheses ({depth})")


fixed = CFG["fixed"]
init = text("init.per")
scout = fixed["scouting"]
eco = fixed["economy_runtime"]
hunt = fixed["hunting"]
combat = fixed["combat_runtime"]

for sn, value in (
    ("sn-percent-civilian-explorers", scout["civilian_explorer_percent"]),
    ("sn-cap-civilian-explorers", scout["civilian_explorer_cap"]),
    ("sn-minimum-civilian-explorers", scout["civilian_explorer_minimum"]),
    ("sn-number-explore-groups", scout["initial_land_explore_groups"]),
    ("sn-total-number-explorers", scout["initial_total_explorers"]),
    ("sn-number-boat-explore-groups", scout["initial_boat_explore_groups"]),
    ("sn-percent-civilian-gatherers", eco["civilian_gatherer_percent"]),
    ("sn-cap-civilian-gatherers", eco["civilian_gatherer_cap"]),
    ("sn-attack-intelligence", combat["attack_intelligence"]),
    ("sn-attack-separation-time-randomness", combat["attack_separation_time_randomness"]),
    ("sn-attack-group-size-randomness", combat["attack_group_size_randomness"]),
    ("sn-initial-attack-delay", combat["initial_attack_delay"]),
    ("sn-number-attack-groups", combat["initial_attack_groups"]),
    ("sn-number-defend-groups", combat["initial_defend_groups"]),
):
    require(init, f"(set-strategic-number {sn} {value})", "init.per")

require(init, f"(set-strategic-number sn-maximum-hunt-drop-distance {hunt['maximum_hunt_drop_distance']})", "init.per")
for resource, value in eco["initial_escrow_percent"].items():
    require(init, f"(set-escrow-percentage {resource} {value})", "init.per")

boar = text("boarhunting.per")
require(boar, f"(unit-type-count-total villager >= {hunt['activation_villager_count']})", "boarhunting.per")
require(boar, f"(set-strategic-number sn-maximum-hunt-drop-distance {hunt['maximum_hunt_drop_distance']})", "boarhunting.per")

resign = text("resign.per")
rcfg = fixed["resign"]
require(resign, f"(game-time >= {rcfg['minimum_game_time_seconds']})", "resign.per")
require(resign, f"(enable-timer resign-timer {rcfg['terminal_resign_timer_seconds']})", "resign.per")

custom = text("customConstants.per")
require(custom, f"(defconst enable-resign {1 if rcfg['enabled'] else 0})", "customConstants.per")
require(custom, f"(defconst faster-resign {1 if rcfg['faster_resign'] else 0})", "customConstants.per")
require(custom, f"(defconst enable-building-walling {1 if fixed['building_walling']['extreme_building_walling_enabled'] else 0})", "customConstants.per")
require(custom, f"(defconst force-old-micro {1 if fixed['micro']['force_old_micro'] else 0})", "customConstants.per")

for name in ("interaction.per", "event.per", "events.per"):
    s = text(name)
    forbid(s, "taunt-detected", name)
    forbid(s, "chat-to-", name)
    require(s, "(disable-self)", name)

wall = text("extremebuildings2.per")
forbid(wall, "(build ", "extremebuildings2.per")
forbid(wall, "(up-build", "extremebuildings2.per")
require(wall, "(disable-self)", "extremebuildings2.per")

for name in (
    "const.per", "customConstants.per", "finalingConstants.per", "init.per",
    "dawn.per", "general.per", "finaling.per", "boarhunting.per",
    "resign.per", "interaction.per", "event.per", "events.per",
    "extremebuildings2.per",
):
    balanced_per(name)

print("fixed runtime v1 PASS")
