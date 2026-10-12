Status: claimed
Category: enhancement
Type: task

# 02：T+1 盘后调度只在 Worker 跨过 09:00 时提交，错过不补交；P0 截止改口径未写入 ADR

## 现象

票 03 实现：Worker 须在运行中跨过 09:00 才提交上一交易日（`src/pring_cycle/worker.py:142`、`:219`），晚于 09:00 启动的 Worker 不补交当日；票 03、残余 02 的调度至今无真实样本。另：票 03 把 P0 截止从“目标日 21:00”改为“提交当天 21:00”，由 ADR-0041 与票 14 推出，建议写入 ADR。需决定：是否在当日截止前补交、是否补写 ADR。

## 来源

[票 03](../model-rules-validation-20261011/issues/03-scheduled-run-t-plus-1.md) 遗留；验收记录遗留 5（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

- **补交**（用户 2026-10-12 决定）：开启计划时，当天北京时间 09:00 后、P0 截止（21:00）前首次判断即补交一次上一交易日；沿用现有幂等键 `scheduled-<目标交易日>-v<计划版本>`，日历不足照旧暂缓并每 10 分钟重试；人工运行与自动运行仍各自独立。同时封住“同日 08:59→21:01 仍先提交、执行入口才拒绝”的漏洞：截止后不再提交。
- **ADR-0041 补写**（不问）：自动运行的 P0 执行入口截止为首次提交日北京时间 21:00，提交日取不可变初始提交时点，不随冻结截止或恢复日期顺延；当前只在进入主体执行前检查，已开始的运行不因跨过该时刻中止。再补上补交规则。同步 `docs/development/local-runtime.md` 与 `spec.md` 的相应段落。

## 主要模块

`worker.py`（`submit_schedule_if_crossed`、`run_worker` 初始化、`DeferredSchedule`）、ADR-0041、`docs/development/local-runtime.md`；测试 `tests/integration/test_worker_execution.py`、`tests/integration/test_run_orchestration.py`。

## 验收

- [ ] 先有稳定变红的测试：09:00 后启动的 Worker 当天不提交（改写 `test_worker_execution.py:843` 的现有断言）
- [ ] 09:00 后、21:00 前首次判断即补交一次；重复判断、Worker 重启后不重复提交（同一幂等键）
- [ ] 21:00 后不再提交（含同日 08:59→21:01 的跨点场景）；21:00 精确边界与现有执行入口口径一致
- [ ] 休市日、日历失败暂缓、跨日醒来的行为不变或有测试覆盖
- [ ] 当天已判定结果有缓存，不每秒重复读全部日历
- [ ] ADR-0041、`local-runtime.md`、规格补写 P0 截止口径与补交规则
- [ ] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-02-06.md](../triage-codex-02-06.md) 第 1–11 条。

- 现象仍在（读码）：`run_worker` 把上次检查时间初始化为启动时刻（`worker.py:138`、`:142`），提交条件 `previous_local < scheduled_at <= observed_local or retrying`（`worker.py:219`），所以 09:00 后启动当日不提交，恰好 09:00 启动也不提交。快照中 `scheduled_full` 运行 0 条，调度尚无真实样本。
- 幂等：键为 `scheduled-<目标交易日>-v<计划版本>`，唯一约束 `(command_type, client_request_id)`（`worker.py:232`、`runs.py:1227`），重复判断与重启补交会返回原运行；人工与自动运行互不合并。
- P0 截止在 `worker.py:2066-2086`（取 `run_cutoff_contract.initial_system_as_of` 的北京日期加 21:00，`>` 比较），只在执行入口检查；ADR-0041 `:28` 只写“时效截止取运行时刻”，没有写 21:00（不是写了旧口径）。
- 决定：用户选“当日 09–21 点首次判断时补交（同一幂等键）”；ADR 补写不问。`ready-for-agent`，线 B 首票。

### 2026-10-12 进展（线 B，worktree `worktree-agent-a72c90c6a4547430b`）

- 已领取。红测试已写：改写 `test_worker_execution.py` 原 `test_enabled_schedule_only_runs_when_a_live_worker_crosses_0900_shanghai`（其 `missed_on_startup is None` 断言即“09:00 后启动不提交”的现状）为补交、21:00 边界、当天缓存三组用例；新接口 `submit_schedule_if_due(paths, observed_at, check)`、`ScheduleCheck` 尚未实现，导入失败（`/tmp/fub02-red.log`）。下一步实现。
- 2026-10-12 16:38 实现完成（`submit_schedule_if_due`、`ScheduleCheck`），调度相关 13 个用例（19 项）通过（`/tmp/fub02-green.log`）。下一步：受影响测试全文件、冒烟、重型。
- 2026-10-12 16:46 受影响测试（`test_worker_execution.py`、`test_run_orchestration.py`＋冒烟）54 通过 70 秒（`/tmp/fub02-affected.log`）；重型两例 4 通过 376 秒（`/tmp/fub02-heavy.log`）。下一步 ruff/mypy、文档。
- 2026-10-12 16:55 ruff/format/mypy（worker.py 无错；测试文件 mypy 18 条均为既有行）通过；ADR-0041 补写一节、`local-runtime.md`、`spec.md` 已改。下一步 Codex 两轴审查（`/tmp/fub02-review-*.log`）。
- 2026-10-12 17:20 审查第 1 轮：标准轴 1 阻断（测试打桩私有 `_scheduled_target`、断言 `ScheduleCheck` 字段）、规格轴无阻断＋2 非阻断（无模型边界、执行入口 21:00 边界测试）；已改为替换日历来源 `SseCalendar` 计数、只断言提交与请求，补执行入口边界用例，文档补无模型与重启区分。受影响测试 56 通过 73 秒（`/tmp/fub02-affected-2.log`）。下一步定向复审。
- 2026-10-12 17:40 审查第 2 轮（定向复审，`/tmp/fub02-review-recheck-2.log`）：第 1 轮四项修复均确认到位；新增阻断 1 项——本轮新加的执行入口 21:00 边界用例沿用了周边打桩私有 `_refresh_core_sources` 的写法。已改为 TuShare 出口替身（`source_adapters.build_opener`，首个请求即以 `BaseException` 中止），只断言是否发出请求与运行分类；受影响测试 56 通过 72 秒（`/tmp/fub02-affected-3.log`），ruff 通过。按规程（两轮后仍有新阻断）暂停，待主 agent 批准后做一次定向复审再收尾。
