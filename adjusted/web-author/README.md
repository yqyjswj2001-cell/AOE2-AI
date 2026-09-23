# 网页参数创作

由 AOE2-AI-STUDIO 迁入的本地创作工具。本版流程：授权 → 对局 → 文明 → 打法 → 作品。每步只显示对应内容，打法页直接开始；作品页分为生成进度、完整用量、开发报告三个平级视图。

生成简报、编辑简报、简报确认和旧 permit 门槛已移除。网页不直接调用模型 API；需要宿主代理按 [skill](../skills/aoe2-web-author/SKILL.md) 保持执行。

## 使用

在 AOE2-AI 仓库根目录执行：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project my-first-ai
python -X utf8 -B adjusted/web-author/web_session.py next --project my-first-ai
```

启动会输出实际 URL 并尝试打开默认浏览器；这只负责打开页面，不代表代理应控制浏览器。网页设置默认由用户完成，主代理通过 `wait / next` 等待提交；除非用户明确要求代理代操作，否则不要调用 Computer Use、浏览器自动化或视觉点击工具。网页按五步前进：用量授权、选模式、选文明盾徽、设置、开始创作。悬停/键盘焦点预览资料，点击立即固定文明；也能让 AI 选择。授权页默认由当前 Agent 确认身份；设置页只设脚本名和时代偏好。当前按标准版无额外 DLC 开放 42 文明；特殊机制作为打法素材，优先减少重复选择。[选择标准与官方版本依据](CIVILIZATION_SELECTION.md)。等待/验证/渲染/结束命令见 skill；`--help` 提供实际参数。Python 标准库即可运行服务。

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

作品页“开发报告”标签提供“生成创作报告”，先预览，用户主动点击才下载。每次只生成两个 Markdown：`creation-report.md` 是可直接复制给开发的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、usage 调用、构建详情、事件时间线和日志摘要。没有 ZIP。原始计量数据库和项目事件文件仍留在项目目录供程序复查；finish 时自动保存最终两份报告。作者或主代理可用 `web_session.py feedback` 随时登记 issue / suggestion / note，避免修复后的问题从最终状态里消失。

来源版本与许可见 [UPSTREAM.json](UPSTREAM.json) 和 [LICENSE](LICENSE)。

## Agent 与计量接入

第一步点击“授权并继续”后即创建同一个持久账本并开始配置阶段计量，不等“开始生成”。Agent 身份默认自动确认，也能选择实际宿主；网页不会启动或切换工具。`wait / next` 会优先交回 `usage_task`，主 Agent 通过认证的 `usage --action connect --payload ...` 提交真实会话身份或明确缺口，不让用户选 session。详细命令见 [Skill](../skills/aoe2-web-author/SKILL.md)。

后台每 3 秒读取选定宿主的本轮来源，不依赖浏览器轮询。未知宿主没有精确绑定时不扫描其他 Agent 的数据目录。配置与生成共用 run；刷新、重复授权和恢复项目不会重置计数。顶部只显示“待授权 / 接入中 / 已接入待记录 / 正在记录 / 存在缺口 / 已停止”等状态，不反复堆叠数字。

“本轮不计量”不读取自动来源；“停止采集”撤回本轮授权，保留已有账本并阻止后续新增采集。未采集不是零，缓存和推理属于明细，不重复加到总量，子代理未覆盖仍显示 PARTIAL。授权前消耗不补算；真实接口未开放或归属不明时保持缺口，不按上下文长度估算。

Cursor 另有可选官方链路：仓库项目 Hook 只记录 conversation_id 等元数据；若启动服务前设置 `CURSOR_ADMIN_API_KEY`，服务会把当前 conversation 自动归属到唯一活动项目并在后台低频刷新 Cursor Team Admin Usage Events，用户无需手动绑定或刷新。API key 不写入项目、网页或报告；无权限时不会回退用本机 tokenCount/上下文占用估算。

盾徽在 web/assets/civilizations/，资料由 civilization_catalog.py 只读提供；本轮备份/截图/验证统一放 adjusted/.local/ui-token-revision/，不上传。


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
