# 10: 单日汇总模块（纯重构＋测试迁移）

**What to build:** 把单日汇总（`CONTEXT.md`）从 Worker 收进新模块 `src/pring_cycle/day_summary.py`：核心就绪 → 上下文投影 → 发布该日分析投影集，目标日与补算日共用；补算循环也归模块。**可观察行为不变**；两条路径的现有差异原样保留为显式参数，遗漏另见 11–14。汇总规则测试迁到模块接口（ADR-0034）。

**Blocked by:** 02、05（三张都动 `_core_readiness` 附近，串行避免冲突）

**勿并行：** 15、16、17、18（同改：Worker 编排与取数；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 3 的访谈记录（2026-09-29）；勘察见 [codex-survey-c3.md](../codex-survey-c3.md)。 规格：[spec.md](../spec.md)「四、单日汇总模块」。

## 现状（调用点）

- 目标日：`worker.py:407` 核心就绪（带计划缺口 `window_gaps`）、`:417` 上下文投影、`:446` 读上次确认阶段、`:447–473` 冻结证据快照并记 `verified_evidence` 检查点、`:476` `P0ProjectionService.publish`（带解释性警告、缺口清单、发布日历）。
- 补算：`_backfill_missed_days`（`worker.py:530`）挑出窗口内无汇总的日子，按日升序调用 `_summarize_day`（`:571`），失败只写运行事件；补算日核心就绪带 `public_as_of`＝该日上海时区结束，上下文 `persist_derived=False`，发布不带快照、缺口清单、发布日历与解释性警告。
- 辅助：`_core_readiness`（`worker.py:1117`）、`_last_confirmed_stage`（`:2148`）；只在上述两条路径使用。
- 隐式作用域状态：批次 id、运行期间交易日历、发布日程（`worker.py:218`、`:381`、`:382`）。

## 已定决定

- **算并发布**：模块内部做核心就绪、上下文投影、`P0ProjectionService.publish`，返回发布结果。检索、计划评估、时效记录、检查点、运行状态推进、模型切换检查、报告、留存都留在 Worker。
- **补算循环归模块**：挑漏跑日、按日升序、某日失败不影响目标日。失败日由模块以清单返回，Worker 写运行事件。
- **接口形状**：

  ```python
  class DaySummaries:  # 传入 EvidenceRepository、ProjectionSetRepository、模型规则、交易日历
      def summarize_target(day, *, system_as_of, run_materials) -> P0PublishResult
      def backfill(window, *, target, system_as_of) -> tuple[FailedDay, ...]
  ```

  `run_materials` 是目标日才有的运行级材料（时效缺口、计划缺口与派生需求、发布日历事件、解释性警告），由 Worker 组装传入。纯重构期间门①仍用计划缺口，经 `run_materials` 传入（改为模块自行枚举见 11）。
- **快照冻结移入模块**，返回快照 id，Worker 用它记 `verified_evidence` 检查点。顺序微调：Worker 先检查活动模型是否切换，再调用模块（现为先记快照检查点再查模型）。
- **批次 id、交易日历、发布日程显式传入**，模块不读作用域状态。交易日历用票 02 的 `TradingCalendar`。
- **`P0ProjectionService` 保留在 `p0.py`**，作为阶段推导与投影集组装层，由模块调用。`_core_readiness`、`_summarize_day`、`_backfill_missed_days`、`_last_confirmed_stage` 从 `worker.py` 移入新模块。
- **不优化补算性能**：生产上只在首次初始化时付一次；票 10、15 做完后重新剖析，仍值得再开票。
- **维持现状并写进模块文档**：补算失败日之后的日子沿用跨过失败日的上次确认阶段，下次只补失败日，不级联重算；降级汇总也算已汇总，不重算（`CONTEXT.md` 发布历史不得改写）。补算日部分时效标签按运行时间而非该日计算（`context_projection.py:298`、`:1764`），因为不展示所以不改。

## 验收

- [x] 新模块 `day_summary.py` 持有单日汇总与补算循环；`worker.py` 不再含 `_core_readiness`、`_summarize_day`、`_backfill_missed_days`、`_last_confirmed_stage`，Worker 只组装 `run_materials`、记检查点、推进状态。
- [x] 模块不读批次、日历、发布日程的作用域状态；直接调用时无需进入 Worker 的作用域。
- [x] 纯重构期间只增不删：现有完整运行测试全部通过，作为行为不变的回归网。
- [x] 按 TDD 在模块接口上新增：落后 1 期核心沿用；落后 ≥2 期阻断；来源冲突阻断；补算失败日返回清单且不影响其他日；补算后阶段史按日连续；补算日只看当日公开的明细。
- [x] 迁移（本票最后一步）：`test_backfill.py:116`（两个日期各调用一次模块）、`test_core_carry_forward.py:125`、`test_gap_list.py:157`、`:169`、`test_full_run_retrieval.py:880` 的阶段阻断断言、`test_decertified_main_chain.py` 的正式阶段与投影标签断言改走模块接口，删除被迁的完整运行断言，不叠加。
- [x] 保留完整运行：`test_backfill.py:86`、`:106`，`test_core_carry_forward.py:89`、`:112`，`test_worker_calendar_gate.py:90`；获取、检索、留存、批次、租约类不动。其余"拆分"类测试在各自规则被改时顺手迁移，本票不一次拆完。
- [x] 记录迁移前后受影响测试的耗时（同范围同身份比较，ADR-0025）。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过；涉及 Worker 编排，另加跑完整目录正例与三核心反例，记录退出码与耗时。
- [x] 代码审查（规格、标准两轴）无阻断。

