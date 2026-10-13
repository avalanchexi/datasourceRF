Status: done
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

- [x] 四个测试缺口各有用例，并都在当前 main 上通过（若有用例暴露真缺陷：停下记录，转为 bug 处理）
- [x] “核心自身声明”用例不再引用 `_evidence_status`
- [x] 规格与 ADR-0040 补写日历请求
- [x] 改动的测试文件通过 ruff、mypy；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-01-08.md](../triage-codex-01-08.md) 第 6–9 条。

- 成本（实测）：第一次真实运行回溯 1 年，`trade_cal` 1 次、`index_daily` 2 次、`fut_index_daily` 1 次，请求耗时合计约 7.0 秒；第二次运行未触发（08-03 已有正式阶段）。上限为每次回溯 15 次核心＋5 次日历（`stage_lookback.py:36`、`:105-122`），无跨运行缓存。
- 测试缺口四条都属实（`file:line` 见“做法”）；其中“核心自身声明”用例**已经**替换私有 `_evidence_status`，缺口是依赖私有替身，不是“尚需替换”。
- 规格：`spec.md:35` 写了“最多 15 次”，`:56` 只写“三核心各请求一年区间、最多 5 年”；两处都没提日历请求。
- 决定：缓存 wontfix（用户 2026-10-12 选择，偏离预设的 `ready-for-agent`，理由见“做法”）；测试缺口与规格补写 `ready-for-agent`，线 A 第二票（排在 01 之后）。主 agent 已复核 ADR-0040 `:17`。

### 2026-10-12 实施进展（fub-08）

- 17:57 领取；HEAD 含 f7b1129，dev-venv 已重装。用例 3 完成：`test_context_projection.py` 贷款窗口用例改走单日汇总接缝（目标日 `summarize_target`、已汇总日 `backfill`），2 passed；在 job 临时目录的 src 副本里去掉 `in_window` 检查复现根因 → 两例皆红（目标日抛 `projection_context_evidence_outside_visible_window`，已汇总日返回 `FailedDay(ValueError)`），证明接缝用例能抓住根因。
- 17:59 用例 4 完成：`test_core_only_correction.py` 的“核心自身声明”用例不再替换 `_evidence_status`，改为把运行时钟定在目标日次日 09:00（北京），商品核心行按真实新鲜度判为 current，其声明随之进入模型输入；1 passed（15 秒）。src 副本里让判据把核心行引用也计入 → 红，证明用例仍有效。
- 09:25 用例 1 完成：`test_core_stage_lookback.py::test_a_lookback_request_held_back_for_the_day_is_not_counted`（日历、核心两例）。完整运行接缝上用 `INTERFACE_GRANTS` 把 `trade_cal`／`fut_index_daily` 的日额度设为只够运行自身调用，回溯的下一次请求被限额拦截；断言计数 (0,0)／(2,1)、`failure`、源端实际收到的请求与回执数。2 passed（38 秒）；src 副本去掉 `:137` 计数回退 → 两例皆红（(0,1)、(3,1)）。注意：期间主分支合入了票 02（8cc4ada），dev-venv 已重装。
- 09:26 用例 2 完成：`test_core_stage_lookback.py::test_cores_held_from_different_days_look_back_from_the_latest_and_keep_their_own`。直接调用 `look_back_for_stage`，用 `TushareCoreAdapter` 的公开 `transport` 参数供应答（现行运行不会出现三核心首日不一致，完整运行接缝无法构造）；股票核心多持有 150 个交易日且第 20 日起转跌，源端应答为一路上涨。断言三核心请求都止于最晚首日前一日（股票重取重叠区间）、阶段日 2025-05-19（按已持有收盘价）。src 副本三处变异各自变红：合并改为源端优先 → 2025-08-25；公共起点改为最早首日 → 请求不符。
- 09:27 规格 `spec.md` 用户故事 11 与“上一确认阶段回溯”、ADR-0040“外部调用”与“后果”已补写日历请求；ruff check／format --check 通过。受影响测试开跑（`/home/tywin/.claude/jobs/cd7879cd/tmp/fub08-affected.log`）。
- 09:30 Codex 两轴第一轮已发出（`/home/tywin/.claude/jobs/cd7879cd/tmp/fub08r/review-spec-1.md`、`review-std-1.md`），与受影响测试并行。
- 09:34 受影响测试 61 passed（4 分 58 秒，`/home/tywin/.claude/jobs/cd7879cd/tmp/fub08-affected.log`）。第一轮审查：规格轴阻断无；标准轴阻断 1 项（日额度用例的 `runtime_clock` 以当前时刻起算，跨北京零点时限额不触发）→ 改用 `install_runtime_clock` 固定在 2026-08-04 10:00（北京），2 passed（34 秒），变异复核仍红。
- 09:45 冒烟两例 2 passed（35 秒）；标准轴定向复审（`review-std-2.md`）确认修复成立，阻断：无。

