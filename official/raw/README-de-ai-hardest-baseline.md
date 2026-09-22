# 官方 DE AI 极难基线：只读参考，禁止修改

绝对路径：

```text
E:\AIproject\playgame\官方DE_AI_极难基线_禁止修改
```

## 禁止事项

- 禁止在本目录原地编辑、格式化、重命名、删除或覆盖任何文件。
- 禁止把本目录当作 AI 实验输出目录。
- 禁止直接把本目录安装进游戏。
- 需要改造时，只能把必要内容复制到：

  ```text
  E:\AIproject\playgame\AI改造脚本_基于官方极难
  ```

## 来源与完整性

来源：

```text
S:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\ai\Promisory
```

本目录的 `Promisory/` 包含 36 个官方 `.per` 模块，共 3,758,279 字节。复制后已逐文件比较 SHA-256，结果为 36/36 一致。`ai.txt` 也从同一官方 AI 根目录复制。

这些文件保留官方原貌，包含全部难度、地图、文明和模式的条件编译分支；本副本没有预处理成单独的极难版本，也不是已经验证可独立加载的单文件 AI。

## 推荐基线

需要制作“完整但不过度专用”的派生 AI 时，优先采用：

```text
DIFFICULTY-HARDEST
```

原因：极难分支保留完整经济、住房、生产、科技、防守、进攻和恢复逻辑，没有低难度的人口/军队阉割，也不加载 `DIFFICULTY-EXTREME` 专用的额外建筑系统和早期微操。

## 读取边界

用户已明确允许 AI 读取本目录中的官方 DE AI 基线。仍然禁止读取游戏中的 HD AI、CD AI、社区 AI、Workshop AI、比赛对手 AI、其他会话生成的 AI 或任何未被用户指定的 AI 源码。
