# 真实 token 与时间计量

## 当前入口：用户授权，Agent 接入

本节优先于下方历史接入示例。用户在第一步点击“授权并继续”时即创建账本和采集线程，配置耗时从此开始；点击“开始生成”只冻结任务和切换阶段，不另建 run。默认使用当前 Agent，不要求用户绑定会话。授权前的聊天消耗不追补。

`next.usage_task` / `wait.web_event=USAGE_CONNECTION_REQUIRED` 是主代理的立即接入任务，包含不可复用的 `authorization_id`。认证主代理调用 `usage --action connect --payload ...`，提交 `agent`、`status=ready`、确切 `session_ids`；没有证据则 `status=unavailable`、空 session 列表和简短 reason。接入回执不是 token 记录：只有真实计数入账后才显示“正在记录”。子代理沿用显式 bind 与既有真实 usage 适配器。不得替用户通过 UI 自行授权。

授权仅限本轮的计量元数据。已选定宿主后只发现该宿主的来源；未知宿主且无精确绑定时等待主 Agent，不扫描全部工具。每 3 秒本地采集一次，与网页轮询独立；Cursor 官方接口采用独立低频刷新，首次具备合法归属后尝试读取，重启仍遵守已保存的刷新间隔。

顶部“停止采集”撤回授权，不再读取新来源、不补一次最终官方查询。保留已有数值和 CONSENT_REVOKED 缺口；connect、bind、source、events、ccusage、cursor-admin 写入均拒绝。旧冻结 request 的授权值不是当前权限，应检查 usage_connection.authorized。重启后继续保持停止；本轮不重新授权，新的授权开新项目。

只有明确配置的账号接口或宿主实际返回的 usage 才能入账。按钮不提供第三方账号权限，不把 Cursor Hook 中的 conversation_id 当作 token，也不将普通 IDE 上下文占用估算成消耗。完整数字、缓存/推理子项、阶段、模型、来源缺口和导出都集中在作品页“完整用量”。


网页第一步先取得本轮计量授权。只有 usage_authorized=true 时才启动自动 usage 采集；选择“本轮不计量”时仍可创作，但 token 保持未采集。授权范围仅是本项目真实 usage、会话 ID、模型、时间等计量元数据，不扩大到聊天正文或凭据。任何来源都不根据字数、上下文窗口占用、账户额度或 credits 估算 token。流程的 RUNNING 表示计时正在进行，不代表已接通计量。JSON、网页和 CSV 均读取同一 SQLite 台账。

## Agent 选择与实际支持范围

网页所选 Agent 会冻结在本轮请求中。选择 Cursor 时不会继承环境中的 Codex 会话；已安装目录不等于正在使用该 Agent，也不等于本轮已计量。

| Agent | 已实现的采集方式 | 必要条件 / 当前边界 |
| --- | --- | --- |
| OpenAI Codex | rollout 的累计 token_count 差值 | 优先继承当前 thread ID；否则唯一的本轮活跃主会话自动绑定；旧会话扣除创作前基线，spawn 子会话按 parent→child 证据自动纳入 |
| Claude Code | 项目 session JSONL 的 assistant usage | 唯一的本轮活跃项目会话自动绑定；无法唯一确认时保留缺口，不要求用户选择 |
| Gemini CLI | chat 文件的消息 tokens | 主 Agent 能证明当前 session 时自动登记；按 total 区分缓存/tool/thoughts；无法证明时保留缺口 |
| Cursor IDE | 项目 Hook 自动归属当前项目 conversation，再用官方 Team Admin Usage Events 按 conversationId 精确关联 | 需 Cursor Hook 生效，并在启动服务前设置 CURSOR_ADMIN_API_KEY；服务自动绑定并低频刷新，用户无需页面操作；官方接口可能有聚合延迟 |
| Cursor SDK | 显式导入最终 RunResult.usage / getUsage() | format=cursor-sdk；只接收本轮 finished/error/cancelled 的真实 usage，不把运行中累计快照相加 |
| OpenCode | SQLite 按 session_id 先筛选，或 storage/message/<session> | 主 Agent 自动登记可证明的 session；支持缓存及 reasoning；不扫全账户消息 |
| GitHub Copilot CLI | 本轮专用本地 OTel 文件的 chat span | 配置 AOE2_COPILOT_USAGE_FILE；主 Agent 自动登记可证明的 conversation ID；忽略 invoke_agent 父汇总 |
| Kimi CLI / Kimi Code | wire.jsonl 的 StatusUpdate.token_usage / turn usage.record | 主 Agent 自动登记可证明的 session；Code 子代理用 session:agent；不统计 context_tokens |
| Cline / Roo Code | task 的 ui_messages.json 请求用量 | 主 Agent 自动登记可证明的 task ID；缺字段保持未知；已删除/折叠汇总不能当完整用量 |
| Windsurf / Trae / Augment | 本轮真实 usage 显式导入 | 尚未核实稳定、按项目归属的 IDE 本地消耗接口；不宣称自动接通 |
| 其他 Agent | agent-usage / 提供商最终响应导入 | 必须有本轮真实来源和稳定事件 ID |

