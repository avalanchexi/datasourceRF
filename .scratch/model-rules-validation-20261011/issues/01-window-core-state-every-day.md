# 01: 窗口内每天都有核心状态

**What to build:** 一次运行取得约 260 个交易日的三核心历史，使 120 日窗口内每个交易日都有核心资产状态，阶段历史从窗口首日起连续；每个核心仍是一次区间请求，窗口前的核心价格照常在运行末尾清理。同时把 A5 核心沿用的计算方式按现行做法写入文档。依据：[spec](../spec.md)、ADR-0040。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 完整运行接缝上的测试先红后绿：改动前窗口前部为“历史不足”，改动后窗口内每日都有核心状态
- [x] 断言每个核心只有一次区间请求，外部调用串行
- [x] 窗口前核心价格照常清理，未新增留存例外
- [x] A5 核心沿用计算方式已写入文档，并注明出处为 2026-10-11 访谈
- [x] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

## Comments

### 2026-10-11 实施

**改了什么**

- `src/pring_cycle/domain/trend.py`：`TrendRules.history_required`（= `window_days + slope_days`，现为 140），趋势两处门槛改读它，语义不变。
- `src/pring_cycle/worker.py`：`_refresh_core_sources` 新增必填参数 `core_sessions`，调用处按生效模型的趋势规则取 `120 + history_required`（= 260），替换原来写死的 160；TuShare 仍是每个核心一次区间请求（`latest_observations=core_sessions`），日历请求起点放宽为 `core_sessions * 7 // 4` 天（260 点约 455 天，原 280 天对 160 点为同一比例）。中证官方补源原来沿用自然日起点，会比 TuShare 多读历史（原先约 190 对 160，放宽后约 305 对 260），现改为与 TuShare 同一组开市日：取已持有上交所日历的最近 260 个开市日（`SseCalendar.window`）；日历缺失时按同样个数的工作日估算，宁短不长。
- 留存不变：窗口前核心价格照常在成功运行末尾清理，未新增例外。
- 文档：`docs/development/data-quality-audit.md` 核心重算一节新增“核心沿用（A5）”，按生产现行做法写明条件、计算、输出与恢复，出处为 2026-10-11 访谈 Q4；同时订正收益链一段（缺 `pre_close` 与沿用无关，生产按相邻收盘之比计算收益），说明体检尚未据此重算沿用日。ADR-0040“后果”补一条：窗口前预热输入由约 40 增至约 140 个交易日，查不到原始来源的代价随之扩大。
- 测试：新增 `tests/integration/test_core_window_history.py`，均经手动完整运行公开入口、外部 HTTP 用替身：
  - 窗口 120 天每天三核心都有测量（不再“历史不足”）；每个核心一次区间请求、覆盖 260 个开市日、外部调用无并发；运行后只剩窗口内核心价格。改动前在窗口首日 2026-02-17 报 `insufficient_history`（先红），改动后通过。
  - TuShare 缺一个中证核心时，官方补源的请求区间与 TuShare 相同（改动前起点 2025-05-05，先红）。
  - TuShare 全部不可用、缓存日历恰好覆盖 260 个开市日时，补源起点仍为第 260 个开市日（对第二轮实现为红）。
  - 冒烟用例里“160 sessions”的注释改为 260。

**测试与耗时**

- 受影响测试（趋势、核心刷新、中证补源、留存、日汇总、日历门、限额、e2e 核心夹具等 18 个文件加冒烟）：合入票 03 后复跑 196 passed，22 分 07 秒（首轮 193 passed，18 分 42 秒）。
- 冒烟两例：2 passed，38 秒。
- 重型两例（`flock` 下 `python -m pytest`）：`test_worker_registered_catalog.py` 与 `test_core_carry_forward.py` 共 4 passed，最终代码 7 分 53 秒。
- `ruff check`、`ruff format --check`、`mypy`（改动的源码与新测试）通过。`test_core_history_refresh.py` 的 format 与 mypy 问题在 HEAD 上已存在，本票只改了其中一行注释。

**审查结论**

- 标准轴：两轮均“阻断：无”。
- 规格轴：第一轮 2 条阻断（中证补源读入多于 260 点；A5 文案中“落后 2 期为 `stale_for_target_business_date`”以及缺 `pre_close` 与沿用的关联不准确），已修；第二轮 1 条新阻断（`sessions_between` 要求缓冲区也有日历，缓存够却会误降级），已改用 `SseCalendar.window` 并补回归测试；定向复审“阻断：无”。
- 非阻断意见：455 天可覆盖有长假的真实日历（审查按上交所 2025、2026 年安排核算，最少约 300 个开市日），无需改动。

**遗留与说明**

- 260 点保证窗口首日就能测量，但稳定方向要连续 8 个观测才确认，所以全新初始化时窗口前 6 天最多只到 `transition_pending`。这是 ADR-0040“120 日窗口加 140 点测量门槛”的直接结果，不在本票改动。
- 已汇总的日子不会重算（`DaySummaries.backfill` 只补没有汇总的日子），规格也把批量重算已有发布物列为范围外。真实运行库里窗口前部已有的日汇总仍按当时持有的历史计算，这一点留待票 06 验收时说明。

