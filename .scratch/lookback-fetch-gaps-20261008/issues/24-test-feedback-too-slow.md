Status: claimed（诊断完成；连接复用待批准）
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

- [ ] 诊断：同一提交下补齐全部阶段耗时，能列出前 30 用例、前 15 文件及前 50／前 10% 占比
- [ ] 诊断：对固定慢节点串行重复测量，分开报告初始化、取数／检索、汇总、清理，冷建与热材料分开
- [ ] 实施后：代表性单票的受影响测试明显缩短（给出前后同口径计时），必要消费者与 ADR-0025 收尾覆盖不缩减
- [ ] 若采用建库模板：副本修改不污染模板或其他用例，准备＋复制＋清理净收益为正
- [ ] 全套不缩减覆盖，记录 C 盘峰值；不以并行争用下的时间宣称提速

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
4. 补算内部（cProfile）：`build_context_projection` 120 次 81 秒，其中 `EvidenceRepository.metric_series` 1.35 万次 41 秒（每日对每个指标重读全史并按公开截止过滤）、`claim_adoption.check` 1.8 万次 47 秒、`select_warrant_inputs` 28 秒。`evidence.py` 的预载分支只在 `public_as_of is None` 时命中，补算日恰好都带公开截止，生产中未用。

**全套层面**（Codex 静态统计，见 scratchpad `d24/codex_census.out`）：约 69 次完整运行进入 120 日补算，分布在 26 个文件里，其中 60 次（87%）在用例内各自跑。按每次 40–90 秒估算，这已占全套 77 分钟的大头。所以降低单次运行成本收益最大，而且生产真实运行同样受益；`test_full_run_retrieval.py:449/469` 一类"同输入各跑一次"的可共享例子只有少数。

**已排除**：共享建库模板（初始化每次运行仅约 1 秒，扣除复制成本净收益接近 0）；原件体积；Worker 轮询（主要慢例直调 `process_pending_run`）；pytest-xdist（ADR-0025 不引入并行）。

**假设排序（已验证第 1 条）**：① 连接开关的 schema 解析（差分 −37%，已证实）；② 补算逐日全史重读证据（预期运行级预载可再降补算段的一部分，未验证）；③ 选择宽、叠加重型文件（15–70 分钟中相当部分来自选择，未量化）；④ 迁移／建库（已证伪，约 1%）。

**切入点与处置**
- 已实施（只动 `tools/`）：`check.py` 每次运行都用 `-p tools.timings` 记录全部用例的三个阶段，结束时打印前 30 用例、前 15 文件、前 50 与前 10% 占比和计时文件路径（验收框 1 随下一次必跑全套即可取得，不必另跑）。
- 待主 agent／用户批准（改生产代码 `storage.py`）：连接复用，预计每次完整运行快约 35%，测试与真实运行同时受益。
- 建议另开票：补算日的证据读取改为运行级预载（涉及双时间边界语义）。
