# 15: 判断检索范围是否已公布时，每个指标只读一次序列

**What to build:** `_retrieval_release_status` 不再对每个检索范围、每个指标都重读完整的 `metric_series`；同一次计划或检索内，每个指标（按截止时间与定义版本）只读一次，再在内存中逐期判断是否已公布。**行为不变。**

**Blocked by:** 无

**勿并行：** 02、05、10、16、17、18、23、24、25、28、30（同改：Worker 编排与取数；完整运行规划；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 3 访谈中的实测（2026-09-29）。 规格：[spec.md](../spec.md)「四、单日汇总模块」。

## 现状

- `_retrieval_release_status`（`worker.py:761`）逐指标调用 `EvidenceRepository.metric_series`（`evidence.py:981`），判断目标期有无已公布的已验证声明。调用方为 `FullRunRetrieval.retrieve`（`full_retrieval.py:84`）、`_plan`（`:481`）与 `worker.py:648`。每次运行约有 3000 个范围（日频指标按日各算一个），同一条序列被读几千次。
- 实测（2026-09-29，从 `src/` 导入，cProfile 下 `test_backfill.py` 首次初始化夹具，两次完整运行共 43 秒）：本函数调用 1.9 万次，累计 **12.6 秒（29%）**，是最大的单点；其中 `_plan` 贡献 8.3 秒，`retrieve` 4.3 秒。cProfile 会放大调用密集型代码，实际节省以不开剖析的计时为准。
- 注：检索记账 `record_retrieval_attempt` 逐次重解析初始计划的问题已由 `174d282` 修复，不属本票。

## 验收

- [~] 同一次计划或检索中，每个（指标、截止时间、定义版本）只读一次序列；读取结果不跨运行复用。
- [x] 按 TDD 补用例：同一指标多期范围的公布状态与改前一致（已公布、`awaiting_release`、LPR 按发布窗口推定、公开时间截止）。
- [x] 同范围同身份比较（ADR-0025）：`test_backfill.py` 首次初始化夹具与一例完整运行正例改前改后的耗时；并测一次 `_plan` 中 `ModelInputSelector.select` 的调用次数（改前约 1.4 万次），结论写入 Comments，决定是否另开票。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [x] 代码审查无阻断。

## Comments

**2026-09-29 实施记录**

- `worker.SeriesReads`：按（指标、截止时间、公开截止、定义版本）缓存 `metric_series`，`_retrieval_release_status` 新增可选参数 `reads`。只在 `FullRunRetrieval._plan` 判断各范围公布状态的循环里共享一个实例，这个循环不写入任何声明。
- **检索（`retrieve`）没有共享，第一条验收只做到计划这一半**：
  - 检索在范围之间会写入声明，其中有的 `available_at` 早于写入时刻（官方回退可以传外部时钟，CLI 也接受历史时间），复用读取可能漏看。
  - 默认的 `acquisition_window` 模式下，`known_at` 每个范围都取当前时间，键每次都不同，缓存本来就命中不了。实测加上检索侧缓存后，`metric_series` 总次数没有变化。
  - 所以检索保持每次都读。
- **测试**：`tests/integration/test_retrieval_release_status.py` 共 4 例。共享读取与每次都读结果一致（已公布、`awaiting_release`、LPR 窗口开启后已公布与未开启、`latest_only` 两种），公开截止时间早于声明，每个指标每个截止时间只读一次。
- **计数与耗时**（同机、同在 `/mnt/d`，`PYTHONPATH=src`；计数用 scratchpad 里的 pytest 插件，跑 `test_backfill.py`）：

  | 项目 | 改前 | 改后 |
  |---|---|---|
  | `_plan` 中 `metric_series` | 12908 | 412 |
  | `metric_series` 总数 | 27648 | 15152 |
  | `_retrieval_release_status` | 19038 | 19038 |
  | `_plan` 中 `ModelInputSelector.select` | **14132** | **14132** |
  | `test_backfill.py`（带计数插件，同一命令） | 35.3 秒 | 29.4 秒 |
  | 首次初始化夹具 setup | 48.6 秒（冷）| 27.0／28.3 秒 |
  | 完整运行正例 `test_worker_completes_…` | 23.3 秒 | 20.0／21.1 秒 |

- **结论**：`_plan` 中 `select` 仍有 1.4 万次，是下一个明显的热点（每个检索范围调一次选值，每次复核家族原件）。是否另开票，放到票 10、15 完成后的剖析里一起定。
- **验证**：发布状态与检索相关的 20 个测试文件 273 例全过（缓存收窄前那一版）。收窄后重跑本票测试、`test_full_run_retrieval.py` 与收尾冒烟正例，32 例全过。ruff、mypy 通过。
- **审查**（Codex 只读）：指出检索侧缓存的前提不成立，已按上文收窄到计划；补了 LPR 窗口开启后"已公布"的断言；docstring 已改。