### 2026-10-12 实施

（实际完成于 2026-10-13 上午；票面日期沿用本批。）

**改了什么**（只改测试与文档，`src/` 未改，也未新增接缝）

- 缺口 1：`tests/integration/test_core_stage_lookback.py::test_a_lookback_request_held_back_for_the_day_is_not_counted`，分日历、核心两例，走完整运行接缝。用 `tushare_quota.INTERFACE_GRANTS` 把 `trade_cal`（日额度 3，保留 90% 即 2）或 `fut_index_daily`（日额度 2，即 1）的额度设为刚够运行自身的调用；回溯的下一次请求被限额拦截，不会发出。断言计数分别为 (0,0)、(2,1)，`failure` 为 `TushareCallNotAttempted:tushare_daily_quota_exhausted`；源端实际收到的请求、回溯阶段的回执数都与计数一致；三个页面都显示“回溯失败”。时钟用 `install_runtime_clock` 固定在 2026-08-04 10:00（北京），避免跨零点。
- 缺口 2：`test_cores_held_from_different_days_look_back_from_the_latest_and_keep_their_own`。现行运行不会出现三核心首日不一致，所以直接调用 `look_back_for_stage`，通过 `TushareCoreAdapter` 的公开 `transport` 参数供应答。构造：股票核心多持有 150 个交易日，第 20 日起转跌；源端应答为一路上涨。断言：三核心请求都止于最晚首日前一日，股票的重叠区间被重新请求；阶段日 2025-05-19 按已持有收盘价得出（若源端应答优先，会是 2025-08-25）。
- 缺口 3：`test_context_projection.py::test_a_loan_change_whose_months_ended_before_the_window_is_not_shown`，改走单日汇总接缝 `DaySummaries`：目标日用 `summarize_target`，已汇总日用 `backfill`。模型为登记的 v0002 清单，`CN_LOAN_STRUCTURE` 设为认证。断言已发布投影的贷款只有缺口行、已汇总日没有失败、不落派生观测。原先直接调用 `build_context_projection` 的写法和私有导入 `_validate_visible_context_window` 一并去掉，发布校验由接缝自身执行。
- 缺口 4：`test_core_only_correction.py::test_a_core_s_own_claims_gone_are_no_context_detail_left_retention` 不再替换 `_evidence_status`。改为把运行时钟定在目标日次日 09:00（北京），商品核心行按真实新鲜度判为 current；`Runtime` 所在模块的 `datetime` 也换到同一时间轴，因为 `Runtime.run` 用它取 `system_as_of`。
- 文档：`spec.md` 用户故事 11 与“上一确认阶段回溯”、ADR-0040“外部调用”与“后果”补写每年 1 次 `trade_cal`（最多 5 次），合计最多 20 次，串行，找到或失败即停。

**有效性核验**：在 job 临时目录的 `src` 副本上逐项变异（`PYTHONPATH` 指向副本），对应用例均变红。

- 去掉 `stage_lookback.py:137` 的计数回退 → (0,1)、(3,1)；
- 合并改为源端优先 → 阶段日变为 2025-08-25；
- 公共起点改为最早首日 → 请求不符；
- 去掉贷款派生的窗口检查 → 目标日抛 `projection_context_evidence_outside_visible_window`，已汇总日返回 `FailedDay(ValueError)`；
- 判据把核心行自身的引用也计入 → `context_details_held` 为假。

本票没有暴露生产缺陷。

**测试与耗时**

- 受影响测试：三个文件共 61 passed（4 分 58 秒），之后修复的单例复跑 2 passed（34 秒）；
- 冒烟两例：2 passed（35 秒）；
- 重型两例未跑：本票只改测试，不涉及 Worker 编排、指标目录或来源；
- ruff check、format --check（三个测试文件）通过；
- mypy：配置范围 `pring_cycle` 共 132 个文件，无问题。测试文件不在配置范围内，以 `--explicit-package-bases` 单独检查，改动行无错误；其余错误都在既有行。

**审查**

- 第一轮：规格轴阻断无。标准轴阻断 1 项：日额度用例随当前时刻起算，可能跨过北京零点。已改为固定时钟，定向复审确认，阻断无。
- 不采纳的非阻断意见：日额度与运行自身调用次数耦合。理由：覆盖真实限额链路有价值，耦合已在参数注释写明，运行流程调整时用例会明确变红，不会静默误判。

**遗留**：无。

### 2026-10-13 附带补写（主 agent 追加，票 01 遗留）

- 09:47 按主 agent 要求补写 `day_summary.py` 模块文档（票 01 的级联说明），只改文档字符串；已重装 dev-venv，ruff、format、mypy（132 文件）通过，冒烟两例 2 passed（35 秒）。在 abc96b7 之后单独提交。
