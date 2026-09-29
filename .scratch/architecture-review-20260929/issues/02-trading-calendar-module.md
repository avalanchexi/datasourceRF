# 02: 交易日历模块（纯重构）

**What to build:** 把交易日历（`CONTEXT.md`）的读、取、覆盖判断和运行期间日历槽集中到新模块 `src/pring_cycle/trading_calendar.py`，调用方只拿"目标交易日""证据窗口"这类领域结果。**只重构上交所日历，可观察行为不变**（下述两处删除除外，均经用户确认）。

**Blocked by:** 01（两票同改 `seed_core_history` 夹具，先 01 后 02）

**勿并行：** 05、09、15、16、17、18、19、20、21（同改：Worker 编排与取数；缺口清单与时效；核心就绪；完整运行规划；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

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

- [x] 新模块 `trading_calendar.py` 持有 `TradingCalendar`、日历读取、日历获取与运行期间日历槽；`freshness`、`full_run_requirements`、`czce_warrants`、`core_history` 不再对 `trade_cal` 回执写 SQL 或解析其 normalized。
- [x] 按 TDD 在模块接口上覆盖：提交运行定目标日（`test_freshness_contract.py` 现有 3 例，含中秋 9/25）、`7f5a2bb` 的两条回归（广度回执不当日历、空广度回执不冒充覆盖）、郑商所窗口 2 例、完整运行窗口"缺核心日仍在窗口内"、新增"日历修订取最新一次"、截止时间之后的回执不被读到。
- [x] 保留集成测试：`test_worker_calendar_gate.py`（缺日历停止发布）与一例完整运行正路径（`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`）。
- [x] 删除 `test_conflicting_calendar_cannot_claim_complete_window`；造 `CN_TRADE_CALENDAR` 来源声明的夹具（`test_full_run_retrieval.py` 的 `seed_core_history`、`test_worker_execution.py`、`test_gap_list.py`）改为造核心日历回执（`seed_core_history` 以票 01 的批量写入为基础改）。被迁到模块接口的旧测试删除，不叠加。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 编排，另加跑完整目录正例与三核心反例，记录退出码与耗时。
- [x] 在快速重构规格"唯一测试接缝"条的 2026-09-29 修订注记后补一句（措辞实施时与用户确认）：各模块接口（交易日历、可采用声明、获取结果、信用脉冲）上的直接测试属于模块自身的测试，不算新增正式测试接缝；正式接缝仍为完整运行与单日汇总（ADR-0034）。
- [x] 代码审查（规格、标准两轴）无阻断。

## Comments

**2026-09-29 实施记录**

