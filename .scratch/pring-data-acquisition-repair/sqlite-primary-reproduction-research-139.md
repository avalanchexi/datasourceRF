# SQLite 3.50.4 原错误路径的受控复现研究（139）

记录日：2026-09-10。性质：只读研究及待执行方案；**未运行诊断测试，未修改产品代码、SQL、超时、依赖或共享环境，原 SQLite 缺陷仍未关闭。** 本文只新增这一份 Markdown。

建议下一步先用独立进程的 POSIX 字节范围锁，校准原 `EvidenceRepository.source_claim_acquisitions_many` 入口确实能够记录“等待后 BUSY”；然后针对实际关闭锁或恢复锁建立原生边界观察。前者可以只用现有 Python 标准库实现，但属于同类故障校准，不能把它认定为第 59 批根因。**现有 `Connection.close` 前置 Barrier 不能停在 SQLite 已取得关闭清理锁的时刻。** 因而不建议继续扩大相同 Barrier 的随机轮数。

## 1. 已有证据支持到哪里

| 证据 | 本文复核结果 | 不支持的结论 |
| --- | --- | --- |
| [59 原日志](verification-interbank-full-59.txt) | 原用例由 `process_pending_run → FullRunRetrieval.retrieve/_plan → ModelInputSelector → CoreInputValidator → EvidenceRepository.source_claim_acquisitions_many` 进入 `_connect`，在 `PRAGMA journal_mode=WAL` 报 `database is locked`；全套 1146 通过、2 失败 | 日志没有原错误的扩展错误码、该语句耗时及锁持有者，不能判定锁类型。旧诊断文档中的 `FullRunRetrievalCoordinator` 应以栈里的实际类名 `FullRunRetrieval` 为准 |
| [135 事件](verification-closure-progress-135.json) | 服务心跳 INSERT 未提交时，原件查询已完成；没有复现 | 只控制服务心跳，不能代表任务租约或关闭清理 |
| [136 事件](verification-sqlite-original-events-136.json)、[终态](verification-sqlite-terminal-136.json) | 原用例观察运行 `exitstatus=0`，外层测试及后验退出码均为 0；68429 次观察连接打开及关闭，最大观察同时连接数 2，错误列表为空 | 不证明缺陷消失；计数只覆盖观察器接入的调用，不代表所有驱动或进程。最近 512 条事件不足以反推整次租约线程活动次数 |
| [138 脚本](verification-runtime-failures/debug/test_sqlite_close_overlap_138.py)、[日志](verification-sqlite-close-138.txt) | 100 轮任务租约心跳与查询交叠通过，循环 2.637409379 秒，测试总耗时 16.30 秒 | writer 停在 `super().close()` 前，reader 停在 `super().execute(PRAGMA...)` 前；屏障控制的是两个 API 的起点，没有证据证明 reader 遇到了 native EXCLUSIVE 锁 |

[现有诊断说明](sqlite-controlled-investigation.md)读取版本仍把 136 写成运行中；本文采用实际终态，并不改写旧记录。[storage.py](../../src/pring_cycle/storage.py)用新的 `sqlite3.connect`，在上下文退出时提交/回滚，再关闭；[evidence.py](../../src/pring_cycle/evidence.py)和[runs.py](../../src/pring_cycle/runs.py)每次连接均设置 WAL。`heartbeat_lease` 的实际写入是 `UPDATE worker_lease`。

