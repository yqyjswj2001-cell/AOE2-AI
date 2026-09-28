"""Standard-edition eligibility and unrestricted AI civilization choice."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
PROFILE_FILE = HERE / "standard-edition.json"
POLICY_ID = "free-choice-v1"
GUIDANCE = [
    "根据本轮游戏模式、competition profile、地图条件和你想设计的打法，从全部合资格文明中自由选择。",
    "系统不提供推荐候选、不按历史使用次数排序，也不要求先比较固定数量的文明。",
    "不需要为了形式把全部文明逐个深度研究；可以先形成打法方向，再按需查询你主动考虑的文明事实。",
    "文明特色是创作素材：用事实核对资源、兵种和特殊机制，再用现有动态参数表达。",
    "不要因为更熟悉、资料更好算或实现更省事就默认优先某文明；也不要为了追求冷门而刻意回避合适文明。",
    "最终用一两句说明所选文明为什么适合本轮条件和你的打法；这是选择依据，不生成简报、不等待用户再次批准。",
    "真实资料缺口须核实或保留未知；不能编造加成、强度或可执行能力。"
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

def selection_context(rows, project_id, history_root=None):
    """Return the full eligible pool without recommendations or history-based bias.

    history_root is retained only for call-site compatibility and is deliberately ignored.
    """
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("A stable project identity is required")
    ids = [row["id"] for row in rows]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Eligible civilization rows must be nonempty and unique")
    return {
        "policy_id": POLICY_ID,
        "eligible_ids": ids,
        "selection_method": "free_choice_from_full_eligible_pool",
        "choice_guidance": GUIDANCE,
    }
