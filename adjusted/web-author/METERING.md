# 真实 token 与时间计量

从 Studio 的计量核心迁入，删除简报阶段和旧许可依赖。网页、JSON 和 CSV 均读取同一 SQLite 台账。没有模型 API、金额换算或按字数估算功能。

## 范围与未知

只记录本项目明确绑定来源的真实 usage。网页开始创作后建立计量；之前聊天不计入。工作流 revision、session token 只是状态/连接标记，不是模型 token。

- NOT_CONNECTED：未取得用量来源，总 token 为 null。
- PARTIAL：仅为已取得的小计；来源未封账、采集缺口、未知调用或未声明全部覆盖都保留部分状态。
- HOST_REPORTED_COMPLETE：来源封账、记录可用且宿主明确声明全部覆盖，仍不是提供商账单审计。

缓存和推理通常是输入/输出子项，不重复相加；Anthropic 缓存读写按其 usage 字段归并一次。缺失细项保持 null；已知部分小计另有完整性标记。失败、重试、耗时仅按有依据的事件报告，不从记录数量猜测。

总历时、工作流程时间、人工等待和未观察时间分开。它们不是纯模型思考时间；并行调用耗时不能简单加成墙钟时间。不能可靠归属阶段的用量留在未归属阶段。

## 自动与显式来源

默认绑定继承的 CODEX_THREAD_ID，按累计 token 差值计数，重复快照不重复累计。只记录 ID、模型、计数和时间等用量元数据，不保存或上传提示词、回答、推理正文及工具输出。

保留上游多宿主解析器，但不再把时间窗口内的所有会话自动归入项目。Claude Code 等其他宿主或新作者子代理必须能明确绑定会话。没有可靠 usage 的宿主保持未采集；格式、截断或重置等缺口会进入网页和导出报告，阻止假完整声明。

主代理取得可靠的子代理会话 ID 后，把下列形式的 JSON 保存到本次项目 tmp/ 目录（示例 ID 必须替换为实际值），再登记：
```json
{"sessions":{"codex":["本任务的实际子会话UUID"],"claude":["本任务的实际会话ID"]}}
```
```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action bind --payload <本轮绑定JSON>
```

不能用代理昵称、时间相近或“我开了子代理”来证明用量已经覆盖。没有子代理的会话或独立 usage 证据时，报告明确保持 PARTIAL。

宿主也可提供已有本次 JSONL 或最终响应的 usage：
```powershell
python -X utf8 -B adjusted/web-author/usage.py import --project <本轮项目绝对路径> --file <本轮JSONL> --source-id <稳定来源ID> --format codex-exec --seal
```
支持格式及参数以 usage.py --help 为准。只导入明确属于本轮的日志，不混入自动采集同一会话的数据。SDK 的 UsageClient 可以包装现有请求，但不能为补计量重放付费调用；宿主隐藏重试不在可观察范围时保留缺口。

## 阶段与完成

使用 web_session.py phase 的 researching / authoring / checking / repairing / packaging；没有简报阶段。

build 只登记真实模块交付，不提前关闭用量台账。等作者和检查调用已结束、已有 usage 已采集后：
```powershell
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action report
python -X utf8 -B adjusted/web-author/web_session.py usage --project <名称> --action complete
python -X utf8 -B adjusted/web-author/web_session.py finish --project <名称>
```
默认 complete 不声明全覆盖。确有全部调用证据时，先用 usage 的 seal 操作按来源登记实际条数，再提交 complete 的 payload：`{"all_sources_declared":true}`。有未封账来源或采集缺口会拒绝声明；不要为通过而删掉缺口或把未知值改成零。

HTTP 来源接口（由 host 命令携带身份与鉴权）：source / events / seal / bind / phase / complete，前缀 /api/author/usage/。事件 event_id 稳定去重，同 ID 内容冲突拒绝。计量写入不推进策略创作状态。complete 绑定当前已校验且未变更的模块交付。

## 落盘与导出

台账：本轮项目 authoring/metrics/usage.sqlite3。结束后保留不可覆盖的 report-<指纹>/summary.json、stages.csv、calls.csv；自动采集状态与缺口也写入正式报告。网页可随时下载当前快照。CSV 为 UTF-8 BOM，空格单元表示未知。

服务结束不等于用量全部覆盖，也不等于游戏验证通过。测试使用合成 usage，不能据此声称所有支持宿主的真实调用都已实测覆盖。测试关闭自动采集可用 AOE2_USAGE_DISABLE_AUTO=1；此时报告明确 DISABLED，不伪造实际计数。
