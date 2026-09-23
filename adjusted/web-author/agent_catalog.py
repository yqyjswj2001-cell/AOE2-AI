"""Host choices and evidence-backed metering capabilities (not installation detection)."""
from copy import deepcopy

_ROWS = [
    ("auto", "由宿主确认", "explicit_binding", "兼容旧项目；不能根据已安装目录猜测正在使用的 Agent。", "宿主绑定本轮真实会话 ID，或明确选择 Agent。"),
    ("codex", "OpenAI Codex", "local_session", "本机 rollout 的累计 token_count；只读绑定会话并扣除创作前基线。", "首次创建计量时继承 CODEX_THREAD_ID；恢复项目和子代理须核对已有绑定。"),
    ("claude", "Claude Code", "local_session", "指定会话 JSONL 的真实 assistant usage。", "绑定 Claude session ID；缓存读写字段必须实际存在。"),
    ("gemini", "Gemini CLI", "local_session", "指定 chat 文件的消息 tokens；区分缓存与推理。", "绑定 session ID 或实际 session 文件名；需要保存本机 chat usage。"),
    ("cursor", "Cursor", "explicit_import", "优先用项目 Hook 的 conversation_id 对接 Cursor 官方 Team Usage Events；无 Admin API 时可导入 Cursor SDK 最终 usage。", "如有 Team Admin API key，在启动网页服务前设置 CURSOR_ADMIN_API_KEY；页面绑定当前 conversation 后可刷新官方 token。没有该权限时保持未采集或导入本轮 Cursor SDK usage。"),
    ("opencode", "OpenCode", "local_session", "按已绑定 session_id 读取 SQLite/JSON 的 assistant tokens。", "绑定 OpenCode session ID；只读取该 session 的用量字段。"),
    ("copilot", "GitHub Copilot CLI", "local_telemetry", "本轮专用 OTel 文件的 chat span 真实 token；不重复累加父 span。", "启动前开启本地文件 OTel，指定 AOE2_COPILOT_USAGE_FILE，再绑定 conversation ID。"),
    ("kimi", "Kimi Code / Kimi CLI", "local_session", "绑定会话 wire.jsonl 中 StatusUpdate.token_usage 或 turn usage.record。", "绑定 Kimi session ID；Code 子代理用 session:agent ID 单独绑定。"),
    ("cline", "Cline", "local_session", "绑定 task 的 ui_messages.json 中完成请求用量；缺字段保持未知。", "绑定 task ID；需要 tokensIn/tokensOut/cacheReads/cacheWrites 的实际记录。"),
    ("roo", "Roo Code", "local_session", "绑定 task 的 ui_messages.json 中完成请求用量；子任务分别绑定。", "绑定 task ID；缺少缓存字段或已压缩删除的区间须补充真实 usage。"),
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
