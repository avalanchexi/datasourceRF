Status: ready-for-agent（(a) done；(b) 待用户决定）
Category: bug
Type: task

# 04 — 郑商所 5/18 仓单报 `acquisition_time_invalid`

## 原始发现

- CF 5/18 回执 `acquisition-92f5d00c74b94d25b5957764488e76d9`：`local_failed/acquisition_time_invalid`（回执时间不单调）。CF 抛出后中止该次刷新，TA 当日也没形成声明（`czce_warrants.py:434`）。
- 时间检查要求墙钟不倒退（`acquisition.py:433`、`:518`），`403cba4` 已有。

## 已知

- 与 [run-findings-20260928 票 01](../../run-findings-20260928/issues/01-wsl-clock-acquisition-time.md)（Windows 时钟快约 9.6 秒、WSL 时钟跳变）症状相同；那次已同步时钟，代码是否防护"待复验后定"。本次未测量系统校时。

## 待决定

- 是否重开票 01：先查 Windows/WSL 时钟是否又漂移；是否需要代码层防护（单次跳变不让整个品种日失败）。
- CF 失败连带 TA 不入库是否合理（ADR-0032 是按品种逐日拒收）。

## 验收

- [x] CF 在 received 与 validated 两个阶段分别注入时间倒退：CF 当日失败回执与原因保留，TA 仍用同一份日报入库
- [x] 同一次刷新中 CF 某日失败后，后续日期照常处理
- [x] 郑商所完全不可达时仍按 ADR-0032 停止本轮；磁盘、数据库等其他本地故障仍上抛
- [x] 外部调用保持串行，同一天日报不为两个品种各下载一次

## 主要模块

`src/pring_cycle/czce_warrants.py`（单品种单日的失败边界）、`tests/integration/test_czce_warrant_refresh.py`。不改来源与库结构。

## Comments

**2026-10-03 补充**：全套 `check.py full`（`e439ae4`）中 `test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out` 报 `acquisition_time_invalid` 一次（测试时间线取系统墙钟加偏移），单独重跑 3 次通过——WSL 时钟回跳再现。

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：拆为 (a)、(b)。
- (a) CF 失败连带 TA：仍在。`czce_warrants.py:308` 排序后先处理 CF，`:447` 遇 `LOCAL_FAILED` 直接重抛，外层日期／品种循环没有隔离；`worker.py:1604` 在整个刷新外抑制 `ValueError`，所以 TA 当日**及本次刷新的后续日期**都被跳过。ADR-0032 `:17` 规定按品种逐日拒收、`:18` 规定完全不可达时停止本轮——只隔离已识别的 `acquisition_time_invalid`，不笼统吞掉磁盘、数据库等其他本地故障。→ `ready-for-agent`。
- (b) 时钟回跳的代码防护：10-03 以来 `acquisition_time_invalid` 0 张；★ 主 agent 实测 Windows 与 WSL 偏差约 +0.25 秒（往返 0.7 秒内，三次一致），时钟目前同步。检查语义是单张回执各阶段墙钟非递减（`acquisition.py:535`、`:416`、`:617`）；改成"单调时钟锚定墙钟"会改变回执、`available_at`（`evidence.py:630`）与推定公开时间的含义，修复面中等。属证据时间语义，交用户决定。

### 2026-10-09 实施（(a)）

> *本段由 AI 在实施时生成。*

- **改动**：`czce_warrants.py` 的 `_take` 在 capture 失败为 `LOCAL_FAILED` 时，新增 `_clock_stepped_back` 精确识别 `ValueError("acquisition_time_invalid")`：只拒收该品种该日（回执 `failed`、`rejection_reason` 与取数记录 `local_failed/acquisition_time_invalid` 照旧保留），返回失败后继续处理另一品种（复用同一份已缓存日报）与后续日期。其他 `LOCAL_FAILED`（磁盘、产物存储、入库阶段 OSError）与未捕获的数据库异常仍上抛、停止本次刷新；完全不可达仍按 ADR-0032 停止本轮。`worker.py`、`acquisition.py`、来源与库结构未改。(b) 未动。
- **测试**（`tests/integration/test_czce_warrant_refresh.py`）：新增 `test_a_clock_stepping_back_fails_only_that_symbol_day`（received／validated 两阶段：在 5/19 日报应答后的第 1／2 次读钟回退 7 秒，确定性时间线；断言 CF 回执失败阶段与原因、TA 同日与 9/02 两品种入库、每日只请求一次），修复前两例均红；新增 `test_any_other_local_failure_still_stops_the_refresh`（产物存储 OSError／ValueError、数据库 `OperationalError`、入库阶段 OSError 四例均上抛且不再请求后续日期）。既有不可达用例保持。
- **验证**（专用 venv `dev-venv-czce`）：本文件 13 passed 约 10 秒；受影响集（`tests/adapters/test_czce_warrants.py`、本文件、`test_warrant_symbol_isolation.py`、`test_gap_source_repairs.py`）＋两例冒烟 46 passed 3:44（超 3 分钟目标，慢在 `test_gap_source_repairs.py` 等既有完整运行替身）；重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 4 passed 10:20（`flock`，含少量排队）；`ruff check`、`ruff format --check` 通过；`mypy` 仅报既有 `tests/conftest.py:21` 缺注解。
- **审查**（Codex 两轴）：标准轴阻断无；规格轴阻断无。采纳两条非阻断：测试时间线改为确定性（原用真实墙钟减 7 秒）、补数据库与入库阶段本地故障用例。
