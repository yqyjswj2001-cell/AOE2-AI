# 固定参数与动态参数分类

现有 2295 个候选参数全部完成静态分类：1715 个保留动态，580 个恢复官方固定值。

本清单是主代理/检查器使用的审查资料，不交给策略作者。

## 判定口径

- 动态：改变资源分配、兵力投入、研究与扩建时机、威胁响应或攻退判断，有明确的战术含义和可解释消费位置。
- 固定：游戏事实、成本与能力、状态和调度、存在性检查、队列互锁、异常恢复、无实际动作、被覆盖/冗余条件、加载或含义无法可靠确认的参数。保持官方原值。
- 未进入原 2295 候选清单的代码和数值继续固定。本次没有把全部官方数值重新开放。
- 复杂或不确定依赖按保守固定处理；这不等于该数字理论上永远不能用于设计策略。

## 完整覆盖

| 模块 | 保留动态空位 | 恢复固定 |
|---|---:|---:|
| boarhunting.per | 35 | 21 |
| buildings.per | 34 | 46 |
| customConstants.per | 400 | 32 |
| dawn.per | 49 | 23 |
| escrow.per | 272 | 176 |
| finaling.per | 15 | 1 |
| gatherers.per | 304 | 40 |
| merge1b.per | 0 | 21 |
| orb.per | 10 | 0 |
| researches.per | 284 | 13 |
| resign.per | 0 | 40 |
| scoutcontrol.per | 2 | 16 |
| threats.per | 6 | 0 |
| trade.per | 129 | 137 |
| tsa.per | 140 | 12 |
| units.per | 25 | 2 |
| watercontrol.per | 10 | 0 |


全部参数的逐项理由、条件、消费者作用、官方来源哈希和数字位置见 [parameters.json](parameters.json)。其中 official_value、source_start/source_end 只供机械还原和边界检查，不属于作者输入。

主模板保留在 ../Promisory/，包括已经没有动态项的模块。只替换预先审查的位置，其余源码逐字节保留；分类表或官方来源变化需要重新审查。

## 作者输入

作者只收到 [策略卡](../strategy/README.md)、对应空答卷和游戏事实。不给完整 PER、固定规则、官方填空答案或本分类表。使用 `adjusted/tools/build_strategy_input.py --out <新的独立目录>` 导出，不从旧试写复制输入。

## 证据边界

这是对现有候选参数的静态语义分类。动态项仅在对应文明、时代、地图和分支触发时可能生效，仍由官方执行框架消费。本次没有解决原件所有逻辑问题，也不宣称是全新 AI。

[本地任务记录](../../.local/parameter-classification/README.md)。旧 boundary-refinement 与 authoring-trial-002 保留为历史，不重写其计数或验证。Parser/Load、Smoke、完整对局和强度仍为 Unverified。
