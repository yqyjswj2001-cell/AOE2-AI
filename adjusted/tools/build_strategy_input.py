#!/usr/bin/env python3
"""Build a fresh author input containing decisions and facts, never fixed PER."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from strategy_catalog import ROOT, load_catalog, validate_author_cards, validate_classified_template, validate_author_prose, BoundaryError
import query_creator_facts as facts


def build(out: Path) -> dict:
    catalog = load_catalog()
    card_root = ROOT / "adjusted/cloze/strategy"
    validate_author_cards(catalog, card_root)
    payload: dict[str, bytes] = {}
    for module, profile in catalog["modules"].items():
        source = (ROOT / "official/raw/Promisory" / module).read_bytes().decode("utf-8")
        template = (ROOT / "adjusted/cloze/Promisory" / (module + ".tpl")).read_bytes().decode("utf-8")
        validate_classified_template(module, source, template, catalog)
        keys = [r["key"] for r in profile["parameters"] if r["decision"] == "dynamic"]
        if not keys:
            continue
        name = module.removesuffix(".per") + ".json"
        payload["strategy/" + name] = (card_root / name).read_bytes()
        payload["answers/" + name] = (json.dumps({key: None for key in keys}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    assets = {
        "README.md": "adjusted/cloze/CREATOR_START.md",
        "ANSWER_CONSTRAINTS.md": "adjusted/cloze/ANSWER_CONSTRAINTS.md",
        "adjusted/tools/query_creator_facts.py": "adjusted/tools/query_creator_facts.py",
        "tools/query_strategy_cards.py": "adjusted/tools/query_strategy_cards.py",
    }
    if set(catalog.get("author_assets", {})) != set(assets.values()):
        raise BoundaryError("reviewed author asset allowlist is missing or differs")
    for target, source in assets.items():
        raw = (ROOT / source).read_bytes()
        if hashlib.sha256(raw).hexdigest() != catalog["author_assets"][source]:
            raise BoundaryError("author asset changed after review: " + source)
        if target.endswith(".md"):
            validate_author_prose(raw.decode("utf-8"), target)
        payload[target] = raw
    for name in facts.FILES:
        raw = (facts.FACTS_ROOT / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != facts.EXPECTED_GIT_BLOBS[name]:
            raise BoundaryError("fact source hash mismatch: " + name)
        payload["adjusted/knowledge/facts/" + name] = raw
    if out.exists():
        raise BoundaryError("output already exists; choose a fresh author-input directory")
    count = sum(sum(r["decision"] == "dynamic" for r in p["parameters"]) for p in catalog["modules"].values())
    manifest = {"schema": "aoe2-strategy-author-input-v1", "dynamic_slots": count, "fixed_source_included": False, "official_answers_included": False, "fresh_author_context_required": True, "runtime": "Unverified", "files": {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}}
    # Prepare all bytes and checks before creating any output directory.
    out.mkdir(parents=True)
    try:
        for name, raw in payload.items():
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    except OSError:
        # Never overwrite an earlier package; leave any partial new output for inspection.
        raise
    return {"ok": True, "out": str(out), "files": len(payload) + 1, "dynamic_slots": count}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.out), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
