#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from curated_defconst import (
    MODULE_PROFILES, CuratedDefconstError, validate_curated_defconst,
)

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "official/raw/Promisory"
ADJUSTED = ROOT / "adjusted/Promisory"
TEMPLATES = ROOT / "adjusted/cloze/Promisory"
DEFAULTS = ROOT / "adjusted/cloze/official-defaults"
ANSWERS = ROOT / "adjusted/cloze/answers"
PH = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


official_files = sorted(p.name for p in OFFICIAL.glob("*.per"))
adjusted_files = sorted(p.name for p in ADJUSTED.glob("*.per"))
if official_files != adjusted_files or len(official_files) != 36:
    raise SystemExit("adjusted Promisory must mirror all 36 official filenames")

for name in official_files:
    a = (OFFICIAL / name).read_bytes()
    b = (ADJUSTED / name).read_bytes()
    if a != b:
        raise SystemExit(f"{name}: adjusted baseline is not byte-identical to official")

templates = sorted(TEMPLATES.glob("*.per.tpl"))
if not templates:
    raise SystemExit("no official-derived cloze templates")
missing_curated = set(MODULE_PROFILES) - {tpl.name.removesuffix(".tpl") for tpl in templates}
if missing_curated:
    raise SystemExit(f"missing curated defconst templates: {sorted(missing_curated)}")

for tpl in templates:
    module = tpl.name.removesuffix(".tpl")
    stem = module.removesuffix(".per")
    official_bytes = (OFFICIAL / module).read_bytes()
    official_text = official_bytes.decode("utf-8")
    template_text = tpl.read_bytes().decode("utf-8")
    if module in MODULE_PROFILES:
        try:
            validate_curated_defconst(module, official_text, template_text)
        except CuratedDefconstError as exc:
            raise SystemExit(str(exc)) from exc
    if module == "finalingConstants.per" and template_text != official_text:
        raise SystemExit("finalingConstants.per: all constants remain fixed")
    defaults_doc = json.loads((DEFAULTS / f"{stem}.json").read_text(encoding="utf-8"))
    defaults = defaults_doc["answers"]
    keys = set(PH.findall(template_text))

    if set(defaults) != keys:
        raise SystemExit(f"{module}: defaults/placeholders differ")
    if defaults_doc["source_file"] != module:
        raise SystemExit(f"{module}: wrong defaults source_file")
    if defaults_doc["source_blob_sha"] != git_blob_sha(official_bytes):
        raise SystemExit(f"{module}: recorded source blob SHA differs from official")

    restored = PH.sub(lambda m: str(defaults[m.group(1)]), template_text)
    if restored != official_text:
        raise SystemExit(f"{module}: filling official defaults does not restore exact official source")

    blank = json.loads((ANSWERS / f"{stem}.json").read_text(encoding="utf-8"))
    if set(blank) != keys or any(v is not None for v in blank.values()):
        raise SystemExit(f"{module}: blank answer sheet must contain exactly the placeholders with null values")


# Module-specific curation guards: placeholders may only exist in strategic
# tuning locations, never arbitrary implementation/control-flow literals.
def chunks(text: str):
    parts = re.split(r"(?=\(defrule)", text)
    return [x for x in parts if x]


gatherers = (TEMPLATES / "gatherers.per.tpl").read_bytes().decode("utf-8")
for line in gatherers.splitlines():
    if "{{" not in line:
        continue
    if not re.search(
        r"\(set-strategic-number\s+sn-(?:food|wood|gold|stone)-gatherer-percentage\s+\{\{",
        line,
    ):
        raise SystemExit(f"gatherers.per: placeholder outside gatherer percentage assignment: {line}")

