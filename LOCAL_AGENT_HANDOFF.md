# AOE2-AI 参数挖空交接文档

> 面向：本地 Agent  
> 日期：2026-09-22  
> 当前主仓库：`yqyjswj2001-cell/AOE2-AI`  
> 当前工作目录：`adjusted/cloze/`

## 1. 唯一目标

现在只做一件事：

**以官方 AoE2 DE Promisory AI 脚本为原件，保留官方结构、条件、命令和固定常量，只把真正会随打法变化的策略参数挖成 `{{PLACEHOLDER}}`，让后续 AI 做“完形填空”。**

不要再走以下旧路线：

- 不让 AI 自由重写整份 PER。
- 不再维护另一套抽象策略语言/动态编译器。
- 不重新设计官方规则。
- 不因为看到数字就挖空。
- 不优先做网页、局后复盘、创作包等外围功能。

## 2. 仓库边界

**必须在 `AOE2-AI` 仓库继续。**

不要把当前工作做回：

`yqyjswj2001-cell/aoe2-ffa8-ai-audit`

那个仓库是此前的实验室/来源仓库，不是本轮参数挖空工作区。曾误在该仓库创建过 `official/parameterized/`，已经全部删除，不需要恢复。

权威目录：

- `official/raw/Promisory/`：36 个官方 Promisory `.per` 原件，**禁止修改**。
- `adjusted/Promisory/`：当前与官方逐字节一致的工作基线，**不要在这里直接改策略**。
- `adjusted/cloze/Promisory/`：已参数挖空的 `.per.tpl` 模板。
- `adjusted/cloze/answers/`：给策略 AI 填写的空答案 JSON。
- `adjusted/cloze/official-defaults/`：每个空对应的官方原值，用于还原证明。
- `adjusted/tools/check_official_cloze.py`：模板边界与官方还原检查。
- `adjusted/tools/render_per_cloze.py`：只负责把答案机械替换进模板。
- `adjusted/tests/test_per_cloze.py`：renderer / round-trip 测试。
- `adjusted/PARAMETER_OWNERSHIP.md`：固定/动态唯一判定规则。
- `adjusted/cloze/README.md`：当前模块进度和每批挖空范围。

## 3. 核心原则

### 固定

凡是官方原件中**没有**替换成 `{{PLACEHOLDER}}` 的内容，一律视为固定。

固定内容不允许本地 Agent：

- 重写；
- “优化”；
- 合并规则；
- 改条件顺序；
- 改命令；
- 改 Goal ID / Timer ID / Object ID；
- 改 Fact ID / Unit ID / Research ID；
- 改 jump 数量；
- 改协议/枚举常量；
- 改微操实现细节。

### 动态

只有模板中已经明确出现的 `{{PLACEHOLDER}}`，以及经过同样严格筛选后新增的 placeholder，才是策略 AI 可以填写的内容。

**数字 != 参数。**

只有“改变打法选择”的数值才应该挖，例如：

- 经济资源分配比例；
- 何时把村民从一种资源切到另一种资源；
- 军事人口/敌我优势触发阈值；
- 攻击组大小；
- 某单位/建筑目标数量；
- 何时研究某经济/军事科技；
- 侦察、贸易、野猪、海战、投降等宏观策略阈值。

下面这些通常保持固定：

- ID；
- timer 编号；
- goal 编号；
- 状态值；
- 搜索/对象控制常量；
- 微操距离；
- 恢复/防卡死值；
- 调试值；
- 纯控制流数字。

## 4. 最重要的验证条件

每一个模板必须满足：

**模板 + `official-defaults` 中记录的官方值 = 对应官方 `.per` 原件，逐字节完全一致。**

不是“逻辑一样”，而是 byte-for-byte 一致。

因此：

- 不格式化官方源码；
- 不自动整理缩进；
- 不统一换行；
- 不删除注释；
- 不移动规则；
- 不顺手修复官方看起来奇怪的代码。

模板不是最终可运行 PER；只有填完所有 placeholder 后才能由 renderer 输出真正 `.per`。

## 5. 当前完成进度

截至 Batch 5，已有 **15 个模板，共 1876 个参数空位**：

