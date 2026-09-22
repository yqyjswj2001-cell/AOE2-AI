"""Host-only classification, exact source-span guards and author-card projection."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from cloze_boundary import BoundaryError, validate_no_noncode_placeholders, validate_strategy_answers

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "adjusted/cloze/classification/parameters.json"
AUTHOR_FIELDS = ("key", "category", "meaning", "unit", "context", "effect", "group_id", "constraints_note")
PH = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def load_catalog(path: Path = CATALOG) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != "aoe2-reviewed-parameters-v1":
        raise BoundaryError("unsupported classification schema")
    keys = set()
    total = 0
    for module, profile in doc["modules"].items():
        if Path(module).name != module or not module.endswith(".per"):
            raise BoundaryError("invalid classification module")
        previous_end = 0
        for row in profile["parameters"]:
            total += 1
            if row["key"] in keys or row["module"] != module:
                raise BoundaryError("duplicate or misplaced classified key")
            keys.add(row["key"])
            if row["decision"] not in ("dynamic", "fixed"):
                raise BoundaryError("unclassified parameter")
            if not (previous_end <= row["source_start"] < row["source_end"]):
                raise BoundaryError("overlapping or unordered source spans")
            previous_end = row["source_end"]
            if type(row["official_value"]) is not int:
                raise BoundaryError("current classification requires integer source values")
            for field in ("reason", "meaning", "context", "effect", "category", "unit"):
                if not isinstance(row[field], str) or not row[field].strip():
                    raise BoundaryError(f"{row['key']}: missing {field}")
    if total != doc["reviewed_candidates"] or total != 2295 or len(doc["modules"]) != 17:
        raise BoundaryError("classification does not cover the frozen 2295 candidates / 17 modules")
    return doc


def expected_template(module: str, official_text: str, catalog: dict) -> str:
    profile = catalog["modules"][module]
    if hashlib.sha256(official_text.encode("utf-8")).hexdigest() != profile["source_sha256"]:
        raise BoundaryError(f"{module}: official source changed; classification review required")
    parts = []
    cursor = 0
    for row in profile["parameters"]:
        start, end = row["source_start"], row["source_end"]
        if official_text[start:end] != str(row["official_value"]):
            raise BoundaryError(f"{row['key']}: source span mismatch")
        parts.append(official_text[cursor:start])
        parts.append("{{" + row["key"] + "}}" if row["decision"] == "dynamic" else official_text[start:end])
        cursor = end
    parts.append(official_text[cursor:])
    return "".join(parts)


def validate_classified_template(module: str, official_text: str, template_text: str, catalog: dict | None = None) -> None:
    catalog = catalog if catalog is not None else load_catalog()
    if module not in catalog["modules"]:
        raise BoundaryError(f"{module}: no reviewed parameter profile")
    validate_no_noncode_placeholders(module, template_text)
    if template_text != expected_template(module, official_text, catalog):
        raise BoundaryError(f"{module}: fixed source or reviewed placeholder position/name changed")


def validate_classified_answers(module: str, answers: dict, catalog: dict | None = None) -> None:
    catalog = catalog if catalog is not None else load_catalog()
    rows = catalog["modules"][module]["parameters"]
    expected = {r["key"] for r in rows if r["decision"] == "dynamic"}
    if not isinstance(answers, dict) or set(answers) != expected:
        raise BoundaryError(f"{module}: answers must contain exactly the reviewed dynamic keys")
    values = {r["key"]: r["official_value"] for r in rows}
    for key, value in answers.items():
        if type(value) is not int:
            raise BoundaryError(f"{key}: integer answer required")
        values[key] = value
    # Relationships may include a value that has since been made fixed.
    # Effective values include those literals without exposing them to authors.
    validate_strategy_answers(module, values)
    for constraint in catalog.get("constraints", []):
        if constraint["module"] != module:
            continue
        subset = [values[key] for key in constraint["keys"]]
        kind = constraint["kind"]
        if kind == "sum_equal":
            ok = sum(subset) == constraint["value"]
        elif kind == "less_equal":
            ok = len(subset) == 2 and subset[0] <= subset[1]
        elif kind == "minimum":
            ok = all(value >= constraint["value"] for value in subset)
        elif kind == "less_than":
            ok = len(subset) == 1 and subset[0] < constraint["value"]
        elif kind == "equal":
            ok = len(set(subset)) <= 1
        elif kind == "range":
            ok = all(constraint["minimum"] <= value <= constraint["maximum"] for value in subset)
        else:
            raise BoundaryError(f"unknown constraint kind: {kind}")
        if not ok:
            raise BoundaryError(f"{module}: inconsistent answers: {constraint['reason']}; keys={constraint['keys']}")


def make_author_cards(module: str, catalog: dict) -> dict:
    rows = catalog["modules"][module]["parameters"]
    cards = [{field: row[field] for field in AUTHOR_FIELDS} for row in rows if row["decision"] == "dynamic"]
    text = json.dumps(cards, ensure_ascii=False)
    validate_author_prose(text, module)
    fixed = {r["key"] for profile in catalog["modules"].values() for r in profile["parameters"] if r["decision"] == "fixed"}
    # Card prose must describe the situation, not refer authors to hidden inputs.
    referenced = set(re.findall(r"[A-Z][A-Z0-9_]+", text)) & fixed
    if referenced:
        raise BoundaryError(f"{module}: author card references fixed keys: {sorted(referenced)}")
    return {"module": module, "kind": "strategy_decisions_only", "runtime": "Unverified", "parameters": cards}


def validate_author_cards(catalog: dict, directory: Path) -> None:
    expected_names = {module.removesuffix(".per") + ".json" for module, profile in catalog["modules"].items() if any(r["decision"] == "dynamic" for r in profile["parameters"])}
    if {p.name for p in directory.glob("*.json")} != expected_names:
        raise BoundaryError("author card files differ from dynamic modules")
    for name in expected_names:
        module = name.removesuffix(".json") + ".per"
        actual = json.loads((directory / name).read_text(encoding="utf-8"))
        if actual != make_author_cards(module, catalog):
            raise BoundaryError(f"{module}: author cards differ from reviewed semantic projection")


def validate_author_prose(text: str, label: str) -> None:
    # PER expressions have an ASCII command atom directly after an opening paren.
    if re.search(r"\([a-z][a-z0-9-]*(?:\s+|\))|=>|\{\{", text):
        raise BoundaryError(f"{label}: author input contains PER expression syntax")
    if re.search(r"(?:官方|原始|默认)(?:数值|值|答案)?\s*(?:是|为|[:：=])\s*-?\d", text):
        raise BoundaryError(f"{label}: author prose exposes a reference answer")
