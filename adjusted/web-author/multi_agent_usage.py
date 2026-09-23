"""Real usage from explicitly bound host sessions; never account-wide scans.

Host discovery is metadata only. Unsupported/missing fields remain actionable
connection gaps. ccusage session JSON can be imported explicitly; no external
package is installed or executed by the web service.
"""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from agent_catalog import agent_catalog, agent_info, normalize_agent
from host_usage import project_candidates, session_files
from usage_formats import PHASES, normalize

SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/+ -]{0,159}$")
STATE_SCHEMA = "author-multi-agent-usage-v1"
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_FILES_PER_SOURCE = 400
SKEW_SECONDS = 0


def _ts(value):
    if isinstance(value, (int, float)):
        # Accept epoch milliseconds used by several IDE agents.
        return float(value) / 1000.0 if value > 20_000_000_000 else float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class _UnknownCount(int):
    """Arithmetic sentinel only: never exported as a measured zero."""

def _count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else _UnknownCount(0)


def _model(value):
    return value if isinstance(value, str) and SAFE_MODEL.fullmatch(value) else "unknown"


def _hash(*parts):
    raw = "\0".join(str(p) for p in parts).encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:24]


def _event_id(agent, session, key):
    return f"agent-{_hash(agent)}-{_hash(session, key)}"


def _norm_usage(inp=None, out=None, cache_read=None, cache_write=None, reasoning=None, total=None):
    # Preserve upstream explicit cache-exclusive formats without inventing missing zeroes.
    if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
        return None
    if isinstance(cache_read, _UnknownCount) or isinstance(cache_write, _UnknownCount):
        return None  # exclusive input cannot be normalized without these counters
    cached = cache_read if type(cache_read) is int else None
    written = cache_write if type(cache_write) is int else None
    thought = reasoning if type(reasoning) is int else None
    inp = inp + (cached or 0) + (written or 0)
    if type(total) is int:
        if total < inp + out:
            return None
        extra = total - inp - out
        out += extra
        thought = min(thought, extra) if thought is not None else None
    elif isinstance(reasoning, _UnknownCount):
        return None
    elif thought is not None:
        out += thought
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
            "cached_input_tokens": cached, "cache_write_tokens": written,
            "reasoning_output_tokens": thought}

def _delta(current, previous):
    if current is None:
        return None
    previous = previous or {k: 0 for k in current}
    required = ("input_tokens", "output_tokens", "total_tokens")
    if any(type(current.get(k)) is not int or type(previous.get(k)) is not int or current[k] < previous[k] for k in required):
        return None
    result = {k: current[k] - previous[k] for k in required}
    if result["total_tokens"] == 0:
        return {}
    for key, limit in (("cached_input_tokens", result["input_tokens"]),
                       ("cache_write_tokens", result["input_tokens"]),
                       ("reasoning_output_tokens", result["output_tokens"])):
        now, old = current.get(key), previous.get(key)
        value = now - old if type(now) is int and type(old) is int else None
        result[key] = value if value is not None and 0 <= value <= limit else None
    return result


def registry(home=None, environ=None):
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    app = Path(env.get("APPDATA") or home / "AppData/Roaming")
    xdg = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    def many(key, defaults):
        return [Path(v).expanduser() for v in env[key].split(",") if v] if env.get(key) else defaults
    claude = Path(env["CLAUDE_CONFIG_DIR"]) / "projects" if env.get("CLAUDE_CONFIG_DIR") else home / ".claude/projects"
    locations = {
        "codex": [Path(env.get("CODEX_HOME") or home / ".codex")],
        "claude": [claude], "gemini": many("GEMINI_DATA_DIR", [home / ".gemini/tmp"]),
        "cursor": [app / "Cursor/User/workspaceStorage", home / "Library/Application Support/Cursor/User/workspaceStorage", home / ".config/Cursor/User/workspaceStorage"],
        "opencode": many("OPENCODE_DATA_DIR", [xdg / "opencode"]),
        "copilot": [Path(env["AOE2_COPILOT_USAGE_FILE"])] if env.get("AOE2_COPILOT_USAGE_FILE") else [],
        "kimi": many("KIMI_DATA_DIR", [home / ".kimi", home / ".kimi-code"]),
    }
    for agent, ext in (("cline", "saoudrizwan.claude-dev"), ("roo", "rooveterinaryinc.roo-cline")):
        locations[agent] = many("AOE2_" + agent.upper() + "_STORAGE", [
            app / editor / "User/globalStorage" / ext for editor in ("Code", "Cursor", "Windsurf")
        ] + [home / ".config/Code/User/globalStorage" / ext,
             home / "Library/Application Support/Code/User/globalStorage" / ext])
    return [{"id": row["id"], "label": row["label"], "mode": row["metering_mode"],
             "roots": locations.get(row["id"], [])} for row in agent_catalog()]


