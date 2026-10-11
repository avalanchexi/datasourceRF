# 03: 盘后调度改为 T+1

**What to build:** 自动盘后运行在每个上交所交易日上午 9:00 提交上一交易日的运行；非交易日不提交；今天或上一交易日缺少日历依据时，先补取日历，补取失败就暂缓并定时重试；节后第一个交易日识别节前最后一个交易日。人工运行不受影响。本地运行文档的盘后计划一段同步更新。依据：[spec](../spec.md)、ADR-0041，在票 14 的调度做法基础上改。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 调度判断接缝上的测试先红后绿，覆盖以下情形：交易日 9:00 提交上一交易日；非交易日不提交；缺日历覆盖时先补取；补取失败时暂缓、重试，过截止后停止；节后第一个交易日识别节前最后一个交易日
- [x] 日历已覆盖时外部调用为 0
- [x] 本地运行文档已更新
- [x] 受影响测试、两例冒烟、ruff、mypy 通过；Codex 两轴审查无阻断

## Comments

### 2026-10-11 实施

**改了什么**（worktree 分支，线 B）：

- `worker.submit_schedule_if_crossed`：触发时刻随计划配置改为 9:00，判定由新函数 `_scheduled_target` 给出目标日。已存上交所日历写明今天休市时不提交；写明今天开市、且从今天往回到上一交易日的每一天都写明时，直接提交上一交易日；这两种情况都不发请求。今天或往回到上一交易日之间有未覆盖的日子时，向 TuShare 补取一次 `trade_cal`（今天往前 14 天至今天，沿用票 14 的 `SCHEDULE_CALENDAR_REACH`），今天开市才提交，目标取应答里今天之前最近的开市日。补取失败，或应答里今天开市却没有更早的开市日（规格轴第一轮意见），都写 `scheduled_run_deferred:calendar_unavailable:…` 事件并暂缓，每 10 分钟重试，过当天 21:00 或跨日就停止（`DeferredSchedule` 沿用票 14）。幂等键改为 `scheduled-<目标日>-v<计划版本>`。
- P0 截止：`_scheduled_p0_deadline_elapsed` 原来取“目标日 21:00”，T+1 运行一提交就会被判过期，所以改为“提交当天 21:00”。提交日读不可变的 `run_cutoff_contract.initial_system_as_of`（新增 `RunRepository.submitted_as_of`），冻结截止跨到次日也不会顺延（标准轴第一轮意见）。这一条是从 ADR-0041 和票 14 推出来的口径，没有另立领域规则；两轴审查都认为不需要另行授权，建议以后在 ADR 中写明。
- 计划配置：`runs.py` 新增 `SCHEDULE_START_TIME = "09:00"`、`SCHEDULE_P0_DEADLINE = "21:00"`，新库初始化和 `configure_schedule` 都用它们。迁移 `0036_scheduled_run_t_plus_1`：最新版本如果仍是 18:30，就追加一个 9:00 的新版本，开关保持原状，历史版本保留；空表、没有这张表、或已经是 9:00 的库不动。`SCHEMA_HEAD` 和 `test_database_lifetime` 的修订号同步更新。ADR-0010 的“默认关闭”不变。
- 人工运行入口没有改动。
- 文档：`docs/development/local-runtime.md` 的盘后计划段改写为 T+1 规则（触发、目标日、截止、补取与暂缓、迁移）。

**测试**（`tests/integration/test_worker_execution.py`、`tests/integration/test_run_orchestration.py`；时钟用显式时刻加 `install_runtime_clock`，TuShare 用 opener 替身 `TradeCalOpener`）：

