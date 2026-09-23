---
name: aoe2-web-author
description: 在 AOE2-AI 中启动本地网页并等待用户选择模式、文明和打法偏好，再让新上下文作者填写动态参数并由主代理校验、机械渲染。用于“打开网页创作 AI”“使用网页创作 skill”等请求；保留真实 token 与时间计量，无生成简报或简报审批步骤。
---

# 网页参数创作

仓库根目录从 SKILL.md 所在目录向上三级取得。主入口：`adjusted/web-author/web_session.py`。
服务、用量说明：[../../web-author/README.md](../../web-author/README.md)、[../../web-author/METERING.md](../../web-author/METERING.md)。

## 开始与等待

仅在用户要求实际创作时启动；迁移、安装 skill 或只读评估不是开始创作。

在仓库根执行：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project <本轮唯一名称>
python -X utf8 -B adjusted/web-author/web_session.py wait --project <名称> --timeout 20
python -X utf8 -B adjusted/web-author/web_session.py next --project <名称>
```

使用启动结果的实际本机 URL，不猜端口。项目自动进入 `adjusted/.local/author-projects/<名称>/`，不复用历史作品。浏览器打开失败时提供真实 URL；不得报告已打开。这里只允许“打开页面”，不代表授权代理控制浏览器。

**网页设置默认由用户操作。** 主代理负责网页服务，不负责网页交互：执行 `launch` 后等待用户自己选择模式、文明、Agent、脚本名和时代偏好，并点击“开始生成”；主代理通过 `wait / next` 得知提交结果后再继续。不得因为任务包含“网页、选择、点击开始”等描述就自行调用 Computer Use、浏览器自动化、屏幕控制或视觉点击工具，也不得替用户填写或提交设置。**只有用户明确要求代理代为操作网页时，才可以使用这类工具。**

网页由用户依次完成模式 → 文明盾徽 → 设置 → 开始创作。文明页完整展示42个标准版盾徽，悬停或键盘焦点只预览右侧资料，点击即固定选择，无额外文明确认；也可选择让 AI 决定。设置包括本次实际使用的 AI Agent、脚本名和四时代攻防偏好。Agent 选择用于连接真实用量来源，不会自动启动或切换另一工具。开始后自主模式先选文明，手动模式直接填参数。滑块是用户偏好，不是某个官方参数的数值。没有简报、方案发布、permit 或二次审批。未点击前继续短周期 wait；超时不是授权，也不是任务结束。网页不能唤醒已退出的宿主代理，执行期间保持本会话工作。用户明确暂停或取消时尊重指令并结束会话。

## 自主选文明

按 [文明选择规则](../../web-author/CIVILIZATION_SELECTION.md) 执行。资格由 next 返回的标准版允许池决定：42 个文明，包含官方免费并入的前三个资料片，未购买额外 DLC。事实库有 53 个文明不代表都可选。

next.status=selecting 时，立即以 fork_turns="none" 创建作者，提供隔离输入、本轮条件和 civilization_selection，不给固定源码或旧作品。让同一作者先读候选相关事实与卡片，再选文明；固定执行机制不需要作者重写，特殊加成应作为打法素材，不能仅因不熟悉或不好算而回避。

推荐候选来自近期较少选择的文明；先比较其中三种不同打法，给出最终文明和一两句具体战术理由。仍可从全部合资格文明中选择，用户手动指定时不重选。不得伪造文明加成或历史使用频率。

作者先只将选择写入本项目 tmp/civilization-choice.json，保留 next 决策快照的 expected_revision：
```json
{"expected_revision": 2, "civilization": "<允许池中的内部标识>", "reason": "<文明特色如何支撑本轮打法>"}
```
主代理登记：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py choose-civilization --project <名称> --choice <本轮选择JSON>
```
成功前保持全部答案为 null；登记成功后，通过 followup_task 让同一作者继续填写。过期 revision 时重新取得 next 并核对条件，不能把旧决定直接升级为新版本。选择理由是轻量任务元数据，不生成简报、不要求用户批准，也不能代替完整参数创作。

## 作者与主代理分工

主代理负责网页服务的启动/等待、计量、导出输入、检查和渲染；默认不负责点击或填写网页。不要自己看完固定实现后再冒充隔离作者。