tsa = (TEMPLATES / "tsa.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(tsa):
    if "{{" not in chunk:
        continue
    if "(set-goal attacking yes)" not in chunk and "(set-goal attacking no)" not in chunk:
        raise SystemExit("tsa.per: placeholder outside a rule that changes attacking state")

orb = (TEMPLATES / "orb.per.tpl").read_bytes().decode("utf-8")
for line in orb.splitlines():
    if "{{" not in line:
        continue
    if not re.search(
        r"sn-(?:minimum-attack-group-size|maximum-attack-group-size|percent-attack-soldiers|number-attack-groups)",
        line,
    ):
        raise SystemExit(f"orb.per: placeholder outside attack-group control: {line}")


def code_without_comments(text: str) -> str:
    return "\n".join(line.split(";", 1)[0] for line in text.splitlines())


units = (TEMPLATES / "units.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(units):
    if "{{UNITS_" not in chunk:
        continue
    code = code_without_comments(chunk)
    trains = set(re.findall(r"\(train\s+([a-z0-9-]+)\)", code))
    if not trains:
        raise SystemExit("units.per: placeholder outside direct train rule")
    for line in code.splitlines():
        if "{{UNITS_" not in line:
            continue
        m = re.search(
            r"\(unit-type-count(?:-total)?\s+([a-z0-9-]+)\s+(?:<|<=)\s+\{\{UNITS_",
            line,
        )
        if not m or m.group(1) not in trains:
            raise SystemExit(f"units.per: placeholder is not same-unit train cap: {line}")


buildings = (TEMPLATES / "buildings.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(buildings):
    if "{{BUILDINGS_" not in chunk:
        continue
    code = code_without_comments(chunk)
    builds = set(re.findall(r"\(build\s+([a-z0-9-]+)\)", code))
    if not builds:
        raise SystemExit("buildings.per: placeholder outside direct build rule")
    for line in code.splitlines():
        if "{{BUILDINGS_" not in line:
            continue
        m = re.search(
            r"\(building-type-count(?:-total)?\s+([a-z0-9-]+)\s+(?:<|<=)\s+\{\{BUILDINGS_",
            line,
        )
        if not m or m.group(1) not in builds:
            raise SystemExit(f"buildings.per: placeholder is not same-building target: {line}")


ECON_TECHS = {
    "ri-double-bit-axe", "ri-bow-saw", "ri-two-man-saw", "ri-horse-collar",
    "ri-heavy-plow", "ri-crop-rotation", "ri-wheel-barrow", "ri-hand-cart",
    "ri-gold-mining", "ri-gold-shaft-mining", "ri-stone-mining",
    "ri-stone-shaft-mining",
}
MIL_TECHS = {
    "ri-forging", "ri-iron-casting", "ri-blast-furnace",
    "ri-scale-mail-armor", "ri-chain-mail-armor", "ri-plate-mail-armor",
    "ri-scale-barding", "ri-chain-barding", "ri-plate-barding",
    "ri-fletching", "ri-bodkin-arrow", "ri-bracer",
    "ri-padded-archer-armor", "ri-leather-archer-armor",
    "ri-ring-archer-armor", "ri-bloodlines", "ri-husbandry", "ri-thumb-ring",
    "ri-ballistics", "ri-chemistry", "ri-siege-engineers", "ri-conscription",
    "ri-arson", "ri-squires",
}

researches = (TEMPLATES / "researches.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(researches):
    if "{{RESEARCH_" not in chunk:
        continue
    code = code_without_comments(chunk)
    mtech = re.search(r"\(research\s+([a-z0-9-]+)\)", code)
    if not mtech:
        raise SystemExit("researches.per: placeholder outside direct research rule")
    tech = mtech.group(1)
    if tech not in ECON_TECHS and tech not in MIL_TECHS:
        raise SystemExit(f"researches.per: placeholder exposed for non-curated tech {tech}")
    for line in code.splitlines():
        if "{{RESEARCH_ECON_" in line:
            ok = re.search(
                r"\((?:civilian-population|population|game-time|current-age-time|food-amount|wood-amount|gold-amount|stone-amount)\s+(?:>=|>)\s+\{\{RESEARCH_ECON_",
                line,
            ) or re.search(
                r"\(unit-type-count(?:-total)?\s+villager[a-z0-9-]*\s+(?:>=|>)\s+\{\{RESEARCH_ECON_",
                line,
            )
            if not ok or tech not in ECON_TECHS:
                raise SystemExit(f"researches.per: invalid economic-tech placeholder: {line}")
        if "{{RESEARCH_MIL_" in line:
            ok = re.search(
                r"\(unit-type-count(?:-total)?\s+[a-z0-9-]+\s+(?:>=|>)\s+\{\{RESEARCH_MIL_",
                line,
            ) or re.search(
                r"\(military-population\s+(?:>=|>)\s+\{\{RESEARCH_MIL_",
                line,
            )
            if not ok or tech not in MIL_TECHS:
                raise SystemExit(f"researches.per: invalid military-tech placeholder: {line}")


boarhunting = (TEMPLATES / "boarhunting.per.tpl").read_bytes().decode("utf-8")
BOAR_GOALS = (
    "totalsheep|mysheep|food-villagers|wood-villagers|villagercount|"
    "villagercounttotal|total-food-amount|deer-luring|forage-count"
)
for chunk in chunks(boarhunting):
    if "{{BOAR_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if (
        "(up-modify-goal minBoar" not in code
        and "(set-strategic-number sn-enable-boar-hunting 1)" not in code
    ):
        raise SystemExit("boarhunting.per: placeholder outside boar timing/enable rule")
    for line in code.splitlines():
        if "{{BOAR_" not in line:
            continue
        ok = (
            re.search(r"\(up-modify-goal\s+minBoar\s+c:(?:min|max)\s+\{\{BOAR_", line)
            or re.search(r"\(game-time\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{BOAR_", line)
            or re.search(
                r"\(unit-type-count(?:-total)?\s+villager(?:-[a-z0-9-]+)?\s+"
                r"(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{BOAR_",
                line,
            )
            or re.search(
                rf"\(up-compare-goal\s+(?:{BOAR_GOALS})\s+"
                r"(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{BOAR_",
                line,
            )
        )
        if not ok:
            raise SystemExit(f"boarhunting.per: invalid strategy placeholder: {line}")


threats = (TEMPLATES / "threats.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(threats):
    if "{{THREATS_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if (
        "(up-modify-sn sn-target-player-number g:= temporary-goal2)" not in code
        or "(up-modify-sn sn-focus-player-number g:= temporary-goal2)" not in code
    ):
        raise SystemExit("threats.per: placeholder outside direct target-switch rule")
    for line in code.splitlines():
        if "{{THREATS_" not in line:
            continue
        ok = (
            re.search(
                r"\(players-military-population\s+target-player\s+"
                r"(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{THREATS_",
                line,
            )
            or re.search(
                r"\(up-compare-goal\s+temporary-goal4\s+"
                r"(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{THREATS_",
                line,
            )
        )
        if not ok:
            raise SystemExit(f"threats.per: invalid target-switch placeholder: {line}")


watercontrol = (TEMPLATES / "watercontrol.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(watercontrol):
    if "{{WATER_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if not re.search(r"\(set-goal\s+water-action\s+[2-8]\)", code):
        raise SystemExit("watercontrol.per: placeholder outside water action decision")
    for line in code.splitlines():
        if "{{WATER_" not in line:
            continue
        if not re.search(
            r"\(up-compare-goal\s+water-advantage\s+"
            r"(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{WATER_ADVANTAGE_",
            line,
        ):
            raise SystemExit(f"watercontrol.per: invalid water-advantage placeholder: {line}")



dawn = (TEMPLATES / "dawn.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(dawn):
    if "{{DAWN_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if not re.search(r"\(up-modify-goal\s+(?:food|wood|gold|stone)-villagers\b", code):
        raise SystemExit("dawn.per: placeholder outside direct gatherer-allocation rule")
    for line in code.splitlines():
        if "{{DAWN_" not in line:
            continue
        ok = (
            re.search(r"\(game-time\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
            or re.search(r"\(gold-amount\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
            or re.search(r"\(unit-type-count\s+villager\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
            or re.search(r"\(unit-type-count-total\s+militiaman-line\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
            or re.search(r"\(up-compare-goal\s+(?:food|wood|gold|stone)-villagers\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
            or re.search(r"\(up-compare-goal\s+totalsheep\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{DAWN_", line)
        )
        if not ok:
            raise SystemExit(f"dawn.per: invalid gatherer-strategy placeholder: {line}")


finaling = (TEMPLATES / "finaling.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(finaling):
    if "{{FINAL_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if not re.search(r"\(train\s+[a-z0-9-]+\)", code):
        raise SystemExit("finaling.per: placeholder outside direct train rule")
    for line in code.splitlines():
        if "{{FINAL_" not in line:
            continue
        ok = (
            re.search(r"\((?:military-population|population|food-amount|wood-amount|gold-amount|stone-amount)\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{FINAL_", line)
            or re.search(r"\(unit-type-count(?:-total)?\s+(?:trebuchet-set|battering-ram-line)\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{FINAL_", line)
            or re.search(r"\(players-unit-type-count\s+any-enemy\s+(?:battle-elephant-line|war-elephant-line|elephant-archer-line|ballista-elephant-line)\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{FINAL_", line)
        )
        if not ok:
            raise SystemExit(f"finaling.per: invalid production placeholder: {line}")


resign = (TEMPLATES / "resign.per.tpl").read_bytes().decode("utf-8")
for chunk in chunks(resign):
    if "{{RESIGN_" not in chunk:
        continue
    code = code_without_comments(chunk)
    if "(set-goal resign yes)" not in code:
        raise SystemExit("resign.per: placeholder outside direct resign-decision rule")
    for line in code.splitlines():
        if "{{RESIGN_" not in line:
            continue
        ok = (
            re.search(r"\(population\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(players-population\s+[a-z0-9-]+\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(players-military-population\s+[a-z0-9-]+\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(military-population\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(strategic-number\s+(?:teamsuperiority|sn-military-superiority)\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(up-compare-goal\s+teamsuperiority-number\s+(?:g:|s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
            or re.search(r"\(game-time\s+(?:s:)?(?:>=|>|<=|<|==|!=)\s+\{\{RESIGN_", line)
        )
        if not ok:
            raise SystemExit(f"resign.per: invalid resign-strategy placeholder: {line}")


print("official-derived cloze PASS", len(official_files), "baseline files,", len(templates), "templates")
