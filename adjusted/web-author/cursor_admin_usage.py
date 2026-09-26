"""Cursor IDE hook identity + official Admin Usage Events collector.

No prompt/response text or credentials are persisted. Project hooks record only
conversation identity and workspace metadata. The Admin API key is read from
process environment and used only in-memory for an explicit refresh.
"""
from __future__ import annotations

import base64
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.request

API_URL = "https://api.cursor.com/teams/filtered-usage-events"
MAX_RANGE_SECONDS = 30 * 24 * 60 * 60
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 100
PAGE_SIZE = 100
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}\Z")


class CursorAdminUsageError(ValueError):
    pass


def _normalize_root(value):
    """Cursor on Windows sends workspace roots as /E:/repo. Drop that extra slash."""
    text = str(value).strip()
    if len(text) >= 3 and text[0] in "/\\" and text[2] == ":":
        text = text[1:]
    return str(Path(text).resolve())


def _path_key(value):
    return os.path.normcase(os.path.abspath(_normalize_root(value))).replace("\\", "/").rstrip("/").casefold()


def _safe_id(value):
    return value if isinstance(value, str) and SAFE_ID.fullmatch(value) else None


def _safe_text(value, limit=320):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and len(value) <= limit else None


def hook_db_path(repo_root):
    return Path(repo_root).resolve() / "adjusted/.local/cursor-hook-events.sqlite3"


def active_project_path(repo_root):
    return Path(repo_root).resolve() / "adjusted/.local/cursor-active-project.json"


def _active_project(repo_root):
    path = active_project_path(repo_root)
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    project_id = _safe_id(value.get("project_id")) if isinstance(value, dict) else None
    project = value.get("project") if isinstance(value, dict) else None
    if value.get("schema") != "aoe2-cursor-active-project-v1" or project_id is None or not isinstance(project, str):
        return None
    return {"project_id": project_id, "project": project,
            "agent": value.get("agent"), "usage_authorized": value.get("usage_authorized") is True}


def _connect(path, readonly=False):
    path = Path(path)
    if readonly:
        if not path.is_file() or path.is_symlink():
            return None
        return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CursorAdminUsageError("Cursor hook database cannot be a symlink")
    return sqlite3.connect(path, timeout=2)