CPython **v3.12.12** 的连接初始化默认 `timeout=5.0`，并调用 `sqlite3_busy_timeout(timeout*1000)`；因此不能把 C API 文档所说“默认 busy handler 为空”直接套到本项目 Python 连接上。[CPython 固定版本源码](https://github.com/python/cpython/blob/v3.12.12/Modules/_sqlite/connection.c#L195-L247)

## 2. 必须区分的机制

| 机制 | 一手依据与可观察差异 | 对原错误的意义 |
| --- | --- | --- |
| 普通 WAL 写事务 | WAL 允许普通读写并行；另一个写入者可能等待已有写事务。[WAL 并发说明](https://sqlite.org/wal.html#concurrency) | 仅保持心跳 UPDATE/INSERT 未提交，并不是让新读连接必然报锁的充分条件；135 的成功与此一致 |
| 最后连接关闭清理 | `sqlite3WalClose` 先尝试数据库文件 EXCLUSIVE 锁，再 checkpoint 和清理；锁到函数返回仍保持。[3.50.4 wal.c](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/wal.c#L2345-L2405) | `close_start` 不是“已取得 EXCLUSIVE”。若新连接先进入读锁，关闭方还可能没有取得这把清理锁 |
| WAL 恢复竞争 | 官方测试 `wal3-5.*` 在恢复者的 `xShmBarrier` 内启动第二连接，断言其查询得到 `database is locked`；测试说明区分 `SQLITE_BUSY_RECOVERY`。[3.50.4 wal3.test](https://github.com/sqlite/sqlite/blob/version-3.50.4/test/wal3.test#L231-L318) | 是已有一手最小复现，但依赖 `testvfs`，不是当前标准 Python 观察器可直接运行的测试 |
| 等待型 BUSY 与立即失败 | pager 的 `NO_LOCK → SHARED` 路径使用 busy handler；部分锁升级不使用。WAL 恢复也不是普通写锁等待。[3.50.4 pager.c](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/pager.c#L3500-L3519) | 时间及扩展码必须一起记录。瞬间 BUSY 不等于“超时太短”，也不自动等于死锁 |
| 死锁规避／旧读快照升级 | busy handler 文档给出回滚模式读锁升级与另一写者互等的例子；`BUSY_SNAPSHOT` 则是 WAL 旧快照升级写入问题。[busy handler](https://sqlite.org/c3ref/busy_handler.html)、[错误码](https://sqlite.org/rescode.html#busy_snapshot) | 本路径是新建连接、尚未执行证据 SELECT；不能用另造“先 SELECT 再 UPDATE”的失败证明此处根因 |
| 真的切换 journal mode | `OP_JournalMode` 只有旧、新模式不同且涉及 WAL 时才进入格式转换分支。[3.50.4 vdbe.c](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/vdbe.c#L7588-L7667) | 报在 `PRAGMA journal_mode=WAL` 不代表每次都发生模式切换；语句准备/首次读取也可能遇锁 |

官方 WAL 文档明确列出最后连接清理与异常退出后的恢复都可能使新查询 BUSY；它只证明机制存在，不证明本项目已发生哪一种。[官方边界](https://sqlite.org/wal.html#sometimes_queries_return_sqlite_busy_in_wal_mode)

## 3. 三个可证伪假设

以下按本项目路径的调查优先级排序，均未被证实。

1. **H1：新查询在真实关闭清理期间遭遇数据库文件锁，等待耗尽。** 预测是查询进入点与已成功取得的数据库 EXCLUSIVE 锁重合，锁持有者处于关闭阶段；若捕获到等待约默认 5 秒、锁一直未释放，会支持这一版本。若实际失败为扩展 `BUSY_RECOVERY`，或完整 native 记录显示根本没有数据库锁冲突，则否定这一具体解释。136 的两个慢关闭约 80/129 毫秒不说明原运行有 5 秒锁持有。
2. **H2：新查询遇到 WAL-index 恢复者，返回恢复竞争错误。** 预测是原失败带 `SQLITE_BUSY_RECOVERY`（扩展值 261）并有恢复锁活动；需要异常退出／恢复入口证据或原生锁路径。若只记录到数据库读锁超时而没有 WAL 恢复路径，则该次失败不支持此假设。正常关闭之后仅看见 WAL 文件并不能证明恢复发生。依据为上表官方恢复测试及[错误码定义](https://sqlite.org/rescode.html#busy_recovery)。
3. **H3：实际失败连接并非预期的新建、已持久 WAL、无事务状态，进入了模式转换或锁升级。** 预测是失败前存在模式不同、连接复用、读事务或其他驱动预处理证据。若精确连接记录证明新连接没有先前 SQL／事务，且数据库及 native 路径确认始终 WAL，则否定这一解释。它目前优先级最低；不能为了复现它而修改产品 journal mode。

单纯“普通 WAL 心跳写事务挡住新读者”不列为第四个假设：它缺少锁转换／关闭／恢复等必要附加条件，上述 135 已给出合法反例。三个假设均需要原故障证据，人工制造一个同样的错误字符串无法选择其中之一。

## 4. 优先方案：同一公开入口的可控锁校准

这是**待执行设计**，本研究没有执行，也不提前声称在该二进制上一定得到预期栈。使用现有独立 Python 3.12.12 / SQLite 3.50.4、仓库专属 ext4 临时 runtime，沿原公开方法调用，不改产品 SQL、`timeout`、busy handler 或依赖。

1. 初始化一个全新独立 runtime，关闭初始化连接，先证明 `EvidenceRepository(database).source_claim_acquisitions_many(("absent",))` 返回 `{"absent": ()}`。保存 schema、解释器/SQLite 版本及输入绑定。该正例结束后关闭其连接。
2. 另起独立进程，通过 `os.open(..., O_RDWR)` 和 **`fcntl.lockf`**，在同一个数据库文件的锁字节区间 `[0x40000000, 0x40000200)` 持有排他 POSIX 锁。这里仅加字节范围锁，不写数据库字节、不改 WAL/SHM 文件，也不使用 `flock` 替代。`os.h` 定义 PENDING 默认在 1 GiB、RESERVED 在后一个字节、SHARED 区间为随后 510 字节；Unix VFS 的 `unixLock` 使用 POSIX 锁。[锁区定义](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/os.h#L110-L160)、[Unix VFS](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/os_unix.c#L1627-L1778)、[Python lockf](https://docs.python.org/3.12/library/fcntl.html#fcntl.lockf)
3. 子进程拿锁成功后才通过 pipe 发 READY；主进程再调用**同一个公开方法**。长持有场景保持锁直到 reader 已返回，另设有界看门狗释放，避免以猜测 sleep 控制开始。记录错误发生的确切操作、起止单调时间、`sqlite_errorcode`、`sqlite_errorname`、连接与持锁 PID。预期在首次数据库读取期间约默认等待后得到 BUSY；必须实测确认是否仍落在本项目 `PRAGMA` 行。
4. 同样条件下增加“提前释放”对照：reader 已进入原 `set_wal` 观察边界后，让辅助进程在明显小于默认 5 秒的固定短间隔释放，并记录实际释放时间。预期查询随后成功。边界只用于发出开始事件，不插入第二条预热查询；若调度延迟使持有超过目标间隔，该轮按准备不合格处理。
5. 每个场景保存辅助进程退出码及锁释放确认，再用全新连接确认原公开查询仍成功。只处理该临时 runtime；生产数据库、共享 Worker/Web 和其他测试运行不参与。

独立进程是必要隔离：Unix VFS 在同进程内部另有 inode 锁状态协调，直接在同一进程混用 POSIX 锁不等价于外部竞争。默认 Unix VFS/锁区的适用性应随运行元数据记录；不能据版本号假定所有编译参数或自定义 VFS 相同。[Unix VFS 实现](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/os_unix.c#L1627-L1722)

这个方案的关闭条件只是“诊断能区分无锁成功、锁持续等待失败、释放后恢复”。**即使全部满足，它仍是外部锁的同类故障校准，并未复现任务租约的实际清理逻辑，更未修复原缺陷。** 它能防止以后用不经过真正 SQLite 锁冲突的 monkeypatch 异常，冒充锁反例。

## 5. 真正清理／恢复复现需要什么边界

| 目标 | 现有 Python 连接观察器能做 | 现有观察器不能保证 | 最小进一步能力 |
| --- | --- | --- | --- |
| 普通写事务交叠 | 实际 UPDATE 返回后、提交前停住；协调另一个公开查询；观察提交和关闭耗时 | 判断 SQLite 内部持有的具体文件/WAL 锁 | 无需新增能力即可作为负对照；已有 135 不必重复扩大轮数 |
| 实际最后连接清理 | 保证没有别的已用连接，控制 `close()` 起点；记录结束 | 在 `sqlite3OsLock(...EXCLUSIVE)` **成功之后**、释放之前停住；确认“最后一个有效 native 连接” | 针对同二进制的原生函数或 VFS `xLock` 返回边界观察；只暂停该独立测试连接的清理，并用事件放行 reader |
| WAL 恢复 | 在独立子进程创建正常已提交 WAL 后异常退出，准备恢复输入；控制新连接起点 | 让恢复者已拿恢复锁且未完成时再启动 reader；只增加 WAL 大小仍是概率放大 | 官方 `wal3-5.*` 展示 `xShmBarrier` 内启动第二连接的明确边界；同二进制需能观察该边界的 native/VFS 工具 |
| 锁升级／模式变化 | 记录新建连接参数、`in_transaction`、实际 SQL 操作序列 | 从 `in_transaction` 一项还原 pager 内部锁状态；从错误字符串断言死锁 | 捕获具体 native 调用路径或足够的实际事务/模式转换证据 |

Python 标准接口的 trace callback 面向实际执行的 SQL，progress handler 面向 VM 指令；没有文档承诺“关闭清理拿锁之后回调”。所以不能把 trace/progress/`close` 子类包装称为 VFS 锁边界。[Python 接口](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.set_trace_callback)、[SQLite VFS 方法](https://sqlite.org/c3ref/io_methods.html)

本机是否已有可用 native 调试器、符号、VFS 测试扩展及附加权限，**本次未探测**；没有安装/编译/替换它们。不要通过未验证的 CPython 对象地址或 `ctypes` 私有内存布局，声称标准连接已有稳定 VFS 钩子。官方 `wal2-3.*` 旧段落在 `if 0` 内，不能引用它当该版本实际运行的通过证据；本研究选择可见启用的 `wal3-5.*` 作为恢复边界示例。[官方 wal2.test](https://github.com/sqlite/sqlite/blob/version-3.50.4/test/wal2.test#L231-L299)

如本轮仅允许现有 Python 观察器，就完成一次第 4 节校准后保留 H1/H2 未决，继续独立的确定缺陷修复。真正根因验收需要捕获 native 交叠或原失败事件；相同 API 屏障再跑更多次不能替代这个条件。

## 6. 读取输入绑定及交付边界

下表为本研究读取的仓库输入字节 SHA-256；路径相对仓库根。仅读取相关源码段落、原日志故障段及 JSON 的诊断字段，不宣称逐行审计整个文件。`CONTEXT.md` 与 ADR 仅用于沿用单机 WSL、单 Worker 及任务语义。没有依据历史记忆推断运行状态。

| 输入 | 字节数 | SHA-256 |
| --- | ---: | --- |
| `AGENTS.md` | 348 | `2017fb00f48480bf657af3e41fe00b27b3a9bddce63b734c9a471c898f4c81c0` |
| `CONTEXT.md` | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| `docs/agents/issue-tracker.md` | 1251 | `bf9cee64d67ac3eb972a341572f481a115c985ee4a579225a854ff3e0e81502c` |
| `docs/agents/domain.md` | 904 | `dfb45dbbc2c1bf3f1bd8ad5c6db249b4f2c6cc6587da4ec63cf75f002c477e9c` |
| `docs/adr/0007-wsl2-sqlite-worker-and-dash-fastapi.md` | 1127 | `691b8884190e26906aa30bdd5cc74b33f65ceb0213fb7aa1542c068253632b42` |
| `docs/adr/0010-manual-first-persistent-refresh-runs.md` | 854 | `d1a85a54f6f30b590b03b8fead633301ae1052e5a48b0c0bad25b938ef7b51a0` |
| `.scratch/pring-data-acquisition-repair/sqlite-controlled-investigation.md` | 4435 | `d67bc29aa46c3417f10337159e812f5fbfeb0d6478ff815a69c4c80364b27aa7` |
| `.scratch/pring-data-acquisition-repair/verification-sqlite-original-events-136.json` | 106022 | `5de603a4de2f15d33fadd032b12dd5781a7e9ce55abdf768c50769aa554ee862` |
| `.scratch/pring-data-acquisition-repair/verification-runtime-failures/debug/sqlite_original_runner_136.py` | 7280 | `adec8dfc550884d4ac1efff1bc2dd42d3998faa2fafa526f8b58032d706457bc` |
| `.scratch/pring-data-acquisition-repair/verification-runtime-failures/debug/test_sqlite_close_overlap_138.py` | 3269 | `5931773c534fd3e1cda4aa89317f372541679ba89c1e2f38be237b473f4dad01` |
| `.scratch/pring-data-acquisition-repair/verification-sqlite-close-138.txt` | 498 | `b8e9b9d6c16594ed33edc7139762ecba84e61a18e1a249fe242a3172f8f171ac` |
| `.scratch/pring-data-acquisition-repair/verification-sqlite-terminal-136.json` | 1286 | `0d67348ce0365d1bef3c76b3c5eb71b8e91d2b89bde3ab189a76aeac4859b31c` |
| `.scratch/pring-data-acquisition-repair/verification-closure-progress-135.json` | 9406 | `af683b6b26368016e7fd5cc19f7d7992652de15dd66306cc9105cbddf2c50da2` |
| `.scratch/pring-data-acquisition-repair/verification-interbank-full-59.txt` | 9322 | `e632768dd09cb2a976bdee854a0ce4c7dab6e65d90e361c3aff8e6cdf9c15dc4` |
| `src/pring_cycle/storage.py` | 7191 | `ef947dab6fc589e8efb4f121f77f4237566f23492cee6351ade035ea66874401` |
| `src/pring_cycle/evidence.py` | 61072 | `9301fcdaee83662c510e2ea51c043678d117ad8049b237b2873e5783de45627d` |
| `src/pring_cycle/runs.py` | 47927 | `ac2855a5ff75004084edd2ce9accb0acc1174884994f20d4001e186a3e0f5ef6` |

网页于记录日读取；SQLite、CPython 源码引用固定发布标签。本文未验证当前已安装 SQLite 二进制的 `source_id`、编译选项或 VFS，所以“标签源码对应具体二进制全部编译分支”仍是待核项。在线文档不能证明本地运行事实；本地日志不能证明官方机制已在原错误中发生。软件全套、真实来源认证、候选模型、120 日回放、AI 报告及切换均不因本研究升级验收状态。

交付前只读核对：10 个本地链接均存在；17 个绑定输入中，`sqlite-controlled-investigation.md` 与 `src/pring_cycle/evidence.py` 已相对读取快照发生变化，其余 15 个相同。主代理正在独立推进状态更新与 Q1 修复，本文保留实际读取版本的哈希，不把变化后的文件冒充已按该哈希审查；实施时须在最终版本重新确认相关入口。这不是冻结代码回归验收。
