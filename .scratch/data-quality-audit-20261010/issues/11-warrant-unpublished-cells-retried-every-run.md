Status: needs-triage
Category: bug
Type: task

# 11：仓单上游未发布的格每次运行都单日补取，被负缓存拦截后计为失败回执（票 05 体检发现）

## 现象

期货仓单 `CN_FUTURES_WARRANTS` 有 6 格已由体检判为上游未发布：CU、RB、RU、SC、SP 的 2026-07-21，PP 的 2026-09-09。依据是最近一次应答的 `fut_wsr` 原件里，该日该品种为 0 行。

尽管如此，每次完整运行的 `gap_retrieval` 都会对这 6 格各发一次单日 `fut_wsr` 补取：

- 本运行 `run-674411db5f492d4b607e` 的 6 条失败回执全部属于这种情况，`error_type=RetrievalBudgetBlocked`、`rejection_reason=negative_cache_active`；
- 此前几次运行也一样：`run-a04dcc78…` 有 5 条，`run-a8675946…` 有 6 条；
- 没被负缓存拦住的时候，这些补取会真的发出去。09-28 至 10-10 之间，07-21、09-09 两天的单日补取取得应答（`validated`）的回执共 99 条；自 10-08 22:34Z 起，这些回执都是 `source_record_count=0`。

## 证据

```sql
SELECT f.run_id, COUNT(*) FROM acquisition_request a
JOIN full_run_acquisition f USING (acquisition_id)
WHERE a.api_name = 'fut_wsr' AND a.rejection_reason = 'negative_cache_active'
GROUP BY f.run_id;
-- run-674411db… 6，run-a04dcc78… 5，run-a8675946… 6

SELECT acquisition_id, parameters_json, state, source_record_count, started_at
FROM acquisition_request
WHERE api_name = 'fut_wsr' AND state = 'validated'
  AND json_extract(parameters_json, '$.start_date') = json_extract(parameters_json, '$.end_date')
  AND json_extract(parameters_json, '$.start_date') IN ('20260721', '20260909')
ORDER BY started_at;  -- 99 条
```

- [report.md](../report.md) 第 460–465 行：第二层·缺失明细的“本运行回执”列为“failed（negative_cache_active） 5／1”。

## 受影响面

- 每次运行多出约 6 次 TuShare 调用，或 6 条失败回执，抬高了回执失败计数，干扰按失败数判断运行健康的做法（票 30 验收时就把这 5 条列为“常规失败”）。
- 这 6 格在计划中一直是 `model_input_missing`，第二层每次都计为真缺失。
- 待分流：
  - 上游确认 0 行之后，是否应记为“上游未发布”并停止补取？
  - 负缓存拦截是否应该计为失败？
  - 仓单的缺格是否可以按沿用处理？