def record_hook_payload(payload, repo_root, observed_at=None):
    """Persist a privacy-minimized Cursor hook observation.

    The hook payload may contain prompt/response text. This function deliberately
    whitelists metadata and never serializes unknown fields.
    """
    if not isinstance(payload, dict):
        return False
    conversation = _safe_id(payload.get("conversation_id") or payload.get("session_id") or payload.get("parent_conversation_id"))
    event = _safe_id(payload.get("hook_event_name"))
    roots = payload.get("workspace_roots")
    repo_root = Path(repo_root).resolve()
    if conversation is None or event is None or not isinstance(roots, list):
        return False
    clean_roots = [_normalize_root(root) for root in roots if isinstance(root, str)]
    if _path_key(repo_root) not in {_path_key(root) for root in clean_roots}:
        return False
    now = time.time() if observed_at is None else float(observed_at)
    email = _safe_text(payload.get("user_email"))
    model = _safe_text(payload.get("model_id") or payload.get("model"), 160)
    cursor_version = _safe_text(payload.get("cursor_version"), 80)
    background = 1 if payload.get("is_background_agent") is True else 0
    session_start = 1 if event == "sessionStart" else 0
    active = _active_project(repo_root)
    attributed = bool(active and active.get("usage_authorized") is True and active.get("agent") in {"cursor", "auto"})
    project_id = active["project_id"] if attributed else None
    project_path = active["project"] if attributed else None
    path = hook_db_path(repo_root)
    db = _connect(path)
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS conversations(
            conversation_id TEXT PRIMARY KEY,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            user_email TEXT,
            model TEXT,
            cursor_version TEXT,
            workspace_roots TEXT NOT NULL,
            is_background INTEGER NOT NULL DEFAULT 0,
            session_start_seen INTEGER NOT NULL DEFAULT 0,
            last_event TEXT NOT NULL,
            project_id TEXT,
            project_path TEXT
        )""")
        cols = {row[1] for row in db.execute("PRAGMA table_info(conversations)")}
        if "project_id" not in cols:
            db.execute("ALTER TABLE conversations ADD COLUMN project_id TEXT")
        if "project_path" not in cols:
            db.execute("ALTER TABLE conversations ADD COLUMN project_path TEXT")
        db.execute("""INSERT INTO conversations(
                conversation_id,first_seen,last_seen,user_email,model,cursor_version,
                workspace_roots,is_background,session_start_seen,last_event,project_id,project_path)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                first_seen=min(conversations.first_seen,excluded.first_seen),
                last_seen=max(conversations.last_seen,excluded.last_seen),
                user_email=COALESCE(excluded.user_email,conversations.user_email),
                model=COALESCE(excluded.model,conversations.model),
                cursor_version=COALESCE(excluded.cursor_version,conversations.cursor_version),
                workspace_roots=excluded.workspace_roots,
                is_background=max(conversations.is_background,excluded.is_background),
                session_start_seen=max(conversations.session_start_seen,excluded.session_start_seen),
                last_event=excluded.last_event,
                project_id=COALESCE(excluded.project_id,conversations.project_id),
                project_path=COALESCE(excluded.project_path,conversations.project_path)""",
            (conversation, now, now, email, model, cursor_version,
             json.dumps(clean_roots, ensure_ascii=False), background, session_start, event,
             project_id, project_path))
        _store_hook_turn(db, payload, conversation, now)
        _store_subagent_link(db, payload, conversation, now)
        db.commit()
    finally:
        db.close()
    return True


_TOKEN_ALIASES = {
    "input_tokens": ("input_tokens", "inputTokens"),
    "output_tokens": ("output_tokens", "outputTokens"),
    "cache_read_tokens": ("cache_read_tokens", "cacheReadTokens"),
    "cache_write_tokens": ("cache_write_tokens", "cacheWriteTokens"),
    "reasoning_tokens": ("reasoning_tokens", "reasoningTokens"),
}


def _token_sources(payload):
    sources = [payload]
    nested = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
    if nested is not None:
        sources.append(nested)
    return sources


def _token_field(payload, name):
    """Absent stays unknown. A present non-integer is invalid, not zero."""
    found = False
    value = None
    for source in _token_sources(payload):
        for alias in _TOKEN_ALIASES[name]:
            if alias not in source or source.get(alias) is None:
                continue
            found = True
            value = source.get(alias)
            break
        if found:
            break
    if not found:
        return None
    if type(value) is bool or type(value) is not int or not 0 <= value <= 10**12:
        return False
    return value


def _ensure_turn_columns(db):
    db.execute("""CREATE TABLE IF NOT EXISTS hook_turns(
        conversation_id TEXT NOT NULL,
        generation_id TEXT NOT NULL,
        event TEXT NOT NULL,
        observed_at REAL NOT NULL,
        model TEXT,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cache_read_tokens INTEGER,
        cache_write_tokens INTEGER,
        reasoning_tokens INTEGER,
        PRIMARY KEY (conversation_id, generation_id, event)
    )""")
    cols = {row[1] for row in db.execute("PRAGMA table_info(hook_turns)")}
    if "reasoning_tokens" not in cols:
        db.execute("ALTER TABLE hook_turns ADD COLUMN reasoning_tokens INTEGER")


def _store_subagent_link(db, payload, conversation, observed_at):
    """Record only a proven parent id. Task text is never stored."""
    event = payload.get("hook_event_name")
    if event not in {"subagentStart", "subagentStop"}:
        return
    parent = _safe_id(payload.get("parent_conversation_id")) or conversation
    child = _safe_id(payload.get("subagent_id"))
    if parent is None or child is None:
        return
    db.execute("""CREATE TABLE IF NOT EXISTS subagent_links(
        subagent_id TEXT PRIMARY KEY,
        parent_conversation_id TEXT NOT NULL,
        observed_at REAL NOT NULL
    )""")
    db.execute("""INSERT INTO subagent_links(subagent_id,parent_conversation_id,observed_at)
        VALUES(?,?,?)
        ON CONFLICT(subagent_id) DO UPDATE SET
            parent_conversation_id=excluded.parent_conversation_id,
            observed_at=excluded.observed_at
        WHERE excluded.observed_at>=subagent_links.observed_at""",
        (child, parent, observed_at))


def _linked_parent(db, payload, conversation):
    parent = _safe_id(payload.get("parent_conversation_id"))
    if parent is not None:
        return parent
    child = _safe_id(payload.get("subagent_id"))
    if child is None:
        return None
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return None
    if "subagent_links" not in tables:
        return None
    row = db.execute(
        "SELECT parent_conversation_id FROM subagent_links WHERE subagent_id=?", (child,)).fetchone()
    return row[0] if row else None


def _store_hook_turn(db, payload, conversation, observed_at):
    """Keep stop/afterAgentResponse/proven subagent counters. Prompt and response text never land here."""
    event = payload.get("hook_event_name")
    generation = _safe_id(payload.get("generation_id")) or _safe_id(payload.get("subagent_id"))
    if event not in {"stop", "afterAgentResponse", "subagentStop"} or generation is None:
        return
    owner = conversation
    if event == "subagentStop":
        owner = _linked_parent(db, payload, conversation)
        if owner is None:
            return
        generation = "subagent:" + generation
    parsed = {name: _token_field(payload, name) for name in _TOKEN_ALIASES}
    if any(value is False for value in parsed.values()):
        return
    if parsed["input_tokens"] is None or parsed["output_tokens"] is None:
        return
    reasoning = parsed["reasoning_tokens"]
    if reasoning is not None and reasoning > parsed["output_tokens"]:
        return
    model = _safe_text(payload.get("model") or payload.get("model_id") or payload.get("subagent_model"), 160)
    _ensure_turn_columns(db)
    db.execute("""INSERT INTO hook_turns(
            conversation_id,generation_id,event,observed_at,model,
            input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,reasoning_tokens)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(conversation_id,generation_id,event) DO UPDATE SET
            observed_at=excluded.observed_at,
            model=COALESCE(excluded.model,hook_turns.model),
            input_tokens=excluded.input_tokens,
            output_tokens=excluded.output_tokens,
            cache_read_tokens=excluded.cache_read_tokens,
            cache_write_tokens=excluded.cache_write_tokens,
            reasoning_tokens=excluded.reasoning_tokens
        WHERE excluded.observed_at>=hook_turns.observed_at""",
        (owner, generation, event, observed_at, model,
         parsed["input_tokens"], parsed["output_tokens"],
         parsed["cache_read_tokens"], parsed["cache_write_tokens"], reasoning))


def _hook_rows(workspace, repo_root):
    db = _connect(hook_db_path(repo_root), readonly=True)
    if db is None:
        return []
    try:
        try:
            cols = {row[1] for row in db.execute("PRAGMA table_info(conversations)")}
            project_cols = ",project_id,project_path" if {"project_id","project_path"} <= cols else ",NULL,NULL"
            rows = db.execute("""SELECT conversation_id,first_seen,last_seen,user_email,model,
                cursor_version,workspace_roots,is_background,session_start_seen,last_event""" +
                project_cols + " FROM conversations").fetchall()
        except sqlite3.Error:
            return []
    finally:
        db.close()
    wanted = _path_key(workspace)
    result = []
    for row in rows:
        try:
            roots = json.loads(row[6])
        except (TypeError, ValueError):
            continue
        if not isinstance(roots, list) or wanted not in {_path_key(root) for root in roots if isinstance(root, str)}:
            continue
        result.append({
            "conversation_id": row[0], "first_seen": row[1], "last_seen": row[2],
            "user_email": row[3], "model": row[4], "cursor_version": row[5],
            "is_background": bool(row[7]), "session_start_seen": bool(row[8]),
            "last_event": row[9], "project_id": row[10], "project_path": row[11],
        })
    return result


def cursor_hook_candidates(workspace, repo_root):
    return [{
        "agent": "cursor", "session_id": row["conversation_id"],
        "created_at": row["first_seen"], "updated_at": row["last_seen"],
        "is_child": row["is_background"], "workspace_match": True,
        "source": "cursor_hook", "hook_verified": True,
        "has_user_email": bool(row["user_email"]),
        "project_id": row.get("project_id"),
    } for row in sorted(_hook_rows(workspace, repo_root), key=lambda x: x["last_seen"], reverse=True)]


def cursor_hook_identity(workspace, repo_root, conversation_id):
    conversation_id = _safe_id(conversation_id)
    if conversation_id is None:
        return None
    return next((row for row in _hook_rows(workspace, repo_root)
                 if row["conversation_id"] == conversation_id), None)


def collect_cursor_hook_usage(workspace, repo_root, conversation_ids, started_at):
    """Account Cursor stop-hook turn totals. input_tokens already includes cache.

    afterAgentResponse carries the same generation total, so it is stored but not
    added. A subagentStop turn is added only when its payload or an earlier
    subagentStart proves parent_conversation_id. Same generation prefers stop.
    """
    ids = []
    for raw in conversation_ids:
        cid = _safe_id(raw)
        if cid is not None and cid not in ids:
            ids.append(cid)
    if not ids:
        return {"items": [], "gaps": [], "matched_sessions": []}
    db = _connect(hook_db_path(repo_root), readonly=True)
    if db is None:
        return {"items": [], "gaps": [
            {"code": "CURSOR_HOOK_USAGE_WAITING", "session": cid} for cid in ids],
            "matched_sessions": []}
    try:
        try:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "hook_turns" not in tables:
                rows = []
            else:
                marks = ",".join("?" for _ in ids)
                turn_cols = {row[1] for row in db.execute("PRAGMA table_info(hook_turns)")}
                reasoning_sql = "reasoning_tokens" if "reasoning_tokens" in turn_cols else "NULL"
                rows = db.execute(
                    "SELECT conversation_id,generation_id,event,observed_at,model,"
                    "input_tokens,output_tokens,cache_read_tokens,cache_write_tokens," +
                    reasoning_sql + " FROM hook_turns WHERE conversation_id IN (" + marks + ")", ids).fetchall()
        except sqlite3.Error:
            rows = []
    finally:
        db.close()
    start = float(started_at)
    grouped = defaultdict(dict)
    for cid, gid, event, observed_at, model, inp, out, cache_read, cache_write, reasoning in rows:
        if observed_at is None or float(observed_at) < start:
            continue
        current = grouped[(cid, gid)].get(event)
        if current is None or float(observed_at) >= current["observed_at"]:
            grouped[(cid, gid)][event] = {
                "observed_at": float(observed_at), "model": model,
                "input_tokens": inp, "output_tokens": out,
                "cache_read_tokens": cache_read, "cache_write_tokens": cache_write,
                "reasoning_tokens": reasoning,
            }
    items = []
    gaps = []
    matched = set()
    for (cid, gid), events in sorted(grouped.items()):
        chosen = events.get("stop") or events.get("subagentStop")
        if chosen is None:
            continue
        inp, out = chosen["input_tokens"], chosen["output_tokens"]
        cache_read, cache_write = chosen["cache_read_tokens"], chosen["cache_write_tokens"]
        if type(inp) is not int or type(out) is not int:
            gaps.append({"code": "CURSOR_HOOK_TOKEN_FIELDS_INVALID", "session": cid})
            continue
        if ((cache_read is not None and cache_read > inp) or
                (cache_write is not None and cache_write > inp) or
                (cache_read is not None and cache_write is not None and cache_read + cache_write > inp)):
            gaps.append({"code": "CURSOR_HOOK_TOKEN_FIELDS_INVALID", "session": cid})
            continue
        usage = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "cached_input_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "reasoning_output_tokens": chosen["reasoning_tokens"] if type(chosen.get("reasoning_tokens")) is int else None,
        }
        key = "cursor-hook:" + hashlib.sha256((cid + "\n" + gid).encode("utf-8")).hexdigest()[:24]
        items.append({
            "agent": "cursor", "session": cid, "key": key,
            "timestamp": chosen["observed_at"], "model": chosen["model"] or "unknown",
            "usage": usage,
        })
        matched.add(cid)
    for cid in ids:
        if cid not in matched:
            gaps.append({"code": "CURSOR_HOOK_USAGE_WAITING", "session": cid})
    return {"items": items, "gaps": gaps, "matched_sessions": sorted(matched)}


def _default_transport(api_key, body):
    auth = base64.b64encode((api_key + ":").encode("utf-8")).decode("ascii")
    raw = json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
    req = urllib.request.Request(API_URL, data=raw, method="POST", headers={
        "Authorization": "Basic " + auth,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AOE2-AI-cursor-usage/1",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise CursorAdminUsageError("Cursor Admin API response is too large")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise CursorAdminUsageError("Cursor Admin API HTTP " + str(exc.code)) from None
    except urllib.error.URLError as exc:
        raise CursorAdminUsageError("Cursor Admin API is unreachable") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CursorAdminUsageError("Cursor Admin API returned invalid JSON") from exc


def _fetch_email_events(api_key, email, start_ms, end_ms, transport):
    events = []
    page = 1
    while True:
        body = {"startDate": start_ms, "endDate": end_ms, "email": email,
                "page": page, "pageSize": PAGE_SIZE}
        value = transport(api_key, body)
        if not isinstance(value, dict) or not isinstance(value.get("usageEvents"), list):
            raise CursorAdminUsageError("Cursor Admin API response shape changed")
        events.extend(row for row in value["usageEvents"] if isinstance(row, dict))
        pagination = value.get("pagination") or {}
        if not pagination.get("hasNextPage"):
            break
        page += 1
        if page > MAX_PAGES:
            raise CursorAdminUsageError("Cursor Admin API pagination exceeded safety limit")
    return events


def _int(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


def collect_cursor_admin_usage(workspace, repo_root, conversation_ids, started_at, *,
                               api_key, end_at=None, transport=None):
    """Fetch team usage then keep only exact hook-verified conversation IDs."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise CursorAdminUsageError("CURSOR_ADMIN_API_KEY is not configured")
    ids = []
    identities = {}
    gaps = []
    for raw in conversation_ids:
        cid = _safe_id(raw)
        if cid is None:
            continue
        identity = cursor_hook_identity(workspace, repo_root, cid)
        if identity is None:
            gaps.append({"code": "CURSOR_ADMIN_HOOK_IDENTITY_MISSING", "session": cid})
            continue
        if not identity.get("user_email"):
            gaps.append({"code": "CURSOR_ADMIN_HOOK_EMAIL_MISSING", "session": cid})
            continue
        ids.append(cid)
        identities[cid] = identity
    if not ids:
        return {"items": [], "gaps": gaps, "matched_sessions": [], "range_truncated": False}

    now = time.time() if end_at is None else float(end_at)
    start = float(started_at)
    truncated = now - start > MAX_RANGE_SECONDS
    if truncated:
        start = now - MAX_RANGE_SECONDS
        gaps.append({"code": "CURSOR_ADMIN_RANGE_TRUNCATED", "session": "project"})
    start_ms, end_ms = int(start * 1000), int(now * 1000)
    transport = transport or _default_transport

    groups = defaultdict(list)
    for cid in ids:
        groups[identities[cid]["user_email"]].append(cid)

    raw_matches = []
    for email, group_ids in groups.items():
        wanted = set(group_ids)
        for event in _fetch_email_events(api_key, email, start_ms, end_ms, transport):
            if event.get("conversationId") not in wanted:
                continue
            ts = event.get("timestamp")
            try:
                when_ms = int(ts)
            except (TypeError, ValueError):
                gaps.append({"code": "CURSOR_ADMIN_EVENT_TIMESTAMP_INVALID",
                             "session": event.get("conversationId")})
                continue
            if not start_ms <= when_ms <= end_ms:
                continue
            raw_matches.append(event)

    canonical_rows = []
    matched_sessions = set()
    for event in raw_matches:
        cid = event.get("conversationId")
        token = event.get("tokenUsage")
        if event.get("isTokenBasedCall") is not True or not isinstance(token, dict):
            gaps.append({"code": "CURSOR_ADMIN_NON_TOKEN_EVENT", "session": cid})
            continue
        inp = _int(token.get("inputTokens"))
        out = _int(token.get("outputTokens"))
        cache_read = _int(token.get("cacheReadTokens"))
        cache_write = _int(token.get("cacheWriteTokens"))
        if None in {inp, out, cache_read, cache_write}:
            gaps.append({"code": "CURSOR_ADMIN_TOKEN_FIELDS_INVALID", "session": cid})
            continue
        usage = {
            "input_tokens": inp + cache_read + cache_write,
            "output_tokens": out,
            "total_tokens": inp + cache_read + cache_write + out,
            "cached_input_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "reasoning_output_tokens": None,
        }
        identity = {
            "conversationId": cid,
            "timestamp": str(event.get("timestamp")),
            "model": event.get("model") or "unknown",
            "kind": event.get("kind"),
            "tokenUsage": {
                "inputTokens": inp, "outputTokens": out,
                "cacheReadTokens": cache_read, "cacheWriteTokens": cache_write,
            },
            "chargedCents": event.get("chargedCents"),
        }
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        canonical_rows.append((canonical, event, usage))
        matched_sessions.add(cid)

    canonical_rows.sort(key=lambda row: (str(row[1].get("timestamp")), row[0]))
    occurrences = defaultdict(int)
    items = []
    for canonical, event, usage in canonical_rows:
        occurrences[canonical] += 1
        suffix = occurrences[canonical]
        key = "cursor-admin:" + hashlib.sha256(
            (canonical + "#" + str(suffix)).encode("utf-8")).hexdigest()[:24]
        items.append({
            "agent": "cursor",
            "session": event["conversationId"],
            "key": key,
            "timestamp": int(event["timestamp"]) / 1000,
            "model": event.get("model") or "unknown",
            "usage": usage,
        })

    for cid in ids:
        if cid not in matched_sessions:
            gaps.append({"code": "CURSOR_ADMIN_NO_MATCHING_EVENTS", "session": cid})
    return {
        "items": items,
        "gaps": gaps,
        "matched_sessions": sorted(matched_sessions),
        "range_truncated": truncated,
    }