- **模块**：`src/pring_cycle/trading_calendar.py` 持有 `TradingCalendar`、`SseCalendar`（读，按截止时间，默认取回执同一时钟 `acquisition.utc_now()`）、`acquire_sse_calendar`（取，适配器传入）、运行期间日历槽。`freshness.launch_calendar`、`full_run_requirements.required_calendar`、`czce_warrants.window_trading_days`、`core_history` 都改走模块，不再写 `trade_cal` SQL 或解析 normalized；`CoreHistoryAdapter` 改为继承模块的 `CalendarAdapter`。
- **发布日程槽**：原来和日历共用一个槽，日历槽迁走后，发布日程在 `freshness` 里单独开 `release_schedule_scope()`，Worker 同时打开两个作用域，生命周期不变。
- **测试**：模块接口上 12 例（`tests/integration/test_trading_calendar.py`）：节假日、区间止于休市日（中秋）、未覆盖日、广度回执不算日历（2 参数）、郑商所窗口两例、窗口不依赖价格、修订取最新、截止之后的回执不读、不可读回执、被更新回执取代的旧坏回执不再阻断。删除已迁移的旧测试：`test_freshness_contract` 两例（节假日、广度）、`test_czce_warrant_refresh` 两例、`test_full_run_retrieval` 两例（缺核心日仍在窗口、日历冲突）。`test_freshness_contract` 的中秋用例保留在 CLI 入口，它测的是"启动时取一次、之后读回"的调用方编排，模块测试只测区间语义。
- **夹具**：`seed_core_history`、`seed_independent_calendar` 改为经 `TushareCoreAdapter`（假 transport）写核心日历回执，时间记在首个交易日 UTC 零点。回执没有归属时会被留存删除（生产上每次运行都重新取日历、回执挂在本次运行下），所以两个跑两次完整运行的用例（`test_candidate_duration`、`test_daily_reacquisition`）在第二次运行前再写一次日历。`seed_core_history` 的 `omit_stock_on` 参数随删掉的用例一并删除。
- **验证**（源码直接导入 `PYTHONPATH=src`；安装副本落后于源码，`check.py quick` 会拒绝，按记忆不擅自 `uv sync`）：
  - 受影响 21 个文件：第一轮 141 过、1 败（`test_candidate_duration`，原因见上"夹具"）；修夹具后重跑其余 11 个文件 83 过、1 败（`test_daily_reacquisition`，同因）；修后单跑通过。
  - 收尾冒烟两例 49.5 秒通过；完整目录正例 `test_worker_registered_catalog.py` 89.6 秒通过；三核心反例 `test_core_carry_forward.py` 3 例 67.0 秒通过。
  - ruff、mypy（改动模块）通过。
- **审查**（Codex 只读，规格、标准两轴）：
  - 已修：不可读回执原先"截止前任一不可读即抛"，会让一份已被取代的旧坏回执永久阻断完整运行；改为窗口可用时只看比窗口所用回执更新的不可读回执，窗口不可用时有不可读即抛（与旧的"从新到旧遍历、遇到即抛"一致）。日期解析移入捕获范围。
  - 其余无阻断。

**需要用户决定的行为差异（按 goal 只记录，未改）**

1. **完整运行窗口合并相邻回执。** 旧：只认"单份回执就含 120 个交易日且止于目标日"。新：相邻回执覆盖的交易日合并计算（郑商所窗口原本就是合并口径）。影响：两份各不足 120 日、合起来足够的回执，旧不可用、新可用。首次初始化按自然年分块取日历（`core_history.py` 的 `ranges`），年初的完整运行窗口本来就跨两份回执，所以这一条更接近生产实际；但票面没写。若要恢复旧口径，可在 `required_calendar` 要求窗口只由一份回执陈述。
2. **读取需要回执参数里的起止日期。** 旧 `required_calendar` 只看 normalized 日期列表；新模块用 `start_date`/`end_date` 判断覆盖范围。核心适配器写的回执都带这两个参数，生产上无差别。
3. **`launch_calendar` 命中条件。** 旧：取最新一份"结束日不早于启动日"的回执。新：启动日须落在已覆盖的连续区间内（可跨回执合并）。只持有未来区间回执时，新版会发起一次取数，旧版会用那份回执。
4. **修订只在窗口可用时记入运行记录**（`daily_window.revisions`）；修订使目标日变成休市、窗口不可用时，运行记录只有"不可用"。本票没有测试修订进入运行记录这一步，只在模块上测了修订本身。
5. **规格补句的措辞**（`.scratch/pring-fast-refactor-20260923/spec.md` 唯一测试接缝条）按票面原文写入，待用户确认。

**2026-09-29 补记（票 10 期间发现）**

- 本票删除 `test_independent_calendar_keeps_missing_core_day_in_required_window` 时，把其中与日历无关的断言也一起删了（计划缺口不完整、运行完成、门①不给阶段）。票 10 以完整运行形式补回，门①规则迁到单日汇总模块测试。
- `test_model_version_switch` 跑三次完整运行，同样受"无归属日历回执被留存删除"影响。本票当时没有把它列入受影响测试，票 10 的回归网发现后已修。

