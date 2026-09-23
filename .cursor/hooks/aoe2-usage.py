#!/usr/bin/env python3
"""Privacy-minimized Cursor hook for AOE2-AI usage attribution."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "adjusted/web-author"))

def main():
    try:
        from cursor_admin_usage import record_hook_payload
        payload = json.load(sys.stdin)
        record_hook_payload(payload, ROOT)
    except Exception:
        # Usage observability must never block the Cursor agent loop.
        pass
    sys.stdout.write("{}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
