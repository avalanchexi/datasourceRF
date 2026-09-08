# SQLite 连接生命周期修复

2026-09-09；沿用已批准修复规格的公开查询/任务入口与最终回归要求，基点为 `3e1b7d3f4f2421fa72ee2e30ffbaefb11da03f8d`。本项是核心与仓单标准化消费批次在全套验证中发现的实际故障，不改变数据家族、认证、模型或业务规则验收范围。

## 原始故障与最小反例

[normalized-full-01](verification-normalized-full-01.txt)终态为1022通过、6失败、1错误，2028.77秒。五个检索台账测试和一个仓单上下文测试失败，另一个台账测试setup报错，异常为文件句柄耗尽及SQLite无法打开数据库。旧日志保留，不能追记为全绿。

新增公开 `RunRepository.create/submit/get` 反例，仅在独立子进程关闭自动循环垃圾回收并将文件描述符上限设为128；父pytest和系统设置不变。重复查询同一条已存在任务，两次分别在1.49秒和2.33秒复现数据库打开失败，见[初始RED](verification-connection-red-01.txt)与[移除完整初始化后的最小RED](verification-connection-red-02.txt)。该循环未使用网络、模型厂商API、生产数据库或内部仓库mock。

## 根因对照

在探测前已向用户列出三个可证伪假设：连接依赖GC释放、检索台账独有累积、数据库路径或存储异常。[三个隔离探测](verification-connection-probe-01.txt)显示：

| 探测 | 成功读取次数 | 后续结果 |
|---|---:|---|
| 详细任务读取 | 30 | 下一次数据库打开失败；GC后恢复 |
| 只读任务数量 | 61 | 下一次数据库打开失败；GC后恢复 |
| 每次详细读取后GC | 64 | 全部成功 |

三个子进程在GC后均回到5个描述符。探测排除了“仅台账累积”和“固定路径不可用”作为独立解释，支持各查询连接未明确关闭的共同根因。诊断原型保存在明确标记的 [debug目录](verification-connection/debug/test_resource_probe.py)，不进入默认测试集。

Python的连接上下文只负责事务提交/回滚，不负责关闭连接；这与本次代码和反例相符，见[Python 3.12官方说明](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager)。

## 实现与验证边界

`storage.database_connection`保留SQLite自身事务上下文，并在finally中关闭连接。9个仓库/模块的连接工厂、目录只读URI及其余直接连接读取/写入均使用这一作用域；各入口原有row factory、WAL、外键、忙等待和默认5秒超时保持。SQLAlchemy迁移仍自行关闭连接并dispose引擎。未引入连接池、GC调度或增大文件上限的生产补丁。

首轮任务与台账修复后，[最小反例及任务编排9项通过](verification-connection-green-01.txt)。扩大到证据、获取历史、模型清单、投影、报告、维护、切换状态和缺失目录后再次[RED](verification-connection-views-red-01.txt)，相应工厂修复后[两项通过](verification-connection-green-02.txt)。继续检查获取归属、完整检索计划、交易日历缺口与运行指纹时在直接连接路径[再次RED](verification-connection-direct-red-01.txt)，修复后[两项通过](verification-connection-green-03.txt)。两个测试累计覆盖不同公开入口，不能把循环次数当作独立测试数。

随后补充缺失任务异常与既有任务仍可读的同循环验证。[扩大回归](verification-connection-targeted-01.txt)完成**257通过、0失败、625.54秒**，包括事务中断、任务编排、检索台账、模型生命周期及候选准入。应用与两个测试文件mypy92、Ruff/格式22文件通过，两轴复审各0项。修复后的[默认全套](verification-connection-full-01.txt)完成**1031通过、0失败、2975.70秒**，主会话37371最终退出码0。运行前后90安装Python源码匹配，22个冻结输入的字节哈希未变；[检查点](verification-connection/checkpoint.json)绑定最终证据。原失败运行仍作为根因与修复记录保留，本批不以提高文件描述符上限、跳过测试或旧版本结果取得通过。

核心/仓单标准化新增21个用例仍属于上一切片；这次新增2个资源行为测试。真实来源认证、完整候选、120中国交易日点时重放、合格AI报告及切换仍未完成。
