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

一点事实由此确定，另一点已于同日更正：

1. **更正（2026-09-17）**：原写作"读不参与竞争，票记录里 `source_claim_acquisitions_many → 开连接` 这一段本身不会因写锁失败"——**该结论越界**。上述夹具以 `BEGIN IMMEDIATE` 持 RESERVED 锁，提交发生在释放之后，读侧从未与提交窗口（PENDING/EXCLUSIVE）重叠；回滚日志模式下读者恰恰是在写者提交时才可能 BUSY。补做的交叠实验（读事务横跨写者 COMMIT，WAL/DELETE × 读先/写先四组）四组均为 ok——**该实验是一次性脚本，未留回执文件**，与上表不同，只能据本段文字复核，需要时须按同样交错重做；**这同样只说明该交错下未失败，不能反证读路径永不失败**。按 [273 方案评审](sqlite-claude-plan-review-273.md)"不能排除其他连接、进程或 SQLite 锁竞争"，本记录不再对读路径下结论。确定的是：**写与写交叠超过忙等上限必然失败**。
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

## 两轴复审（2026-09-17）与据此的返工

同日对本批（`9d44c7d~1..HEAD`）做冻结树两轴复审，两轴均有实质发现，已逐条处理：

**Standards**
- 清单键改名未升 schema：已写过 `measured_seconds` 的历史清单重建会少这个值而永久 `cutover_manifest_stale`。改为读时同时接受新旧键。
- 心跳把**所有** `OperationalError` 当竞争：磁盘满、I/O 错误、数据库损坏也会被静默重试一整个租约窗口。改为仅匹配锁占用消息，其余照常抛出。
- 放弃阈值正好等于租约有效期，等于"租约已失效后才报"：改为提前一个心跳间隔放弃。
- `_claim_families(scope)` 参数未用：删除。
- 家族结果以 `name` 为字典键：同名家族会互相覆盖；改为结果随家族一起携带。
- 重复指标 id 会让 `points_of` 重复取点（原实现不会）：按首次出现去重。
- 测试用 `GROUP BY ... HAVING MAX(fetched_at)` 取"最新一条"不可靠（裸列取值未定义）：改为相关子查询。

**Spec（更严厉，结论是我勾早了）**
- 该项明文要求"租约心跳与查询交叠时**完成共享预算用例**"，而我的交叠用例只播种核心历史、没有缺口与检索密钥，跨期共享硬搜索预算用例**一次都没在争用下跑过**。
- "心跳退出与连接释放顺序"只断了终态，且 `audit_lease` 根本没有 `released` 状态，租约从未获取也会通过。
- 交叠强度不足以让心跳跳过一拍，把"遇锁即退出"改回去该用例不会变红。

**已撤回票17 的勾选**，并按复审意见重做用例 `test_the_shared_budget_run_completes_while_queries_overlap_the_heartbeat`：播种 12 天 DR007 缺口与检索密钥、劫持 `search_discovery.urlopen`，心跳间隔压到 0.2 秒与运行全程交错，另起查询线程持续调用 `audit_lease`、`runs.get` 与 `source_claim_acquisitions_many`。断言：查询实际重叠（>20 次）且**零锁错误**；运行 completed；**共享预算实测 `{"tavily": 8, "exa": 4, "ai_websearch": 0}`**，两家请求数各为 8 与 4；投影身份与运行记录一致；顺序严格为 `heartbeat_started → heartbeat_stopped → lease_released`，释放的 owner 为本进程，事后租约为 `absent`。该文件 4 项通过/126.1秒。

注：期间试过让邻居持锁 6.5 秒以强制心跳阻塞，但那会同时饿死运行自身的写入（运行直接以 `database is locked` 失败）——说明这种强度的争用下运行本就无法完成，与工单"交叠时完成共享预算用例"的要求不符。阻塞式心跳竞争由本文件第一个用例单独覆盖。

## 第二轮两轴复审（2026-09-17）

返工后重跑两轴，固定点 `56d47cd`（=`9d44c7d~1`），11 个提交。两轴都仍有发现，已全部处理。

**需求轴的裁定**：line 31 该项**已达成**。三条缺口逐条核对——共享预算跨期硬预算确实被用尽（`tavily 8/8`、`exa 4/4`、12 天 DR007 缺口）且心跳每 0.2 秒与之交错，不再是"只播核心历史"；顺序严格为 `heartbeat_started → heartbeat_stopped → lease_released`，`worker.py` 确实先 join 再释放；第三条（共享预算用例的变异变红）**不属于 line 31 的要求**——该子句要的交叠是心跳⟷查询，而"修复仍成立"由第一个用例及其变异检查承担。

但需求轴同时指出两处必须先改，其中第一处正是上一轮被否的同类问题：

