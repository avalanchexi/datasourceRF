# 候选 3 勘察：目标日与补算日两条路径

来源：Codex 只读勘察（2026-09-29，`gpt-6-astra`／high，约 13 万 tokens），原样收录其结论。第 2 条已抽查属实（`context_projection.py:263` 按目标日包装仓库）；第 8 条"历史投影阶段史含未来日期"已核（`projections.py:164`、`p0.py:202`）。访谈结论见 [README](README.md)。

1. **结论：上下文“未限制公开时间”的前提不成立；补算漏传窗口缺口门禁则确实可能放出正式阶段。** 下表中“明确”指 ADR／票据要求，“未见依据”指没有找到允许该差异的要求，并不等于已经实测为缺陷；本次仅阅读文件与静态解析调用，没有修改文件、运行测试或访问外部接口。

   | 对比项 | 目标日 | 补算日 | 依据判断 |
   |---|---|---|---|
   | 核心 `public_as_of` | 不传，按 `system_as_of` 读取，再限制统计日≤目标日 | 显式传上海时区当日 `time.max` | **明确**：运行冻结时点与历史公开边界有别；票07:22、票24:19；`src/pring_cycle/worker.py:407`、`:584`、`:1137` |
   | 核心 `window_gaps` | 从最终计划提取核心缺失，排除目标日自身 | 默认空集合 | **未见依据，可能遗漏**；`src/pring_cycle/worker.py:398`、`:587`、`:1124` |
   | 核心 `calendar` | 最终计划中的交易日历 | 同一个日历 | **相同**；主要用于找前一交易日，不自动验证序列连续；`src/pring_cycle/worker.py:378`、`:412`、`:592`、`:1130` |
   | 上下文 `as_of` | `run.system_as_of` | 同值 | **相同**；`src/pring_cycle/worker.py:419`、`:597` |
   | 上下文公开边界 | 内部按目标日结束过滤 | 内部按补算日结束过滤 | **明确且已有实现**；`src/pring_cycle/context_projection.py:263`、`:659` |
   | `persist_derived` | 默认 `True` | `False` | **未见明确依据**；补算只生成派生身份、不保存派生记录；`src/pring_cycle/context_projection.py:250`、`:1374`；`src/pring_cycle/worker.py:608` |
   | 快照 | 有输入时冻结核心展示输入、模型输入及上下文输入；无输入仍会哈希回退 | 不冻结，总是走核心资产文档哈希回退 | **未见历史日豁免依据**；ADR-0008要求共享快照；`src/pring_cycle/worker.py:447`、`:460`、`:610`；`src/pring_cycle/p0.py:102` |
   | warnings | explanatory warnings 与 context warnings 合并去重 | 仅 context warnings | **未见依据，可能遗漏**；两者发布时都另加核心缺失／沿用 warning；`src/pring_cycle/worker.py:482`、`:616`；`src/pring_cycle/p0.py:106` |
   | `gap_list` | 批次缺口加投影缺口、派生需求缺口 | 默认空列表 | **未见依据，可能遗漏**；核心 assessment 自身的 `gaps` 仍存在，不能混同；`src/pring_cycle/worker.py:497`；`src/pring_cycle/p0.py:72`、`:77`、`:192` |
   | `release_calendar_events` | 调用 `_release_calendar_documents`，当前实现为 LPR 日历 | 默认空列表 | **未见依据，可能遗漏**；`src/pring_cycle/worker.py:431`、`:1095`；`src/pring_cycle/p0.py:71` |
   | `last_confirmed_stage` | 补算结束后读取 | 每个补算日发布前读取 | **明确的逐日重建方向**；精确编排顺序属实现；票24:19；`src/pring_cycle/worker.py:446`、`:614` |
   | 批次 id | 当前运行 id | 同一运行 id，未创建每日批次 | **明确且相同**：ADR-0022:7；`src/pring_cycle/worker.py:218`、`:583`；`src/pring_cycle/p0.py:133` |
   | 检查点 | `verified_evidence`、`p0_assessment`、绑定发布投影、报告检查点 | 无逐日检查点；靠已汇总日期跳过 | ADR-0031明确保留运行恢复，**未要求逐日检查点**；`src/pring_cycle/worker.py:467`、`:508`、`:517`、`:547` |
   | 报告 | 发布并绑定后生成 | 不生成 | **明确**：ADR-0024:7、票07:21、票24:3；`src/pring_cycle/worker.py:520`、`:610` |

   此处票07为 `.scratch/pring-fast-refactor-20260923/issues/07-simplified-run-pipeline-shape.md`，票24为同目录 `24-first-initialization-and-missed-day-backfill.md`；ADR路径分别为 `docs/adr/0008-atomic-analytical-projection-sets.md:7`、`0022-uniform-120-day-retention-and-processing-batches.md:7`、`0024-interrupted-runs-restart-as-new-batches.md:7`、`0031-keep-run-resume.md:9`。

