# 2026-09-25 旧票现状核对

Codex 只读静态核对（未跑测试、未联网），A 类三张经人工抽查属实（fast-refactor 票 15 删除验收/回放/切换链，迁移 `0025_drop_model_lifecycle` 删模型生命周期表）。A 被取代；B 已交付仍有效，只差人工复核；C 部分取代。票面状态：A 改为 superseded，B/C 保留原状态并在 Comments 指向本文。

由此发现的两处重构遗留已另立票：[run-resume 与 ADR-0024](../acceptance-findings-20260925/issues/05-run-resume-after-adr-0024.md)、[报告正文 30 天清空](../acceptance-findings-20260925/issues/06-report-body-30-day-clear.md)。

以下按核心功能判断；B 表示软件实现仍在、可供人工复核，不表示本次已验收。源码证据均位于 `src/pring_cycle/`；FR 指 `.scratch/pring-fast-refactor-20260923/issues/`。当前源码还落实了 ADR-0026–0028，相关行一并注明。

| 票号 | 类别 | 一句理由 | 证据 file:line |
|---|---|---|---|
| 01 | **B 已交付仍有效** | 初始化、离线 doctor、本机 Web/Worker 仍在；旧统一验收入口的撤除归入 24。 | [cli.py:420](../../src/pring_cycle/cli.py:420)、[runtime.py:145](../../src/pring_cycle/runtime.py:145)、[web.py:468](../../src/pring_cycle/web.py:468) |
| 02 | **C 部分取代** | 双点时契约被 ADR-0022 废弃，摄取和追溯保留，但源码甚至仍暴露双模式查询，不能称已删净。 | [ADR-0022:7](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[evidence.py:911](../../src/pring_cycle/evidence.py:911)、[web.py:119](../../src/pring_cycle/web.py:119) |
| 03 | **B 已交付仍有效** | fixture 正式入口、120日趋势、30日候选、12M代理及六阶段机械映射仍在。 | [core_fixture.py:39](../../src/pring_cycle/core_fixture.py:39)、[domain/trend.py:120](../../src/pring_cycle/domain/trend.py:120)、[domain/stage.py:28](../../src/pring_cycle/domain/stage.py:28) |
| 04 | **C 部分取代** | 非典型组合留空仍有效，但“一缺即阻止发布”改为落后一期可沿用、严重缺口仅阻断正式阶段。 | [ADR-0021:7](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[p0.py:106](../../src/pring_cycle/p0.py:106)、[domain/stage.py:38](../../src/pring_cycle/domain/stage.py:38) |
| 05 | **C 部分取代** | 股票、债券真实核心接口保留，来源认证和对应 smoke 门禁被撤销。 | [FR/16:19](../../.scratch/pring-fast-refactor-20260923/issues/16-delete-source-certification-and-preflight.md:19)、[source_adapters.py:18](../../src/pring_cycle/source_adapters.py:18)、[source_adapters.py:186](../../src/pring_cycle/source_adapters.py:186) |
| 06 | **C 部分取代** | NHII 核心及取数保留，认证包、认证区间和预认证后备的门禁语义失效。 | [ADR-0021:7](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[source_adapters.py:21](../../src/pring_cycle/source_adapters.py:21)、[source_adapters.py:186](../../src/pring_cycle/source_adapters.py:186) |
| 07 | **A 被取代** | 核心交付物“候选校准→无前视回放→机器验收→生效”已删除，改为登记版本后显式切换。 | [FR/15:20](../../.scratch/pring-fast-refactor-20260923/issues/15-delete-candidate-replay-cutover-chain.md:20)、[models.py:288](../../src/pring_cycle/models.py:288) |
| 08 | **C 部分取代** | 指标目录和发布日历保留，认证状态及逐值发布时间证明改为注册来源与推定时效。 | [ADR-0021:7](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[web.py:165](../../src/pring_cycle/web.py:165)、[dashboard.py:559](../../src/pring_cycle/dashboard.py:559) |
| 09 | **C 部分取代** | 串行检索、负缓存和手动深搜仍在，但旧预算、Exa顺序、认证准入及P2禁用AI规则已替换。 | [ADR-0023:7](../../docs/adr/0023-retrieval-verification-by-registered-parsers.md:7)、[retrieval.py:35](../../src/pring_cycle/retrieval.py:35)、[retrieval.py:97](../../src/pring_cycle/retrieval.py:97) |
| 10 | **C 部分取代** | 政策行动、市场传导分区和方向计算保留，认证、点时入场及官方抽样门禁失效。 | [ADR-0021:11](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:11)、[context_projection.py:435](../../src/pring_cycle/context_projection.py:435)、[context_projection.py:465](../../src/pring_cycle/context_projection.py:465) |
| 11 | **C 部分取代** | 信用响应、信用脉冲及输入血缘保留，“真实公开/系统双点时后才可见”的保证被替换。 | [ADR-0022:7](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[context_projection.py:424](../../src/pring_cycle/context_projection.py:424)、[context_projection.py:475](../../src/pring_cycle/context_projection.py:475) |
| 12 | **C 部分取代** | 过热状态及支持、反证、缺口输出保留，旧点时输入和真实抽样认证条件失效。 | [ADR-0021:11](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:11)、[domain/macro.py:109](../../src/pring_cycle/domain/macro.py:109)、[context_projection.py:481](../../src/pring_cycle/context_projection.py:481) |
| 13 | **C 部分取代** | 物价传导链和能源解释边界保留，认证来源、逐值真实发布时间及“未认证即缺口”规则失效。 | [ADR-0021:7](../../docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[context_projection.py:489](../../src/pring_cycle/context_projection.py:489) |
| 14 | **B 已交付仍有效** | 库存四象限、七张独立卡、实际库存近似及“不合成总分”的核心功能仍在。 | [domain/macro.py:155](../../src/pring_cycle/domain/macro.py:155)、[context_projection.py:501](../../src/pring_cycle/context_projection.py:501) |
| 15 | **C 部分取代** | 国际背景展示及不参与中国阶段判断保留，待认证状态和P2止于Exa规则废弃；真实来源齐备性不能据此认定。 | [ADR-0023:7](../../docs/adr/0023-retrieval-verification-by-registered-parsers.md:7)、[context_projection.py:498](../../src/pring_cycle/context_projection.py:498)、[context_projection.py:564](../../src/pring_cycle/context_projection.py:564) |
| 16 | **C 部分取代** | 六分区原子发布仍有效，但旧验收项“P0失败不得发布新投影”已改变。 | [projections.py:89](../../src/pring_cycle/projections.py:89)、[p0.py:106](../../src/pring_cycle/p0.py:106)、[ADR-0022:11](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:11) |
| 17 | **C 部分取代** | 手动父运行、持久化和编排保留，旧P0失败即停止投影与报告的处理被替换。 | [runs.py:110](../../src/pring_cycle/runs.py:110)、[p0.py:106](../../src/pring_cycle/p0.py:106)、[worker.py:502](../../src/pring_cycle/worker.py:502) |
| 18 | **C 部分取代** | 取消和可选调度保留，恢复机制按ADR应改为新批次重跑，但当前CLI与Worker仍能恢复原运行并复用检查点。 | [ADR-0024:7](../../docs/adr/0024-interrupted-runs-restart-as-new-batches.md:7)、[cli.py:334](../../src/pring_cycle/cli.py:334)、[worker.py:271](../../src/pring_cycle/worker.py:271)、[runs.py:862](../../src/pring_cycle/runs.py:862) |
| 19 | **C 部分取代** | CLI双适配器与确定性降级保留，逐条证据包和引用语义校验被后续ADR-0027撤销。 | [ADR-0027:7](../../docs/adr/0027-report-input-is-verified-results-without-evidence-chain.md:7)、[reports.py:706](../../src/pring_cycle/reports.py:706)、[reports.py:765](../../src/pring_cycle/reports.py:765) |
| 20 | **C 部分取代** | 生成、历史、阅读工作区保留，绑定证据引用及正文过期后永久保留结构化身份的承诺已替换。 | [dashboard.py:1001](../../src/pring_cycle/dashboard.py:1001)、[ADR-0027:9](../../docs/adr/0027-report-input-is-verified-results-without-evidence-chain.md:9)、[retention.py:136](../../src/pring_cycle/retention.py:136) |
| 21 | **C 部分取代** | 容量水位和重新初始化保留，长期保留改为120交易日清理；旧30天正文清空代码仍残留。 | [ADR-0022:7](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[maintenance.py:33](../../src/pring_cycle/maintenance.py:33)、[maintenance.py:159](../../src/pring_cycle/maintenance.py:159) |
| 22 | **A 被取代** | 并行回放、质量验收和30交易日回退保证整套生命周期已删除，只剩版本指针切换。 | [ADR-0022:7](../../docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[FR/15:20](../../.scratch/pring-fast-refactor-20260923/issues/15-delete-candidate-replay-cutover-chain.md:20)、[migrations/versions/0025_drop_model_lifecycle.py:13](../../src/pring_cycle/migrations/versions/0025_drop_model_lifecycle.py:13) |
| 23 | **B 已交付仍有效** | 八页导航、明暗主题记忆、中文市场状态色和键盘焦点实现仍在，视觉效果待人工复核。 | [navigation.py:3](../../src/pring_cycle/navigation.py:3)、[assets/dashboard.js:5](../../src/pring_cycle/assets/dashboard.js:5)、[assets/dashboard.css:15](../../src/pring_cycle/assets/dashboard.css:15)、[assets/dashboard.css:74](../../src/pring_cycle/assets/dashboard.css:74) |
| 24 | **A 被取代** | 统一acceptance及切换性能硬门已删除，改为受影响测试、切片冒烟和终点全套策略。 | [FR/15:20](../../.scratch/pring-fast-refactor-20260923/issues/15-delete-candidate-replay-cutover-chain.md:20)、[ADR-0025:7](../../docs/adr/0025-affected-tests-daily-full-suite-once.md:7) |
| 25 | **C 部分取代** | 切换清单、机器切换与旧演练链已删除，但运行文档和真实完整运行目标仍有效，后者转由FR28承接。 | [FR/15:20](../../.scratch/pring-fast-refactor-20260923/issues/15-delete-candidate-replay-cutover-chain.md:20)、[FR/16:19](../../.scratch/pring-fast-refactor-20260923/issues/16-delete-source-certification-and-preflight.md:19)、[FR/28:19](../../.scratch/pring-fast-refactor-20260923/issues/28-endpoint-full-suite-and-real-run.md:19) |

**不确定／不能直接关闭的票：**

- **02、18**：取代决策明确，但旧机制仍有可达入口；不确定这是兼容保留还是重构遗漏，不能写成“已删除”。
- **20、21**：120交易日删除与旧30天正文清空并存，留存行为尚未统一；另有事件现行基准的窗口外保留例外（[retention.py:150](../../src/pring_cycle/retention.py:150)）。
- **15**：可确认展示及降级功能，不能确认全部国际来源实际可用；FR仍记录来源缺口（[map.md:54](../../.scratch/pring-fast-refactor-20260923/map.md:54)）。

本次仅静态只读核对，未改文件、未跑测试、未联网。
