"""Project-scoped token/time ledger. SQLite transactions, no model, price or prompt store.

One live Author service owns the timer; usage reporters only append through HTTP.
Wall-time partitions and measured action/model durations are DIFFERENT measures.
A usage record is evidence supplied by a host, never an authenticated billing receipt.
"""
from __future__ import annotations

from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from usage_formats import COUNTERS, FORMATS, PHASES, canonical, count, digest, duration, event, identifier, require

SCHEMA = "author-metering-v1"
BUCKETS = ("configuration", "workflow", "human_wait", "unobserved")
BOUNDARY = ("统计范围：本轮计量接入至登记交付；网页自动来源只在用户授权后采集，授权前不追补。不含真实游戏测试和后续实战复盘。"
            "token 为宿主提供的 usage；未采集不是零，未接入的调用不可推算。"
            "缓存和推理是输入/输出的子项，不重复累加。工作流程时间不是纯模型计算时间。"
            "模型与工具调用时长可能重叠，不能与总历时相加。")


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def sums(records):
    """Unknown detailed counters stay null unless ALL records supply them."""
    result = {k: sum(r["usage"][k] for r in records if r["usage"][k] is not None) for k in COUNTERS}
    result["usage_records"] = len(records)
    known = [r for r in records if r["usage"]["total_tokens"] is not None]
    result["measured_records"] = len(known)
    result["missing_usage_records"] = len(records) - len(known)
    for key in COUNTERS:
        if not records or all(r["usage"][key] is None for r in records):
            result[key] = None
    result["detail_complete"] = {k: bool(records) and all(r["usage"][k] is not None for r in records) for k in COUNTERS}
    result["failed_or_cancelled_records"] = sum(r["outcome"] in {"failed", "cancelled"} for r in records)
    result["failed_or_cancelled_tokens"] = sum(r["usage"]["total_tokens"] or 0 for r in known if r["outcome"] in {"failed", "cancelled"}) if known else None
    result["retry_records"] = sum(r["retry_of"] is not None for r in records)
    result["retry_tokens"] = sum(r["usage"]["total_tokens"] or 0 for r in known if r["retry_of"] is not None) if known else None
    result["unknown_outcome_records"] = sum(r["outcome"] == "unknown" for r in records)
    result["outcome_complete"] = bool(records) and result["unknown_outcome_records"] == 0
    result["usage_interval_records"] = sum(r["unit"] == "usage_interval" for r in records)
    if result["unknown_outcome_records"] and not result["failed_or_cancelled_records"]:
        result["failed_or_cancelled_tokens"] = None
    result["request_records"] = sum(r["unit"] == "request" for r in records)
    result["turn_records"] = sum(r["unit"] == "turn" for r in records)
    measured_time = [r["duration_seconds"] for r in records if r["duration_seconds"] is not None]
    result["reported_duration_seconds"] = sum(measured_time) if measured_time else None
    result["missing_duration_records"] = len(records) - len(measured_time)
    return result


