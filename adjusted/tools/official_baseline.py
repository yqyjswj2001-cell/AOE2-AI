"""Frozen official Promisory module set. Count comes from the files, not a literal."""
from __future__ import annotations

from pathlib import Path

OFFICIAL = Path(__file__).resolve().parents[2] / "official/raw/Promisory"


def official_module_names() -> list[str]:
    names = sorted(path.name for path in OFFICIAL.glob("*.per") if path.is_file())
    if not names:
        raise RuntimeError("official Promisory baseline is empty")
    return names


def official_module_count() -> int:
    return len(official_module_names())