def detect_agents(home=None, environ=None):
    """A generic .agent folder is not proof that the agent is in use or meterable."""
    result = []
    patterns = {"codex": ["sessions/*/*/*/rollout-*.jsonl"], "claude": ["**/*.jsonl"],
                "gemini": ["*/chats/session-*.json"], "cursor": ["*/workspace.json"],
                "opencode": ["opencode*.db", "storage/message/*/*.json"],
                "kimi": ["sessions/*/*/wire.jsonl", "sessions/*/*/agents/*/wire.jsonl"],
                "cline": ["tasks/*/ui_messages.json"], "roo": ["tasks/*/ui_messages.json"]}
    for row in registry(home, environ):
        existing = [p for p in row["roots"] if p.exists()]
        detected = any(p.is_file() for p in existing) if row["id"] == "copilot" else any(
            next(p.glob(pattern), None) is not None for p in existing for pattern in patterns.get(row["id"], []))
        result.append({**row, "roots": [str(p) for p in existing], "detected": detected,
                       "detection_basis": "usage_storage_present" if detected else "not_observed"})
    return result


def _recent_files(roots, suffixes, started_at):
    found = []
    threshold = started_at - 86400  # old session files can keep receiving new lines
    for root in roots:
        try:
            if not root.exists():
                continue
            candidates = root.rglob("*") if root.is_dir() else [root]
            for path in candidates:
                try:
                    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in suffixes:
                        continue
                    stat = path.stat()
                    if stat.st_size > MAX_FILE_BYTES or stat.st_mtime < threshold:
                        continue
                    found.append((stat.st_mtime, path))
                except OSError:
                    continue
        except OSError:
            continue
    found.sort(reverse=True, key=lambda x:x[0])
    return [p for _,p in found[:MAX_FILES_PER_SOURCE]]


def _iter_all_jsonl(path):
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            for index, line in enumerate(stream, 1):
                if len(line) > 4 * 1024 * 1024:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield index, row
    except OSError:
        return


def _iter_jsonl(path):
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            for index, line in enumerate(stream, 1):
                if len(line) > 4 * 1024 * 1024:
                    continue
                if "usage" not in line and "token" not in line and "turn_context" not in line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield index, row
    except OSError:
        return


def _claude_like_events(agent, roots, started_at):
    events = []
    for path in _recent_files(roots,{".jsonl"},started_at):
        session = path.stem
        for index,row in _iter_jsonl(path):
            msg = row.get("message") if isinstance(row.get("message"),dict) else {}
            usage = msg.get("usage") if isinstance(msg.get("usage"),dict) else row.get("usage")
            if not isinstance(usage,dict):
                continue
            when = _ts(row.get("timestamp") or msg.get("timestamp"))
            if when is not None and when < started_at - SKEW_SECONDS:
                continue
            inp=_count(usage.get("input_tokens")); out=_count(usage.get("output_tokens"))
            cr=_count(usage.get("cache_read_input_tokens")); cw=_count(usage.get("cache_creation_input_tokens"))
            if not any((inp,out,cr,cw)):
                continue
            mid = msg.get("id") or row.get("uuid") or row.get("id") or f"{path.name}:{index}"
            events.append({"agent":agent,"session":session,"key":mid,"timestamp":when,
                           "model":_model(msg.get("model") or row.get("model")),
                           "usage":_norm_usage(inp,out,cr,cw)})
    return events


def _codex_events(roots, started_at):
    """Read exact bound rollout files; charge cumulative deltas, never last-token repeats."""
    files = []
    for root in roots:
        files += _recent_files([root / "sessions", root / "archived_sessions"] if root.is_dir() else [root],
                               {".jsonl"}, 0)
    events = []
    replayed = set()
    for path in sorted(set(files), key=str):
        previous = None
        model = "unknown"
        created = None
        session = path.stem
        try:
            with path.open("rb") as stream:
                for index, raw in enumerate(stream, 1):
                    if not raw.endswith(b"\n"):
                        break
                    if len(raw) > 4 * 1024 * 1024:
                        continue
                    if not any(key in raw for key in (b'"session_meta"', b'"turn_context"', b'"token_count"')):
                        continue
                    try:
                        row = json.loads(raw)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(row, dict):
                        continue
                    payload = row.get("payload") or {}
                    if row.get("type") == "session_meta":
                        created = _ts(row.get("timestamp") or payload.get("timestamp"))
                        session = str(payload.get("id") or session)
                        continue
                    if row.get("type") == "turn_context":
                        model = _model(payload.get("model"))
                        continue
                    if row.get("type") != "event_msg" or payload.get("type") != "token_count":
                        continue
                    when = _ts(row.get("timestamp"))
                    raw_usage = (payload.get("info") or {}).get("total_token_usage")
                    base = {"agent": "codex", "session": session, "timestamp": when, "model": model,
                            "key": "cumulative:" + _hash(row.get("timestamp"), raw_usage)}
                    if not isinstance(raw_usage, dict) or type(raw_usage.get("input_tokens")) is not int or type(raw_usage.get("output_tokens")) is not int:
                        if when is None or when >= started_at:
                            events.append({**base, "usage": None, "gap": "UNSUPPORTED_CODEX_USAGE"})
                        continue
                    inp, out = raw_usage["input_tokens"], raw_usage["output_tokens"]
                    if inp < 0 or out < 0 or raw_usage.get("total_tokens", inp + out) != inp + out:
                        events.append({**base, "usage": None, "gap": "INVALID_CODEX_TOTAL"})
                        continue
                    current = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
                               "cached_input_tokens": raw_usage.get("cached_input_tokens"),
                               "cache_write_tokens": None,
                               "reasoning_output_tokens": raw_usage.get("reasoning_output_tokens")}
                    if when is not None and when < started_at:
                        previous = current
                        continue
                    if when is None:
                        events.append({**base, "usage": None, "gap": "MISSING_USAGE_TIMESTAMP"})
                        previous = current
                        continue
                    if previous is None and not (created is not None and created >= started_at):
                        events.append({**base, "usage": None, "gap": "NO_PROJECT_START_BASELINE"})
                        previous = current
                        continue
                    change = _delta(current, previous)
                    previous = current
                    marker = (row.get("timestamp"), model, tuple(current.items()))
                    if marker in replayed:
                        events.append({**base, "usage": None, "gap": "AMBIGUOUS_CROSS_SESSION_REPLAY"})
                        continue
                    replayed.add(marker)
                    if change is None:
                        events.append({**base, "usage": None, "gap": "CUMULATIVE_RESET"})
                    elif change:
                        events.append({**base, "usage": change})
        except OSError:
            continue
    return events


