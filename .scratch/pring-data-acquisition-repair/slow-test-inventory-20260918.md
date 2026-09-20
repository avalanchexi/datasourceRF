# 慢用例清单（2026-09-18）

门槛：单次 pytest 阶段 ≥30 秒。来自必跑验证的实际事件，不额外重跑建立榜单；耗时为单调计时。
材料冷构建计入调用它的测试，不能把该数当作每次热运行成本。不同批次不合计为一份通过结果。

## v2：SIGSEGV 中断

收据状态 `finished`；退出码 `-11`；完整通过节点 4。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| `tests/models/test_isolated_lifecycle.py::test_complete_context_replay_rejects_a_damaged_candidate_original` | call | 2067.65 | passed | 含 acquisition-repairs 冷材料构建；之后同身份可复用。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[True]` | call | 788.92 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[False]` | call | 51.44 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[True]` | call | 38.61 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |

原始事件：[verification-current-full-events-20260918.jsonl](verification-current-full-events-20260918.jsonl)。

## v3：重排导致历史内存峰值污染验收

收据状态 `finished`；退出码 `1`；完整通过节点 7。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| `tests/models/test_isolated_lifecycle.py::test_complete_isolated_candidate_is_calibrated_replayed_and_activated` | call | 2002.15 | passed | legacy 原始生命周期强制构建：公开准入、校准、120日回放、激活。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[True]` | call | 882.08 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[False]` | call | 829.37 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_replay_rejects_a_damaged_candidate_original` | call | 75.84 | passed | 同身份已有材料；完整context回放损坏/恢复控制。 |
| `tests/integration/test_integrated_worker_core_gap.py::test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original` | call | 51.63 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[True]` | call | 43.64 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[False]` | call | 41.52 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |

原始事件：[verification-current-full-v3-events-20260918.jsonl](verification-current-full-v3-events-20260918.jsonl)。

## v4：原始顺序下发现旧夹具缺日历

收据状态 `finished`；退出码 `1`；完整通过节点 416。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| 尚无完成的 ≥30 秒阶段 | — | — | — | 正在运行不等于通过。 |

原始事件：[verification-current-full-v4-events-20260918.jsonl](verification-current-full-v4-events-20260918.jsonl)。

## v5：C盘保护中断的完整批次

收据状态 `finished`；退出码 `2`；完整通过节点 914。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[False]` | call | 917.82 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[True]` | call | 870.66 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_for_a_fixed_target_retrieves_gaps_and_failure_keeps_the_projection` | call | 548.76 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_tushare_failures_keep_required_blocking_and_optional_degrading[optional-gdp]` | call | 474.85 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` | call | 461.18 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_tushare_failures_keep_required_blocking_and_optional_degrading[required-market-indices]` | call | 92.60 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_integrated_worker_core_gap.py::test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original` | call | 90.37 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_official_refresh_uses_the_active_registered_catalog[False]` | call | 54.61 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[False]` | call | 41.79 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[True]` | call | 40.10 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_worker_database_lifetime.py::test_worker_retains_lease_until_periodic_heartbeat_has_closed` | call | 34.68 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_candidate_duration.py::test_new_model_reports_actual_candidate_days_and_preserves_old_snapshots` | call | 32.51 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` | call | 31.18 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_newly_acquired_historical_publication_fact_can_open_full_run_search` | call | 30.58 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection[treasury_partial]` | call | 30.42 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection[gdp_no_levels]` | call | 30.36 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_daily_reacquisition.py::test_a_verified_daily_series_is_not_requested_again` | call | 30.31 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_credit_formula_expands_required_history_in_full_run_plan` | call | 30.26 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_independent_calendar_keeps_missing_core_day_in_required_window` | call | 30.12 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_adoption_excludes_uncertified_candidates` | call | 30.03 | passed | 按本次范围计时，进一步优化需单独证据。 |

原始事件：[verification-current-full-v5-events-20260918.jsonl](verification-current-full-v5-events-20260918.jsonl)。

## v6：EIA夹具缺独立日历而失败

收据状态 `finished`；退出码 `1`；完整通过节点 914。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[True]` | call | 868.67 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[False]` | call | 850.72 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` | call | 409.10 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_for_a_fixed_target_retrieves_gaps_and_failure_keeps_the_projection` | call | 402.62 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_tushare_failures_keep_required_blocking_and_optional_degrading[optional-gdp]` | call | 374.10 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[missing-missing_credentials]` | call | 266.38 | failed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_integrated_worker_core_gap.py::test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original` | call | 57.46 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[True]` | call | 44.07 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[False]` | call | 38.98 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_worker_database_lifetime.py::test_worker_retains_lease_until_periodic_heartbeat_has_closed` | call | 35.19 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` | call | 30.36 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_daily_reacquisition.py::test_a_verified_daily_series_is_not_requested_again` | call | 30.11 | passed | 按本次范围计时，进一步优化需单独证据。 |

原始事件：[verification-current-full-v6-events-20260918.jsonl](verification-current-full-v6-events-20260918.jsonl)。

