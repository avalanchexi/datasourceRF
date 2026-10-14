Status: needs-info
Category: bug
Type: task

# 07：观察项：心跳 `database is locked` 与调度日历 SSL EOF

## 现象

- 10-14 14:06:16 运行完成后 9 秒出现一次 `lease_heartbeat_contended:database is locked`（warning），未影响结果。
- 10-14 11:30 唤醒后首次调度日历 TuShare 请求 `SSL: UNEXPECTED_EOF_WHILE_READING`，暂缓 10 分钟后重试成功，按设计工作。

## 处置

先观察。后续运行的 `worker.jsonl` 中任一项反复出现，再转 needs-triage 剖析。

## 来源

[验收记录](../../recurring-input-gaps-20261013/acceptance-20261014.md) 遗留 4、5。
