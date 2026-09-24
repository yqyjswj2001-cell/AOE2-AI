#!/usr/bin/env python3
"""Capture a verified DE loader once, then package without a local game install."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import shutil

from installable_ai import InstallableAIError, find_promide, parse_promide, sha256, _module_name

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT / "adjusted/install-template"
BASELINE = ROOT / "official/raw/Promisory"
SCHEMA = "aoe2-install-template-v1"


def _safe(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise InstallableAIError("Template paths cannot use symlinks or junctions")
    return path


def baseline_hashes(baseline):
    baseline = _safe(baseline)
    files = sorted(baseline.glob("*.per"))
    if len(files) != 36 or len({p.name.casefold() for p in files}) != 36:
        raise InstallableAIError("Template requires the complete 36-module official baseline")
    return {p.name: sha256(_safe(p).read_bytes()) for p in files}


def load_template(directory, baseline):
    directory = _safe(directory)
    manifest_path = _safe(directory / "manifest.json")
    doc = json.loads(manifest_path.read_bytes())
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("status") != "READY":
        raise InstallableAIError("Install template is not ready; capture the real DE loader first")
    hashes = baseline_hashes(baseline)
    if doc.get("baseline_sha256") != hashes:
        raise InstallableAIError("Install template baseline differs from official/raw; recapture matching game files")
    raw = _safe(directory / "PromiDE.per2").read_bytes()
    if sha256(raw) != doc.get("entrypoint_sha256"):
        raise InstallableAIError("Install template loader hash differs")
    text, targets = parse_promide(raw)
    names = {name.casefold() for name in hashes}
    if any(_module_name(target).casefold() not in names for target in targets):
        raise InstallableAIError("Install template loads a module outside the frozen baseline")
    if doc.get("loads") != targets:
        raise InstallableAIError("Install template load order differs")
    if _safe(directory / "marker.ai").read_bytes() != b"":
        raise InstallableAIError("Install template AI marker must be empty")
    return raw, text, targets


def template_ready(directory):
    path = _safe(Path(directory) / "manifest.json")
    if not path.is_file():
        return False
    # Corruption is an error, never an excuse to bypass the registered template.
    doc = json.loads(path.read_bytes())
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("status") not in {"READY", "MISSING_ENTRYPOINT"}:
        raise InstallableAIError("Invalid install template manifest")
    return doc["status"] == "READY"


def check_installed(promide, baseline, game_promisory=None):
    promide = _safe(promide)
    raw = promide.read_bytes()
    text, targets = parse_promide(raw)
    hashes = baseline_hashes(baseline)
    names = {name.casefold(): name for name in hashes}
    if any(_module_name(target).casefold() not in names for target in targets):
        raise InstallableAIError("DE loader references modules outside the repository baseline")
    game = _safe(game_promisory if game_promisory is not None else promide.parents[2] / "ai/Promisory")
    for name, expected in hashes.items():
        path = _safe(game / name)
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            raise InstallableAIError("Installed DE baseline differs from official/raw: " + name)
    return raw, text, targets, hashes


def capture(promide, output=DEFAULT_TEMPLATE, baseline=BASELINE, *, game_promisory=None):
    """Only explicit maintenance calls write the template; normal authoring never does."""
    output = _safe(output)
    if output.exists() and any(p.name not in {"README.md", "manifest.json"} for p in output.iterdir()):
        raise InstallableAIError("Template already contains files; use a fresh output directory")
    if output.exists() and template_ready(output):
        raise InstallableAIError("A ready template cannot be overwritten; use a fresh output directory")
    raw, text, targets, hashes = check_installed(promide, baseline, game_promisory)
    doc = {"schema": SCHEMA, "status": "READY", "source": "verified-installed-DE-files",
           "entrypoint_sha256": sha256(raw), "baseline_sha256": hashes, "loads": targets,
           "runtime": {"parser_load": "Unverified", "full_game": "Unverified"}}
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".capture-", dir=output.parent))
    try:
        (work / "PromiDE.per2").write_bytes(raw)
        (work / "marker.ai").write_bytes(b"")
        (work / "manifest.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        load_template(work, baseline)
        output.mkdir(exist_ok=True)
        for name in ("PromiDE.per2", "marker.ai", "manifest.json"):
            os.replace(work / name, _safe(output / name))  # manifest last: never advertise an incomplete capture
    finally:
        shutil.rmtree(work)
    return {"ok": True, "template": str(output), "entrypoint_sha256": sha256(raw), "modules": len(hashes)}


def preflight(baseline=BASELINE, *, template_dir=DEFAULT_TEMPLATE, environ=None, home=None):
    env = os.environ if environ is None else environ
    try:
        explicit_game = bool(env.get("AOE2DE_PROMIDE_PER2") or env.get("AOE2DE_ROOT"))
        if not explicit_game and template_ready(template_dir):
            raw, _, targets = load_template(template_dir, baseline)
            kind = "repository_template"
        else:
            promide = find_promide(environ=env, home=home)
            raw, _, targets, _ = check_installed(promide, baseline)
            kind = "installed_game"
        return {"ready": True, "source": kind, "entrypoint_sha256": sha256(raw),
                "load_count": len(targets), "parser_load": "Unverified"}
    except (OSError, ValueError, KeyError, IndexError) as exc:
        return {"ready": False, "source": "unavailable", "code": "INSTALL_TEMPLATE_UNAVAILABLE",
                "message": str(exc), "parameter_authoring_available": True,
                "instruction": "Prepare a matching real DE loader once; do not guess loads or repeatedly scan disks"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="Real PromiDE.per2 to verify and copy")
    parser.add_argument("--game-promisory", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args(argv)
    try:
        result = capture(args.capture, args.out, game_promisory=args.game_promisory) if args.capture else preflight(template_dir=args.out)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") or result.get("ready") else 2
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)); return 2


if __name__ == "__main__":
    raise SystemExit(main())
