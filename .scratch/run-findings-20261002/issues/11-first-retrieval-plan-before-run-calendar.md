Status: done
Category: bug
Type: task

# 11 — 完整补缺首次规划在装入运行日历之前

## 原始发现（票 01 审查，Codex 只读）

- `full_retrieval.py` 先调用 `_plan` 生成首次计划，之后才 `use_run_calendar(judging_calendar(...))`；`_plan` 内依赖 `current_calendar()` 推算最新发布期，此时仍为工作日日历。
- 内存对照：9/28 判定融资余额、人民币收盘价时，工作日日历推算最新发布期为休市的 9/25，完整日历为 9/24。
- 既有行为（HEAD 前即如此），票 01 只修了运行内时效与发布状态的日历。

## 待决定

- 是否在首次规划前装入判定日日历（需先有窗口日历，或用 `SseCalendar.around`）。

## 验收

- [x] 替身：判定 09-28 时，融资余额、人民币 16:30 收盘价的首次计划最新发布期都是 09-24，初始计划不出现休市的 09-25
- [x] 正确期次未持有时进入正常补缺；已持有时不新增检索
- [x] 首次、恢复与最终规划使用同一判定日历口径（同票 12）

## 主要模块

`src/pring_cycle/full_retrieval.py`（取得窗口后、推算期次前装入判定日历）、`trading_calendar.py`、Worker 调用接缝。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`，按 `/diagnosing-bugs` 先拿到稳定变红的用例。
- 仍在：`full_retrieval.py:91` 首次 `_plan` 早于 `:102` 的 `use_run_calendar(judging_calendar(...))`；`worker.py:228` 建空日历槽，`trading_calendar.py:460` 在槽未填时返回工作日日历。`2a3935f`（票 12）只改了判定日历保留休市日的方式，没动调用顺序。
- 内存实测：2026-09-28 23:59:59（北京）判定融资余额、人民币 16:30 收盘价，工作日日历给 09-25，上交所日历给 09-24。
- 运行库实测：目标日 09-28 的六次运行，收盘价初始计划都是 09-25／`model_input_missing`，最终都是 09-24／`local_complete`；错误期次只有 6 条 `release_gate/not_attempted`，没有多余外部检索。读码推断的真正风险：正确日历装入后门禁拦下 09-25，`full_retrieval.py:836` 最终重算计划但不重跑检索循环，若 09-24 未持有就会留下本可补取的缺口。

### 2026-10-10 实施

**复现（/diagnosing-bugs）**：替身日历（3-02..10-30 工作日，去掉 09-25 与国庆），目标日 09-28、显式截止北京时间 09-28 23:59:59，当前生效模型。修复前首次计划：人民币 16:30 收盘价只计划 09-25（`model_input_missing`）；融资余额（`CN_MARGIN_BALANCE_SSE_SZSE`）整窗计划不含 09-25，但最新发布期按工作日推为 09-25，于是 09-24 的 scope 被标 `earlier_session_not_searched`，不会检索。这就是分流记录推断的风险：门禁会把正确的最新期当成更早的交易日跳过。变红命令：`tools/check.py quick tests/integration/test_full_run_retrieval.py::test_the_first_plan_counts_the_sessions_of_the_sse_calendar`（两参数都红在期次断言上）。根因与分流记录一致：`_plan` 在装入判定日历之前就推算期次。

**改动**（`src/pring_cycle/full_retrieval.py`）：
- 新增 `FullRunRetrieval._use_judging_calendar(run, window)`，用窗口与 `run.system_as_of` 装入 `judging_calendar`；窗口为空时不装入，与原逻辑相同。
- `_plan` 在 `required_calendar` 取得窗口后、`_period` 推算期次前调用它。首次计划、`recover_legacy_plan`、`evaluate` 的最终计划都经 `_plan`，因此三者使用同一判定日历口径（冻结截止后按新的 `system_as_of` 延伸，与 `worker.py` 评估后的装入一致）。
- `retrieve` 中原来的装入改为调用同一方法，只用于已存首次计划的恢复路径。
- 外盘指标仍由 `market_calendar` 按各自市场判定：VIX、美债 09-25 照常计划。

**测试**（`tests/integration/test_full_run_retrieval.py`，先红后绿）：
1. `test_the_first_plan_counts_the_sessions_of_the_sse_calendar[held=False/True]`（Worker 全流程）：首次计划中收盘价为 09-24（未持有时 `model_input_missing`，已持有时 `local_complete`）；融资余额不含 09-25，09-24 为 `released`、09-23 为 `earlier_session_not_searched`；VIX 仍含 09-25。未持有时 09-24 的融资与收盘价都有非门禁检索尝试；已持有时收盘价无 scope、无检索。最终计划的收盘价同为 09-24。
2. `test_a_plan_made_afresh_judges_on_the_sse_calendar_too`：在空日历槽中直接调用 `_plan`（恢复与评估入口的情形），装入后 09-25 为非交易日，收盘价为 09-24。修复前红。

**验证**：
- 受影响测试（直接涉及补缺计划、运行日历或节假日的 28 个文件，不含重型）：540 passed，46:53。远超 3 分钟目标，最慢单例为 `test_daily_reacquisition`、`test_lookback_declaration` 等全流程用例（65–92 秒）。
- 采纳审查意见后（只改注释）重装，复跑两个新测试与两例冒烟：5 passed，2:23。
- 重型两例（`flock`）`test_worker_registered_catalog.py`＋`test_core_carry_forward.py`：4 passed，9:10。
- `ruff check`、`ruff format --check` 通过（两个改动文件）；`mypy src/pring_cycle/full_retrieval.py` 通过。测试文件原有 34 个 mypy 错误，改动前后数量相同，新增代码没有引入。

**审查（Codex，各一轮）**：标准轴、规格轴均为"阻断：无"。
- 采纳：`_plan` 处注释原写"每个期次按上交所日历"，范围过宽，已改为国内期次按上交所日历、外盘按各自市场。
- 不采纳，补融资余额"已持有"分支：融资声明入库要经登记来源契约核对（`registered_margin_source_identity_mismatch`），替身需要构造真实的 TuShare margin 回执，成本高。"选值完整则不生成 scope"对各指标是同一段代码（`full_retrieval.py` 的 `selection.complete` 分支），收盘价已覆盖。
- 不采纳，补真实 `recover_legacy_plan` 与冻结截止跨假期的 `evaluate` 用例：两者都只经 `_plan` 取日历，用例 2 已直接覆盖空槽入口；既有 `test_upgrade_resumes_verified_evidence_at_original_cutoff` 在受影响测试中通过。

**已知边界**：`daily_window` 为空（日历不可用）时仍不装入，期次按工作日推算。这条分支最终以 `p0_required_calendar_unavailable` 停止，属既有行为，不在本票范围。