手动模式取得 next 返回的输入与答案目录后，以 `fork_turns="none"` 创建新作者；自主模式复用刚选定文明的同一作者。只给：
- 本次模式、文明和偏好，以及专属答案目录；
- 隔离输入包的 README、manifest、ANSWER_CONSTRAINTS；
- strategy 卡片、全 null 答卷、PARAMETER_CONSTRAINTS.json、基础 facts 和包内两种只读查询工具。

选定文明后，让作者按卡片的 group_id / 模块成组处理：查一组、决定一组、立即写入本轮 answers JSON，不要读完整包后才第一次落盘。每完成若干组就保存现有文件；主代理用 next 的 filled/total 看真实进度，长时间不增长时只让同一作者检查当前组，不重开整轮。无需逐批向用户汇报。自主选择阶段仅额外允许上面的选择元数据文件。

作者只写本轮 answers JSON。不要提供仓库模板、分类审查、官方默认答案、固定 PER、历史作品或其他 AI。不得增删键、用官方答案补空、自由编写 PER、改说明卡或把未知事实编成已验证结论。以 manifest 动态项数为准，不能硬编码旧版空位数。

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

build 会从本机 AoE2DE 安装目录读取官方 `PromiDE.per2`，核对其实际引用模块与仓库 `official/raw/Promisory/` 基线逐字节一致，再生成同名空 `.ai`、主 `.per`、36 个模块和 `resources/_common/ai` 安装结构。找不到入口时设置 `AOE2DE_PROMIDE_PER2` 指向游戏的 `resources/_common/drs/gamedata_x2/PromiDE.per2`；基线版本不一致时停止构建，不能猜加载顺序或混用不同补丁文件。

成功 build 标记 `installable=true` 仅表示安装结构和入口完整。不要把它声称为已经安装、Parser/Load 通过、完整对局或强度通过；这些游戏验证仍需用户授权。

## 用量与结束

先查看 next.usage_connection 与网页选定的 Agent，按 METERING.md 接入该宿主来源。创建子代理后绑定本次主会话和子会话；不把检测到安装目录当作已采集。不自动把所有宿主会话或其他项目计入。可使用 GitHub ccusage 的受控、按会话导出的 JSON 快照，通过 usage --action ccusage 导入；只能用真实记录，不能自己编造快照。Cursor IDE 优先走仓库项目 Hook + Cursor Team Admin Usage Events：Hook 只记录 conversation_id 等元数据；如有 Team Admin API key，在启动网页服务前通过环境变量 CURSOR_ADMIN_API_KEY 提供，绝不能写进仓库或网页。绑定当前 Cursor conversation 后可在最后生成页刷新官方 token。官方接口可能有聚合延迟；普通 IDE 不回退读取 bubble.tokenCount，也不按上下文占用/estimatedTokens 估算。没有 Admin API 权限时可导入 Cursor SDK 的真实 RunResult.usage / getUsage()，否则保持明确缺口。Cursor 子代理目前无法由官方 Hook 可靠回链 parent conversation，不能凭时间或同工作区猜归属。用户选择 Agent 不构成自动计量成功。

用量来自已绑定本项目的宿主实际 usage 或显式上报。上下文/工作流版本号不是模型 token。没有数据显示未采集；不按字数估算、不补零、不把并行无关任务算进来。子代理必须有可验证的会话或 usage 来源绑定；未能覆盖全部作者/审查调用时保持 PARTIAL。见计量说明登记来源、补报和封账。

完成交付后仅按真实覆盖情况封账；没有证据不声明 all_sources_declared。不可为补计量而重放付费模型调用。实际交付完成后，先补齐已有 usage，再执行下列 complete（默认只声明部分覆盖），最后 finish。需要声明全部来源已采集时，按计量说明封账并提供明确声明；不能默认认为子代理已覆盖。

```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action complete
python -X utf8 -B adjusted/web-author/web_session.py finish --project <名称>
```
单纯关闭浏览器或结束会话不代表交付或用量完整。网页“开发报告”可随时一键生成两个 Markdown：`creation-report.md` 是页面可直接查看/复制的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、阶段与调用用量、构建详情、事件时间线和日志摘要。不要生成 ZIP。finish 时还会自动保留最终两份报告。报告不能把未执行的游戏验证写成通过。最终聊天只需简短报告参数交付、实际用量覆盖和未验证部分。
