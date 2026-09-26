"""Persistent local registry for completed AOE2-AI works.

The registry accepts either verified current builds or older script packages.
Recognition is content-based: filenames + SHA-256 of a known baseline,
either the previous 36-module packages or the current frozen official set.
Unknown historical metadata stays unknown instead of being guessed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
from datetime import datetime, timezone
import zipfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "adjusted/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from official_baseline import official_module_count

REGISTRY_ROOT = ROOT / "adjusted/.local/ai-registry"
LEGACY_MODULE_COUNTS = frozenset({36})
REGISTRY_DB = REGISTRY_ROOT / "works.sqlite3"
PROJECTS = ROOT / "adjusted/.local/author-projects"
SCRIPT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
MAX_ZIP_FILES = 256
MAX_ZIP_MEMBER = 4 * 1024 * 1024
MAX_ZIP_TOTAL = 64 * 1024 * 1024
ALLOWED_METADATA = {
    "agent", "model", "mode", "civilization", "created_at", "notes",
}

ALLOWED_MATCH_FIELDS = {
    "played_at", "mode", "map", "civilization", "outcome", "result",
    "placement", "players", "duration_seconds", "score", "notes",
    "issues", "evidence", "opponents", "allies",
}
MATCH_OUTCOMES = {"win", "loss", "draw", "unknown"}


class RegistryError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _accepted_module_counts() -> set[int]:
    return set(LEGACY_MODULE_COUNTS) | {official_module_count()}


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _validate_script_name(value: str) -> str:
    if not isinstance(value, str) or not SCRIPT_NAME.fullmatch(value):
        raise RegistryError("Could not determine a valid script name")
    return value


def _module_fingerprint(modules: dict[str, bytes]) -> tuple[str, dict[str, str]]:
    if len(modules) not in _accepted_module_counts():
        raise RegistryError("A completed AOE2-AI work must use a known baseline module count")
    hashes = {}
    for name, data in modules.items():
        if not isinstance(name, str) or "/" in name or "\\" in name or not name.lower().endswith(".per"):
            raise RegistryError("Invalid PER module filename")
        key = name.casefold()
        if key in hashes:
            raise RegistryError("Duplicate PER module filename")
        hashes[key] = sha256(data)
    return sha256(canonical(hashes)), hashes


def _safe_zip_infos(archive: zipfile.ZipFile):
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_FILES:
        raise RegistryError("Package contains too many files")
    total = 0
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise RegistryError("Package contains an unsafe path")
        if info.file_size > MAX_ZIP_MEMBER:
            raise RegistryError("Package contains an unexpectedly large file")
        total += info.file_size
        if total > MAX_ZIP_TOTAL:
            raise RegistryError("Package is unexpectedly large")
    return infos


def _manifest_from_zip(archive: zipfile.ZipFile):
    names = {info.filename for info in archive.infolist() if not info.is_dir()}
    if "manifest.json" not in names:
        return None
    try:
        value = json.loads(archive.read("manifest.json"))
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise RegistryError("Package manifest.json is invalid") from exc
    return value if isinstance(value, dict) else None


def _recognize_share_zip(path: Path) -> dict | None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = _safe_zip_infos(archive)
            manifest = _manifest_from_zip(archive)
            if not manifest:
                return None
            script_name = manifest.get("script_name")
            if not isinstance(script_name, str) or not SCRIPT_NAME.fullmatch(script_name):
                return None
            if manifest.get("script_files") not in _accepted_module_counts():
                return None
            prefix = script_name + "/"
            modules = {}
            for info in infos:
                if info.is_dir() or not info.filename.lower().endswith(".per"):
                    continue
                if not info.filename.startswith(prefix):
                    raise RegistryError("Manifest package contains PER files outside its script directory")
                name = info.filename[len(prefix):]
                if not name or "/" in name or "\\" in name:
                    raise RegistryError("Manifest package contains an invalid PER path")
                modules[name] = archive.read(info)
            fingerprint, hashes = _module_fingerprint(modules)
            declared = manifest.get("files_sha256")
            if declared is not None:
                if not isinstance(declared, dict):
                    raise RegistryError("Package files_sha256 is invalid")
                normalized = {str(k).casefold(): str(v) for k, v in declared.items()}
                if normalized != hashes:
                    raise RegistryError("Package manifest hashes do not match the PER files")
            return {
                "script_name": script_name,
                "artifact_kind": "share_package",
                "module_fingerprint": fingerprint,
                "module_hashes": hashes,
                "module_files": len(modules),
                "manifest_schema": manifest.get("schema"),
                "manifest_present": True,
                "package_sha256": sha256(path.read_bytes()),
            }
    except zipfile.BadZipFile as exc:
        raise RegistryError("Artifact is not a valid ZIP package") from exc


def _recognize_installable_zip(path: Path) -> dict | None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = _safe_zip_infos(archive)
            names = {info.filename for info in infos if not info.is_dir()}
            markers = [name for name in names
                       if name.startswith("resources/_common/ai/") and name.lower().endswith(".ai")
                       and "/" not in name.removeprefix("resources/_common/ai/")]
            candidates = []
            for marker in markers:
                script_name = PurePosixPath(marker).stem
                if not SCRIPT_NAME.fullmatch(script_name):
                    continue
                entry = "resources/_common/ai/" + script_name + ".per"
                prefix = "resources/_common/ai/" + script_name + "/"
                per_infos = [info for info in infos if not info.is_dir()
                             and info.filename.startswith(prefix) and info.filename.lower().endswith(".per")]
                if entry in names and len(per_infos) in _accepted_module_counts():
                    candidates.append((script_name, per_infos))
            if len(candidates) != 1:
                return None
            script_name, per_infos = candidates[0]
            modules = {}
            for info in per_infos:
                name = PurePosixPath(info.filename).name
                modules[name] = archive.read(info)
            fingerprint, hashes = _module_fingerprint(modules)
            return {
                "script_name": script_name,
                "artifact_kind": "installable_zip",
                "module_fingerprint": fingerprint,
                "module_hashes": hashes,
                "module_files": len(modules),
                "manifest_schema": None,
                "manifest_present": False,
                "package_sha256": sha256(path.read_bytes()),
            }
    except zipfile.BadZipFile as exc:
        raise RegistryError("Artifact is not a valid ZIP package") from exc


def _recognize_plain_zip(path: Path) -> dict | None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = _safe_zip_infos(archive)
            per_infos = [i for i in infos if not i.is_dir() and i.filename.lower().endswith(".per")]
            if len(per_infos) not in _accepted_module_counts():
                return None
            parents = {str(PurePosixPath(i.filename).parent) for i in per_infos}
            if len(parents) != 1:
                return None
            parent = next(iter(parents))
            if parent in {"", "."}:
                script_name = path.stem
            else:
                script_name = PurePosixPath(parent).name
            if not SCRIPT_NAME.fullmatch(script_name):
                return None
            modules = {}
            for info in per_infos:
                name = PurePosixPath(info.filename).name
                modules[name] = archive.read(info)
            fingerprint, hashes = _module_fingerprint(modules)
            return {
                "script_name": script_name,
                "artifact_kind": "legacy_zip",
                "module_fingerprint": fingerprint,
                "module_hashes": hashes,
                "module_files": len(modules),
                "manifest_schema": None,
                "manifest_present": False,
                "package_sha256": sha256(path.read_bytes()),
            }
    except zipfile.BadZipFile as exc:
        raise RegistryError("Artifact is not a valid ZIP package") from exc


def _read_dir_modules(root: Path):
    if root.is_symlink():
        raise RegistryError("Symlinked script directories are not accepted")
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".per"]
    if len(files) not in _accepted_module_counts():
        return None
    if any(p.is_symlink() for p in files):
        raise RegistryError("Symlinked PER files are not accepted")
    return {p.name: p.read_bytes() for p in files}


def _recognize_directory(path: Path) -> dict | None:
    direct = _read_dir_modules(path)
    if direct is not None:
        script_name = _validate_script_name(path.name)
        fingerprint, hashes = _module_fingerprint(direct)
        return {
            "script_name": script_name,
            "artifact_kind": "raw_scripts",
            "module_fingerprint": fingerprint,
            "module_hashes": hashes,
            "module_files": len(direct),
            "manifest_schema": None,
            "manifest_present": False,
            "package_sha256": None,
        }

    candidates = []
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            modules = _read_dir_modules(child)
            if modules is not None and SCRIPT_NAME.fullmatch(child.name):
                candidates.append((child, modules))
    if len(candidates) == 1:
        child, modules = candidates[0]
        fingerprint, hashes = _module_fingerprint(modules)
        return {
            "script_name": child.name,
            "artifact_kind": "raw_scripts_parent",
            "module_fingerprint": fingerprint,
            "module_hashes": hashes,
            "module_files": len(modules),
            "manifest_schema": None,
            "manifest_present": False,
            "package_sha256": None,
        }

    ai_root = path / "resources/_common/ai"
    if ai_root.is_dir():
        names = []
        for marker in ai_root.glob("*.ai"):
            name = marker.stem
            if SCRIPT_NAME.fullmatch(name) and (ai_root / name).is_dir() and (ai_root / (name + ".per")).is_file():
                modules = _read_dir_modules(ai_root / name)
                if modules is not None:
                    names.append((name, modules))
        if len(names) == 1:
            name, modules = names[0]
            fingerprint, hashes = _module_fingerprint(modules)
            return {
                "script_name": name,
                "artifact_kind": "installable_layout",
                "module_fingerprint": fingerprint,
                "module_hashes": hashes,
                "module_files": len(modules),
                "manifest_schema": None,
                "manifest_present": False,
                "package_sha256": None,
            }
    return None


def recognize_artifact(value: str | Path) -> dict:
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise RegistryError("Artifact path does not exist")
    if path.is_symlink():
        raise RegistryError("Symlinked artifacts are not accepted")
    if path.is_file():
        if path.suffix.lower() != ".zip":
            raise RegistryError("Existing-work registration accepts a ZIP package or script directory")
        result = _recognize_share_zip(path) or _recognize_installable_zip(path) or _recognize_plain_zip(path)
    elif path.is_dir():
        result = _recognize_directory(path)
    else:
        result = None
    if not result:
        raise RegistryError("Could not recognize a completed AOE2-AI work")
    return {**result, "artifact_path": str(path)}


def _metadata(value: dict | None) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict) or any(key not in ALLOWED_METADATA for key in value):
        raise RegistryError("Metadata contains unsupported fields")
    out = {}
    for key, item in value.items():
        if item is None:
            continue
        if not isinstance(item, str) or len(item.strip()) > 2000:
            raise RegistryError("Metadata values must be short strings")
        if item.strip():
            out[key] = item.strip()
    return out


@contextmanager
def _connect(db_path: Path = REGISTRY_DB):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(
        """
        CREATE TABLE IF NOT EXISTS works(
          work_id TEXT PRIMARY KEY,
          module_fingerprint TEXT NOT NULL UNIQUE,
          script_name TEXT NOT NULL,
          first_registered_at TEXT NOT NULL,
          last_registered_at TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          project_id TEXT,
          build_id TEXT,
          mode TEXT,
          civilization TEXT,
          agent TEXT,
          model TEXT,
          created_at TEXT,
          notes TEXT,
          module_files INTEGER NOT NULL,
          metadata_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS artifacts(
          artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
          work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE,
          artifact_path TEXT NOT NULL,
          artifact_kind TEXT NOT NULL,
          package_sha256 TEXT,
          manifest_schema TEXT,
          manifest_present INTEGER NOT NULL,
          registered_at TEXT NOT NULL,
          UNIQUE(work_id, artifact_path)
        );
        CREATE TABLE IF NOT EXISTS matches(
          match_id TEXT PRIMARY KEY,
          work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE,
          recorded_at TEXT NOT NULL,
          played_at TEXT,
          mode TEXT,
          map_name TEXT,
          civilization TEXT,
          outcome TEXT,
          result_text TEXT,
          placement INTEGER,
          players INTEGER,
          duration_seconds INTEGER,
          score INTEGER,
          notes TEXT,
          issues_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          record_hash TEXT NOT NULL,
          record_json TEXT NOT NULL,
          UNIQUE(work_id, record_hash)
        );
        """
        )
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _work_id(fingerprint: str) -> str:
    return "work-" + fingerprint[:20]


def register_artifact(value: str | Path, *, metadata=None, source_kind="legacy_artifact",
                      project_id=None, build_id=None, db_path: Path = REGISTRY_DB) -> dict:
    found = recognize_artifact(value)
    meta = _metadata(metadata)
    now = utc_now()
    work_id = _work_id(found["module_fingerprint"])
    with _connect(db_path) as con:
        row = con.execute("SELECT work_id, script_name FROM works WHERE module_fingerprint=?",
                          (found["module_fingerprint"],)).fetchone()
        duplicate = row is not None
        if row is not None and row[1] != found["script_name"]:
            # Same modules may be copied under a different name; preserve the original identity,
            # but never silently rewrite the canonical registered name.
            canonical_name = row[1]
        else:
            canonical_name = found["script_name"]
        values = {
            "mode": meta.get("mode"),
            "civilization": meta.get("civilization"),
            "agent": meta.get("agent"),
            "model": meta.get("model"),
            "created_at": meta.get("created_at"),
            "notes": meta.get("notes"),
        }
        if not duplicate:
            con.execute(
                """INSERT INTO works(
                   work_id,module_fingerprint,script_name,first_registered_at,last_registered_at,
                   source_kind,project_id,build_id,mode,civilization,agent,model,created_at,notes,
                   module_files,metadata_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (work_id, found["module_fingerprint"], canonical_name, now, now, source_kind,
                 project_id, build_id, values["mode"], values["civilization"], values["agent"],
                 values["model"], values["created_at"], values["notes"], found["module_files"],
                 json.dumps(meta, ensure_ascii=False, sort_keys=True)),
            )
        else:
            con.execute(
                """UPDATE works SET last_registered_at=?,
                   project_id=COALESCE(?,project_id), build_id=COALESCE(?,build_id),
                   mode=COALESCE(?,mode), civilization=COALESCE(?,civilization),
                   agent=COALESCE(?,agent), model=COALESCE(?,model),
                   created_at=COALESCE(?,created_at), notes=COALESCE(?,notes),
                   metadata_json=CASE WHEN ?='{}' THEN metadata_json ELSE ? END
                   WHERE module_fingerprint=?""",
                (now, project_id, build_id, values["mode"], values["civilization"], values["agent"],
                 values["model"], values["created_at"], values["notes"],
                 json.dumps(meta, ensure_ascii=False, sort_keys=True),
                 json.dumps(meta, ensure_ascii=False, sort_keys=True),
                 found["module_fingerprint"]),
            )
        con.execute(
            """INSERT OR IGNORE INTO artifacts(
               work_id,artifact_path,artifact_kind,package_sha256,manifest_schema,manifest_present,registered_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (work_id, found["artifact_path"], found["artifact_kind"], found["package_sha256"],
             found["manifest_schema"], 1 if found["manifest_present"] else 0, now),
        )
        artifact_count = con.execute("SELECT COUNT(*) FROM artifacts WHERE work_id=?", (work_id,)).fetchone()[0]
    return {
        "ok": True,
        "registered": True,
        "duplicate": duplicate,
        "work_id": work_id,
        "script_name": canonical_name,
        "detected_script_name": found["script_name"],
        "module_fingerprint": found["module_fingerprint"],
        "module_files": found["module_files"],
        "artifact_kind": found["artifact_kind"],
        "artifact_path": found["artifact_path"],
        "artifact_count": artifact_count,
        "manifest_present": found["manifest_present"],
        "registry_db": str(Path(db_path).resolve()),
        "unknown_fields": [key for key in ("mode", "civilization", "agent", "model", "created_at")
                           if not meta.get(key)],
    }


def register_completed_project(project: str | Path, state: dict, *, db_path: Path = REGISTRY_DB) -> dict:
    project = Path(project).resolve()
    build = state.get("build")
    request = state.get("request") or {}
    if state.get("status") != "completed" or not isinstance(build, dict):
        raise RegistryError("Only a completed project can be auto-registered")
    artifact = build.get("package_file") if build.get("output_mode") == "share_package" else build.get("script_root")
    if not isinstance(artifact, str):
        raise RegistryError("Completed build does not expose a registerable artifact")
    meta = {
        "mode": request.get("mode"),
        "civilization": request.get("civilization"),
        "agent": request.get("agent"),
    }
    meta = {k: v for k, v in meta.items() if isinstance(v, str) and v}
    return register_artifact(
        artifact,
        metadata=meta,
        source_kind="completed_project",
        project_id=state.get("project_id"),
        build_id=build.get("build_id"),
        db_path=db_path,
    )



def _resolve_work(con, *, name=None, work_id=None):
    con.row_factory = sqlite3.Row
    if work_id:
        row = con.execute("SELECT * FROM works WHERE work_id=?", (work_id,)).fetchone()
        if row is None:
            raise RegistryError("No registered work matches work_id " + work_id)
        return row
    if not isinstance(name, str) or not name.strip():
        raise RegistryError("Provide a script name or work_id")
    rows = con.execute(
        "SELECT * FROM works WHERE lower(script_name)=lower(?) ORDER BY first_registered_at DESC",
        (name.strip(),),
    ).fetchall()
    if not rows:
        raise RegistryError("No registered work matches script name " + name.strip())
    if len(rows) > 1:
        ids = ", ".join(row["work_id"] for row in rows[:8])
        raise RegistryError("Multiple registered versions use this script name; choose a work_id: " + ids)
    return rows[0]


def _clean_match_record(value: dict) -> dict:
    if not isinstance(value, dict) or not value:
        raise RegistryError("Game record must be a non-empty JSON object")
    unknown = set(value) - ALLOWED_MATCH_FIELDS
    if unknown:
        raise RegistryError("Game record contains unsupported fields: " + ", ".join(sorted(unknown)))
    clean = {}
    for key in ("played_at", "mode", "map", "civilization", "result"):
        item = value.get(key)
        if item is None:
            continue
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > 200:
            raise RegistryError(key + " must be a short string")
        clean[key] = item.strip()
    outcome = value.get("outcome")
    if outcome is not None:
        if outcome not in MATCH_OUTCOMES:
            raise RegistryError("outcome must be win, loss, draw, or unknown")
        clean["outcome"] = outcome
    for key in ("placement", "players", "duration_seconds", "score"):
        item = value.get(key)
        if item is None:
            continue
        if type(item) is not int or item < 0:
            raise RegistryError(key + " must be a non-negative integer")
        clean[key] = item
    if clean.get("placement") == 0:
        raise RegistryError("placement must start at 1")
    if clean.get("players") == 0:
        raise RegistryError("players must be at least 1")
    if clean.get("placement") and clean.get("players") and clean["placement"] > clean["players"]:
        raise RegistryError("placement cannot exceed players")
    notes = value.get("notes")
    if notes is not None:
        if not isinstance(notes, str) or len(notes.strip()) > 4000:
            raise RegistryError("notes must be text of at most 4000 characters")
        if notes.strip():
            clean["notes"] = notes.strip()
    for key in ("issues", "evidence", "opponents", "allies"):
        items = value.get(key)
        if items is None:
            continue
        if not isinstance(items, list) or len(items) > 32:
            raise RegistryError(key + " must be an array of at most 32 strings")
        normalized = []
        for item in items:
            if not isinstance(item, str) or not item.strip() or len(item.strip()) > 1000:
                raise RegistryError(key + " entries must be short strings")
            normalized.append(item.strip())
        if normalized:
            clean[key] = normalized
    return clean


def record_game(record: dict, *, name=None, work_id=None, db_path: Path = REGISTRY_DB) -> dict:
    clean = _clean_match_record(record)
    now = utc_now()
    record_hash = sha256(canonical(clean))
    with _connect(db_path) as con:
        work = _resolve_work(con, name=name, work_id=work_id)
        existing = con.execute(
            "SELECT match_id FROM matches WHERE work_id=? AND record_hash=?",
            (work["work_id"], record_hash),
        ).fetchone()
        if existing:
            return {
                "ok": True, "registered": True, "duplicate": True,
                "match_id": existing[0], "work_id": work["work_id"],
                "script_name": work["script_name"],
            }
        match_id = "match-" + uuid.uuid4().hex[:16]
        con.execute(
            """INSERT INTO matches(
               match_id,work_id,recorded_at,played_at,mode,map_name,civilization,outcome,
               result_text,placement,players,duration_seconds,score,notes,issues_json,
               evidence_json,record_hash,record_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                match_id, work["work_id"], now, clean.get("played_at"), clean.get("mode"),
                clean.get("map"), clean.get("civilization"), clean.get("outcome"),
                clean.get("result"), clean.get("placement"), clean.get("players"),
                clean.get("duration_seconds"), clean.get("score"), clean.get("notes"),
                json.dumps(clean.get("issues", []), ensure_ascii=False),
                json.dumps(clean.get("evidence", []), ensure_ascii=False),
                record_hash, json.dumps(clean, ensure_ascii=False, sort_keys=True),
            ),
        )
        total = con.execute("SELECT COUNT(*) FROM matches WHERE work_id=?", (work["work_id"],)).fetchone()[0]
    return {
        "ok": True, "registered": True, "duplicate": False,
        "match_id": match_id, "work_id": work["work_id"], "script_name": work["script_name"],
        "match_count": total, "record": clean,
    }


def show_work(*, name=None, work_id=None, db_path: Path = REGISTRY_DB) -> dict:
    if not Path(db_path).exists():
        raise RegistryError("Work registry does not exist yet")
    with _connect(db_path) as con:
        work = _resolve_work(con, name=name, work_id=work_id)
        con.row_factory = sqlite3.Row
        artifacts = [dict(row) for row in con.execute(
            """SELECT artifact_kind,artifact_path,package_sha256,manifest_schema,
                      manifest_present,registered_at
               FROM artifacts WHERE work_id=? ORDER BY registered_at DESC""",
            (work["work_id"],),
        ).fetchall()]
        matches = [dict(row) for row in con.execute(
            """SELECT match_id,recorded_at,played_at,mode,map_name,civilization,outcome,
                      result_text,placement,players,duration_seconds,score,notes,
                      issues_json,evidence_json,record_json
               FROM matches WHERE work_id=? ORDER BY recorded_at DESC LIMIT 50""",
            (work["work_id"],),
        ).fetchall()]
        total = con.execute("SELECT COUNT(*) FROM matches WHERE work_id=?", (work["work_id"],)).fetchone()[0]
        wins = con.execute("SELECT COUNT(*) FROM matches WHERE work_id=? AND outcome='win'", (work["work_id"],)).fetchone()[0]
        losses = con.execute("SELECT COUNT(*) FROM matches WHERE work_id=? AND outcome='loss'", (work["work_id"],)).fetchone()[0]
        draws = con.execute("SELECT COUNT(*) FROM matches WHERE work_id=? AND outcome='draw'", (work["work_id"],)).fetchone()[0]
    clean_matches = []
    for row in matches:
        item = dict(row)
        item["issues"] = json.loads(item.pop("issues_json"))
        item["evidence"] = json.loads(item.pop("evidence_json"))
        item["record"] = json.loads(item.pop("record_json"))
        clean_matches.append(item)
    return {
        "ok": True,
        "work": dict(work),
        "artifacts": artifacts,
        "match_summary": {"total": total, "wins": wins, "losses": losses, "draws": draws},
        "matches": clean_matches,
        "registry_db": str(Path(db_path).resolve()),
    }


def list_works(*, db_path: Path = REGISTRY_DB) -> list[dict]:
    if not Path(db_path).exists():
        return []
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT w.*, (SELECT COUNT(*) FROM artifacts a WHERE a.work_id=w.work_id) AS artifact_count
               FROM works w ORDER BY first_registered_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]


def _load_metadata(path: Path | None):
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RegistryError("Metadata JSON could not be read") from exc
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register-existing")
    register.add_argument("--artifact", type=Path, required=True)
    register.add_argument("--metadata", type=Path)
    recognize = sub.add_parser("recognize")
    recognize.add_argument("--artifact", type=Path, required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show_group = show.add_mutually_exclusive_group(required=True)
    show_group.add_argument("--name")
    show_group.add_argument("--work-id")
    game = sub.add_parser("record-game")
    game_group = game.add_mutually_exclusive_group(required=True)
    game_group.add_argument("--name")
    game_group.add_argument("--work-id")
    game.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "register-existing":
            result = register_artifact(args.artifact, metadata=_load_metadata(args.metadata))
        elif args.command == "recognize":
            result = {"ok": True, **recognize_artifact(args.artifact)}
        elif args.command == "show":
            result = show_work(name=args.name, work_id=args.work_id)
        elif args.command == "record-game":
            result = record_game(_load_metadata(args.record), name=args.name, work_id=args.work_id)
        else:
            result = {"ok": True, "works": list_works(), "registry_db": str(REGISTRY_DB)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, RegistryError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
