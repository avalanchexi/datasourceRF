# SQLite Worker 连接生命周期修复

2026-09-11。属于票17，沿用已批准的公开 Worker / 证据查询测试入口。
本切片基线 HEAD `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；此前工作区中的
P1/P2、Q1、报告等改动保持原样。源码改动限 storage.py 和 worker.py。

## 已执行的根因调查

- 历史59完整测试为1146通过、2失败。其中原件读取在新连接
  `EvidenceRepository.source_claim_acquisitions_many -> PRAGMA journal_mode=WAL`
  返回 `database is locked`；原记录没有锁持有者及原生时间信息。
- 162原生跟踪实际显示 `RunRepository.heartbeat_lease` 关闭连接时，
  `sqlite3WalClose -> unixLock` 成功取得数据库共享字节区间的排他锁，随后执行检查点同步。
- 164只将该真实关闭同步延迟500ms，原公开查询成功，0.824秒，pytest 1通过/24.23秒。
- 165同一机制延迟6秒，原公开查询5.037秒后在原PRAGMA路径报
  `SQLITE_BUSY`（错误码5），pytest实际1失败/20.44秒。
  [原生栈](verification-sqlite-overlap-trace-165.txt)的DELAYED fsync位于
  `sqlite3WalCheckpoint -> sqlite3WalClose`，没有替换返回值或修改SQLite参数。
- 166反事实保留一个无事务的有效WAL连接，真实心跳完成后查询成功，0.116秒。
  原生排他清理延后到查询结束后，pytest 1通过/18.86秒。这不是增加等待时间。
- 167通过真实公开任务提交、Worker执行和真实租约操作加入回归，
  原查询再次报同样错误：
  [RED](verification-worker-lifetime-red-167.txt)，1失败/51.45秒。

以上证明了当前代码的可复现故障机制：短连接在并发工作期间变成最后连接，
慢关闭检查点占据排他锁，使另一个新查询耗尽默认等待。
不能据此还原历史59未记录的锁持有者，或声称已排除所有其他SQLite故障机制。
H2恢复竞争未得到扩展BUSY_RECOVERY证据；H3模式切换没有得到支持，实验始终使用既有WAL库。
官方机制参见 [SQLite WAL busy边界](https://sqlite.org/wal.html#sometimes_queries_return_sqlite_busy_in_wal_mode)。

## 修复及影响范围

新增 `keep_database_open`，读完journal mode以打开真实pager，但不启动事务。
Worker服务整个循环和单次公开执行都保留此连接；实际读写仍各用独立、及时关闭的连接。
心跳线程必须退出后才释放租约和保留连接，避免收尾期间重新出现关闭交叠。
影响完整运行、定向刷新、手动深搜及报告任务的共同执行生命周期。
不更改SQL等待参数、来源/阶段规则、预算、数据库schema或模型生效状态。
任意其他进程长期持锁、设备永久阻塞与历史失败的具体锁持有者不在已证明范围。

新回归位于 `tests/integration/test_worker_database_lifetime.py`，其进程夹具位于
`tests/fixtures/worker_sqlite_lifetime.py`。使用Linux现有strace延迟真实fsync，
从内核锁或真实心跳完成事件选择查询起点；主断言是原件查询可用，未取得证据的任务仍为
action_required。没有返回假claim来冒充获取成功。没有Linux/strace的环境显式skip。
169修复后同一Worker回归实际1通过/36.33秒，前后232输入/4保护文件/91安装源码/53依赖匹配，mypy4通过。
169双轴审查发现两个测试工具风险（缓冲选择器、tracer子进程清理）及收尾覆盖缺口。
171已改为二进制帧读取和整个自有进程组清理，新增真实30秒周期心跳收尾用例：
在外部SQLite close边界暂停已提交的真实连接，任务终态出现后仍不得转让租约；放行心跳后才可转让。
171实际终态为2通过/73.36秒，前验、测试、后验均0，233输入/4保护文件/91安装源码/53依赖匹配。
172已给原CLI停止测试补正常退出码断言，不能再用SIGKILL冒充正常收尾。
最终6文件Ruff、格式、mypy均通过；Standards172和Spec172均无未关闭静态发现。
172关联范围包括数据库资源、运行编排、Worker、原完整失败用例和CLI正常停止；
真实执行器PID118928/start_ticks241880，pytest PID119539，工具会话65410。
172实际终态为35通过、1失败/436.68秒，前验和后验均0，233冻结输入、4保护文件、91安装源码和53依赖匹配。
唯一失败是`test_repeated_runtime_views_remain_available`的子进程30秒看门狗超时，
不是SQLITE_BUSY；原完整运行预算用例和CLI正常停止用例均在该批通过。
该失败子进程未调用新增Worker保留连接，当前先用173只读诊断记录原64轮公开视图
各步骤耗时、打开句柄数及运行栈，保留原30秒上限。没有通过放宽上限或重跑关闭失败。
源码与冻结172继续保持不变；本切片尚未通过全部关联范围、默认全套或提交。

**后续176实际关联验收：38通过、0失败/398.75秒。** 172原失败保留。
173/174定位该超时为DrvFS应用包指纹读取，完整过程见
[超时根因及环境修正](runtime-views-timeout-diagnosis-175.md)。175在原有项目专属ext4测试卷
离线安装相同Python、53依赖版本和95个相同应用文件；176执行原36项及两项原生并发回归，
原30秒上限和64轮均未改变。原生前后收据均核233输入/4保护文件/91源码/95包文件/53依赖。
[根核验176](verification-worker-lifetime-acceptance-176.json)绑定真实测试退出码、完整日志和原生收据，
不以外层旧环境检查或执行器退出码代替。Spec176无范围放宽；Standards176两项执行器问题
在未启动的后续177中修正并经Standards177复核：失败非零退出、异常仍监督子进程收尾及卸载。
176已结束，测试卷已卸载；默认全套尚未重跑、本切片未提交、整票17未关闭。

168安装命令错误使用--no-build-isolation，环境没有hatchling，构建失败；
169恢复原离线隔离构建后安装成功，没有增加或升级运行依赖。这是验证准备错误。

Q1关联163已独立核验132通过/305未选/631.42秒，
[根验收](verification-capacity-acceptance-163.json)核230输入/4保护文件与既有审查证据。
其限定范围验收不替代本切片，也不关闭Q1历史目录兼容、Worker新目录路由、信用脉冲、
真实认证、完整候选、固定120日、真实AI或正式切换。
