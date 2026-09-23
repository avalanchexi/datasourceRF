# 03 研究：测试套件分层与被删门禁的耦合

日期：2026-09-23。回答票 [03-test-suite-layering](../issues/03-test-suite-layering.md)。
方法：未运行任何测试。用例数来自当前树 `pytest --collect-only -q`（1988 项，9.38 秒）；耗时来自 v7 全套逐节点事件
[verification-current-full-v7-events-20260919.jsonl](../../pring-data-acquisition-repair/verification-current-full-v7-events-20260919.jsonl)
（1848 passed / 8865.15 秒，setup+call+teardown 求和 8830.8 秒），按文件聚合；文件分类由 Codex 只读通读 106 个测试文件得出，
关键结论已本人抽查（见“核实记录”）。

## 结论（先行）

1. **耗时高度集中**：v7 的 8831 秒里，4 个文件占 7434 秒（84%）：
   `test_worker_registered_catalog.py` 2937 秒 / 10 项、`test_isolated_lifecycle.py` 1936 秒 / 7 项、
   `test_integrated_worker_delivery.py` 1496 秒 / 2 项、`test_candidate_admission.py` 1066 秒 / 654 项；
   再加 `test_full_run_retrieval.py` 648 秒 / 35 项，5 个文件占 93%。其余 101 个文件合计约 650 秒。
2. **耗时的根因几乎都是被删门禁**：前三名全部走 `isolated_lifecycle_material`——公开准入（来源认证包）→ 校准 → 120 日回放 → 激活，
   冷构建 1742–2068 秒；材料身份键覆盖源码，改 `src/` 就失效并冷重建（ADR-0014）。消费者每例还要复制约 3.2 GB 的独立运行库，
   然后在完整注册目录上跑 Worker，每例约 350–920 秒（热点：商品原件复核、选值、缺口规划，都是逐值发布证据与原件复查逻辑）。
   `test_candidate_admission.py` 几乎每个用例都先跑 `model-source-certify`（认证包＋候选准入）CLI 作前置，本身不慢，但 654 项累积成本高。
3. **专门验证被删门禁的文件有 22 个 / 353 项**（整文件可删），v7 已记录的耗时约 2013 秒（其中 isolated_lifecycle 1936 秒）；
   其中 7 个文件是 v7 之后新增的预检/迁移测试（material/catalog/fixed-window 预检、预热、CNY030/融资迁移、回放消费，共 118 项），耗时没有全套记录。
   另有 **47 个“部分耦合”文件 / 1327 项**：主体测主流程，但前置要认证/激活，或者断言里带认证状态、PUBLIC 发布时间。这批要改，不能整删。
   只有 37 个文件 / 308 项完全不碰被删门禁。
4. **删门后的规模（推断）**：约 **1300–1500 项**，串行约 **30–50 分钟**（现为 138–148 分钟）。主要节省来自删掉 isolated_lifecycle、
   三个重型 Worker 文件改用直接登记的简单模型，以及候选准入前置的删除。剩下的大头是 Worker 完整运行类用例（每例 15–40 秒，
   原因没剖析过）。想降到 10 分钟级，还要单独处理 `test_full_run_retrieval.py` 和注册目录 Worker 用例的单例成本。
