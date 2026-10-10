Status: done
Category: bug
Type: task

# 12 — 盘后自动调度只排除周末

## 原始发现（票 01 审查，Codex 只读）

- `worker.py` 盘后计划只按周末跳过；启用调度后，国庆等节假日的工作日仍会以当天为目标提交，随后可能因目标日不是开市日而取不到窗口。
- 调度默认关闭；手动提交不受影响（提交时定目标日已读核心口径日历）。

## 待决定

- 是否让调度按上交所日历判断当天是否开市。

## 验收

- [x] 已知国庆休市的工作日不提交；已知开市日跨过计划时刻只提交一次
- [x] 日历未覆盖的工作日提交、未覆盖的周末不提交；不抹掉已知休市声明
- [x] 调度关闭、跨日检查和去重行为不变；判断不引入外部请求

## 主要模块

`src/pring_cycle/worker.py`（盘后计划判断）；如抽"某日是否开市"共用函数则放 `trading_calendar.py`。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`。
- 仍在：`worker.py:168` 只检查同一天与 `weekday() >= 5`，`:179` 直接以当天提交。
- 注意：默认关闭（`runs.py:153`），但**运行库当前配置已开启**（`schedule_configuration` version=2、enabled=1、Asia/Shanghai、18:30）；`scheduled_full` 运行目前为 0，尚无节假日误提交实例。优先级因此不再是"低"。
- 建议复用 `SseCalendar(paths, as_of=observed_at).stated_between(day, day)`（`trading_calendar.py:367`）：有声明就按开／休市，无声明才按工作日；不要用 `judging_calendar(paths, (), ...)`（空窗口提前返回，`:420`），也不要用可能触网的 `launch_calendar`。

### 2026-10-10 实施

- **改动**：`worker.py` `submit_schedule_if_crossed` 去掉单独的 `weekday() >= 5` 判断；同日、跨过计划时刻两道守卫之后，用 `SseCalendar(paths, as_of=observed_at).stated_between(today, today)` 判当天（`today` 为调度时区本地日）：有声明按开／休市，无声明才按工作日。日历只在跨过计划时刻后读取，不进每秒循环；只读本地已验证回执，不触网。未抽共用函数（只此一处用）。
- **测试**（`tests/integration/test_worker_execution.py` 新增两例，先红后绿）：国庆 10/1、10/2、10/5–10/7 声明休市不提交；9/30 跨过 18:30 提交一次，同日后续检查不提交、重复跨过返回同一运行；跨日检查不提交；调度关闭时不提交；前后 `trade_cal` 请求数不变。另一例：日历只声明到 10/8 时，10/7（声明休市）不提交、10/9（未覆盖周五）提交、10/10（未覆盖周六）不提交。
- **验证**：受影响 `check.py quick tests/integration/test_worker_execution.py tests/integration/test_holiday_freshness.py tests/integration/test_trading_calendar.py` 58 passed，3:32（超 3 分钟目标，主要是 `test_worker_execution.py` 既有用例）；两例冒烟 2 passed，1:39；`ruff check`、`ruff format --check` 通过；`mypy` 对改动文件 17 处报错与 HEAD 版测试文件同数，均为既有，新增代码无报错。重型两例（`test_worker_registered_catalog.py`、`test_core_carry_forward.py`）不经过调度入口（grep 无 `submit_schedule_if_crossed`／`scheduled_full`），未加跑。
- **审查**（Codex 两轴）：标准轴无问题，阻断：无；规格轴三项验收均有实现与测试证据，阻断：无。非阻断：(1) 集成测试未直接覆盖上海／UTC 日界、过滤 `is_open` 响应与材料不可读的调度组合——不采纳，这些已由 `SseCalendar` 组件测试覆盖（`test_trading_calendar.py`），调度只多一次本地日换算，沿用原守卫；(2) 日历的数据库查询异常会经主循环抛出——不采纳，同一循环里 `repository.schedule()`、心跳本就直接查库，属同类既有边界。