以上是已实现的格式支持及合成测试范围，不是所有 Agent 的本机实测认证。Cursor IDE 的本机 bubble.tokenCount 已不再作为用量来源。仓库改用 Cursor 官方 Hook 的稳定 conversation_id 与 Team Admin Usage Events 的 conversationId 做 join；只有官方事件返回的 input/output/cache token 才进入账本。contextTokensUsed、contextUsagePercent 和 promptTokenBreakdown.estimatedTokens 仍全部排除。无 Admin API 权限时保持未采集，或导入本轮 Cursor SDK RunResult.usage / getUsage()。

## 会话绑定与连接提示

identity 接受 agent、workspace_root、usage_sessions 和 auto_capture。正常用户流程没有“选择会话”步骤：首次 Codex 优先继承 CODEX_THREAD_ID；否则对能提供项目会话元数据的宿主，后台只在恰好一个非子会话在本轮开始后发生实际活动时自动绑定，即使该会话早于项目创建。主代理若从宿主运行时拿到精确 session ID，也可自行登记。多个候选同时活跃或归属证据不足时保持缺口，不让用户选择，也不按“最近会话”猜测。来源根目录仅作文件名/元数据定位。OpenCode 在 SQL WHERE 中先限制 session_id。Cursor 只用 composer/Hook 元数据识别 conversation，不再从 cursorDiskKV 读取 token。

会话候选只由项目/工作区元数据产生，不返回会话标题、正文或凭据。后台把 created_at 与 updated_at 分开看：会话可以早于项目创建，只要它是唯一一个在本轮开始后继续活动的主候选，就可以自动绑定。多个候选同时活跃、没有活动时间或缺少项目归属证据时不猜选，直接保留计量缺口。Codex 若存在 thread_spawn_edges，则已绑定父 thread 在本轮明确 spawn 的后代 thread 会递归自动纳入；没有 parent→child 证据的同工作区会话不会因此加入。

报告中的 `auto_capture.connection` 提供 code、message、中文 action_label 和 requirements；`session_candidates` 只提供 session_id、时间和归属说明。常见状态：

- AUTO_SESSION_DISCOVERY：后台正在确认唯一的本轮活跃会话；用户无需选择。
- AUTO_SESSION_AMBIGUOUS：同时存在多个活跃候选，后台不猜选；计量保持缺口，但创作继续。
- WAITING_FOR_USAGE：会话已自动确认或由主代理登记，等待真实日志字段。
- BASELINE_CAPTURED：旧会话首份累计快照仅建立基线，尚未取得本轮增量。
- CURSOR_ADMIN_READY：已由项目 Hook 自动绑定 Cursor conversation，且进程中存在 CURSOR_ADMIN_API_KEY；后台会低频刷新官方 Usage Events。
- EXPLICIT_USAGE_REQUIRED（Cursor）：没有可用的 Cursor Team Admin API key；普通 IDE 不回退读取本机气泡，可改用 Cursor SDK 真实 usage。
- EXPLICIT_USAGE_REQUIRED：当前 Agent 尚无经核实的本地解析方式，需显式导入。
- RECORDED_PARTIAL：已记录绑定来源的小计，未绑定子代理仍不在覆盖内。

`usage --action bind` 仅保留给主代理/宿主内部：主代理已经拿到可验证的精确 session ID（例如自己创建的子代理）时可直接登记。它不是用户步骤，网页不提供会话选择器；无法证明归属时宁可缺失，不要求用户判断。