| 模块 | 空位数 | 当前挖空范围 |
| --- | ---: | --- |
| `gatherers.per` | 346 | 食/木/金/石采集百分比 |
| `tsa.per` | 157 | 直接切换 attacking 状态的军力/优势阈值 |
| `orb.per` | 10 | 攻击组大小/数量等直接攻击组控制 |
| `scoutcontrol.per` | 45 | 探索数量、时间、战术阈值 |
| `trade.per` | 266 | 市场、资源、贸易数量阈值 |
| `escrow.per` | 448 | 升代、科研、经济、军事预算阈值 |
| `units.per` | 27 | 直接 train X 规则中，同 X 的生产数量上限 |
| `buildings.per` | 80 | 直接 build X 规则中，同 X 的目标建筑数 |
| `researches.per` | 297 | 常用经济科技与军事升级的直接触发阈值 |
| `boarhunting.per` | 56 | 野猪时机、村民、羊/食物触发阈值 |
| `threats.per` | 6 | 直接换攻击目标时的敌军人口阈值 |
| `watercontrol.per` | 10 | 海战 attack/retreat 的 water-advantage 阈值 |
| `dawn.per` | 72 | 前期村民资源分配的时机/数量阈值 |
| `finaling.per` | 16 | 后期直接出兵规则的人口/资源/反制触发阈值 |
| `resign.per` | 40 | 宏观投降的人口/时间/敌我优势阈值 |

累计：**1876**。

Batch 5 最后状态已经写入 `adjusted/cloze/README.md`。

Batch 5 之前的主状态提交：

`4d3c412335e70f47f74fce27649893436379e5a4` — Document official cloze batch 5

## 6. 每新增一个模块必须同时产生的东西

以 `foo.per` 为例，至少需要：

1. `adjusted/cloze/Promisory/foo.per.tpl`
   - 从 `official/raw/Promisory/foo.per` 原文生成；
   - 只把选中的值替换为 placeholder。

2. `adjusted/cloze/answers/foo.json`
   - key 与模板 placeholder 完全一致；
   - 所有值必须为 `null`。

3. `adjusted/cloze/official-defaults/foo.json`
   - 包含：
     - `source_file`
     - `source_blob_sha`
     - `answers`
   - `answers` 保存每个 placeholder 被挖掉前的官方原值。

4. 更新 `adjusted/tools/check_official_cloze.py`
   - 增加该模块专属的 curation guard；
   - 限制 placeholder 只能出现在批准的位置；
   - 防止以后误把控制常量也挖掉。

5. 更新 `adjusted/cloze/README.md`
   - 写模块名；
   - 写空位数；
   - 写“允许挖什么 / 明确不挖什么”。

## 7. Placeholder 规则

当前格式：

`{{UPPERCASE_DESCRIPTIVE_NAME_001}}`

要求：

- 仅使用 `A-Z 0-9 _`；
- 每个 placeholder 唯一；
- 名字表达它控制的策略意义；
- 不用源码行号作为唯一语义；
- official-defaults、answers、模板三方 key 必须完全一致。

现有例子：

- `{{TSA_MY_MILITARY_001}}`
- `{{BOAR_TIME_...}}`
- `{{WATER_ADVANTAGE_...}}`
- `{{DAWN_GATHERER_TARGET_...}}`
- `{{RESIGN_POPULATION_...}}`

## 8. 本地验证命令

每次改完必须先跑：

```bash
python3 -B adjusted/tools/check_official_cloze.py
python3 -B -m unittest discover -s adjusted/tests -v
```

Windows 可用：

```bat
py -3 -B adjusted\tools\check_official_cloze.py
py -3 -B -m unittest discover -s adjusted\tests -v
```

CI 工作流：

`.github/workflows/adjusted-runtime-validation.yml`

CI 做两件事：

1. 校验 36 个 `adjusted/Promisory/*.per` 仍与官方原件一致；
2. 校验所有 cloze 模板用官方默认值回填后能精确恢复官方源码，并执行 renderer unittest。

## 9. 当前断点：Batch 6 尚未落库

用户让我继续 Batch 6 时，已经开始筛选，但**还没有把 Batch 6 模板提交到仓库**。

因此本地 Agent 应从这里继续，不要把 Batch 6 当成已经完成。

当前剩余的主要非空/非微型模块包括：

- `ImprovementBucketsConst.per`
- `ImprovementBucketsTestConst.per`
- `const.per`
- `customConstants.per`
- `defaultConstants.per`
- `extremebuildings2.per`
- `finalingConstants.per`
- `general.per`
- `init.per`
- `interaction.per`
- `merge1b.per`
- `merge4.per`
- `paphosConstants.per`
- `ugp.per`

不要强求所有文件都必须产生 placeholder。纯常量、ID、协议、测试/控制模块完全可以保持 0 个动态参数。

## 10. Batch 6 已做过的分析

已经初步检查了剩余模块，结论如下。

### `finalingConstants.per`

这是比较干净的候选。

发现 6 组难度分支中反复出现这些策略值：

