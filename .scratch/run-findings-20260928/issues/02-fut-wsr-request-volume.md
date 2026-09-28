Status: done
Category: bug
Type: task

# 02 — 按品种逐日取 `fut_wsr` 请求量过大，缺日

## 原始发现

- 20260926 票 01 改成按品种单独取以后，6 个 TuShare 品种在 120 日窗口里逐日请求，约 720 次。
- 本轮 `fut_wsr` 失败 62 张：20 张是时钟问题（票 01），**42 张没有收到应答**（`received_at` 为空，没有原因码），分布在 6 个品种和各个日期上。疑似触发 TuShare 限频。
- 结果：CU 持有 110/120 天，PP、RB、RU、SC、SP 各 119/120 天（7/21 五个品种都缺）。20260926 票 01 的最后一条验收因此未达成。

## 待决定

- 先确认 42 次没有应答的原因（限频、超时还是别的），并让失败回执记下原因码。
- 取数单位：继续按品种逐日取，还是按日取整族、入库时再按品种隔离（请求数降到约 120 次）。

## Comments

> *本段由 AI 在分流时生成。*

### 调查结论（2026-09-28，[Codex 报告](../research/codex-fut-wsr-failures.md)，关键数据已人工核对）

- **撤回“限频”的判断。** 42 张没有收件时间的失败，根因也是时钟回拨：补缺中的 39 张，账本里的完成时间全都早于开始时间（−5.7～−7.8 秒，已核对）；另 3 张直接刷新失败，`retrieval_attempt` 明确记为 `acquisition_time_invalid`。`_receive()` 先查时间再写 `received_at`，所以时钟一回拨，就留下“没收到应答”的假象（`acquisition.py:326`、`acquisition.py:411`）。
- **原因码为什么是空的：** `fail_validation()` 只在状态已是 `received` 时才保存原因；状态还是 `started` 时只存异常类名，异常消息丢了（`acquisition.py:285`）。票 08 郑商所 CF 失败没有原因码，是同一个毛病。
- TuShare 非零业务码一律改写成 `tushare_source_failed`，`code`/`msg` 没有结构化保留（`tushare_context.py:146`、`:891`）；补缺账本还把它归为语义失败，不会重试（`retrieval_ledger.py:843`）。
- **请求量：** 本轮 752 次 = 直接刷新 38 次（按品种、31 天分块）+ 补缺 714 次。补缺对每个不完整的日期逐一请求全部 6 个品种，不看缺的是哪个品种（`targeted_context.py:65`）。本轮 CU 缺 119 天，于是 119 天 × 6 个品种都重取了一遍，RB、RU、SC 已经持有的数据也被重复请求。
- **最终缺日的原因：** CU 的 10 天里，3 天是收件后报 `acquisition_time_invalid`，5 天是没有收件时间的时钟失败，1 天（9/07）是入库时报 `acquisition_availability_time_invalid`，都与时钟有关；另外 7/21 这一天 CU、RB、RU、SC、SP 都缺，PP 缺 9/09（不是之前写的 7/21），这两处都是 TuShare 应答 `code=0` 但没有数据，属于上游本身缺数据。

### 决定（2026-09-28，用户确认）

- 改动范围：补诊断，并且补缺时只请求缺失的品种。
- 7/21（CU、RB、RU、SC、SP）和 PP 9/09 是 TuShare 上游本身没有数据，接受为透明缺口，不另找来源。
- 票 08（郑商所 CF 失败没有原因码）是同一个毛病，并入本票。

## Agent Brief

**Category:** bug
**Summary:** 失败回执无论在哪个阶段失败都记下原因；补缺仓单只向 TuShare 请求当天缺失的品种

**Current behavior:**
- `AcquisitionRepository.fail_validation()` 只在回执状态已是 `received` 时写 `rejection_reason`。请求还在 `started` 阶段就失败的（时间校验、网络、请求前检查），只留下异常类名，原因丢失（`acquisition.py:285`）。本轮 42 张 `fut_wsr` 和 6 张郑商所 CF 失败回执都因此没有原因码，被误判为“没收到应答”。
- TuShare 返回非零 `code` 时一律报 `tushare_source_failed`，不带业务码，看不出是权限不足还是限频（`tushare_context.py:894`）。
- 补缺某一天的仓单时，对 6 个 TuShare 品种全部重新请求，不看这一天缺的是哪个品种（`targeted_context.py:65`）。本轮 CU 缺 119 天，补缺就发了 119 × 6 = 714 次请求。

