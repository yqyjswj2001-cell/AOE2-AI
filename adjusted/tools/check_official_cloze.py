#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

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

for tpl in templates:
    module = tpl.name.removesuffix(".tpl")
    stem = module.removesuffix(".per")
    official_bytes = (OFFICIAL / module).read_bytes()
    official_text = official_bytes.decode("utf-8")
    template_text = tpl.read_bytes().decode("utf-8")
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

print("official-derived cloze PASS", len(official_files), "baseline files,", len(templates), "templates")