def _gemini_tokens(value):
    if not isinstance(value,dict): return None
    def one(*keys):
        for key in keys:
            if key in value: return _count(value.get(key))
        return _UnknownCount(0)
    return dict(inp=one("input","prompt","input_tokens","prompt_tokens"),
                out=one("output","candidates","output_tokens","candidates_tokens"),
                cached=one("cached","cached_tokens"),
                thoughts=one("thoughts","reasoning","thoughts_tokens","reasoning_tokens"),
                tool=one("tool","tool_tokens"),
                total=one("total","total_tokens"))


def _gemini_events(roots, started_at):
    events=[]
    for path in _recent_files(roots,{".json",".jsonl"},started_at):
        records=[]
        document_session=None
        if path.suffix.lower()==".jsonl":
            records=[row for _,row in _iter_jsonl(path)]
        else:
            try:
                doc=json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError,UnicodeError,json.JSONDecodeError):
                continue
            if isinstance(doc,dict) and isinstance(doc.get("messages"),list):
                records=doc["messages"]
                document_session=doc.get("sessionId")
            elif isinstance(doc,dict):
                records=[doc]
        session=document_session or path.stem
        for index,row in enumerate(records):
            if not isinstance(row,dict): continue
            if row.get("type") not in (None,"gemini") and "tokens" not in row and "stats" not in row:
                continue
            token=_gemini_tokens(row.get("tokens"))
            if token is None and isinstance(row.get("stats"),dict):
                token=_gemini_tokens(row["stats"].get("tokens") or row["stats"])
            if token is None: continue
            complete_counts = all(type(token[k]) is int for k in ("inp", "out", "cached", "thoughts", "tool"))
            when=_ts(row.get("timestamp") or row.get("created_at") or row.get("startTime") or row.get("lastUpdated"))
            if when is not None and when < started_at-SKEW_SECONDS: continue
            raw_input=token["inp"]; cached=token["cached"]; total=token["total"] or None
            inclusive_total=raw_input+token["out"]+token["thoughts"]+token["tool"]
            exclusive_total=inclusive_total+cached
            # Gemini logs exist in both forms: input can include the cached portion
            # or exclude it. Match ccusage's total-based disambiguation.
            if cached>0 and total==inclusive_total and total!=exclusive_total:
                noncached=max(0,raw_input-min(raw_input,cached))
            else:
                noncached=raw_input
            usage=_norm_usage(noncached+token["tool"],token["out"],cached,0,token["thoughts"],total) if complete_counts else None
            if usage is not None and not usage["total_tokens"]: continue
            events.append({"agent":"gemini","session":session,
                           "key":row.get("id") or f"{path.name}:{index}","timestamp":when,
                           "model":_model(row.get("model")),"usage":usage})
    return events



def _opencode_message(agent, row, message_id, session_id, created, started_at):
    if not isinstance(row, dict):
        return None
    tokens=row.get("tokens")
    if not isinstance(tokens,dict):
        return None
    model_ref=row.get("model") if isinstance(row.get("model"),dict) else {}
    model=row.get("modelID") or model_ref.get("id") or model_ref.get("modelID")
    provider=row.get("providerID") or model_ref.get("providerID")
    model_name=(str(provider)+"/"+str(model)) if provider and model else model
    time_row=row.get("time") if isinstance(row.get("time"),dict) else {}
    when=_ts(time_row.get("created") or created)
    if when is not None and when < started_at-SKEW_SECONDS:
        return None
    cache=tokens.get("cache") if isinstance(tokens.get("cache"),dict) else {}
    inp=_count(tokens.get("input")); out=_count(tokens.get("output"))
    cr=_count(cache.get("read")); cw=_count(cache.get("write"))
    reasoning=_count(tokens.get("reasoning"))
    total=_count(tokens.get("total"))
    if not any((inp,out,cr,cw,reasoning,total)):
        return None
    if not total:
        total=inp+out+cr+cw+reasoning
    session=str(row.get("sessionID") or session_id or "unknown-session")
    key=str(row.get("id") or message_id or _hash(session,when,model_name,inp,out,total))
    return {"agent":agent,"session":session,"key":key,"timestamp":when,
            "model":_model(model_name),"snapshot":True,"usage":_norm_usage(inp,out,cr,cw,reasoning,total)}


