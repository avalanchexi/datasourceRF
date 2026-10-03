Status: needs-triage
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

## Comments

**2026-10-03 补充**：全套 `check.py full`（`e439ae4`）中 `test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out` 报 `acquisition_time_invalid` 一次（测试时间线取系统墙钟加偏移），单独重跑 3 次通过——WSL 时钟回跳再现。