## v7：补EIA日历并收集全部失败的完整批次

收据状态 `finished`；退出码 `0`；完整通过节点 1848。

| 用例 | 阶段 | 秒 | 该阶段结果 | 成本解释 |
|---|---|---:|---|---|
| `tests/models/test_isolated_lifecycle.py::test_complete_isolated_candidate_is_calibrated_replayed_and_activated` | call | 1741.68 | passed | legacy 原始生命周期强制构建：公开准入、校准、120日回放、激活。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[True]` | call | 748.94 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_integrated_worker_delivery.py::test_integrated_worker_preserves_delivery_time_and_source_in_publication[False]` | call | 746.95 | passed | 复用合法材料；两个目标日真实Worker发布链及必需字段失败。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[parse-validation_failed]` | call | 430.31 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` | call | 420.33 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_for_a_fixed_target_retrieves_gaps_and_failure_keeps_the_projection` | call | 413.78 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[network-source_failed]` | call | 407.99 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[success-verified_candidate]` | call | 407.65 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[missing-missing_credentials]` | call | 400.13 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_tushare_failures_keep_required_blocking_and_optional_degrading[optional-gdp]` | call | 362.44 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_replay_rejects_a_damaged_candidate_original` | call | 68.56 | passed | 同身份已有材料；完整context回放损坏/恢复控制。 |
| `tests/integration/test_worker_registered_catalog.py::test_worker_official_refresh_uses_the_active_registered_catalog[False]` | call | 52.85 | passed | 完整登记目录的Worker消费；legacy材料复用条件以该批身份为准。 |
| `tests/models/test_isolated_lifecycle.py::test_isolated_material_copy_keeps_the_activated_candidate_and_its_evidence` | call | 43.84 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[False]` | call | 41.37 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[True]` | call | 40.33 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/models/test_isolated_lifecycle.py::test_complete_context_snapshot_binds_older_warrant_coverage[True]` | call | 40.04 | passed | 复用合法材料后核验完整context覆盖快照，含隔离复制。 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[False]` | call | 39.78 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_worker_database_lifetime.py::test_worker_retains_lease_until_periodic_heartbeat_has_closed` | call | 35.18 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/models/test_candidate_admission.py::test_registered_window_breadth_outputs_fixed_120_days_with_hidden_warmup` | call | 33.32 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_daily_reacquisition.py::test_a_verified_daily_series_is_not_requested_again` | call | 32.54 | passed | 按本次范围计时，进一步优化需单独证据。 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` | call | 30.22 | passed | 按本次范围计时，进一步优化需单独证据。 |

原始事件：[verification-current-full-v7-events-20260919.jsonl](verification-current-full-v7-events-20260919.jsonl)。

## 候选日历修正后的相关回归

187 项通过，pytest 923.74 秒；这是相关诊断批次，不与完整验证加总。外层驱动收据错误及输入证明范围见 `verification-calendar-related-fixtures-recovered-20260918.json`。

| 用例 | 阶段 | 秒 |
|---|---|---:|
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[True]` | call | 39.69 |
| `tests/integration/test_full_run_retrieval.py::test_resume_rechecks_unknown_release_without_mutating_initial_plan[False]` | call | 38.90 |
| `tests/integration/test_full_run_retrieval.py::test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection[treasury_schema]` | call | 33.63 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` | call | 30.49 |
| `tests/integration/test_full_run_retrieval.py::test_full_run_plan_includes_missing_historical_daily_members` | call | 30.34 |
| `tests/integration/test_full_run_retrieval.py::test_lpr_direction_inputs_are_certified_and_in_frozen_snapshot[False]` | call | 30.33 |
| `tests/integration/test_full_run_retrieval.py::test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection[treasury_partial]` | call | 30.09 |

以上完整检索场景每例约30–40秒；下一次局部变更优先选直接相关节点，影响面扩大时仍完整覆盖该范围。不能据 quick 入口名称声称本批满足3分钟。

## 已测改善与下一步

- 同版本对照的六个日历/Worker相关离线用例：230.88秒 → 56.44秒；改动仅选择器跳过无所属指标的家族校验，证据见 `verification-22-selection-feedback-comparison-20260918.json`。不能外推到全套或业务运行倍数。
- 组件反例使用真实公开投影/选值入口；完整回放编排与存储由独立重型场景保留。快速入口不会隐式触发已知完整生命周期文件，pytest默认发现保持完整。
- v3已完成legacy强制冷构建；v4恢复原始默认顺序；v5仅修正候选天数夹具，两profile须按完整身份与内容哈希核对后供消费者复用。原强制构建测试仍实际执行，不因缓存而跳过；每例使用独立可变运行库。
- Worker热点采样仍出现商品原件复核、选值与缺口规划。若继续优化，需同身份公共场景的剖析对照，保持原件损坏、点时和认证反例；当前批次期间不改绑定输入。
- 诊断计时器崩溃单列于 `diagnosis-verification-faulthandler-20260918.md`，不作为慢测试正常完成时间。
