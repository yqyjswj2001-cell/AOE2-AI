"""Automatic multi-agent usage collection for Author Studio.

Design:
- Built-in, standard-library parsers cover common local agents with explicit
  token fields: Codex, Claude Code, Cursor, Windsurf, Cline, Roo Code, Aider,
  Continue and Gemini CLI.
- If a local ccusage executable is available, its unified JSON session report
  is used for the broader agent ecosystem (OpenCode, Copilot CLI, Amp, Droid,
  Goose, Kimi, Qwen, Kilo, etc.).
- Detection is broader than accounting. An agent can be DETECTED_UNMETERED when
  its local files exist but no reliable token format is available.
- No transcript/prompt/response content is persisted. Only source/session IDs,
  model labels, timestamps and token counters enter Meter.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess

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


def _windows_appdata(home, environ):
    roaming = environ.get("APPDATA")
    base = Path(roaming) if roaming else home / "AppData/Roaming"
    return base


def registry(home=None, environ=None):
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    xdg_data = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    appdata = _windows_appdata(home, env)
    def paths(*values):
        return [Path(v).expanduser() for v in values if v]
    def list_paths(value):
        if not value:
            return []
        return [Path(v.strip()).expanduser() for v in str(value).split(",") if v.strip()]
    return [
        {"id":"claude","label":"Claude Code","mode":"builtin+ccusage",
         "roots":paths(env.get("CLAUDE_CONFIG_DIR"), home/".claude/projects", home/".config/claude/projects")},
        {"id":"claude-desktop","label":"Claude Desktop Agent","mode":"builtin",
         "roots":paths(appdata/"Claude/local-agent-mode-sessions",
                       home/"Library/Application Support/Claude/local-agent-mode-sessions")},
        {"id":"codex","label":"OpenAI Codex","mode":"builtin+ccusage",
         "roots":paths(env.get("CODEX_HOME"), home/".codex")},
        {"id":"gemini","label":"Gemini CLI","mode":"builtin+ccusage",
         "roots":paths(env.get("GEMINI_DATA_DIR"), home/".gemini/tmp")},
        {"id":"cursor","label":"Cursor","mode":"builtin",
         "roots":paths(home/".cursor/projects", appdata/"Cursor/User/workspaceStorage")},
        {"id":"windsurf","label":"Windsurf","mode":"builtin",
         "roots":paths(home/".windsurf", home/".codeium/windsurf", appdata/"Windsurf/User/workspaceStorage")},
        {"id":"cline","label":"Cline","mode":"builtin",
         "roots":paths(home/".cline", appdata/"Code/User/globalStorage/saoudrizwan.claude-dev",
                       appdata/"Cursor/User/globalStorage/saoudrizwan.claude-dev")},
        {"id":"roo","label":"Roo Code","mode":"builtin",
         "roots":paths(home/".roo-code", appdata/"Code/User/globalStorage/rooveterinaryinc.roo-cline",
                       appdata/"Cursor/User/globalStorage/rooveterinaryinc.roo-cline")},
        {"id":"aider","label":"Aider","mode":"builtin",
         "roots":paths(home/".aider", home/".aider/logs")},
        {"id":"continue","label":"Continue","mode":"builtin",
         "roots":paths(home/".continue/sessions")},
        {"id":"opencode","label":"OpenCode","mode":"builtin+ccusage",
         "roots":list_paths(env.get("OPENCODE_DATA_DIR")) + paths(xdg_data/"opencode")},
        {"id":"copilot","label":"GitHub Copilot CLI","mode":"builtin+ccusage",
         "roots":paths(env.get("COPILOT_HOME"), home/".copilot",
                       env.get("COPILOT_OTEL_FILE_EXPORTER_PATH"))},
        {"id":"amp","label":"Amp","mode":"ccusage",
         "roots":paths(env.get("AMP_DATA_DIR"), xdg_data/"amp")},
        {"id":"droid","label":"Factory Droid","mode":"ccusage",
         "roots":paths(env.get("DROID_SESSIONS_DIR"), home/".factory/sessions")},
        {"id":"codebuff","label":"Codebuff","mode":"ccusage",
         "roots":paths(env.get("CODEBUFF_DATA_DIR"), home/".config/manicode")},
        {"id":"hermes","label":"Hermes Agent","mode":"ccusage",
         "roots":paths(env.get("HERMES_HOME"), home/".hermes")},
        {"id":"pi","label":"pi-agent","mode":"ccusage",
         "roots":paths(env.get("PI_AGENT_DIR"), home/".pi/agent/sessions")},
        {"id":"goose","label":"Goose","mode":"ccusage",
         "roots":paths(env.get("GOOSE_PATH_ROOT"), home/".config/goose", xdg_data/"goose")},
        {"id":"openclaw","label":"OpenClaw","mode":"ccusage",
         "roots":paths(env.get("OPENCLAW_DIR"), home/".openclaw")},
        {"id":"kilo","label":"Kilo Code","mode":"ccusage",
         "roots":paths(env.get("KILO_DATA_DIR"), xdg_data/"kilo")},
        {"id":"kimi","label":"Kimi Code","mode":"ccusage",
         "roots":paths(env.get("KIMI_DATA_DIR"), home/".kimi", home/".kimi-code")},
        {"id":"qwen","label":"Qwen Code","mode":"ccusage",
         "roots":paths(env.get("QWEN_DATA_DIR"), home/".qwen")},
        {"id":"antigravity","label":"Antigravity","mode":"ccusage",
         "roots":paths(env.get("ANTIGRAVITY_DATA_DIR"), home/".config/antigravity", home/".gemini")},
        {"id":"grok","label":"Grok Build CLI","mode":"ccusage",
         "roots":paths(env.get("GROK_HOME"), home/".grok")},
        {"id":"zcode","label":"ZCode","mode":"ccusage",
         "roots":paths(env.get("ZCODE_HOME"), home/".zcode")},
        # Detection-only: formats currently lack a stable audited token contract here.
        {"id":"kiro","label":"Kiro","mode":"detected",
         "roots":paths(home/".kiro", appdata/"Kiro")},
        {"id":"trae","label":"Trae","mode":"detected",
         "roots":paths(home/".trae", appdata/"Trae")},
        {"id":"qoder","label":"Qoder","mode":"detected",
         "roots":paths(home/".qoder", appdata/"Qoder")},
        {"id":"junie","label":"JetBrains Junie","mode":"detected",
         "roots":paths(home/".junie")},
        {"id":"augment","label":"Augment","mode":"detected",
         "roots":paths(home/".augment", appdata/"Augment")},
    ]


def detect_agents(home=None, environ=None):
    rows = []
    for row in registry(home, environ):
        existing = []
        for root in row["roots"]:
            try:
                if root.exists():
                    existing.append(str(root))
            except OSError:
                pass
        rows.append({"id":row["id"],"label":row["label"],"mode":row["mode"],
                     "detected":bool(existing),"roots":existing})
    return rows


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
                           "usage":_norm_usage(inp,out,cr,cw,0)})
    return events


def _aider_events(roots, started_at):
    events=[]
    for path in _recent_files(roots,{".jsonl",".json"},started_at):
        session=path.stem
        for index,row in _iter_jsonl(path):
            usage=row.get("usage") or (row.get("response") or {}).get("usage")
            if not isinstance(usage,dict): continue
            when=_ts(row.get("timestamp") or row.get("created"))
            if when is not None and when < started_at-SKEW_SECONDS: continue
            inp=_count(usage.get("prompt_tokens") or usage.get("input_tokens"))
            out=_count(usage.get("completion_tokens") or usage.get("output_tokens"))
            cr=_count(usage.get("cache_read_input_tokens")); cw=_count(usage.get("cache_creation_input_tokens"))
            if not any((inp,out,cr,cw)): continue
            events.append({"agent":"aider","session":session,"key":row.get("id") or f"{path.name}:{index}",
                           "timestamp":when,"model":_model(row.get("model")),
                           "usage":_norm_usage(inp,out,cr,cw,0)})
    return events


def _continue_events(roots, started_at):
    events=[]
    for path in _recent_files(roots,{".json"},started_at):
        try:
            data=json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError,UnicodeError,json.JSONDecodeError):
            continue
        if not isinstance(data,dict): continue
        steps=data.get("steps") or data.get("history") or []
        if not isinstance(steps,list): continue
        for index,step in enumerate(steps):
            if not isinstance(step,dict): continue
            usage=step.get("usage") if isinstance(step.get("usage"),dict) else {}
            inp=_count(usage.get("input_tokens") or step.get("promptTokens"))
            out=_count(usage.get("output_tokens") or step.get("completionTokens"))
            if not inp and not out: continue
            when=_ts(step.get("timestamp") or data.get("dateCreated"))
            if when is not None and when < started_at-SKEW_SECONDS: continue
            events.append({"agent":"continue","session":path.stem,
                           "key":step.get("id") or f"{path.name}:{index}","timestamp":when,
                           "model":_model(step.get("model") or data.get("model")),
                           "usage":_norm_usage(inp,out)})
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
        if path.suffix.lower()==".jsonl":
            records=[row for _,row in _iter_jsonl(path)]
        else:
            try:
                doc=json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError,UnicodeError,json.JSONDecodeError):
                continue
            if isinstance(doc,dict) and isinstance(doc.get("messages"),list):
                records=doc["messages"]
            elif isinstance(doc,dict):
                records=[doc]
        session=path.stem
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
            "model":_model(model_name),"usage":_norm_usage(inp,out,cr,cw,reasoning,total)}


def _sqlite_columns(db, table):
    try:
        return {str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _opencode_db_events(root, started_at):
    events=[]; seen=set()
    candidates=[]
    try:
        direct=root/"opencode.db"
        if direct.is_file(): candidates.append(direct)
        candidates.extend(p for p in root.glob("opencode-*.db") if p.is_file() and not p.is_symlink())
    except OSError:
        return events
    start_ms=int((started_at-SKEW_SECONDS)*1000)
    for path in dict.fromkeys(candidates):
        try:
            db=sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro",uri=True,timeout=1)
        except (sqlite3.Error,OSError):
            continue
        try:
            cols=_sqlite_columns(db,"message")
            if {"id","session_id","data"} <= cols:
                if "time_created" in cols:
                    query="SELECT id,session_id,data,time_created FROM message WHERE time_created>=? ORDER BY time_created"
                    rows=db.execute(query,(start_ms,))
                else:
                    rows=db.execute("SELECT id,session_id,data,NULL FROM message ORDER BY rowid DESC LIMIT 5000")
                for mid,sid,data,created in rows:
                    try: row=json.loads(data)
                    except (TypeError,json.JSONDecodeError): continue
                    event=_opencode_message("opencode",row,mid,sid,created,started_at)
                    if event and event["key"] not in seen:
                        seen.add(event["key"]); events.append(event)
            cols=_sqlite_columns(db,"session_message")
            if {"id","session_id","type","data"} <= cols:
                if "time_created" in cols:
                    rows=db.execute("SELECT id,session_id,type,data,time_created FROM session_message WHERE time_created>=? AND type='assistant' ORDER BY time_created",(start_ms,))
                else:
                    rows=db.execute("SELECT id,session_id,type,data,NULL FROM session_message WHERE type='assistant' ORDER BY rowid DESC LIMIT 5000")
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


def _opencode_events(roots, started_at):
    events=[]; seen=set()
    for root in roots:
        if not root.is_dir():
            continue
        for event in _opencode_db_events(root,started_at):
            marker=(event["session"],event["key"])
            if marker not in seen:
                seen.add(marker); events.append(event)
        message_root=root/"storage/message"
        for path in _recent_files([message_root],{".json"},started_at):
            try: row=json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError,UnicodeError,json.JSONDecodeError): continue
            event=_opencode_message("opencode",row,path.stem,path.parent.name,None,started_at)
            if event:
                marker=(event["session"],event["key"])
                if marker not in seen:
                    seen.add(marker); events.append(event)
    return events


def _number(value):
    if type(value) is int and value>=0:
        return value
    if isinstance(value,str):
        try:
            parsed=int(value)
            return parsed if parsed>=0 else _UnknownCount(0)
        except ValueError:
            return _UnknownCount(0)
    return _UnknownCount(0)


def _copilot_timestamp(row):
    for key in ("endTime","startTime","hrTime","_hrTime","time"):
        value=row.get(key)
        if isinstance(value,list) and len(value)>=2:
            sec=_number(value[0]); nanos=_number(value[1])
            if sec: return sec+nanos/1_000_000_000
    for key in ("timestamp","observedTimestamp"):
        value=row.get(key)
        if isinstance(value,str):
            parsed=_ts(value)
            if parsed is not None: return parsed
        raw=_number(value)
        if raw:
            if raw>=100_000_000_000_000_000: return raw/1_000_000_000
            if raw>=100_000_000_000_000: return raw/1_000_000
            if raw>=100_000_000_000: return raw/1000
            return raw
    raw=_number(row.get("timeUnixNano"))
    return raw/1_000_000_000 if raw else None


def _copilot_session_id(attrs,row):
    for key in ("gen_ai.conversation.id","copilot_chat.session_id","copilot_chat.chat_session_id",
                "session.id","github.copilot.interaction_id","gen_ai.response.id"):
        value=attrs.get(key) if isinstance(attrs,dict) else None
        if isinstance(value,str) and value.strip(): return value.strip()
    for key in ("traceId","trace_id"):
        value=row.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    return "unknown-session"


def _copilot_model(attrs):
    for key in ("gen_ai.response.model","gen_ai.request.model"):
        value=attrs.get(key) if isinstance(attrs,dict) else None
        if isinstance(value,str) and value.strip():
            value=value.strip()
            for suffix in ("-1m-internal","-1m"):
                if value.endswith(suffix): value=value[:-len(suffix)]
            return _model(value)
    return "unknown"


def _copilot_otel_events(root, started_at):
    events=[]; seen=set()
    files=[]
    explicit=root if root.is_file() else None
    if explicit:
        files=[explicit]
    elif root.is_dir():
        files=_recent_files([root/"otel"],{".jsonl"},started_at)
    for path in files:
        for index,row in _iter_jsonl(path):
            attrs=row.get("attributes")
            if not isinstance(attrs,dict): continue
            inp=_number(attrs.get("gen_ai.usage.input_tokens"))
            out=_number(attrs.get("gen_ai.usage.output_tokens"))
            cr=_number(attrs.get("gen_ai.usage.cache_read.input_tokens"))
            cw=_number(attrs.get("gen_ai.usage.cache_write.input_tokens") or attrs.get("gen_ai.usage.cache_creation.input_tokens"))
            reasoning=_number(attrs.get("gen_ai.usage.reasoning.output_tokens") or attrs.get("gen_ai.usage.reasoning_tokens"))
            total=_number(attrs.get("gen_ai.usage.total_tokens") or attrs.get("gen_ai.usage.total.token_count"))
            if not any((inp,out,cr,cw,reasoning,total)): continue
            when=_copilot_timestamp(row)
            if when is not None and when<started_at-SKEW_SECONDS: continue
            session=_copilot_session_id(attrs,row)
            response=attrs.get("gen_ai.response.id")
            trace=row.get("traceId") or row.get("trace_id")
            span=row.get("spanId") or row.get("span_id")
            key=str(response or (str(trace)+":"+str(span) if trace and span else f"{path.name}:{index}:{when}"))
            marker=(session,key)
            if marker in seen: continue
            seen.add(marker)
            uncached=max(0,inp-min(inp,cr)) if type(inp) is int and type(out) is int else None
            usage=_norm_usage(uncached,out,cr,cw,reasoning,total or None)
            events.append({"agent":"copilot","session":session,"key":key,"timestamp":when,
                           "model":_copilot_model(attrs),"usage":usage})
    return events


def _copilot_shutdown_events(root, started_at, covered_sessions):
    events=[]
    if not root.is_dir(): return events
    state_root=root/"session-state"
    for path in _recent_files([state_root],{".jsonl"},started_at):
        if path.name!="events.jsonl": continue
        session=path.parent.name
        if session in covered_sessions: continue
        first=None; shutdowns=[]
        for index,row in _iter_all_jsonl(path):
            when=_ts(row.get("timestamp"))
            if when is not None and (first is None or when<first): first=when
            if row.get("type")=="session.shutdown": shutdowns.append((index,when,row))
        # A pre-existing session can contain usage from before this creation. Without
        # request-level OTEL, do not charge the cumulative shutdown total.
        if first is None or first<started_at-SKEW_SECONDS: continue
        for index,when,row in shutdowns:
            if when is not None and when<started_at-SKEW_SECONDS: continue
            data=row.get("data") if isinstance(row.get("data"),dict) else {}
            metrics=data.get("modelMetrics") if isinstance(data.get("modelMetrics"),dict) else {}
            for model,value in metrics.items():
                usage=value.get("usage") if isinstance(value,dict) and isinstance(value.get("usage"),dict) else {}
                inp=_number(usage.get("inputTokens")); out=_number(usage.get("outputTokens"))
                cr=_number(usage.get("cacheReadTokens")); cw=_number(usage.get("cacheWriteTokens"))
                reasoning=_number(usage.get("reasoningTokens"))
                if not any((inp,out,cr,cw,reasoning)): continue
                uncached=max(0,inp-min(inp,cr+cw)) if type(inp) is int and type(out) is int else None
                key=f"shutdown:{row.get('id') or index}:{model}"
                events.append({"agent":"copilot","session":session,"key":key,"timestamp":when,
                               "model":_model(model),"usage":_norm_usage(uncached,out,cr,cw,reasoning)})
    return events


def _copilot_events(roots, started_at):
    otel=[]; home_roots=[]
    for root in roots:
        if root.is_file():
            otel.extend(_copilot_otel_events(root,started_at))
        elif root.is_dir():
            home_roots.append(root)
            otel.extend(_copilot_otel_events(root,started_at))
    covered={event["session"] for event in otel}
    events=list(otel)
    for root in home_roots:
        events.extend(_copilot_shutdown_events(root,started_at,covered))
    return events


BUILTIN_PARSERS={
    "claude":_claude_like_events,"cursor":_claude_like_events,"windsurf":_claude_like_events,
    "cline":_claude_like_events,"roo":_claude_like_events,
    "aider":lambda _id,roots,start:_aider_events(roots,start),
    "continue":lambda _id,roots,start:_continue_events(roots,start),
    "codex":lambda _id,roots,start:_codex_events(roots,start),
    "gemini":lambda _id,roots,start:_gemini_events(roots,start),
    "opencode":lambda _id,roots,start:_opencode_events(roots,start),
    "copilot":lambda _id,roots,start:_copilot_events(roots,start),
    "claude-desktop":_claude_like_events,
}


def _ccusage_binary(root, environ):
    explicit=environ.get("AOE2_CCUSAGE_BIN") or environ.get("CCUSAGE_BIN")
    candidates=[]
    if explicit: candidates.append(Path(explicit))
    name="ccusage.exe" if os.name=="nt" else "ccusage"
    machine=platform.machine().lower()
    plat=("win32" if os.name=="nt" else "darwin" if sys_platform()=="darwin" else "linux")
    arch="arm64" if machine in ("arm64","aarch64") else "x64"
    candidates.append(Path(root)/"tools/author_agent/vendor/ccusage"/f"{plat}-{arch}"/name)
    path=shutil.which("ccusage")
    if path: candidates.append(Path(path))
    for candidate in candidates:
        try:
            if candidate.is_file() and not candidate.is_symlink():
                return candidate.resolve()
        except OSError:
            pass
    return None


def sys_platform():
    import sys
    return sys.platform


def _ccusage_sessions(binary):
    cmd=[str(binary),"session","--json","--offline","--no-cost"]
    run=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
    if run.returncode!=0:
        raise RuntimeError("ccusage exit "+str(run.returncode))
    data=json.loads(run.stdout)
    if isinstance(data.get("session"),list): rows=data["session"]
    elif isinstance(data.get("sessions"),list): rows=data["sessions"]
    elif isinstance(data.get("data"),list): rows=data["data"]
    else: rows=[]
    result=[]
    for row in rows:
        if not isinstance(row,dict): continue
        agent=row.get("agent") or "unknown"
        session=row.get("sessionId") or row.get("session") or row.get("period")
        if not isinstance(session,str): continue
        metadata=row.get("metadata") if isinstance(row.get("metadata"),dict) else {}
        first=_ts(row.get("firstActivity") or metadata.get("firstActivity"))
        last=_ts(row.get("lastActivity") or metadata.get("lastActivity"))
        inp=_count(row.get("inputTokens")); out=_count(row.get("outputTokens"))
        cr=_count(row.get("cacheReadTokens")); cw=_count(row.get("cacheCreationTokens"))
        total=_count(row.get("totalTokens"))
        reasoning=_count(row.get("reasoningOutputTokens") or metadata.get("reasoningOutputTokens"))
        if not any((inp,out,cr,cw,total)): continue
        models=row.get("modelsUsed") or row.get("models") or []
        model=_model(models[0] if isinstance(models,list) and len(models)==1 else f"{agent}:mixed")
        usage=_norm_usage(inp,out,cr,cw,reasoning,total or None)
        result.append({"agent":str(agent),"session":session,"first":first,"last":last,"model":model,"usage":usage})
    return result


class MultiAgentUsage:
    """Upstream multi-host parsers, restricted to explicitly owned sessions.

    bindings = {"codex": ["root UUID", "owned child UUID"], "claude": ["session ID"]}.
    The adapter adds CODEX_THREAD_ID automatically. A child is NOT inferred from time.
    Hosts must register every owned child and may declare complete coverage only after
    all those calls have ended. Detection of unrelated installed agents is metadata only.
    """
    def __init__(self, meter, project, root, *, environ=None, home=None, bindings=None):
        self.meter = meter
        self.project = Path(project).resolve()
        self.root = Path(root).resolve()
        self.environ = os.environ if environ is None else environ
        self.home = Path.home() if home is None else Path(home)
        self.path = self.meter.root / "multi-agent-auto.json"
        self.state = self._load()
        self.bind(bindings or {})

    def _base(self):
        return {"schema": STATE_SCHEMA, "status": "DISCOVERING", "sessions": {},
                "bindings": {}, "agents": [], "events_added": 0, "duplicates": 0,
                "reset_gaps": 0, "gaps": {}, "event_phases": {},
                "scope": "EXPLICITLY_BOUND_SESSIONS_ONLY",
                "privacy": "persists session/model/timestamps/token counts only; no prompt/response text"}

    def _load(self):
        if not self.path.is_file() or self.path.is_symlink():
            return self._base()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._base()
        # Do not migrate broad time-window state into project-owned accounting.
        return value if value.get("schema") == STATE_SCHEMA and value.get("scope") == "EXPLICITLY_BOUND_SESSIONS_ONLY" else self._base()

    def bind(self, bindings):
        if not isinstance(bindings, dict):
            raise ValueError("usage_sessions 必须是宿主到会话 ID 列表的映射。")
        known = {r["id"] for r in registry(self.home, self.environ)}
        for agent, sessions in bindings.items():
            if agent not in known or not isinstance(sessions, list):
                raise ValueError("未知用量宿主或会话列表无效。")
            for session in sessions:
                if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", session):
                    raise ValueError("用量会话 ID 无效。")
            values = self.state.setdefault("bindings", {}).setdefault(agent, [])
            values[:] = sorted(set(values) | set(sessions))

    def _save(self):
        self.meter.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _matches(session, bindings):
        return any(session == item or session.endswith("-" + item) for item in bindings)

    def _gap(self, code, agent, session):
        key = _hash(code, agent, session)
        self.state.setdefault("gaps", {})[key] = {"code": code, "agent": agent, "session": _hash(session)}
        self.state["reset_gaps"] = sum(g["code"] == "CUMULATIVE_RESET" for g in self.state["gaps"].values())

    def _record(self, item, phase):
        agent, session, key = item["agent"], item["session"], str(item["key"])
        source = f"agent:{_hash(agent)}:{_hash(session)}"
        event_id = _event_id(agent, session, key)
        # Re-reading a log after changing stages must not rewrite original attribution.
        stored_phase = self.state.setdefault("event_phases", {}).setdefault(event_id, "unattributed")
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

    def _codex_roots(self, roots, bindings):
        # Filename enumeration only; unrelated transcripts are never opened.
        files = []
        for root in roots:
            for session in bindings:
                for pattern in (f"sessions/*/*/*/rollout-*-{session}.jsonl",
                                f"archived_sessions/rollout-*-{session}.jsonl"):
                    files.extend(p for p in root.glob(pattern) if p.is_file() and not p.is_symlink())
        safe = []
        for path in files:
            key = _hash(path.name)
            stat = path.stat()
            previous = self.state.setdefault("file_state", {}).get(key)
            now = {"size": stat.st_size, "inode": stat.st_ino}
            if previous and (now["size"] < previous["size"] or now["inode"] != previous["inode"]):
                self._gap("LOG_REPLACED_OR_TRUNCATED", "codex", path.stem)
                continue  # retain old evidence; never reinterpret a rewritten file
            self.state["file_state"][key] = now
            safe.append(path)
        return safe

    def sync(self, phase=None):
        if self.meter.meta["state"] != "RUNNING":
            return self.status()
        phase = phase or self.meter.meta.get("phase") or "unattributed"
        detected = detect_agents(self.home, self.environ)
        self.state["agents"] = [{k: row[k] for k in ("id", "label", "mode", "detected")} for row in detected]
        active = []
        missing = []
        binary = _ccusage_binary(self.root, self.environ)
        self.state["ccusage"] = {"available": bool(binary), "binary": binary.name if binary else None}
        ccrows = None
        try:
            for info in detected:
                bindings = self.state.get("bindings", {}).get(info["id"], [])
                if not bindings:
                    continue
                roots = [Path(p) for p in info["roots"]]
                parser = BUILTIN_PARSERS.get(info["id"])
                if info["id"] == "codex":
                    roots = self._codex_roots(roots, bindings)
                if parser:
                    events = parser(info["id"], roots, self.meter.meta["started_at"])
                    owned = [e for e in events if self._matches(e["session"], bindings)]
                    for item in owned:
                        if item.get("timestamp") is None:
                            self._gap("MISSING_USAGE_TIMESTAMP", item["agent"], item["session"])
                            continue
                        self._record(item, phase)
                    seen = {e["session"] for e in owned}
                    for session in bindings:
                        if not any(self._matches(s, [session]) for s in seen):
                            missing.append({"agent": info["id"], "session": _hash(session), "code": "BOUND_SESSION_NOT_OBSERVED"})
                    active.extend({"agent": info["id"], "session": _hash(session)} for session in seen)
                elif binary:
                    if ccrows is None:
                        ccrows = _ccusage_sessions(binary)
                    for session in bindings:
                        matches = [r for r in ccrows if r["agent"] == info["id"] and self._matches(r["session"], [session])]
                        if not matches:
                            missing.append({"agent": info["id"], "session": _hash(session), "code": "BOUND_SESSION_NOT_OBSERVED"})
                        for row in matches:
                            key = _hash(row["agent"], row["session"])
                            old = self.state.setdefault("sessions", {}).get(key)
                            usage = row["usage"]
                            if usage is None:
                                self._gap("MISSING_OR_UNSUPPORTED_USAGE", row["agent"], row["session"])
                                continue
                            if old is None:
                                if row["first"] is not None and row["first"] >= self.meter.meta["started_at"]:
                                    old = {k: 0 for k in usage}
                                else:
                                    old = usage
                                    self._gap("NO_PROJECT_START_BASELINE", row["agent"], row["session"])
                            delta = _delta(usage, old)
                            if delta is None:
                                self._gap("CUMULATIVE_RESET", row["agent"], row["session"])
                            elif delta:
                                self._record({"agent": row["agent"], "session": row["session"],
                                              "key": "ccusage:" + _hash(usage), "model": row["model"],
                                              "usage": delta}, phase)
                            self.state["sessions"][key] = usage
                            active.append({"agent": row["agent"], "session": _hash(row["session"])})
                else:
                    missing.extend({"agent": info["id"], "session": _hash(session), "code": "UNSUPPORTED_BOUND_HOST"} for session in bindings)
            self.state["active_sessions"] = active
            self.state["pending_bindings"] = missing
            self.state["status"] = "CONNECTED_PARTIAL" if missing or self.state.get("gaps") else (
                "CONNECTED_BUILTIN" if active else "NO_BOUND_SESSIONS")
            self.state["backend"] = "builtin+optional-ccusage"
        except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            self.state["status"] = "ERROR"
            self.state["error"] = type(exc).__name__
            self._gap("AUTO_CAPTURE_ERROR", "adapter", "unknown")
        self._save()
        return self.status()

    def status(self):
        return {"schema": STATE_SCHEMA, "status": self.state.get("status"), "backend": self.state.get("backend"),
                "ccusage": self.state.get("ccusage"), "scope": self.state["scope"], "privacy": self.state["privacy"],
                "detected_agents": [r for r in self.state.get("agents", []) if r.get("detected")],
                "active_sessions": self.state.get("active_sessions", []),
                "events_added": self.state.get("events_added", 0), "duplicates": self.state.get("duplicates", 0),
                "reset_gaps": self.state.get("reset_gaps", 0),
                "gaps": list(self.state.get("gaps", {}).values()) + self.state.get("pending_bindings", []),
                "bound_session_count": sum(len(v) for v in self.state.get("bindings", {}).values()),
                "unbound_children_covered": False}
