"""Workflow-independent usage adapter: no brief, permit, PER parser, or FieldStore.

identity["usage_sessions"] explicitly binds main/child host sessions:
    {"codex": ["main UUID", "owned child UUID"], "claude": ["owned session ID"]}
The current CODEX_THREAD_ID is added automatically, never every concurrent session.
Register newly spawned owned children through bind_sessions or POST usage/bind.
Unbound children are outside coverage; all_sources_declared is a host attestation.
Tests must set identity["auto_capture"]=False or AOE2_USAGE_DISABLE_AUTO=1.
"""
from pathlib import Path
import os
import threading

from metering import Meter
from multi_agent_usage import MultiAgentUsage
from usage_formats import PHASES, canonical, require

ALIASES = {"researching": "1", "authoring": "3", "checking": "4",
           "repairing": "4", "packaging": "5", "configuration": "0"}
GAP_MESSAGES = {
    "AMBIGUOUS_CROSS_SESSION_REPLAY": "不同会话出现相同累计记录，无法证明是否为继承重放，该条保持未知。",
    "LOG_REPLACED_OR_TRUNCATED": "绑定日志被替换或截断，保留原记录并停止重算该文件。",
    "BOUND_SESSION_NOT_OBSERVED": "已绑定会话尚无本次可核实用量。",
    "UNSUPPORTED_BOUND_HOST": "已绑定宿主没有可用的真实用量适配器。",
    "NO_PROJECT_START_BASELINE": "缺少项目起点累计基线，只保留接入后的已知用量。",
    "CUMULATIVE_RESET": "来源累计计数回退，缺失区间没有估算。",
    "MISSING_USAGE_TIMESTAMP": "来源缺少时间，无法归入本次创作。",
    "MISSING_OR_UNSUPPORTED_USAGE": "来源缺少计数或字段无法可靠归一化。",
    "UNSUPPORTED_CODEX_USAGE": "Codex 日志没有受支持的累计 usage。",
    "INVALID_CODEX_TOTAL": "Codex 总数与输入输出不一致。",
    "AUTO_CAPTURE_ERROR": "自动采集发生错误，当前只保留已记录小计。",
}