**Desired behavior:**
- 任何失败回执都在 `rejection_reason` 里留下原因（异常消息，截断 300 字）。`structure_check` 的语义不变：只有已收到应答、又被结构检查拒绝的才记 `rejected`（或 `skipped`）；`started` 阶段失败的仍为空，所以缺口清单的分类不受影响。
- TuShare 非零业务码：原因码带上业务码，形如 `tushare_source_failed:2002`；`40203` 记为 `tushare_rate_limited`（与 `tushare_news` 的现有叫法一致）。异常类型仍是 `TushareSourceError`。
- 补缺某一天的仓单时，只对该日输入选择里缺失（`symbol_missing`）或冲突（`delivery_conflicted`）的 TuShare 品种发请求。已持有的品种不再请求。只缺 TA 或 CF 时不请求 TuShare（郑商所那条路径照旧）。看不出缺哪个品种时，退回请求全部 6 个品种。

**Key interfaces:**
- `AcquisitionRepository.fail_validation(acquisition_id, error)`：`started` 状态也写 `rejection_reason`。
- `TushareContextAdapter` 内部的非零 `code` 处理：原因码带业务码，40203 单独命名。
- `targeted_context.retrieve_tushare_context`：仓单的补缺请求按该日 `select_retrieval_input(...).missing_members` 过滤品种。

**Acceptance criteria:**
- [x] 请求在收到应答前失败（例如取数抛出 `ValueError("fixture_reason")`）：回执为 `failed`，`rejection_reason` 为该原因，`structure_check` 为空。
- [x] 收到应答后被结构检查拒绝的回执，行为与现在相同（`structure_check='rejected'` 并带原因）。
- [x] TuShare 返回 `code=2002`：原因码为 `tushare_source_failed:2002`；返回 `code=40203`：原因码为 `tushare_rate_limited`。
- [x] 某天直接刷新只缺 CU，其余 5 个品种已持有：补缺这一天只以 `symbol=CU` 请求 `fut_wsr` 一次，其他品种不再请求。
- [x] 某天看不出缺哪个品种时，补缺仍请求全部 6 个品种（保持现有行为）；与能认出品种的缺口同时出现时也一样。
- [x] 现有的品种隔离、郑商所补缺用例全部通过。

**Out of scope:**
- 把相邻缺失日期合并成区间请求（补缺范围是按天组织的，要改检索计划的粒度）。
- 直接刷新的请求方式与 220 天回看。
- 时钟防护（票 01 已关闭）。
- 上游空数据日的补缺来源。

### 实施记录（2026-09-28）

> *本段由 AI 在实施时生成。*

- **原因码：** `AcquisitionRepository.fail_validation()` 无论回执停在哪个阶段都写 `rejection_reason`；`structure_check` 仍只在已收到应答时写，缺口清单按它分类，不受影响。
- **业务码：** TuShare 非零 `code` 记为 `tushare_source_failed:<code>`，`40203` 记为 `tushare_rate_limited`。融资融券复核用例的期望随之改为 `tushare_rate_limited`（复核用的是同一个解析）。检索账本仍把 `TushareSourceError` 归为语义失败，这是既有行为，这次没改。
- **补缺品种：** `targeted_context._warrant_symbols_to_refetch()` 读这一天的输入选择：缺口 `CN_FUTURES_WARRANTS:<类型>:<品种>` 中的 `symbol_missing`、`delivery_conflicted`、`warehouse_member_missing` 都按品种补取；只要有一条认不出的缺口，就请求全部 6 个品种。只缺 TA 或 CF 时不请求 TuShare，直接判断这一天是否已完整。
- **审查（Codex 两轴）：** 发现 1 项 P2 问题：最初只认前两种缺口，`warehouse_member_missing` 会被漏掉。已修复，并补了参数化测试。其余核查项（缺口清单、终态触发器、业务码的使用方、零请求时的后续流程）都没有问题。
- **测试：** 新增 `test_a_call_failing_before_its_answer_is_recorded_keeps_why`、`test_a_refused_call_says_which_code_refused_it`（2 例）、`test_a_gap_day_refetch_asks_only_for_the_symbols_still_missing`、`test_a_gap_day_missing_only_czce_symbols_asks_tushare_for_nothing`、`test_a_gap_day_refetch_asks_for_every_symbol_its_shortfall_names`（7 例）。第一轮受影响测试 115 个全过，用时 7 分 59 秒，超出 3 分钟目标，因为范围里有几个较重的集成文件；修复后复跑 95 个全过，用时 3 分 39 秒。


### 真实运行确认（2026-09-28 晚）

> *本段由 AI 在验收时生成。*

`run-67ad41fc9072b672e3bb`（目标日 9/28，代码 `d351c06`）：`fut_wsr` 共 54 次（6 个品种各 9 次），全部通过校验；上一轮是 714 次。本次运行 261 张回执中，没有一张失败回执缺少原因码。两条都已确认。