5. **最小端到端（获取→校验→派生→投影→报告）**：现有用例里没有一例能**不依赖被删门禁**、又覆盖全部五环。建议由 3 例组成：
   `test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`（13.5 秒）补断言报告、
   `test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report`（16.2 秒）去掉 `certification_status`，
   再把 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report`（420 秒）
   从生命周期夹具改为“直接登记＋显式切换”的模型，作为完整目录那一例。三核心缺失阻断另保留一例 `test_integrated_worker_core_gap.py`，同样改夹具。

## 被删门禁代号

CERT 来源认证包；PUBEV 逐值发布证据（PUBLIC 发布时间证明）；WARMUP 计算预热发布证据；PREFLIGHT 预检完整性；
REPLAY 候选准入/校准/回放；CUTOVER 生效/切换验收（激活、演练、切换清单、回退）。
判断：YES = 文件主体专测被删门禁（可整删）；PART = 部分用例专测，或前置/断言依赖被删门禁（需改写）；NO = 与被删门禁无关。
Worker 列：HEAVY = 构建完整生命周期材料；WORKER = 跑 `process_pending_run`/真实 Worker 进程；LIGHT = 其余。

## 逐文件表

用例数 = 当前收集数；已知耗时 = v7 该文件全部阶段之和（秒），“—”表示 v7 之后新增、无全套记录。按耗时降序，同为 0 秒的按目录排列。

| 测试文件 | 用例数 | 已知耗时(s) | 主要验证对象 | 是否专测被删门禁 | 代号 | 类型 |
|---|---:|---:|---|---|---|---|
| tests/integration/test_worker_registered_catalog.py | 10 | 2936.5 | 注册目录 Worker 获取→投影→报告，PPI 回退、EIA 四条件、TuShare 必需/可选 | PART（全部依赖生命周期夹具；约 4/5 函数带认证断言） | CERT,PUBEV,REPLAY,CUTOVER | HEAVY |
| tests/models/test_isolated_lifecycle.py | 7 | 1935.5 | 完整隔离候选的准入、校准、120 日回放、激活，以及材料身份 | YES | CERT,PUBEV,WARMUP,REPLAY,CUTOVER | HEAVY |
| tests/integration/test_integrated_worker_delivery.py | 2 | 1495.9 | 综合获取修复贯穿投影/报告的交付时间与来源 | PART（前置为完整生命周期，显式断言认证点） | CERT,PUBEV,REPLAY,CUTOVER | HEAVY |
| tests/models/test_candidate_admission.py | 654 | 1065.6 | 各注册家族经候选准入后的解析、选值、原件复查、上下文投影 | PART（约 50–70% 函数带门禁断言；几乎全部以 `model-source-certify` 为前置） | CERT,PUBEV,WARMUP,PREFLIGHT,REPLAY | LIGHT |
| tests/integration/test_full_run_retrieval.py | 35 | 648.3 | 完整运行检索计划、预算、采纳、续跑、日历窗口 | PART（约 22–30%） | CERT,PUBEV | WORKER |
| tests/integration/test_worker_execution.py | 24 | 60.0 | Worker 发布、报告、恢复与调度 | PART（约 19%） | CERT,PUBEV,CUTOVER | WORKER |
| tests/integration/test_lease_heartbeat_overlap.py | 4 | 46.5 | 写锁并发下的心跳续租 | NO | - | WORKER |
| tests/integration/test_worker_database_lifetime.py | 2 | 42.2 | Worker 心跳关闭与数据库寿命 | NO | - | WORKER |
| tests/adapters/test_futures_inputs.py | 71 | 41.6 | 期货合约日历、结算、证据绑定 | PART（约 50–60%，发布证据包） | PUBEV | LIGHT |
| tests/integration/test_context_acquisition_receipts.py | 25 | 34.2 | 宏观获取回执与 PUBLIC/SYSTEM 时间 | PART（约 65–80%） | CERT,PUBEV | WORKER |
| tests/integration/test_daily_reacquisition.py | 1 | 32.5 | 已验证日线不重复获取 | NO | - | WORKER |
| tests/integration/test_candidate_duration.py | 2 | 26.8 | 候选趋势实际持续天数的展示 | NO | - | WORKER |
| tests/integration/test_official_social_financing_fallback.py | 11 | 26.3 | 社融交付与官方回退 | PART（约 67–100%） | CERT,PUBEV | LIGHT |
| tests/models/test_registered_commodity.py | 14 | 26.3 | 注册商品篮子持久化与消费校验 | PART（约 23–38%） | CERT,PUBEV | LIGHT |
| tests/integration/test_core_history_refresh.py | 23 | 23.9 | 核心历史获取及 Worker 发布 | PART（约 27%） | PUBEV | WORKER |
| tests/integration/test_official_gdp_fallback.py | 21 | 23.0 | GDP 官方回退与口径 | PART（约 50–75%） | CERT,PUBEV | LIGHT |
| tests/integration/test_retrieval_ledger.py | 32 | 21.9 | 检索回执、预算、缓存、中断恢复 | NO | - | WORKER |
| tests/models/test_candidate_replay.py | 75 | 20.2 | 候选历史校准与逐日回放记录 | YES | CERT,PUBEV,REPLAY,CUTOVER | LIGHT |
| tests/integration/test_integrated_worker_core_gap.py | 1 | 18.0 | 三核心缺失阻断完整运行并保留旧投影 | PART（仅激活前置/断言） | CUTOVER | HEAVY |
| tests/integration/test_official_pmi_fallback.py | 13 | 16.2 | PMI 按指标回退及原件复验 | PART | CERT,PUBEV | LIGHT |
| tests/adapters/test_commodity_basket.py | 21 | 15.4 | 商品选约、移仓、定权 | PART（约 27%） | PUBEV | LIGHT |
| tests/integration/test_search_evidence.py | 29 | 15.3 | 搜索结果取原件并验证采纳 | PART（约 19–31%） | CERT,PUBEV | WORKER |
| tests/integration/test_worker_reviewed_context.py | 9 | 15.2 | 审定货币/社融契约的直接获取 | PART（约 50%） | CERT,PUBEV | LIGHT |
| tests/e2e/test_local_runtime_cli.py | 10 | 14.4 | 本地初始化诊断、独立 web/worker 进程 | NO | - | WORKER |
| tests/integration/test_valuation_completeness.py | 1 | 13.4 | 估值三指数九成员完整性 | NO | - | WORKER |
| tests/adapters/test_source_history_acquisition.py | 15 | 12.9 | 历史文档获取回执与失败留存 | NO | - | LIGHT |
| tests/integration/test_context_projection.py | 32 | 11.2 | 宏观派生投影的时效与选值 | PART（约 25–35%） | CERT,PUBEV | LIGHT |
| tests/integration/test_eia_html_acquisition.py | 27 | 11.2 | EIA 历史网页获取与缺失坐标 | PART（约 25%） | CERT,PUBEV | LIGHT |
| tests/integration/test_ecb_reference_acquisition.py | 24 | 10.5 | ECB 双腿交叉汇率与原件追溯 | PART（约 25–33%） | CERT,PUBEV | LIGHT |
| tests/reports/test_cli_protocol.py | 25 | 10.1 | AI 命令行协议审计与降级 | NO | - | LIGHT |
| tests/models/test_context_output_references.py | 11 | 9.7 | 回放上下文去重引用 | YES | PUBEV,REPLAY | LIGHT |
| tests/adapters/test_official_context.py | 43 | 8.6 | 官方宏观文档解析与获取 | PART（约 13%） | CERT,PUBEV | LIGHT |
| tests/integration/test_treasury_csv_acquisition.py | 27 | 8.4 | 美债 CSV 获取、缺失、版本 | PART（约 11%） | CERT,PUBEV | LIGHT |
| tests/integration/test_worker_calendar_gate.py | 3 | 7.8 | 独立交易日历缺失阻断发布 | NO | - | WORKER |
| tests/integration/test_acceptance_timing.py | 11 | 7.8 | 验收耗时目标与切换硬门 | YES | CUTOVER | LIGHT |
| tests/integration/test_official_full_run_fallback.py | 6 | 7.8 | 完整获取阶段官方 PPI 补缺 | PART | CERT,PUBEV | LIGHT |
| tests/models/test_model_replay_rollback.py | 6 | 7.7 | 回放资格、激活、限期回退 | YES | CERT,REPLAY,CUTOVER | LIGHT |
| tests/integration/test_official_metric_fallback.py | 6 | 7.6 | CPI 按缺失指标官方回退 | PART | CERT,PUBEV | LIGHT |
| tests/integration/test_official_money_fallback.py | 7 | 7.5 | 货币数据官方回退与成员完整 | PART | CERT,PUBEV | LIGHT |
| tests/integration/test_system_target_inputs.py | 9 | 6.5 | 新时间规则下使用 SYSTEM 证据 | PART（约 83–100%） | CERT,PUBEV,REPLAY | LIGHT |
| tests/integration/test_rehearsal_cutover.py | 12 | 6.1 | 演练证据与切换验收 | YES | CERT,CUTOVER | LIGHT |
| tests/models/test_model_evaluation_regressions.py | 22 | 6.0 | 历史评估的校准区间与回放资格 | YES | CERT,PUBEV,REPLAY | LIGHT |
| tests/acceptance/test_v1_acceptance.py | 2 | 5.1 | 离线统一回归与性能验收 | PART（1/2） | PUBEV | LIGHT |
| tests/models/test_p2_identity_migration.py | 14 | 5.0 | P2 身份迁移的候选准入 | YES | CERT,REPLAY | LIGHT |
| tests/models/test_ecb_identity_migration.py | 12 | 4.2 | ECB 新身份的候选准入 | YES | CERT,REPLAY | LIGHT |
| tests/integration/test_inventory_period_alignment.py | 9 | 4.1 | 库存代理按共同月份取值 | NO | - | LIGHT |
| tests/integration/test_context_model_certification.py | 25 | 3.7 | 派生公式不得绕过模型认证 | YES | CERT | LIGHT |
| tests/web/test_projection_api.py | 9 | 3.6 | 投影/证据/日历/命令 API | PART（约 22–33%） | CERT,REPLAY,CUTOVER | LIGHT |
| tests/integration/test_derived_context_freshness.py | 20 | 3.3 | 派生结果继承输入时效 | NO | - | LIGHT |
| tests/integration/test_worker_ecb_refresh.py | 6 | 2.8 | ECB 直接刷新与 SYSTEM 采用 | PART（约 50%） | CERT,PUBEV | LIGHT |
| tests/models/test_capacity_historical_contract.py | 10 | 2.7 | 旧产能认证依赖不可省 | YES | CERT | LIGHT |
| tests/adapters/test_tushare_context.py | 21 | 2.6 | TuShare 宏观/市场标量契约 | PART（约 35%） | CERT,PUBEV | LIGHT |
| tests/integration/test_futures_warrant_completeness.py | 2 | 2.3 | 仓单分页完整性 | PART（1/2，附带时间断言） | PUBEV | LIGHT |
| tests/integration/test_database_lifetime.py | 2 | 2.3 | 重复读库不耗尽句柄 | NO | - | LIGHT |
| tests/integration/test_gdp_semantics.py | 5 | 2.0 | GDP 累计水平与增速口径 | PART（约 67%） | CERT,PUBEV | LIGHT |
| tests/e2e/test_v1_cli.py | 5 | 1.9 | 模型/运行/证据/报告公开命令 | PART（约 60%） | CERT,REPLAY,CUTOVER | LIGHT |
| tests/reports/test_report_boundary.py | 15 | 1.8 | 报告事实边界、快照、失败降级 | NO | - | LIGHT |
| tests/adapters/test_chinamoney_lpr.py | 11 | 1.7 | LPR 解析入库与发布日历 | PART（约 38%） | CERT,PUBEV | LIGHT |
| tests/evidence/test_point_in_time.py | 20 | 1.6 | 证据双时点、修订、冲突、血缘 | PART（约 41–53%） | CERT,PUBEV | LIGHT |
| tests/models/test_model_lifecycle.py | 21 | 1.6 | 模型验收、激活、上下文回放门 | YES | CERT,PUBEV,PREFLIGHT,REPLAY,CUTOVER | LIGHT |
| tests/integration/test_run_orchestration.py | 8 | 1.6 | 运行幂等、租约恢复、调度 | NO | - | LIGHT |
| tests/e2e/test_core_fixture_cli.py | 3 | 1.5 | 核心夹具投影与缺口说明 CLI | PART（1/3，断言模型为 candidate） | CUTOVER | LIGHT |
| tests/integration/test_worker_eia_html_fallback.py | 2 | 1.4 | EIA 缺密钥后网页回退 | PART（1/2） | CERT | LIGHT |
| tests/integration/test_p2_source_timing.py | 2 | 1.4 | P2 来源时间随获取状态展示 | PART | CERT,PUBEV | LIGHT |
| tests/integration/test_source_contract_quarantine.py | 4 | 1.4 | 失效认证阻止激活与重新发布 | YES | CERT,REPLAY,CUTOVER | WORKER |
| tests/integration/test_loan_ytd_year_boundary.py | 14 | 1.2 | 贷款年初累计转月度流量 | PART（仅公开时间传播断言） | PUBEV | LIGHT |
| tests/adapters/test_eia_context.py | 15 | 1.2 | EIA 接口身份与入库 | PART（约 56%） | CERT,PUBEV | LIGHT |
| tests/adapters/test_rrr_context.py | 13 | 1.2 | 降准机构范围及修订 | PART（约 33%） | CERT,PUBEV | LIGHT |
| tests/integration/test_omo_invalid_flow.py | 9 | 0.8 | 公开市场无效流量不补零 | PART（仅公开时间传播断言） | PUBEV | LIGHT |
| tests/e2e/test_lpr_release_cli.py | 3 | 0.7 | LPR 公开命令与自认证限制 | PART（约 67%） | CERT,CUTOVER | LIGHT |
| tests/domain/test_trend_state.py | 10 | 0.7 | 趋势持续性与候选天数 | NO | - | LIGHT |
| tests/models/test_source_certification.py | 4 | 0.6 | 来源认证包创建与历史来源约束 | YES | CERT | LIGHT |
| tests/integration/test_official_negative_cache.py | 1 | 0.5 | 跨目标日复用官方负缓存 | NO | - | WORKER |
| tests/adapters/test_margin_candidate.py | 14 | 0.4 | 融资交易所矩阵与候选值 | PART（约 25%） | CERT,PUBEV | LIGHT |
| tests/adapters/test_official_money_units.py | 5 | 0.4 | 货币余额精确单位 | PART（约 33%） | CERT | LIGHT |
| tests/adapters/test_source_history.py | 1 | 0.4 | 历史发布日期次日可见 | YES | PUBEV | LIGHT |
| tests/adapters/test_capacity_column_completeness.py | 11 | 0.3 | 产能利用率列完整性 | NO | - | LIGHT |
| tests/web/test_dashboard_contract.py | 13 | 0.3 | 驾驶舱展示契约 | PART（约 8%，“认证 certified”文案） | CERT | LIGHT |
| tests/integration/test_p0_gate.py | 5 | 0.2 | P0 阻断与跨数据集约束 | NO | - | LIGHT |
| tests/integration/test_atomic_projection.py | 3 | 0.1 | 六数据集原子发布 | NO | - | LIGHT |
| tests/maintenance/test_retention_capacity.py | 5 | 0.1 | 留存清理与容量水位 | NO | - | LIGHT |
| tests/adapters/test_market_breadth_inputs.py | 44 | 0.0 | 市场宽度成员行情与停牌 | NO | - | LIGHT |
| tests/adapters/test_metric_identity.py | 7 | 0.0 | 核心指标身份与单位 | NO | - | LIGHT |
| tests/adapters/test_search_discovery.py | 3 | 0.0 | 搜索发现与脱敏 | NO | - | LIGHT |
| tests/adapters/test_tushare_core_adapter.py | 7 | 0.0 | 核心接口身份、收益率、日历 | NO | - | LIGHT |
| tests/catalog/test_metric_catalog.py | 5 | 0.0 | 指标目录身份、维度、认证状态 | PART（约 40%） | CERT | LIGHT |
| tests/catalog/test_official_fallback_candidates.py | 1 | 0.0 | 同族指标共享官方文档 | NO | - | LIGHT |
| tests/catalog/test_release_calendar.py | 6 | 0.0 | 发布窗口时效与刷新决策 | NO | - | LIGHT |
| tests/domain/test_bond_direction.py | 1 | 0.0 | 债券方向确认 | NO | - | LIGHT |
| tests/domain/test_boundary_types.py | 1 | 0.0 | 领域类型不加载框架 | NO | - | LIGHT |
| tests/domain/test_futures_rolls.py | 2 | 0.0 | 连续期货移仓收益 | NO | - | LIGHT |
| tests/domain/test_macro_states.py | 19 | 0.0 | 宏观/库存状态 | NO | - | LIGHT |
| tests/domain/test_pring_stage.py | 10 | 0.0 | 三资产映射正式六阶段 | NO | - | LIGHT |
| tests/domain/test_secret_boundary.py | 1 | 0.0 | 仅数据源凭据进入配置 | NO | - | LIGHT |
| tests/e2e/test_official_context_cli.py | 2 | 0.0 | 官方宏观/EIA 离线契约 CLI | NO | - | LIGHT |
| tests/retrieval/test_cascade.py | 9 | 0.0 | 串行检索降级与预算 | NO | - | LIGHT |
| tests/adapters/test_fixed_window_calendar.py | 1 | — | 交易日排除调休周日 | NO | - | LIGHT |
| tests/catalog/test_registered_catalog_reuse.py | 4 | — | 注册目录共享读取与损坏复查 | PART（1/4） | REPLAY | LIGHT |
| tests/maintenance/test_verification_inputs.py | 10 | — | 软件/材料身份分离（收据驱动） | NO（服务于冻结收据，随 ADR-0014 取舍） | - | LIGHT |
| tests/models/test_material_preflight.py | 34 | — (09-22 分支记录 33 项/84.24 秒) | 候选材料覆盖、预热、原件预检 | YES | CERT,PUBEV,WARMUP,PREFLIGHT | LIGHT* |
| tests/models/test_catalog_preflight.py | 17 | — | 逐指标目录预检 | YES | CERT,PUBEV,PREFLIGHT | LIGHT |
| tests/models/test_fixed_window_preflight.py | 14 | — | 固定窗口日历预检与收据 | YES | PUBEV,WARMUP,PREFLIGHT | LIGHT |
| tests/models/test_core_formula_warmup.py | 18 | — | 核心公式预热的公开证据预检 | YES | CERT,PUBEV,WARMUP,PREFLIGHT | LIGHT |
| tests/models/test_core_replay_consumption.py | 1 | — | 首次正式回放消费预热证据 | YES | PUBEV,WARMUP,REPLAY | LIGHT |
| tests/models/test_cny030_optional_migration.py | 29 | — | CNY030 降为 P2 的候选准入 | YES | CERT,REPLAY | LIGHT |
| tests/models/test_margin_scope_migration.py | 5 | — | 两交易所融资身份的候选准入 | YES | CERT,REPLAY | LIGHT |

\* `test_material_preflight.py` 在 `tools/check.py` 的 `HEAVY_FILES` 里，但它只借用生命周期模块的导入函数、不跑完整生命周期（Codex 判断，已核：导入 `tests.models.test_isolated_lifecycle` 的辅助函数）。
单次耗时引自 [09-22 execution-status](../../pring-window-publication-20260922/execution-status.md)（heavy-04-preflight-parent-r3：33 passed / 84.24 秒），那是别的分支上的数字。

汇总（当前 1988 项；秒数只统计 v7 有记录的文件）：

| 分类 | 文件 | 用例 | v7 耗时(s) | 其中 v7 后新增文件 |
|---|---:|---:|---:|---:|
| YES（整文件专测被删门禁） | 22 | 353 | 2012.6 | 7 |
| PART（需改写） | 47 | 1327 | 6575.1 | 1 |
| NO（无关，保留） | 37 | 308 | 243.5 | 2 |

PART 按类型拆分：HEAVY 3 个文件 / 13 项 / 4450 秒；WORKER 5 个 / 136 项 / 782 秒；LIGHT 39 个 / 1178 项 / 1343 秒（其中 candidate_admission 独占 654 项 / 1066 秒）。

## 耗时大户及原因

| 大户 | v7 耗时 | 原因（出处） |
|---|---|---|
| `test_isolated_lifecycle.py::test_complete_isolated_candidate_is_calibrated_replayed_and_activated` | 1741.7 秒（v3 为 2002 秒，v2 含冷材料构建的首例为 2067.65 秒） | legacy 生命周期强制冷构建：公开准入（认证包）、校准、120 日回放、激活，每段一个独立进程（文件 1–48、888–936 行；[慢用例清单](../../pring-data-acquisition-repair/slow-test-inventory-20260918.md)）。材料身份键覆盖源码，改 `src/` 就作废（ADR-0014）。 |
| `test_worker_registered_catalog.py` 10 项 | 2936.5 秒；单例 350–430 秒 | 每例从生命周期材料复制出独立运行库，再在完整注册目录（59 项）上跑 Worker 全流程。热点是商品原件复核、选值、缺口规划（慢用例清单“已测改善与下一步”）。 |
| `test_integrated_worker_delivery.py` 2 项 | 1495.9 秒；单例 747–918 秒（v2–v7） | 同一生命周期材料，两个目标日的真实 Worker 发布链，外加必需字段失败分支。每例独立副本约 3.2 GB，结束后回收（continuation-status 09-18 v5 段）。 |
| `test_candidate_admission.py` 654 项 | 1065.6 秒 | 单例都不重（最大 33 秒），但 145 个函数参数化成 654 项，几乎全以 `submit()` → `model-source-certify` CLI（第 120–132 行）为前置，每例新建运行库、存制品、走准入。最重的两个参数化函数：`test_registered_window_breadth_uses_full_window_with_hidden_warmup` 27 项 / 232.5 秒，`test_registered_credit_window_requires_comparable_gdp_release_baselines` 36 项 / 203.5 秒。 |
| `test_full_run_retrieval.py` 35 项 | 648.3 秒；多例 30–40 秒 | 每例都跑完整 `process_pending_run`：检索计划、预算、日历窗口。模型只用 `record_acceptance`＋`activate("model-v0001")` 直接激活（第 25–27 行），不经生命周期。单例 30 秒以上的原因**没剖析过**（慢清单写的是“进一步优化需单独证据”）。 |
| 其余 101 个文件 | 约 650 秒 | Worker/租约类单例 15–35 秒，其余基本在 1 秒以内。 |

v7 所有文件的 setup 阶段都不超过 5 秒：材料构建计入 call，缓存命中时热运行。全套磁盘峰值 60.51 GiB，主要是 basetemp 中的隔离运行库（docs/agents/testing.md）。

## 删门后的剩余规模与耗时（推断，未实测）

| 部分 | 处理 | 预计用例 | 预计耗时 |
|---|---|---:|---:|
| YES 22 个文件 | 整删 | 0（−353） | −2013 秒以上（外加新增预检文件，约 85 秒以上） |
| 重型 PART 3 个文件（13 项） | 改用“直接登记目录＋显式切换”的简单模型夹具，参照 `test_full_run_retrieval.py` 的直接激活写法；删认证断言；可合并 EIA 四条件等参数 | 6–13 | 约 400–800 秒（按 Worker 单例 30–60 秒估；完整目录比 full_run_retrieval 大，也可能更慢） |
| `test_candidate_admission.py` | 去掉认证/准入前置，保留各家族“结构校验/原件损坏拒收/选值/投影”断言，移到获取或派生层；删除认证、PUBLIC 截止、回放预检类断言 | 约 200–330 | 约 300–600 秒（预热窗口两函数若保留“回看计算”但去掉发布证据，仍是主要成本） |
| 其余 PART（WORKER 5 个、LIGHT 38 个） | 删认证/PUBLIC 断言、改前置 | 约 550–600 | 约 900–1100 秒（full_run_retrieval 占大头） |
| NO 37 个文件 | 保留 | 308 | 约 245 秒 |
| **合计** | | **约 1300–1500** | **约 1900–2800 秒 ≈ 30–50 分钟（串行）** |

说明：

- 这些都是按 v7 单例成本外推的。改写后夹具变轻，实际可能更快；新门禁（时效、结构、加工批次）会新增测试，可能更多。
- 删门后，单例成本的主因会从“生命周期材料”变成“完整 Worker 运行”（15–40 秒/例，约 40–60 例）。想接近 ADR-0014 所说“可以随手运行”的 10 分钟级，要么剖析并压低 Worker 单例成本，要么把完整 Worker 用例收窄到下述最小端到端集合，其余下沉为组件测试。项目目前没装 pytest-xdist，并行化另需评估（数据库/端口隔离）。
- 生命周期材料删掉以后，材料身份键和冻结收据跟着失去主要理由（ADR-0014 的前提是“材料身份键覆盖源码”）。`tools/check.py` 的 `HEAVY_FILES` 和 `tests/maintenance/test_verification_inputs.py` 是否保留，应由票 08（开发验证策略）一并决定。

## 最小端到端用例候选（获取→校验→派生→投影→报告）

| node id | v7 耗时 | 覆盖环节 | 依赖被删门禁？ | 离线 |
|---|---:|---|---|---|
| `tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability` | 13.5 秒 | 真实 TuShare 适配器（HTTP 替身）获取 → 结构/日历校验 → 趋势/阶段 → Worker 投影；报告阶段执行了，但没断言报告 | 只用 `record_acceptance`＋`activate("model-v0001")`（第 243–244 行），不涉认证包和回放；断言里有 PUBLIC/SYSTEM 可见性（PUBEV），要改成“按频率推定”的口径 | 是 |
| `tests/integration/test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` | 16.2 秒 | 预置证据 → P0 校验 → 趋势/非典型组合 → 投影 → 确定性降级报告（`report_adapters=()`，`completed_degraded`） | 预置声明带 `certification_status="certified"` 和 `public_available_at`（第 474–477 行），要去掉；直接激活 model-v0001 | 是 |
| `tests/integration/test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` | 420.3 秒 | 完整注册目录：核心＋宏观获取、官方 PPI 回退 → 校验 → 派生 → 投影 → 报告里的交付来源 | **是**：依赖 `isolated_lifecycle_material`（准入/校准/回放/激活）。须改用直接登记的夹具，才能当“完整目录”那一例 | 是 |
| `tests/integration/test_integrated_worker_core_gap.py::test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original` | 18.0 秒（外加材料） | 反例：三核心缺失时阻断正式阶段、保留旧投影 | 是（生命周期夹具）；要改夹具 | 是 |
| `tests/e2e/test_core_fixture_cli.py::test_public_fixture_command_projects_the_three_core_tracks_atomically` | 0.54 秒 | 本地夹具 → 结构校验 → 三核心派生 → 原子投影；不经适配器，不出报告 | 否（断言模型保持 candidate，属 CUTOVER 语义的附带断言） | 是（`network_requests == 0`） |

建议：前两例补断言后组成最快的正例冒烟（约 30 秒）；第三例改夹具后作为完整目录的正例；第四例作三核心缺失的反例；`test_worker_calendar_gate.py`（3.9 秒/例）作日历反例。第五例太浅（不经获取、没有报告），只适合当秒级的派生/投影冒烟。

## 核实记录（抽查 Codex 结论）

- 用例数：本人 `pytest --collect-only -q`，1988 项。v7 的 1848 项与当前树按文件逐一比对，差异全部落在 13 个文件（10 个 v7 后新增文件，另 3 个文件用例数小幅变化：commodity_basket、worker_calendar_gate、registered_commodity）。
- 耗时：本人从 v7 事件 JSONL 逐节点聚合，总和 8830.8 秒，与收据 8865.15 秒相差不到 0.5%。
- `test_candidate_admission.py`：`submit(` 出现 159 次，`submit()` 调用 `model-source-certify`（第 120–132 行），已核。
- 三个重型文件都从 `tests.models.test_isolated_lifecycle` 导入 `isolated_lifecycle_material`，已核；生命周期文件的 docstring 写明“admission, calibration, replay and activation”。
- `test_full_run_retrieval.py` 直接激活 model-v0001（第 25–27 行），已核。
- 三个最小端到端候选的断言与前置（`report_adapters=()`、`completed_degraded`、`certification_status="certified"`、`network_requests == 0`、第 243–244 行激活）逐一核对过行号。
- 没核实的部分：PART 文件里“门禁相关函数比例”只是 Codex 的估计，本人没逐函数复核；删门后的规模与耗时是推断。
