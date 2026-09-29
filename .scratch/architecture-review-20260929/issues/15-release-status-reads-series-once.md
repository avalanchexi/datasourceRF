# 15: 判断检索范围是否已公布时，每个指标只读一次序列

**What to build:** `_retrieval_release_status` 不再对每个检索范围、每个指标都重读完整的 `metric_series`；同一次计划或检索内，每个指标（按截止时间与定义版本）只读一次，再在内存中逐期判断是否已公布。**行为不变。**

**Blocked by:** 无

**勿并行：** 02、05、10、16、17、18、23、24、25、28、30（同改：Worker 编排与取数；完整运行规划；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 3 访谈中的实测（2026-09-29）。 规格：[spec.md](../spec.md)「四、单日汇总模块」。

## 现状

- `_retrieval_release_status`（`worker.py:761`）逐指标调用 `EvidenceRepository.metric_series`（`evidence.py:981`），判断目标期有无已公布的已验证声明。调用方为 `FullRunRetrieval.retrieve`（`full_retrieval.py:84`）、`_plan`（`:481`）与 `worker.py:648`。每次运行约有 3000 个范围（日频指标按日各算一个），同一条序列被读几千次。
- 实测（2026-09-29，从 `src/` 导入，cProfile 下 `test_backfill.py` 首次初始化夹具，两次完整运行共 43 秒）：本函数调用 1.9 万次，累计 **12.6 秒（29%）**，是最大的单点；其中 `_plan` 贡献 8.3 秒，`retrieve` 4.3 秒。cProfile 会放大调用密集型代码，实际节省以不开剖析的计时为准。
- 注：检索记账 `record_retrieval_attempt` 逐次重解析初始计划的问题已由 `174d282` 修复，不属本票。

## 验收

- [ ] 同一次计划或检索中，每个（指标、截止时间、定义版本）只读一次序列；读取结果不跨运行复用。
- [ ] 按 TDD 补用例：同一指标多期范围的公布状态与改前一致（已公布、`awaiting_release`、LPR 按发布窗口推定、公开时间截止）。
- [ ] 同范围同身份比较（ADR-0025）：`test_backfill.py` 首次初始化夹具与一例完整运行正例改前改后的耗时；并测一次 `_plan` 中 `ModelInputSelector.select` 的调用次数（改前约 1.4 万次），结论写入 Comments，决定是否另开票。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [ ] 代码审查无阻断。