2. **补算宏观、库存并非直接读取运行时点的全部明细，不能据 `as_of` 判定存在前视。** `build_context_projection` 把仓库包装为 `TargetBoundEvidenceRepository`，查询加入上海时区补算日结束的 `public_as_of`，随后再次筛选声明并重新选值；库存及信用派生也使用包装后的仓库，证据见 `src/pring_cycle/context_projection.py:263`、`:609`、`:659`、`:703`、`:455`、`:2167`。但有一个条件例外：`dual-cutoff-v0003` 模型允许“系统在当日已取得”的声明，即使声明公开时间更晚，因此不能声称所有模型都严格满足字面上的 `public_available_at≤当日`；它仍不允许公开时间和系统可用时间都晚于补算日的声明，见 `src/pring_cycle/catalog_registry.py:31`、`src/pring_cycle/context_projection.py:267`、`:720`、`src/pring_cycle/evidence.py:1009`。另外实现截的是**当日结束，不是交易所收盘时刻**，且未知发布时间可按登记节奏推定，不能扩大为“真实官方发布时间已经逐值证明”，见 `src/pring_cycle/worker.py:584`、`src/pring_cycle/evidence.py:1654`。

   | 已有覆盖 | 证据与覆盖边界 |
   |---|---|
   | 补算日 CPI 前视 | `tests/integration/test_backfill.py:116`：8月4日不含7月CPI，8月5日包含；共享夹具中的公布时间为8月5日09:30 |
   | 统计期结束但尚未公布 | `tests/integration/test_context_projection.py:528`：相同运行 `as_of`，不同目标日，公布前后取不同期 |
   | 修订版本公开边界 | `tests/integration/test_context_projection.py:603`：历史目标日重新选取当时可见版本 |
   | 未来统计期 | `tests/integration/test_context_projection.py:476`、`:682` |
   | 覆盖不足 | 未找到专门经补算断言库存延迟公布、`dual-cutoff-v0003`例外或收盘后公布的测试；`:682` 的“未知公开时间”名称已过时，实际只剩未来月份参数，见同文件`:679` |

3. **窗口内部缺一个核心交易日，补算仍可能给正式阶段，与门①不一致；不是任何缺口都会必然放行。** 补算的 `window_gaps` 默认为空，`_core_readiness` 不会触发 `window_session_missing`，而 `evaluate_trend` 仅检查点数、正值并按现有观测排序计算，没有交易日连续性检查，见 `src/pring_cycle/worker.py:1124`、`:1170`、`:1196`、`src/pring_cycle/domain/trend.py:62`。因此，只要剩余历史足够、最新值有效、三资产状态形成典型组合，正式阶段就能发布；历史不足、冲突或最新值落后仍可能阻断，见 `src/pring_cycle/worker.py:1168`、`src/pring_cycle/p0.py:77`。票07:15要求枚举窗口应有明细，目标日已有对应反例，但没有断言补算日也阻断：`tests/integration/test_full_run_retrieval.py:880`，尤其`:898`。

