---
name: aoe2-web-author
description: 在 AOE2-AI 中启动本地网页，先等待用户选择实际 Agent 并授权本轮自动计量，再完成模式、文明和打法偏好；随后由新上下文作者填写动态参数并由主代理校验、机械渲染。用于“打开网页创作 AI”“使用网页创作 skill”等请求。
---

# 网页参数创作

仓库根目录从 SKILL.md 所在目录向上三级取得。主入口：`adjusted/web-author/web_session.py`。
服务、用量说明：[../../web-author/README.md](../../web-author/README.md)、[../../web-author/METERING.md](../../web-author/METERING.md)。

## 开始与等待

仅在用户要求实际创作时启动；迁移、安装 skill 或只读评估不是开始创作。正常创作只使用当前 main 的文件和流程，不扫描或接续历史 PR、Draft PR、feature/codex 分支；只有用户明确要求仓库维护或历史回溯时才查看它们。

在仓库根执行：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project <本轮唯一名称>
python -X utf8 -B adjusted/web-author/web_session.py watch --project <名称> --until start --timeout 600
python -X utf8 -B adjusted/web-author/web_session.py next --project <名称> --compact
```

**硬规则：`launch`、授权、网页配置、参数创作、校验和脚本生成均不要求安装游戏。不要在启动前寻找 AoE2DE、`PromiDE.per2`、Steam 目录或安装模板，也不得因这些文件不存在而拒绝创作。**

使用启动结果的实际本机 URL，不猜端口。项目自动进入 `adjusted/.local/author-projects/<名称>/`，不复用历史作品。浏览器打开失败时提供真实 URL；不得报告已打开。这里只允许“打开页面”，不代表授权代理控制浏览器。

**网页设置默认由用户操作。** 主代理负责网页服务，不负责网页交互：执行 `launch` 后等待用户自己选择模式、文明、Agent、脚本名和时代偏好，并点击“开始生成”；主代理通过 `watch` 得知提交结果后再继续。不得因为任务包含“网页、选择、点击开始”等描述就自行调用 Computer Use、浏览器自动化、屏幕控制或视觉点击工具，也不得替用户填写或提交设置。**只有用户明确要求代理代为操作网页时，才可以使用这类工具。**

网页由用户依次完成授权 → 对局 → 文明 → 打法，设置页直接点击“开始生成”进入作品页，不再增加确认页。第一步默认“当前 Agent（自动确认）”，用户点击“授权并继续”或“本轮不计量”。允许只授权本项目读取真实 usage、会话 ID、模型、时间等计量元数据，不授权搜集、上传聊天正文或账号凭据（适配器仅从本机记录提取计量字段）；外部厂商账户权限仍以本机已有连接为准。文明页完整展示42个标准版盾徽，悬停或键盘焦点只预览右侧资料，点击即固定选择，无额外文明确认；也可选择让 AI 决定。设置只保留脚本名和四时代攻防偏好。Agent 选择不会自动启动或切换另一工具。开始后自主模式先选文明，手动模式直接填参数。滑块是用户偏好，不是某个官方参数的数值。没有简报、方案发布、permit 或二次审批。未点击前由同一个 watch 进程等待；超时不是授权，也不是任务结束。网页不能唤醒已退出的宿主代理，执行期间保持本会话工作。用户明确暂停或取消时尊重指令并结束会话。

## 授权后立即接入，不等开始生成

已知当前宿主时，在 `launch` 增加 `--agent codex`（或实际支持的 Agent ID）；掌握确切当前会话 ID 时可再传 `--session-id <真实ID>`。只传能够证明的身份，不凭目录名、时间接近或历史会话猜测。启动参数不是用户授权，点击前不得读取自动计量来源；网页选择也不会启动另一种工具。

用户授权后服务立即创建账本、记录配置阶段并启动独立采集循环。`watch`（兼容旧 `wait`）会提前返回 `web_event=USAGE_CONNECTION_REQUIRED`，`next.usage_task` 给出本轮 `authorization_id` 和 `run_id`。**先处理此任务，再继续等待游戏设置；不要因为 status 仍是 configuring 就忽略计量，也不要因此提前创作。**

主代理将自己掌握的当前宿主/会话身份写入本项目 `tmp/usage-connect.json`：
```json
{"authorization_id":"<usage_task 中原样取得>","agent":"codex","status":"ready","session_ids":["<可证明属于本轮的真实主会话ID>"]}
```
```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action connect --payload <本项目tmp/usage-connect.json>
```
无法证明归属或当前宿主没有可用来源时，同样登记回执：`status=unavailable`、`session_ids=[]`，附简短且不含凭据的 `reason`。`agent` 使用实际宿主；无法识别时保留 `auto`。这只标记缺口，不伪装成功，也不阻塞后续创作。没有用户手动选择会话的步骤。后续取得确切身份可用当前授权再次 connect；子代理创建后立即按既有 `usage bind` 登记可证明的归属，不等结束才补记。

配置阶段与生成阶段使用同一个 run，不重置累计值。后台采集不依赖网页刷新；用户可通过顶部“停止采集”撤回，停止后拒绝新增绑定、导入和官方刷新，保留已记录小计。本轮撤回后不重新开启；下一次需要计量时新建项目。每次接入前检查最新授权，不使用过期回执。

## 自主选文明

按 [文明选择规则](../../web-author/CIVILIZATION_SELECTION.md) 执行。资格由 next 返回的标准版允许池决定：42 个文明，包含官方免费并入的前三个资料片，未购买额外 DLC。事实库有 53 个文明不代表都可选。

收到 choose_civilization 动作后，先执行 `web_session.py handoff --project <名称>`。以 fork_turns="none" 创建作者，只交回执中的 task_file 及其中许可路径；自动生成的 task.json 已包含完整本轮条件、42项允许池和推荐候选，不要手抄或漏传。不给固定源码或旧作品。让同一作者先读候选相关事实与卡片，再选文明；固定执行机制不需要作者重写，特殊加成应作为打法素材，不能仅因不熟悉或不好算而回避。

推荐候选来自近期较少选择的文明；先比较其中三种不同打法，给出最终文明和一两句具体战术理由。仍可从全部合资格文明中选择，用户手动指定时不重选。不得伪造文明加成或历史使用频率。

作者先只将选择写入本项目 tmp/civilization-choice.json，保留 next 决策快照的 expected_revision：
```json
{"expected_revision": 2, "civilization": "<允许池中的内部标识>", "reason": "<文明特色如何支撑本轮打法>"}
```
主代理登记：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py choose-civilization --project <名称> --choice <本轮选择JSON>
```
成功前保持全部答案为 null；登记成功后重新执行 handoff 更新 task.json，通过 followup_task 让同一作者读取更新后的任务并继续填写。过期 revision 时重新取得 next 并核对条件，不能把旧决定直接升级为新版本。选择理由是轻量任务元数据，不生成简报、不要求用户批准，也不能代替完整参数创作。