1. **用例名与文档串在说谎**。名字叫 `..._while_a_writer_blocks_the_heartbeat`、docstring 写"邻居持写锁超过忙等，心跳确实失败并重试"——**该用例里根本没有写入者**，`beats` 收集了却从未断言。已改名为 `test_the_shared_budget_run_completes_while_queries_overlap_the_heartbeat`，docstring 如实说明为什么故意不放阻塞写入者（放了会连运行自身的写入一起饿死，而本子句要求运行**完成**），并把收集项改名 `contended` 且**显式断言为空**——这轮交叠不足以让心跳重试，说出来比留着不说诚实。
2. **幻影状态 `released`** 仍留在第四个用例与本记录里。`audit_lease` 没有这个状态，且租约从未获取也会通过。两处都已改为 `== "absent"`。
3. 需求轴另指出：非锁 `OperationalError` 在心跳线程里直接重抛，**又变成静默死亡**——正是被修掉的那个形状。已在重抛前写 `lease_heartbeat_failed:<错误>` 运行期事件。

**标准轴的发现**，逐条核实后处理：

| 发现 | 核实 | 处理 |
|---|---|---|
| `runs.py` 四处硬编码 `120`，与 `worker.LEASE_VALID_SECONDS` 无关联 | 真。租约有效期分居两模块，改一处会静默错开放弃阈值 | `LEASE_VALID_SECONDS` 移到 `runs.py` 并由 worker 导入；四处硬编码替换 |
| `detail = f"...{type(error).__name__}"` 恒为常量 | 真。`except` 已收窄到 `OperationalError` | 改记实际错误消息 |
| `_ClaimFamily.name` 从未被读 | 真，`grep` 零使用 | 删除该字段与 9 处传参 |
| `.gitattributes` 漏覆盖 `core-transport-196/*.json` | **假**。`git check-attr` 显示已 `text: unset`，该目录自带属性文件 | 不改；但由此发现真问题↓ |
| 根 `.gitattributes` 是第三套机制 | 真。仓库早有 23 个逐目录 `.gitattributes`，我那两行对应目录都已自带 | 删去重复的两行，只留 `evidence-*` 兜底并写明逐目录文件仍是显式形式 |
| `held_write(database, seconds)` 参数名误导（实为 `release.wait()` 超时） | 真 | 改名 `max_seconds` 并写明它只是兜底 |
| `order` 在闭包之后才定义 | 真，能跑但读起来像 bug | 提到闭包之前 |
| 测试间重复（相关子查询 SQL、`page_offline`、脚手架） | 真，判断项 | **本轮不动**。冻结全套即将开跑，此时重排测试脚手架会让两小时的同版本证据作废；记为待办 |
| `on_contention` 仅测试使用 | 判断项 | 保留：顺序断言需要它，运行期事件无法给出"第几拍" |

静态检查：`ruff check src tests` 通过，`ruff format --check` 我改的 5 个文件通过（仓库另有 13 个文件与当前 ruff 版本有既存差异，非本批引入），`mypy src` 96 源文件通过。

**据此勾选票17 line 31**，并在票上写明勾的是哪几句、不含哪句。line 33（同版本关联回归、默认全套、两轴复审与前后指纹）**仍未勾**——本批的 `search_evidence.py` 重构改动了热路径，2026-09-16 那份全套回执绑定的冻结树已失效，须按 [任务D 冻结参数](plan-taskD-frozen-suite-20260917.md)在 HEAD 上重跑。

## 完整链路验证（2026-09-17 补）

票17 该项还要求"经公开任务提交 → 持久任务 → Worker 执行 → 投影与状态查询"全链路验证，已补上第三个用例 `test_a_run_under_write_contention_still_publishes_and_reports_its_state`：

- 经 `submit_manual_full` 提交公开任务，确认持久任务状态为 `queued`；
- 运行期间另起一个邻居写入者，每 0.05 秒抢一次写锁并持有 0.2 秒，贯穿整个 `process_pending_run`；用例断言邻居确实抢到过锁（`grabs > 0`），避免"碰巧没撞上"被当成通过；
- 运行结束后核对：状态 `completed`、投影集已发布、当前投影身份与运行记录一致、目标交易日正确；
- 心跳退出与连接释放顺序：运行结束后租约不再被任何 owner 持有（`absent`）。**注（2026-09-17 更正）**：此处原写作 `absent`/`released`，而 `audit_lease` 并不存在 `released` 这个状态——那是我凭印象写下的幻影状态，且"从未获取过租约"同样会是 `absent`，所以单靠这条断言不足以证明顺序。顺序本身由下一节重做的用例显式断言。

该文件当时 3 项通过/61.6秒（按时间顺序：2 项 → 3 项 → 4 项，每次新增一个用例；本文件各节记的是各自当时的数字，最新结论见下节）。变异检查（把锁错误改回"即刻退出"）仍使心跳竞争用例失败。

## 范围

票17 该项的公开反例与全链路验证均已具备（含复审要求的共享预算争用场景）。**当前仍为未勾**，是否勾选由票17 的收口批次统一判断——该项原文还含"慢关闭已复现机制的修复仍成立"，其历史机制的持锁身份按 273 方案评审属无法从现存证据确认，本记录不代为勾选。
