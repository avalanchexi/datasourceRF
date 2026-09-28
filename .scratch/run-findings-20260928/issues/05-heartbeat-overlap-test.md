Status: done
Category: bug
Type: task

# 05 — 心跳锁冲突用例稳定失败

## 原始发现

- `tests/integration/test_lease_heartbeat_overlap.py::test_a_heartbeat_blocked_by_a_long_write_keeps_the_lease` 在全套里失败，单独跑也失败，在 `9d230f9`（9/26 全套时通过）上同样失败。心跳代码（`worker.lease_heartbeat`、`runs.heartbeat_lease`）这段时间没有改动。
- 调试：另一个连接用 `BEGIN IMMEDIATE` 持锁，预期持 6.5 秒；心跳的第一次写入等了约 **4.8 秒**后成功，没有超过 5 秒的 `busy_timeout`，所以从未触发锁冲突，`contention` 为空。
- 也就是说，锁比预期更早释放了。

## 待决定

- 查持锁线程为什么提前放锁；看是否与 WSL 时钟跳变（票 01）或 SQLite 版本、文件系统有关。
- 生产上心跳照样续上了租约，只是没有走到“冲突后重试”这条路径。

### 关闭（2026-09-28）

> *本段由 AI 按用户确认记录。*

Windows 对时后单独复跑通过（8 秒）。按时钟问题处理，不改代码；如果全套里再失败再重开。
