# 02: 交易日历模块（纯重构）

**What to build:** 把交易日历（`CONTEXT.md`）的读、取、覆盖判断和运行期间日历槽集中到新模块 `src/pring_cycle/trading_calendar.py`，调用方只拿"目标交易日""证据窗口"这类领域结果。**只重构上交所日历，可观察行为不变**（下述两处删除除外，均经用户确认）。

**Blocked by:** 01（两票同改 `seed_core_history` 夹具，先 01 后 02）

**勿并行：** 05、09、15、16、17、18、19、20、21（同改：Worker 编排与取数；缺口清单与时效；核心就绪；完整运行规划；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 1 的访谈记录（2026-09-29）。起因是 `7f5a2bb`：同一份"认哪个口径"的知识漏在两处。 规格：[spec.md](../spec.md)「二、交易日历模块」。

## 现状（调用点）

- 读：`freshness.launch_calendar`（`freshness.py:628`，提交运行定目标日）、`full_run_requirements.required_calendar`（`full_run_requirements.py:29`，完整运行 120 日窗口）、`czce_warrants.window_trading_days`（`czce_warrants.py:259`，郑商所仓单窗口）——各自对 `acquisition_request` 写 SQL、各自判断口径、各自解析 normalized。
- 取：`core_history.py:91`（核心刷新）与 `freshness.py:662`（提交时临时取 30 天），都经 `TushareCoreAdapter.acquire_calendar`（`source_adapters.py:174`）。
- 值类型与运行期间日历槽：`TradingCalendar`（`freshness.py:214`）、`run_calendar_scope` / `current_calendar` / `use_run_calendar`（`freshness.py:677–731`）；使用方 `worker.py:218/381/839/1130/1990`、`full_retrieval.py:73/552`、`evidence.py:1668`、`search_evidence.py:682/819/873`。
- 调用入口：`cli.py:314`、`full_retrieval.py:358`、`worker.py:378/395/1749`。

## 已定决定

- **读和取都归日历模块**：写入用哪个解析器版本、读取认哪个，只在模块内出现一次。TuShare 作为适配器传入，测试用假适配器（测试现已替换 TuShare 网络请求，是真实的第二个适配器）。
- **降级由调用方写明**：模块如实回答知道哪些交易日、覆盖到哪、够不够所要的窗口；提交运行的工作日推定、完整运行的严格 120 日要求、郑商所窗口不完整时只取目标日，都留在各调用方显式表达。不在模块里做模式开关。
- **统一截止时间**：模块接受截止时间，默认当前时间；完整运行传入冻结截止时间（现 `required_calendar` 的 `validated_at <= as_of` 约束保留）。
- **删除日历来源声明路径**：`required_calendar` 先读 `CN_TRADE_CALENDAR` 来源声明的分支删除——生产从未写入（真实库 0 条），只有测试夹具写。交易日历只从回执读。目录登记里的 `CN_TRADE_CALENDAR`（`catalog.py:44/190`）不动，目录版本不可变。
- **日历修订按数据版本处理**：同一来源前后两份日历对同一天说法不同，取最新一份并把变化记入运行记录，不阻断。原"日历冲突即 `calendar_source_conflict` 不可用"依赖测试造的第二来源，随声明路径删除。
- **运行期间日历槽迁入本模块**，工作日推定行为不变。
- **删除死代码** `calendar_coverage`（`source_adapters.py:302`），全仓无调用方。
- 市场广度自己的 `is_open=1` 请求本票不动（见 03）；不预留"市场"参数（见 04）。

## 验收

- [ ] 新模块 `trading_calendar.py` 持有 `TradingCalendar`、日历读取、日历获取与运行期间日历槽；`freshness`、`full_run_requirements`、`czce_warrants`、`core_history` 不再对 `trade_cal` 回执写 SQL 或解析其 normalized。
- [ ] 按 TDD 在模块接口上覆盖：提交运行定目标日（`test_freshness_contract.py` 现有 3 例，含中秋 9/25）、`7f5a2bb` 的两条回归（广度回执不当日历、空广度回执不冒充覆盖）、郑商所窗口 2 例、完整运行窗口"缺核心日仍在窗口内"、新增"日历修订取最新一次"、截止时间之后的回执不被读到。
- [ ] 保留集成测试：`test_worker_calendar_gate.py`（缺日历停止发布）与一例完整运行正路径（`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`）。
- [ ] 删除 `test_conflicting_calendar_cannot_claim_complete_window`；造 `CN_TRADE_CALENDAR` 来源声明的夹具（`test_full_run_retrieval.py` 的 `seed_core_history`、`test_worker_execution.py`、`test_gap_list.py`）改为造核心日历回执（`seed_core_history` 以票 01 的批量写入为基础改）。被迁到模块接口的旧测试删除，不叠加。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 编排，另加跑完整目录正例与三核心反例，记录退出码与耗时。
- [ ] 在快速重构规格"唯一测试接缝"条的 2026-09-29 修订注记后补一句（措辞实施时与用户确认）：各模块接口（交易日历、可采用声明、获取结果、信用脉冲）上的直接测试属于模块自身的测试，不算新增正式测试接缝；正式接缝仍为完整运行与单日汇总（ADR-0034）。
- [ ] 代码审查（规格、标准两轴）无阻断。
