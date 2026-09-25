Status: ready-for-agent
Type: task

# 03 — 回执记录入库结果，Worker 保留拒收原因码

规格“取数回执”一节（用户故事 2、4）。

- 迁移 0031：`acquisition_request` 新增入库结果列（结果与原因），终态触发器只放行这两列的一次写入；已有列语义不变。
- 请求校验通过后入库失败，回执写入 `ingest_rejected` 与原因码。
- Worker 家族失败的 `retrieval_attempt` 记录保存异常原因码（不只是 `ValueError`）。

## Comments
