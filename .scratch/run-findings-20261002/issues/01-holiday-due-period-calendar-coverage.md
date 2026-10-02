Status: needs-triage
Category: bug
Type: task

# 01 — 节假日被当成应有期：运行内日历只覆盖到目标日

## 原始发现

- 运行 `run-b7ccf5dbbe8e21b2a6fc`（目标日 2026-09-30，2026-10-02 22:23 北京时间冻结时效）的缺口清单中，21 项国内日频指标记 `freshness_gap`、`one_period_behind_carried`，`due_period=2026-10-01`、`held_period=2026-09-30`。10-01 是国庆休市日。涉及三个 P0 核心（000985、000012、NHII）、七个广度指标、中证 300/500/1000、估值、国债、商品、SHIBOR 等。
- 融资余额 due 9/30、held 9/29 同因（T+1 发布按错误日历推到 10/01、宽限到 10/02）。DR007 被推成"落后两期"（实际只缺 9/30，见下）。OMO 操作量、USDCNY 中间价也同因（另见票 05）。
- 正式阶段未受影响（无核心沿用），但缺口清单由基线 1 项变为 28 项，P0 核心被标为"沿用上一期"。

## 根因（Codex 只读调查）

- 运行内两张 `trade_cal` 回执 `end_date=20260930`；正式计划 `daily_window` 为 4/09–9/30。`full_retrieval.py:73`、`worker.py:399` 用窗口开市日重建 `TradingCalendar`，`day_summary.py:177` 再装入；目标日以后的覆盖边界丢失。
- `trading_calendar.py:72` 对覆盖外日期按 `weekday()<5` 推定，于是 10/01、10/02 被当交易日；日频宽限一个交易日，得 due=10/01（`freshness.py:52`、`:295`）。
- **库里已有休市信息**：启动日历回执 `acquisition-26f0c3f7d1114556b8daabcd92b8bd7d` 请求至 20261002，原件写明 9/30=1、10/01=0、10/02=0，只是运行内没用上。
- **不是本轮重构回归**：`403cba4` 同样如此（`freshness.py:229–232`、`full_run_requirements.py:75–80`、`full_retrieval.py:71–73`、`worker.py:378–384`）。与 [run-findings-20260928 票 03](../../run-findings-20260928/issues/03-mid-autumn-due-period.md)（中秋，wontfix：T+1 可接受）同一问题。
- 内存对照：保留休市覆盖到 10/02 后，核心债券、融资余额、OMO 操作量、USDCNY 中间价均为 `current`，DR007 为 `awaiting_release`。

## 待决定

- 是否重开（上次 wontfix 依据是"只落后一期、T+1 可接受"；这次节假日长、影响面大，且 P0 核心被标为沿用、DR007 被判两期）。
- 修复方向（建议）：时效判断使用覆盖判定日的完整日历，保留休市覆盖边界，不用 120 日开市序列代替。