4. **当前 `_core_readiness` 只有两个调用点；你提示的1146、1183附近不是额外调用方。** 它们分别是 `CoreInputValidator` 构造及其校验分支，见 `src/pring_cycle/worker.py:1146`、`:1183`；下表列出 `src`、`tests` 全部直接调用位置，同文件后续数字均为行号，导入、定义和 monkeypatch 不算调用。

   | 函数 | 全部生产调用方及用途 |
   |---|---|
   | `_core_readiness` | `src/pring_cycle/worker.py:407` 目标日；`:587` 补算日；tests无直接调用 |
   | `build_context_projection` | `src/pring_cycle/worker.py:417`、`:595`；`src/pring_cycle/core_fixture.py:63` 验收夹具投影 |
   | `P0ProjectionService.publish` | `src/pring_cycle/worker.py:476`、`:610`；`src/pring_cycle/core_fixture.py:71` |

   | `build_context_projection` 测试调用文件 | 调用行号 |
   |---|---|
   | `tests/fixtures/public_context.py` | 51 |
   | `tests/integration/test_context_projection.py` | 115、120、182、248、308、368、417、438、451、515、575、581、663、724、755、804、842、860、886、917、943、986、1042、1097、1184、1265、1386、1482、1583、1646、1707 |
   | `tests/models/test_registered_model_inputs.py` | 485、955、1197、1215、1831、1849、2057、2095、2136、2253 |
   | `tests/integration/test_derived_context_freshness.py` | 79、162、215 |
   | `tests/integration/test_ecb_reference_acquisition.py` | 309 |
   | `tests/integration/test_gdp_semantics.py` | 166、226 |
   | `tests/integration/test_inventory_period_alignment.py` | 57、142、241 |
   | `tests/integration/test_loan_ytd_year_boundary.py` | 64、139 |
   | `tests/integration/test_official_full_run_fallback.py` | 215 |
   | `tests/integration/test_official_gdp_fallback.py` | 314 |
   | `tests/integration/test_official_metric_fallback.py` | 227 |
   | `tests/integration/test_official_money_fallback.py` | 196 |
   | `tests/integration/test_official_pmi_fallback.py` | 219 |
   | `tests/integration/test_official_social_financing_fallback.py` | 251 |
   | `tests/integration/test_omo_invalid_flow.py` | 63、165、229 |
   | `tests/integration/test_p2_source_timing.py` | 76、98 |
   | `tests/integration/test_tushare_news.py` | 322、550、709 |
   | `tests/integration/test_worker_reviewed_context.py` | 267 |

   | `P0ProjectionService.publish` 测试调用文件 | 调用行号 |
   |---|---|
   | `tests/integration/test_p0_gate.py` | 40、51、81、109、148、181、192、224、249、270 |
   | `tests/integration/test_worker_execution.py` | 621、666、725 |
   | `tests/integration/test_worker_calendar_gate.py` | 40 |
   | `tests/integration/test_source_contract_quarantine.py` | 95、137 |
   | `tests/reports/test_report_boundary.py` | 331、417、494 |
   | `tests/web/test_projection_api.py` | 169、179、275 |
   | `tests/e2e/test_v1_cli.py` | 142 |

5. **现有实现要求补算按日期升序发布，但不是因为趋势计算读取上一日投影状态。** `_last_confirmed_stage` 实际查询 `p0_assessment` 中日期≤本日的最近正式记录，发布同时读取已有阶段史；`evaluate_trend` 则每次从价格序列重新计算，所以可独立准备输入，但不能不加协调地并行发布，见 `src/pring_cycle/projections.py:185`、`src/pring_cycle/p0.py:202`、`src/pring_cycle/worker.py:1196`。上游窗口已经排序，补算循环只是保持传入顺序；目标日 `last_stage` 放在补算后符合票24重建阶段史的明确意图，但 readiness/context 必须放在补算前并无独立要求，见 `src/pring_cycle/full_run_requirements.py:47`、`:74`、`src/pring_cycle/worker.py:417`、`:437`、`:446`。某日抛出被捕获的四类异常后，后续日读取更早的成功正式阶段，有则沿用、没有则 `None`，不会因该失败自动阻断；失败日下次可重试，但后续已经发布的日不会自动重算，见 `src/pring_cycle/worker.py:548`、`:563`、`src/pring_cycle/projections.py:177`。

