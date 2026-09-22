#!/usr/bin/env python3
"""Query only isolated strategy cards; never read PER files or write answers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

DEFAULT_CARDS = Path(__file__).resolve().parents[1] / "strategy"
DOCUMENT_FIELDS = frozenset({"module", "kind", "runtime", "parameters"})
CARD_FIELDS = frozenset({"key", "category", "meaning", "unit", "context", "effect", "group_id", "constraints_note"})
SEARCH_FIELDS = ("key", "category", "meaning", "unit", "context", "effect", "group_id")
MODULE_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.per)?\Z")
KEY_NAME = re.compile(r"[A-Z0-9_]+\Z")
SEARCH_LIMIT = 20


class QueryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise QueryError("invalid_arguments", message)


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise QueryError("invalid_cards", "JSON contains a duplicate field")
        obj[key] = value
    return obj


def load_cards(directory: Path) -> list[dict]:
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise QueryError("invalid_cards_directory", "cards directory is not a directory")
    documents = []
    seen_modules: set[str] = set()
    seen_keys: set[str] = set()
    # No recursion and no content-derived paths. Resolve links before reading.
    for path in sorted(root.glob("*.json"), key=lambda item: item.name.casefold()):
        resolved = path.resolve(strict=True)
        if resolved.parent != root or resolved.suffix.lower() != ".json" or not resolved.is_file():
            raise QueryError("invalid_cards_path", "card files must stay directly inside the selected cards directory")
        doc = json.loads(resolved.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)
        if not isinstance(doc, dict) or set(doc) != DOCUMENT_FIELDS:
            raise QueryError("invalid_cards", f"{path.name}: document fields differ from the author-card schema")
        if doc["kind"] != "strategy_decisions_only" or doc["runtime"] != "Unverified":
            raise QueryError("invalid_cards", f"{path.name}: not an unverified strategy-decisions document")
        module = doc["module"]
        if not isinstance(module, str) or not MODULE_NAME.fullmatch(module) or not module.endswith(".per"):
            raise QueryError("invalid_cards", f"{path.name}: invalid module name")
        if module.casefold() in seen_modules:
            raise QueryError("invalid_cards", "duplicate module in cards directory")
        seen_modules.add(module.casefold())
        if not isinstance(doc["parameters"], list):
            raise QueryError("invalid_cards", f"{path.name}: parameters must be an array")
        for card in doc["parameters"]:
            if not isinstance(card, dict) or set(card) != CARD_FIELDS:
                raise QueryError("invalid_cards", f"{path.name}: parameter fields differ from the author-card schema")
            if not all(isinstance(card[field], str) for field in CARD_FIELDS):
                raise QueryError("invalid_cards", f"{path.name}: parameter fields must be strings")
            if any(not card[field].strip() for field in CARD_FIELDS - {"constraints_note"}):
                raise QueryError("invalid_cards", f"{path.name}: required parameter description is empty")
            if not KEY_NAME.fullmatch(card["key"]) or card["key"] in seen_keys:
                raise QueryError("invalid_cards", "invalid or duplicate strategy key")
            seen_keys.add(card["key"])
        documents.append(doc)
    if not documents:
        raise QueryError("no_cards", "no author-card JSON files found")
    return documents


def summarize(values, limit: int, width: int) -> str:
    unique = list(dict.fromkeys(value.strip() for value in values))
    shown = [value if len(value) <= width else value[:width] + "…" for value in unique[:limit]]
    suffix = f"（另有 {len(unique) - limit} 项）" if len(unique) > limit else ""
    return "；".join(shown) + suffix


def query(args) -> dict:
    if args.groups and not args.module:
        raise QueryError("invalid_arguments", "--groups requires --module")
    if args.module and not MODULE_NAME.fullmatch(args.module):
        raise QueryError("invalid_arguments", "--module must be a module name, not a path")
    if args.search is not None and not args.search.strip():
        raise QueryError("invalid_arguments", "--search must not be empty")
    documents = load_cards(args.cards)
    if args.module:
        wanted = args.module.casefold()
        if not wanted.endswith(".per"):
            wanted += ".per"
        documents = [doc for doc in documents if doc["module"].casefold() == wanted]
        if not documents:
            raise QueryError("module_not_found", "no strategy cards for the requested module")
    base = {"ok": True, "runtime": "Unverified"}
    indexed = [(doc["module"], card) for doc in documents for card in doc["parameters"]]
    if args.key is not None:
        found = [(module, card) for module, card in indexed if card["key"] == args.key]
        if not found:
            raise QueryError("key_not_found", "strategy key not found in the selected cards")
        module, card = found[0]
        return {**base, "command": "key", "module": module, "parameter": card}
    if args.group is not None:
        found = [{"module": module, "parameter": card} for module, card in indexed if card["group_id"] == args.group]
        if not found:
            raise QueryError("group_not_found", "strategy group not found in the selected cards")
        return {**base, "command": "group", "group_id": args.group, "count": len(found), "parameters": found}
    if args.search is not None:
        text = args.search.strip().casefold()
        found = [card for module, card in indexed if text in " ".join([module] + [card[field] for field in SEARCH_FIELDS]).casefold()]
        return {**base, "command": "search", "query": args.search, "total_matches": len(found), "returned": min(len(found), SEARCH_LIMIT), "limit": SEARCH_LIMIT, "results": [{field: card[field] for field in ("key", "meaning", "group_id")} for card in found[:SEARCH_LIMIT]]}
    if args.groups:
        grouped: dict[str, list[dict]] = {}
        for _, card in indexed:
            grouped.setdefault(card["group_id"], []).append(card)
        result = [{"group_id": group, "count": len(cards), "meaning_summary": summarize((card["meaning"] for card in cards), 3, 90), "context_summary": summarize((card["context"] for card in cards), 2, 180), "keys": [card["key"] for card in cards]} for group, cards in grouped.items()]
        return {**base, "command": "groups", "module": documents[0]["module"], "total_groups": len(result), "groups": result}
    modules = [{"module": doc["module"], "parameters": len(doc["parameters"]), "groups": len({card["group_id"] for card in doc["parameters"]})} for doc in documents]
    return {**base, "command": "overview", "total_modules": len(modules), "total_parameters": len(indexed), "modules": modules}


def main(argv=None) -> int:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS, help="author-card directory (default: ../strategy)")
    parser.add_argument("--module", help="module field to match, with or without .per; never a path")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--groups", action="store_true", help="summarize groups for --module")
    operation.add_argument("--key", help="return one exact strategy card")
    operation.add_argument("--group", help="return every card in one exact group")
    operation.add_argument("--search", help="search card descriptions; return at most 20 short matches")
    try:
        result = query(parser.parse_args(argv))
    except QueryError as exc:
        result = {"ok": False, "error": {"code": exc.code, "message": str(exc)}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {"ok": False, "error": {"code": "cards_read_error", "message": str(exc)}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
