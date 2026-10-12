Status: ready-for-agent
Category: task
Type: task

# 08：上一确认阶段回溯的成本与测试缺口

## 现象

票 02：每次运行满足条件都会重新回溯（最多 15 次核心请求＋5 次日历请求，无缓存）；限额拦截后未实际发出的请求，计数分支无单独用例；三核心已持有首日不一致时会多请求一段重叠区间（现行不会出现）。票 08：根因的窗口测试直接调用构建函数、未走单日汇总接缝；“核心自身声明”用例需替换私有函数 `_evidence_status`。

另：票 02 的回溯除最多 15 次核心区间请求外，每年还有 1 次 `trade_cal` 日历请求（最多 5 次），用于按上交所日历数清 139 个交易日的预热；规格（`spec.md` 用户故事 11、Implementation Decisions“上一确认阶段回溯”）只写了“每年每个核心一次、最多 15 次”。分流时决定补进规格还是改实现。

## 来源

[票 02](../model-rules-validation-20261011/issues/02-last-confirmed-stage-backfill.md)、[票 08](../model-rules-validation-20261011/issues/08-correct-core-only-when-day-context-left-retention.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

- **回溯结果缓存：wontfix**（用户 2026-10-12 决定）。理由：实测一次回溯 4 次请求、约 7 秒；缓存键含窗口首日，而窗口每个交易日都会前移，只有同窗口重跑才命中；还与 ADR-0040“窗口前核心价格每次运行重新取得”冲突。
- **测试缺口：补测试**（不改生产行为）：
  1. 回溯中 `TushareCallNotAttempted`（限额拦截、未实际发出）时的核心／日历计数分支（`stage_lookback.py:137`）单独用例；
  2. 三核心已持有首日不一致时以最晚首日为公共起点、重取重叠区间、合并时已持有价格优先（`stage_lookback.py:100`、`:127`、`:184`）的用例；
  3. 票 08 根因（贷款派生取窗口外期）的回归改走单日汇总接缝，不只直接调用 `build_context_projection()`（`tests/integration/test_context_projection.py:1946-2004`）；
  4. “核心自身声明移出仍不算上下文缺失”的用例（`tests/integration/test_core_only_correction.py:320-342`）改为用真实数据构造状态，不再替换私有 `_evidence_status`。
- **规格补写**（不问）：`.scratch/model-rules-validation-20261011/spec.md` 用户故事 11（`:35`）与 Implementation Decisions“上一确认阶段回溯”（`:56`）补为“三核心最多 15 次区间请求，另有每年 1 次 `trade_cal` 日历请求（最多 5 次），合计最多 20 次；串行，找到或失败即停”；ADR-0040 的“外部调用”一条同步补写日历请求。

## 主要模块

`tests/integration/test_core_stage_lookback.py`、`tests/integration/test_context_projection.py`、`tests/integration/test_core_only_correction.py`；`spec.md`、ADR-0040。生产代码原则上不改；若某个用例必须增加一个接缝才能写，限于测试所需的最小改动并在票面说明。

## 验收

- [ ] 四个测试缺口各有用例，并都在当前 main 上通过（若有用例暴露真缺陷：停下记录，转为 bug 处理）
- [ ] “核心自身声明”用例不再引用 `_evidence_status`
- [ ] 规格与 ADR-0040 补写日历请求
- [ ] 改动的测试文件通过 ruff、mypy；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-01-08.md](../triage-codex-01-08.md) 第 6–9 条。

- 成本（实测）：第一次真实运行回溯 1 年，`trade_cal` 1 次、`index_daily` 2 次、`fut_index_daily` 1 次，请求耗时合计约 7.0 秒；第二次运行未触发（08-03 已有正式阶段）。上限为每次回溯 15 次核心＋5 次日历（`stage_lookback.py:36`、`:105-122`），无跨运行缓存。
- 测试缺口四条都属实（`file:line` 见“做法”）；其中“核心自身声明”用例**已经**替换私有 `_evidence_status`，缺口是依赖私有替身，不是“尚需替换”。
- 规格：`spec.md:35` 写了“最多 15 次”，`:56` 只写“三核心各请求一年区间、最多 5 年”；两处都没提日历请求。
- 决定：缓存 wontfix（用户 2026-10-12 选择，偏离预设的 `ready-for-agent`，理由见“做法”）；测试缺口与规格补写 `ready-for-agent`，线 A 第二票（排在 01 之后）。主 agent 已复核 ADR-0040 `:17`。