## 作者与主代理分工

主代理负责网页服务的启动/等待、计量、导出输入、检查和渲染；默认不负责点击或填写网页。不要自己看完固定实现后再冒充隔离作者。

手动模式在开始后执行 `web_session.py handoff --project <名称>`，以 `fork_turns="none"` 创建新作者；自主模式复用刚选定文明的同一作者。只交回执中的 task_file；文件自动列出本轮条件、隔离输入、写入工具和提交目录，不转述整份 next，不重复发送固定说明或计量历史。

作者按卡片 group_id / 模块查资料、决定一组、提交一组。只在本项目 `submissions/` 写小段 JSON，然后调用 task.json 指定的项目内 `author-session/submit_answers.py`。不要直接修改 author-input 或维护完整 answers 文件。

```json
{"module":"<模块名，不带路径>","answers":{"<该组参数键>":42}}
```
这里的 42 只是格式示意，不是推荐参数。主代理不得把示意值填入答卷。

```powershell
python -X utf8 -B <task.writer> --patch <本项目submissions内的JSON>
```

程序合并已提交值、保留其余 null、校验已具备条件的关联要求并原子保存。`deferred_constraints` 表示尚有其他成员未填写，不是错误，也不代表最终校验通过。修改已填值时先用 `--status <模块名>` 取得当前 sha256，放进增量的 `expected_sha256`；冲突时核对当前值再改，不覆盖其他已完成组。提交失败不改变原答卷。

作者必须填写 manifest 要求的全部键；不能按文明名称自行让其他分支保持 null，也不能用官方答案、默认值或零补空。保留原有参数卡、事实查询、策略检查和完整最终校验。作者不可读仓库模板、分类审查、官方默认答案、固定 PER、历史作品或其他 AI。

作者完成策略检查后执行 `python -X utf8 -B <task.writer> --complete`，再向主代理报告完成。程序会固定这一版答卷的完成回执；只填满数字不算作者完成。之后修改任何答案都会使旧回执失效，需要检查后重新 complete。

主代理优先使用宿主原生的作者完成通知；否则执行一次下列命令并让同一个进程持续等待：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py watch --project <名称> --until answers --timeout 600
```

程序在内部检查进度，普通增量不会交回模型；仅在计量需要接入、文明需要决定、作者标记完成或出现错误时返回。宿主命令提前返回进程句柄时，等待同一进程，不反复新开 watch、next 或向作者催进度。超时仅返回短状态，不重开作者、不减参数。确认作者完成后才做最终校验与打包。旧 `wait` 的20秒上限仅为兼容，不再作为正常等待方式。

卡片按需查：
```powershell
python -X utf8 -B tools/query_strategy_cards.py --module gatherers --groups
python -X utf8 -I -B adjusted/tools/query_creator_facts.py civilization Portuguese
```
命令在隔离输入包中运行。遇到“能不能填 0、范围是什么、和哪些键联动”时先查 PARAMETER_CONSTRAINTS.json：required_for_delivery 只表示生成完整脚本必须给值，runtime_applicability=not_proven 表示并未证明该分支本局会触发；zero_rule=allowed_by_static_rule 只表示机械校验允许 0，不表示策略上应该填 0，unspecified 则不能自行推断。资料 UNKNOWN 时指出缺口；不要因缺资料读取固定实现。

作者或主代理一旦发现说明缺口、工具异常、无效返工或改进建议，立即登记到本项目开发事件中，不必在用户聊天里展开：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py feedback --project <名称> --source author --kind issue --message "<具体问题>"
python -X utf8 -B adjusted/web-author/web_session.py feedback --project <名称> --source author --kind suggestion --message "<具体建议>"
```