6. **测试不能简单分成“完整运行都慢、全部改单日”：应区分单日规则、获取编排和运行生命周期。** 下表行号指测试定义或明确标出的共享夹具，**单日**可迁移结果断言，**拆分**必须保留获取／计划／报告等其他断言，**完整**应保留运行级覆盖；未执行测试，清单不代表通过。`test_backfill.py` 三例共享两次运行，不是每例各跑119天，而 P2 与核心沿用也并非全都“只断言单日结果”，见 `tests/integration/test_backfill.py:48`、`:78`、`:82`、`tests/integration/test_core_carry_forward.py:93`。既有记录中的32.54秒、32.69–35.37秒只是整例成本，不能直接当节省量，证据为 `.scratch/architecture-review-20260929/codex-survey.md:28`、`:48`，票24:20另记当时首次初始化约13秒。

   | 测试／共享夹具清单 | 分类与需要保留的内容 |
   |---|---|
   | `tests/integration/test_backfill.py:86` 首次120日；`:106`漏跑两日 | **完整**：阶段史、漏日选择、报告仅目标日、最终指针 |
   | `tests/integration/test_backfill.py:116` 公布边界 | **单日**：可对两个日期独立调用单日模块验证 |
   | `tests/integration/test_core_carry_forward.py:89`、`:112`、`:125` | 前两例**拆分／完整**，分别含报告沿用标志、报告关联；`:125`冲突阻断为**单日** |
   | `tests/integration/test_worker_execution.py:213`、`:404`、`:437` | `:213` **拆分**核心日期过滤与adoption；后两例**完整**，含报告与运行完成 |
   | `tests/integration/test_full_run_retrieval.py:42`、`:134` | **拆分**：P2投影规则可单日，请求次数、失败分类、回执不能删 |
   | 同文件`:391`、`:482`、`:524`、`:563`、`:631`、`:689`、`:764` | **完整／编排**：检索采用关联、恢复、跨期预算、调用归属、冻结输入、联合发布请求 |
   | 同文件`:462`、`:880`、`:904`、`:976` | **拆分**：需求规划与日历断言归规划层；`:880`阶段阻断归单日 |
   | `tests/integration/test_core_official_fill.py:150`、`:174`、`:189` | **拆分**：保留TuShare→官方补缺路径，阶段结果可单日 |
   | `tests/integration/test_core_history_refresh.py:183` | **完整**：实际运行取得数据的时间边界 |
   | `tests/integration/test_structural_rejection.py:88`、`:102` | **完整／拆分**：结构拒收、回执、运行继续；输出规则可拆 |
   | `tests/integration/test_worker_registered_catalog.py:299` | **完整**：生效目录、官方PPI回退、报告交付 |
   | `tests/integration/test_worker_eia_html_fallback.py:130` | **完整／拆分**：获取回退与投影接入 |
   | `tests/integration/test_context_acquisition_receipts.py:214` | **完整／拆分**：原件、回执、系统可用时间及发布 |
   | `tests/integration/test_decertified_main_chain.py:106`夹具 → `:121`、`:135`、`:145` | 正式阶段／投影标签为**单日候选**；发布时间推定归获取层，保留主链集成 |
   | `tests/integration/test_gap_list.py:104`夹具 → `:118`、`:140`、`:157`、`:169`、`:175` | `:157`、`:169` **单日**；其他**拆分**；`:175`保留页面、报告、投影一致性 |
   | `tests/integration/test_gap_source_repairs.py:217`夹具 → `:274`、`:285`、`:301`、`:327`、`:347`、`:360`、`:372`、`:388`、`:395` | **拆分**：各来源获取／拒收／缺口规则与单日展示；共享完整运行保留 |
   | `tests/integration/test_source_gap_fixes.py:40`夹具 → `:81`、`:101`、`:112` | **拆分**：交付、时效、目录频率；不是整组单日规则 |
   | `tests/integration/test_release_preannouncement.py:118`、`:136`、`:151` | **完整／编排**：预告获取优先级及对推定时间的影响 |
   | `tests/integration/test_daily_reacquisition.py:39` | **完整**：跨次运行不重复获取 |
   | `tests/integration/test_unsearchable_gaps.py:22` | **完整／拆分**：不发搜索请求与缺口展示 |
   | `tests/integration/test_model_version_switch.py:64` | **完整**：模型切换、批次与历史不可改写 |
   | `tests/integration/test_candidate_duration.py:36` | **完整／拆分**：候选天数规则可单日，模型切换与旧快照保留完整 |
   | `tests/integration/test_processing_batch.py:41`夹具 → `:94`、`:111`、`:136`、`:148` | **完整**：批次贯穿获取、全部汇总与报告 |
   | `tests/integration/test_retention.py:77`夹具 → `:109`、`:130`、`:140`、`:162`、`:173`、`:211`、`:261` | **完整**：多次运行、成功清理、失败保留、公式回看及历史状态 |
   | `tests/integration/test_report_input.py:24` | **完整**：报告实际接收运行产出 |
   | `tests/integration/test_worker_calendar_gate.py:90` | **完整**：有独立日历时确实走到发布 |
   | `tests/integration/test_lease_heartbeat_overlap.py:130`、`:277` | **完整**：真实Worker中的租约、并发查询／写竞争及报告完成 |

   | 不应误计为“119日补算慢例” | 原因及证据 |
   |---|---|
   | `tests/integration/test_worker_execution.py:504`、`:565`、`:584`、`:754` | 上下文失败、模型／运行库／时限门禁，未走到补算 |
   | 同文件`:601`、`:645`、`:703` | 报告或已发布投影恢复路径；仍应保留运行级覆盖 |
   | `tests/integration/test_worker_calendar_gate.py:24`；`tests/integration/test_full_run_retrieval.py:235`、`:927` | 日历不可用，在补算前结束 |
   | `tests/integration/test_gap_list.py:187`；`tests/integration/test_source_contract_quarantine.py:76` | 时效未配置／来源契约门禁 |
   | `tests/integration/test_full_run_retrieval.py:849`、`:1029` | 前者取消在检索期间，后者只调用selector |
   | `tests/integration/test_media_page_values.py:63`及targeted retrieval类测试 | `targeted_refresh`在Worker早期分支返回，见 `src/pring_cycle/worker.py:325` |
   | `tests/integration/test_context_projection.py:115`等第4条所列直接调用 | 原本就在调用上下文组件，没有首次初始化开销 |