Agent 选择不会切换或启动宿主，更不会自行发起模型调用。测试关闭自动采集可用 AOE2_USAGE_DISABLE_AUTO=1，此时明确显示 DISABLED。

## Cursor Hook + 官方 Usage Events

仓库自带项目级 `.cursor/hooks.json`。Hook 只白名单记录 conversation_id、时间、模型、Cursor 版本、workspace 和“是否取得用户邮箱”，不会保存用户 prompt、Agent 回复、thinking、transcript 内容或 API key。Hook 数据写入被 gitignore 排除的 `adjusted/.local/cursor-hook-events.sqlite3`。

如果 Cursor 账户/团队能创建可调用 Team Admin API 的 key，在**启动网页服务前**仅放入当前进程环境：

```powershell
$env:CURSOR_ADMIN_API_KEY="<你的 Cursor Team Admin API key>"
```

不要把 key 写入仓库、网页字段、报告或项目 JSON。开始创作后，项目 Hook 会把当前 Cursor conversation 与唯一活动 project_id 关联；服务只在归属证据唯一时自动绑定。正常使用不需要在页面选会话或点击刷新。开发排查时仍可显式执行：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <项目名称> --action cursor-admin
```

后台低频刷新只请求 `POST /teams/filtered-usage-events`，并在 complete / finish 前补一次最终刷新。它用 Hook 的当前用户邮箱缩小时间范围，再在本机内存中按已绑定 `conversationId` 精确过滤；其他 conversation/team event 不写入项目。官方事件的 `inputTokens + cacheReadTokens + cacheWriteTokens` 作为规范化输入，`outputTokens` 作为输出，reasoning 未单独暴露时保持 null。接口文档说明数据按小时聚合，因此刚结束的调用可能暂时查不到；这种情况显示 WAITING_FOR_USAGE，不补零也不估算。

Cursor 当前仍有一个已确认的 Hook 限制：本地子代理 conversation 不能可靠回链 parent conversation。主会话可以按 conversationId 精确统计，但无法证明归属的 Cursor 子代理不会自动并入，报告继续保持 PARTIAL。这个缺口不能用“同工作区、时间接近”猜测。

## ccusage 的受控复用

本适配器复用 [ccusage 官方 Session JSON](https://github.com/ccusage/ccusage/blob/main/docs/guide/session-reports.md) 的计数字段，核查版本为 [v20.0.24](https://github.com/ccusage/ccusage/releases/tag/v20.0.24)。网页服务不执行、安装或下载 ccusage，不执行全账号 session 扫描。已有工具由宿主自行对本轮来源导出；传入本地服务的只允许一个明确 session 的 JSON，不包含提示词和回答。

支持已核实的 ccusage 来源：codex、claude、gemini、opencode、copilot、kimi。先绑定 session，再把以下内容保存到本轮 tmp/ 并使用 --action ccusage：

```json
{
  "agent":"kimi",
  "session_id":"actual-session-id",
  "report":{"sessions":[{
    "sessionId":"actual-session-id",
    "inputTokens":100,"outputTokens":20,
    "cacheReadTokens":0,"cacheCreationTokens":0,"totalTokens":120,
    "firstActivity":"本会话真实ISO时间","lastActivity":"本次快照真实ISO时间",
    "modelsUsed":["实际模型标识"]
  }]}
}
```

```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <项目名称> --action ccusage --payload <本轮快照JSON>
```

示例数字不是实际用量。账户 totals、日期报表、多会话报表、不匹配 session/agent、无本轮时间一律拒绝。若会话在本轮开始前已存在，首份快照只建立基线，之后仅计差值，同时永久保留 NO_PROJECT_START_BASELINE 缺口。已用本机解析器采集的同一会话拒绝再导入 ccusage，避免重复。重复快照不重复累计，计数回退保留 CUMULATIVE_RESET 缺口。

## 通用真实 usage 导入

宿主可导入明确属于本轮的现有 JSONL，不重新调用模型补计量：

```powershell
python -X utf8 -B adjusted/web-author/usage.py import --project <本轮项目绝对路径> --file <本轮JSONL> --source-id <稳定来源ID> --format agent-usage --seal
```

agent-usage 每行只允许稳定 ID、实际模型、阶段、结果、耗时和计数：

```json
{"event_id":"actual-call-id","phase":"3","model":"actual-model","outcome":"unknown","usage":{"input_tokens":100,"output_tokens":20,"total_tokens":120,"cached_input_tokens":null,"cache_write_tokens":null,"reasoning_output_tokens":null}}
```

input_tokens 包含缓存读写，output_tokens 包含推理；细项是子集，缺失用 null。真实零值和缺失值必须区分。当前还支持 openai-responses、openai-chat、anthropic-messages、codex-exec、cursor-sdk。Cursor SDK 从现有调用的最终 RunResult 导入，只传 id/status/model/usage；其 totalTokens=inputTokens+outputTokens+cacheReadTokens+cacheWriteTokens，reasoningTokens 是 outputTokens 子项。不能把相同调用同时通过自动采集和另一手动 source 重复上报，宿主必须保证来源不重叠。

## 覆盖、时间与完成

- NOT_CONNECTED：尚无来源真实计数，总 token 为 null。
- PARTIAL：只有已记录小计；来源未封账、采集缺口、未知调用或未声明全覆盖时都保持部分状态。
- HOST_REPORTED_COMPLETE：来源封账、记录可用且宿主明确声明全部覆盖；仍不是提供商账单审计。

失败、重试、耗时仅按实际事件报告，不从记录数量猜测。总历时、工作流程时间、人工等待和未观察时间分开；并行调用耗时不能相加冒充墙钟时间。无法可靠归属阶段的采集留在 unattributed。

阶段命令使用 researching / authoring / checking / repairing / packaging。自动采集到的新 usage 事件在首次观察时固定到当时的工作流阶段；同一事件后续重复扫描不会改阶段。无法可靠归属的旧记录仍保留未分阶段，不做事后猜测。build 只登记实际交付，等作者与检查调用结束并收集 usage 后再 complete；默认不声明全覆盖。只有来源真实封账且无采集缺口才可 all_sources_declared=true。不要为了通过而删除缺口或把未知改为 0。

台账固定在本轮项目 authoring/metrics/usage.sqlite3，自动采集元数据在同目录 multi-agent-auto.json。结束时保留 report-<指纹>/summary.json、stages.csv、calls.csv；CSV 使用 UTF-8 BOM，空单元表示未知。计量不推进参数创作、不更改答案和 PER、不影响游戏验证状态。

## 核查来源

- [Cursor Hooks](https://cursor.com/docs/hooks)：conversation_id 是跨多轮稳定 ID；项目 Hook 可用于 analytics。
- [Cursor Team Admin API](https://cursor.com/docs/account/teams/admin-api)：/teams/filtered-usage-events 返回 conversationId、模型、input/output/cache token 和费用；使用 API key Basic Auth。
- [Cursor SDK Token usage](https://cursor.com/docs/sdk/typescript)：最终 RunResult、getUsage()、缓存与推理语义。
- Cursor 官方社区已确认桌面端 cursorDiskKV 的 tokenCount 是 best-effort、当前不可靠；同时 Cursor 也已确认本地子代理 Hook 目前缺少可靠 parent conversation 回链。
- [Gemini 官方 ChatRecordingService](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingService.ts)：消息 tokens 的实际字段。
- [Kimi 官方 Wire 类型](https://github.com/MoonshotAI/kimi-cli/blob/main/src/kimi_cli/wire/types.py) 和 [ccusage Kimi](https://github.com/ccusage/ccusage/blob/main/docs/guide/kimi/index.md)：step usage 与 context/session 字段区别。
- [Copilot CLI 官方 OTel 参考](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)：chat 与 invoke_agent 层级、真实 token、默认关闭消息内容捕获。
- [Cline 官方指标实现](https://github.com/cline/cline/blob/main/src/shared/getApiMetrics.ts) 和 [Roo 官方消息类型](https://github.com/RooCodeInc/Roo-Code/blob/main/packages/types/src/message.ts)：请求计数与上下文占用的区别。
- [ccusage 官方来源说明](https://github.com/ccusage/ccusage/blob/main/docs/guide/getting-started.md)：支持来源与数据目录。Windsurf/Trae/Augment 不因出现在选择列表中就视为已自动采集。