## 检查与交付

阶段按实际动作更新：researching、authoring、checking、repairing、packaging。
```powershell
python -X utf8 -B adjusted/web-author/web_session.py phase --project <名称> --value authoring
python -X utf8 -B adjusted/web-author/web_session.py validate --project <名称>
python -X utf8 -B adjusted/web-author/web_session.py build --project <名称>
```

校验缺项或类型错误时读取项目 tmp/answer-diagnostics.json，把其中具体文件和参数键交给同一作者修正；不要只转述“未填完整”。其他错误只反馈参数键、类型、范围或关联要求，不要反馈官方参考值或固定源码。用现有 renderer 机械代入，不编译另一套策略语言。不能把 null 填零或默默回退默认值。完成时返回真实交付目录、哈希回执和静态结果。

`build` 不需要本机安装 AoE2DE，也不读取或检查 `PromiDE.per2`。参数完整校验通过后，直接把渲染后的 36 个 `.per` 文件输出到本项目 delivery 目录并结束。不要生成 `.ai`、`resources/_common/ai` 安装结构、主入口或安装模板，也不要因为本机没有游戏而阻止 launch、授权、文明选择、参数创作、validate 或 build。

## 用量与结束

先查看 next.usage_task、next.usage_connection 和最新授权回执（以 usage_connection.authorized 为准，撤回后不能沿用冻结 request 的旧值）。**不要让用户选择或绑定用量会话。** 用户在第一步授权后，后台自动识别唯一的本轮活跃主会话；主代理如果掌握当前宿主或子代理的精确 session ID，可自行通过 usage bind 登记，不在聊天里询问用户。存在多个无法证明归属的候选时保持计量缺口并继续创作，不按“最近会话”猜测，也不把检测到安装目录当作已采集。用户选择“本轮不计量”时不得读取自动 usage 来源。可使用 GitHub ccusage 的受控、按会话导出的 JSON 快照，通过 usage --action ccusage 导入；只能用真实记录，不能自己编造快照。Cursor IDE 优先走仓库项目 Hook + Cursor Team Admin Usage Events：Hook 只记录 conversation_id 等元数据；如有 Team Admin API key，在启动网页服务前通过环境变量 CURSOR_ADMIN_API_KEY 提供，绝不能写进仓库或网页。服务会用唯一活动 project_id 自动归属并绑定当前 Cursor conversation，后台低频刷新官方 token，complete / finish 前再补一次最终刷新；用户不需要在网页选会话或点刷新。官方接口可能有聚合延迟；普通 IDE 不回退读取 bubble.tokenCount，也不按上下文占用/estimatedTokens 估算。没有 Admin API 权限时可导入 Cursor SDK 的真实 RunResult.usage / getUsage()，否则保持明确缺口。Cursor 子代理目前无法由官方 Hook 可靠回链 parent conversation，不能凭时间或同工作区猜归属。用户选择 Agent 不构成自动计量成功。

用量来自已绑定本项目的宿主实际 usage 或显式上报。上下文/工作流版本号不是模型 token。没有数据显示未采集；不按字数估算、不补零、不把并行无关任务算进来。子代理必须有可验证的会话或 usage 来源绑定；未能覆盖全部作者/审查调用时保持 PARTIAL。见计量说明登记来源、补报和封账。

完成交付后仅按真实覆盖情况封账；没有证据不声明 all_sources_declared。不可为补计量而重放付费模型调用。实际交付完成后，先补齐已有 usage，再执行下列 complete（默认只声明部分覆盖），最后 finish。需要声明全部来源已采集时，按计量说明封账并提供明确声明；不能默认认为子代理已覆盖。

```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action complete
python -X utf8 -B adjusted/web-author/web_session.py finish --project <名称>
```
单纯关闭浏览器或结束会话不代表交付或用量完整。作品页的“开发报告”标签可一键生成两个 Markdown：`creation-report.md` 是页面可直接查看/复制的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、阶段与调用用量、构建详情、事件时间线和日志摘要。不要生成 ZIP。finish 时还会自动保留最终两份报告。报告不能把未执行的游戏验证写成通过。最终聊天只需简短报告参数交付、实际用量覆盖和未验证部分。
