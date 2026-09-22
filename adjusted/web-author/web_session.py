#!/usr/bin/env python3
"""Browser launcher and bounded model-neutral host handoff. No model calls."""
from __future__ import annotations
import argparse
import contextlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
import uuid
import webbrowser

from controller import Controller, PROJECTS, ROOT, WorkflowError, atomic_json, parse_json, project_path, safe_path
from server import SESSION_SCHEMA, make_server

SESSION_FILE = ".author-web-session.json"


class SessionError(WorkflowError):
    pass


class ActiveLock:
    """An OS lock, released even on process failure; never a stale PID guess."""
    def __init__(self, path=None):
        self.path = path or (PROJECTS / ".active.lock")
        self.file = None

    def __enter__(self):
        safe_path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"\0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            raise SessionError("Another author project is active; finish that session first") from None
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SessionError("Local author connections never follow redirects")


def validated_base(url):
    parsed = urlparse(url)
    if not (parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port
            and not parsed.username and not parsed.password and parsed.path in {"", "/"}
            and not parsed.query and not parsed.fragment):
        raise SessionError("Only a local author service is allowed")
    return url.rstrip("/")


def request(meta, route, payload=None, timeout=10, waiting=False):
    base = validated_base(meta["url"])
    headers = {"X-Author-Token": meta["host_token"]}
    if waiting:
        headers["X-Author-Wait"] = "1"
    raw = None
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(base + route, data=raw, headers=headers)
    with opener.open(req, timeout=timeout) as response:
        return json.load(response)


def descriptor(project):
    path = safe_path(project / SESSION_FILE)
    if not path.exists():
        return None
    data = parse_json(path.read_bytes())
    if (data.get("schema") != SESSION_SCHEMA or data.get("project") != str(project)
            or data.get("root") != str(ROOT) or not data.get("host_token")):
        raise SessionError("Saved web connection belongs to a different project or repository")
    validated_base(data["url"])
    return data


def connected(project):
    data = descriptor(project)
    if data is None:
        return None
    try:
        remote = request(data, "/api/author/session", timeout=2)
    except urllib.error.HTTPError:
        raise SessionError("The recorded port is not the current author session") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None
    if (remote.get("schema"), remote.get("instance_id"), remote.get("project_id")) != (
            SESSION_SCHEMA, data.get("instance_id"), data.get("project_id")):
        raise SessionError("Session identity changed; refusing to reuse the old connection")
    return data


def public_meta(meta):
    return {key: value for key, value in meta.items() if key != "host_token"}


def wait_for_agent(meta, timeout=20, interval=0.5, *, read=request, sleep=time.sleep, clock=time.monotonic):
    if not math.isfinite(timeout) or not 0 <= timeout <= 20:
        raise SessionError("Wait must be between 0 and 20 seconds")
    if not math.isfinite(interval) or interval <= 0:
        raise SessionError("Polling interval must be positive")
    deadline = clock() + timeout
    while True:
        identity = read(meta, "/api/author/session")
        if (identity.get("instance_id"), identity.get("project_id")) != (meta["instance_id"], meta["project_id"]):
            raise SessionError("Project/session identity changed while waiting")
        state = read(meta, "/api/author/next", waiting=True)
        if state.get("project_id") != meta["project_id"]:
            raise SessionError("Next action belongs to a different project")
        if state.get("status") != "configuring":
            return {**state, "web_event": "AUTHOR_ACTION_REQUIRED", "url": meta["url"]}
        if clock() >= deadline:
            return {**state, "web_event": "WAIT_TIMEOUT", "continue_waiting": True, "url": meta["url"],
                    "message": "Browser cannot wake an exited host; keep the host task active or run wait again"}
        sleep(min(interval, max(0, deadline - clock())))


def serve(project, port=0):
    with ActiveLock():
        app = Controller(project)
        meta = {"schema": SESSION_SCHEMA, "root": str(ROOT), "project": str(project),
                "project_id": app.data["project_id"], "instance_id": uuid.uuid4().hex,
                "host_token": uuid.uuid4().hex + uuid.uuid4().hex}
        server = make_server(app, meta, port)
        meta["url"] = "http://127.0.0.1:" + str(server.server_port)
        try:
            atomic_json(project / SESSION_FILE, meta)
            print(json.dumps(public_meta(meta), ensure_ascii=False), flush=True)
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            try:
                app.close()
            finally:
                if descriptor(project) == meta:
                    (project / SESSION_FILE).unlink(missing_ok=True)


