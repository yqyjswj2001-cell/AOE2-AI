---
name: aoe2-web-author
description: 使用完整 AOE2-AI 仓库启动网页、选择模式与文明，并让独立作者填写动态策略参数、检查和生成 PER 模块；保留真实 token 计量，无生成简报。用于下载并使用本仓库、打开网页创作 AI 等请求。
---

# AOE2-AI 创作入口

本技能依赖完整仓库。以本文件所在目录为仓库根，确认 adjusted/web-author/web_session.py、adjusted/tools/build_strategy_input.py 和 adjusted/knowledge/facts/ 均存在。缺失时重新获取完整仓库，不能只复制本文件。

主代理必须读取并执行唯一的 [详细创作流程](adjusted/skills/aoe2-web-author/SKILL.md)。这是现成的参数创作工具，不是继续挖空、重新分类或重写官方 AI 的任务。

用户要求实际使用、打开网页或创作时，按详细流程启动服务并保持宿主执行；仅下载、同步、安装或评估时不自动创作。按需将此完整仓库放入宿主支持的技能目录，或让宿主直接读取本入口，不假称已经自动安装。

作者必须是独立的新上下文，仅给本轮隔离输入和答卷目录；不得给官方固定源码、模板、分类表或官方答案。宿主无法创建独立作者时说明能力缺口，不用已读固定实现的主代理冒充作者。

运行产物仅放 adjusted/.local/author-projects/。实际创作数量由本轮 manifest 决定；保留未知 token 和未覆盖来源。当前产物为模块包，不能声称已经可安装、通过游戏加载或实战验证。
