# 网页参数创作

由 AOE2-AI-STUDIO 迁入的本地创作工具。本版流程：可选测试功能 → 对局 → 文明 → 设置 → 作品。Token 计量默认关闭；普通创作不读取宿主 usage。只有手动打开测试开关时才显示 Agent 授权与 Token 结果页。

生成简报、编辑简报、简报确认和旧 permit 门槛已移除。网页不直接调用模型 API；需要宿主代理按 [skill](../skills/aoe2-web-author/SKILL.md) 保持执行。

## 使用

在 AOE2-AI 仓库根目录执行：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py launch --project my-first-ai
python -X utf8 -B adjusted/web-author/web_session.py watch --project my-first-ai --until start --timeout 600
```

启动会输出实际 URL 并尝试打开默认浏览器；这只负责打开页面，不代表代理应控制浏览器。网页设置默认由用户完成，主代理通过 `watch` 等待提交；除非用户明确要求代理代操作，否则不要调用 Computer Use、浏览器自动化或视觉点击工具。网页按五步前进：可选测试、选模式、选文明盾徽、设置、开始创作。第一步的 Token 测试计量默认关闭，直接下一步即可；只有手动开启时才选择 Agent 并授权。悬停/键盘焦点预览资料，点击立即固定文明；也能让 AI 选择。设置页选择脚本名和输出方式。脚本名同时作为创作名、游戏大厅 AI 类型名和进入对局后的显示名，三者必须一致。输出方式为原生脚本或分享脚本包。当前按标准版无额外 DLC 开放 42 文明；特殊机制作为打法素材，优先减少重复选择。[选择标准与官方版本依据](CIVILIZATION_SELECTION.md)。等待/验证/渲染/结束命令见 skill；`--help` 提供实际参数。Python 标准库即可运行服务。

作者仍需根据卡片与事实填写参数。本地服务不是文件系统沙箱：源码隔离依靠仅向新作者交付隔离输入包，并限制作者读取范围。

## 固定位置

- 本目录：服务、静态页面、计量模块、来源与说明。
- ../skills/aoe2-web-author/：仓库内可复用 skill；可让宿主直接读取 SKILL.md 使用。
- ../tests/web_author/：合成流程和计量测试。
- ../.local/author-projects/<名称>/：本轮 author-input、author-session、submissions、answers、delivery、logs、tmp、project.json、.author-web-session.json 和 authoring/metrics。
- ../.local/web-author-migration/：来源快照、备份、日志、验证证据与临时材料。
- ../.local/tmp/：Agent 一次性分析脚本和中间文件；禁止把 `tmp_*.py` 写到仓库根目录。

作者输入由现有 build_strategy_input.py 生成；只含动态卡片、空答卷和冻结基础事实。官方原件、固定代码、模板及参考值不通过网页发送。交付采用现有 renderer，不改变固定/动态分类。

## 作品登记

完整 `build` 成功后，作品会自动登记到 `adjusted/.local/ai-registry/works.sqlite3`。登记使用该套 PER 的内容指纹去重，因此同一作品重新打包不会重复新增。

以前已经做完、现在只剩 ZIP 或脚本目录的作品使用：

```powershell
python -X utf8 -B adjusted/web-author/web_session.py register-existing --artifact "<ZIP或目录>"
```

它支持当前 38 模块分享包、旧式无 manifest 的 36 模块 ZIP、旧式 `resources/_common/ai` 安装 ZIP，以及对应数量的原生脚本目录。其他模块数量不会被当成已完成作品。包内无法证明的历史字段保持未知；可直接证明的历史信息可通过 `--metadata <JSON>` 补充。用 `web_session.py registry-list` 查看已登记作品。

临时查看单个作品：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py registry-show --name "GROK_FFA8"
```

局后测试记录追加到同一作品，不覆盖创作资料：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py record-game --name "GROK_FFA8" --record "adjusted/.local/tmp/match-record.json"
```

`record-game` 适合由 Agent 根据结算截图和用户自然语言生成小型 JSON；无法从证据确认的字段应省略。每条对局记录单独保存，可查询累计局数、胜负和最近测试记录。

## 输出边界

创作不依赖本机游戏。完整参数校验通过后，原生模式写出当前冻结官方基线的全部 `.per`；分享模式生成一个 `.zip`，内含同一套 `.per`、`manifest.json` 和 `README.txt`。普通 build 不读取 `PromiDE.per2`，不生成 `.ai`、主入口或游戏安装目录，也不会自动安装或启动游戏。

用户明确要求直接安装到本机游戏时，可在 build 完成后执行 `web_session.py install --project <名称> --confirm-install`。该独立步骤才会定位真实 AoE2DE 根目录，只读游戏自带 `PromiDE.per2` 和 `Promisory`，生成同名 `.ai`、主 `.per` 与同一套模块并写入 `resources/_common/ai`。它不会修改官方 AI；同名旧安装先备份到项目 `install-backups/`。只有返回 `installed=true` 与 `verification=PASS` 才表示安装完成。

针对 2026-09-22 的 AoE2 DE Update 185872 后进入对局可能重新显示文明领袖名的情况，直接安装还会生成一个名字兼容 XS 到 `resources/_common/xs`，主 AI 入口在开局通过 `xsSetPlayerName` 把当前 AI 玩家名设回脚本名。该文件只负责显示名称，不参与策略决策。

[用量与时间计量](METERING.md) 是可选开发测试功能，默认关闭。开启时仍只保留真实来源、未知值与覆盖缺口；关闭时不读取宿主 usage、不创建自动采集连接，也不在结果页显示 Token 标签。

作品页“开发报告”标签提供“生成创作报告”，先预览，用户主动点击才下载。每次只生成两个 Markdown：`creation-report.md` 是可直接复制给开发的主报告；`technical-details.md` 合并完整问题/反馈、参数诊断、usage 调用、构建详情、事件时间线和日志摘要。报告本身不额外打 ZIP。原始计量数据库和项目事件文件仍留在项目目录供程序复查；finish 时自动保存最终两份报告。作者或主代理可用 `web_session.py feedback` 随时登记 issue / suggestion / note，避免修复后的问题从最终状态里消失。

来源版本与许可见 [UPSTREAM.json](UPSTREAM.json) 和 [LICENSE](LICENSE)。

## Agent 与计量接入

第一步点击“授权并继续”后即创建同一个持久账本并开始配置阶段计量，不等“开始生成”。Agent 身份默认自动确认，也能选择实际宿主；网页不会启动或切换工具。`watch / next` 会优先交回 `usage_task`，主 Agent 通过认证的 `usage --action connect --payload ...` 提交真实会话身份或明确缺口，不让用户选 session。详细命令见 [Skill](../skills/aoe2-web-author/SKILL.md)。

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

## 减少流程往返

`web_session.py handoff --project <名称>` 自动生成 `author-session/task.json`，包含完整文明允许池、候选、设置和唯一提交位置。作者只提交参数增量，由项目内 `submit_answers.py` 合并、校验并保留其他空项；不直接重写完整答卷。完成策略检查后执行该工具的 `--complete`，主代理再运行原有完整校验。

`watch --until answers --timeout 600` 在同一程序进程中等待作者完成或错误，不把普通进度变化交回模型。调试时可用 `next --compact` 读取简短状态，完整 next 仍保留。服务不能唤醒已经退出的宿主；优先使用宿主原生完成通知，不反复新建等待进程。

参数数量、策略卡、事实文件、官方固定源码和最终渲染校验未减少。省时与 token 效果需要真实创作前后比较，合成测试不证明策略质量或账单节省。
