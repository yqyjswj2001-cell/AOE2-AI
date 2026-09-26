"""Local host controller: immutable author input, separate answers, guarded delivery."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile

from civilizations import content_profile, eligible_rows, selection_context
from agent_catalog import agent_catalog, normalize_agent
from development_report import DevelopmentJournal, DevelopmentReportError, generate_reports, report_file
from cursor_admin_usage import active_project_path
from work_registry import REGISTRY_DB, RegistryError, register_completed_project

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROJECTS = ROOT / "adjusted/.local/author-projects"
TEST_ROOT = ROOT / "adjusted/.local/web-author-migration/tmp"
CIVILIZATION_TEST_ROOT = ROOT / "adjusted/.local/civilization-selection/tmp"
UI_TEST_ROOT = ROOT / "adjusted/.local/ui-token-revision/tmp"
TOOLS = ROOT / "adjusted/tools"
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
MODES = {"1v1", "2v2", "3v3", "4v4", "ffa4", "ffa8"}
OUTPUT_MODES = {"raw_scripts", "share_package"}
SCHEMA = "aoe2-web-author-project-v1"


class WorkflowError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WorkflowError("JSON contains duplicate keys")
        out[key] = value
    return out


def parse_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(WorkflowError("Non-finite JSON number")))


def safe_path(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise WorkflowError("Path cannot redirect through a symlink or junction")
    return path


def project_path(value, test_project=False):
    given = Path(value)
    if not given.is_absolute() and len(given.parts) == 1 and NAME.fullmatch(str(given)):
        result = PROJECTS / given
    else:
        result = given
    result = safe_path(result)
    if result.parent == safe_path(PROJECTS) and NAME.fullmatch(result.name):
        return result
    test_roots = (safe_path(TEST_ROOT), safe_path(CIVILIZATION_TEST_ROOT), safe_path(UI_TEST_ROOT), safe_path(Path(tempfile.gettempdir())))
    if test_project and any(result.is_relative_to(base) and result != base for base in test_roots):
        return result
    raise WorkflowError("Project must be adjusted/.local/author-projects/<name>; explicit test projects must stay in temporary storage")


def atomic_json(path, value):
    safe_path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(json_bytes(value))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_tool(name, *args):
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(TOOLS / name), *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise WorkflowError("Host validation tool failed; inspect project logs") from None
    if result.returncode or payload.get("ok") is False:
        # Do not expose tool stderr, fixed source, or reference values over HTTP.
        raise WorkflowError(payload.get("error", "Host validation failed"))
    return payload


class RealEngine:
    def civilizations(self):
        data = run_tool("query_creator_facts.py", "civilizations")
        return eligible_rows([{"id": row["internal_name"], "name": row["display_name_zh"]} for row in data["civilizations"]])

    def export(self, out):
        return run_tool("build_strategy_input.py", "--out", out)

    def source_digest(self):
        groups = [
            (ROOT / "official/raw/Promisory", "*.per"),
            (ROOT / "adjusted/cloze/Promisory", "*.per.tpl"),
            (ROOT / "adjusted/cloze/official-defaults", "*.json"),
        ]
        files = [safe_path(path) for directory, pattern in groups for path in sorted(directory.glob(pattern))]
        files += [ROOT / "adjusted/cloze/classification/parameters.json", HERE / "standard-edition.json", HERE / "civilizations.py"]
        files += [TOOLS / name for name in ("render_per_cloze.py", "strategy_catalog.py", "cloze_boundary.py", "build_strategy_input.py")]
        if len(list((ROOT / "official/raw/Promisory").glob("*.per"))) != 36:
            raise WorkflowError("Expected 36 fixed source modules")
        return digest(json_bytes({str(path.relative_to(ROOT)): digest(safe_path(path).read_bytes()) for path in files}))

    def render(self, answer_snapshot, out):
        run_tool("render_per_cloze.py", "--answers-dir", answer_snapshot, "--out", out)
        rendered = {path.name for path in out.glob("*.per")}
        if len(rendered) != 17:
            raise WorkflowError("Renderer must return all 17 reviewed template modules")
        for source in (ROOT / "official/raw/Promisory").glob("*.per"):
            if source.name not in rendered:
                (out / source.name).write_bytes(safe_path(source).read_bytes())
        if len(list(out.glob("*.per"))) != 36:
            raise WorkflowError("Delivery must contain all 36 modules")


class Controller:
    def __init__(self, project, *, engine=None, meter_factory=None):
        self.project = safe_path(project)
        self.project.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.engine = engine or RealEngine()
        self.registry_db = REGISTRY_DB if engine is None else self.project / "tmp/test-work-registry.sqlite3"
        self._preflight_result = None
        self.civilizations = self.engine.civilizations()
        self.state_file = self.project / "project.json"
        state_existed = self.state_file.exists()
        journal_existed = (self.project / "development/events.json").is_file()
        if state_existed:
            self.data = parse_json(safe_path(self.state_file).read_bytes())
            if self.data.get("schema") != SCHEMA or self.data.get("project") != str(self.project):
                raise WorkflowError("Saved project identity does not match")
        else:
            self.data = {"schema": SCHEMA, "project": str(self.project), "project_id": uuid.uuid4().hex,
                         "status": "configuring", "revision": 0, "request": None, "build": None,
                         "progress": {"filled": 0, "total": 0, "errors": []}}
            self._save()
        self.development = DevelopmentJournal(self.project, self.data["project_id"])
        if not state_existed:
            self._dev_event("system", "project_created", "info", "创作项目已创建。")
        elif not journal_existed:
            self._dev_event("system", "journal_started", "info",
                            "开发事件记录从当前版本开始；此前项目历史可能不完整。")
        self._injected_meter = meter_factory is not None
        if meter_factory is None:
            from meter_adapter import MeterAdapter
            meter_factory = MeterAdapter
        self.meter_factory = meter_factory
        self.meter = None
        self._closed_result = None
        # Migrate a previously saved consent without silently changing its scope.
        auth = self.data.get("usage_authorization") or {}
        if auth.get("authorized") and not auth.get("authorization_id"):
            auth["authorization_id"] = uuid.uuid4().hex
            if not self.data.get("usage_source_sha256"):
                self.data["usage_source_sha256"] = self.data.get("input_sha256") or self.engine.source_digest()
            self._save()
        saved_request = self.data.get("request") or {}
        saved_auth = self.data.get("usage_authorization") or {}
        if self.data.get("usage_source_sha256") or saved_request.get("usage_authorized") is True or saved_auth.get("authorized") is True:
            self._open_meter()
            self._sync()

    def _save(self):
        atomic_json(self.state_file, self.data)

    def _dev_event(self, source, kind, severity, message, data=None):
        return self.development.record(source, kind, severity, message, data)

    def _runtime_state(self):
        return {}

    def _browser_observations(self, value):
        if value is None:
            return []
        if not isinstance(value, list) or len(value) > 200:
            raise WorkflowError("browser observations must be an array of at most 200 items")
        clean = []
        allowed = {"kind", "message", "count", "first_at", "last_at"}
        for row in value:
            if not isinstance(row, dict) or not set(row) <= allowed:
                raise WorkflowError("browser observation fields are invalid")
            kind, message = row.get("kind"), row.get("message")
            if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", kind):
                raise WorkflowError("browser observation kind is invalid")
            if not isinstance(message, str) or not 1 <= len(message.strip()) <= 1000:
                raise WorkflowError("browser observation message is invalid")
            item = {"kind": kind, "message": message.strip()}
            if type(row.get("count")) is int and 1 <= row["count"] <= 1000000:
                item["count"] = row["count"]
            for key in ("first_at", "last_at"):
                if isinstance(row.get(key), str) and len(row[key]) <= 64:
                    item[key] = row[key]
            clean.append(item)
        return clean

    def _generate_development_report(self, browser_observations=None):
        usage = self.usage(include_records=True)
        result = generate_reports(
            project=self.project,
            repository_root=ROOT,
            project_snapshot=self.data,
            usage=usage,
            runtime=self._runtime_state(),
            civilization_selection=self._selection_state(),
            events=self.development.read(),
            browser_observations=browser_observations or [],
        )
        result["download_url"] = "/api/report/download?id=" + result["report_id"] + "&format=main"
        result["details_url"] = "/api/report/download?id=" + result["report_id"] + "&format=details"
        return result

    def _open_meter(self):
        """One ledger from consent through delivery; configuring is a real phase."""
        request = self.data.get("request") or {}
        auth = self.data.get("usage_authorization") or {}
        identity = {
            "project_id": self.data["project_id"],
            "source_sha256": self.data.get("usage_source_sha256") or self.data["input_sha256"],
            "agent": self.data.get("usage_agent", auth.get("agent", request.get("agent", "auto"))),
            "workspace_root": str(ROOT), "usage_sessions": self.data.get("usage_sessions", {}),
            "auto_capture": auth.get("authorized", request.get("usage_authorized", False)) is True,
        }
        context = {}
        if request:
            task = self.data.get("task_request", request)
            task_hash = self.data.get("task_sha256", digest(json_bytes(task)))
            if task_hash != digest(json_bytes(task)):
                raise WorkflowError("Frozen task identity changed")
            context = {"task_sha256": task_hash, "game_mode": request["mode"],
                       "civilization": request["civilization"], "script_name": request["script_name"]}
        if self.meter is None:
            self.meter = self.meter_factory(self.project, {**identity, **context})
        elif context:
            update = getattr(self.meter, "update_context", None)
            if callable(update):
                update(context)
            elif self._injected_meter:
                self.meter.identity.update(context)

    def _usage_task(self):
        auth = self.data.get("usage_authorization") or {}
        if not auth.get("authorized") or self.data.get("usage_host_ack") == auth.get("authorization_id"):
            return None
        return {"action": "connect_usage", "authorization_id": auth["authorization_id"],
                "run_id": self.usage().get("run_id"), "agent": auth["agent"],
                "user_action_required": False,
                "instructions": "Use usage --action connect with this authorization_id, actual agent, "
                "and proven session_ids; or status=unavailable with a metadata-only reason. "
                "Do this now, even while game settings are configuring. Never request user session "
                "selection, read credentials, estimate tokens, or start generation before the user."}

    def _usage_connection(self, report):
        auth = self.data.get("usage_authorization") or {}
        capture = report.get("auto_capture") or {}
        measured = report.get("tokens", {}).get("total_tokens") is not None
        if not auth:
            code, label = "NOT_AUTHORIZED", "用量待授权"
        elif not auth.get("authorized"):
            code, label = ("REVOKED", "采集已停止") if auth.get("revoked_at") else ("DISABLED", "本轮不计量")
        elif measured:
            code, label = "RECORDING", "已读到真实用量"
        elif self.data.get("usage_host_status") == "unavailable" or capture.get("connection", {}).get("code") == "EXPLICIT_USAGE_REQUIRED":
            code, label = "LIMITED", "暂未取得真实用量"
        elif capture.get("bound_session_count", 0):
            code, label = "AWAITING_USAGE", "已接入，等待用量"
        else:
            code, label = "CONNECTING", "已授权，正在接入"
        return {"status": code, "code": code, "label": label,
                "authorized": auth.get("authorized") is True,
                "authorized_at": auth.get("decided_at"),
                "agent": self.data.get("usage_agent", auth.get("agent", "auto")),
                "host_acknowledged": bool(auth.get("authorization_id")) and self.data.get("usage_host_ack") == auth.get("authorization_id"),
                "coverage": report.get("coverage", "NOT_CONNECTED"),
                "reason": self.data.get("usage_host_reason", ""),
                "can_revoke": auth.get("authorized") is True and report.get("state") not in {"COMPLETED", "SESSION_CLOSED"}}

    def _selection_pending(self):
        task = self.data.get("task_request") or self.data.get("request") or {}
        return task.get("civilization") == "auto" and self.data.get("civilization_choice") is None

    def _selection_state(self):
        request = self.data.get("request")
        if not request:
            return None
        task = self.data.get("task_request", request)
        automatic = task.get("civilization") == "auto"
        choice = self.data.get("civilization_choice")
        if choice is None and not automatic:
            # Existing manual projects predate explicit selection metadata.
            choice = {"civilization": request["civilization"], "reason": "", "selected_by": "user"}
        return {**self.data.get("civilization_selection", {}),
                "mode": "auto" if automatic else "manual", "choice": choice}

    def _update_meter_civilization(self, civilization):
        update = getattr(self.meter, "update_context", None)
        if callable(update):
            update({"civilization": civilization})
        elif self._injected_meter and isinstance(getattr(self.meter, "identity", None), dict):
            # Compatibility for explicitly injected synthetic test meters only.
            self.meter.identity["civilization"] = civilization
        else:
            raise WorkflowError("The usage adapter cannot persist the selected civilization")

    def _expected(self, payload):
        if type(payload.get("expected_revision")) is not int or payload["expected_revision"] != self.data["revision"]:
            raise WorkflowError("Project changed; refresh its revision before retrying")
        if payload.get("project_id", self.data["project_id"]) != self.data["project_id"]:
            raise WorkflowError("Project identity does not match")

    def _input(self):
        root = safe_path(self.project / "author-input")
        manifest = parse_json(safe_path(root / "manifest.json").read_bytes())
        expected = manifest.get("files", {})
        if not isinstance(expected, dict) or not expected:
            raise WorkflowError("Author input manifest is missing")
        for name, recorded in expected.items():
            path = safe_path(root / name)
            if not path.is_relative_to(root) or name.startswith(("/", "\\")) or ":" in name:
                raise WorkflowError("Author input manifest path is invalid")
            if digest(path.read_bytes()) != recorded:
                raise WorkflowError("Author input changed after export")
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        if actual != set(expected) | {"manifest.json"}:
            raise WorkflowError("Unexpected files in isolated author input")
        bundle_hash = digest(json_bytes(manifest))
        if bundle_hash != self.data["input_sha256"]:
            raise WorkflowError("Author input manifest changed")
        return root, manifest

    def _answers(self):
        root, manifest = self._input()
        directory = safe_path(self.project / "answers")
        expected = {Path(name).name for name in manifest["files"] if name.startswith("answers/")}
        actual = {p.name for p in directory.iterdir()}
        errors = []
        diagnostics = {"missing": {}, "non_integer": {}, "key_mismatch": {}, "unreadable": []}
        if actual != expected:
            errors.append("Answer files differ from the 15 exported answer sheets")
        raw = {}
        filled = 0
        total = 0
        for name in sorted(expected):
            nulls = parse_json((root / "answers" / name).read_bytes())
            total += len(nulls)
            if any(value is not None for value in nulls.values()):
                raise WorkflowError("Isolated input answer sheets must remain all null")
            try:
                content = safe_path(directory / name).read_bytes()
                raw[name] = content
                answers = parse_json(content)
                if not isinstance(answers, dict) or set(answers) != set(nulls):
                    errors.append(name + ": answer keys differ")
                    answer_keys = set(answers) if isinstance(answers, dict) else set()
                    diagnostics["key_mismatch"][name] = {
                        "missing": sorted(set(nulls) - answer_keys),
                        "unexpected": sorted(answer_keys - set(nulls)),
                    }
                    continue
                missing = [key for key, value in answers.items() if value is None]
                non_integer = [key for key, value in answers.items() if value is not None and type(value) is not int]
                if missing:
                    diagnostics["missing"][name] = missing
                if non_integer:
                    diagnostics["non_integer"][name] = non_integer
                filled += sum(type(value) is int for value in answers.values())
                if non_integer:
                    errors.append(name + ": answers must be integers")
            except (OSError, ValueError):
                errors.append(name + ": cannot read valid answer JSON")
                diagnostics["unreadable"].append(name)
        signature = digest(json_bytes({"files": {name: digest(value) for name, value in raw.items()},
                                       "names": sorted(actual), "errors": errors}))
        return raw, signature, {"filled": filled, "total": total, "errors": errors}, diagnostics

    def _write_answer_diagnostics(self, progress, diagnostics):
        missing_count = sum(len(keys) for keys in diagnostics["missing"].values())
        invalid_count = sum(len(keys) for keys in diagnostics["non_integer"].values())
        report = {
            "schema": "aoe2-answer-diagnostics-v1",
            "filled": progress["filled"],
            "total": progress["total"],
            "missing_count": missing_count,
            "invalid_count": invalid_count,
            "errors": list(progress["errors"]),
            **diagnostics,
        }
        path = safe_path(self.project / "tmp" / "answer-diagnostics.json")
        path.parent.mkdir(exist_ok=True)
        atomic_json(path, report)
        return path, missing_count, invalid_count

    def _sync(self):
        if not self.data.get("request"):
            return
        selecting = self._selection_pending()
        previous_status = self.data["status"]
        previous_errors = list((self.data.get("progress") or {}).get("errors") or [])
        try:
            _, current, progress, _ = self._answers()
            if self.engine.source_digest() != self.data["fixed_sha256"]:
                progress["errors"].append("Host fixed source changed; create a fresh project")
            civilization = self.data["request"]["civilization"]
            if civilization not in {row["id"] for row in self.civilizations} and not (selecting and civilization == "auto"):
                progress["errors"].append("The selected civilization is outside the current content profile")
            if selecting and progress["filled"]:
                progress["errors"].append("Keep all answers null until the host freezes the civilization")
            source_error = bool(progress["errors"])
        except (OSError, ValueError):
            current = "invalid_input"
            progress = {"filled": 0, "total": self.data["progress"]["total"], "errors": ["Author input integrity check failed"]}
            source_error = True
        previous = self.data.get("answers_sha256")
        next_status = "invalid" if source_error else ("selecting" if selecting else "authoring")
        if (current != previous or (source_error and self.data["status"] in {"ready", "completed"})
                or (selecting and self.data["status"] != next_status)):
            self.data.update(answers_sha256=current, progress=progress, build=None, validation=None)
            self.data["status"] = next_status
            self.data["revision"] += 1
            self._save()
            if source_error and (previous_status != "invalid" or previous_errors != progress["errors"]):
                self._dev_event("workflow", "input_invalid", "error",
                                "作者输入或答案结构检查失败。",
                                {"errors": list(progress["errors"])})
        elif self.data["status"] in {"authoring", "configuring", "selecting"} and self.data["progress"] != progress:
            self.data["progress"] = progress
            self._save()
        elif self.data["status"] == "completed" and not self._delivery_valid():
            self.data.update(status="invalid", build=None, validation=None)
            self.data["progress"]["errors"] = ["Delivery files changed after build"]
            self.data["revision"] += 1
            self._save()
            self._dev_event("workflow", "delivery_changed", "error",
                            "构建完成后交付文件发生变化，原构建已失效。")

    def usage(self, include_records=False):
        if self.meter:
            return self.meter.report(include_records=include_records)
        return {"state": "NOT_STARTED", "tokens": {"total_tokens": None}, "time": {"elapsed_seconds": 0},
                "coverage": "NOT_CONNECTED", "stages": [], "by_model": [], "capture_gaps": []}

    def preflight(self, force=False):
        # Authoring and script rendering never require a local game installation.
        self._preflight_result = {
            "ready": True,
            "source": "not_required",
            "parameter_authoring_available": True,
            "script_rendering_available": True,
            "game_installation_required": False,
        }
        return dict(self._preflight_result)

    def _write_handoff(self):
        root, manifest = self._input()
        directory = safe_path(self.project / "author-session")
        directory.mkdir(exist_ok=True)
        submissions = safe_path(self.project / "submissions")
        submissions.mkdir(exist_ok=True)
        writer = safe_path(directory / "submit_answers.py")
        writer.write_bytes(safe_path(HERE / "submit_answers.py").read_bytes())
        task = {"schema": "aoe2-author-task-v1", "project_id": self.data["project_id"],
                "task_sha256": self.data["task_sha256"], "input_sha256": self.data["input_sha256"],
                "expected_revision": self.data["revision"], "request": self.data["request"],
                "civilization_selection": self._selection_state(), "eligible_civilizations": self.civilizations,
                "input_read_only": str(root), "answers_read_only": str(self.project / "answers"),
                "submissions": str(submissions), "writer": str(writer),
                "dynamic_slots": manifest["dynamic_slots"],
                "answer_modules": sorted(Path(n).stem for n in manifest["files"] if n.startswith("answers/")),
                "instructions": [
                    "Read only this task, the isolated input, the local writer, and your own submissions/answers.",
                    "Do not read fixed PER, templates, classification, official answers or other projects.",
                    "When civilization is auto, choose first; all answers must remain null until host freezes the choice.",
                    "Query strategy cards by group, decide values, write a small patch under submissions and run the local writer.",
                    "Patch: {module: module_name, answers: {KEY: integer}}. Do not rewrite whole sheets or input files.",
                    "To revise an existing value, read --status MODULE and include its sha256 as expected_sha256.",
                    "Fill every required key, including branches whose runtime applicability is not proven; never auto-fill zero.",
                    "After your strategy review is finished, run the local writer with --complete; filling the last field alone is not completion.",
                    "Do not reduce research, invent facts, or skip the final complete validation."]}
        target = directory / "task.json"
        atomic_json(target, task)
        return {"task_file": str(target), "writer": str(writer), "submissions": str(submissions),
                "dynamic_slots": manifest["dynamic_slots"], "fresh_context_required": True}

    def handoff(self, payload):
        with self.lock:
            self._sync()
            self._expected(payload)
            if not self.data.get("request") or self.data["status"] == "completed":
                raise WorkflowError("Handoff requires a started, unfinished project")
            return self._write_handoff()

    def _author_completed(self):
        path = safe_path(self.project / "author-session/completion.json")
        if not path.is_file():
            return False
        try:
            done = parse_json(path.read_bytes())
            return (done.get("schema") == "aoe2-author-complete-v1" and
                    done.get("project_id") == self.data["project_id"] and
                    done.get("task_sha256") == self.data.get("task_sha256") and
                    done.get("answers_sha256") == self.data.get("answers_sha256"))
        except (OSError, ValueError, AttributeError):
            return False

    def signal(self):
        """Small host-only observation; no catalogs, answer lists or usage histories."""
        with self.lock:
            self._sync()
            task = self._usage_task()
            status = self.data["status"]
            progress = self.data["progress"]
            if task:
                action = "connect_usage"
            elif status == "configuring":
                action = "wait_for_start"
            elif status == "invalid":
                action = "repair_answers"
            elif self._selection_pending():
                action = "choose_civilization"
            elif status == "completed":
                action = "finish"
            elif status == "ready":
                action = "build"
            elif progress["total"] and progress["filled"] == progress["total"] and self._author_completed():
                action = "validate"
            else:
                action = "wait_for_answers"
            result = {"project_id": self.data["project_id"], "revision": self.data["revision"],
                      "status": status, "next_action": action,
                      "progress": {k: progress[k] for k in ("filled", "total")}}
            if task:
                result["usage_task"] = task
            if status == "invalid":
                result["error"] = "Inspect current diagnostics; do not restart the author or discard answers"
                result["diagnostics"] = str(self.project / "tmp/answer-diagnostics.json")
            return result

    def state(self):
        with self.lock:
            self._sync()
            usage = self.usage()
            return {key: self.data[key] for key in ("status", "revision", "request", "progress", "build", "project_id")} | {
                "usage": usage, "usage_connection": self._usage_connection(usage),
                "host_agent": os.environ.get("AOE2_AUTHOR_AGENT", "codex" if os.environ.get("CODEX_THREAD_ID") else "auto"),
                "civilizations": self.civilizations, "agents": agent_catalog(),
                "content_profile": content_profile(), "civilization_selection": self._selection_state(),
                "runtime": self._runtime_state(), "host_required": True,
                "preflight": self.preflight(),
                "usage_authorization": self.data.get("usage_authorization"),
                "usage_access": {
                    "consent_required": False,
                    "metering_opt_in": True,
                    "metering_default_enabled": False,
                    "cursor_admin_configured": bool(os.environ.get("CURSOR_ADMIN_API_KEY")),
                    "copilot_telemetry_configured": bool(os.environ.get("AOE2_COPILOT_USAGE_FILE")),
                }}

    def authorize_usage(self, payload):
        """A click starts a collector, not just a saved preference. Revocation stops it."""
        with self.lock:
            self._expected(payload)
            agent = normalize_agent(payload.get("agent", "auto"))
            authorized = payload.get("usage_authorized")
            if type(authorized) is not bool:
                raise WorkflowError("usage_authorized must be a JSON boolean")
            previous = self.data.get("usage_authorization") or {}
            if previous and previous.get("agent") == agent and previous.get("authorized") == authorized:
                if authorized and self.meter is None:
                    self._open_meter()
                return self.state()
            if authorized and (self.data["status"] != "configuring" or previous.get("revoked_at")):
                raise WorkflowError("Start a new project to authorize again after revocation or generation")
            if (previous.get("authorized") or previous.get("revoked_at")) and agent != previous.get("agent"):
                raise WorkflowError("The authorized host cannot be replaced; stop collection or create a new project")
            now = time.time()
            decision = {"agent": agent, "authorized": authorized, "decided_at": now,
                        "authorization_id": uuid.uuid4().hex}
            if previous.get("revoked_at"):
                decision["revoked_at"] = previous["revoked_at"]
            if previous.get("authorized") and not authorized:
                decision["revoked_at"] = now
                revoke = getattr(self.meter, "revoke", None)
                if callable(revoke):
                    revoke()  # no final sync: revocation must not collect another record
            self.data["usage_authorization"] = decision
            if authorized and not self.data.get("usage_source_sha256"):
                self.data["usage_source_sha256"] = self.engine.source_digest()
            self.data["revision"] += 1
            self._save()
            marker_path = active_project_path(ROOT)
            try:
                current = parse_json(marker_path.read_bytes()) if marker_path.is_file() else {}
            except (OSError, ValueError):
                current = {}
            if current.get("project_id") == self.data["project_id"]:
                atomic_json(marker_path, {**current, "agent": agent,
                    "usage_authorized": authorized, "authorized_at": now})
            if authorized:
                self._open_meter()
            self._dev_event("browser", "usage_authorization", "info",
                            "本轮自动计量已启动。" if authorized else "本轮自动计量已关闭。",
                            {"agent": agent, "authorized": authorized})
            return self.state()

    def start(self, payload):
        with self.lock:
            self._expected(payload)
            if self.data["status"] != "configuring":
                raise WorkflowError("This project's task is frozen; create a new project for another script")
            mode = payload.get("mode")
            civ = payload.get("civilization")
            name = payload.get("script_name")
            output_mode = payload.get("output_mode", "raw_scripts")
            if not isinstance(mode, str) or not isinstance(civ, str) or mode not in MODES or civ not in {"auto", *(row["id"] for row in self.civilizations)}:
                raise WorkflowError("Select a supported mode and civilization")
            if not isinstance(name, str) or not NAME.fullmatch(name):
                raise WorkflowError("Script name must start with a letter and contain 1-48 ASCII letters, digits, underscore or hyphen")
            if not isinstance(output_mode, str) or output_mode not in OUTPUT_MODES:
                raise WorkflowError("Select raw scripts or a share package")
            agent = normalize_agent(payload.get("agent", "auto"))
            explicit_usage_choice = "usage_authorized" in payload
            usage_authorized = payload.get("usage_authorized", False)
            if type(usage_authorized) is not bool:
                raise WorkflowError("usage_authorized must be a JSON boolean")
            authorization = self.data.get("usage_authorization")
            if (explicit_usage_choice or authorization) and (not isinstance(authorization, dict)
                    or authorization.get("agent") != agent
                    or authorization.get("authorized") is not usage_authorized):
                raise WorkflowError("Confirm usage authorization before starting generation")
            request = {"mode": mode, "civilization": civ, "script_name": name, "output_mode": output_mode,
                       "agent": agent, "usage_authorized": usage_authorized}
            selection = selection_context(self.civilizations, self.data["project_id"]) if civ == "auto" else {}
            choice = None if civ == "auto" else {
                "civilization": civ, "reason": "", "selected_by": "user", "selected_at": time.time()}
            # Existing partial exports are never silently reused or overwritten.
            out = safe_path(self.project / "author-input")
            self.engine.export(out)
            manifest = parse_json((out / "manifest.json").read_bytes())
            if manifest.get("dynamic_slots") != 1715 or manifest.get("fixed_source_included") is not False or manifest.get("official_answers_included") is not False:
                raise WorkflowError("Unexpected author input boundary")
            answer_files = list((out / "answers").glob("*.json"))
            if len(answer_files) != 15:
                raise WorkflowError("Expected 15 all-null answer sheets")
            answers = safe_path(self.project / "answers")
            answers.mkdir()
            for source in answer_files:
                (answers / source.name).write_bytes(source.read_bytes())
            self.data.update(request=request, task_request=parse_json(json_bytes(request)),
                             task_sha256=digest(json_bytes(request)),
                             civilization_selection=selection, civilization_choice=choice,
                             input_sha256=digest(json_bytes(manifest)),
                             fixed_sha256=self.engine.source_digest(),
                             status="selecting" if civ == "auto" else "authoring",
                             progress={"filled": 0, "total": 1715, "errors": []})
            self.data["revision"] += 1
            self._save()
            if usage_authorized:
                self._open_meter()
                self.meter.phase("researching" if civ == "auto" else "authoring")
            self._dev_event("workflow", "project_started", "info", "创作已开始。",
                            {"mode": mode, "civilization": civ, "script_name": name, "output_mode": output_mode,
                             "agent": agent, "usage_authorized": usage_authorized})
            self._sync()
            self._write_handoff()
            return self.state()

    def choose_civilization(self, payload):
        with self.lock:
            self._sync()
            self._expected(payload)
            if not self._selection_pending():
                raise WorkflowError("Civilization is already frozen or was specified by the user")
            if self.data["status"] != "selecting":
                raise WorkflowError("Restore the unchanged author input and all-null answers before choosing")
            civilization = payload.get("civilization")
            reason = payload.get("reason")
            available = {row["id"] for row in self.civilizations}
            frozen_pool = self.data.get("civilization_selection", {}).get("eligible_ids", [])
            if not isinstance(civilization, str) or civilization not in available or civilization not in frozen_pool:
                raise WorkflowError("Choose an eligible standard-edition civilization")
            if not isinstance(reason, str) or not 5 <= len(reason.strip()) <= 500:
                raise WorkflowError("Give a short tactical reason of 5-500 characters, not an authoring brief")
            choice = {"civilization": civilization, "reason": reason.strip(),
                      "selected_by": "ai", "selected_at": time.time()}
            if self.meter:
                self._update_meter_civilization(civilization)
                self.meter.phase("authoring")
            self.data.update(request={**self.data["request"], "civilization": civilization},
                             civilization_choice=choice, status="authoring")
            self.data["revision"] += 1
            self._save()
            self._dev_event("author", "civilization_selected", "info",
                            "AI 已确定文明：" + civilization,
                            {"civilization": civilization, "reason": reason.strip()})
            self._write_handoff()
            return self.next()

    def next(self):
        with self.lock:
            state = self.state()
            return {"project_id": state["project_id"], "revision": state["revision"], "status": state["status"],
                    "request": state["request"], "progress": state["progress"], "build": state["build"],
                    "content_profile": state["content_profile"],
                    "civilization_selection": state["civilization_selection"],
                    "choice_contract": {"action": "choose-civilization", "revision": state["revision"],
                                        "required_fields": ["civilization", "reason", "expected_revision"],
                                        "reason": "5-500 characters describing the civilization's tactical fit; no brief",
                                        "answers_must_remain_null": True,
                                        "same_fresh_author_continues_after_choice": True}
                                       if self._selection_pending() else None,
                    "author_input": str(self.project / "author-input") if state["request"] else None,
                    "answers_output": str(self.project / "answers") if state["request"] else None,
                    "author_task": str(self.project / "author-session/task.json") if state["request"] else None,
                    "preflight": self.preflight(),
                    "usage_task": self._usage_task(),
                    "usage_connection": {
                        **state["usage_connection"],
                        "capture": state["usage"].get("auto_capture", {}),
                        "instructions": "If authorized, automatically identify or register only provably project-owned main/child sessions and collect real usage. Never ask the user to choose a session. If ownership is ambiguous, keep a coverage gap. Never infer consumption from context size, character counts, or account totals."},
                    "fresh_context_required": True, "host_required": True,
                    "next_action": ("connect_usage" if self._usage_task() else "wait_for_start") if state["status"] == "configuring" else
                    ("choose_civilization" if self._selection_pending() else
                     ("finish" if state["status"] == "completed" else "author_answers_then_validate"))}

    def _render_snapshot(self):
        self._sync()
        if not self.data.get("request"):
            raise WorkflowError("Start the project first")
        raw, signature, progress, diagnostics = self._answers()
        if self.engine.source_digest() != self.data["fixed_sha256"]:
            raise WorkflowError("Fixed source changed; cannot render this project")
        report, missing_count, invalid_count = self._write_answer_diagnostics(progress, diagnostics)
        if progress["errors"] or progress["filled"] != progress["total"]:
            summary = []
            if missing_count:
                summary.append(str(missing_count) + " missing")
            if invalid_count:
                summary.append(str(invalid_count) + " non-integer")
            if progress["errors"]:
                summary.append(str(len(progress["errors"])) + " file/structure errors")
            raise WorkflowError("Answers incomplete or invalid (" + ", ".join(summary) + "); exact file/key report: " + str(report))
        temporary = safe_path(self.project / "tmp")
        temporary.mkdir(exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="validate-", dir=temporary))
        answers = work / "answers"
        modules = work / "modules"
        answers.mkdir()
        modules.mkdir()
        try:
            for name, content in raw.items():
                (answers / name).write_bytes(content)
            try:
                self.engine.render(answers, modules)
            except (OSError, ValueError) as exc:
                self._write_answer_diagnostics({**progress, "errors": [str(exc)]}, diagnostics)
                raise
            if self._answers()[1] != signature or self.engine.source_digest() != self.data["fixed_sha256"]:
                raise WorkflowError("Answers or fixed source changed during validation")
            return work, modules, signature
        except Exception:
            shutil.rmtree(work)
            raise

    def validate(self, payload):
        with self.lock:
            self._sync()
            self._expected(payload)
            if self._selection_pending():
                raise WorkflowError("Freeze the civilization before validating answers")
            self.meter.phase("checking") if self.meter else None
            try:
                work, modules, signature = self._render_snapshot()
                shutil.rmtree(work)
            except (OSError, ValueError) as exc:
                self.data.update(status="invalid", validation=None, build=None)
                # Only the host receives exact mechanical errors. The browser gets a non-source message.
                self.data["progress"]["errors"] = ["Validation failed; the host must inspect and repair the submitted answers"]
                self.data["revision"] += 1
                self._save()
                evidence = self.development.snapshot("validation_failed", self.project / "tmp/answer-diagnostics.json")
                self._dev_event("workflow", "validation_failed", "error", str(exc),
                                {"evidence": evidence} if evidence else {})
                raise WorkflowError(str(exc)) from None
            self.data.update(status="ready", validation={"answers_sha256": signature, "fixed_sha256": self.data["fixed_sha256"]}, build=None)
            self.data["progress"]["errors"] = []
            self.data["revision"] += 1
            self._save()
            self._dev_event("workflow", "validation_passed", "info", "参数静态校验通过。",
                            {"answers_sha256": signature})
            return self.next()

    def _delivery_valid(self):
        build = self.data.get("build")
        if not build:
            return False
        root = safe_path(self.project / "delivery" / build["build_id"])
        try:
            expected = build.get("artifact_hashes", {})
            actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
            return bool(expected) and actual == set(expected) and all(
                digest(safe_path(root / name).read_bytes()) == value for name, value in expected.items())
        except (OSError, ValueError):
            return False

    def delivery_file(self):
        with self.lock:
            self._sync()
            build = self.data.get("build") or {}
            if self.data.get("status") != "completed" or build.get("output_mode") != "share_package":
                raise WorkflowError("This project has no share package")
            if not self._delivery_valid():
                raise WorkflowError("Share package delivery is no longer valid")
            path = safe_path(build.get("package_file", ""))
            root = safe_path(self.project / "delivery" / build["build_id"])
            if path.parent != root or path.suffix.lower() != ".zip" or not path.is_file():
                raise WorkflowError("Share package path is invalid")
            return path

    def build(self, payload):
        with self.lock:
            self._sync()
            self._expected(payload)
            if self._selection_pending():
                raise WorkflowError("Freeze the civilization before building")
            validation = self.data.get("validation")
            if not validation or validation["answers_sha256"] != self.data.get("answers_sha256"):
                raise WorkflowError("Validate the current answers before building")
            if self.meter:
                self.meter.phase("packaging")
            self.data["status"] = "rendering"
            self._save()
            work = None
            output = None
            try:
                work, modules, signature = self._render_snapshot()
                rendered = sorted(path for path in modules.glob("*.per") if path.is_file())
                if len(rendered) != 36 or len({path.name.casefold() for path in rendered}) != 36:
                    raise WorkflowError("Script delivery requires exactly 36 rendered PER files")
                build_id = "build-" + uuid.uuid4().hex[:12]
                output = safe_path(self.project / "delivery" / build_id)
                output.mkdir(parents=True)
                script_name = self.data["request"]["script_name"]
                output_mode = self.data["request"].get("output_mode", "raw_scripts")
                if output_mode not in OUTPUT_MODES:
                    raise WorkflowError("Saved output mode is invalid")

                build_extra = {}
                if output_mode == "raw_scripts":
                    script_root = safe_path(output / script_name)
                    script_root.mkdir()
                    for source in rendered:
                        (script_root / source.name).write_bytes(source.read_bytes())
                    files = {path.relative_to(output).as_posix(): digest(path.read_bytes())
                             for path in output.rglob("*") if path.is_file()}
                    if len(files) != 36 or any(not name.lower().endswith(".per") for name in files):
                        raise WorkflowError("Raw script delivery must contain only the 36 rendered PER files")
                    artifact_kind = "aoe2_per_scripts"
                    package_sha256 = digest(json_bytes(files))
                    build_extra["script_root"] = str(script_root)
                else:
                    per_hashes = {source.name: digest(source.read_bytes()) for source in rendered}
                    manifest = {
                        "schema": "aoe2-share-script-package-v1",
                        "script_name": script_name,
                        "script_files": 36,
                        "files_sha256": per_hashes,
                        "installable": False,
                        "description": "Portable AOE2-AI PER script bundle; no game installation files included.",
                    }
                    package_name = script_name + ".zip"
                    package_path = safe_path(output / package_name)
                    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                        for source in rendered:
                            info = zipfile.ZipInfo(script_name + "/" + source.name, (1980, 1, 1, 0, 0, 0))
                            info.compress_type = zipfile.ZIP_DEFLATED
                            info.external_attr = 0o644 << 16
                            archive.writestr(info, source.read_bytes())
                        readme = (
                            "AOE2-AI 分享脚本包\n"
                            "包含 36 个 .per 脚本文件。\n"
                            "这是便于发送和保存的脚本归档，不是游戏安装包。\n"
                        ).encode("utf-8")
                        for name, data in (("README.txt", readme), ("manifest.json", json_bytes(manifest))):
                            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                            info.compress_type = zipfile.ZIP_DEFLATED
                            info.external_attr = 0o644 << 16
                            archive.writestr(info, data)
                    files = {package_name: digest(package_path.read_bytes())}
                    artifact_kind = "aoe2_per_share_package"
                    package_sha256 = files[package_name]
                    build_extra.update(package_file=str(package_path), package_name=package_name)

                if self._answers()[1] != signature or self.engine.source_digest() != self.data["fixed_sha256"]:
                    raise WorkflowError("Answers or source changed before delivery; the new directory is not a valid build")
                artifact_hashes = dict(files)
                build = {
                    "schema": "aoe2-web-author-script-delivery-v2",
                    "project_id": self.data["project_id"],
                    "build_id": build_id,
                    "script_name": script_name,
                    "output_mode": output_mode,
                    "answers_sha256": signature,
                    "fixed_sha256": self.data["fixed_sha256"],
                    "input_sha256": self.data["input_sha256"],
                    "artifact_kind": artifact_kind,
                    "modules": 36,
                    "script_files": 36,
                    "static_validation": "PASS",
                    "path": str(output),
                    "artifact_hashes": artifact_hashes,
                    "package_sha256": package_sha256,
                    **build_extra,
                }
                self.data.update(build=build, status="completed")
                try:
                    registry = register_completed_project(self.project, self.data, db_path=self.registry_db)
                    self.data["registry"] = registry
                    self._dev_event("workflow", "work_registered", "info", "作品已自动登记。",
                                    {"work_id": registry["work_id"], "script_name": registry["script_name"],
                                     "duplicate": registry["duplicate"]})
                except (OSError, ValueError, RegistryError) as exc:
                    self.data["registry"] = {"ok": False, "error": str(exc)}
                    self._dev_event("workflow", "work_registration_failed", "error", "作品自动登记失败。",
                                    {"error": str(exc)})
                self.data["revision"] += 1
                self._save()
                self._dev_event("workflow", "build_completed", "info", "脚本生成完成。",
                                {"build_id": build_id, "package_sha256": build["package_sha256"],
                                 "script_files": 36, "output_mode": output_mode})
                return self.next()
            except (OSError, ValueError, zipfile.BadZipFile) as exc:
                if output is not None and output.exists():
                    shutil.rmtree(output)
                self.data.update(status="invalid", build=None, validation=None)
                self.data["revision"] += 1
                self._save()
                self._dev_event("workflow", "build_failed", "error", str(exc),
                                {"stage": "script_render"})
                raise
            finally:
                if work:
                    shutil.rmtree(work)

    def phase(self, payload):
        with self.lock:
            self._sync()
            self._expected(payload)
            if self._selection_pending() and payload.get("value") != "researching":
                raise WorkflowError("Only the research phase is allowed before choosing a civilization")
            result = self.meter.phase(payload["value"]) if self.meter else self.usage()
            self._dev_event("workflow", "phase_changed", "info", "创作阶段切换：" + payload["value"],
                            {"phase": payload["value"]})
            return result

    def refresh_cursor_admin_usage(self, payload):
        """Same-origin browser refresh of official Cursor Usage Events; API key never reaches the browser."""
        with self.lock:
            self._expected(payload)
            if not self.meter:
                raise WorkflowError("Start the project before refreshing Cursor usage")
            report = self.usage()
            if payload.get("run_id") != report.get("run_id"):
                raise WorkflowError("Usage run identity does not match")
            capture = report.get("auto_capture", {})
            if capture.get("selected_agent") != "cursor":
                raise WorkflowError("Cursor official usage refresh is only available for a Cursor project")
            return self.usage_action("cursor-admin", payload)

    def usage_action(self, action, payload):
        with self.lock:
            if not self.meter:
                raise WorkflowError("Authorize this project before connecting usage")
            self._expected(payload)
            auth = self.data.get("usage_authorization")
            if auth and not auth.get("authorized") and action not in {"complete", "phase"}:
                raise WorkflowError("Usage collection is not authorized for this project")
            if action == "connect":
                if not auth or payload.get("authorization_id") != auth.get("authorization_id"):
                    raise WorkflowError("Usage authorization changed; read next before connecting")
                agent = normalize_agent(payload.get("agent", auth["agent"]))
                if auth["agent"] not in {"auto", agent}:
                    raise WorkflowError("Host does not match the authorized Agent")
                status = payload.get("status", "ready")
                sessions = payload.get("session_ids", [])
                reason = payload.get("reason", "")
                if status not in {"ready", "unavailable"} or not isinstance(reason, str) or len(reason) > 300:
                    raise WorkflowError("Invalid connection result")
                if not isinstance(sessions, list) or len(sessions) > 128 or any(not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", v) for v in sessions):
                    raise WorkflowError("Provide proven session IDs only")
                if status == "ready" and (agent == "auto" or not sessions):
                    raise WorkflowError("Ready requires an actual host and proven session IDs")
                connect = getattr(self.meter, "connect", None)
                if callable(connect) and agent != "auto":
                    connect(agent, sessions)
                self.data.update(usage_agent=agent, usage_host_ack=auth["authorization_id"],
                                 usage_host_status=status, usage_host_reason=reason.strip())
                if sessions:
                    existing = self.data.setdefault("usage_sessions", {}).setdefault(agent, [])
                    self.data["usage_sessions"][agent] = sorted(set(existing) | set(sessions))
                self._save()
                marker_path = active_project_path(ROOT)
                try:
                    marker = parse_json(marker_path.read_bytes()) if marker_path.is_file() else {}
                except (OSError, ValueError):
                    marker = {}
                if marker.get("project_id") == self.data["project_id"]:
                    atomic_json(marker_path, {**marker, "agent": agent,
                        "usage_authorized": True, "authorized_at": auth.get("decided_at")})
                return self.next()
            if action == "phase" and self._selection_pending() and str(payload.get("phase")) not in {"1", "researching"}:
                raise WorkflowError("Only the research phase is allowed before choosing a civilization")
            if action == "bind":
                sessions = payload.get("sessions")
                if not isinstance(sessions, dict):
                    raise WorkflowError("sessions must be an explicit host-to-session mapping")
                result = self.meter.bind_sessions(sessions)
                existing = self.data.setdefault("usage_sessions", {})
                for host, ids in sessions.items():
                    existing[host] = sorted(set(existing.get(host, [])) | set(ids))
                self._save()
                self._dev_event("system", "usage_sessions_bound", "info", "已绑定用量会话。",
                                {"hosts": {host: len(ids) for host, ids in sessions.items()}})
                return result
            if action == "complete":
                self._sync()
                if self.data["status"] != "completed" or not self._delivery_valid():
                    raise WorkflowError("Only an unchanged validated build can complete usage")
                declared = payload.get("all_sources_declared", False)
                if type(declared) is not bool:
                    raise WorkflowError("all_sources_declared must be a JSON boolean")
                result = self.meter.complete(self.data["build"], declared)
                self._dev_event("system", "usage_completed", "info", "用量记录已封账。",
                                {"all_sources_declared": declared, "coverage": result.get("coverage")})
                return result
            return self.meter.handle(action, payload)

    def feedback(self, payload):
        with self.lock:
            self._expected(payload)
            source = payload.get("source", "host")
            kind = payload.get("kind")
            message = payload.get("message")
            event = self.development.feedback(source, kind, message, {"revision": self.data["revision"]})
            return {"ok": True, "event": event}

    def development_report(self, payload):
        with self.lock:
            if payload.get("project_id") != self.data["project_id"]:
                raise WorkflowError("Project identity does not match")
            self._sync()
            feedback = payload.get("feedback")
            if feedback is not None:
                if not isinstance(feedback, str) or len(feedback.strip()) > 4000:
                    raise WorkflowError("Report feedback must be at most 4000 characters")
                if feedback.strip():
                    self.development.feedback("browser", "note", feedback.strip(),
                                              {"revision": self.data["revision"]})
            observations = self._browser_observations(payload.get("browser_observations"))
            result = self._generate_development_report(observations)
            self._dev_event("system", "report_generated", "info", "开发报告已生成。",
                            {"report_id": result["report_id"], "issue_count": result["issue_count"],
                             "feedback_count": result["feedback_count"]})
            return result

    def development_report_file(self, report_id, format_name="main"):
        return report_file(self.project, report_id, format_name)

    def close(self):
        with self.lock:
            if self._closed_result is not None:
                return self._closed_result
            self._sync()
            if self.meter and self.data["status"] == "completed" and self._delivery_valid():
                self.meter.complete(self.data["build"], all_sources_declared=False)
            report = self.meter.close() if self.meter else self.usage()
            self._dev_event("workflow", "session_finished", "info", "创作会话已结束。",
                            {"status": self.data["status"], "coverage": report.get("coverage")})
            try:
                final_report = self._generate_development_report()
                final_report.pop("markdown", None)
                self._dev_event("system", "final_report_generated", "info", "最终开发报告已自动生成。",
                                {"report_id": final_report["report_id"]})
            except (OSError, ValueError, DevelopmentReportError) as exc:
                final_report = {"error": str(exc)}
                self._dev_event("system", "final_report_failed", "error", "最终开发报告生成失败。",
                                {"error": str(exc)})
            self._closed_result = {"status": "SESSION_FINISHED", "project_id": self.data["project_id"], "usage": report,
                                   "build": self.data.get("build"), "development_report": final_report}
            return self._closed_result
