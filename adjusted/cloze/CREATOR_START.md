# 策略作者入口

你负责选择打法参数：资源怎么分、军队练多少、何时升级或出击，以及如何判断威胁。固定执行代码由主代理保留，作者输入不包含这部分代码，也不需要你填写它。

本页用于主代理通过 `build_strategy_input.py` 导出的隔离输入包。具体可填数量见包内 `manifest.json`；以本轮包为准，不继承旧版空位。

## 先读什么

1. 主代理给定的比赛条件、文明和本轮专属输出目录。
2. `strategy/*.json` 中与你当前决策相关的说明卡。每张卡写明参数含义、适用情境、直接作用、单位和关联要求。
3. [关联填写要求](ANSWER_CONSTRAINTS.md)。配比、上下限和重复引用需要一起考虑。
4. 需要游戏事实时，使用下面的只读查询；不必预读全部资料。

卡片很多时先按需查询，不用一次读完：

```powershell
python -X utf8 -B tools/query_strategy_cards.py
python -X utf8 -B tools/query_strategy_cards.py --module gatherers --groups
python -X utf8 -B tools/query_strategy_cards.py --search 葡萄牙
python -X utf8 -B tools/query_strategy_cards.py --key ORB_ATTACK_GROUP_005
```

查询只读取说明卡，不会接触固定实现或生成答案。

`answers/*.json` 是完整的可填键清单，初值都是 null。只填写这些键；不要增删参数、生成 PER 或修改说明卡。

## 作者输入范围

只读取本轮隔离包内的本页、manifest、关联要求、策略说明卡、空答卷、基础事实及两种只读查询工具，以及你自己本轮创建的文件。

不要回到主仓库读取模板、固定模块、分类审查记录、官方参考答案、历史策略或其他 AI。主代理会将合法答案机械填入受保护的位置，作者不需要接触固定实现。

## 查询基础事实

在输入包根目录执行（Python 标准库，只读）：

```powershell
python -X utf8 -I -B adjusted/tools/query_creator_facts.py info
python -X utf8 -I -B adjusted/tools/query_creator_facts.py civilizations
python -X utf8 -I -B adjusted/tools/query_creator_facts.py civilization Portuguese
python -X utf8 -I -B adjusted/tools/query_creator_facts.py unit 83
python -X utf8 -I -B adjusted/tools/query_creator_facts.py technology 101
python -X utf8 -I -B adjusted/tools/query_creator_facts.py gathering food_farm
```

资料有成本、生产时间、文明和采集事实；它不提供现成打法，也不保证覆盖所有文明条件。UNKNOWN 就保持未知，不能拿近似项代替。数值是记录范围内的基础值，需要考虑文明、科技、步行和避敌等修正；采集净收入未验证时不能宣称一定不断兵。

## 怎么交付

- 将填写完的答案写入主代理指定的独立输出目录，保留输入包的全 null 答卷。
- 围绕说明卡成组决策，关注不同阶段、触发条件和关联参数；多个空位不一定是多个独立战术。
- 简短说明资源与兵力安排、查询过的事实和未验证假设。资料或卡片不足时指出具体缺口，不自行补写固定代码。
- 新答案必须经过覆盖、关联关系与固定文本检查。静态通过不等于游戏加载、对局表现或强度通过。

本轮是官方固定实现上的参数化打法创作。读取基础事实不等于拥有最优策略；可填参数也不代表游戏中必定触发。
