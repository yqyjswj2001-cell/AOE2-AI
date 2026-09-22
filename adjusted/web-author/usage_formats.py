"""Provider usage normalization. No tokenizer/character estimates or model calls.

All normalized input includes cache reads/writes; output includes reasoning.
Detailed counters are subsets, not extra tokens to add to input + output.
See METERING.md for primary sources and adapters' explicit boundaries.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

FORMATS = {"openai-responses", "openai-chat", "anthropic-messages", "codex-exec", "agent-usage", "cursor-sdk", "ccusage-session"}
PHASES = {"0": "配置与准备", "1": "阅读策略卡", "3": "填写动态参数",
          "4": "检查与返工", "5": "整理交付", "unattributed": "未分阶段"}
COUNTERS = ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
            "cache_write_tokens", "reasoning_tokens")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identifier(value, name):
    require(isinstance(value, str) and SAFE_ID.fullmatch(value), name + " 必须是稳定的安全标识符。")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def count(value, field):
    require(type(value) is int and 0 <= value <= 10**12, field + " 必须是非负整数，不能是估算、布尔或缺失值。")
    return value


def duration(value):
    if value is None:
        return None
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 86400 * 365,
            "duration_seconds 无效。")
    return value


def normalize(format_name, raw):
    require(format_name in FORMATS, "不支持的 usage 格式。")
    if raw is None:
        return dict.fromkeys(COUNTERS)
    require(isinstance(raw, dict), "usage 必须是对象或 null。")
    cached = written = reasoning = None
    if format_name in {"cursor-sdk", "ccusage-session"}:
        inp, out = count(raw.get("inputTokens"), "inputTokens"), count(raw.get("outputTokens"), "outputTokens")
        cached = count(raw.get("cacheReadTokens"), "cacheReadTokens")
        written_key = "cacheWriteTokens" if format_name == "cursor-sdk" else "cacheCreationTokens"
        written = count(raw.get(written_key), written_key)
        inp += cached + written
        reasoning = raw.get("reasoningTokens", raw.get("reasoningOutputTokens"))
        total = count(raw.get("totalTokens"), "totalTokens")
        if format_name == "ccusage-session" and reasoning is not None and total == inp + out + reasoning:
            out += count(reasoning, "reasoningTokens")
        require(total == inp + out, "totalTokens 与输入、输出及缓存不一致。")
    elif format_name == "openai-chat":
        inp, out = raw.get("prompt_tokens"), raw.get("completion_tokens")
        i_detail, o_detail = raw.get("prompt_tokens_details") or {}, raw.get("completion_tokens_details") or {}
        require(isinstance(i_detail, dict) and isinstance(o_detail, dict), "usage details 格式错误。")
        cached, written, reasoning = i_detail.get("cached_tokens"), i_detail.get("cache_write_tokens"), o_detail.get("reasoning_tokens")
    else:
        inp, out = raw.get("input_tokens"), raw.get("output_tokens")
        if format_name == "agent-usage":
            cached = raw.get("cached_input_tokens")
            written = raw.get("cache_write_tokens")
            reasoning = raw.get("reasoning_output_tokens")
        elif format_name == "openai-responses":
            i_detail, o_detail = raw.get("input_tokens_details") or {}, raw.get("output_tokens_details") or {}
            require(isinstance(i_detail, dict) and isinstance(o_detail, dict), "usage details 格式错误。")
            cached, written, reasoning = i_detail.get("cached_tokens"), i_detail.get("cache_write_tokens"), o_detail.get("reasoning_tokens")
        elif format_name == "codex-exec":
            cached = raw.get("cached_input_tokens")
            reasoning = raw.get("reasoning_output_tokens")
        else:
            # Anthropic's input_tokens excludes BOTH cache-read and cache-write.
            # Require these fields explicitly; absent is unknown, not assumed zero.
            cached = count(raw.get("cache_read_input_tokens"), "cache_read_input_tokens")
            written = count(raw.get("cache_creation_input_tokens"), "cache_creation_input_tokens")
            inp = count(inp, "input_tokens") + cached + written
    inp, out = count(inp, "input_tokens"), count(out, "output_tokens")
    for key, value in (("cached_input_tokens", cached), ("cache_write_tokens", written), ("reasoning_tokens", reasoning)):
        if value is not None:
            count(value, key)
    require(cached is None or cached <= inp, "缓存读取不能超过总输入。")
    require(written is None or written <= inp, "缓存写入不能超过总输入。")
    require(cached is None or written is None or cached + written <= inp, "缓存分项超过总输入。")
    require(reasoning is None or reasoning <= out, "推理 token 不能超过总输出。")
    total = inp + out
    if raw.get("total_tokens") is not None:
        require(count(raw["total_tokens"], "total_tokens") == total, "total_tokens 与输入加输出不一致。")
    return dict(zip(COUNTERS, (inp, out, total, cached, written, reasoning)))


def usage_payload(format_name, raw):
    """Whitelist usage fields before transporting host data to the local service."""
    normalize(format_name, raw)
    if raw is None:
        return None
    base = {"input_tokens", "output_tokens", "total_tokens"}
    nested = {}
    if format_name in {"cursor-sdk", "ccusage-session"}:
        base = {"inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens", "cacheCreationTokens", "totalTokens", "reasoningTokens", "reasoningOutputTokens"}
    elif format_name == "openai-chat":
        base = {"prompt_tokens", "completion_tokens", "total_tokens"}
        nested = {"prompt_tokens_details": {"cached_tokens", "cache_write_tokens"},
                  "completion_tokens_details": {"reasoning_tokens"}}
    elif format_name == "openai-responses":
        nested = {"input_tokens_details": {"cached_tokens", "cache_write_tokens"},
                  "output_tokens_details": {"reasoning_tokens"}}
    elif format_name in {"codex-exec", "agent-usage"}:
        base |= {"cached_input_tokens", "reasoning_output_tokens"}
        if format_name == "agent-usage":
            base |= {"cache_write_tokens"}
    else:
        base |= {"cache_read_input_tokens", "cache_creation_input_tokens"}
    result = {key: raw[key] for key in base if key in raw}
    for key, fields in nested.items():
        if isinstance(raw.get(key), dict):
            result[key] = {f: raw[key][f] for f in fields if f in raw[key]}
    return result


def event(format_name, value):
    allowed = {"event_id", "phase", "model", "outcome", "usage", "duration_seconds", "retry_of"}
    require(isinstance(value, dict) and set(value) <= allowed and {"event_id", "usage"} <= set(value),
            "用量事件字段错误；只接收标识、计数与时间，不接收提示词或正文。")
    eid = identifier(value["event_id"], "event_id")
    phase = value.get("phase", "unattributed")
    require(phase in PHASES, "未知计量阶段。")
    model = value.get("model", "unknown")
    require(isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/+ -]{0,159}", model), "model 标识无效。")
    outcome = value.get("outcome", "succeeded")
    require(outcome in {"succeeded", "failed", "cancelled", "unknown"}, "未知调用结果。")
    retry = value.get("retry_of")
    if retry is not None:
        identifier(retry, "retry_of")
        require(retry != eid, "retry_of 不能指向自己。")
    return {"event_id": eid, "phase": phase, "model": model, "outcome": outcome,
            "duration_seconds": duration(value.get("duration_seconds")), "retry_of": retry,
            "unit": "usage_interval" if format_name == "agent-usage" else "turn" if format_name == "codex-exec" else "request",
            "usage": normalize(format_name, value["usage"])}


def response_event(format_name, raw, phase="unattributed"):
    """Extract ONLY final response usage; never sum streaming deltas/cumulative counters."""
    require(isinstance(raw, dict), "响应必须是 JSON 对象。")
    if format_name == "agent-usage":
        event(format_name, raw)
        return raw
    if format_name == "ccusage-session":
        raise ValueError("ccusage 是累计会话快照，必须经 usage --action ccusage 接入以扣除基线。")
    if format_name == "cursor-sdk":
        require(raw.get("status") in {"finished", "error", "cancelled"}, "只接收 Cursor SDK 最终 RunResult，不累加运行中快照。")
        return {"event_id": identifier(raw.get("id"), "Cursor run id"), "phase": phase,
                "model": raw.get("model", {}).get("id", "unknown") if isinstance(raw.get("model"), dict) else raw.get("model", "unknown"),
                "usage": raw.get("usage"), "outcome": {"finished": "succeeded", "error": "failed", "cancelled": "cancelled"}[raw["status"]]}
    if format_name == "openai-responses" and raw.get("type") in {"response.completed", "response.failed", "response.incomplete"}:
        raw = raw.get("response", {})
    require(format_name != "codex-exec", "Codex 需要逐轮解析，不是 API response。")
    require(isinstance(raw, dict), "缺少完整 response。")
    if format_name == "openai-responses":
        require(raw.get("status") in {"completed", "failed", "incomplete", "cancelled"}, "只接收最终 Responses usage。")
    elif format_name == "openai-chat":
        require(raw.get("object") == "chat.completion", "只接收完整 Chat Completions 响应，不累加 stream chunk。")
    else:
        require(raw.get("type") == "message" and raw.get("stop_reason") is not None,
                "只接收最终 Anthropic Message；请先由 SDK 合并流式消息。")
    return {"event_id": identifier(raw.get("id"), "response id"), "model": raw.get("model", "unknown"),
            "phase": phase, "usage": raw.get("usage"),
            "outcome": "failed" if raw.get("status") in {"failed", "incomplete"} else
                       "cancelled" if raw.get("status") == "cancelled" else "succeeded"}


class CodexTurns:
    """One explicit codex exec --json invocation; ignores item/reasoning text entirely."""
    def __init__(self, invocation_id, phase="unattributed", model="unknown"):
        self.invocation = identifier(invocation_id, "invocation_id")
        self.phase, self.model, self.index = phase, model, 0
        self.pending = False
        self.thread_id = None

    def feed(self, row):
        require(isinstance(row, dict), "Codex JSONL 必须逐行对象。")
        kind = row.get("type")
        if kind == "thread.started":
            thread = identifier(row.get("thread_id"), "thread_id")
            require(self.thread_id in (None, thread), "日志包含不同会话，不能混入本次创作。")
            self.thread_id = thread
        if kind == "turn.started":
            require(not self.pending, "上轮没有结束，不能默默跳过丢失 usage。")
            self.pending = True
        if kind not in {"turn.completed", "turn.failed"}:
            return None
        require(self.pending, "没有 turn.started；文件可能不完整，拒绝重复终结事件。")
        self.pending = False
        self.index += 1
        return {"event_id": self.invocation + ":turn:" + str(self.index), "phase": self.phase,
                "model": self.model, "outcome": "failed" if kind == "turn.failed" else "succeeded",
                "usage": row.get("usage")}

    def interrupted(self):
        if not self.pending:
            return None
        self.pending = False
        self.index += 1
        return {"event_id": self.invocation + ":turn:" + str(self.index), "phase": self.phase,
                "model": self.model, "outcome": "cancelled", "usage": None}
