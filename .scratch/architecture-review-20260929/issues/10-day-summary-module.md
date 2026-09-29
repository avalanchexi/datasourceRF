# 10: 单日汇总模块（纯重构＋测试迁移）

**What to build:** 把单日汇总（`CONTEXT.md`）从 Worker 收进新模块 `src/pring_cycle/day_summary.py`：核心就绪 → 上下文投影 → 发布该日分析投影集，目标日与补算日共用；补算循环也归模块。**可观察行为不变**；两条路径的现有差异原样保留为显式参数，遗漏另见 11–14。汇总规则测试迁到模块接口（ADR-0034）。

**Blocked by:** 02、05（三张都动 `_core_readiness` 附近，串行避免冲突）

**勿并行：** 15、16、17、18（同改：Worker 编排与取数；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

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

- [ ] 新模块 `day_summary.py` 持有单日汇总与补算循环；`worker.py` 不再含 `_core_readiness`、`_summarize_day`、`_backfill_missed_days`、`_last_confirmed_stage`，Worker 只组装 `run_materials`、记检查点、推进状态。
- [ ] 模块不读批次、日历、发布日程的作用域状态；直接调用时无需进入 Worker 的作用域。
- [ ] 纯重构期间只增不删：现有完整运行测试全部通过，作为行为不变的回归网。
- [ ] 按 TDD 在模块接口上新增：落后 1 期核心沿用；落后 ≥2 期阻断；来源冲突阻断；补算失败日返回清单且不影响其他日；补算后阶段史按日连续；补算日只看当日公开的明细。
- [ ] 迁移（本票最后一步）：`test_backfill.py:116`（两个日期各调用一次模块）、`test_core_carry_forward.py:125`、`test_gap_list.py:157`、`:169`、`test_full_run_retrieval.py:880` 的阶段阻断断言、`test_decertified_main_chain.py` 的正式阶段与投影标签断言改走模块接口，删除被迁的完整运行断言，不叠加。
- [ ] 保留完整运行：`test_backfill.py:86`、`:106`，`test_core_carry_forward.py:89`、`:112`，`test_worker_calendar_gate.py:90`；获取、检索、留存、批次、租约类不动。其余"拆分"类测试在各自规则被改时顺手迁移，本票不一次拆完。
- [ ] 记录迁移前后受影响测试的耗时（同范围同身份比较，ADR-0025）。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过；涉及 Worker 编排，另加跑完整目录正例与三核心反例，记录退出码与耗时。
- [ ] 代码审查（规格、标准两轴）无阻断。
