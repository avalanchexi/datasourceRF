Type: research
Status: resolved
Blocked by: none

# 盘点测试套件与被删门禁的耦合

## Question

现有默认全套（约 1848 项、约 8865 秒）中，哪些测试文件/用例专门验证将被删除的门禁（来源认证包、逐值发布证据、计算预热发布证据、预检完整性、候选回放、生效/切换验收）？哪些是耗时大户，耗时来自什么（构建完整模型、真实 Worker 生命周期、夹具日历）？删除这些门禁后，剩余套件的规模与预计耗时量级如何，以及覆盖主流程所需的最小端到端用例是哪几个？不跑重型测试，基于已有慢用例清单与代码阅读。

## Answer

见 [研究：测试套件分层](../research/03-test-suite-layering.md)。
- 耗时高度集中：v7 的 8831 秒中，5 个文件占 93%（注册目录 Worker 2937 秒、隔离生命周期 1936 秒、综合 Worker 交付 1496 秒、候选准入 1066 秒 / 654 项、完整运行检索 648 秒）。前三者的根因是 `isolated_lifecycle_material`（认证→准入→校准→120 日回放→激活，冷构建 1742–2068 秒，改源码即失效），外加每例约 3.2 GB 副本上的完整目录 Worker。
- 当前 1988 项中：22 个文件 / 353 项整文件专测被删门禁（可删）；47 个文件 / 1327 项部分耦合（前置或断言依赖认证/PUBLIC/激活，需改写）；37 个文件 / 308 项无关。
- 推断删门后约 1300–1500 项、串行 30–50 分钟。剩下的大头是 Worker 完整运行（15–40 秒/例，成因未剖析），想到 10 分钟级需另行处理。
- 最小端到端：`test_core_history_refresh::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution::test_worker_completes_a_valid_noncanonical_projection_and_report`（两例各需去认证/补报告断言），加改夹具后的 `test_worker_registered_catalog::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report`；三核心缺失反例用 `test_integrated_worker_core_gap`。

