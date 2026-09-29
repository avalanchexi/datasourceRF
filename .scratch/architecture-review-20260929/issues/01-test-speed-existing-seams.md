Status: done
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

- [x] 改动前后各跑一次 `test_full_run_retrieval.py`，记录总耗时与最慢 10 例。
- [x] 断言语义不变：被改写的用例在删去对应行为时仍会失败。
- [x] 不删除必要测试凑时限（`docs/agents/testing.md`）。

## Comments

**2026-09-29 实施记录**

- 计时（同一台机器、同在 `/mnt/d` 工作区，`PYTHONPATH=src`，串行各跑一次）：
  - 改动前（HEAD 版测试文件的临时副本）：28 例全过，**524.16 秒**。最慢 10 例：treasury_partial 45.42、searches_real_gap 38.11、shares_hard_search_budget 37.10、plan_includes_missing_historical 33.97、adoption_excludes_uncertified 33.96、lpr_direction[True] 30.74、treasury_schema 28.72、gdp_no_levels 28.55、p2_projection[failure1] 27.57、p2_projection[failure2] 27.48。
  - 改动后：28 例全过，**399.38 秒**（−24%）。最慢 10 例在 22.8–24.6 秒之间：searches_real_gap 24.61、treasury_partial 24.51、p2_projection[None] 24.50、treasury_schema 24.01、gdp_no_levels 23.87、lpr_direction[True] 23.58、independent_calendar 23.51、credit_formula 23.32、p2_projection[failure2] 23.08、adoption_excludes_uncertified 22.78。
  - 预算用例单独计时：37.10 → 24.30 秒。剩下的主要是 `prepare` 与 180 天夹具的开销，每例约 20 秒，跑不跑完整 Worker 都一样；要再降，得减夹具天数或共享库，不在本票范围。
- 断言语义：临时让 `retrieval_ledger.py` 的每轮上限不再拦截（`blocked = "run_limit"` 改为 `None`），预算用例失败（Tavily 调用 184 次，期望 16），随即还原。夹具改用 `append_source_claims`：单条追加本身就调批量追加（`evidence.py:551`），写入语义相同。
- 预算与运行记录的关联仍由 `test_full_run_searches_real_gap_and_publishes_traceable_adoption` 经完整运行断言（`consumed_budget["tavily"]` 等于实际调用次数）。
- `test_gap_source_repairs.py`：按票面只记录，不改。
- 未删测试。收尾冒烟两例通过（53.7 秒）。

