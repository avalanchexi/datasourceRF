Status: ready-for-agent
Category: enhancement
Type: task

# 01 — 慢测试改走已有接口、夹具改批量写入

**Blocked by:** 无

**勿并行：** 16（同改：完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

规格：[spec.md](../spec.md)「七、测试提速」。

## 背景

2026-09-29 架构评审（[README](../README.md)）发现两处不需要新模块就能提速的地方。用户决定单独开票先做，与五个加深候选互不依赖。

## 要做的事

1. **检索预算类测试改走检索入口。** `tests/integration/test_full_run_retrieval.py` 里只断言检索预算的用例（如 `test_full_run_shares_hard_search_budget_across_periods`，约 33 秒）现在跑完整 Worker；改为直接调用 `FullRunRetrieval.retrieve()`（`src/pring_cycle/full_retrieval.py:116`）断言预算，只保留一例完整运行验证预算与运行记录的关联。
2. **夹具批量写入。** `seed_core_history()`（`test_full_run_retrieval.py:320`）逐条写入 720 条来源声明（180 天 ×〔日历＋三核心〕），改用证据仓库已有的批量追加（`src/pring_cycle/evidence.py:577`）。
3. **只记录不改**：`test_gap_source_repairs.py` 的 89 秒是模块级共享 setup（`:216`），不是单例成本。

## 验收

- [ ] 改动前后各跑一次 `test_full_run_retrieval.py`，记录总耗时与最慢 10 例。
- [ ] 断言语义不变：被改写的用例在删去对应行为时仍会失败。
- [ ] 不删除必要测试凑时限（`docs/agents/testing.md`）。
