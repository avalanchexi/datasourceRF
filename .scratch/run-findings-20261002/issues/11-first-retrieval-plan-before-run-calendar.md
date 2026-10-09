Status: ready-for-agent
Category: bug
Type: task

# 11 — 完整补缺首次规划在装入运行日历之前

## 原始发现（票 01 审查，Codex 只读）

- `full_retrieval.py` 先调用 `_plan` 生成首次计划，之后才 `use_run_calendar(judging_calendar(...))`；`_plan` 内依赖 `current_calendar()` 推算最新发布期，此时仍为工作日日历。
- 内存对照：9/28 判定融资余额、人民币收盘价时，工作日日历推算最新发布期为休市的 9/25，完整日历为 9/24。
- 既有行为（HEAD 前即如此），票 01 只修了运行内时效与发布状态的日历。

## 待决定

- 是否在首次规划前装入判定日日历（需先有窗口日历，或用 `SseCalendar.around`）。

## 验收

- [ ] 替身：判定 09-28 时，融资余额、人民币 16:30 收盘价的首次计划最新发布期都是 09-24，初始计划不出现休市的 09-25
- [ ] 正确期次未持有时进入正常补缺；已持有时不新增检索
- [ ] 首次、恢复与最终规划使用同一判定日历口径（同票 12）

## 主要模块

`src/pring_cycle/full_retrieval.py`（取得窗口后、推算期次前装入判定日历）、`trading_calendar.py`、Worker 调用接缝。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`，按 `/diagnosing-bugs` 先拿到稳定变红的用例。
- 仍在：`full_retrieval.py:91` 首次 `_plan` 早于 `:102` 的 `use_run_calendar(judging_calendar(...))`；`worker.py:228` 建空日历槽，`trading_calendar.py:460` 在槽未填时返回工作日日历。`2a3935f`（票 12）只改了判定日历保留休市日的方式，没动调用顺序。
- 内存实测：2026-09-28 23:59:59（北京）判定融资余额、人民币 16:30 收盘价，工作日日历给 09-25，上交所日历给 09-24。
- 运行库实测：目标日 09-28 的六次运行，收盘价初始计划都是 09-25／`model_input_missing`，最终都是 09-24／`local_complete`；错误期次只有 6 条 `release_gate/not_attempted`，没有多余外部检索。读码推断的真正风险：正确日历装入后门禁拦下 09-25，`full_retrieval.py:836` 最终重算计划但不重跑检索循环，若 09-24 未持有就会留下本可补取的缺口。
