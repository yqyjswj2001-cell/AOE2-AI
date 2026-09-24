# 固定安装模板

当前状态：缺少与仓库基线配套的真实 `PromiDE.per2`。没有用测试入口或推测顺序代替。

只需维护者导入一次真实文件。程序核对实际游戏目录内全部 36 个官方模块与 `official/raw/Promisory` 一致，再保存原入口、空 `.ai` 标记和校验清单：

```powershell
python -X utf8 -B adjusted/web-author/install_template.py --capture "游戏目录/resources/_common/drs/gamedata_x2/PromiDE.per2"
```

目录位置特殊时，增加 `--game-promisory "实际的 Promisory 目录"`。生成后的 `PromiDE.per2`、`marker.ai` 和 `manifest.json` 一起保留在本目录并提交仓库。之后正常打包不需要本机安装游戏，只机械替换脚本目录名称、复制本轮 36 个模块。不要把作者答案或完整策略放进本目录。

入口哈希、模块哈希或加载清单不一致时拒绝打包，不偷偷回退或重排。升级基线时先用 `--out` 导入到新目录核对，再由维护者替换本模板。模板不对隔离作者开放。

启动预检：`python -X utf8 -B adjusted/web-author/install_template.py`。缺失时仍可填写、验证参数，但不能声称已有可安装包。静态结构检查不等于游戏 Parser/Load 或实战通过。
