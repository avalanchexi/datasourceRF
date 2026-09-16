# 票17 最后一项：租约心跳与写入交叠（2026-09-16）

按 diagnosing-bugs 流程执行：先建可稳定变红的反馈回路，再定位、再修、再回归。历史第59批的完整运行共享预算路径出现过真实 SQLite 锁错误，此前单例与随机并发均未复现、持锁身份未知。

## 反馈回路（先于任何假设）

最小可控交叠脚本：一个线程以 `BEGIN IMMEDIATE` 持写锁 N 秒，另一侧经运行期连接助手 `database_connection` 访问，按 `WAL/DELETE` × `读/写` 四种组合各跑一次。结果（持锁 6 秒）：

| 日志模式 | 访问 | 结果 | 等待 |
|---|---|---|---:|
| WAL | 读 | ok | 0.0s |
| WAL | **写** | **OperationalError: database is locked** | 5.11s |
| DELETE | 读 | ok | 0.0s |
| DELETE | **写** | **OperationalError: database is locked** | 5.10s |

两点事实由此确定：

1. **读不参与竞争**，票记录里"`source_claim_acquisitions_many → 开连接`"这一段本身不会因写锁失败。真正会失败的是**写与写交叠**。
2. 运行期连接的忙等上限是 **5 秒**——不是代码里那条 `PRAGMA busy_timeout=5000`（它只作用于迁移期的 alembic 连接和 `_sqlite_connection`），而是 Python `sqlite3.connect` 的默认 `timeout=5.0`。超过 5 秒必然抛锁错误。

## 定位

租约心跳每 30 秒经 `RunRepository.heartbeat_lease` **写** `worker_lease`，与运行自身的长写（如证据批量写入、模型输出文档）竞争同一把写锁。而原 `_lease_heartbeat` 只捕获 `ValueError`：

```python
while not stopped.wait(30):
    try:
        runs.heartbeat_lease(owner_id)
    except ValueError:
        return
```

锁错误是 `sqlite3.OperationalError`，不被捕获 → **心跳线程静默死亡** → 租约在 120 秒后过期 → 运行被判失主。这与第59批"共享预算路径下的锁错误"的表现一致：长写窗口越长（共享预算批量写入越多），撞上心跳的概率越高。

**未被本次证明的部分**：第59批当时具体是哪一条长写持锁，现存证据无法确认，不补造历史取证（沿用 273 方案评审的结论）。本次确定的是机制与修复，不是那一次的持锁身份。

## 修复

不加超时、不删 WAL 设置、不用单例重试绕过。改为让心跳在**租约自身的有效期内**重试并留证：

- `_lease_heartbeat` 提升为公开的 `lease_heartbeat`，参数化心跳间隔，便于在公开接缝测试。
- 捕获 `sqlite3.OperationalError`：这是竞争而非失主，记 `lease_heartbeat_contended:<异常类型>` 运行事件（warning）后重试下一拍。
- 只有两种情况结束循环：`ValueError`（确实失去所有权，立即退出，行为不变）；或连续竞争累计达到租约有效期 `LEASE_VALID_SECONDS = 120` 仍未成功，记 `lease_heartbeat_abandoned`（error）后退出。租约语义不变——真的 120 秒写不进去，仍然失去租约，但有据可查。

## 回归与验证

- 新用例 `tests/integration/test_lease_heartbeat_overlap.py`：① 长写持锁超过忙等上限时，心跳循环不退出、竞争被记录，长写释放后租约仍为本运行所有（`owner_state=active`）；② 失去所有权时心跳仍立即停止。2 通过/8.8秒。
- 变异检查：把锁错误改回"即刻退出"，用例①立即失败。
- 相关回归：`test_lease_heartbeat_overlap`、`test_worker_execution`、`test_worker_database_lifetime`、`test_retrieval_ledger` 共 **59 通过/175.4秒**；ruff 与 `mypy src`（96 源文件）通过。

## 连带修正（票14 回退的遗漏）

`test_worker_classifies_optional_eia_failures` 未挡住新的无密钥页面回退，既可能触网，断言也只看单一渠道。已改为：页面在夹具中离线，分别断言 API 渠道保留原分类（`source_failed`/`adapter_failed`/`validation_failed`）、页面渠道记 `source_failed`。4 通过。至此所有走 EIA 分支的测试都不触网。

## 范围

本记录只覆盖票17「慢关闭已复现机制的修复仍成立；租约心跳与查询交叠」这一项的**心跳交叠**部分与其公开反例。该项还要求在完整运行到投影与状态查询的链路上验证，属下一批合并验证范围；票17 本次**不勾选**该项。
