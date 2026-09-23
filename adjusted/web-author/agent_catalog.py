"""Host choices and evidence-backed metering capabilities (not installation detection)."""
from copy import deepcopy

_ROWS = [
    ("auto", "当前 Agent（自动确认）", "explicit_binding", "由正在执行本轮任务的 Agent 确认来源，不扫描其他已安装工具。", "先选择实际 Agent；会话由后台自动识别，无法唯一确认时保留缺口。"),
    ("codex", "OpenAI Codex", "local_session", "本机 rollout 的累计 token_count；自动识别当前工作区主会话并扣除创作前基线。", "优先使用 CODEX_THREAD_ID；否则唯一的本轮活跃主会话自动绑定，spawn 子会话按 parent→child 证据纳入。"),
    ("claude", "Claude Code", "local_session", "项目会话 JSONL 的真实 assistant usage。", "唯一的本轮活跃项目会话自动绑定；无法唯一确认时保留缺口，不要求用户选择。"),
    ("gemini", "Gemini CLI", "local_session", "chat 文件的消息 tokens；区分缓存与推理。", "主 Agent 能证明当前 session 时自动登记；无法证明时保留缺口。"),
    ("cursor", "Cursor", "explicit_import", "项目 Hook 自动归属当前 conversation；有 Team Admin API 时后台低频同步官方 Usage Events，无权限时可导入 Cursor SDK 最终 usage。", "如有 Team Admin API key，在启动网页服务前设置 CURSOR_ADMIN_API_KEY；之后由服务自动绑定和刷新，无需页面操作。没有该权限时保持未采集或导入本轮 Cursor SDK usage。"),
    ("opencode", "OpenCode", "local_session", "按项目 session_id 读取 SQLite/JSON 的 assistant tokens。", "主 Agent 能证明当前 session 时自动登记；只读取该 session 的用量字段。"),
    ("copilot", "GitHub Copilot CLI", "local_telemetry", "本轮专用 OTel 文件的 chat span 真实 token；不重复累加父 span。", "启动前开启本地文件 OTel，指定 AOE2_COPILOT_USAGE_FILE，再绑定 conversation ID。"),
    ("kimi", "Kimi Code / Kimi CLI", "local_session", "会话 wire.jsonl 中 StatusUpdate.token_usage 或 turn usage.record。", "主 Agent 自动登记可证明的 session；Code 子代理用 session:agent ID 单独登记。"),
    ("cline", "Cline", "local_session", "task 的 ui_messages.json 中完成请求用量；缺字段保持未知。", "主 Agent 自动登记可证明的 task ID；缺字段保持未知。"),
    ("roo", "Roo Code", "local_session", "task 的 ui_messages.json 中完成请求用量；子任务分别登记。", "主 Agent 自动登记可证明的 task ID；缺少真实字段时保留缺口。"),
    ("windsurf", "Windsurf", "explicit_import", "尚未核实可按本项目会话读取的公开本机 token 字段。", "导入本轮真实 usage；账户额度和 credits 不能换算为 token。"),
    ("trae", "Trae", "explicit_import", "尚未核实可按本项目会话读取的公开本机 token 字段。", "导入本轮真实 usage；不读取登录凭据，不按字数估算。"),
    ("augment", "Augment", "explicit_import", "尚未核实本机 IDE 会话的稳定消耗接口。", "导入本轮真实 usage；账户或团队汇总不能算作本项目。"),
    ("other", "其他 Agent（真实 usage 导入）", "explicit_import", "接受本轮 provider 最终响应或统一 agent-usage 事件。", "必须有稳定事件 ID、真实计数和明确本轮来源。"),
]
_ALIASES = {"claude-code": "claude", "gemini-cli": "gemini", "github-copilot": "copilot",
            "copilot-cli": "copilot", "kimi-code": "kimi", "roo-code": "roo", "roocode": "roo"}

def normalize_agent(value="auto"):
    if not isinstance(value, str):
        raise ValueError("Agent 必须从列表中选择。")
    value = _ALIASES.get(value.strip().lower(), value.strip().lower())
    if value not in {row[0] for row in _ROWS}:
        raise ValueError("未知 Agent，请从网页列表中选择。")
    return value

def agent_catalog():
    return [{"id": a, "label": label, "metering_mode": mode, "status": mode,
             "help": help_text, "requirements": requirements,
             "automatic": mode in {"local_session", "local_telemetry"},
             "explicit_import": True} for a, label, mode, help_text, requirements in _ROWS]

def agent_info(agent):
    agent = normalize_agent(agent)
    return next(row for row in agent_catalog() if row["id"] == agent)
