# AOE2-AI 网页创作 skill

本仓库已包含可执行的网页参数创作流程。下载完整仓库后，先读根目录 [SKILL.md](SKILL.md)，再按其指向的唯一创作流程执行。不要根据旧交接文档继续挖空，也不要重新写一套 skill。

## 下载后怎么用

需要 Python 3.10 或更新版本，以及能执行本地命令、创建独立作者子代理的 AI 宿主。服务本身只用 Python 标准库；网页不独立调用模型。

把完整仓库克隆或解压到固定目录，然后对 AI 说：

> 读取这个仓库根目录的 SKILL.md，并按它打开网页开始创作。

不要只下载 SKILL.md 或 adjusted/skills/aoe2-web-author/：工具、模板、策略卡和事实库都是必需依赖。直接读入口即可使用；克隆仓库不等于安装到所有宿主的技能菜单。

主代理在仓库根执行：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project my-first-ai
```

网页第一步先选择实际 AI Agent，并明确允许自动计量或本轮不计量；之后再选择模式、文明盾徽、脚本名和时代偏好，最后开始创作。允许自动计量后，会话由后台/主 Agent 自动识别，不再要求用户选择 session。宿主继续等待网页提交，并按 [详细 skill](adjusted/skills/aoe2-web-author/SKILL.md) 调度作者、检查、渲染和记录 token。仅启动网页、随后结束宿主会话不会自动创作。

## 当前范围

- 1715 个动态参数由新上下文作者填写；580 个已审查候选恢复为官方固定值。
- 作者只接收策略卡、空答卷和基础事实，不接收固定实现或官方答案。
- 默认 AI 自主选文明，限制为标准版 42 文明，鼓励有战术理由的多样选择。
- 已移除生成简报、简报审批；保留真实 token、耗时及计量缺口。
- 可一键生成两份开发 Markdown：主报告可直接查看/复制，技术明细合并完整问题、反馈、参数诊断、调用用量、构建详情和日志摘要；不生成 ZIP。finish 自动保存最终报告。
- build 不依赖本机游戏；用户可选当前冻结官方基线的全部原生 `.per`，或一个可发送的 `.zip` 分享包。分享包只包含同一套脚本、清单和说明，不是游戏安装包。

## 目录地图

- SKILL.md：下载后的技能入口；详细流程唯一保存在 adjusted/skills/aoe2-web-author/。
- official/：参考原件与常量，禁止改写。
- adjusted/Promisory/：与官方一致的工作基线，禁止直接创作。
- adjusted/cloze/：模板、主代理参考答案、分类、作者卡片和空答卷。
- adjusted/knowledge/facts/：9 份冻结基础资料，随仓库分发。
- adjusted/tools/、adjusted/web-author/：工具、服务、页面和计量。
- adjusted/tests/：机械检查与合成测试。
- adjusted/.local/：运行项目、日志、备份、证据和临时产物；由 .gitignore 排除，不上传。

所有创作输出进入 adjusted/.local/author-projects/<项目名>/。禁止散落到根目录、游戏目录或其他项目。字节敏感的官方文件、模板和冻结资料禁止自动转换换行；仓库 .gitattributes 已关闭自动文本转换。

本仓库是私人项目，不是 Microsoft 或 Forgotten Empires 官方仓库。网页及计量迁入来源和许可证见 [UPSTREAM.json](adjusted/web-author/UPSTREAM.json) 与 [LICENSE](adjusted/web-author/LICENSE)；游戏资料权利不变。
