# 官方固定实现与动态策略参数

现有 2295 个候选参数全部完成静态分类：1715 个保留动态，580 个恢复官方固定值。

## 当前方式

官方代码结构、条件、命令和固定值由工具保留。AI 只选择已审查的动态参数，不重写 PER。

1. 主代理按 [分类表](classification/README.md) 保管模板和官方原值。
2. 用 `python -B adjusted/tools/build_strategy_input.py --out <新目录>` 生成作者输入。
3. 创建不继承审查历史的新作者，只给隔离输入包。作者读策略卡、查游戏事实并填答卷；不复用已经看过官方原值的审查代理。
4. 主代理检查关联参数和受保护位置，再由 `render_per_cloze.py` 机械替换。答案无效时先拒绝，不写部分结果，也不替作者改策略。

[作者入口](CREATOR_START.md) · [参数约束](ANSWER_CONSTRAINTS.md) · [策略卡](strategy/README.md)

## 数量

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


仍保留 17 份主代理模板，方便完整还原；全固定模块不出现在作者卡片和作者答卷中。空位数量不等于规则数或独立决策数。

## 文件位置

- Promisory/：主代理专用模板，包含固定实现，不交给作者。
- official-defaults/：主代理专用原值，用于逐字节恢复证明。
- answers/：全 null 答卷；全固定模块在此为空对象，导出作者包时略过。
- classification/：主代理专用逐项分类与源码位置白名单。
- strategy/：仅动态参数的作者说明卡。
- ../tools/、../tests/：机械渲染、保护检查、导出工具与相关测试。
- ../.local/parameter-classification/：本轮备份、审查、证据、日志及作者输入样本。

## 验证和历史

检查器要求 36 个工作基线仍与官方原件一致；17 份模板填回原值必须逐字节恢复官方文件。每个保留空位绑定到已审查源码位置，固定项即使换名重新挖空也会被拒绝。

Batch 6 的 2329 空记录见 [历史审查](BATCH6_REVIEW.md)；上一轮先恢复 34 项后为 2295 空，本轮对这 2295 项作完整分类。历史试写、旧证据和游戏安装不变。

分类与检查通过只证明当前静态边界和已登记关系。Parser/Load、Smoke、完整对局与强度仍为 Unverified。当前创作流程入口见仓库根目录 SKILL.md。
