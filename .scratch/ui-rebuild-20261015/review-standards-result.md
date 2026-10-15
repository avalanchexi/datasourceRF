确认以下 4 项正确性问题，均非可选重构建议。**基线审查未完成**：`git diff`、`rg` 持续报 `helper_unknown_error`，以下仅依据已读取并复核的当前文件；未改文件、运行测试或访问运行库及外部接口。

1. **P2｜[run_health.py:201](/D:/cursor/datasourceRF/src/pring_cycle/run_health.py:201)**：官方请求命中负缓存时，获取回执已创建，但 `reserve()` 在 `fetch()` 前拒绝发送；这里仍将回执计入请求和失败，虚增请求数与桑基流量。调用链见 `acquisition.py:350–368`、`retrieval_ledger.py:457`。规则：规格 §9，缓存命中及未发送请求不计外部请求。

2. **P2｜[run_health.py:257](/D:/cursor/datasourceRF/src/pring_cycle/run_health.py:257)**：最终计划形成前中断，函数回退读取初始需求；初始需求使用 `status="local_complete"`，这里却只判断 `complete`，导致已持有的期也被归为 `flow_stopped`，抬高未完成数。规则：规格 §8，已持有与流程终止须按记录区分。

3. **P2｜[web.py:615](/D:/cursor/datasourceRF/src/pring_cycle/web.py:615)**：轮询若落在运行标记完成、健康摘要尚未写入的间隙，会缓存“无摘要”页面。摘要随后写入不改变当前指纹，后续轮询持续返回 `no_update`，新摘要不能自动出现。规则：ADR-0008、规格 §8/11，运行读模型独立更新并可被轮询观察。

4. **P2｜[web.py:633](/D:/cursor/datasourceRF/src/pring_cycle/web.py:633)**：从历史投影进入数据链路且未指定 `run` 时，默认取最新运行；若后来存在失败运行或报告任务，显示的取数流向便属于另一运行。规则：规格 §9 明确要求默认选择该投影的产出运行。
