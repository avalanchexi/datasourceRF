Status: needs-triage
Category: bug
Type: task

# 11 — 完整补缺首次规划在装入运行日历之前

## 原始发现（票 01 审查，Codex 只读）

- `full_retrieval.py` 先调用 `_plan` 生成首次计划，之后才 `use_run_calendar(judging_calendar(...))`；`_plan` 内依赖 `current_calendar()` 推算最新发布期，此时仍为工作日日历。
- 内存对照：9/28 判定融资余额、人民币收盘价时，工作日日历推算最新发布期为休市的 9/25，完整日历为 9/24。
- 既有行为（HEAD 前即如此），票 01 只修了运行内时效与发布状态的日历。

## 待决定

- 是否在首次规划前装入判定日日历（需先有窗口日历，或用 `SseCalendar.around`）。
