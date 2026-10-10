---
status: accepted
---

# SQLite WAL 使用 `synchronous=NORMAL`

2026-10-10 用户在分流票 29 时确认（[票 29](../../.scratch/lookback-fetch-gaps-20261008/issues/29-backfill-evidence-preload-and-wal-sync.md)）。

[ADR-0007](0007-wsl2-sqlite-worker-and-dash-fastapi.md) 让 SQLite WAL 保存唯一权威状态，但没有设定 `synchronous`，于是沿用 WAL 下的默认值 `FULL`：每次提交写事务都会 fsync 一次。票 24 合入连接池后重新剖析，同一节点一次完整运行有 7.1 万次 `commit`，自身耗时约 9.5 秒，约占剖析总时长的 8%；strace 记录到 10,953 次 fsync。

决定：所有连接到运行库和测试库的连接一律设为 `PRAGMA synchronous=NORMAL`。生产和测试使用同一设置，不分环境。

依据：在 WAL 模式下，`NORMAL` 只在检查点时 fsync，提交时不再 fsync。程序自身崩溃（进程被杀、异常退出）不会丢失已提交事务。断电或操作系统崩溃时，可能丢失最后几笔已提交事务，但数据库不会损坏。用户对时效的要求是 T+1，丢掉的最后几笔可以重跑补回。原件按内容寻址，最多多出无人引用的孤儿文件，不会出现引用了却找不到的原件。

放弃的方案：保持 `FULL`，耐久性最强，但每次提交都要承担 fsync 成本；只在测试中用 `NORMAL`，可以节省测试时间，但测试和生产的设置会不一致。

后果：断电后，任务账本最后几次状态转换可能回退，相应任务会被重新领取并重做，所以依赖 ADR-0007 的幂等追加。`synchronous` 是连接级设置，每条新连接（包括连接池新建的连接和 fork 后重开的连接）都要设置，不能只在建库时设一次。
