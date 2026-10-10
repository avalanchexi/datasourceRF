Status: done
Category: enhancement
Type: task

# 24：测试反馈过慢

## 现象（第一、二轮实施中实测，2026-10-08—09）

- 单票的受影响测试一轮约 **15–70 分钟**，审查修复后复跑再翻倍，成为单票耗时的大头。
- 慢文件与单例：多个用例单例 **56–94 秒**；全套 2158 例 1:23:40（第二轮），最慢的窗口前取数用例 307 秒、模型切换 97 秒（见 [acceptance-20261009-round2.md](../acceptance-20261009-round2.md) 第一节）。

## 待分流时确认

- 慢在哪里：完整运行级替身的重复建库、迁移、Worker 编排，还是夹具规模。
- 方向：共享只读建库模板、拆分重型用例、受影响测试选择更细，或按 ADR-0025 调整分层。

不进第三轮（用户决定，2026-10-09）。

## 验收

- [x] 诊断：同一提交下补齐全部阶段耗时，能列出前 30 用例、前 15 文件及前 50／前 10% 占比（见积压批次收尾验收 [acceptance-20261010.md](../../backlog-triage-20261009/acceptance-20261010.md) 第一节）
- [x] 诊断：对固定慢节点串行重复测量，分开报告初始化、取数／检索、汇总、清理，冷建与热材料分开（见下"2026-10-09 诊断"：单节点 4 轮，另有同文件交替 A/B 6 轮）
- [x] 实施后：代表性单票的受影响测试明显缩短（给出前后同口径计时），必要消费者与 ADR-0025 收尾覆盖不缩减（见"2026-10-10 实施"：交替 A/B 中位数 −28%／−50%，未删减任何测试）
- [ ] 若采用建库模板：副本修改不污染模板或其他用例，准备＋复制＋清理净收益为正（未采用：初始化每次仅约 1 秒，见诊断）
- [x] 全套不缩减覆盖，记录 C 盘峰值；不以并行争用下的时间宣称提速（同上第一节：2259 例全过、无删除测试，C 盘最低 52G、basetemp 峰值 15G，锁独占）

## 主要模块

