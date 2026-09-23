"""Project-scoped host metadata. Never reads credentials or unrelated transcripts."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlparse

SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")

def timestamp(value):
    if type(value) in (int, float):
        return value / 1000 if value > 20_000_000_000 else value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None

def path_key(value):
    value = str(value)
    if value.startswith("file:"):
        value = unquote(urlparse(value).path)
        if re.match(r"^/[A-Za-z]:", value):
            value = value[1:]
    return os.path.normcase(os.path.abspath(value)).replace("\\", "/").rstrip("/").casefold()

@contextmanager
def readonly_db(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        yield db
    finally:
        db.close()

def cursor_metadata(workspace, home=None, environ=None):
    """Only workspace.json and SQL-projected composer metadata; no value blobs."""
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    bases = [Path(env.get("APPDATA") or home / "AppData/Roaming") / "Cursor/User",
             home / "Library/Application Support/Cursor/User", home / ".config/Cursor/User"]
    found = {}
    for base in bases:
        workspace_ids = []
        for meta in (base / "workspaceStorage").glob("*/workspace.json"):
            if meta.is_symlink():
                continue
            try:
                value = json.loads(meta.read_text(encoding="utf-8-sig"))
                if path_key(value.get("folder", "")) == path_key(workspace):
                    workspace_ids.append(meta.parent.name)
            except (OSError, ValueError, TypeError):
                continue
        if not workspace_ids:
            continue
        dbs = [base / "globalStorage/state.vscdb"]
        dbs += [base / "workspaceStorage" / wid / "state.vscdb" for wid in workspace_ids]
        for path in dbs:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                with readonly_db(path) as db:
                    cols = {row[1] for row in db.execute("PRAGMA table_info(composerHeaders)")}
                    if not {"composerId", "workspaceId", "createdAt", "lastUpdatedAt"} <= cols:
                        continue
                    slots = ",".join("?" for _ in workspace_ids)
                    subagent = "isSubagent" if "isSubagent" in cols else "0"
                    rows = db.execute("SELECT composerId,createdAt,lastUpdatedAt," + subagent +
                                      " FROM composerHeaders WHERE workspaceId IN (" + slots + ")", workspace_ids)
                    for cid, created, updated, child in rows:
                        if not isinstance(cid, str) or not SESSION_ID.fullmatch(cid):
                            continue
                        usage = None
                        try:
                            usage = db.execute("SELECT json_type(value,'$.usageData'), "
                                "(SELECT count(*) FROM json_each(json_extract(value,'$.usageData'))) "
                                "FROM cursorDiskKV WHERE key=?", ("composerData:" + cid,)).fetchone()
                        except sqlite3.Error:
                            pass
                        found[cid] = {"agent": "cursor", "session_id": cid,
                            "created_at": timestamp(created), "updated_at": timestamp(updated),
                            "is_child": bool(child), "workspace_match": True,
                            "usage_fields": usage[1] if usage else None,
                            "usage_status": "EMPTY_USAGE_DATA" if usage and usage[1] == 0 else "UNVERIFIED_LOCAL_SCHEMA"}
            except sqlite3.Error:
                continue
    return sorted(found.values(), key=lambda row: row.get("updated_at") or row.get("created_at") or 0, reverse=True)

def session_files(agent, roots, sessions):
    """Enumerate names first. Only explicitly bound files are ever opened."""
    result = []
    for root in roots:
        root = Path(root)
        for session in sessions:
            if not SESSION_ID.fullmatch(session):
                continue
            if agent == "claude":
                patterns = [f"**/{session}.jsonl"]
            elif agent == "gemini":
                patterns = [f"**/chats/{session}.json", f"**/chats/{session}.jsonl",
                            f"**/chats/session-*-{session}.json", f"**/chats/session-*-{session[:8]}.json"]
            elif agent in {"cline", "roo"}:
                patterns = [f"tasks/{session}/ui_messages.json"]
            elif agent == "kimi":
                if ":" in session:
                    sid, child = session.split(":", 1)
                    patterns = [f"sessions/*/{sid}/agents/{child}/wire.jsonl"]
                else:
                    patterns = [f"sessions/*/{session}/wire.jsonl"]
            else:
                patterns = []
            for pattern in patterns:
                for path in root.glob(pattern):
                    if path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024 * 1024:
                        result.append((session, path))
    return list(dict.fromkeys(result))

def project_candidates(agent, workspace, roots, home=None, environ=None):
    if not workspace:
        return []
    if agent == "cursor":
        return cursor_metadata(workspace, home, environ)
    found = {}
    if agent == "codex":
        for root in roots:
            for path in Path(root).glob("state_*.sqlite"):
                try:
                    with readonly_db(path) as db:
                        cols = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
                        if not {"id", "cwd", "created_at", "updated_at"} <= cols:
                            continue
                        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        parents = {}
                        if "thread_spawn_edges" in tables:
                            edge_cols = {row[1] for row in db.execute("PRAGMA table_info(thread_spawn_edges)")}
                            if {"parent_thread_id", "child_thread_id"} <= edge_cols:
                                for parent, child in db.execute("SELECT parent_thread_id,child_thread_id FROM thread_spawn_edges"):
                                    if (isinstance(parent, str) and SESSION_ID.fullmatch(parent)
                                            and isinstance(child, str) and SESSION_ID.fullmatch(child)):
                                        parents[child] = parent
                        for sid, cwd, created, updated in db.execute("SELECT id,cwd,created_at,updated_at FROM threads WHERE cwd=?", (str(workspace),)):
                            if SESSION_ID.fullmatch(sid) and path_key(cwd) == path_key(workspace):
                                row = {"agent": agent, "session_id": sid, "created_at": timestamp(created),
                                       "updated_at": timestamp(updated), "workspace_match": True}
                                if sid in parents:
                                    row.update(is_child=True, parent_session_id=parents[sid])
                                found[sid] = row
                except sqlite3.Error:
                    continue
    elif agent == "claude":
        # Index metadata only, never reads all session logs to find their cwd.
        for root in roots:
            encoded = re.sub(r"[^A-Za-z0-9-]", "-", str(workspace))
            for path in [Path(root) / encoded / "sessions-index.json"]:
                try:
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    for row in data.get("entries", []):
                        sid = row.get("sessionId")
                        if isinstance(sid, str) and SESSION_ID.fullmatch(sid) and path_key(row.get("projectPath", "")) == path_key(workspace):
                            found[sid] = {"agent": agent, "session_id": sid,
                                "created_at": timestamp(row.get("created")), "updated_at": timestamp(row.get("modified")),
                                "workspace_match": True}
                except (OSError, ValueError, TypeError):
                    continue
    return sorted(found.values(), key=lambda row: row.get("updated_at") or 0, reverse=True)
