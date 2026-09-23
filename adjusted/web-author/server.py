"""Loopback HTTP surface for authoring, metering and developer report snapshots."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import re
import threading
import time
from urllib.parse import parse_qs, urlparse
from controller import HERE, WorkflowError, parse_json

SESSION_SCHEMA = "aoe2-web-author-session-v1"
MAX_BODY = 2 * 1024 * 1024


def make_server(controller, meta, port=0):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalAuthor/1"
        last_wait = None

        def log_message(self, format, *args):
            pass

        def _json(self, value, status=200):
            raw = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            self._send(raw, "application/json; charset=utf-8", status)

        def _send(self, raw, content_type, status=200, filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            if filename is not None:
                if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", filename):
                    raise WorkflowError("Invalid download filename")
                self.send_header("Content-Disposition", 'attachment; filename="' + filename + '"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def _host_authorized(self):
            return hmac.compare_digest(self.headers.get("X-Author-Token", ""), meta["host_token"])

        def _local_request(self, mutation=False):
            allowed_hosts = {"127.0.0.1:" + str(self.server.server_port), "localhost:" + str(self.server.server_port)}
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if (self.client_address[0] != "127.0.0.1" or host not in allowed_hosts or
                    (origin is not None and origin != "http://" + host) or
                    self.headers.get("Sec-Fetch-Site") == "cross-site"):
                self._json({"error": "Only the current loopback origin is allowed"}, 403)
                return False
            if mutation and origin is None and not self._host_authorized():
                self._json({"error": "Same-origin browser or authenticated host required"}, 403)
                return False
            return True

        def _host(self):
            if not self._host_authorized():
                self._json({"error": "This action requires the current host session"}, 403)
                return False
            return True

        def do_GET(self):
            if not self._local_request():
                return
            try:
                parsed = urlparse(self.path)
                route = parsed.path
                if route == "/api/state":
                    return self._json(controller.state())
                if route == "/api/civilizations" and not parsed.query:
                    from civilization_catalog import catalog
                    return self._json(catalog())
                if route == "/api/agents" and not parsed.query:
                    from agent_catalog import agent_catalog
                    return self._json({"agents": agent_catalog()})
                if route.startswith("/assets/civilizations/") and not parsed.query:
                    name = route.removeprefix("/assets/civilizations/")
                    from civilization_catalog import catalog
                    allowed_icons = {row["icon"] for row in catalog()["civilizations"]}
                    if route not in allowed_icons or not re.fullmatch(r"[A-Za-z]+\.png", name):
                        return self._json({"error": "Unknown civilization icon"}, 404)
                    return self._send((HERE / "web/assets/civilizations" / name).read_bytes(), "image/png")
                if route == "/api/author/session":
                    elapsed = None if Handler.last_wait is None else time.monotonic() - Handler.last_wait
                    return self._json({"schema": SESSION_SCHEMA, "instance_id": meta["instance_id"],
                                       "project_id": meta["project_id"], "agent_waiting": elapsed is not None and elapsed < 25,
                                       "host_required": True, "ui_version": "shield-host-v2"})
                if route == "/api/author/next":
                    if not self._host():
                        return
                    if self.headers.get("X-Author-Wait") == "1":
                        Handler.last_wait = time.monotonic()
                    return self._json(controller.next())
                if route == "/api/author/usage":
                    return self._json(controller.usage())
                if route == "/api/report/download":
                    query = parse_qs(parsed.query)
                    report_id = query.get("id", [""])[0]
                    fmt = query.get("format", ["main"])[0]
                    report = controller.development_report_file(report_id, fmt)
                    return self._send(report.read_bytes(), "text/markdown; charset=utf-8", filename=report.name)
                if route == "/api/author/usage/export":
                    fmt = parse_qs(parsed.query).get("format", ["json"])[0]
                    if fmt not in {"json", "stages", "calls"}:
                        raise WorkflowError("Export format must be json, stages, or calls")
                    report = controller.usage(include_records=True)
                    if fmt == "json":
                        return self._json(report)
                    from metering import Meter
                    return self._send(Meter.csv_bytes(report, fmt), "text/csv; charset=utf-8")
                static = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/index.html": ("index.html", "text/html; charset=utf-8"),
                          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "/styles.css": ("styles.css", "text/css; charset=utf-8")}
                if route in static and not parsed.query:
                    name, mime = static[route]
                    return self._send((HERE / "web" / name).read_bytes(), mime)
                self._json({"error": "Unknown route"}, 404)
            except (OSError, ValueError, KeyError):
                self._json({"error": "Unable to read the current project"}, 409)

        def do_POST(self):
            if not self._local_request(mutation=True):
                return
            try:
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                    return self._json({"error": "JSON request required"}, 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self._json({"error": "Invalid request size"}, 413)
                payload = parse_json(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise WorkflowError("JSON object required")
                route = urlparse(self.path).path
                if route == "/api/start":
                    return self._json(controller.start(payload))
                if route == "/api/usage/bind-session":
                    return self._json(controller.bind_usage_candidate(payload))
                if route == "/api/report/generate":
                    return self._json(controller.development_report(payload))
                if not self._host():
                    return
                if payload.get("project_id") != meta["project_id"]:
                    raise WorkflowError("Project identity does not match")
                if route == "/api/host/choose-civilization":
                    return self._json(controller.choose_civilization(payload))
                if route == "/api/host/validate":
                    return self._json(controller.validate(payload))
                if route == "/api/host/build":
                    return self._json(controller.build(payload))
                if route == "/api/host/phase":
                    return self._json(controller.phase(payload))
                if route == "/api/host/feedback":
                    return self._json(controller.feedback(payload))
                if route == "/api/author/session/finish":
                    with controller.lock:
                        controller._sync()
                        controller._expected(payload)
                        result = controller.close()
                    self._json(result)
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                prefix = "/api/author/usage/"
                if route.startswith(prefix):
                    action = route[len(prefix):]
                    if action not in {"source", "events", "seal", "phase", "complete", "bind", "ccusage"}:
                        return self._json({"error": "Unknown usage action"}, 404)
                    current = controller.usage()
                    if payload.get("run_id") != current.get("run_id"):
                        raise WorkflowError("Usage run identity does not match")
                    return self._json(controller.usage_action(action, payload))
                self._json({"error": "Unknown route"}, 404)
            except (OSError, ValueError, KeyError) as exc:
                # Detailed renderer diagnostics are restricted to the authenticated host.
                error = str(exc) if self._host_authorized() else "请求未完成，请刷新当前项目后重试。"
                self._json({"error": error}, 409)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
