# 12: 补算日冻结证据快照

**What to build:** 补算日也冻结证据快照（核心展示输入、模型输入与上下文输入），投影集引用真实快照 id，不再用核心资产文档哈希代替。`persist_derived` 维持 `False`；本票先查清补算日关掉派生落库的原因，再决定是否对齐。

**Blocked by:** 10

**勿并行：** 11、13、14（同改：单日汇总模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 3 差异（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「四、单日汇总模块」。

## 现状

- 目标日有输入时冻结快照（`worker.py:447–467`）；补算日不冻结，快照 id 走 `p0.py:102` 的哈希回退。ADR-0008 要求投影集共享数据快照，未见补算日豁免的依据。
- 补算日上下文 `persist_derived=False`（`worker.py:608`），投影引用的派生身份没有对应持久记录（`context_projection.py:1374`）。一种可能的原因：历史日派生观测落库后，会被后续"取最新"的查询选中。未核实。
- 已知线索（[c5 勘察](../codex-survey-c5.md)第 4.7 条，读码、未实测）：该 `False` 由提交 `edb8b1d` 引入，提交说明与快速重构 effort 的旧票 24 均未解释原因；全仓未见按指标"取最新派生值"的读取方。上述猜测因此没有得到支持，但也不能据此断言开启无害。
- 实测 `freeze_snapshot` 每次约数毫秒（目标日 2 次共 0.01 秒），121 天补算合计不到 1 秒。

## 验收

- [ ] 补算日投影集的 `evidence_snapshot_id` 指向真实冻结的快照，快照包含该日核心与上下文输入。
- [ ] `persist_derived=False` 的原因查清（提交记录、快速重构 effort 的旧票 [24](../../pring-fast-refactor-20260923/issues/24-first-initialization-and-missed-day-backfill.md)、实验），结论写入 Comments；若落库无害，另议是否对齐，不在本票改。
- [ ] 按 TDD 补用例：补算日快照可按 id 读回，成员与该日可见输入一致。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [ ] 代码审查无阻断。