class Meter:
    def __init__(self, project, project_id, source_sha256, *, new_project=True, clock=time.time, monotonic=time.monotonic):
        self.root = Path(project).resolve() / "authoring" / "metrics"
        self.path = self.root / "usage.sqlite3"
        self.clock, self.monotonic, self.lock = clock, monotonic, threading.RLock()
        self._paths()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intervals (phase TEXT, bucket TEXT, seconds REAL NOT NULL,
                    PRIMARY KEY(phase,bucket));
                CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (format TEXT, id TEXT, source_id TEXT NOT NULL,
                    value TEXT NOT NULL, received_at REAL NOT NULL, PRIMARY KEY(format,id));
                CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            """)
            row = db.execute("SELECT value FROM meta WHERE id=1").fetchone()
            now = self.clock()
            if row is None:
                self.meta = {"schema": SCHEMA, "run_id": "run-" + uuid.uuid4().hex,
                             "project_id": project_id, "source_sha256": source_sha256,
                             "started_at": now, "cursor_at": now, "authoring_started_at": None,
                             "stopped_at": None, "state": "RUNNING", "phase": "0", "bucket": "configuration",
                             "external_phase": "3", "all_sources_declared": False, "delivery": None,
                             "timing_origin": "PROJECT_CREATED" if new_project else "ATTACHED_LATE",
                             "clock_adjustments": 0, "restart_count": 0, "authoring_seconds": 0, "context": {}}
            else:
                self.meta = json.loads(row[0])
                require(self.meta.get("schema") == SCHEMA and self.meta.get("project_id") == project_id
                        and self.meta.get("source_sha256") == source_sha256,
                        "计量记录属于其他项目/工具版本，禁止挪用或重置旧消耗。")
                if self.meta["state"] == "RUNNING":
                    gap = max(0, now - self.meta["cursor_at"])
                    self._allocate(db, "unattributed", "unobserved", gap)
                    if self.meta["authoring_started_at"] is not None:
                        self.meta["authoring_seconds"] += gap
                    self.meta["restart_count"] += 1
                    self.meta["cursor_at"] = now
            self._save(db)
        self.last_mono = self.monotonic()
        self.last_wall = self.clock()

    def _paths(self):
        for path in (self.root, self.root.parent, self.path):
            require(not path.is_symlink(), "计量目录不允许符号链接。")

    @contextmanager
    def db(self):
        self._paths()
        con = sqlite3.connect(self.path, timeout=15)
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except sqlite3.Error as exc:
            con.rollback()
            raise ValueError("计量数据库无法读写；请保留原记录，不要重跑已发生的调用。") from exc
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def _save(self, db):
        db.execute("INSERT OR REPLACE INTO meta VALUES(1,?)", (canonical(self.meta),))

    @staticmethod
    def _allocate(db, phase, bucket, elapsed):
        require(elapsed >= 0, "负时间无效。")
        db.execute("INSERT INTO intervals VALUES(?,?,?) ON CONFLICT(phase,bucket) DO UPDATE SET seconds=seconds+excluded.seconds",
                   (phase, bucket, elapsed))

    def tick(self, phase=None, bucket=None):
        with self.lock, self.db() as db:
            if self.meta["state"] != "RUNNING":
                return
            mono, wall = self.monotonic(), self.clock()
            elapsed = max(0, mono - self.last_mono)
            if abs((wall - self.last_wall) - elapsed) > 2:
                self.meta["clock_adjustments"] += 1
            self._allocate(db, self.meta["phase"], self.meta["bucket"], elapsed)
            if self.meta["authoring_started_at"] is not None:
                self.meta["authoring_seconds"] += elapsed
            if phase is not None:
                require(phase in PHASES and bucket in BUCKETS, "计时阶段无效。")
                self.meta.update(phase=phase, bucket=bucket)
                if phase != "0" and self.meta["authoring_started_at"] is None:
                    self.meta["authoring_started_at"] = wall
            self.meta["cursor_at"] = wall
            self._save(db)
            self.last_mono, self.last_wall = mono, wall

    def observe(self, phase, status):
        if phase == "3":
            phase = self.meta["external_phase"]
        bucket = "configuration" if status == "TASK_REQUIRED" else "human_wait" if status == "WAITING_FOR_HUMAN" else "workflow"
        self.tick(phase, bucket)

    def context(self, value):
        with self.lock:
            if self.meta["state"] == "RUNNING" and self.meta["context"] != value:
                with self.db() as db:
                    self.meta["context"] = value
                    self._save(db)

    def capture(self, auto_capture, gaps):
        """Persist metadata-only capture evidence so web and immutable exports agree."""
        with self.lock, self.db() as db:
            if self.meta["state"] == "RUNNING":
                self.meta["auto_capture"] = auto_capture
                self.meta["capture_gaps"] = gaps
                self._save(db)

    def set_phase(self, phase):
        require(phase in PHASES, "未知创作阶段。")
        require(self.meta["state"] == "RUNNING", "计量已经结束。")
        self.tick(phase, "configuration" if phase == "0" else "workflow")
        with self.lock, self.db() as db:
            self.meta["external_phase"] = phase
            self._save(db)

    def operation(self, kind, name, phase, seconds, outcome):
        require(kind in {"action", "tool"} and outcome in {"succeeded", "failed", "cancelled"}, "操作计量格式错误。")
        value = {"kind": kind, "name": identifier(name, "operation"), "phase": phase,
                 "duration_seconds": duration(seconds), "outcome": outcome}
        with self.lock, self.db() as db:
            if self.meta["state"] == "RUNNING":
                db.execute("INSERT INTO operations(value) VALUES(?)", (canonical(value),))

    def register(self, source_id, format_name):
        identifier(source_id, "source_id")
        require(format_name in FORMATS, "不支持的 usage 格式。")
        with self.lock, self.db() as db:
            row = db.execute("SELECT value FROM sources WHERE id=?", (source_id,)).fetchone()
            if row:
                require(json.loads(row[0])["format"] == format_name, "来源编号已绑定其他格式。")
                return
            require(self.meta["state"] == "RUNNING", "结束后不能新建来源；请在结束前登记采集来源。")
            db.execute("INSERT INTO sources VALUES(?,?)", (source_id, canonical({"source_id": source_id,
                       "format": format_name, "closed": False, "expected_records": None})))

    def ingest(self, source_id, values):
        require(isinstance(values, list) and 1 <= len(values) <= 200, "每批用量事件必须为 1–200 条。")
        with self.lock, self.db() as db:
            row = db.execute("SELECT value FROM sources WHERE id=?", (source_id,)).fetchone()
            require(row is not None, "先登记 usage 来源。")
            source = json.loads(row[0])
            normalized = [event(source["format"], value) for value in values]
            added = 0
            for value in normalized:
                old = db.execute("SELECT source_id,value FROM events WHERE format=? AND id=?",
                                 (source["format"], value["event_id"])).fetchone()
                if old:
                    require(old[0] == source_id and json.loads(old[1]) == value,
                            "相同调用编号内容冲突或跨来源重复，禁止重复计费。")
                    continue
                require(self.meta["state"] == "RUNNING", "计量已经结束，不接受新增调用。")
                require(not source["closed"], "来源已封账；不接受新增调用，但允许原样重复提交。")
                retry = value["retry_of"]
                if retry:
                    prev = db.execute("SELECT source_id FROM events WHERE format=? AND id=?", (source["format"], retry)).fetchone()
                    require(prev is not None and prev[0] == source_id, "retry_of 必须引用同来源已登记调用。")
                db.execute("INSERT INTO events VALUES(?,?,?,?,?)", (source["format"], value["event_id"], source_id,
                           canonical(value), self.clock()))
                added += 1
            return {"added": added, "duplicates": len(values) - added}

    def seal_source(self, source_id, expected_records):
        count(expected_records, "expected_records")
        with self.lock, self.db() as db:
            row = db.execute("SELECT value FROM sources WHERE id=?", (source_id,)).fetchone()
            require(row is not None, "未知 usage 来源。")
            actual = db.execute("SELECT count(*) FROM events WHERE source_id=?", (source_id,)).fetchone()[0]
            require(actual == expected_records, "登记数量与宿主预计数量不符，不能声明完整。")
            value = json.loads(row[0])
            value.update(closed=True, expected_records=expected_records)
            db.execute("UPDATE sources SET value=? WHERE id=?", (canonical(value), source_id))

    def close(self, outcome="SESSION_CLOSED", *, delivery=None, all_sources_declared=False):
        require(outcome in {"COMPLETED", "ABORTED", "SESSION_CLOSED"}, "无效的计量结束状态。")
        require(type(all_sources_declared) is bool, "覆盖声明必须是布尔值。")
        with self.lock:
            self.tick()
            with self.db() as db:
                if self.meta["state"] != "RUNNING":
                    # A transport close never downgrades a completed creation.
                    require(outcome == "SESSION_CLOSED" or (outcome == self.meta["state"] and delivery == self.meta["delivery"]
                            and all_sources_declared == self.meta["all_sources_declared"]), "不能重新定义已结束计量。")
                    return
                require(outcome != "COMPLETED" or isinstance(delivery, dict), "完整创作必须绑定实际交付 Build。")
                if all_sources_declared:
                    require(not self.meta.get("capture_gaps"), "自动采集存在缺口，不能声明完整覆盖。")
                    sources = [json.loads(x[0]) for x in db.execute("SELECT value FROM sources")]
                    require(sources and all(s["closed"] for s in sources), "先封账全部来源，再声明完整覆盖。")
                self.meta.update(state=outcome, stopped_at=self.clock(), delivery=delivery,
                                 all_sources_declared=all_sources_declared)
                self._save(db)

    def report(self, include_records=False):
        with self.lock:
            self.tick()
            with self.db() as db:
                sources = [json.loads(x[0]) for x in db.execute("SELECT value FROM sources ORDER BY id")]
                records = [{**json.loads(v), "format": f, "source_id": s, "received_at": stamp(t)}
                           for f, s, v, t in db.execute("SELECT format,source_id,value,received_at FROM events ORDER BY rowid")]
                operations = [json.loads(x[0]) for x in db.execute("SELECT value FROM operations ORDER BY id")]
                intervals = list(db.execute("SELECT phase,bucket,seconds FROM intervals"))
            by_bucket = {b: sum(t for _, bucket, t in intervals if b == bucket) for b in BUCKETS}
            stages = []
            for phase, label in PHASES.items():
                tokens = sums([r for r in records if r["phase"] == phase])
                actions = [o for o in operations if o["phase"] == phase and o["kind"] == "action"]
                tools = [o for o in operations if o["phase"] == phase and o["kind"] == "tool"]
                stages.append({"phase": phase, "label": label, **tokens,
                               "elapsed_seconds": sum(t for p, _, t in intervals if phase == p),
                               "human_wait_seconds": sum(t for p, b, t in intervals if p == phase and b == "human_wait"),
                               "action_attempts": len(actions), "action_failures": sum(o["outcome"] != "succeeded" for o in actions),
                               "action_seconds": sum(o["duration_seconds"] for o in actions),
                               "tool_seconds": sum(o["duration_seconds"] for o in tools)})
            totals = sums(records)
            coverage = "NOT_CONNECTED" if not sources else "PARTIAL"
            if (records and all(s["closed"] for s in sources) and totals["missing_usage_records"] == 0
                    and self.meta["all_sources_declared"] and self.meta["state"] == "COMPLETED"
                    and not self.meta.get("capture_gaps")):
                coverage = "HOST_REPORTED_COMPLETE"
            result = {**self.meta, "started_at": stamp(self.meta["started_at"]),
                      "stopped_at": stamp(self.meta["stopped_at"]) if self.meta["stopped_at"] else None,
                      "authoring_started_at": stamp(self.meta["authoring_started_at"]) if self.meta["authoring_started_at"] else None,
                      "coverage": coverage, "tokens": totals, "sources": sources, "stages": stages,
                      "by_model": [{"format": fmt, "model": model, **sums([r for r in records if (r["format"], r["model"]) == (fmt, model)])}
                                   for fmt, model in sorted({(r["format"], r["model"]) for r in records})],
                      "time": {"elapsed_seconds": sum(by_bucket.values()), "authoring_elapsed_seconds": self.meta["authoring_seconds"], **{b + "_seconds": t for b, t in by_bucket.items()},
                               "action_seconds": sum(o["duration_seconds"] for o in operations if o["kind"] == "action"),
                               "tool_seconds": sum(o["duration_seconds"] for o in operations if o["kind"] == "tool")},
                      "game_validation": "NOT_RUN", "boundary": BOUNDARY}
            result.pop("cursor_at", None)
            if include_records:
                result.update(records=records, operations=operations)
            return result

    @staticmethod
    def csv_bytes(report, kind="stages"):
        require(kind in {"stages", "calls"}, "无效 CSV。")
        output = io.StringIO(newline="")
        rows = report["stages"] if kind == "stages" else [
            {**{k: v for k, v in r.items() if k != "usage"}, **r["usage"]} for r in report.get("records", [])]
        keys = (["phase", "label", "elapsed_seconds", "human_wait_seconds", *COUNTERS,
                 "measured_records", "missing_usage_records", "retry_records", "action_attempts", "action_failures", "action_seconds", "tool_seconds"]
                if kind == "stages" else ["source_id", "format", "model", "event_id", "unit", "phase", "outcome", "retry_of", "duration_seconds", *COUNTERS])
        writer = csv.writer(output)
        writer.writerow(["run_id", "coverage", *keys])
        def safe(v):
            # CSV formula injection protection, including user-chosen model labels.
            return "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        for row in rows:
            writer.writerow([report["run_id"], report["coverage"], *[safe(row.get(k)) for k in keys]])
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    def export(self):
        report = self.report(include_records=True)
        folder = self.root / ("report-" + digest(report)[:16])
        require(not folder.is_symlink(), "报告目录不允许符号链接。")
        folder.mkdir(exist_ok=True)
        for name, data in (("summary.json", (canonical(report) + "\n").encode()),
                           ("stages.csv", self.csv_bytes(report)), ("calls.csv", self.csv_bytes(report, "calls"))):
            path = folder / name
            require(not path.is_symlink(), "报告文件不允许符号链接。")
            if path.exists():
                require(path.read_bytes() == data, "报告指纹冲突，拒绝覆盖。")
            else:
                with path.open("xb") as stream:
                    stream.write(data)
        return folder
