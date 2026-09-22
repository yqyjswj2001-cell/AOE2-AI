"""Edition eligibility and varied recommendations; reads project metadata only."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
PROFILE_FILE = HERE / "standard-edition.json"
PROJECTS = HERE.parents[1] / "adjusted/.local/author-projects"
POLICY_ID = "distinct-playstyles-v1"
GUIDANCE = [
    "用文明特色塑造一套可辨认、能落地的打法；胜负能力与观赏性共同考虑。",
    "不要把熟悉程度、资料好算或通用加成当作选文明的加分项。",
    "特殊资源、单位或经济机制是创作素材：先查本包事实，再用现有参数表达；不要求重写机制，也不要求一次用尽所有特色。",
    "先比较推荐候选中三种不同文明的打法切入点，选最适合本场条件和偏好的一个；相近时优先近期较少选择的文明。",
    "推荐不是禁选表；全部合资格文明都可选，推荐外选择也须有具体战术理由，不能只说熟悉或稳妥。",
    "用一两句说明所选文明的关键特色及其怎样影响资源或兵力安排；这是选择依据，不生成简报、不等待用户再次批准。",
    "真实资料缺口须核实或保留未知；不能编造加成、强度、可执行能力或历史出场记录。"
]

def _profile():
    value = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    allowed = value["allowed_internal_names"]
    excluded = [c for group in value["excluded_by_required_dlc"].values() for c in group]
    if len(allowed) != 42 or len(set(allowed)) != 42 or set(allowed) & set(excluded):
        raise ValueError("Standard-edition civilization policy is invalid")
    return value

def content_profile():
    value = _profile()
    return {key: value[key] for key in (
        "profile_id", "label", "edition", "available_count", "catalog_count",
        "based_on", "ownership_verified", "verified_at")}

def eligible_rows(rows):
    allowed = _profile()["allowed_internal_names"]
    mapped = {row["id"]: row for row in rows}
    missing = set(allowed) - set(mapped)
    if missing or len(mapped) != len(rows):
        raise ValueError("Civilization catalog does not match the allowed standard-edition names")
    return [dict(mapped[key]) for key in allowed]

def _recent(history_root, current_id, allowed):
    root = Path(history_root)
    if not root.exists():
        return [], False, 0
    if root.resolve() != root.absolute():
        raise ValueError("History root cannot redirect through a link")
    records, skipped, identities = [], 0, set()
    for path in root.glob("*/project.json"):
        try:
            if path.resolve() != path.absolute() or path.stat().st_size > 1024 * 1024:
                skipped += 1
                continue
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
            identity = doc.get("project_id")
            if not identity or identity == current_id or identity in identities:
                continue
            request = doc.get("request") or {}
            civilization = request.get("civilization")
            if civilization not in allowed:
                continue
            choice = doc.get("civilization_choice") or {}
            stamp = choice.get("selected_at", path.stat().st_mtime)
            if not isinstance(stamp, (int, float)) or isinstance(stamp, bool) or not math.isfinite(stamp):
                stamp = path.stat().st_mtime
            records.append((stamp, identity, civilization))
            identities.add(identity)
        except (OSError, ValueError, TypeError, AttributeError):
            skipped += 1
    return sorted(records, reverse=True)[:42], True, skipped

def selection_context(rows, project_id, history_root=PROJECTS):
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("A stable project identity is required")
    ids = [row["id"] for row in rows]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Eligible civilization rows must be nonempty and unique")
    history, available, skipped = _recent(history_root, project_id, set(ids))
    counts = Counter(row[2] for row in history)
    def order(row):
        tie = hashlib.sha256((POLICY_ID + ":" + project_id + ":" + row["id"]).encode()).hexdigest()
        return counts[row["id"]], tie
    ordered = sorted(rows, key=order)
    return {
        "policy_id": POLICY_ID,
        "eligible_ids": ids,
        "suggested": [{"id": row["id"], "name": row["name"], "recent_selections": counts[row["id"]]}
                      for row in ordered[:6]],
        "history_scope": "仅本仓库网页项目最近42次已确定文明的创作记录；不是游戏出场率或胜率",
        "history_available": available,
        "observed_selections": len(history),
        "skipped_metadata": skipped,
        "selection_method": "prefer_less_used_then_project_seeded_order",
        "choice_guidance": GUIDANCE,
    }
