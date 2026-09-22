# Adjusted AI Scripts

现有 2295 个候选参数全部完成静态分类：1715 个保留动态，580 个恢复官方固定值。

官方原件 official/raw/Promisory/ 和工作基线 adjusted/Promisory/ 保持一致。分类、模板与创作输入在 [cloze/README.md](cloze/README.md)。

作者只读动态策略卡、空答卷和基础游戏事实，不接收固定 PER。主代理通过 tools/build_strategy_input.py 导出输入，再通过机械 renderer 回填，保持官方实现不变。

工具在 tools/，测试在 tests/；本轮备份、审查和证据在 .local/parameter-classification/。历史试写和游戏安装不变。当前结果为本地静态分类，不代表实机效果。

网页创作：web-author/ 存服务、界面、计量与使用说明；skills/aoe2-web-author/ 存可复用创作 skill；tests/web_author/ 存合成测试。运行项目仅进入 .local/author-projects/<项目名>/；迁移原件、备份和证据进入 .local/web-author-migration/。

文明资格、选择逻辑和说明统一位于 web-author/；skill 继续位于 skills/aoe2-web-author/，检查位于 tests/web_author/。本轮备份与证据统一进入 .local/civilization-selection/。

基础资料固定在 knowledge/facts/，随仓库发布；本地输出、历史备份和日志仍在 .local/，不上传。下载入口见根目录 SKILL.md。