def _sqlite_columns(db, table):
    try:
        return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _opencode_db_events(root, started_at, bindings):
    events=[]; seen=set()
    candidates=[]
    try:
        direct=root/"opencode.db"
        if direct.is_file(): candidates.append(direct)
        candidates.extend(p for p in root.glob("opencode-*.db") if p.is_file() and not p.is_symlink())
    except OSError:
        return events
    start_ms=int((started_at-SKEW_SECONDS)*1000)
    slots=",".join("?" for _ in bindings)
    if not bindings: return events
    for path in dict.fromkeys(candidates):
        try:
            db=sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro",uri=True,timeout=1)
        except (sqlite3.Error,OSError):
            continue
        try:
            cols=_sqlite_columns(db,"message")
            if {"id","session_id","data"} <= cols:
                if "time_created" in cols:
                    query="SELECT id,session_id,data,time_created FROM message WHERE session_id IN ("+slots+") AND time_created>=? ORDER BY time_created"
                    rows=db.execute(query,(*bindings,start_ms))
                else:
                    rows=db.execute("SELECT id,session_id,data,NULL FROM message WHERE session_id IN ("+slots+") ORDER BY rowid DESC LIMIT 5000", bindings)
                for mid,sid,data,created in rows:
                    try: row=json.loads(data)
                    except (TypeError,json.JSONDecodeError): continue
                    event=_opencode_message("opencode",row,mid,sid,created,started_at)
                    if event and event["key"] not in seen:
                        seen.add(event["key"]); events.append(event)
            cols=_sqlite_columns(db,"session_message")
            if {"id","session_id","type","data"} <= cols:
                if "time_created" in cols:
                    rows=db.execute("SELECT id,session_id,type,data,time_created FROM session_message WHERE session_id IN ("+slots+") AND time_created>=? AND type='assistant' ORDER BY time_created",(*bindings,start_ms))
                else:
                    rows=db.execute("SELECT id,session_id,type,data,NULL FROM session_message WHERE session_id IN ("+slots+") AND type='assistant' ORDER BY rowid DESC LIMIT 5000", bindings)
                for mid,sid,kind,data,created in rows:
                    try: row=json.loads(data)
                    except (TypeError,json.JSONDecodeError): continue
                    event=_opencode_message("opencode",row,mid,sid,created,started_at)
                    if event and event["key"] not in seen:
                        seen.add(event["key"]); events.append(event)
        except sqlite3.Error:
            pass
        finally:
            db.close()
    return events


def _opencode_events(roots, started_at, bindings):
    events=[]; seen=set()
    for root in roots:
        if not root.is_dir():
            continue
        for event in _opencode_db_events(root,started_at,bindings):
            marker=(event["session"],event["key"])
            if marker not in seen:
                seen.add(marker); events.append(event)
        message_roots=[root/"storage/message"/sid for sid in bindings]
        for path in _recent_files(message_roots,{".json"},started_at):
            try: row=json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError,UnicodeError,json.JSONDecodeError): continue
            event=_opencode_message("opencode",row,path.stem,path.parent.name,None,started_at)
            if event:
                marker=(event["session"],event["key"])
                if marker not in seen:
                    seen.add(marker); events.append(event)
    return events


def _kimi_events(files, started_at):
    result = []
    for session, path in files:
        for index, row in _iter_jsonl(path):
            message = row.get("message") if isinstance(row.get("message"), dict) else row
            kind = message.get("type")
            payload = message.get("payload") if isinstance(message.get("payload"), dict) else message
            if kind == "StatusUpdate":
                raw = payload.get("token_usage")
                names = ("input_other", "output", "input_cache_read", "input_cache_creation")
            elif kind == "usage.record" and payload.get("usageScope") == "turn":
                raw = payload.get("usage")
                names = ("inputOther", "output", "inputCacheRead", "inputCacheCreation")
            else:
                continue
            if not isinstance(raw, dict):
                continue
            when = _ts(row.get("timestamp") or row.get("time") or payload.get("timestamp"))
            if when is not None and when < started_at:
                continue
            counts = [_count(raw.get(key)) for key in names]
            if not any(counts):
                continue
            result.append({"agent": "kimi", "session": session, "key": payload.get("message_id") or f"wire:{index}",
                "timestamp": when, "model": _model(payload.get("model") or row.get("model")),
                "usage": _norm_usage(*counts), "snapshot": True})
    return result


