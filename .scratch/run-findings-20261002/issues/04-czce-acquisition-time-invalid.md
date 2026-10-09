Status: ready-for-agent（(a) 部分；(b) 待用户决定）
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

- [ ] CF 在 received 与 validated 两个阶段分别注入时间倒退：CF 当日失败回执与原因保留，TA 仍用同一份日报入库
- [ ] 同一次刷新中 CF 某日失败后，后续日期照常处理
- [ ] 郑商所完全不可达时仍按 ADR-0032 停止本轮；磁盘、数据库等其他本地故障仍上抛
- [ ] 外部调用保持串行，同一天日报不为两个品种各下载一次

## 主要模块

`src/pring_cycle/czce_warrants.py`（单品种单日的失败边界）、`tests/integration/test_czce_warrant_refresh.py`。不改来源与库结构。

## Comments

**2026-10-03 补充**：全套 `check.py full`（`e439ae4`）中 `test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out` 报 `acquisition_time_invalid` 一次（测试时间线取系统墙钟加偏移），单独重跑 3 次通过——WSL 时钟回跳再现。

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：拆为 (a)、(b)。
- (a) CF 失败连带 TA：仍在。`czce_warrants.py:308` 排序后先处理 CF，`:447` 遇 `LOCAL_FAILED` 直接重抛，外层日期／品种循环没有隔离；`worker.py:1604` 在整个刷新外抑制 `ValueError`，所以 TA 当日**及本次刷新的后续日期**都被跳过。ADR-0032 `:17` 规定按品种逐日拒收、`:18` 规定完全不可达时停止本轮——只隔离已识别的 `acquisition_time_invalid`，不笼统吞掉磁盘、数据库等其他本地故障。→ `ready-for-agent`。
- (b) 时钟回跳的代码防护：10-03 以来 `acquisition_time_invalid` 0 张；★ 主 agent 实测 Windows 与 WSL 偏差约 +0.25 秒（往返 0.7 秒内，三次一致），时钟目前同步。检查语义是单张回执各阶段墙钟非递减（`acquisition.py:535`、`:416`、`:617`）；改成"单调时钟锚定墙钟"会改变回执、`available_at`（`evidence.py:630`）与推定公开时间的含义，修复面中等。属证据时间语义，交用户决定。
