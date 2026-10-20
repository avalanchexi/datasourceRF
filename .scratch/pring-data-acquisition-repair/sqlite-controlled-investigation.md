# SQLite 真实运行路径诊断

状态：**第136批原用例观察和第138批受控交叠均已结束，未复现原锁错误。** 锁问题仍未关闭，未修改 SQLite 生产逻辑、WAL 模式或超时。第139阶段另行实施已取得 RED 的 Q1 映射，不将该业务修复算作锁修复。

**144新增能力核查，尚未执行原生锁探针：**[研究报告](sqlite-native-capability-research-144.md)实际核对独立Python3.12.12内置SQLite3.50.4、固定source_id和解释器哈希。已有strace5.16支持真实syscall返回后的延迟与调用栈；gdb未安装。下一步先在专属隔离runtime追踪真实 `heartbeat_lease` 最后连接关闭，不注入错误/返回值；确认主数据库EXCLUSIVE成功及关闭checkpoint I/O后再选可控边界。同进程线程应避免在 `unixLock` 持inode mutex的fcntl返回处暂停；跨进程校准不能冒充原Worker线程复现。恢复边界仍无已验证停点。该研究没有修改应用、依赖或共享服务，也不证明第59批根因。

## 反馈边界与现有证据

- 第59批默认全套的原失败来自完整任务的初始缺口计划：`process_pending_run → FullRunRetrieval → ModelInputSelector → CoreInputValidator → EvidenceRepository.source_claim_acquisitions_many → 开连接设置WAL`。报错位置不等于根因。见[原日志](verification-interbank-full-59.txt)。
- 第64/65批并发读取/审计写入没有复现；第135批控制服务心跳写事务保持未提交，原件查询成功，也不足以证明修复。见[135事件及实际结果](verification-closure-progress-135.json)。
- 当前源码明确区分两种心跳：`record_worker_heartbeat`写服务状态；完整运行内部另起`pring-run-lease-heartbeat`线程，每30秒调用`RunRepository.heartbeat_lease`写任务租约。135只覆盖前者，不能作为后者或完整Worker的成功证明。依据：[worker.py](../../src/pring_cycle/worker.py)、[runs.py](../../src/pring_cycle/runs.py)。

## 第136批实际做法

重用原`tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods`，由内层pytest正常加载原conftest、原时钟fixture及外部搜索替身。保留原取数、完整运行、预算和结果断言；它使用旧model-v0001，因此只用于重现原运行故障，不证明新注册目录Worker通过。

诊断插件仅在该用例call阶段观察Python sqlite3连接：记录单调时间、逻辑连接编号、线程、事务状态、操作类别、关闭耗时；发生OperationalError时保存错误码、活动连接、最近512条事件和调用栈，不打印SQL参数或凭据。未改变线程调度、SQL、WAL模式或原5秒等待设置。该观察器会有额外开销，未复现时不能证明自然运行也无问题。

[外层诊断启动器](verification-runtime-failures/debug/test_sqlite_original_136.py)只负责在现有仓库专属ext4测试目录内执行原用例；[观察器](verification-runtime-failures/debug/sqlite_original_runner_136.py)及原测试分别保留。诊断文件位于明确debug目录，不属于默认产品回归。

[前验](verification-sqlite-runtime-before-136.json)核91安装源码、53依赖、230绑定输入和4受保护文件；生产仍与已验收P2版本一致，唯一既有测试变化是已知RED的Q1测试，另加2个本次诊断文件。[输入清单](verification-sqlite-inputs-136.json)明确变化范围。

该批使用[持久执行器](verification-sqlite-durable-136.py)，历史[运行状态](verification-sqlite-running-136.json)绑定 PID149389、启动 ticks294805。已有[实际终态](verification-sqlite-terminal-136.json)：2026-09-10 01:12:07 UTC 结束，外层 1 passed / 128.42 秒，pytest 和后验退出码均为 0。内层原用例 exitstatus=0，观察记录 errors=[]；68429 次打开与关闭、最多 2 个受观察连接。该统计不覆盖未经过观察器的连接，也不是锁根因。

[根核验139](verification-closure-progress-139.json)重新核对终态各阶段的真实退出码、日志哈希与字节数、内层事件及后验；后验仍为 230 冻结输入、4 受保护文件、91 安装源码及 53 依赖一致。[日志](verification-sqlite-joint-136.txt)保留实际结果，不能将 scoped pass 改写为原全套失败已关闭。

## 第137/138批受控关闭交叠

[137](verification-sqlite-close-137.txt)在进入观察器之前因 fixture 未给定 targeted_refresh 所需 scope 失败：`retrieval_scope_required`，1 failed / 10.85 秒。归类为测试准备错误，原文件及日志保留。

[138](verification-sqlite-close-138.txt)改用合法公开 `submit_manual_full` 创建任务和租约。真实 `heartbeat_lease` 连接提交后即将关闭时，与原件查询即将执行 `PRAGMA journal_mode=WAL` 的起点用 Barrier 对齐，100 轮完成、无失败；外层 1 passed / 16.30 秒。它没有固定 SQLite 内部取得排他锁与释放锁的区间，因此未复现不能否定关闭清理冲突。该诊断未执行完整 Worker，也不证明新目录入口通过。

## 构造下一复现场景的一手依据

[SQLite WAL 文档第9节](https://sqlite.org/wal.html#sometimes_queries_return_sqlite_busy_in_wal_mode)说明：最后连接关闭时的WAL清理，以及异常退出后的恢复期间，新连接查询可能返回SQLITE_BUSY。[忙等待回调文档](https://sqlite.org/c3ref/busy_handler.html)说明：忙等待回调并不保证被调用，SQLite可为避免死锁直接返回BUSY。

这些是2026-09-10读取的官方机制说明，仅用于选择下一步受控交叠场景。它们没有证明原错误来自关闭、恢复或死锁，也不能支持直接增加超时、移除WAL设置或升级依赖后宣称问题已修。先读取136的实际事件，再选择可以复现同一报错路径的最小场景。

## 关闭条件

仍按[票17](issues/17-full-run-gap-retrieval.md)：捕获并区分实际根因，建立可复验反例，修复后原完整运行路径及任务/租约心跳/查询交叠通过，并在最终同代码版本完成关联回归、默认全套和后验。软件完成与真实来源/完整候选/120日/AI/切换分别验收；当前均不因本诊断升级状态。