`tests/`（夹具、完整运行级替身）、`tools/check.py`（耗时采集与选择）、`docs/agents/testing.md`；如证据读取是热点，再涉及 `evidence.py`、`day_summary.py`、`context_projection.py`。调整 ADR-0025 分层属领域决定，先问用户。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`，按用户指示先走 `/diagnosing-bugs` 找到慢在哪里；结论若是测试结构没有好的切入点，再转架构加深（`/improve-codebase-architecture` 的做法）。
- 第三轮全套只留了 `--durations=10`（`tools/check.py:120` 硬编码），前十阶段合计 968 秒、占 4617 秒的 21%，完整排名无法恢复。最慢：窗口前取数双运行 277.6 秒、官方 PPI 回退 114.3 秒、美债来源 setup 91.3 秒（含一次完整运行）、模型切换三轮 85.0 秒、留存 setup 82.1 秒（两次完整运行）。
- 读码推断的主因是**重复完整业务运行**（每轮约 28–139 秒），其次检索层本身已到分钟级（`FullRunRetrieval.retrieve` 直调用例 63–67 秒）。原件体积已排除（四份 JSON＋PPI HTML 读取 0.02 秒）；轮询对主要慢例收益约 0；33 个迁移的建库成本**没有测量数据**，不能认定为主因。
- 15–70 分钟来自选择宽（`testing.md:13` 覆盖消费者、`:22` 追加重型）叠加重型文件，`check.py` 无依赖选择器也无时间预算。ADR-0025 明确不引入并行，所以 pytest-xdist 不在范围内。
- Codex 判断：没有证据表明"无切入点、必须先做架构加深"。建议顺序：补全测量（`--durations=0` 或 JUnit 逐阶段）→ 定位单个慢节点的成本分解 → 细化受影响选择、减少无关完整运行 → 视测量结果再看证据重复读取（`evidence.py:1144` 预加载分支在生产中未用）。
- 诊断反馈环候选（单节点，冷启动，须 `flock`）：`tests/integration/test_gap_source_repairs.py::test_treasury_yields_are_held_from_tushare_us_tycr`，配 `/usr/bin/time` 与 `--durations=0`。

### 2026-10-09 诊断

**结论：慢在每次完整业务运行本身，不在建库、夹具规模或用例断言；最大的单一成本是 SQLite 连接开关导致的 schema 重复解析（约占每次完整运行的 35–40%）。** 测试结构有明确切入点，不需要先做架构加深。

**反馈环**：上述单节点，提交 `4a72eaa`，专用 venv（`dev-venv-tests`），`flock /tmp/pring-heavy.lock` 串行，`/usr/bin/time` ＋ `--durations=0`。另配一个只在本次诊断中用的分阶段计时 pytest 插件（scratchpad `d24/plugin/d24timer.py`，包装 `initialize_runtime`、`refresh_context_sources`、`FullRunRetrieval.retrieve/evaluate`、`DaySummaries.summarize_target/_backfill`、`prune_to_window` 等，可选统计每阶段 `sqlite3.connect` 次数），未进仓库。测量期间有另一会话未加锁的 quick pytest 并发（1 个进程，12 核负载 1.4–3.2），绝对秒数因此波动 95–148 秒；各阶段比例稳定。

**单节点分阶段（秒；setup 即一次 `process_pending_run`，call 0.01、teardown 0.00）**

| 运行 | wall | user | 初始化（33 迁移＋bootstrap） | 背景源刷新 | 检索 retrieve | evaluate | 补算 119 日 | 留存 prune | 整次运行 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 无插件 | 94.6 | 77.4 | — | — | — | — | — | — | 92.4（setup） |
| ph1 | 98.0 | 79.3 | 0.90 | 18.1 | 20.1 | 5.7 | 47.3 | 1.4 | 94.9 |
| ph2 | 147.6 | 118.9 | 1.34 | 29.3 | 29.8 | 8.3 | 71.2 | 1.9 | 143.7 |
| ph3（含连接计数） | 127.0 | 98.9 | 1.35 | 28.2 | 29.7 | 8.3 | 51.7 | 1.5 | 122.5 |

- 比例：补算约 42–50%，检索约 21–24%，背景源刷新约 19–23%，evaluate 约 6%，**初始化（迁移）约 1%**，留存约 1.5%。
- 冷热：运行库每次都冷建（无热材料可复用），初始化 0.9–1.35 秒；原件读取 0.02 秒（分流取证）；`PYTHONDONTWRITEBYTECODE=1` 下导入编译约 1 秒（cProfile `compile` 1.1 秒）。冷热差最多 1–2 秒，不是主因。
- 清理：teardown 0.00 秒；pytest 不删 basetemp，一次完整运行留下 **226 MB** 运行库（`analytical_dataset` 148 MB、`full_run_gap_plan` 33 MB），这是全套 basetemp 峰值的来源，不计入耗时。

**根因证据**

1. 一次完整运行开约 **7.1 万**个 SQLite 连接（ph3 计数：补算 34,780、背景源刷新 16,276、检索 14,412、evaluate 5,157，其余数百）。
2. 微测（同一 226 MB 运行库，143 个 schema 对象）：`connect+close` 0.020 ms；新连接的首条表查询 **0.556 ms**（解析 schema）；复用连接的同一查询 0.002 ms。7.1 万 × 约 0.53 ms ≈ **38 秒／运行**。cProfile 同向：`sqlite3 execute` 自身 32 秒、`Connection.__exit__` 15 秒、`connect`＋`close` 9.5 秒（剖析下总 159 秒）。
3. **差分验证**：插件原型把 `storage.database_connection` 改为按线程、按库复用连接（借出时复位 `row_factory`、`isolation_level`、`foreign_keys`）。整个 `test_gap_source_repairs.py` 8 例全过，紧挨着测的同口径对比：**110.1 → 69.8 秒（−37%）**；背景源 20.8→9.0、检索 21.7→12.9、补算 51.2→35.9、evaluate 6.0→5.1。
   复测改用正确的原型：每个线程、每个库各维护一组空闲连接，每次借出独占一个连接，嵌套时另取一个，归还前复位状态。必须这样做，因为 `worker.keep_database_open` 在整次运行期间都占着一个连接，**约 6.9 万次借出都发生在已有连接借出期间**，若共享同一连接，就会被内层的 `with connection:` 提交外层事务、改写 `row_factory`。这一版整次运行只新建 5 个连接，复用 7.1 万次。交替串行 A/B 各 3 轮（同文件 8 例，均全过，负载 2.0–2.3）：基线 130.6／111.3／132.9 秒，连接池 73.2／70.3／97.1 秒，**中位数 130.6 → 73.2 秒（−44%）**。
4. 补算内部（cProfile）：`build_context_projection` 120 次 81 秒，其中 `EvidenceRepository.metric_series` 1.35 万次 41 秒（每日对每个指标重读全史并按公开截止过滤）、`claim_adoption.check` 1.8 万次 47 秒、`select_warrant_inputs` 28 秒。`evidence.py` 的预载分支只在 `public_as_of is None` 时命中，补算日恰好都带公开截止，生产中未用。

**全套层面**（Codex 静态统计，见 scratchpad `d24/codex_census.out`）：约 69 次完整运行进入 120 日补算，分布在 26 个文件里，其中 60 次（87%）在用例内各自跑。按每次 40–90 秒估算，这已占全套 77 分钟的大头。所以降低单次运行成本收益最大，而且生产真实运行同样受益；`test_full_run_retrieval.py:449/469` 一类"同输入各跑一次"的可共享例子只有少数。

**已排除**：共享建库模板（初始化每次运行仅约 1 秒，扣除复制成本净收益接近 0）；原件体积；Worker 轮询（主要慢例直调 `process_pending_run`）；pytest-xdist（ADR-0025 不引入并行）。

**假设排序（已验证第 1 条）**：① 连接开关的 schema 解析（差分 −37%～−44%，已证实）；② 补算逐日全史重读证据（预期运行级预载可再降补算段的一部分，未验证）；③ 选择宽、叠加重型文件（15–70 分钟中相当部分来自选择，未量化）；④ 迁移／建库（已证伪，约 1%）。

**切入点与处置**
- 已实施（只动 `tools/`）：`check.py` 每次运行都用 `-p tools.timings` 记录全部用例的三个阶段，结束时打印前 30 用例、前 15 文件、前 50 与前 10% 占比和计时文件路径（验收框 1 随下一次必跑全套即可取得，不必另跑）。
- 待主 agent／用户批准（改生产代码 `storage.py`）：`database_connection` 改为按线程、按库的空闲连接池（独占借出、嵌套另取、归还复位），预计每次完整运行快约 35–45%，测试与真实运行同时受益。需要定的风险：池中连接的生命周期（进程退出或测试删库时关闭，否则会占住已删除的 226 MB 库文件，抬高 basetemp 峰值）；未耗尽的游标可能让复用连接停在旧的 WAL 快照上；调用方改过的连接级设置（`row_factory`、`isolation_level`、`foreign_keys` 等）要在归还时复位。
- 建议另开票：补算日的证据读取改为运行级预载（涉及双时间边界语义）。

### 2026-10-10 实施

主 agent 批准第 2 项（只改 `storage.py`；补算证据预载暂不开票，合入后重新剖析再定；quick 是否排队暂不改规程）。

**改动**（`src/pring_cycle/storage.py`，新测试 `tests/integration/test_database_connection_reuse.py` 16 例，先红后绿）
- `keep_database_open` 作用域内（Worker 的 `process_pending_run` 与守护循环），**本线程**对该库的 `database_connection` 改从空闲连接池借出：每次借出独占一个连接，嵌套借出另取一个；作用域退出时先关闭池中连接，保活连接仍最后关闭（WAL 收尾时机不变）。嵌套作用域（守护循环内再进 `process_pending_run`）按深度计数，只有最外层退出才关闭池。
- 归还时复位：关闭经 `cursor()`、`execute*`、`blobopen` 产生的游标与 blob，避免未读完的语句把复用连接钉在旧 WAL 快照上；恢复 `autocommit` 为 legacy 后再回滚残留事务；`row_factory`、`text_factory`、`isolation_level` 复位；`PRAGMA foreign_keys=OFF`。复位失败（例如调用方自行关闭了连接）则丢弃该连接。
- 借出前 `stat` 库文件：文件被删除或替换时关闭旧空闲连接，改读路径上的新文件。
- fork：`os.register_at_fork` 让子进程从空池开始；`database_connection` 与 `keep_database_open` 只在打开连接的进程里提交、回滚、归还或关闭，子进程展栈时一律不碰继承来的连接。新用例证明，在旧实现下子进程正常退出 `with` 时会**提交父进程未提交的事务**（4≠3），这是原有隐患，现一并修正。子进程（`subprocess`）不继承库文件描述符（SQLite 以 `O_CLOEXEC` 打开，已有用例验证）。
- 不入池：`:memory:`、空名、`file:` 名称和 `uri=True`；不在作用域内的线程（租约心跳线程仍每次新建并关闭，`test_worker_database_lifetime.py` 两例照旧验证）；`sqlite3.connect` 被替换时（`tests/fixtures/attempt_reads.py`、`worker_heartbeat_shutdown.py` 观察每个新连接）回退为新建。所以无需改任何调用方或夹具。

**绕过连接池的直连盘点**（`grep -n "database_connection\|sqlite3.connect"`，src 与 tools）
- `freshness.py:479` `batch_freshness` 直接 `sqlite3.connect`（每次运行 1 次）；
- `catalog_registry.py:94`、`:144`，`same_definition.py:169`：`uri=True` 只读连接（按设计不入池）；
- `storage.py` 的 `migrate_database`：SQLAlchemy 自有引擎；
- 保活连接本身；租约心跳线程（`worker.py` 的 `lease_heartbeat`）；作用域外的 CLI、Web、仓储调用和测试直连。
- 剖析中，一次完整运行池借出 69,212 次，新建池连接仅 2 个，其余直连约 2,080 次（主要是心跳线程与作用域外）。

**已知边界（非阻断，已写入 docstring）**：只追踪经上述方法产生的游标，`sqlite3.Cursor(connection)` 或基类方法直接调用不在追踪范围内，生产代码中没有这样用的；调用方设置的自定义函数、回调及其他 pragma 不复位，生产代码中也没有设置这些的；保活连接本就会持有已删除的库文件直到作用域结束（旧实现相同；同进程有连接持有该 inode 时，SQLite 也会推迟关闭其他 fd）。

**前后同口径计时**：在 0e45e8c 之上，base 为 main 的 `storage.py`，pool 为本分支；`flock` 串行交替，每轮前确认没有别的 pytest（others=0），负载 1.1–1.2；剔除 08:40–09:05 系统卡顿期间的计时，重测。

| 范围 | base 三轮（秒） | pool 三轮（秒） | 中位数 |
|---|---|---|---|
| `test_gap_source_repairs.py`（8 例，1 次完整运行） | 102.4／110.1／102.9 | 78.7／74.1／72.4 | **102.9 → 74.1（−28%）** |
| `test_core_carry_forward.py`（2 例，2 次完整运行） | 80.8／80.3／82.1 | 40.5／38.2／41.0 | **80.8 → 40.5（−50%）** |

分阶段（gap 文件，中位数）：背景源刷新 19.5→9.6，检索 20.9→13.7，补算 49.7→37.7，evaluate 5.8→4.9，初始化与留存不变。原型估计的 −37%～−44% 偏高：当时基线受到未加锁并发的 quick pytest 拖累，而正式实现又多了游标追踪、`stat` 与复位开销（微测每次借还约 0.016 ms，新建连接约 1.1 ms）。

**合入后剩余占比**（同节点 cProfile，总 113 秒；未剖析时整次运行约 70 秒）：补算约 54%，检索约 20%，背景源约 14%，evaluate 约 7%。热点如下：
- `EvidenceRepository.metric_series` 1.35 万次，累计 30 秒（约 27%），即补算证据运行级预载候选；
- `select_warrant_inputs` 8,765 次，累计 20 秒（约 18%，与前者部分重叠）；
- `Connection.commit` 7.1 万次，自身 9.5 秒（约 8%）。strace 计得一次运行 10,953 次 fsync。WAL 模式下默认 `synchronous=FULL`，每次写事务都 fsync；改为 `NORMAL` 属于耐久性取舍，需要用户决定，不在本票。
- `sqlite3 execute` 自身从 32 秒降到 8.6 秒。

是否为预载开票，由主 agent 决定。

**验证**（rebase 到 0e45e8c 并重装 venv 之后）
- 受影响测试 `check.py quick`：13 个目标，含新用例、Worker 执行与库生命周期、编排（attempt_reads）、`test_gap_source_repairs`、目录 URI 读取、租约心跳、e2e 本地运行 CLI、留存、模型切换、日历门禁、冒烟 1 例及 check 工具，**115 passed，523.9 秒**。
- 重型两例在 `flock` 下运行：`test_worker_registered_catalog.py`＋`test_core_carry_forward.py` **4 passed，348.1 秒**（窗口前取数 222.8 秒，历史为 277.6 秒；PPI 回退 90.2 秒，历史为 114.3 秒；三核心两例各约 16–17 秒）。
- ruff、ruff format、mypy（改动文件）均干净。
- Codex 两轴审查：首轮有阻断，共三项：fork 子进程展栈时会提交、关闭继承连接（P1）；`blobopen` 未追踪；`autocommit` 未复位。修复后定向复审，结论"阻断：无"。

验收框 1、5 随终点那次全套勾选：`check.py full` 会自动给出排名摘要，届时同时记录 C 盘峰值。

### 2026-10-10 收尾全套（积压批次票 01）

main `d0402d1`，`flock` 独占，`disk_guard.sh … 12`：**2259 passed，1:06:05**（第三轮 2208 例 1:16:56，−14.1%，只跑一轮，不作严格提速结论）。`check.py` 的排名摘要已存档：测试阶段合计 3955.90 秒，前 50 例占 48.0%，前 10%（226 例）占 83.7%；最慢为窗口前取数 231.7 秒（原 277.6）、PPI 回退 89.1 秒（原 114.3）、模型切换 55.9 秒（原 85.0）、留存 setup 49.3 秒（原 82.1）；最慢文件 `test_full_run_retrieval.py` 503.4 秒／31 例。C 盘最低 52G，basetemp 峰值 15G。`b54e57d..d0402d1` 间 `tests/` 无删除文件或测试函数。全套期间未见其他 pytest 运行。框 1、5 据此勾选；框 4 未采用建库模板，保持不勾。真实运行 `run-a1110cb8616e39b00f60` 约 10.2 分钟（第三轮 11.3），回执与渠道相同，无 `database is locked`，`integrity_check` ok。详见 [acceptance-20261010.md](../../backlog-triage-20261009/acceptance-20261010.md)。
