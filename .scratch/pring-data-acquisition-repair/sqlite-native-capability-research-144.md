# SQLite 同二进制诊断能力核查（144）

记录日：2026-09-10。承接[研究 139](sqlite-primary-reproduction-research-139.md)。本次仅执行只读命令、内存数据库查询和 ELF 静态检查；**未创建/打开磁盘数据库，未执行项目测试，未安装或编译工具，未附加进程，未改变 SQL、超时、应用、共享服务或内核设置**。只新增本文件。

结论：现有环境具备进一步尝试受控关闭清理实验的工具条件，优先使用 **strace 5.16 的 syscall 退出延迟与调用栈**。但尚未实际跟踪或注入，不能称“已可稳定复现”。直接在 `sqlite3WalClose` 指令或恢复 `xShmBarrier` 上设函数断点的现成能力不足：gdb 未安装，标准 Python 接口没有这类回调。无需为下一步先安装 gdb，也不应换用系统 SQLite。

## 1. 实际解释器与 SQLite 构建

所有核查经 `wsl -d Ubuntu-22.04 -u tywin --cd /mnt/d/cursor/datasourceRF --exec`，使用：

```text
/mnt/d/cursor/datasourceRF/.tmp/venvs/pring-repair-20260909/bin/python -B
```

它解析到：

```text
/home/tywin/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12
```

只读 Python 探针使用 `sqlite3.connect(':memory:')`，执行 `select sqlite_version(), sqlite_source_id()` 和 `pragma compile_options`，关闭连接后查询模块元信息及 `/proc/self/maps`。没有导入 `pring_cycle`。

| 项目 | 实际输出 |
| --- | --- |
| Python | `3.12.12 (main, Dec 2 2025, 19:47:35) [Clang 21.1.4 ]` |
| 架构 | `x86_64-linux-gnu` |
| SQLite | `3.50.4` |
| source_id | `2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3` |
| `_sqlite3.__file__` | 无此属性；纠正后的 `getattr(..., None)` 得到 `None` |
| `_sqlite3` origin | `built-in`，且在 `sys.builtin_module_names` 内 |
| 实际链接布局 | SQLite 并入主 Python 可执行文件；该进程没有单独 `_sqlite3.so`、`libsqlite3.so` 或 `libpython` 映射 |

