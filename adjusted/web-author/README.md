# 网页参数创作

从 AOE2-AI-STUDIO 的网页创作 skill 与真实计量实现迁入。新流程为：模式 → 完整文明盾徽与资料 → 设置及实际 AI Agent → 开始创作 → 新上下文作者填写动态参数 → 校验修正 → 主代理机械渲染 → 交付模块。

生成简报、编辑简报、简报确认和旧 permit 门槛已移除。网页不直接调用模型 API；需要宿主代理按 [skill](../skills/aoe2-web-author/SKILL.md) 保持执行。

## 使用

在 AOE2-AI 仓库根目录执行：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project my-first-ai
python -X utf8 -B adjusted/web-author/web_session.py next --project my-first-ai
```

启动会输出实际 URL 并尝试打开默认浏览器；这只负责打开页面，不代表代理应控制浏览器。网页设置默认由用户完成，主代理通过 `wait / next` 等待提交；除非用户明确要求代理代操作，否则不要调用 Computer Use、浏览器自动化或视觉点击工具。网页按四步前进：选模式、选文明盾徽、设置、开始创作。悬停/键盘焦点预览资料，点击立即固定文明；也能让 AI 选择。设置页选择本次实际使用的 AI Agent、脚本名和时代偏好。当前按标准版无额外 DLC 开放 42 文明；特殊机制作为打法素材，优先减少重复选择。[选择标准与官方版本依据](CIVILIZATION_SELECTION.md)。等待/验证/渲染/结束命令见 skill；`--help` 提供实际参数。Python 标准库即可运行服务。

网页偏好不是参数答案；作者仍需根据卡片与事实填写。本地服务不是文件系统沙箱：源码隔离依靠仅向新作者交付隔离输入包，并限制作者读取范围。

## 固定位置

- 本目录：服务、静态页面、计量模块、来源与说明。
- ../skills/aoe2-web-author/：仓库内可复用 skill；可让宿主直接读取 SKILL.md 使用。
- ../tests/web_author/：合成流程和计量测试。
- ../.local/author-projects/<名称>/：本轮 author-input、answers、delivery、logs、tmp、project.json、.author-web-session.json 和 authoring/metrics。
- ../.local/web-author-migration/：来源快照、备份、日志、验证证据与临时材料。

作者输入由现有 build_strategy_input.py 生成；只含动态卡片、空答卷和冻结基础事实。官方原件、固定代码、模板及参考值不通过网页发送。交付采用现有 renderer，不改变固定/动态分类。

## 验证边界

构建会使用本机游戏的官方 PromiDE.per2 作为加载顺序来源，并要求它引用的官方 Promisory 模块与仓库冻结基线逐字节一致；随后生成同名 .ai、主 .per、36 个模块及 resources/_common/ai 目录，作为可安装包。若找不到游戏入口或基线版本不一致则拒绝构建，不猜加载顺序。Parser/Load、实机开局、完整对局和强度仍为 Unverified；本功能不会自动安装或启动游戏。

[用量与时间计量](METERING.md) 保留真实来源、未知值与覆盖缺口。仅声明本次测试实际覆盖的行为，不能从合成测试推断所有宿主的真实调用都已计入。

网页底部提供“生成创作报告”。每次只生成两个 Markdown：`creation-report.md` 是可直接复制给开发的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、usage 调用、构建详情、事件时间线和日志摘要。没有 ZIP。原始计量数据库和项目事件文件仍留在项目目录供程序复查；finish 时自动保存最终两份报告。作者或主代理可用 `web_session.py feedback` 随时登记 issue / suggestion / note，避免修复后的问题从最终状态里消失。

来源版本与许可见 [UPSTREAM.json](UPSTREAM.json) 和 [LICENSE](LICENSE)。

## Agent 与计量接入

选择 Agent 表示本轮实际运行宿主，不会由网页自动切换工具。自动采集、会话快照导入、SDK usage 上报按各宿主真实能力区分，见 [计量说明](METERING.md)。未开放真实用量的宿主明确显示缺口；上下文长度不是消耗。

Cursor 另有可选官方链路：仓库项目 Hook 只记录 conversation_id 等元数据；若启动服务前设置 `CURSOR_ADMIN_API_KEY`，绑定当前 Cursor conversation 后，可在最后生成页手动刷新 Cursor Team Admin Usage Events。API key 不写入项目、网页或报告；无权限时不会回退用本机 tokenCount/上下文占用估算。

盾徽在 web/assets/civilizations/，资料由 civilization_catalog.py 只读提供；本轮备份/截图/验证统一放 adjusted/.local/ui-token-revision/，不上传。
