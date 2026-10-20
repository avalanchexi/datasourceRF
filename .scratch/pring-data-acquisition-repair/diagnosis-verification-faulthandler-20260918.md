# 当前完整验证的原生线程栈计时器崩溃

2026-09-18，Python 3.12.12 / pytest 8.4.2 / WSL2。此记录属于 #22 验证执行安排，不修改产品行为或降低测试门。

## 原始失败与现场

`verification-current-full-20260918.json`：1848 项完整默认发现，前四项通过，第五项 Worker False 尚未完成，在 180 秒线程栈输出中 SIGSEGV，退出 -11；3181.21 秒为整批单调时间。冻结源、测试、安装、依赖身份前后相同，监督器未触发资源/时间终止；`verification-current-full-descendants-20260918.json` 已 finished、残留为空。失败库保留在 `/tmp/datasourceRF-current-verify-20260918-v2/pytest/test_integrated_worker_preserv0/runtime`。

内核记录和二进制符号见 `verification-faulthandler-kernel-20260918.txt` / `verification-faulthandler-symbol-20260918.txt`：原始及最小复现均在 `dump_frame+0x1e` 地址 0x49d07e，R15=0，指令解引用 0x70(%r15)。原始日志中断于 `  File `。崩溃发生在打印 Python 栈的原生 watchdog 路径，不能归因为 Worker 断言失败或 OOM。

## 反馈环与对照

命令：`/home/tywin/.local/share/pring-cycle/dev-venv/bin/python .scratch/pring-data-acquisition-repair/verify-faulthandler-minimal-20260918.py`。

公开 stdlib 最小负载只进行 30000 次 `sqlite3.connect(":memory:")` / `close()`，没有项目导入、Worker、pytest 插件或清理器。

- 开启 `faulthandler.dump_traceback_later(.0001, repeat=True)`：3/3 退出 -11，0.112 / 0.148 / 0.116 秒。
- 相同负载关闭计时器：3/3 完成，0.432 / 0.434 / 0.417 秒。
- 相同负载由普通 Python 线程调用 `sys._current_frames()` 打印栈：3/3 完成，0.644 / 0.710 / 0.702 秒，实际产生采样。

原始一般函数循环 3/3 没复现；加入 SQLite 创建/关闭后约 0.12 秒复现，再缩减为只创建/关闭连接仍稳定触发。完整载荷、退出码、二进制身份、日志哈希及控制记录在 `verification-faulthandler-minimal-20260918.json`；初始探索记录保留。负载与诊断均为独立复现，不添加到产品测试套件。

假设按顺序为：原生 watchdog 无锁读取瞬变栈；SQLite 自身崩溃；WSL 环境因素。对照把触发因素定位到该解释器的原生计时诊断与 SQLite 创建/关闭组合；并未证明其他平台全部安全或已找到上游同一修复。

[CPython 官方 issue 140815](https://github.com/python/cpython/issues/140815) 记录了类似 faulthandler 无效/已释放帧崩溃，仅作机制参考，不把它当作本机版本的确证。判定依据是本机负载、二进制地址和对照。

## 当前修正与后续验证

v3 监督驱动复用 v2 完全相同的冻结 project/site，运行前后检查身份；仅取消自加的 `faulthandler_timeout=180`（恢复为0），改用普通 Python 线程每30秒记录节点进度，超过180秒记录不含局部值的栈。独立进程仍每30秒检查 C 盘和4小时上限，保留有界进程组关闭及脱离进程组子进程监督。

新观察器自检 `verification-current-observer-v3-selfcheck-20260918.json` 验证真实 SQLite 工作、采样输出和 session_finished。Standards 只读审查阻断项0。v3将完整默认发现全部测试，优先重验原 False 场景；仅把 legacy 强制冷构建提到其材料消费者之前，避免同批重复冷构建，不改变用例或断言。最终必须收完整结果才能声称软件验证完成；v2原始失败收据不覆盖。

Spec复核另指出v3驱动未强制比较重新计算的材料身份与v2相同。收到时v3已启动，随即独立运行断言：全部依赖环境、两profile key/完整identity与v2相等，acquisition-repairs缓存存在，保存于 `verification-current-full-v3-reuse-precheck-20260918.json`。名称含precheck但实际为启动后补核；不改运行中脚本、不重复启动，后续驱动需把此门前置。

后续Standards复审的异常收尾和实际解释器/依赖核验已补齐；money新监督可追踪脱离session子进程，真实自检见 `verification-command-supervisor-selfcheck-20260918.json`。两轴剩余阻断项0，实际后续验收仍由串行队列等待v3成功后执行。

原始未缩减场景的复验：v3原Worker False节点setup/call/teardown均passed，call 829.37秒；两个目标日均completed，各有投影/报告。该节点通过后按已通过临时副本规则回收。原SIGSEGV场景得到GREEN，产品/测试/解释器版本保持，改变项仅为诊断监督。全套其余节点仍在运行，未声明全部通过。
