Status: needs-triage
Category: task
Type: task

# 08：上一确认阶段回溯的成本与测试缺口

## 现象

票 02：每次运行满足条件都会重新回溯（最多 15 次核心请求＋5 次日历请求，无缓存）；限额拦截后未实际发出的请求，计数分支无单独用例；三核心已持有首日不一致时会多请求一段重叠区间（现行不会出现）。票 08：根因的窗口测试直接调用构建函数、未走单日汇总接缝；“核心自身声明”用例需替换私有函数 `_evidence_status`。

另：票 02 的回溯除最多 15 次核心区间请求外，每年还有 1 次 `trade_cal` 日历请求（最多 5 次），用于按上交所日历数清 139 个交易日的预热；规格（`spec.md` 用户故事 11、Implementation Decisions“上一确认阶段回溯”）只写了“每年每个核心一次、最多 15 次”。分流时决定补进规格还是改实现。

## 来源

[票 02](../model-rules-validation-20261011/issues/02-last-confirmed-stage-backfill.md)、[票 08](../model-rules-validation-20261011/issues/08-correct-core-only-when-day-context-left-retention.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
