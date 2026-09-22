# 冻结创作事实资料

`facts/` 随仓库发布，供只读查询工具和隔离作者输入包使用；不依赖本机 `.local/` 缓存。

## 来源与完整性

- 固定来源仓库：`yqyjswj2001-cell/aoe2-ai-studio`
- 固定提交：`bb36e88dd2a5d4ea1841da2f647753106bf7421b`
- 来源目录：`creator-kit/current/write/facts/`
- 仅包含 `../tools/query_creator_facts.py` 的 `FILES` 允许清单中 9 个 JSON；逐字节保留，不修改内容或来源哈希。
- 查询时逐个核对工具内的 `EXPECTED_GIT_BLOBS`；内容中的路径仅作来源说明，不跟随读取。

## 目录与使用

- `facts/economy/`：单位与建筑、科技、村民采集基础值及来源清单。
- `facts/civilizations/`：文明资料子集。
- `facts/api/`：API 形状、审核修正及常量资料。
- `facts/public-api.json`：公开 API 资料。

在仓库根执行 `python -X utf8 -I -B adjusted/tools/query_creator_facts.py info` 验证 9 份资料。`build_strategy_input.py` 将同样的资料导出到作者包的 `adjusted/knowledge/facts/`，保持工具可独立运行。

本目录只保存发布所需的冻结资料；任务日志、备份和临时文件继续进入 `adjusted/.local/` 对应任务目录，本次同步证据位于 `adjusted/.local/github-sync/`。

## 真实性边界

这是固定来源资料子集，不是完整官方事实库，也不是本次游戏实测。空值与版本范围保持原样；API 或常量收录不证明当前游戏接受。Parser/Load、实机效果与强度仍为 `Unverified`。
