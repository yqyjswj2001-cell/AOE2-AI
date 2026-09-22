"""Public UI catalog from the frozen facts and the standard-edition allowlist."""
from pathlib import Path
import json

from civilizations import content_profile, eligible_rows

HERE = Path(__file__).resolve().parent
FACTS_FILE = HERE.parent / "knowledge/facts/civilizations/civilizations.standard53.compact.json"
ASSET_DIR = HERE / "web/assets/civilizations"


def _strings(value):
    """Keep a missing facts field empty rather than supply invented content."""
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def catalog():
    """Return eligible names, unmodified Chinese facts, and local shield URLs."""
    facts = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    rows = []
    for item in facts["civilizations"]:
        details = item.get("official_facts_zh") or {}
        identity = item["internal_name"]
        rows.append({
            "id": identity,
            "name": item.get("display_name_zh", ""),
            "name_en": item.get("display_name_en", ""),
            "icon": "/assets/civilizations/" + identity + ".png",
            "description": details.get("archetype", ""),
            "bonuses": _strings(details.get("civilization_bonuses")),
            "unique_units": _strings(details.get("unique_units")),
            "unique_techs": _strings(details.get("unique_technologies")),
            "team_bonus": _strings(details.get("team_bonus")),
        })
    selected = eligible_rows(rows)
    for item in selected:
        if not (ASSET_DIR / (item["id"] + ".png")).is_file():
            raise ValueError("Missing civilization shield: " + item["id"])
    return {
        "civilizations": selected,
        "content_profile": content_profile(),
        "source": {
            "kind": "frozen_local_game_facts",
            "file": "adjusted/knowledge/facts/civilizations/civilizations.standard53.compact.json",
            "pack_id": facts.get("pack_id"),
            "game_version": facts.get("game_version"),
            "generated_at": facts.get("generated_at"),
            "note": "文明资料来自随仓库冻结的游戏资料，不代表最新补丁或实战强度。",
        },
        "artwork": {
            "manifest": "adjusted/web-author/web/assets/civilizations/manifest.json",
            "copyright": "Age of Empires II © Microsoft Corporation.",
            "note": "游戏美术不属于本仓库 MIT 许可；本项目不由 Microsoft 认可或关联。",
        },
    }