## Comments

**2026-09-29 实施记录**

- **模块** `src/pring_cycle/day_summary.py`：`DaySummaries(evidence, projections, ModelRules, calendar=, release_schedule=, batch_id=)`；`summarize_target(day, system_as_of=, run_materials=, backfill_window=) -> TargetSummary`（发布结果、快照 id、补算失败日）与 `backfill(window, target=, system_as_of=) -> tuple[FailedDay, ...]`。`ModelRules.of(ModelRepository, model_version_id)` 取代 Worker 的 `_trend_rules_for_model`。`_core_readiness`、`_summarize_day`、`_backfill_missed_days`、`_last_confirmed_stage`、`_core_originals_disagree`、`CORE_METRICS` 移出 Worker。
- **接口与票面约定的出入**（规格同步订正）：
  - `summarize_target` 多一个 `backfill_window`：旧代码先算目标日核心就绪与上下文（上下文会落库派生观测），再补算，最后发布。为保持这个先后，补算在模块内部、在目标日计算之后执行。
  - 返回 `TargetSummary`，里面带快照 id，而不是直接返回 `P0PublishResult`。
  - `RunMaterials` 带回调：`explanatory_warnings`（依赖当日上下文）、`step_done`（每步完成后通知；Worker 在这里推进运行状态，已取消的运行在这里抛错，不再发布）、`snapshot_frozen`（冻结快照后立即记 `verified_evidence`）、`day_failed`（补算失败当场写运行事件）。检查点、状态推进、失败事件都保持旧代码的时机。
- **作用域**：模块内部自己打开批次、运行日历、发布日程三个作用域，并设置为传入的值，不读调用方的状态。`processing_batch` 改为接受 `None`，不传批次时就不归属任何批次，也不会沿用外层的批次。退出作用域后恢复 Worker 原来的值。
- **测试**：
  - 模块接口 8 例（`tests/integration/test_day_summary.py`）：落后 1 期沿用；落后 ≥2 期阻断；来源冲突阻断；窗口内缺核心日阻断（门①）；补算失败日返回清单；补算失败后目标日照常发布，回调顺序正确；补算后阶段史按日连续；补算日只看当日公开的明细（两个日期各调一次模块）。
  - 迁移：`test_backfill` 公开时点用例（连同其专用 CPI 造数）、`test_core_carry_forward` 冲突用例删除；`test_gap_list` 的 `:157`、`:169` 两例改用模块 fixture；`test_decertified_main_chain` 的正式阶段与无认证标签两例改用模块 fixture，另保留一例完整运行，断言运行完成且报告关联投影。`test_worker_execution` 里 monkeypatch 的目标从 `worker._core_readiness` 改为 `DaySummaries._core_readiness`，断言不变。
  - 保留的完整运行：`test_backfill` 两例、`test_core_carry_forward` 两例、`test_worker_calendar_gate` 正例。
  - 票 02 删除的 `test_independent_calendar_keeps_missing_core_day_in_required_window` 以完整运行形式恢复为 `test_a_core_session_missing_inside_the_window_holds_the_core_through_the_run`：断言初始窗口含缺日、最终缺口不完整、运行完成、股票核心原因 `window_session_missing`（Worker 把计划缺口交给门①这一环的端到端覆盖）。阶段不给的规则本身在模块测试里。
- **耗时**（同机、同在 `/mnt/d`）：迁到模块的单例约 1–2 秒，原完整运行单例约 23–30 秒。例如冲突用例：完整运行 30.2 秒（票 02 回归日志）→ 模块 1.05 秒。`test_decertified_main_chain` 原来是整文件共用一次完整运行，现在是模块 fixture（1.5 秒）加一例完整运行，总量基本持平。受影响的 36 个 Worker 路径文件加模块测试共 305 例，29 分 12 秒。
- **验证**（`PYTHONPATH=src`）：上述 305 例中 304 过、1 败。失败的是 `test_model_version_switch`：它跑三次完整运行，但日历回执只写了一次，第一次运行后被留存删除。这是票 02 夹具改动留下的问题（该文件借用降准主链的造数，当时不在票 02 的受影响列表里），改为每次运行前重写日历后通过。其中含收尾冒烟两例、完整目录正例、三核心反例。ruff、mypy 通过。
- **审查**（Codex 只读两轴）已按意见修：不传批次时会沿用外层批次；状态推进提前会削弱取消边界；补算失败事件在后续出错时可能整批丢失；快照检查点被推迟到发布之后；降准主链迁移范围过大；缺核心日的运行级断言与门①的 Worker 衔接没有端到端覆盖；docstring 措辞。

**行为差异（记录，未改）**

1. 模型切换检查提前到调用模块之前（票面授权）。后果：检查之后、目标日发布之前（例如首次初始化较长的补算期间）如果切换了模型，目标日仍会按旧模型发布；旧代码会在发布前拦下。
2. LPR 发布日历事件（`_release_calendar_documents`）提前到目标日计算之前。只影响"日历读取与上下文同时出错"时先报哪个错，以及日历单独出错时目标日派生数据是否已经落库。

