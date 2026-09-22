#!/usr/bin/env python3
"""Host usage collection client. Reads an explicitly chosen log, never scans chats.

No raw prompt/response/log content is sent to Studio. Only final, normalized
usage records are stored. A closed log source is not a whole-run declaration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import uuid
import urllib.error

from http_client import request
from usage_formats import CodexTurns, FORMATS, PHASES, event, require, response_event, usage_payload


class UsageClient:
    def __init__(self, url=None, *, project=None):
        self.headers = {}
        self.project_id = None
        if project is not None:
            descriptor = Path(project).resolve() / ".author-web-session.json"
            require(descriptor.is_file() and not descriptor.is_symlink(), "项目缺少本机作者会话描述文件。")
            meta = json.loads(descriptor.read_text(encoding="utf-8-sig"))
            require(isinstance(meta, dict) and meta.get("host_token") and meta.get("project_id") and meta.get("url"), "会话描述文件不完整。")
            require(url is None or url.rstrip("/") == meta["url"].rstrip("/"), "URL 与项目会话不匹配。")
            url = meta["url"]
            self.headers = {"X-Author-Token": meta["host_token"]}
            self.project_id = meta["project_id"]
        require(bool(url), "请提供 --project；仅只读报告可用 --url。")
        self.url = url
        self.run_id = request(url, "/api/author/usage", headers=self.headers)["run_id"]

    def send(self, op, **payload):
        require(self.project_id is not None, "计量写入必须通过 --project 读取本机宿主凭据。")
        current = request(self.url, "/api/author/next", headers=self.headers)
        require(current["project_id"] == self.project_id, "会话已被替换，停止上报。")
        return request(self.url, "/api/author/usage/" + op,
                       {**payload, "run_id": self.run_id, "project_id": self.project_id,
                        "expected_revision": current["revision"]}, headers=self.headers)

    def register(self, source_id, format_name):
        return self.send("source", source_id=source_id, format=format_name)

    def append(self, source_id, format_name, values):
        # Validate before network; discard unknown provider fields or any response text.
        clean = []
        for value in values:
            event(format_name, value)
            clean.append({**value, "usage": usage_payload(format_name, value["usage"])})
        return self.send("events", source_id=source_id, events=clean)

    def measured_call(self, source_id, format_name, invoke, *, model="unknown", phase=None, retry_of=None):
        """Wrap one host SDK call; the host must instrument/disable hidden SDK retries.

        This helper never reads API keys. The supplied callable retains the host's
        existing provider client, permissions, request parameters and response type.
        """
        require(format_name != "codex-exec", "Codex 用 JSONL 轮次采集器。")
        self.register(source_id, format_name)
        phase = phase or self.report()["phase"]
        started = time.monotonic()
        try:
            response = invoke()
        except BaseException as original:
            try:
                self.append(source_id, format_name, [{"event_id": "failed-" + uuid.uuid4().hex,
                    "phase": phase, "model": model, "outcome": "cancelled" if isinstance(original, KeyboardInterrupt) else "failed",
                    "usage": None, "duration_seconds": time.monotonic() - started, "retry_of": retry_of}])
            except Exception:
                # Never turn a paid/failed request into a request that is safe to replay.
                print("模型调用已发生，但失败用量记录未能写入；不要自动重试。", file=sys.stderr)
            raise
        elapsed = time.monotonic() - started
        try:
            raw = response.model_dump() if hasattr(response, "model_dump") else response
            value = response_event(format_name, raw, phase)
            value.update(duration_seconds=elapsed, retry_of=retry_of)
            self.append(source_id, format_name, [value])
        except Exception as error:
            raise ValueError("模型调用已完成，但 usage 写入失败；不要重放模型调用。请从原响应补录。") from error
        return response

    def report(self):
        report = request(self.url, "/api/author/usage", headers=self.headers)
        require(report["run_id"] == self.run_id, "项目已被替换，停止采集。")
        return report


def read_usage_lines(stream, format_name, source_id, phase="unattributed", model="unknown"):
    """Consume one complete, dedicated invocation log; no cumulative token_count sums."""
    codex = CodexTurns(source_id, phase, model) if format_name == "codex-exec" else None
    ids = set()
    for line in stream:
        require(len(line) <= 4 * 1024 * 1024, "单行日志超过 4 MiB，停止而非跳过。")
        if not line.strip():
            continue
        value = json.loads(line)
        require(isinstance(value, dict), "日志必须是逐行 JSON 对象。")
        if codex:
            item = codex.feed(value)
        else:
            # A final API response or Responses terminal event, not text deltas.
            item = response_event(format_name, value, phase)
        if item is not None:
            event(format_name, item)
            ids.add(item["event_id"])
            yield item
    if codex:
        interrupted = codex.interrupted()
        if interrupted:
            yield interrupted


def import_log(client, file, source_id, format_name, phase, model, *, seal=False):
    file = Path(file)
    require(file.is_file() and not file.is_symlink(), "请明确选择当前创作的普通 JSONL 文件。")
    require(file.stat().st_size <= 512 * 1024 * 1024, "日志超过 512 MiB，先按单次调用拆分。")
    # Parse all before sending: malformed input cannot partially masquerade as complete.
    with file.open(encoding="utf-8-sig") as stream:
        items = list(read_usage_lines(stream, format_name, source_id, phase, model))
    require(len(items) <= 100_000, "单次导入记录过多。")
    require(items, "未发现终结 usage 记录；不是受支持的当前调用日志。")
    client.register(source_id, format_name)
    added = duplicates = 0
    for at in range(0, len(items), 200):
        result = client.append(source_id, format_name, items[at:at+200])
        added += result["added"]; duplicates += result["duplicates"]
    if seal:
        client.send("seal", source_id=source_id, expected_records=len({r["event_id"] for r in items}))
    return {"added": added, "duplicates": duplicates, "records": len(items), "run_id": client.run_id}


def follow_log(client, file, source_id, format_name, phase, model, seconds=0):
    """Live tail of an explicit run-only log. Replay from start is idempotent on restart.

    No auto-discovery of private log directories, no transcript uploads. A tail
    interruption leaves its source OPEN, so it cannot falsely claim coverage.
    """
    file = Path(file)
    require(file.is_file() and not file.is_symlink(), "请指定本次创作的 JSONL 日志。")
    codex = CodexTurns(source_id, phase, model) if format_name == "codex-exec" else None
    client.register(source_id, format_name)
    start = time.monotonic()
    # Binary offsets let a partially written UTF-8 line wait until its newline.
    with file.open("rb") as stream:
        identity = (file.stat().st_dev, file.stat().st_ino)
        while seconds == 0 or time.monotonic() - start < seconds:
            stat = file.stat()
            require(not file.is_symlink() and (stat.st_dev, stat.st_ino) == identity and stat.st_size >= stream.tell(),
                    "日志被替换或截断；停止采集，不能悄悄重算。")
            at = stream.tell()
            raw = stream.readline(4 * 1024 * 1024 + 1)
            require(len(raw) <= 4 * 1024 * 1024, "日志单行过大。")
            if not raw.endswith(b"\n"):
                stream.seek(at); time.sleep(0.5); continue
            row = json.loads(raw.decode("utf-8-sig"))
            value = codex.feed(row) if codex else response_event(format_name, row, phase)
            if value:
                client.append(source_id, format_name, [value])
    return {"status": "CAPTURE_STOPPED_SOURCE_OPEN", "run_id": client.run_id}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("report", "import", "follow", "phase", "complete"):
        child = commands.add_parser(name)
        location = child.add_mutually_exclusive_group(required=True)
        location.add_argument("--url", help="只读报告使用的本机 URL")
        location.add_argument("--project", type=Path, help="含 .author-web-session.json 的本轮项目目录")
        if name in {"import", "follow"}:
            child.add_argument("--file", type=Path, required=True)
            child.add_argument("--source-id", required=True, help="stable ID for this invocation; reuse on reimport")
            child.add_argument("--format", choices=sorted(FORMATS), required=True)
            child.add_argument("--phase", choices=PHASES, default="unattributed")
            child.add_argument("--model", default="unknown", help="Codex only: explicit model label, never guessed")
            if name == "import":
                child.add_argument("--seal", action="store_true")
            else:
                child.add_argument("--seconds", type=int, default=0, help="0 waits continuously; no model polling")
        if name == "report":
            child.add_argument("--output", type=Path, help="new JSON path; never overwrites")
        if name == "phase":
            child.add_argument("--phase", choices=[p for p in PHASES if p != "unattributed"], required=True)
        if name == "complete":
            child.add_argument("--build-id", help="可选的预期 Build ID；服务重新核验当前实际交付")
            child.add_argument("--all-sources-reported", action="store_true", help="host attestation, NOT automatic proof")
    args = parser.parse_args(argv)
    try:
        client = UsageClient(args.url, project=args.project)
        if args.command in {"import", "follow"}:
            if args.command == "follow":
                require(args.seconds >= 0, "seconds 不能为负。")
                result = follow_log(client, args.file, args.source_id, args.format, args.phase, args.model, args.seconds)
            else:
                result = import_log(client, args.file, args.source_id, args.format, args.phase, args.model, seal=args.seal)
        elif args.command == "report":
            result = request(client.url, "/api/author/usage/export?format=json", headers=client.headers)
            if args.output:
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
        else:
            if args.command == "complete" and args.build_id:
                current = request(client.url, "/api/author/next", headers=client.headers)
                require((current.get("build") or {}).get("build_id") == args.build_id, "当前 Build 与预期不匹配。")
            result = client.send(args.command, **(
                {"phase": args.phase} if args.command == "phase" else
                {"all_sources_declared": args.all_sources_reported}))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print("采集已停止；来源未封账，不会当作完整用量。", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError) as exc:
        message = exc.read().decode("utf-8", errors="replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        print(json.dumps({"status": "METERING_ERROR", "error": message}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
