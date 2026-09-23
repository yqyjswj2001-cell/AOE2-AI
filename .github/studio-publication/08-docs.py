# Reviewed line edits. Applied only to exact baseline files.
edit('SKILL.md', '9501b29378d3d1dd89e230b0158b27190760613bd2ca94d2d065c5517775f1da', 'f576e41b6869dbb37f834bc06953fe3792f02bf9164e5d88e87d18413c1cbbf3', [
(11, 12, r'''用户要求实际使用、打开网页或创作时，按详细流程启动服务并保持宿主执行；仅下载、同步、安装或评估时不自动创作。网页设置默认由用户完成：第一步默认由当前 Agent 确认宿主，用户点击“授权并继续”或“本轮不计量”；授权立即开启本轮采集，之后再完成游戏设置。主代理只启动网页服务、提供或打开实际 URL，并通过 `wait / next` 等待用户点击“开始生成”。等待期间若返回 `usage_task`，先完成计量接入回执，再继续等用户；计量授权不等于开始创作。不得因为流程出现“网页、选择、点击”等描述就自行调用 Computer Use、浏览器自动化或视觉点击工具；只有用户明确要求代理代为操作网页时才允许。按需将此完整仓库放入宿主支持的技能目录，或让宿主直接读取本入口，不假称已经自动安装。
'''),
])
edit('adjusted/skills/aoe2-web-author/SKILL.md', '6974b8e7738385db34c143bd86a0deb3df342decfcb3347d040206c1078ae35f', '5d1ccf9b185ae8bbed8a9180aa9f97165e1b2ba28f0d761c919909486ec1de34', [
(25, 26, r'''网页由用户依次完成授权 → 对局 → 文明 → 打法，设置页直接点击“开始生成”进入作品页，不再增加确认页。第一步默认“当前 Agent（自动确认）”，用户点击“授权并继续”或“本轮不计量”。允许只授权本项目读取真实 usage、会话 ID、模型、时间等计量元数据，不授权搜集、上传聊天正文或账号凭据（适配器仅从本机记录提取计量字段）；外部厂商账户权限仍以本机已有连接为准。文明页完整展示42个标准版盾徽，悬停或键盘焦点只预览右侧资料，点击即固定选择，无额外文明确认；也可选择让 AI 决定。设置只保留脚本名和四时代攻防偏好。Agent 选择不会自动启动或切换另一工具。开始后自主模式先选文明，手动模式直接填参数。滑块是用户偏好，不是某个官方参数的数值。没有简报、方案发布、permit 或二次审批。未点击前继续短周期 wait；超时不是授权，也不是任务结束。网页不能唤醒已退出的宿主代理，执行期间保持本会话工作。用户明确暂停或取消时尊重指令并结束会话。

## 授权后立即接入，不等开始生成

已知当前宿主时，在 `launch` 增加 `--agent codex`（或实际支持的 Agent ID）；掌握确切当前会话 ID 时可再传 `--session-id <真实ID>`。只传能够证明的身份，不凭目录名、时间接近或历史会话猜测。启动参数不是用户授权，点击前不得读取自动计量来源；网页选择也不会启动另一种工具。

用户授权后服务立即创建账本、记录配置阶段并启动独立采集循环。`wait` 会提前返回 `web_event=USAGE_CONNECTION_REQUIRED`，`next.usage_task` 给出本轮 `authorization_id` 和 `run_id`。**先处理此任务，再继续等待游戏设置；不要因为 status 仍是 configuring 就忽略计量，也不要因此提前创作。**

主代理将自己掌握的当前宿主/会话身份写入本项目 `tmp/usage-connect.json`：
```json
{"authorization_id":"<usage_task 中原样取得>","agent":"codex","status":"ready","session_ids":["<可证明属于本轮的真实主会话ID>"]}
```
```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action connect --payload <本项目tmp/usage-connect.json>
```
无法证明归属或当前宿主没有可用来源时，同样登记回执：`status=unavailable`、`session_ids=[]`，附简短且不含凭据的 `reason`。`agent` 使用实际宿主；无法识别时保留 `auto`。这只标记缺口，不伪装成功，也不阻塞后续创作。没有用户手动选择会话的步骤。后续取得确切身份可用当前授权再次 connect；子代理创建后立即按既有 `usage bind` 登记可证明的归属，不等结束才补记。

配置阶段与生成阶段使用同一个 run，不重置累计值。后台采集不依赖网页刷新；用户可通过顶部“停止采集”撤回，停止后拒绝新增绑定、导入和官方刷新，保留已记录小计。本轮撤回后不重新开启；下一次需要计量时新建项目。每次接入前检查最新授权，不使用过期回执。
'''),
(88, 89, r'''先查看 next.usage_task、next.usage_connection 和最新授权回执（以 usage_connection.authorized 为准，撤回后不能沿用冻结 request 的旧值）。**不要让用户选择或绑定用量会话。** 用户在第一步授权后，后台自动识别唯一的本轮活跃主会话；主代理如果掌握当前宿主或子代理的精确 session ID，可自行通过 usage bind 登记，不在聊天里询问用户。存在多个无法证明归属的候选时保持计量缺口并继续创作，不按“最近会话”猜测，也不把检测到安装目录当作已采集。用户选择“本轮不计量”时不得读取自动 usage 来源。可使用 GitHub ccusage 的受控、按会话导出的 JSON 快照，通过 usage --action ccusage 导入；只能用真实记录，不能自己编造快照。Cursor IDE 优先走仓库项目 Hook + Cursor Team Admin Usage Events：Hook 只记录 conversation_id 等元数据；如有 Team Admin API key，在启动网页服务前通过环境变量 CURSOR_ADMIN_API_KEY 提供，绝不能写进仓库或网页。服务会用唯一活动 project_id 自动归属并绑定当前 Cursor conversation，后台低频刷新官方 token，complete / finish 前再补一次最终刷新；用户不需要在网页选会话或点刷新。官方接口可能有聚合延迟；普通 IDE 不回退读取 bubble.tokenCount，也不按上下文占用/estimatedTokens 估算。没有 Admin API 权限时可导入 Cursor SDK 的真实 RunResult.usage / getUsage()，否则保持明确缺口。Cursor 子代理目前无法由官方 Hook 可靠回链 parent conversation，不能凭时间或同工作区猜归属。用户选择 Agent 不构成自动计量成功。
'''),
(98, 99, r'''单纯关闭浏览器或结束会话不代表交付或用量完整。作品页的“开发报告”标签可一键生成两个 Markdown：`creation-report.md` 是页面可直接查看/复制的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、阶段与调用用量、构建详情、事件时间线和日志摘要。不要生成 ZIP。finish 时还会自动保留最终两份报告。报告不能把未执行的游戏验证写成通过。最终聊天只需简短报告参数交付、实际用量覆盖和未验证部分。
'''),
])
edit('adjusted/web-author/METERING.md', 'a7682a98d9f770abc529398c37ae6a4b8fab2992a0e2b5a309a470831257dfda', '9a84f5aec4ed5fd3b9819f726babccb63b90e23cbf04b6eb62be27f5ea00c86a', [
(1, 1, r'''
## 当前入口：用户授权，Agent 接入

本节优先于下方历史接入示例。用户在第一步点击“授权并继续”时即创建账本和采集线程，配置耗时从此开始；点击“开始生成”只冻结任务和切换阶段，不另建 run。默认使用当前 Agent，不要求用户绑定会话。授权前的聊天消耗不追补。

`next.usage_task` / `wait.web_event=USAGE_CONNECTION_REQUIRED` 是主代理的立即接入任务，包含不可复用的 `authorization_id`。认证主代理调用 `usage --action connect --payload ...`，提交 `agent`、`status=ready`、确切 `session_ids`；没有证据则 `status=unavailable`、空 session 列表和简短 reason。接入回执不是 token 记录：只有真实计数入账后才显示“正在记录”。子代理沿用显式 bind 与既有真实 usage 适配器。不得替用户通过 UI 自行授权。

授权仅限本轮的计量元数据。已选定宿主后只发现该宿主的来源；未知宿主且无精确绑定时等待主 Agent，不扫描全部工具。每 3 秒本地采集一次，与网页轮询独立；Cursor 官方接口采用独立低频刷新，首次具备合法归属后尝试读取，重启仍遵守已保存的刷新间隔。

顶部“停止采集”撤回授权，不再读取新来源、不补一次最终官方查询。保留已有数值和 CONSENT_REVOKED 缺口；connect、bind、source、events、ccusage、cursor-admin 写入均拒绝。旧冻结 request 的授权值不是当前权限，应检查 usage_connection.authorized。重启后继续保持停止；本轮不重新授权，新的授权开新项目。

只有明确配置的账号接口或宿主实际返回的 usage 才能入账。按钮不提供第三方账号权限，不把 Cursor Hook 中的 conversation_id 当作 token，也不将普通 IDE 上下文占用估算成消耗。完整数字、缓存/推理子项、阶段、模型、来源缺口和导出都集中在作品页“完整用量”。

'''),
])
edit('adjusted/web-author/README.md', 'fae5ed121e366083cde0e8ece5ccad87765accde1a2c7009cd6b31fe9073e7c1', 'a8f535ecaf6edb7dfc5451daab9b2d382f040730399d447a73d7bbdc3e103654', [
(2, 3, r'''由 AOE2-AI-STUDIO 迁入的本地创作工具。本版流程：授权 → 对局 → 文明 → 打法 → 作品。每步只显示对应内容，打法页直接开始；作品页分为生成进度、完整用量、开发报告三个平级视图。
'''),
(15, 16, r'''启动会输出实际 URL 并尝试打开默认浏览器；这只负责打开页面，不代表代理应控制浏览器。网页设置默认由用户完成，主代理通过 `wait / next` 等待提交；除非用户明确要求代理代操作，否则不要调用 Computer Use、浏览器自动化或视觉点击工具。网页按五步前进：用量授权、选模式、选文明盾徽、设置、开始创作。悬停/键盘焦点预览资料，点击立即固定文明；也能让 AI 选择。授权页默认由当前 Agent 确认身份；设置页只设脚本名和时代偏好。当前按标准版无额外 DLC 开放 42 文明；特殊机制作为打法素材，优先减少重复选择。[选择标准与官方版本依据](CIVILIZATION_SELECTION.md)。等待/验证/渲染/结束命令见 skill；`--help` 提供实际参数。Python 标准库即可运行服务。
'''),
(35, 36, r'''作品页“开发报告”标签提供“生成创作报告”，先预览，用户主动点击才下载。每次只生成两个 Markdown：`creation-report.md` 是可直接复制给开发的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、usage 调用、构建详情、事件时间线和日志摘要。没有 ZIP。原始计量数据库和项目事件文件仍留在项目目录供程序复查；finish 时自动保存最终两份报告。作者或主代理可用 `web_session.py feedback` 随时登记 issue / suggestion / note，避免修复后的问题从最终状态里消失。
'''),
(41, 42, r'''第一步点击“授权并继续”后即创建同一个持久账本并开始配置阶段计量，不等“开始生成”。Agent 身份默认自动确认，也能选择实际宿主；网页不会启动或切换工具。`wait / next` 会优先交回 `usage_task`，主 Agent 通过认证的 `usage --action connect --payload ...` 提交真实会话身份或明确缺口，不让用户选 session。详细命令见 [Skill](../skills/aoe2-web-author/SKILL.md)。

后台每 3 秒读取选定宿主的本轮来源，不依赖浏览器轮询。未知宿主没有精确绑定时不扫描其他 Agent 的数据目录。配置与生成共用 run；刷新、重复授权和恢复项目不会重置计数。顶部只显示“待授权 / 接入中 / 已接入待记录 / 正在记录 / 存在缺口 / 已停止”等状态，不反复堆叠数字。

“本轮不计量”不读取自动来源；“停止采集”撤回本轮授权，保留已有账本并阻止后续新增采集。未采集不是零，缓存和推理属于明细，不重复加到总量，子代理未覆盖仍显示 PARTIAL。授权前消耗不补算；真实接口未开放或归属不明时保持缺口，不按上下文长度估算。
'''),
(46, 46, r'''

## 维护验证

```sh
python -B -m unittest discover -s adjusted/tests -v
python -B -m unittest discover -s adjusted/tests/web_author -v
python -B adjusted/tools/check_official_cloze.py
node --check adjusted/web-author/web/app.js
# 仅浏览器回归测试需要开发依赖；本地服务仍只用 Python 标准库。
python -m pip install playwright
python -m playwright install chromium
python adjusted/tests/web_author/test_wizard_browser.py
```

浏览器用合成项目拦截请求，不读取账号或真实作品；测试图中的示例 token 不是实测。`AOE2_BROWSER_EXECUTABLE` 可指定现有浏览器，`AOE2_UI_TEST_OUTPUT` 可指定测试输出目录。CI 同时覆盖网页子目录，避免只运行上层 unittest 而漏掉网页与计量回归。
'''),
])