def launch(project, port=0, *, open_browser=True, test_project=False):
    data = connected(project)
    if data is None:
        project.mkdir(parents=True, exist_ok=True)
        logs = safe_path(project / "logs")
        logs.mkdir(exist_ok=True)
        log_path = logs / "web-session.log"
        command = [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()), "serve",
                   "--project", str(project), "--port", str(port)]
        if test_project:
            command.append("--test-project")
        options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with log_path.open("ab") as log:
            child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **options)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            data = connected(project)
            if data:
                break
            if child.poll() is not None:
                raise SessionError("Author service did not start; inspect " + str(log_path))
            time.sleep(0.15)
        if data is None:
            child.terminate()
            child.wait(timeout=5)
            raise SessionError("Author service startup timed out; inspect " + str(log_path))
    opened = False
    if open_browser:
        try:
            opened = bool(webbrowser.open(data["url"]))
        except webbrowser.Error:
            pass
    return data, opened


def host_action(meta, action, extra=None):
    if action == "choose-civilization":
        if not isinstance(extra, dict) or type(extra.get("expected_revision")) is not int:
            raise SessionError("Choice must include expected_revision from the decision's next response")
        payload = dict(extra)
        if payload.get("project_id", meta["project_id"]) != meta["project_id"]:
            raise SessionError("Choice belongs to a different project")
        payload["project_id"] = meta["project_id"]
    else:
        current = request(meta, "/api/author/next")
        payload = {"project_id": meta["project_id"], "expected_revision": current["revision"]}
        payload.update(extra or {})
    route = "/api/author/session/finish" if action == "finish" else "/api/host/" + action
    return request(meta, route, payload, timeout=120 if action in {"choose-civilization", "validate", "build"} else 10)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("launch", "serve", "wait", "next", "choose-civilization", "validate", "build", "phase", "finish", "usage"):
        sub = commands.add_parser(name)
        sub.add_argument("--project", required=True)
        sub.add_argument("--test-project", action="store_true", help="Explicit synthetic project inside temporary storage")
        if name in {"launch", "serve"}:
            sub.add_argument("--port", type=int, default=0)
        if name == "launch":
            sub.add_argument("--no-browser", action="store_true")
        if name in {"launch", "wait"}:
            sub.add_argument("--timeout", type=float, default=0 if name == "launch" else 20)
        if name == "choose-civilization":
            sub.add_argument("--choice", type=Path, required=True,
                             help="JSON with civilization, reason and the expected_revision returned for this decision")
        if name == "phase":
            sub.add_argument("--value", required=True, choices=["researching", "authoring", "checking", "repairing", "packaging"])
        if name == "usage":
            sub.add_argument("--action", choices=["report", "source", "events", "seal", "complete", "bind", "ccusage"], default="report")
            sub.add_argument("--payload", type=Path)
    args = parser.parse_args(argv)
    try:
        project = project_path(args.project, args.test_project)
        if args.command == "serve":
            serve(project, args.port)
            return 0
        if args.command == "launch":
            if not math.isfinite(args.timeout) or not 0 <= args.timeout <= 20:
                raise SessionError("Wait must be between 0 and 20 seconds")
            meta, opened = launch(project, args.port, open_browser=not args.no_browser, test_project=args.test_project)
            result = {**public_meta(meta), "browser_opened": opened, "web_event": "SESSION_READY"}
            if args.timeout:
                print(json.dumps(result, ensure_ascii=False), flush=True)
                result = wait_for_agent(meta, args.timeout)
        else:
            meta = connected(project)
            if meta is None:
                raise SessionError("No running author session; the host must run launch")
            if args.command == "wait":
                result = wait_for_agent(meta, args.timeout)
            elif args.command == "next":
                result = request(meta, "/api/author/next")
            elif args.command == "choose-civilization":
                result = host_action(meta, args.command, parse_json(args.choice.read_bytes()))
            elif args.command == "usage":
                if args.action == "report":
                    result = request(meta, "/api/author/usage")
                else:
                    extra = parse_json(args.payload.read_bytes()) if args.payload else {}
                    state = request(meta, "/api/author/next")
                    usage = request(meta, "/api/author/usage")
                    payload = {**extra, "project_id": meta["project_id"], "expected_revision": state["revision"], "run_id": usage["run_id"]}
                    result = request(meta, "/api/author/usage/" + args.action, payload)
            else:
                result = host_action(meta, args.command, {"value": args.value} if args.command == "phase" else None)
                if args.command == "finish":
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if not (project / SESSION_FILE).exists():
                            break
                        time.sleep(0.1)
                    else:
                        raise SessionError("Session did not finish within 10 seconds; do not start another project")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"error": "Only waiting was cancelled; saved project state is unchanged"}, ensure_ascii=False), file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        print(json.dumps({"error": detail}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