class MeterAdapter:
    def __init__(self, project: Path, identity: dict):
        require(isinstance(identity, dict), "计量 identity 必须是对象。")
        self.project = Path(project).resolve()
        self.lock = threading.RLock()
        require(bool(identity.get("project_id")) and bool(identity.get("source_sha256")), "计量缺少项目或来源标识。")
        existed = (self.project / "authoring/metrics/usage.sqlite3").exists()
        self.meter = Meter(self.project, identity["project_id"], identity["source_sha256"], new_project=not existed)
        self.update_context({k: identity[k] for k in ("task_sha256", "game_mode", "civilization", "script_name") if k in identity})
        self.auto = None
        disabled = identity.get("auto_capture") is False or os.environ.get("AOE2_USAGE_DISABLE_AUTO") == "1"
        if not disabled:
            bindings = {k: list(v) for k, v in identity.get("usage_sessions", {}).items()}
            thread = os.environ.get("AOE2_AUTHOR_CODEX_THREAD_ID") or os.environ.get("CODEX_THREAD_ID")
            if thread:
                bindings.setdefault("codex", []).append(thread)
            self.auto = MultiAgentUsage(self.meter, self.project, Path(__file__).parent, bindings=bindings)
        self._sync()

    def update_context(self, changes: dict) -> dict:
        """Persist selection metadata without replacing the frozen task identity."""
        require(isinstance(changes, dict), "计量上下文更新必须是对象。")
        allowed = {"task_sha256", "game_mode", "civilization", "script_name"}
        require(set(changes) <= allowed, "不能通过上下文更换计量运行或来源。")
        with self.lock:
            current = dict(self.meter.meta.get("context", {}))
            for key in ("task_sha256", "game_mode", "script_name"):
                require(key not in current or key not in changes or current[key] == changes[key],
                        "不能更改冻结的计量任务标识。")
            updated = {**current, **changes}
            require(self.meter.meta["state"] == "RUNNING" or updated == current,
                    "计量已经结束，不能更改文明上下文。")
            self.meter.context(updated)
            require(self.meter.meta.get("context") == updated, "计量上下文未能持久化。")
            return dict(updated)

    def _sync(self):
        if self.meter.meta["state"] != "RUNNING":
            return
        capture = self.auto.sync(self.meter.meta["phase"]) if self.auto else {
            "status": "DISABLED", "scope": "NO_AUTOMATIC_COLLECTION", "active_sessions": [],
            "detected_agents": [], "events_added": 0, "gaps": [], "unbound_children_covered": False}
        gaps = [{**gap, "message": GAP_MESSAGES.get(gap["code"], "用量采集存在未核实区间。")}
                for gap in capture.get("gaps", [])]
        self.meter.capture(capture, gaps)

    def report(self, include_records=False) -> dict:
        with self.lock:
            self._sync()
            result = self.meter.report(include_records=include_records)
            result.setdefault("auto_capture", {"status": "NOT_CONNECTED"})
            result.setdefault("capture_gaps", [])
            result["scope_note"] = "只覆盖明确绑定和明确上报的本任务来源；未绑定子代理不在统计内。"
            return result

    def phase(self, value) -> dict:
        value = ALIASES.get(str(value), str(value))
        require(value in PHASES, "未知计量阶段。")
        with self.lock:
            self._sync()
            self.meter.set_phase(value)
            return self.report()

    def bind_sessions(self, sessions: dict) -> dict:
        with self.lock:
            require(self.meter.meta["state"] == "RUNNING", "计量已经结束，不能添加来源。")
            require(self.auto is not None, "自动采集已显式禁用，不能绑定宿主会话。")
            self.auto.bind(sessions)
            self.auto._save()
            return self.report()

    def handle(self, action, payload) -> dict:
        require(isinstance(payload, dict), "计量请求必须是对象。")
        # Authentication, project/revision/run binding belong to the HTTP service.
        # complete is deliberately excluded: service must validate actual Build first.
        with self.lock:
            self._sync()
            if action == "source":
                self.meter.register(payload["source_id"], payload["format"])
            elif action == "events":
                result = self.meter.ingest(payload["source_id"], payload["events"])
                return {"status": "RECORDED", **result, "run_id": self.meter.meta["run_id"]}
            elif action == "seal":
                self.meter.seal_source(payload["source_id"], payload["expected_records"])
            elif action == "phase":
                return self.phase(payload["phase"])
            elif action == "bind":
                return self.bind_sessions(payload["sessions"])
            else:
                raise ValueError("未知计量操作；complete 必须由服务核对实际交付后调用。")
            return {"status": "RECORDED", "run_id": self.meter.meta["run_id"]}

    def complete(self, build: dict, all_sources_declared=False) -> dict:
        with self.lock:
            require(isinstance(build, dict) and bool(build.get("build_id")), "完成计量必须绑定实际交付 Build。")
            if self.meter.meta["state"] == "COMPLETED":
                require(self.meter.meta["delivery"] == build, "不能更换已完成计量的交付物。")
                return self._export_result()
            self._sync()
            require(self.meter.meta["phase"] == "5", "请先进入整理交付阶段。")
            if all_sources_declared:
                require(not self.meter.meta.get("capture_gaps"), "采集存在缺口，不能声明完整覆盖。")
            self.meter.close("COMPLETED", delivery=build, all_sources_declared=all_sources_declared)
            return self._export_result()

    def _export_result(self):
        directory = self.meter.export()
        result = self.report()
        result["report_directory"] = directory.relative_to(self.project).as_posix()
        return result

    def close(self) -> dict:
        with self.lock:
            self._sync()
            self.meter.close("SESSION_CLOSED")
            return self._export_result()
