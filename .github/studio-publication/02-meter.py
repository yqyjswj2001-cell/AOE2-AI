# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/web-author/agent_catalog.py', 'f4b8a5bced5dfef8d3631cab6e2c632043292d02a5319ea33693b5902fd93892', 'e18b0fc31d05863484b90d587154a419694e54f0dfb8e51740a0cfdd437809ec', [
(4, 5, r'''    ("auto", "当前 Agent（自动确认）", "explicit_binding", "由正在执行本轮任务的 Agent 确认来源，不扫描其他已安装工具。", "先选择实际 Agent；会话由后台自动识别，无法唯一确认时保留缺口。"),
'''),
])
edit('adjusted/web-author/meter_adapter.py', '14510b378bbfaf8f55a33bd71e83379c91f3fdc684825fc164399442ac9a0e7f', '0c0f209a9ba7c23ee2414e3b3f4046284d3c9bc6f04724e5f3b5a14540730512', [
(59, 59, r'''        self._poll_thread = None
        self._last_sync = 0.0
'''),
(69, 69, r'''            if selected_agent == "auto":
                selected_agent = normalize_agent(os.environ.get("AOE2_AUTHOR_AGENT", "codex" if thread else "auto"))
            host_session = os.environ.get("AOE2_AUTHOR_SESSION_ID")
            if host_session and not existed and os.environ.get("AOE2_AUTHOR_AGENT") == selected_agent:
                bindings.setdefault(selected_agent, []).append(host_session)
'''),
(74, 74, r'''        if self.auto is not None:
            self._poll_thread = threading.Thread(target=self._poll_loop, name="aoe2-usage-collector", daemon=True)
            self._poll_thread.start()
'''),
(80, 80, r'''    def _poll_loop(self):
        """Collection continues without an open browser; HTTP reads are not the scheduler."""
        while not self._cursor_stop.wait(3):
            with self.lock:
                if self.auto is None or self.meter.meta["state"] != "RUNNING":
                    return
                try:
                    self._sync()
                except (OSError, ValueError):
                    self.meter.capture({"status": "ERROR", "scope": "BOUND_SESSIONS_ONLY"},
                        [{"code": "AUTO_CAPTURE_ERROR", "message": GAP_MESSAGES["AUTO_CAPTURE_ERROR"]}])

    def connect(self, agent, session_ids):
        with self.lock:
            require(self.meter.meta["state"] == "RUNNING", "计量已结束，不能重新接入。")
            require(self.auto is not None, "本轮未授权采集。")
            agent = normalize_agent(agent)
            require(self.auto.selected_agent in {"auto", agent}, "不能替换已确认的采集宿主。")
            self.auto.selected_agent = agent
            if session_ids:
                self.auto.bind({agent: session_ids})
            self.auto._save()
            self._sync()
            if agent == "cursor" and os.environ.get("CURSOR_ADMIN_API_KEY") and self._cursor_refresh_thread is None:
                self._cursor_refresh_thread = threading.Thread(target=self._cursor_refresh_loop,
                    name="aoe2-cursor-usage", daemon=True)
                self._cursor_refresh_thread.start()
            return self.report()

    def revoke(self):
        """Stop before any further scan or final refresh. Preserve the existing ledger."""
        self._cursor_stop.set()
        with self.lock:
            self.auto = None
            self.meter.capture({"status": "DISABLED", "scope": "REVOKED",
                                "active_sessions": [], "events_added": 0},
                               [{"code": "CONSENT_REVOKED", "message": "授权已撤回；停止后发生的消耗不在覆盖范围内。"}])

'''),
(82, 83, r'''        delay = 1
'''),
(93, 93, r'''                    last = self.auto.state.get("cursor_admin_last_refresh")
                    if isinstance(last, (int, float)) and time.time() - last < 3600:
                        delay = max(1, 3600 - (time.time() - last))
                        continue
'''),
(99, 100, r'''        if (self.auto is None or getattr(self.auto, "selected_agent", None) != "cursor"
'''),
(136, 136, r'''        # Revocation is a permanent coverage boundary for this run.
        if self.auto is None and any(g.get("code") == "CONSENT_REVOKED" for g in self.meter.meta.get("capture_gaps", [])):
            gaps.append({"code": "CONSENT_REVOKED", "message": "授权已撤回；停止后发生的消耗不在覆盖范围内。"})
'''),
(137, 137, r'''        self._last_sync = time.monotonic()
'''),
(140, 141, r'''            if time.monotonic() - self._last_sync >= 3:
                self._sync()
'''),
])
edit('adjusted/web-author/metering.py', 'efa7ab5f44e92d7aa9d56772453f64c417d16c644430a7afaed45d362602479b', '1ce0b985fbd2de2298b29fb297fd3080eee2d58feeb0d2b4a01616d5d1ca91c4', [
(23, 24, r'''BOUNDARY = ("统计范围：本轮计量接入至登记交付；网页自动来源只在用户授权后采集，授权前不追补。不含真实游戏测试和后续实战复盘。"
'''),
])
edit('adjusted/web-author/multi_agent_usage.py', 'c725e6f656ed8ec84731e5b50bc7b0957312bb1bd3624a4a529d7978b23c44df', 'a2b661b923882034aed01429edcd3bdbcdacc756a1a6776374b6c531db8b2c49', [
(127, 128, r'''def detect_agents(home=None, environ=None, selected_agent=None):
'''),
(136, 136, r'''        if selected_agent is not None and row["id"] not in ({selected_agent} if isinstance(selected_agent, str) else set(selected_agent)):
            continue
'''),
(833, 834, r'''        if self.selected_agent == "auto" and not any(self.state.get("bindings", {}).values()):
            # Agent identity comes from the running host, never from unrelated installed apps.
            self.state["status"] = "NO_BOUND_SESSIONS"
            self._save()
            return self.status()
        detected = detect_agents(self.home, self.environ,
            list(self.state.get("bindings", {})) if self.selected_agent == "auto" else self.selected_agent)
'''),
(840, 841, r'''            selected = next((row for row in detected if row["id"] == self.selected_agent), {"roots": []})
'''),
(943, 944, r'''            code, message, action = "WAITING_FOR_HOST", "已授权，等待当前 Agent 确认用量来源；无需选择会话。", "wait_for_usage"
'''),
(975, 976, r'''                    "action_label": {"wait_for_usage": "Agent 正在接入或等待真实 usage", "select_agent": "选择创作使用的 Agent",
'''),
])
edit('adjusted/web-author/server.py', '3e043b4391267a904aa734e302330b968dc536e242fb91bfda8483cf07231dbd', '2af159b693c6aa9dfe58180a6872db7d8c05c878a4ac35d7c1149bee367499bc', [
(90, 91, r'''                                       "host_required": True, "ui_version": "studio-consent-v3"})
'''),
(171, 172, r'''                    if action not in {"connect", "source", "events", "seal", "phase", "complete", "bind", "ccusage", "cursor-admin"}:
'''),
])
edit('adjusted/web-author/web_session.py', '1e4b174a68be7ce0af8df0dd57d56e9b16776c2f29c34ffd6b9368e3ea97d58f', '97afc3c83143871ab2dbfe1d97225ef7ad28615b5d4aea4a90a4791cf38117a1', [
(143, 143, r'''        if state.get("usage_task"):
            return {**state, "web_event": "USAGE_CONNECTION_REQUIRED", "url": meta["url"]}
'''),
(251, 251, r'''            sub.add_argument("--agent", help="Actual host ID; records identity, never grants consent")
            sub.add_argument("--session-id", help="Proven current host session ID; never a guessed recent session")
'''),
(265, 266, r'''            sub.add_argument("--action", choices=["report", "connect", "source", "events", "seal", "complete", "bind", "ccusage", "cursor-admin"], default="report")
'''),
(270, 270, r'''        if args.command in {"launch", "serve"}:
            from agent_catalog import normalize_agent
            if args.agent:
                os.environ["AOE2_AUTHOR_AGENT"] = normalize_agent(args.agent)
            if args.session_id:
                import re
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", args.session_id):
                    raise SessionError("Invalid host session ID")
                if not args.agent or normalize_agent(args.agent) == "auto":
                    raise SessionError("--session-id requires the actual --agent")
                os.environ["AOE2_AUTHOR_SESSION_ID"] = args.session_id
'''),
])