- 交易日 9:00 提交上一交易日，18:30 不再触发，启动时错过的不补（`test_enabled_schedule_only_runs_when_a_live_worker_crosses_0900_shanghai`）；
- 日历已写明时：国庆假日不提交，9/30 识别 9/29，节后第一天 10/8 识别 9/30，重复检查返回同一运行，跨日检查不提交；`trade_cal` 请求数与暂缓事件都为 0（`test_enabled_schedule_skips_a_stated_sse_holiday_and_submits_the_session_before_once`）；
- 缺覆盖时先补取：已写明的日子 0 次请求；10/1 补取后休市；10/8 补取后识别 9/30；10/9 识别 10/8，再查不请求；10/10 周六补取后休市；10/12 自身已写明开市、前面周末未覆盖时补取，识别 10/9；断言每次请求区间（`test_an_unstated_day_fetches_its_sse_calendar_before_the_schedule_submits`）；
- 补取失败暂缓、到期重试后提交上一交易日（`OSError`、`IncompleteRead` 两种）；过 21:00 或跨日不再重试；应答里没有上一交易日时暂缓并重试（`test_a_response_without_the_session_before_today_defers_the_schedule`）；
- P0 截止：T+1 运行在提交当天上午执行时不过期；过提交当天 21:00 过期，冻结截止跨到次日也一样（`test_a_next_morning_scheduled_run_is_not_expired_by_its_target_days_deadline`、`test_a_next_morning_scheduled_run_expires_past_the_deadline_of_its_scheduled_day`）；
- 迁移：18:30 的库追加 9:00 版本，开关两种状态都保持；空表不追加；最新版本已是 9:00 时不变（`test_an_upgraded_schedule_moves_to_the_next_morning_and_keeps_its_switch`），新库默认 9:00（`test_after_close_schedule_is_versioned_and_disabled_by_default`）。
- 原用例 `test_enabled_schedule_only_runs_when_a_live_worker_crosses_1830_shanghai` 与 `test_an_uncovered_weekday_fetches_its_sse_calendar_before_the_schedule_submits` 测的是当天 18:30 识别当天，已由上述 T+1 用例取代。
- 先红后绿：实现前 10 例失败；审查后补的两例，对未修复的安装副本运行时失败（`--allow-stale-environment`），修复后通过。

**验证**（专用 venv `dev-venv-mrb`，rebase 到 main `8b2e2d6` 之后复跑）：

- 受影响测试：`test_worker_execution.py`（含冒烟例 `test_worker_completes_a_valid_noncanonical_projection_and_report`）、`test_run_orchestration.py`、`test_database_lifetime.py`、`test_receipt_counts.py`、`test_claim_adoption.py`、`test_worker_calendar_gate.py`、`test_trading_calendar.py`，加冒烟例 `test_manual_run_cannot_backdate_daily_core_availability`，共 102 passed（242 秒）；
- 重型 `test_worker_registered_catalog.py` 与 `test_core_carry_forward.py` 经 flock 运行：审查前 4 passed（498 秒），修复并 rebase 后 4 passed（452 秒）；
- ruff check／format 通过；mypy 对 `worker.py`、`runs.py`、`storage.py`、迁移 0036 无错；两个测试文件只剩 main 上原有的错误，改动区域没有新增。

**审查**（Codex 两轴，两轮）：

- 第一轮：标准轴有 1 项阻断，P0 截止读的是会被冻结截止改写的 `system_as_of`，已改为读提交时刻；规格轴有 1 项阻断，应答里今天开市却没有上一交易日时会静默停止，已改为暂缓重试。两项都补了回归用例。
- 第二轮：两轴均为“阻断：无”，并确认两项修复成立。
- 采纳的非阻断意见：`_Calendar` 改名为 `_CalendarStatus`；压缩 docstring；迁移测试补“历史 18:30、最新 9:00 时不追加版本”。
- 不采纳：①“开启 T+1 后人工运行任意目标日”的专项回归，人工入口与截止判断都没有改，已有人工运行用例覆盖；②“预存旧运行→迁移→新运行”的组合回归，迁移让计划版本加一，幂等键里带版本，两者不会冲突；③正例用替换 `_refresh_core_sources` 来证明执行越过截止检查，与同文件既有过期用例的接缝一致。

**已知残余风险**：沿用票 14 的说明，日历解析器不检查区间内每天都有一行；应答如果漏列今天，会被当作休市，当天不提交也不重试。后果是漏掉一次自动运行，不会误提交。

**遗留**：本票不做真实运行；调度行为要在 Worker 跨过 9:00 时才能真实核对，按需并入票 06。旧运行库需要先执行 `pring-cycle init`，迁移 0036 才会生效。
