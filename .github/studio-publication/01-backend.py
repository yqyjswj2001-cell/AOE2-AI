# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/web-author/controller.py', 'cfb8f04358797bb7d2e5a91867d8ca61b34ada66ae9ddb1494b1951dd6505e9c', '239a00fe59475835bda0ffcb59a756e18e549d60796ad2b0e9a75e91df6bb385', [
(175, 176, r'''        # Migrate a previously saved consent without silently changing its scope.
        auth = self.data.get("usage_authorization") or {}
        if auth.get("authorized") and not auth.get("authorization_id"):
            auth["authorization_id"] = uuid.uuid4().hex
            if not self.data.get("usage_source_sha256"):
                self.data["usage_source_sha256"] = self.data.get("input_sha256") or self.engine.source_digest()
            self._save()
        if self.data.get("request") or self.data.get("usage_source_sha256"):
'''),
(230, 242, r'''        """One ledger from consent through delivery; configuring is a real phase."""
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
'''),
(410, 410, r'''            usage = self.usage()
'''),
(411, 412, r'''                "usage": usage, "usage_connection": self._usage_connection(usage),
                "host_agent": os.environ.get("AOE2_AUTHOR_AGENT", "codex" if os.environ.get("CODEX_THREAD_ID") else "auto"),
                "civilizations": self.civilizations, "agents": agent_catalog(),
'''),
(422, 423, r'''        """A click starts a collector, not just a saved preference. Revocation stops it."""
'''),
(425, 428, r'''            agent = normalize_agent(payload.get("agent", "auto"))
'''),
(431, 433, r'''            previous = self.data.get("usage_authorization") or {}
'''),
(434, 434, r'''                if authorized and self.meter is None:
                    self._open_meter()
'''),
(435, 435, r'''            if authorized and (self.data["status"] != "configuring" or previous.get("revoked_at")):
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
'''),
(436, 436, r'''            if authorized and not self.data.get("usage_source_sha256"):
                self.data["usage_source_sha256"] = self.engine.source_digest()
'''),
(438, 439, r''''''),
(446, 448, r'''                    "usage_authorized": authorized, "authorized_at": now})
            if authorized:
                self._open_meter()
'''),
(449, 450, r'''                            "本轮自动计量已启动。" if authorized else "本轮自动计量已关闭。",
'''),
(474, 475, r'''            if (explicit_usage_choice or authorization) and (not isinstance(authorization, dict)
'''),
(557, 557, r'''                    "usage_task": self._usage_task(),
'''),
(558, 560, r'''                        **state["usage_connection"],
'''),
(563, 564, r'''                    "next_action": ("connect_usage" if self._usage_task() else "wait_for_start") if state["status"] == "configuring" else
'''),
(748, 749, r'''                raise WorkflowError("Authorize this project before connecting usage")
'''),
(750, 750, r'''            auth = self.data.get("usage_authorization")
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
'''),
])