def _task_events(agent, files, started_at):
    result = []
    for session, path in files:
        try:
            rows = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != "say":
                continue
            if row.get("say") in {"deleted_api_reqs", "subagent_usage"}:
                result.append({"agent": agent, "session": session, "key": "unmapped:" + str(row.get("ts")),
                    "timestamp": _ts(row.get("ts")), "model": "unknown", "usage": None,
                    "gap": "TASK_AGGREGATE_NOT_ATTRIBUTABLE"})
                continue
            if row.get("say") != "api_req_started" or row.get("partial") is True:
                continue
            when = _ts(row.get("ts"))
            if when is not None and when < started_at:
                continue
            try:
                raw = json.loads(row.get("text") or "{}")
            except ValueError:
                continue
            if not isinstance(raw, dict) or "tokensIn" not in raw or "tokensOut" not in raw:
                continue  # still waiting for the request's final usage
            result.append({"agent": agent, "session": session, "key": "request:" + str(row.get("ts")),
                "timestamp": when, "model": _model(raw.get("model")), "snapshot": True,
                "usage": _norm_usage(_count(raw.get("tokensIn")), _count(raw.get("tokensOut")),
                                     _count(raw.get("cacheReads")), _count(raw.get("cacheWrites")))})
    return result


def _copilot_scoped_events(files, bindings, started_at):
    """Explicit dedicated OTel files only, chat spans only (not parent totals)."""
    result = []
    for path in files:
        if not path.is_file():
            continue
        for index, row in _iter_jsonl(path):
            attrs = row.get("attributes")
            if not isinstance(attrs, dict) or attrs.get("gen_ai.operation.name") != "chat":
                continue
            session = attrs.get("gen_ai.conversation.id")
            if session not in bindings:
                continue
            when = _ts(row.get("timestamp"))
            end = row.get("endTime")
            if isinstance(end, list) and len(end) == 2 and all(type(n) is int for n in end):
                when = end[0] + end[1] / 1_000_000_000
            if when is not None and when < started_at:
                continue
            inp, out = attrs.get("gen_ai.usage.input_tokens"), attrs.get("gen_ai.usage.output_tokens")
            usage = None
            if type(inp) is int and type(out) is int and min(inp, out) >= 0:
                usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
                    "cached_input_tokens": attrs.get("gen_ai.usage.cache_read.input_tokens"),
                    "cache_write_tokens": attrs.get("gen_ai.usage.cache_creation.input_tokens"),
                    "reasoning_output_tokens": attrs.get("gen_ai.usage.reasoning.output_tokens")}
            key = attrs.get("gen_ai.response.id") or row.get("spanId")
            if not key:
                continue
            result.append({"agent": "copilot", "session": session, "key": key,
                           "timestamp": when, "model": _model(attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model")), "usage": usage})
    return result


def _ccusage_binary(root, environ):
    """Compatibility seam: no package discovery/execution in the author service."""
    return None



class MultiAgentUsage:
    """Every byte of transcript parsed must first belong to an explicit session."""
    def __init__(self, meter, project, root, *, environ=None, home=None, bindings=None,
                 selected_agent="auto", workspace_root=None):
        self.meter = meter
        self.project = Path(project).resolve()
        self.root = Path(root).resolve()
        self.environ = os.environ if environ is None else environ
        self.home = Path.home() if home is None else Path(home)
        self.selected_agent = normalize_agent(selected_agent)
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.path = self.meter.root / "multi-agent-auto.json"
        self.state = self._load()
        self.bind(bindings or {})

    def _base(self):
        return {"schema": STATE_SCHEMA, "status": "DISCOVERING", "sessions": {},
                "bindings": {}, "agents": [], "events_added": 0, "duplicates": 0,
                "reset_gaps": 0, "gaps": {}, "event_phases": {},
                "scope": "PROJECT_OWNED_BOUND_SESSIONS_ONLY",
                "privacy": "persists session/model/timestamps/token counts only; no prompt/response text"}

    def _load(self):
        if not self.path.is_file() or self.path.is_symlink():
            return self._base()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._base()
        if value.get("schema") != STATE_SCHEMA or value.get("scope") not in {
                "EXPLICITLY_BOUND_SESSIONS_ONLY", "PROJECT_OWNED_BOUND_SESSIONS_ONLY"}:
            return self._base()
        value["scope"] = "PROJECT_OWNED_BOUND_SESSIONS_ONLY"
        return value

    def bind(self, bindings):
        if not isinstance(bindings, dict):
            raise ValueError("usage_sessions 必须是宿主到会话 ID 列表的映射。")
        known = {r["id"] for r in agent_catalog()} - {"auto", "other"}
        for agent, sessions in bindings.items():
            if agent not in known or not isinstance(sessions, list):
                raise ValueError("未知用量宿主或会话列表无效。")
            if self.selected_agent not in {"auto", agent}:
                raise ValueError("绑定宿主与本项目已选择的 Agent 不一致。")
            for session in sessions:
                if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", session):
                    raise ValueError("用量会话 ID 无效。")
            values = self.state.setdefault("bindings", {}).setdefault(agent, [])
            values[:] = sorted(set(values) | set(sessions))

    def _bind_verified_children(self, agent, candidates):
        if agent != "codex":
            return []
        started = self.meter.meta["started_at"]
        bound = set(self.state.get("bindings", {}).get(agent, []))
        added = []
        changed = True
        while changed:
            changed = False
            for row in candidates:
                sid = row.get("session_id")
                parent = row.get("parent_session_id")
                created = row.get("created_at")
                if (row.get("workspace_match") is True and row.get("is_child") is True
                        and isinstance(sid, str) and isinstance(parent, str)
                        and parent in bound and sid not in bound
                        and created is not None and created >= started):
                    bound.add(sid)
                    added.append(sid)
                    changed = True
        if added:
            self.bind({agent: added})
            known = self.state.setdefault("auto_bound_children", {}).setdefault(agent, [])
            known[:] = sorted(set(known) | set(added))
        return added

    def _save(self):
        self.meter.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _matches(session, bindings):
        return session in bindings

    def _gap(self, code, agent, session):
        self.state.setdefault("gaps", {})[_hash(code, agent, session)] = {
            "code": code, "agent": agent, "session": _hash(session)}
        self.state["reset_gaps"] = sum(g["code"] == "CUMULATIVE_RESET" for g in self.state["gaps"].values())

    def _record(self, item, phase):
        agent, session, key = item["agent"], item["session"], str(item["key"])
        source = f"agent:{_hash(agent)}:{_hash(session)}"
        event_id = _event_id(agent, session, key)
        observed_phase = phase if phase in PHASES else "unattributed"
        stored_phase = self.state.setdefault("event_phases", {}).setdefault(event_id, observed_phase)
        self.meter.register(source, "agent-usage")
        value = {"event_id": event_id, "phase": stored_phase, "model": _model(item["model"]),
                 "outcome": "unknown", "usage": item["usage"], "duration_seconds": None, "retry_of": None}
        if item.get("gap"):
            self._gap(item["gap"], agent, session)
        if item["usage"] is None:
            self._gap("MISSING_OR_UNSUPPORTED_USAGE", agent, session)
        result = self.meter.ingest(source, [value])
        self.state["events_added"] += result["added"]
        self.state["duplicates"] += result["duplicates"]
        if item["usage"] is not None:
            self.state.setdefault("known_usage_sessions", {})[_hash(agent, session)] = {
                "agent": agent, "session": _hash(session)}

    def _snapshot(self, item, phase):
        key = _hash(item["agent"], item["session"], item["key"])
        old = self.state.setdefault("snapshots", {}).get(key)
        delta = _delta(item["usage"], old)
        if delta is None:
            self._gap("CUMULATIVE_RESET", item["agent"], item["session"])
            return
        if delta:
            self._record({**item, "usage": delta, "key": item["key"] + ":" + _hash(item["usage"])}, phase)
        self.state["snapshots"][key] = item["usage"]

    def _codex_roots(self, roots, bindings):
        files = []
        for root in roots:
            for session in bindings:
                for pattern in (f"sessions/*/*/*/rollout-*-{session}.jsonl",
                                f"archived_sessions/rollout-*-{session}.jsonl"):
                    files.extend(p for p in root.glob(pattern) if p.is_file() and not p.is_symlink())
        safe = []
        for path in dict.fromkeys(files):
            key = _hash(path.name)
            stat = path.stat()
            previous = self.state.setdefault("file_state", {}).get(key)
            now = {"size": stat.st_size, "inode": stat.st_ino}
            if previous and (now["size"] < previous["size"] or now["inode"] != previous["inode"]):
                self._gap("LOG_REPLACED_OR_TRUNCATED", "codex", path.stem)
                continue
            self.state["file_state"][key] = now
            safe.append(path)
        return safe

    def _events(self, agent, roots, bindings):
        start = self.meter.meta["started_at"]
        if agent == "codex":
            return _codex_events(self._codex_roots(roots, bindings), start)
        if agent == "opencode":
            return _opencode_events(roots, start, bindings)
        if agent == "copilot":
            return _copilot_scoped_events(roots, bindings, start)
        if agent == "cursor":
            return []
        files = session_files(agent, roots, bindings)
        if agent == "claude":
            return _claude_like_events(agent, [p for _, p in files], start)
        if agent == "gemini":
            return _gemini_events([p for _, p in files], start)
        if agent == "kimi":
            return _kimi_events(files, start)
        if agent in {"cline", "roo"}:
            return _task_events(agent, files, start)
        return []

    def ingest_ccusage(self, agent, session_id, report):
        """Import one explicitly selected session snapshot, never report totals."""
        agent = normalize_agent(agent)
        if session_id not in self.state.get("bindings", {}).get(agent, []):
            raise ValueError("请先明确绑定这份 ccusage 报告对应的宿主会话。")
        if agent not in {"codex", "claude", "gemini", "opencode", "copilot", "kimi"}:
            raise ValueError("该宿主不在已核实的 ccusage 来源支持范围。")
        if not isinstance(report, dict):
            raise ValueError("ccusage 报告必须是 JSON 对象。")
        rows = report.get("sessions", report.get("session"))
        if rows is None and report.get("sessionId"):
            rows = [report]
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("只接收一个明确 session 的 ccusage JSON，不接收账户或日期总计。")
        row = rows[0]
        if row.get("sessionId") != session_id or row.get("agent", agent) != agent:
            raise ValueError("ccusage 报告与绑定 Agent/session 不一致。")
        owner = _hash(agent, session_id)
        if self.state.setdefault("backend_by_session", {}).get(owner) == "builtin":
            raise ValueError("该会话已自动采集，不能再次导入同一会话的 ccusage 总计。")
        values = normalize("ccusage-session", row)
        usage = {"input_tokens": values["input_tokens"], "output_tokens": values["output_tokens"],
                 "total_tokens": values["total_tokens"], "cached_input_tokens": values["cached_input_tokens"],
                 "cache_write_tokens": values["cache_write_tokens"], "reasoning_output_tokens": values["reasoning_tokens"]}
        first, last = _ts(row.get("firstActivity")), _ts(row.get("lastActivity"))
        if last is None or last < self.meter.meta["started_at"]:
            raise ValueError("报告缺少本轮可核实的 lastActivity。")
        old = self.state.setdefault("ccusage_snapshots", {}).get(owner)
        if old is None and not (first is not None and first >= self.meter.meta["started_at"]):
            old = usage
            self._gap("NO_PROJECT_START_BASELINE", agent, session_id)
        delta = _delta(usage, old)
        if delta is None:
            self._gap("CUMULATIVE_RESET", agent, session_id)
        elif delta:
            models = row.get("modelsUsed") or []
            self._record({"agent": agent, "session": session_id, "key": "ccusage:" + _hash(usage),
                "model": models[0] if len(models) == 1 else "unknown", "usage": delta}, "unattributed")
        self.state["ccusage_snapshots"][owner] = usage
        self.state["backend_by_session"][owner] = "ccusage-import"
        self.state.setdefault("imported_sessions", {})[owner] = {"agent": agent, "session": _hash(session_id)}
        self._save()
        return self.sync()

    def sync(self, phase=None):
        if self.meter.meta["state"] != "RUNNING":
            return self.status()
        phase = phase or self.meter.meta.get("phase") or "unattributed"
        detected = detect_agents(self.home, self.environ)
        self.state["agents"] = [{k: row[k] for k in ("id", "label", "mode", "detected", "detection_basis")} for row in detected]
        self.state["ccusage"] = {"available": False, "mode": "explicit_session_json_import", "reviewed_version": "20.0.24"}
        active = list(self.state.get("imported_sessions", {}).values())
        missing = []
        try:
            selected = next(row for row in detected if row["id"] == self.selected_agent)
            candidates = project_candidates(self.selected_agent, self.workspace_root,
                [Path(p) for p in selected["roots"]], self.home, self.environ)
            self.state["session_candidates"] = candidates
            self._bind_verified_children(self.selected_agent, candidates)
            # Only auto-bind a uniquely identified current workspace session started
            # during this project. Existing/multiple sessions require host confirmation.
            if self.selected_agent != "cursor" and not self.state.get("bindings", {}).get(self.selected_agent):
                eligible = [r for r in candidates if r.get("created_at") is not None and
                            r["created_at"] >= self.meter.meta["started_at"] and not r.get("is_child")]
                if len(candidates) == 1 and len(eligible) == 1:
                    self.bind({self.selected_agent: [eligible[0]["session_id"]]})
            if self.selected_agent == "cursor":
                missing.append({"agent": "cursor", "session": "ide", "code": "CURSOR_IDE_USAGE_UNAVAILABLE"})
            supported = {"codex", "claude", "gemini", "opencode", "copilot", "kimi", "cline", "roo"}
            for info in detected:
                agent = info["id"]
                bindings = self.state.get("bindings", {}).get(agent, [])
                if self.selected_agent not in {"auto", agent} or not bindings:
                    continue
                local = [sid for sid in bindings if self.state.get("backend_by_session", {}).get(_hash(agent, sid)) != "ccusage-import"]
                if not local:
                    continue
                if agent == "cursor":
                    continue
                if agent not in supported:
                    missing += [{"agent": agent, "session": _hash(sid), "code": "UNSUPPORTED_BOUND_HOST"} for sid in local]
                    continue
                events = self._events(agent, [Path(p) for p in info["roots"]], local)
                seen = set()
                for item in events:
                    if item["session"] not in local:
                        continue
                    if item.get("timestamp") is None:
                        missing.append({"agent": agent, "session": _hash(item["session"]), "code": "MISSING_USAGE_TIMESTAMP"})
                        continue
                    if item["usage"] is None and item.get("gap") == "CURSOR_USAGE_NOT_REPORTED":
                        missing.append({"agent": agent, "session": _hash(item["session"]), "code": "CURSOR_USAGE_NOT_REPORTED"})
                        continue
                    if item.get("snapshot") and item["usage"] is not None:
                        self._snapshot(item, phase)
                    else:
                        self._record(item, phase)
                    self.state.setdefault("backend_by_session", {})[_hash(agent, item["session"])] = "builtin"
                    seen.add(item["session"])
                for sid in local:
                    if sid not in seen:
                        code = ("CURSOR_USAGE_NOT_REPORTED" if sid in {r["session_id"] for r in candidates} else "BOUND_SESSION_WORKSPACE_MISMATCH") if agent == "cursor" else "BOUND_SESSION_NOT_OBSERVED"
                        missing.append({"agent": agent, "session": _hash(sid), "code": code})
                active.extend({"agent": agent, "session": _hash(sid)} for sid in seen)
            self.state["active_sessions"] = list({(r["agent"], r["session"]): r for r in active}.values())
            self.state["pending_bindings"] = list({(r["agent"], r["session"], r["code"]): r for r in missing}.values())
            known = self.state.get("known_usage_sessions", {}).values()
            known_active = any(row in known for row in self.state["active_sessions"])
            if known_active:
                self.state["status"] = "CONNECTED_PARTIAL" if missing or self.state.get("gaps") else "CONNECTED_BUILTIN"
            else:
                self.state["status"] = "WAITING_FOR_USAGE" if missing or active else "NO_BOUND_SESSIONS"
            self.state["backend"] = "scoped-local+explicit-ccusage-json"
        except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error) as exc:
            self.state["status"] = "ERROR"
            self.state["error"] = type(exc).__name__
            self._gap("AUTO_CAPTURE_ERROR", "adapter", "unknown")
        self._save()
        return self.status()

    def status(self):
        info = agent_info(self.selected_agent)
        active = self.state.get("active_sessions", [])
        known = [row for row in self.state.get("known_usage_sessions", {}).values()
                 if self.selected_agent in {"auto", row["agent"]}]
        gaps = list(self.state.get("gaps", {}).values()) + self.state.get("pending_bindings", [])
        bound = sum(len(v) for k, v in self.state.get("bindings", {}).items() if self.selected_agent in {"auto", k})
        code, message, action = "SESSION_BINDING_REQUIRED", "尚未绑定本轮宿主会话，token 不是 0。", "bind_session"
        if self.selected_agent == "auto" and not bound:
            code, message, action = "AGENT_SELECTION_REQUIRED", "请选择创作使用的 Agent，并由宿主绑定本轮会话。", "select_agent"
        elif self.selected_agent in {"cursor", "windsurf", "trae", "augment", "other"}:
            code, message, action = "EXPLICIT_USAGE_REQUIRED", info["help"], "import_usage"
        elif self.state.get("status") == "ERROR":
            code, message, action = "CAPTURE_ERROR", "采集遇到格式或来源错误；查看采集缺口并提供原始 usage。", "inspect_source"
        elif active and known:
            code, message, action = "RECORDED_PARTIAL", "已记录绑定来源的真实用量；缺失字段和未绑定子代理仍不在覆盖内。", "bind_children_or_import_missing"
        elif active and not known and any(g["code"] == "NO_PROJECT_START_BASELINE" for g in gaps):
            code, message, action = "BASELINE_CAPTURED", "已保存旧会话累计基线，尚无可归属本轮的已知差额；请提供后续真实用量快照。", "check_requirements"
        elif active or bound:
            code, message, action = "WAITING_FOR_USAGE", "会话已绑定，尚未读到本轮可核实 usage。请核对日志条件或导入本轮真实 usage。", "check_requirements"
        return {"schema": STATE_SCHEMA, "status": self.state.get("status"), "backend": self.state.get("backend"),
                "selected_agent": self.selected_agent, "agent": info,
                "connection": {"code": code, "message": message, "action": action,
                    "action_label": {"bind_session": "绑定本轮宿主会话", "select_agent": "选择创作使用的 Agent",
                        "import_usage": "导入本轮真实 usage", "inspect_source": "检查来源和计量缺口",
                        "bind_children_or_import_missing": "绑定子代理或补充缺失用量",
                        "check_requirements": "核对日志条件或导入真实用量"}[action], "requirements": info["requirements"]},
                "session_candidates": self.state.get("session_candidates", []),
                "ccusage": self.state.get("ccusage"), "scope": self.state["scope"], "privacy": self.state["privacy"],
                "detected_agents": [r for r in self.state.get("agents", []) if r.get("detected")],
                "active_sessions": active, "events_added": self.state.get("events_added", 0),
                "duplicates": self.state.get("duplicates", 0), "reset_gaps": self.state.get("reset_gaps", 0),
                "gaps": gaps, "bound_session_count": bound,
                "auto_bound_child_count": sum(len(v) for v in self.state.get("auto_bound_children", {}).values()),
                "unbound_children_covered": False}