7. **补算历史日可以切换当前指针；准确规则是“日期不倒退”，不是“补算不切指针”。** `ProjectionSetRepository` 没有目标日／补算日类型字段，只比较新投影日期与当前日期：当前为空或新日期≥当前日期就切换，否则仅保存历史集，见 `src/pring_cycle/projections.py:118`、`:130`。因此首次初始化会随补算逐日前移，日常补算中晚于旧当前日的漏日也会前移；旧日期补洞不会后退，同日重跑可以替换当前指针，这符合票24:19但不能解释成“整个运行结束才切换”。每次发布的数据集、assessment和指针处于同一事务，满足ADR-0008的**单套投影原子性**，却不提供“119日补算＋目标日”的运行级原子性，见 `src/pring_cycle/projections.py:91`、`:99`、`:116`。

8. **建议单日模块负责“已取得证据＋明确日界限→完整且可追踪的一日投影”，Worker负责运行编排。** 理由是核心门禁、上下文、缺口和快照必须共享同一日期语义，检索、报告与恢复则具有不同生命周期，依据 `CONTEXT.md:71`、`:321`及 `docs/adr/0008-atomic-analytical-projection-sets.md:9`。不能直接认可调查中的“无需调整约定”：`.scratch/pring-fast-refactor-20260923/spec.md:228`明确要求唯一测试入口为手动完整运行，新增单日测试接口须同步修改这条规格，虽然不必因此推翻上述ADR。

   | 边界 | 建议 |
   |---|---|
   | 包含 | 按本日可见性读证据、枚举本日所需窗口缺口、核心就绪与趋势、宏观库存及派生、解释warning、gap_list、输入快照、阶段assessment、原子投影发布 |
   | 日历 | 接收已验证交易日历／发布日程；本日发布日历文档组装可包含，日历获取与修复留在外层 |
   | 不包含 | 网络检索、刷新来源、挑选漏跑日、报告生成、检查点、租约／取消、运行状态推进、留存清理 |
   | 显式输入／输出 | 输入日期、冻结时点、历史公开策略、模型、批次及已验证日历；输出投影／assessment／snapshot身份与发布结果，避免仅把现有长参数列表搬家 |

   | 风险 | 证据与影响 |
   |---|---|
   | 门①漏判 | `src/pring_cycle/worker.py:587`：补算没有按本日重新枚举缺口；也不能直接复用目标日缺口集合，否则会把本日之后的缺口算进去 |
   | 快照与派生血缘不完整 | `src/pring_cycle/p0.py:102`；`src/pring_cycle/context_projection.py:1374`：历史快照仅核心哈希，派生身份可能没有对应持久记录 |
   | 历史时效标签采用运行时间 | `src/pring_cycle/context_projection.py:298`、`:1764`：公开可见性按历史日限制，但部分freshness仍按运行 `as_of` 计算，历史值可能被判成运行时已过期 |
   | 补算失败后历史不自动修复 | `src/pring_cycle/worker.py:563`；`src/pring_cycle/projections.py:177`：后续成功日保存了跨过失败日的历史上下文，下次只补失败日 |
   | 降级结果也算“已汇总” | `src/pring_cycle/projections.py:177`：已有assessment即跳过，即使当时因缺核心而无正式阶段 |
   | 历史投影的阶段史可能含未来日期 | `src/pring_cycle/p0.py:202`；`src/pring_cycle/projections.py:164`：读取全部assessment，没有按待发布历史日过滤 |
   | 运行未完成也已推进当前指针 | `src/pring_cycle/projections.py:130`；`src/pring_cycle/worker.py:473`：补算先发布，目标日前才再次检查生效模型，须明确中断／切模时的可见结果 |
   | 隐式环境与直接调用脱节 | `src/pring_cycle/worker.py:218`、`:381`、`:382`：批次、交易日历和发布日程存在作用域状态，抽模块时不能遗漏 |