实际 `source_id` 与[SQLite 3.50.4 官方发布记录](https://sqlite.org/releaselog/3_50_4.html)一致。这补齐 139 对本地版本身份的待核项，但不能推导为原 BUSY 的根因已明。

实际 `compile_options` 完整输出如下，共 45 项；其中未出现 `ENABLE_SETLK_TIMEOUT`、`SQLITE_TEST` 或 `OMIT_WAL` 字样。这里只报告该 API 暴露的选项，不用缺项推断未公开编译配置。

```text
ATOMIC_INTRINSICS=1
COMPILER=clang-21.1.4
DEFAULT_AUTOVACUUM
DEFAULT_CACHE_SIZE=-2000
DEFAULT_FILE_FORMAT=4
DEFAULT_JOURNAL_SIZE_LIMIT=-1
DEFAULT_MMAP_SIZE=0
DEFAULT_PAGE_SIZE=4096
DEFAULT_PCACHE_INITSZ=20
DEFAULT_RECURSIVE_TRIGGERS
DEFAULT_SECTOR_SIZE=4096
DEFAULT_SYNCHRONOUS=2
DEFAULT_WAL_AUTOCHECKPOINT=1000
DEFAULT_WAL_SYNCHRONOUS=2
DEFAULT_WORKER_THREADS=0
DIRECT_OVERFLOW_READ
ENABLE_DBSTAT_VTAB
ENABLE_FTS3
ENABLE_FTS3_PARENTHESIS
ENABLE_FTS4
ENABLE_FTS5
ENABLE_GEOPOLY
ENABLE_MATH_FUNCTIONS
ENABLE_RTREE
MALLOC_SOFT_LIMIT=1024
MAX_ATTACHED=10
MAX_COLUMN=2000
MAX_COMPOUND_SELECT=500
MAX_DEFAULT_PAGE_SIZE=8192
MAX_EXPR_DEPTH=1000
MAX_FUNCTION_ARG=1000
MAX_LENGTH=1000000000
MAX_LIKE_PATTERN_LENGTH=50000
MAX_MMAP_SIZE=0x7fff0000
MAX_PAGE_COUNT=0xfffffffe
MAX_PAGE_SIZE=65536
MAX_SQL_LENGTH=1000000000
MAX_TRIGGER_DEPTH=1000
MAX_VARIABLE_NUMBER=32766
MAX_VDBE_OP=250000000
MAX_WORKER_THREADS=8
MUTEX_PTHREADS
SYSTEM_MALLOC
TEMP_STORE=1
THREADSAFE=1
```

## 2. ELF、依赖及符号

对上述**解析后的真实主程序**执行以下命令，退出码均为 0。完整输出由本次工具调用返回；本文保留与决策有关的摘要，没有另建原始日志文件。

| 实际命令 | 输出摘要 |
| --- | --- |
| `file <python3.12>` | ELF64 x86-64，动态链接，`not stripped` |
| `readelf -h <python3.12>` | `Type: EXEC`，不是 PIE 的 `DYN` |
| `readelf -d <python3.12>` | NEEDED 仅 `libpthread.so.0, libdl.so.2, libutil.so.1, librt.so.1, libm.so.6, libc.so.6`；没有 libsqlite3 |
| `ldd <python3.12>` | 与上述依赖一致；常规库来自 `/lib/x86_64-linux-gnu`，加载器 `/lib64/ld-linux-x86-64.so.2` |
| `readelf -S <python3.12>` | 有 `.symtab/.strtab/.dynsym/.dynstr`；没有 `.debug_*` 段；存在 `.bolt.org.text` |
| `readelf -n <python3.12>` | 有 `.note.bolt_info`，说明应用过 BOLT；不能把重新编译得到的地址用于当前程序 |
| `nm -an <python3.12>`、`readelf -sW <python3.12>` | 下列 SQLite 函数为本地 `t`／`FUNC LOCAL` 符号 |
| `nm -D <python3.12>` | 指定 SQLite 函数筛选结果为空；不能当动态导出 API 使用 |

```text
0x00b828a0 sqlite3_vfs_find
0x00b83940 sqlite3_vfs_register
0x00b9e150 sqlite3_busy_timeout
0x00ba0520 sqlite3_open_v2
0x00ba4b80 sqlite3_sourceid
0x00ba58a0 unixLock
0x00ba7070 unixShmBarrier
0x00bba2b0 sqlite3WalClose
0x00bba4c0 sqlite3WalCheckpoint
```

`objdump -d --disassemble=sqlite3WalClose <python3.12>` 显示：

```text
0x00bba2e6: mov $0x4,%esi
0x00bba2eb: call *0x38(%rax)
0x00bba2ee: test %eax,%eax
0x00bba2f0: jne <failure/exit branch>
...
0x00bba322: call 0x00bba4c0 <sqlite3WalCheckpoint>
```

这与公开 `sqlite3_io_methods.xLock` 的 EXCLUSIVE 参数及源码顺序相符：拿锁成功后再 checkpoint。[固定版本 wal.c](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/wal.c#L2345-L2409)、[公开 I/O ABI](https://sqlite.org/c3ref/io_methods.html)。这些地址仅是**此哈希主程序的静态观察**，本次没有执行地址调用或插入断点。

`objdump -d --disassemble=unixShmBarrier <python3.12>` 显示内存屏障及可选 mutex 调用，不是每次都有 syscall。因此 `strace` 无法以该函数名直接停在恢复时的指定 `xShmBarrier`。

## 3. 已安装工具及权限线索

先以 `shutil.which` 检查，再运行已有工具的版本/帮助和 `dpkg-query`；没有安装操作。

| 能力 | 当前结果 |
| --- | --- |
| gdb | PATH 未找到；dpkg 为 `unknown ok not-installed` |
| gdb-multiarch | dpkg 未找到；未搜索任意自定义工具目录 |
| gcc / cc | `/usr/bin/gcc`、`/usr/bin/cc`，都解析到 `/usr/bin/x86_64-linux-gnu-gcc-11`；实际执行版本 `11.4.0` |
| nm / readelf / objdump | 均在 `/usr/bin`，Binutils `2.38`；dpkg 包 `2.38-4ubuntu2.12` |
| strace | `/usr/bin/strace`，`5.16`，dpkg `5.16-0ubuntu3`；启用 `stack-trace=libunwind`、`stack-demangle`、`m32-mpers`、`mx32-mpers` |
| ldd / file | `/usr/bin/ldd`、`/usr/bin/file`，本次只读执行成功 |
| clang / bpftrace / perf | PATH 未找到；没有声称全文件系统不存在 |

`strace -h` 实际列出：

```text
-e inject=SET[:error=ERRNO|:retval=VALUE][:signal=SIG][:syscall=SYSCALL]
            [:delay_enter=DELAY][:delay_exit=DELAY]
            [:when=WHEN]
delay: microseconds or NUMBER{s|ms|us|ns}
```

只读安全元数据：`/proc/sys/kernel/yama/ptrace_scope=1`；本次 tywin 探针 `CapEff=0, NoNewPrivs=0, Seccomp=0`。Linux 文档说明 scope 1 的通常边界是跟踪后代进程；**本次没有启动被跟踪程序，所以这不是 ptrace 可用性的动态验证**。[内核 Yama 说明](https://docs.kernel.org/admin-guide/LSM/Yama.html)

## 4. 最小可行候选：现有 strace 的原生 syscall 边界

下一次仅对新建、明确归属本任务的独立测试进程启动 `strace`，不附加共享 Worker 或正在进行的回归。保留当前解释器哈希、现有 SQLite、真实仓库方法和默认等待；不添加 `error=`、`retval=` 或 `poke_*`，只延长指定系统调用退出到用户态的时间。

strace 5.16 文档支持 `delay_exit` 与按调用序号 `when=N`；源码先取得真实 syscall 结果，再安排退出延迟，随后记录 `(DELAYED)`。这不同于用 `error=EBUSY` 伪造失败。[5.16 手册](https://github.com/strace/strace/blob/v5.16/doc/strace.1.in#L1303-L1498)、[结果与延迟顺序](https://github.com/strace/strace/blob/v5.16/src/syscall.c#L502-L528)、[延迟计时实现](https://github.com/strace/strace/blob/v5.16/src/delay.c#L94-L126)

先做无注入轨迹，确定真实事件后，才选下面一种边界；本文没有给未经验证的固定 `N`。

### A. 实际关闭拿锁 syscall 退出：最容易定位，但先用于跨进程读者

1. 在隔离 runtime 准备合法租约，关闭准备连接；一个被跟踪的独立写者执行真实 `RunRepository.heartbeat_lease` 并关闭连接。
2. 用 strace 的 fd 路径、时间及 `-k` 栈，定位关闭阶段针对**主数据库 fd**的 `fcntl(F_SETLK, F_WRLCK, start=1073741826, len=510)=0`，栈应能关联 `sqlite3WalClose → unixLock`。不能把 RESERVED 字节、WAL 写锁或失败的 `F_SETLK` 当成这个事件。
3. 重建等价隔离条件，只在该 tracee 的该次 `fcntl` 加 `delay_exit`。真实返回码须仍为 0；辅助读者在已确认的延迟窗口内调用原 `EvidenceRepository.source_claim_acquisitions_many`。观察器必须保存错误码、阶段、起止、PID 和 inode，并确认写者仍在延迟中。
4. 设置长持有和短持有对照，等待时长保持产品默认值；各进程真实退出后重新读验证释放完成。迟到的读者、错序号、错误 fd、没有 EXCLUSIVE 成功或栈无法核验，都归为准备/观测不合格。

**这里的重要限制是进程内 mutex。** `unixLock` 的 `fcntl` 返回后，还要更新 inode 状态并执行 `sqlite3_mutex_leave(pInode->pLockMutex)` 才返回。如果在 fcntl 退出点暂停写者，同进程读者可能先卡在该 mutex，而非进入 SQLite busy 等待。所以 A 先使用独立 reader 进程，只证明真实关闭持有的 OS 锁能够影响同二进制的新读者，不冒充原 Worker 的线程交叠。[固定版本 Unix VFS](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/os_unix.c#L1782-L1834)

### B. 拿锁成功之后的关闭 checkpoint I/O：更贴近同进程线程，需先看轨迹

若无注入轨迹显示，在上述 EXCLUSIVE 成功之后、主数据库解锁之前，存在调用栈包含 `sqlite3WalClose/sqlite3WalCheckpoint` 的 `fdatasync` 或 `fsync`，可优先延迟**这个后续 syscall**。它位于 `unixLock` 已返回之后，避免 A 的 inode mutex 边界；同时需要证明确实是关闭 checkpoint，而不是此前事务提交的 WAL sync。

此方案有机会保持原“任务租约线程关闭／主线程查询”的同进程关系，但目前只是由源码顺序推导的候选：本次没有取得任何磁盘关闭轨迹。若实际关闭没有对应 I/O，不能声称 B 可用，也不为制造 I/O 而修改应用同步模式。strace 的注入序号按每个 syscall、每个 tracee 计数，线程及新进程可能改变序号；必须审查被延迟的实际 TID/调用，不可将上一轮 `N` 无条件复用。[源码关闭顺序](https://github.com/sqlite/sqlite/blob/version-3.50.4/src/wal.c#L2368-L2399)、[strace 计数规则](https://github.com/strace/strace/blob/v5.16/doc/strace.1.in#L1396-L1498)

上述两个方案是人为延长真实锁持有时间的诊断。即使产生 `database is locked`，也只把“该机制能够导致此错误”从静态推断推进到受控反例，**不能解释第 59 批在没有延迟注入时为什么发生**。最终仍要与原失败的错误扩展码、实际持锁阶段和耗时对应。

## 5. 恢复边界与不可直接使用的方案

- **恢复 `xShmBarrier`：** 现有标准 Python 与 strace 不能按函数名控制它。139 引用的官方 `wal3-5.*` 使用 SQLite 测试 VFS 回调，不是本机已发现的能力。可以另行研究“恢复锁成功 syscall 之后”的替代停点，但须先证明正在恢复而非普通写入；不能把任意 SHM 锁或 WAL 文件存在作为恢复证据。本次未制造异常退出或恢复输入。
- **gdb 函数/指令断点：** ELF 保留 `sqlite3WalClose` 等符号，可供未来兼容调试器定位；本机未安装 gdb，没有实现“停在 `0x00bba2ee` 且 EAX=0”这一能力。存在符号不等于已有调试器或断点实测。
- **VFS 包装：** SQLite 公共 ABI 有 `xLock/xShmBarrier`，但本构建的 `sqlite3_vfs_find/register` 是本地符号，不是动态导出；不能假设普通 `ctypes.CDLL(None)` 可按名称拿到。注册新的 VFS 包装需要额外实现及完整 ABI/生命周期验证，不是现成能力。[VFS 公共接口](https://sqlite.org/c3ref/vfs.html)
- **按 ELF 数字地址调用本地函数、改写函数指针或加载另一个 libsqlite3：** 本次没有这样做，也不将它作为最小方案。地址布局虽已观察，但这种做法增加二进制绑定与生命周期风险；加载系统 libsqlite3 更不能证明应用内置 SQLite 的行为。不依赖 CPython 连接对象私有内存布局。
- **gcc 已安装：** 只证明编译器可执行，不证明诊断辅助库已存在，也不授权把编译产物算作当前工具能力。本次未编译。

## 6. 命令边界、失败记录与文件哈希

执行载体为 PowerShell here-string 经 UTF-8/base64 传给上面固定解释器的 `-B -c`；只读工具调用使用 Python `subprocess.run([...], capture_output=True, timeout=...)` 传 argv，没有拼接 shell SQL。

本次保留两项准备错误：第一版探针访问 `_sqlite3.__file__`，在已关闭内存连接之后得到 `AttributeError`，由此发现模块为 built-in；一条初始 `/bin/sh` 工具枚举命令在 Windows 转义后出现 shell 语法错误，没有执行能力枚举。随后改用 `shutil.which` 和 argv 数组，核查成功。`dpkg-query` 退出码 1 来自 `gdb-multiarch` 缺包，已保留其 `gdb not-installed` 与其余包输出。它们均不是项目测试失败或 SQLite 锁失败。

读取及核查绑定如下；ELF 和工具路径为 WSL 路径。哈希按实际字节计算。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| 主解释器 `/home/tywin/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12` | 27808208 | `f2d0b657dc3f06685de256968bfacc9c0db1c2e4fa38a59785edd472f63dcf7d` |
| `/usr/bin/strace` | 1972848 | `38a5c75cb29dd85ddd7780d54f5bf595554d7a1b5c42524b23065f5dc4c4b01d` |
| `/usr/bin/x86_64-linux-gnu-nm` | 44672 | `ed6565c132d6f20019ff3f050043dc1b2b8bc2e8b3b94c1ffe3f34436431a5a4` |
| `/usr/bin/x86_64-linux-gnu-readelf` | 776640 | `04db0000749aff89e4af21429340b00b536fc6f80e811c872c006507881a5560` |
| `/usr/bin/x86_64-linux-gnu-objdump` | 373888 | `1eaaef2e7f57c4c7f69115c495e2466f5a8c8e5f3bc42221d092382f30f9d4cd` |
| `/usr/bin/x86_64-linux-gnu-gcc-11`（gcc/cc 同指向） | 928584 | `821af3c74506283c179ca413bb33e6b528805a4dd8a5c09df125e5ad560a9e89` |
| `.scratch/pring-data-acquisition-repair/sqlite-primary-reproduction-research-139.md` | 17095 | `142a00a77850975b7738fcc6a9498d366ea9d64f10d6c47823d459b87f1b7724` |
| `AGENTS.md` | 348 | `2017fb00f48480bf657af3e41fe00b27b3a9bddce63b734c9a471c898f4c81c0` |
| `docs/adr/0007-wsl2-sqlite-worker-and-dash-fastapi.md` | 1127 | `691b8884190e26906aa30bdd5cc74b33f65ceb0213fb7aa1542c068253632b42` |

源码持续由主代理推进 Q1 修复，本次没有重新审计或冻结应用源码。交付结论只包含**现有解释器身份、工具与符号能力，以及待验证的最小实验设计**；SQLite 原根因、软件最终全套及产品交付仍未收口。
