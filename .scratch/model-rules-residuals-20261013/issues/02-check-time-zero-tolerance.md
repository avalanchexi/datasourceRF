Status: needs-triage
Category: bug
Type: task

# 02：生产 `_check_time` 对墙钟回拨零容忍，而且整批拒收

## 现象

`acquisition.py:683-685`（调用点 `:460`、`:579`）：校验时刻早于接收时刻就拒收（`acquisition_time_invalid`）。`run-742b…` 因此丢了 31 条回执，拒收集中成片，推断是回拨落在批次取数与批末统一校验之间（未核实）。拒收记为 `local_failed`，没有负缓存，下一轮会重取。`test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out` 在回拨环境下也会失败。

## 待分流

是否引入容忍度，或改用单调时钟判断先后；是否属于领域口径（回执时间线的可信度）需要用户定。

## 来源

[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 2。
