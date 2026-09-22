---
name: aoe2-web-author
description: 在 AOE2-AI 中通过本地网页选择模式、文明和打法偏好，让新上下文作者填写动态参数并由主代理校验、机械渲染。用于“打开网页创作 AI”“使用网页创作 skill”等请求；保留真实 token 与时间计量，无生成简报或简报审批步骤。
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

使用启动结果的实际本机 URL，不猜端口。项目自动进入 `adjusted/.local/author-projects/<名称>/`，不复用历史作品。浏览器打开失败时提供真实 URL；不得报告已打开。

网页依次选择模式 → 文明盾徽 → 设置 → 开始创作。文明页完整展示42个标准版盾徽，悬停或键盘焦点只预览右侧资料，点击即固定选择，无额外文明确认；也可选择让 AI 决定。设置包括本次实际使用的 AI Agent、脚本名和四时代攻防偏好。Agent 选择用于连接真实用量来源，不会自动启动或切换另一工具。开始后自主模式先选文明，手动模式直接填参数。滑块是用户偏好，不是某个官方参数的数值。没有简报、方案发布、permit 或二次审批。未点击前继续短周期 wait；超时不是授权，也不是任务结束。网页不能唤醒已退出的宿主代理，执行期间保持本会话工作。用户明确暂停或取消时尊重指令并结束会话。

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

主代理负责网页、计量、导出输入、检查和渲染；不要自己看完固定实现后再冒充隔离作者。

手动模式取得 next 返回的输入与答案目录后，以 `fork_turns="none"` 创建新作者；自主模式复用刚选定文明的同一作者。只给：
- 本次模式、文明和偏好，以及专属答案目录；
- 隔离输入包的 README、manifest、ANSWER_CONSTRAINTS；
- strategy 卡片、全 null 答卷、基础 facts 和包内两种只读查询工具。

选定文明后，让作者按卡片关联要求成组填完全部参数，只写本轮 answers JSON；自主选择阶段仅额外允许上面的选择元数据文件。不要提供仓库模板、分类审查、官方默认答案、固定 PER、历史作品或其他 AI。不得增删键、用官方答案补空、自由编写 PER、改说明卡或把未知事实编成已验证结论。以 manifest 动态项数为准，不能硬编码旧版空位数。

卡片按需查：
```powershell
python -X utf8 -B tools/query_strategy_cards.py --module gatherers --groups
python -X utf8 -I -B adjusted/tools/query_creator_facts.py civilization Portuguese
```
命令在隔离输入包中运行。资料 UNKNOWN 时指出缺口；不要因缺资料读取固定实现。

## 检查与交付

阶段按实际动作更新：researching、authoring、checking、repairing、packaging。
```powershell
python -X utf8 -B adjusted/web-author/web_session.py phase --project <名称> --value authoring
python -X utf8 -B adjusted/web-author/web_session.py validate --project <名称>
python -X utf8 -B adjusted/web-author/web_session.py build --project <名称>
```

错误只反馈参数键、类型、范围或关联要求，交给同一作者修正；不要反馈官方参考值或固定源码。用现有 renderer 机械代入，不编译另一套策略语言。不能把 null 填零或默默回退默认值。完成时返回真实交付目录、哈希回执和静态结果。

当前 build 是 36 个模块的交付包，不含独立游戏入口；`installable=false`。不要把模块交付声称为游戏已安装、Parser/Load 通过、完整对局或强度通过。游戏验证另需用户授权。

## 用量与结束

先查看 next.usage_connection 与网页选定的 Agent，按 METERING.md 接入该宿主来源。创建子代理后绑定本次主会话和子会话；不把检测到安装目录当作已采集。不自动把所有宿主会话或其他项目计入。可使用 GitHub ccusage 的受控、按会话导出的 JSON 快照，通过 usage --action ccusage 导入；只能用真实记录，不能自己编造快照。Cursor SDK 的真实 RunResult 可上报 cursor-sdk；普通 Cursor IDE 的上下文占用和 estimatedTokens 不等于消耗，来源缺失时保留明确缺口。用户选择 Agent 不构成自动计量成功。

用量来自已绑定本项目的宿主实际 usage 或显式上报。上下文/工作流版本号不是模型 token。没有数据显示未采集；不按字数估算、不补零、不把并行无关任务算进来。子代理必须有可验证的会话或 usage 来源绑定；未能覆盖全部作者/审查调用时保持 PARTIAL。见计量说明登记来源、补报和封账。

完成交付后仅按真实覆盖情况封账；没有证据不声明 all_sources_declared。不可为补计量而重放付费模型调用。实际交付完成后，先补齐已有 usage，再执行下列 complete（默认只声明部分覆盖），最后 finish。需要声明全部来源已采集时，按计量说明封账并提供明确声明；不能默认认为子代理已覆盖。

```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action complete
python -X utf8 -B adjusted/web-author/web_session.py finish --project <名称>
```
单纯关闭浏览器或结束会话不代表交付或用量完整。最终简短报告参数交付、实际用量覆盖和未验证部分。
