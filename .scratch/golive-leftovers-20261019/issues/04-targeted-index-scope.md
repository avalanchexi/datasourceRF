# 04: 定向补取市场指数时请求、校验、入库范围一致

**What to build:** 定向补取单只债券指数时，原件重解析得六只指数、入库输出被裁成一只，整组比对必然 `registered_market_index_acquisition_values_mismatch`（调查第 4 节，目标值两侧相同）。让请求、原件校验与入库输出采用同一范围（最好按所需指数请求），保留严格数值比对，不放宽容差。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 集成测试：定向补取 CNY030／930916 成功入库；数值不同时仍拒收
- [x] 两例冒烟通过

## Comments

- 2026-10-19 ticket-gl04（分支 gl-04）：改为按所需指数请求。`TushareContextAdapter.market_indices` 新增可选 `metric_ids`，只请求所列指数（缺省仍请求全部六只，全量刷新不变）；`targeted_context.retrieve_tushare_context` 的指数族传入本次范围的指标。请求、原件重解析与入库输出因而同一范围；`acquire_scalars` 的整组严格比对未改（整批请求时少一只仍拒收，原测试 `missing_member` 照旧通过）。
- 新测试 `tests/integration/test_targeted_market_index_refetch.py`：补 CNY030／930916 各只请求一只并入库（值取 run-153de306 原件 111.6248、185.8319），改前两例均 `registered_market_index_acquisition_values_mismatch`；输出与原件差 0.0001 仍以同一原因拒收、不入证据。
- 测试（venv dev-venv-gl04，basetemp /tmp/pytest-gl04）：
  - `python tools/check.py quick` 新测试＋ test_targeted_monthly_refetch、test_warrant_symbol_isolation、adapters/test_tushare_context、test_context_acquisition_receipts、test_receipt_counts、test_attempt_classification、test_lookback_declaration、test_registered_model_inputs 中 4 例 market_indices：169 passed，494 秒（超 3 分钟目标，如实记录）。
  - `flock /tmp/pring-heavy.lock python -m pytest` 两例冒烟＋ test_worker_registered_catalog.py：4 passed，478 秒（含等锁共 576 秒）。
  - 合并 main 最新头（af16948）：Already up to date，无需复跑。ruff check／format 通过；mypy 仅报既有 tests/conftest.py:22。
- 偏离：无。
