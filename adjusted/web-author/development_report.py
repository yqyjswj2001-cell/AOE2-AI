"""Developer-facing creation reports: one readable summary plus one Markdown technical appendix."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import time
import uuid

EVENT_SCHEMA = "aoe2-development-events-v1"
REPORT_SCHEMA = "aoe2-development-report-v1"
REPORT_ID = re.compile(r"report-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}\Z")
EVENT_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
SOURCES = {"system", "workflow", "host", "author", "browser", "server"}
SEVERITIES = {"info", "warning", "error"}
FEEDBACK_KINDS = {"issue", "suggestion", "note"}
MAX_MESSAGE = 4000
MAX_DATA_BYTES = 128 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024


class DevelopmentReportError(ValueError):
    pass


def _stamp(epoch=None):
    epoch = time.time() if epoch is None else epoch
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_bytes(raw)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _plain_data(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DevelopmentReportError("development event data must be an object")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_DATA_BYTES:
        raise DevelopmentReportError("development event data is too large")
    return json.loads(raw)


class DevelopmentJournal:
    def __init__(self, project: Path, project_id: str):
        self.project = Path(project).resolve()
        self.project_id = project_id
        self.root = self.project / "development"
        self.path = self.root / "events.json"
        self.evidence = self.root / "evidence"

    def read(self):
        if not self.path.is_file() or self.path.is_symlink():
            return []
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DevelopmentReportError("development event log is unreadable") from exc
        if doc.get("schema") != EVENT_SCHEMA or doc.get("project_id") != self.project_id or not isinstance(doc.get("events"), list):
            raise DevelopmentReportError("development event log belongs to another project or schema")
        return doc["events"]

    def record(self, source: str, kind: str, severity: str, message: str, data=None):
        if source not in SOURCES or severity not in SEVERITIES or not EVENT_NAME.fullmatch(kind):
            raise DevelopmentReportError("invalid development event metadata")
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= MAX_MESSAGE:
            raise DevelopmentReportError("development event message must be 1-4000 characters")
        now = time.time()
        event = {
            "event_id": "evt-" + uuid.uuid4().hex[:16],
            "timestamp": _stamp(now),
            "epoch": now,
            "source": source,
            "kind": kind,
            "severity": severity,
            "message": message.strip(),
            "data": _plain_data(data),
        }
        events = self.read()
        events.append(event)
        _atomic_json(self.path, {"schema": EVENT_SCHEMA, "project_id": self.project_id, "events": events})
        return event

    def feedback(self, source: str, kind: str, message: str, data=None):
        if source not in {"host", "author", "browser"} or kind not in FEEDBACK_KINDS:
            raise DevelopmentReportError("invalid feedback source or kind")
        severity = "warning" if kind == "issue" else "info"
        return self.record(source, "feedback_" + kind, severity, message, data)

    def snapshot(self, label: str, source: Path):
        if not EVENT_NAME.fullmatch(label):
            raise DevelopmentReportError("invalid evidence label")
        source = Path(source)
        if not source.is_file() or source.is_symlink():
            return None
        size = source.stat().st_size
        if size > MAX_EVIDENCE_BYTES:
            return None
        self.evidence.mkdir(parents=True, exist_ok=True)
        suffix = source.suffix if len(source.suffix) <= 12 else ""
        target = self.evidence / (label + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + suffix)
        shutil.copyfile(source, target)
        return target.relative_to(self.project).as_posix()


def _safe_read_json(path: Path):
    try:
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_EVIDENCE_BYTES:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return None


def _seconds(value):
    if not isinstance(value, (int, float)) or value < 0:
        return "未记录"
    value = int(value)
    h, rem = divmod(value, 3600)
    m, s = divmod(rem, 60)
    return (f"{h}时 " if h else "") + (f"{m}分 " if m or h else "") + f"{s}秒"


def _num(value):
    return f"{value:,}" if type(value) is int else "未记录"


def _table(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _dedupe(values):
    seen, result = set(), []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _issue_list(snapshot, usage, runtime, diagnostics, events, browser_observations):
    issues = []
    def add(code, severity, source, message, data=None):
        issues.append({"code": code, "severity": severity, "source": source, "message": message, "data": data or {}})

    progress = snapshot.get("progress") or {}
    for message in progress.get("errors") or []:
        add("CURRENT_WORKFLOW_ERROR", "error", "project", str(message))

    if diagnostics:
        missing = diagnostics.get("missing_count") or 0
        invalid = diagnostics.get("invalid_count") or 0
        if missing:
            add("MISSING_PARAMETERS", "error", "validation", f"仍有 {missing} 个参数未填写", {"missing_count": missing})
        if invalid:
            add("INVALID_PARAMETER_TYPES", "error", "validation", f"仍有 {invalid} 个参数类型错误", {"invalid_count": invalid})
        for name in diagnostics.get("unreadable") or []:
            add("UNREADABLE_ANSWER_FILE", "error", "validation", "答案文件无法读取: " + str(name))

    for event in events:
        if event.get("severity") in {"warning", "error"}:
            add("EVENT_" + str(event.get("kind", "UNKNOWN")).upper(), event["severity"], event.get("source", "event"),
                event.get("message", ""), {"event_id": event.get("event_id"), **(event.get("data") or {})})

    capture_gaps = list(usage.get("capture_gaps") or [])
    auto = usage.get("auto_capture") or {}
    capture_gaps += list(auto.get("gaps") or [])
    for gap in _dedupe(capture_gaps):
        code = str(gap.get("code") or "USAGE_GAP")
        add(code, "warning", "usage", str(gap.get("message") or code), {k: v for k, v in gap.items() if k != "message"})

    request = snapshot.get("request") or {}
    if request:
        if request.get("usage_authorized") is False:
            add("USAGE_DISABLED_BY_USER", "info", "usage", "本轮用户选择不启用自动 token 计量")
        else:
            coverage = usage.get("coverage")
            if coverage != "HOST_REPORTED_COMPLETE":
                add("USAGE_COVERAGE_" + str(coverage or "UNKNOWN"), "warning", "usage",
                    "Token 用量覆盖并非完整封账: " + str(coverage or "UNKNOWN"))
            tokens = usage.get("tokens") or {}
            if tokens.get("total_tokens") is None:
                add("TOKEN_TOTAL_UNKNOWN", "warning", "usage", "本轮总 token 未取得可靠记录")
            missing_duration = tokens.get("missing_duration_records")
            if type(missing_duration) is int and missing_duration > 0:
                add("USAGE_DURATION_MISSING", "warning", "usage", f"{missing_duration} 条用量记录缺少调用时长")
            unknown_outcome = tokens.get("unknown_outcome_records")
            if type(unknown_outcome) is int and unknown_outcome > 0:
                add("USAGE_OUTCOME_UNKNOWN", "warning", "usage", f"{unknown_outcome} 条用量记录结果状态未知")

    unverified = [name for name, value in (runtime or {}).items() if str(value).lower() in {"unverified", "not_run", "unknown"}]
    if unverified:
        add("GAME_VALIDATION_INCOMPLETE", "warning", "runtime", "游戏侧验证尚未完成: " + ", ".join(unverified))

    build = snapshot.get("build")
    if build and build.get("installable") is False:
        add("BUILD_NOT_INSTALLABLE", "warning", "build", "当前构建物没有完整游戏入口")
    if snapshot.get("status") != "completed":
        add("WORKFLOW_NOT_COMPLETED", "info", "project", "生成报告时创作流程尚未完成")

    for row in browser_observations:
        if isinstance(row, dict) and isinstance(row.get("message"), str):
            add("BROWSER_" + str(row.get("kind") or "OBSERVATION").upper(), "warning", "browser",
                row["message"], {k: v for k, v in row.items() if k != "message"})

    result = _dedupe(issues)
    for index, issue in enumerate(result, 1):
        issue["issue_id"] = f"I{index:03d}"
    return result


def _markdown(report):
    snap = report["project"]
    request = snap.get("request") or {}
    usage = report["usage"]
    tokens = usage.get("tokens") or {}
    time_data = usage.get("time") or {}
    build = snap.get("build") or {}
    lines = [
        "# AOE2 AI 创作报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 项目：{snap.get('project_name', '')}",
        f"- 项目 ID：{snap.get('project_id', '')}",
        f"- 仓库提交：{report.get('repository_head') or '未取得'}",
        f"- 当前状态：{snap.get('status', '')}",
        f"- 脚本名：{request.get('script_name') or '尚未设置'}",
        f"- 模式：{request.get('mode') or '尚未设置'}",
        f"- 文明：{request.get('civilization') or '尚未设置'}",
        f"- 用量授权：{'允许自动计量' if request.get('usage_authorized') is True else '本轮不计量' if request.get('usage_authorized') is False else '旧项目未记录'}",
        "",
        "## 问题汇总",
        "",
    ]
    issues = report["issues"]
    if issues:
        for issue in issues:
            lines.append(f"- **{issue['issue_id']} · {issue['severity']} · {issue['source']}**：{issue['message']}")
    else:
        lines.append("- 本次快照未发现已记录问题；这不代表未执行的实机验证已经通过。")

    lines += ["", "## 反馈", ""]
    feedback = report["feedback"]
    if feedback:
        for event in feedback:
            lines.append(f"- {event['timestamp']} · {event['source']} · {event['kind'].removeprefix('feedback_')}：{event['message']}")
    else:
        lines.append("- 暂无主动登记的反馈。")

    lines += [
        "",
        "## 参数与校验",
        "",
        f"- 已填写：{_num((snap.get('progress') or {}).get('filled'))} / {_num((snap.get('progress') or {}).get('total'))}",
        f"- 当前校验状态：{'PASS' if snap.get('validation') else '未通过或尚未执行'}",
    ]
    diagnostics = report.get("answer_diagnostics")
    if diagnostics:
        lines += [
            f"- 最近缺项：{diagnostics.get('missing_count', 0)}",
            f"- 最近类型错误：{diagnostics.get('invalid_count', 0)}",
        ]
        for name, keys in (diagnostics.get("missing") or {}).items():
            lines.append(f"  - {name}：缺 {len(keys)} 项")
        for name, keys in (diagnostics.get("non_integer") or {}).items():
            lines.append(f"  - {name}：类型错误 {len(keys)} 项")

    lines += [
        "",
        "## 时间与 Token",
        "",
        f"- 总历时：{_seconds(time_data.get('elapsed_seconds'))}",
        f"- 工作流时间：{_seconds(time_data.get('workflow_seconds'))}",
        f"- 未观察时间：{_seconds(time_data.get('unobserved_seconds'))}",
        f"- 输入 token：{_num(tokens.get('input_tokens'))}",
        f"- 输出 token：{_num(tokens.get('output_tokens'))}",
        f"- 总 token：{_num(tokens.get('total_tokens'))}",
        f"- 覆盖状态：{usage.get('coverage') or 'UNKNOWN'}",
        "",
        "| 阶段 | 历时 | 已记录 token | 调用/操作问题 |",
        "| --- | ---: | ---: | --- |",
    ]
    for stage in usage.get("stages") or []:
        failures = stage.get("failed_or_cancelled_records") or 0
        missing = stage.get("missing_usage_records") or 0
        action_failures = stage.get("action_failures") or 0
        note = f"失败/取消 {failures}；缺 usage {missing}；操作失败 {action_failures}"
        lines.append(f"| {_table(stage.get('label') or stage.get('phase'))} | {_seconds(stage.get('elapsed_seconds'))} | {_num(stage.get('total_tokens'))} | {_table(note)} |")

    lines += [
        "",
        "## 脚本输出",
        "",
        f"- 构建 ID：{build.get('build_id') or '尚无'}",
        f"- 脚本文件：{build.get('script_files') if build else '尚无构建'}",
        f"- 静态校验：{build.get('static_validation') or '未记录'}",
        f"- 输出目录：{build.get('script_root') or build.get('path') or '尚无'}",
    ]

    lines += ["", "## 过程记录", ""]
    events = report["events"]
    if events:
        for event in events:
            lines.append(f"- {event['timestamp']} · {event['source']} · {event['kind']} · {event['severity']}：{event['message']}")
    else:
        lines.append("- 该项目没有持久化的开发事件记录；旧项目可能早于此功能。")

    lines += [
        "",
        "## 证据与边界",
        "",
        "- creation-report.md 是给开发直接阅读/粘贴的主报告。",
        "- technical-details.md 合并参数诊断、完整问题/反馈、usage 调用、构建详情、事件时间线和日志摘要。",
        "- 未采集不等于 0；脚本输出只代表静态生成完成。",
        "- 这是开发快照，不包含游戏安装或实机验证。",
        "",
    ]
    return "\n".join(lines)


def _json_block(value):
    return ["~~~json", json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False), "~~~"]


def _technical_markdown(report, project: Path):
    snap = report["project"]
    usage = report["usage"]
    build = snap.get("build") or {}
    lines = [
        "# AOE2 AI 创作技术明细",
        "",
        f"- 报告 ID：{report['report_id']}",
        f"- 生成时间：{report['generated_at']}",
        f"- 项目：{snap.get('project_name', '')}",
        f"- 仓库提交：{report.get('repository_head') or '未取得'}",
        "",
        "## 问题与反馈完整记录",
        "",
    ]
    if report["issues"]:
        for issue in report["issues"]:
            lines += [
                f"### {issue['issue_id']} · {issue['severity']} · {issue['source']}",
                "",
                f"- code：{issue['code']}",
                f"- 内容：{issue['message']}",
            ]
            if issue.get("data"):
                lines += ["", "附加数据：", "", *_json_block(issue["data"])]
            lines.append("")
    else:
        lines += ["- 无已记录问题。", ""]

    lines += ["## 主动反馈", ""]
    if report["feedback"]:
        for event in report["feedback"]:
            lines.append(f"- {event['timestamp']} · {event['source']} · {event['kind']}：{event['message']}")
            if event.get("data"):
                lines += ["", *_json_block(event["data"]), ""]
    else:
        lines += ["- 无主动反馈。", ""]

    lines += ["## 参数校验完整明细", ""]
    diagnostics = report.get("answer_diagnostics")
    if diagnostics is None:
        lines += ["- 当前没有 answer-diagnostics 快照。", ""]
    else:
        lines += _json_block(diagnostics) + [""]

    lines += [
        "## Usage 汇总",
        "",
        f"- coverage：{usage.get('coverage')}",
        f"- state：{usage.get('state')}",
        f"- run_id：{usage.get('run_id')}",
        "",
        "### Token 与时间",
        "",
        *_json_block({"tokens": usage.get("tokens"), "time": usage.get("time")}),
        "",
        "### 自动采集与缺口",
        "",
        *_json_block({"auto_capture": usage.get("auto_capture"), "capture_gaps": usage.get("capture_gaps")}),
        "",
        "### 阶段",
        "",
        "| phase | label | elapsed | total token | missing usage | action failures |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for stage in usage.get("stages") or []:
        lines.append(
            f"| {_table(stage.get('phase'))} | {_table(stage.get('label'))} | "
            f"{_seconds(stage.get('elapsed_seconds'))} | {_num(stage.get('total_tokens'))} | "
            f"{_num(stage.get('missing_usage_records'))} | {_num(stage.get('action_failures'))} |"
        )
    if not usage.get("stages"):
        lines.append("| — | — | — | — | — | — |")

    lines += [
        "",
        "### 调用记录",
        "",
        "| time | source | model | event | unit | phase | outcome | total | input | output | cached | reasoning | duration | retry_of |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in usage.get("records") or []:
        u = row.get("usage") or {}
        lines.append(
            "| " + " | ".join([
                _table(row.get("received_at")),
                _table(row.get("source_id")),
                _table(row.get("model")),
                _table(row.get("event_id")),
                _table(row.get("unit")),
                _table(row.get("phase")),
                _table(row.get("outcome")),
                _table(_num(u.get("total_tokens"))),
                _table(_num(u.get("input_tokens"))),
                _table(_num(u.get("output_tokens"))),
                _table(_num(u.get("cached_input_tokens"))),
                _table(_num(u.get("reasoning_output_tokens"))),
                _table(row.get("duration_seconds")),
                _table(row.get("retry_of")),
            ]) + " |"
        )
    if not usage.get("records"):
        lines.append("| — | — | — | — | — | — | — | — | — | — | — | — | — | — |")

    lines += ["", "### 操作记录", ""]
    if usage.get("operations"):
        lines += _json_block(usage["operations"]) + [""]
    else:
        lines += ["- 无操作记录。", ""]

    lines += ["## 脚本输出完整数据", "", *_json_block({
        "build": build,
        "civilization_selection": report.get("civilization_selection"),
    }), ""]

    lines += ["## 浏览器观察", ""]
    if report.get("browser_observations"):
        lines += _json_block(report["browser_observations"]) + [""]
    else:
        lines += ["- 无浏览器观察记录。", ""]

    lines += ["## 完整过程事件", ""]
    if report.get("events"):
        for event in report["events"]:
            lines += [
                f"### {event.get('timestamp')} · {event.get('source')} · {event.get('kind')} · {event.get('severity')}",
                "",
                event.get("message", ""),
            ]
            if event.get("data"):
                lines += ["", *_json_block(event["data"])]
            lines.append("")
    else:
        lines += ["- 无事件记录。", ""]

    log = project / "logs/web-session.log"
    lines += ["## Web Session 日志", ""]
    try:
        if log.is_file() and not log.is_symlink():
            raw = log.read_bytes()
            limit = 512 * 1024
            truncated = len(raw) > limit
            if truncated:
                raw = raw[-limit:]
            log_text = raw.decode("utf-8", errors="replace")
            if truncated:
                lines += ["- 日志过大，下方仅保留最后 512 KiB；原始日志仍保存在项目目录。", ""]
            lines += ["~~~text", log_text.rstrip(), "~~~", ""]
        else:
            lines += ["- 无 Web Session 日志。", ""]
    except OSError:
        lines += ["- Web Session 日志读取失败；原始文件仍留在项目目录。", ""]

    evidence = project / "development/evidence"
    lines += ["## 错误现场快照", ""]
    if evidence.is_dir() and not evidence.is_symlink():
        files = [p for p in sorted(evidence.iterdir()) if p.is_file() and not p.is_symlink()]
        if not files:
            lines.append("- 无额外快照。")
        for source in files:
            lines += [f"### {source.name}", ""]
            try:
                if source.stat().st_size > MAX_EVIDENCE_BYTES:
                    lines += [f"- 文件过大（{source.stat().st_size} bytes），保留在项目目录，未嵌入。", ""]
                    continue
                snapshot_text = source.read_text(encoding="utf-8", errors="replace")
                lines += ["~~~text", snapshot_text.rstrip(), "~~~", ""]
            except OSError:
                lines += ["- 快照读取失败，原始文件仍保留。", ""]
    else:
        lines += ["- 无额外快照。", ""]

    lines += [
        "## 边界",
        "",
        "- 这是开发技术明细，不代表未执行的游戏测试已经通过。",
        "- 未采集数据保持未知，不补零、不估算。",
        "- 原始项目状态、计量数据库和事件文件继续保存在项目目录，供程序复查。",
        "",
    ]
    return "\n".join(lines)


def generate_reports(*, project: Path, repository_root: Path, project_snapshot: dict, usage: dict,
                    runtime: dict, civilization_selection, events: list, browser_observations: list):
    project = Path(project).resolve()
    report_id = "report-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    if not REPORT_ID.fullmatch(report_id):
        raise DevelopmentReportError("failed to create report id")
    generated_at = _stamp()
    diagnostics = _safe_read_json(project / "tmp/answer-diagnostics.json")

    snapshot = {
        "project_name": project.name,
        "project_id": project_snapshot.get("project_id"),
        "status": project_snapshot.get("status"),
        "revision": project_snapshot.get("revision"),
        "request": project_snapshot.get("request"),
        "progress": project_snapshot.get("progress"),
        "validation": project_snapshot.get("validation"),
        "build": project_snapshot.get("build"),
        "answers_sha256": project_snapshot.get("answers_sha256"),
        "input_sha256": project_snapshot.get("input_sha256"),
        "fixed_sha256": project_snapshot.get("fixed_sha256"),
    }

    try:
        import subprocess
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository_root, capture_output=True, text=True, timeout=3)
        repository_head = proc.stdout.strip() if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", proc.stdout.strip()) else None
    except (OSError, subprocess.SubprocessError):
        repository_head = None

    feedback = [event for event in events if str(event.get("kind", "")).startswith("feedback_")]
    issues = _issue_list(snapshot, usage, runtime, diagnostics, events, browser_observations)
    report = {
        "schema": REPORT_SCHEMA,
        "report_id": report_id,
        "generated_at": generated_at,
        "repository_head": repository_head,
        "project": snapshot,
        "civilization_selection": civilization_selection,
        "runtime": runtime,
        "usage": usage,
        "answer_diagnostics": diagnostics,
        "events": events,
        "feedback": feedback,
        "browser_observations": browser_observations,
        "issues": issues,
    }

    report_root = project / "development/reports"
    folder = report_root / report_id
    folder.mkdir(parents=True, exist_ok=False)
    markdown = _markdown(report)
    technical = _technical_markdown(report, project)
    main_path = folder / "creation-report.md"
    technical_path = folder / "technical-details.md"
    main_path.write_text(markdown, encoding="utf-8", newline="\n")
    technical_path.write_text(technical, encoding="utf-8", newline="\n")

    script_name = (snapshot.get("request") or {}).get("script_name") or project.name
    return {
        "report_id": report_id,
        "generated_at": generated_at,
        "issue_count": len(issues),
        "feedback_count": len(feedback),
        "path": str(folder),
        "markdown": markdown,
        "markdown_path": str(main_path),
        "technical_path": str(technical_path),
        "markdown_download_name": script_name + "-creation-report.md",
        "technical_download_name": script_name + "-technical-details.md",
    }

def report_file(project: Path, report_id: str, format_name: str = "main") -> Path:
    if not isinstance(report_id, str) or not REPORT_ID.fullmatch(report_id):
        raise DevelopmentReportError("invalid report id")
    root = Path(project).resolve() / "development/reports" / report_id
    if format_name == "main":
        path = root / "creation-report.md"
    elif format_name == "details":
        path = root / "technical-details.md"
    else:
        raise DevelopmentReportError("invalid report format")
    if not path.is_file() or path.is_symlink():
        raise DevelopmentReportError("report file not found")
    return path