- `consecutive-idle-unit-limit`
- `enemy-sighted-response-percentage`
- `enemy-sighted-response-distance`
- `escrowing-percentage`

共看到 **24 个明显候选值**。

但仍需要先判断：这些值是否确实希望交给“策略 AI”而不是继续作为难度固定行为。不要因为已经找到 24 个就直接全部挖。

### `merge1b.per`

里面是若干文明配置块，存在明显的策略常量，例如：

- `number-barracks`
- `number-stables`
- `number-archery-ranges`
- `ig-food / ig-wood / ig-gold / ig-stone`
- `uu-food / uu-wood / uu-gold ...`
- `ur-food / ur-wood / ur-gold / ur-stone`
- `sling-number`
- 各种 `*-affinity`

这些比单位 ID / 科技 ID 更像真正的策略参数。

但以下内容不要自动挖：

- 文明 ID；
- 单位/建筑/科技 ID；
- `text-civ`；
- 纯可用性事实；
- 无法确认是否属于策略选择的 symbol。

### `customConstants.per`

这是一个很大的文明配置文件，其中大量文明重复定义类似：

- 建筑数量；
- 经济资源比例；
- UU 资源预算；
- 各 rush / flush / grush 等 affinity；
- 某些文明特有选择。

它很可能是后续大批量参数挖空的重要来源，但**风险也最高**。

建议方法：

1. 先列出一小组已经确认是策略参数的 defconst 名称；
2. 只对这些名字做精确替换；
3. 每个文明分支保留自己的官方默认值；
4. 不要用“匹配所有数字 defconst”的方式批量挖；
5. 加专属 checker guard，只允许白名单名称出现 placeholder；
6. round-trip 必须逐字节通过。

### `defaultConstants.per`

大部分是 Fact ID、class ID、枚举、action/order/object-data 常量。

**默认视为固定。**

名字里即便出现 food / attack / population，也不代表它是策略参数。例如：

`(defconst food-amount 5)`

这里的 `5` 是 Fact ID，不是“食物数量 5”，绝对不能挖。

这类错误是本项目当前最需要避免的。

### `general.per / init.per / interaction.per`

体量很大、控制流复杂。

不要先用宽泛正则扫数字。

后面处理时应该像前 5 批一样：

**先找一个明确的动作/决策结果，再只挖直接决定这个结果的条件。**

例如：

- 某规则直接改变策略状态；
- 某规则直接选择目标；
- 某规则直接触发援助/贡品；
- 某规则直接改变宏观生产/经济状态。

若数字只是搜索半径、临时变量、jump、timer、状态机实现，则固定。

### `merge4.per`

主要是多玩家编号、taunt、目标玩家控制。

当前判断应优先保持固定，不应因为里面有数字就参数化。

## 11. 建议本地 Agent 的下一步

先同步仓库并确认工作区干净：

```bash
git pull
git status
```

然后跑现有基线验证：

```bash
python3 -B adjusted/tools/check_official_cloze.py
python3 -B -m unittest discover -s adjusted/tests -v
```

两项都通过后再开始 Batch 6。

建议 Batch 6 继续采用“一次 3 个模块”的节奏，但模块选择以**边界是否清楚**为第一优先级，不追求数量。

比较合理的顺序：

1. 先精审 `finalingConstants.per`；
2. 再精审 `merge1b.per`；
3. 第三个可从 `customConstants.per` 中只做一个严格白名单批次，或另选边界更清晰的模块。

如果发现某个模块没有可靠的动态参数边界，**可以明确标记为 fixed/skip，不要硬挖。**

## 12. 提交要求

每批完成后至少确认：

- 官方原件没有修改；
- `adjusted/Promisory` 没有被改；
- 模板只改变已批准参数位置；
- blank answers 全部为 null；
- official defaults 完整；
- exact round-trip 通过；
- checker 增加模块专属限制；
- unittest 通过；
- `adjusted/cloze/README.md` 更新总数与本批说明。

提交信息继续保持简单明确，例如：

- `Add official cloze batch 6`
- `Enforce batch 6 curated cloze boundaries`
- `Document official cloze batch 6`

## 13. 最终判断标准

不要问“还有多少数字没挖”。

应该问：

> **还有哪些值是真正应该由策略 AI 决定，而不是官方运行机制的一部分？**

宁可少挖，也不要把固定机制错误暴露给 AI。

本项目的最终形态不是“AI 写 PER”，而是：

```text
官方 Promisory 规则
        ↓
只挖经过确认的策略参数
        ↓
AI 填 placeholder
        ↓
机械 renderer
        ↓
最终 .per
```

本地 Agent 从 **Batch 6** 继续即可。
