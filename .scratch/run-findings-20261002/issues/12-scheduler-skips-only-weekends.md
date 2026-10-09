Status: ready-for-agent
Category: bug
Type: task

# 12 — 盘后自动调度只排除周末

## 原始发现（票 01 审查，Codex 只读）

- `worker.py` 盘后计划只按周末跳过；启用调度后，国庆等节假日的工作日仍会以当天为目标提交，随后可能因目标日不是开市日而取不到窗口。
- 调度默认关闭；手动提交不受影响（提交时定目标日已读核心口径日历）。

## 待决定

- 是否让调度按上交所日历判断当天是否开市。

## 验收

- [ ] 已知国庆休市的工作日不提交；已知开市日跨过计划时刻只提交一次
- [ ] 日历未覆盖的工作日提交、未覆盖的周末不提交；不抹掉已知休市声明
- [ ] 调度关闭、跨日检查和去重行为不变；判断不引入外部请求

## 主要模块

`src/pring_cycle/worker.py`（盘后计划判断）；如抽"某日是否开市"共用函数则放 `trading_calendar.py`。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`。
- 仍在：`worker.py:168` 只检查同一天与 `weekday() >= 5`，`:179` 直接以当天提交。
- 注意：默认关闭（`runs.py:153`），但**运行库当前配置已开启**（`schedule_configuration` version=2、enabled=1、Asia/Shanghai、18:30）；`scheduled_full` 运行目前为 0，尚无节假日误提交实例。优先级因此不再是"低"。
- 建议复用 `SseCalendar(paths, as_of=observed_at).stated_between(day, day)`（`trading_calendar.py:367`）：有声明就按开／休市，无声明才按工作日；不要用 `judging_calendar(paths, (), ...)`（空窗口提前返回，`:420`），也不要用可能触网的 `launch_calendar`。
