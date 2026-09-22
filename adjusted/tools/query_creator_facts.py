#!/usr/bin/env python3
"""Read the pinned creator facts without network access or AI source reads.

Adapted conceptually from creator-kit/current/write/tools/facts_core.py in
yqyjswj2001-cell/aoe2-ai-studio at bb36e88dd2a5d4ea1841da2f647753106bf7421b.
This is a rewritten local JSON CLI, not a byte-for-byte copy of that tool.
Only the nine allowlisted JSON files below are opened; paths in their contents
are provenance strings and are never followed. No answer or strategy is written.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys


REPOSITORY = "yqyjswj2001-cell/aoe2-ai-studio"
REF = "bb36e88dd2a5d4ea1841da2f647753106bf7421b"
REMOTE_FACTS = "creator-kit/current/write/facts/"
ADJUSTED_ROOT = Path(__file__).resolve().parents[1]
FACTS_ROOT = ADJUSTED_ROOT / "knowledge" / "facts"
UNIT = "economy/单位与建筑基础数据.json"
TECHNOLOGY = "economy/科技基础数据.json"
GATHERING = "economy/村民基础采集速率.json"
ECONOMY_SOURCE = "economy/source-manifest.json"
CIVILIZATION = "civilizations/civilizations.standard53.compact.json"
PUBLIC_API = "public-api.json"
API_SHAPES = "api/api-shapes.json"
API_OVERRIDES = "api/developer-api-overrides.json"
CONSTANTS = "api/developer-constant-reference.json"
FILES = (
    UNIT, TECHNOLOGY, GATHERING, ECONOMY_SOURCE, CIVILIZATION,
    PUBLIC_API, API_SHAPES, API_OVERRIDES, CONSTANTS,
)
# Git blob IDs recorded from the pinned repository/ref, not bare file SHA1.
EXPECTED_GIT_BLOBS = {
    UNIT: "4417f6d851ee0b3eb1fd4d08371c5472f2039f82",
    TECHNOLOGY: "812f6beba4aff49b93714e8923184ac3fcd90807",
    GATHERING: "163f9ba171e9f5d0ddd4587dd12d14e8d2a44f50",
    ECONOMY_SOURCE: "49d77277411609dfb2956a221c0fa141a2dc988a",
    CIVILIZATION: "cc26b0d0c3b528352f09fd85b1f9a3255f5afc18",
    PUBLIC_API: "4980d224b8b67a94861d55e97648be9ff31cf055",
    API_SHAPES: "c4eb594fa555bc437622ef4e08e27e4b2f927e5a",
    API_OVERRIDES: "9f2bd32f2dca387021be751db32de480bcedcab4",
    CONSTANTS: "121d59c23d0c477c28bc7a16f2fb546b4d226b2f",
}
BOUNDARY = {
    "runtime_verified": False,
    "runtime_validation": "Unverified",
    "effectiveness_validation": "Unverified",
    "engine_acceptance": "Unverified",
    "current_session_measurement": False,
    "catalog_is_complete": False,
    "notes_zh": [
        "这是固定来源资料的只读查询，资料值不是本次游戏实测。",
        "经济数值为资料记录的基础值；文明、科技、地图和实际效率修正须看记录范围。",
        "名称、DAT ID 和 internal_name 不自动等同于 PER 标识符，不推导别名。",
        "API 与常量收录不证明当前 DE 接受；UNKNOWN 仅表示资料未收录，不表示非法。",
        "记录中的空值保持为空，不补数值、不生成填空答案、不执行策略。",
    ],
}
IDENTITY_FIELDS = {
    UNIT: ("id", "name_zh", "name_en", "internal_name"),
    TECHNOLOGY: ("id", "name_zh", "name_en", "internal_name"),
    CIVILIZATION: ("display_name_zh", "display_name_en", "internal_name"),
    GATHERING: ("key", "label_zh"),
}


class QueryError(Exception):
    def __init__(self, code: str, message: str, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.path = path


def envelope(command: str | None, query: str | None = None) -> dict:
    return {
        "status": "OK",
        "command": command,
        "query": query,
        "provenance": {"repository": REPOSITORY, "ref": REF, "remote_blob_verified": False},
        "truth_boundary": BOUNDARY,
        "sources": [],
    }


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise QueryError("USAGE_ERROR", message)

    def print_help(self, file=None) -> None:
        output = envelope("help")
        output["usage"] = self.format_help()
        output["exit_codes"] = {
            "0": "查询成功或帮助",
            "2": "参数错误、资料缺失或损坏",
            "3": "UNKNOWN 或 AMBIGUOUS；不表示游戏命令非法",
        }
        emit(output)


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contains a duplicate key: " + key)
        result[key] = value
    return result


def reject_nonfinite(value: str):
    raise ValueError("Non-finite JSON number: " + value)


def require_mapping(value, path: str, label: str) -> dict:
    if not isinstance(value, dict):
        raise QueryError("INVALID_DATA", label + " 必须是 JSON 对象", path)
    return value


def require_table(document: dict, key: str, path: str) -> dict:
    table = require_mapping(document.get(key), path, key)
    if any(not isinstance(value, dict) for value in table.values()):
        raise QueryError("INVALID_DATA", key + " 的每条记录必须是对象", path)
    return table


def require_rows(document: dict, key: str, path: str) -> list[dict]:
    rows = document.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise QueryError("INVALID_DATA", key + " 必须是对象数组", path)
    if "item_count" in document:
        count = document["item_count"]
        if type(count) is not int or count != len(rows):
            raise QueryError("INVALID_DATA", "item_count 与实际记录数不一致", path)
    return rows


class Catalog:
    def __init__(self):
        self.documents = {}
        self.hashes = {}
        self.blob_hashes = {}
        for relative in FILES:
            path = FACTS_ROOT / relative
            # Reject redirection through symlinks/junctions, including the facts root.
            if path.resolve() != path:
                raise QueryError("PATH_BOUNDARY_ERROR", "事实文件不能通过链接重定向", relative)
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise QueryError(
                    "DATA_READ_ERROR", "无法读取必需资料: " + str(exc), relative
                ) from exc
            git_header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
            actual_blob = hashlib.sha1(git_header + raw).hexdigest()
            expected_blob = EXPECTED_GIT_BLOBS[relative]
            if actual_blob != expected_blob:
                raise QueryError(
                    "SOURCE_HASH_MISMATCH",
                    "本地资料与固定提交不一致: expected Git blob "
                    + expected_blob + ", actual " + actual_blob,
                    relative,
                )
            self.blob_hashes[relative] = actual_blob
            try:
                document = json.loads(
                    raw.decode("utf-8-sig"),
                    object_pairs_hook=unique_object,
                    parse_constant=reject_nonfinite,
                )
            except (UnicodeError, ValueError) as exc:
                raise QueryError(
                    "INVALID_JSON", "必需资料不是有效 UTF-8 JSON: " + str(exc), relative
                ) from exc
            self.documents[relative] = require_mapping(document, relative, "顶层")
            self.hashes[relative] = hashlib.sha256(raw).hexdigest()
        for relative in (UNIT, TECHNOLOGY, GATHERING):
            doc = self.documents[relative]
            require_mapping(doc.get("meta"), relative, "meta")
            require_rows(doc, "items", relative)
        civ = self.documents[CIVILIZATION]
        rows = require_rows(civ, "civilizations", CIVILIZATION)
        pool = require_mapping(civ.get("selection_pool"), CIVILIZATION, "selection_pool")
        if type(pool.get("civilization_count")) is not int or pool["civilization_count"] != len(rows):
            raise QueryError("INVALID_DATA", "文明计数与实际记录数不一致", CIVILIZATION)
        for relative in (PUBLIC_API, API_SHAPES, API_OVERRIDES):
            require_table(self.documents[relative], "commands", relative)
        require_table(self.documents[CONSTANTS], "constants", CONSTANTS)
        require_table(self.documents[API_OVERRIDES], "documented_symbol_usages", API_OVERRIDES)
        selected = require_mapping(
            self.documents[PUBLIC_API].get("selected_constant_reference"),
            PUBLIC_API, "selected_constant_reference",
        )
        require_table(selected, "constants", PUBLIC_API)

    def source(self, relative: str) -> dict:
        document = self.documents[relative]
        version_meta = document.get("meta", document)
        data_keys = {
            "items", "civilizations", "commands", "constants",
            "documented_symbol_usages", "selected_constant_reference",
        }
        return {
            "repository": REPOSITORY,
            "ref": REF,
            "path": REMOTE_FACTS + relative,
            "local_path": str(FACTS_ROOT / relative),
            "local_sha256": self.hashes[relative],
            "git_blob_sha1": self.blob_hashes[relative],
            "remote_blob_verified": True,
            "data_version": version_meta.get("game_version"),
            "dat_version": version_meta.get("dat_version"),
            "recorded_metadata": {
                key: value for key, value in document.items() if key not in data_keys
            },
            "runtime_verified": False,
            "effectiveness_validation": "Unverified",
        }

    def rows(self, relative: str) -> list[dict]:
        key = "civilizations" if relative == CIVILIZATION else "items"
        return self.documents[relative][key]

    def sources_for(self, *paths: str) -> list[dict]:
        return [self.source(path) for path in dict.fromkeys(paths)]


def normalized(value) -> str:
    return str(value).strip().casefold()


def identities(row: dict, fields: tuple[str, ...]) -> list[str]:
    return [
        normalized(row[field]) for field in fields
        if field in row and row[field] is not None and str(row[field]).strip()
    ]


def label(row: dict, fields: tuple[str, ...]) -> dict:
    return {key: row[key] for key in fields if key in row}


def suggestions(query: str, records: list[dict], fields: tuple[str, ...]) -> list[dict]:
    if not query:
        return []
    ranked = []
    for index, row in enumerate(records):
        names = identities(row, fields)
        if not names:
            continue
        score = max(
            1.0 if query in name else difflib.SequenceMatcher(None, query, name).ratio()
            for name in names
        )
        if score >= 0.55:
            ranked.append((-score, index, row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [label(row, fields) for _, _, row in ranked[:5]]


def query_entity(catalog: Catalog, command: str, query: str, relative: str) -> dict:
    result = envelope(command, query)
    result["sources"] = catalog.sources_for(
        relative, *([ECONOMY_SOURCE] if relative in (UNIT, TECHNOLOGY, GATHERING) else [])
    )
    records = catalog.rows(relative)
    fields = IDENTITY_FIELDS[relative]
    folded = normalized(query)
    matches = [row for row in records if folded in identities(row, fields)]
    result["match_policy"] = "仅 ID 或记录中的中英文/internal 名称精确匹配；忽略大小写和首尾空格。"
    if len(matches) == 1:
        result["status"] = "FOUND"
        result["match_type"] = "exact"
        result["record"] = matches[0]
    elif matches:
        result["status"] = "AMBIGUOUS"
        result["match_type"] = "ambiguous_exact"
        result["matches"] = matches
        result["message_zh"] = "存在多条同名记录；未替用户选择。请使用记录中的 ID。"
    else:
        result["status"] = "UNKNOWN"
        result["match_type"] = "none"
        result["record"] = None
        result["suggestions_not_matches"] = suggestions(folded, records, fields)
        result["message_zh"] = "资料中没有精确命中；候选不是查询结果或 PER 标识符证明。"
    return result


def exact_entry(table: dict, query: str):
    keys = [key for key in table if normalized(key) == normalized(query)]
    if len(keys) > 1:
        raise QueryError("INVALID_DATA", "资料含大小写冲突的同名 API/常量")
    return table[keys[0]] if keys else None


def query_command(catalog: Catalog, query: str) -> dict:
    paths = (PUBLIC_API, API_SHAPES, API_OVERRIDES)
    tables = [catalog.documents[path]["commands"] for path in paths]
    matches = [exact_entry(table, query) for table in tables]
    result = envelope("command", query)
    result["sources"] = catalog.sources_for(*paths)
    result.update({
        "status": "FOUND" if any(item is not None for item in matches) else "UNKNOWN",
        "match_type": "exact" if any(item is not None for item in matches) else "none",
        "public_api_metadata": matches[0],
        "api_shapes_metadata": matches[1],
        "reviewed_developer_override": matches[2],
        "runtime_verified": False,
        "notes_zh": [
            "各栏保留对应资料原貌；public-api 可能已合并审核修正，不代表修正前的形状。",
            "api_shapes_metadata 为 null 表示该文件未收录，不能重建或猜测原始参数。",
            "审核修正仅覆盖其明确记载范围；不能扩展为其他运算符或当前 DE 实机通过。",
        ],
    })
    if result["status"] == "UNKNOWN":
        names = sorted(set().union(*(set(table) for table in tables)))
        result["suggestions_not_matches"] = suggestions(
            normalized(query), [{"name": name} for name in names], ("name",)
        )
        result["message_zh"] = "API 资料未收录该命令；不表示命令非法。"
    return result


def query_constant(catalog: Catalog, query: str) -> dict:
    selected = catalog.documents[PUBLIC_API]["selected_constant_reference"]
    developer = catalog.documents[CONSTANTS]["constants"]
    usages = catalog.documents[API_OVERRIDES]["documented_symbol_usages"]
    tables = (developer, selected["constants"], usages)
    matches = [exact_entry(table, query) for table in tables]
    found = any(item is not None for item in matches)
    result = envelope("constant", query)
    result["sources"] = catalog.sources_for(CONSTANTS, PUBLIC_API, API_OVERRIDES)
    recorded_values = [
        item["value"] for item in matches[:2] if item is not None and "value" in item
    ]
    result.update({
        "status": "FOUND" if found else "UNKNOWN",
        "match_type": "exact" if found else "none",
        "developer_constant_reference": matches[0],
        "public_api_selected_constant_reference": matches[1],
        "public_api_selected_reference_metadata": {
            key: value for key, value in selected.items() if key != "constants"
        },
        "documented_symbol_usage": matches[2],
        "numeric_value_status": (
            "CONFLICT" if len({json.dumps(value) for value in recorded_values}) > 1
            else "RECORDED" if any(value is not None for value in recorded_values)
            else "UNKNOWN"
        ),
        "runtime_verified": False,
        "message_zh": "仅原样返回已记录常量；文档用法没有数值时，数值仍为 UNKNOWN。",
    })
    if not found:
        names = sorted(set().union(*(set(table) for table in tables)))
        result["suggestions_not_matches"] = suggestions(
            normalized(query), [{"name": name} for name in names], ("name",)
        )
        result["message_zh"] = "常量资料未收录该名称；不表示该名称非法，也不推导数值。"
    return result


def info(catalog: Catalog) -> dict:
    result = envelope("info")
    result["facts_root"] = str(FACTS_ROOT)
    result["sources"] = catalog.sources_for(*FILES)
    result["counts"] = {
        "units_and_buildings": len(catalog.rows(UNIT)),
        "technologies": len(catalog.rows(TECHNOLOGY)),
        "gathering_records": len(catalog.rows(GATHERING)),
        "civilizations": len(catalog.rows(CIVILIZATION)),
        "public_api_commands": len(catalog.documents[PUBLIC_API]["commands"]),
        "api_shapes": len(catalog.documents[API_SHAPES]["commands"]),
        "reviewed_developer_overrides": len(catalog.documents[API_OVERRIDES]["commands"]),
        "developer_constants": len(catalog.documents[CONSTANTS]["constants"]),
        "documented_symbol_usages": len(catalog.documents[API_OVERRIDES]["documented_symbol_usages"]),
    }
    result["scope_zh"] = (
        "本地冻结子集，不是全部官方事实。版本只取各文件自身的 game_version；"
        "API 未记载游戏版本时 data_version 为 null。来源清单中的路径仅作说明，不读取。"
    )
    return result


def parser() -> JsonParser:
    root = JsonParser(description="只读查询固定 creator-knowledge；全部输出为 JSON。")
    sub = root.add_subparsers(dest="command", required=True, parser_class=JsonParser)
    for name in ("info", "civilizations"):
        sub.add_parser(name)
    for name in ("unit", "technology", "civilization", "command", "constant"):
        child = sub.add_parser(name)
        child.add_argument("query", help="记录中的精确名称；unit/technology 也接受真实 ID")
    sub.add_parser("gathering").add_argument("query", nargs="?", help="可选采集记录 key 或中文标签")
    return root


def main(argv: list[str] | None = None) -> int:
    # Make Chinese JSON consistent when redirected on Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = None
    try:
        args = parser().parse_args(argv)
        query = getattr(args, "query", None)
        if query is not None and not query.strip():
            raise QueryError("USAGE_ERROR", "查询词不能为空")
        catalog = Catalog()
        if args.command == "info":
            result = info(catalog)
        elif args.command == "civilizations":
            result = envelope(args.command)
            result["sources"] = catalog.sources_for(CIVILIZATION)
            fields = IDENTITY_FIELDS[CIVILIZATION]
            result["civilizations"] = [label(row, fields) for row in catalog.rows(CIVILIZATION)]
        elif args.command == "gathering" and query is None:
            result = envelope(args.command)
            result["sources"] = catalog.sources_for(GATHERING, ECONOMY_SOURCE)
            result["items"] = catalog.rows(GATHERING)
        elif args.command == "command":
            result = query_command(catalog, query)
        elif args.command == "constant":
            result = query_constant(catalog, query)
        else:
            path = {
                "unit": UNIT, "technology": TECHNOLOGY,
                "civilization": CIVILIZATION, "gathering": GATHERING,
            }[args.command]
            result = query_entity(catalog, args.command, query, path)
        result["provenance"]["remote_blob_verified"] = True
        emit(result)
        return 3 if result["status"] in ("UNKNOWN", "AMBIGUOUS") else 0
    except QueryError as exc:
        result = envelope(getattr(args, "command", None), getattr(args, "query", None))
        result["status"] = "ERROR"
        result["error"] = {"code": exc.code, "message": str(exc), "path": exc.path}
        emit(result)
        return 2
    except (OSError, UnicodeError, ValueError) as exc:
        result = envelope(getattr(args, "command", None), getattr(args, "query", None))
        result["status"] = "ERROR"
        result["error"] = {"code": "QUERY_ERROR", "message": str(exc)}
        emit(result)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
