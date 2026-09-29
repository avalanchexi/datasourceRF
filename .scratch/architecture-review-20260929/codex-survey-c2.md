1. **结论：可以统一“已选声明能否采用”的核对，但不能把现状当成两套等价分派直接合并。** 两侧覆盖的家族、统计期范围和成员完整性处理存在差异，且目标日包装层还承担重选声明的职责；候选 2 的方向成立，边界需要比“搬走两个分派块”更完整。以下均为静态读码结果，未改文件、未运行测试、未访问外部网络；实现文件的简写 `文件.py:行号` 均位于 `src/pring_cycle/`。

2. **家族对照：检索侧共有 8 个 `_ClaimFamily`，另有仓单、降准、核心 P0 三条专门路径；`_metric_rows` 只有其中 7 类复核。**

   | 家族／指标 | 检索侧函数与调用位置 | `_metric_rows` 投影侧函数与调用位置 | 是否相同／仅一侧 |
   |---|---|---|---|
   | ECB 交叉汇率 `CN_USDCNY_ECB_REFERENCE_CROSS` | `source_claims_matching_registered_contract`，`search_evidence.py:212` | 同名方法，`context_projection.py:1552` | 同函数，外层豁免不同 |
   | LPR `CN_LPR_1Y_5Y` | `lpr_claims_matching_acquisitions ∪ news_claims_matching_quotes`，`search_evidence.py:224`、`search_evidence.py:232` | 同一并集，`context_projection.py:1502` | 相同 |
   | 官方宏观／政策完整性集合 | `official_claims_matching_acquisitions ∪ news_claims_matching_quotes`，`search_evidence.py:239` | `_official_or_quoted_claims`，`context_projection.py:1514`；包装函数在 `context_projection.py:576` | 包装后相同 |
   | 银行间：DR007、Shibor ON／1W／3M | `interbank_claims_matching_acquisitions`，`search_evidence.py:249` | 同名函数，`context_projection.py:1526` | 相同 |
   | 美债：UST2Y、UST10Y 名义收益率 | `treasury_claims_matching_acquisitions`，`search_evidence.py:257` | 同名函数，`context_projection.py:1539` | 相同；这里不是中国国债核心 |
   | 融资余额 `CN_MARGIN_BALANCE` | `tushare_claims_matching_acquisitions`，默认 `parse_margin_acquisition`，`search_evidence.py:265` | 无对应原件复核分支 | 仅检索 |
   | 指数行情 `MARKET_INDEX_IDENTITIES` | `tushare_claims_matching_acquisitions(parse=parse_market_index_acquisition)`，`search_evidence.py:273` | 无对应原件复核分支 | 仅检索 |
   | 估值 `CN_INDEX_VALUATION` | `tushare_claims_matching_acquisitions(parse=parse_valuation_acquisition)`，`search_evidence.py:282` | 无对应原件复核分支 | 仅检索 |
   | 降准 `CN_RRR_EVENT` | `select_published_rrr_events`，`search_evidence.py:345` | 同名函数，`context_projection.py:1488` | 同函数，输入范围不同 |
   | 仓单 `CN_FUTURES_WARRANTS` | `select_warrant_inputs`，`search_evidence.py:322` | 同名函数，逐期调用，`context_projection.py:1563` | 同函数，结果处理不同 |
   | 三核心 P0 | `selected_core_claim_is_valid`＋`CoreInputValidator.is_valid`，`search_evidence.py:293`、`search_evidence.py:416` | `_metric_rows` 无此分支；核心就绪在 Worker 判断 | 在这两处比较中仅检索；并非整个投影流程不检查 |
   | 其他指标 | 通用质量、数值、维度成员判断，`search_evidence.py:375` | 通用 `_evidence_status`，`context_projection.py:1619` | 没有统一的兜底原件核对 |

3. **“官方宏观”不是所有注册官方来源的统称，而是明确列举的 12 个发布家族。** 完整清单是 `nbs_gdp`、`nbs_pmi`、`nbs_core_cpi`、`nbs_ppi`、`nbs_industrial_value_added`、`nbs_industrial_finance`、`nbs_capacity_utilization`、`pbc_money`、`pbc_social_financing`、`pbc_loan_structure`、`pbc_tool_liquidity_monthly`、`pbc_omo_notice`，证据为 `official_context.py:121`，指标映射见 `retrieval_registry.py:57`。指数行情集合则是 CSI300、CSI500、CSI1000、CNY030、930916、NHCI 六个指标，见 `tushare_context.py:45`；`CN_MARGIN_BALANCE_SSE_SZSE` 并不属于上述融资余额复核分支，不能因名称相似就算进去，见 `search_evidence.py:264`、`search_evidence.py:435`。

4. **统计期范围不同，属于有明确理由的用途差异。** 普通检索家族只核对 `adoptable(metric, period)`，事件持续生效指标取截止该期每个成员的最新事件，注释明确说明是避免重复读取无关历史原件，见 `search_evidence.py:149`、`search_evidence.py:193`。投影 `_metric_rows` 核对传入仓库返回的整个可见序列，以便判断当前值、前值和仓单历史，见 `context_projection.py:1481`、`context_projection.py:1635`；这里的“全序列”不等于数据库全部历史，因为目标日包装层还会限制目标日和可见窗口，见 `context_projection.py:609`、`context_projection.py:629`。

5. **BUILTIN 豁免大体一致；ECB 缺的是外层判断，不能直接认定为实际漏豁免。** 检索对 BUILTIN 不构造家族复核，仓单、降准及 P0 原件复核也跳过，但 P0 来源身份检查仍执行，见 `search_evidence.py:292`、`search_evidence.py:304`、`search_evidence.py:416`。投影相应分支通常同样豁免，ECB 在 `context_projection.py:1546` 无外层条件，不过底层 `require_registered_source_contract` 在 `source_contract_review.py:207` 已直接豁免 BUILTIN，而且 ECB 指标由迁移新增，见 `catalog.py:820`。因此这是结构不对称，当前证据不足以认定有可达的 BUILTIN ECB 行为缺陷，也没有证据说明作者有意让 ECB 更严格。

6. **融资余额、指数行情、估值的原件复核缺口是真实不对称，未见有意豁免的说明。** 检索明确检查这些声明的原件，投影对应分派结束后直接进入通用状态生成，见 `search_evidence.py:263`、`context_projection.py:1587`。因此，仅从 `_metric_rows` 看，原件损坏可以让检索拒用，而投影仍依据声明质量与时效显示状态；不能因为声明入库时检查过，就把消费时复核视作等价。统一时补上投影复核会改变行为，应与纯搬移区分。

7. **仓单成员完整性在检索侧已经检查，而且是按物理交付确定仓库成员，不是只数八个品种。** `select_warrant_inputs` 先按日期过滤，再逐品种选择最新可见交付、检查同排名原件冲突，并要求已匹配 `registered_receipts` 数量等于交付的 `current_member_count`，见 `warrant_inputs.py:104`、`warrant_inputs.py:151`、`warrant_inputs.py:186`。检索保留完整品种的选中声明，同时返回其他品种缺口；投影若该日存在任何 `missing_members`，会把当天所有已选声明加入不完整集合，见 `search_evidence.py:342`、`context_projection.py:1578`。这看起来是检索允许部分补齐、投影保守展示的用途差异，但失败范围确实扩大，不能把它描述成同一判断的简单复用。

8. **降准在 `select` 独立分支里，不在 `_claim_families`，且没有按普通事件 `adoptable` 的方式取输入。** 检索传入匹配 `scope.period` 的全部降准点，投影传入整个可见序列，见 `search_evidence.py:345`、`context_projection.py:1488`。两侧共享的规则是：官方公告必须保留公告全部成员，资讯声明则按各成员的命中原话采用，这是函数注释明确说明的有意区别，见 `published_events.py:20`、`published_events.py:38`、`published_events.py:94`。因此既不能遗漏降准，也不能把它机械改成“每个维度最新一点”的普通事件检查。

9. **检索“完整”与投影“可显示／可参与分析”本来就不是同一个结果。** 检索对登记维度逐成员要求恰好一条合格声明，见 `search_evidence.py:375`、`search_evidence.py:427`；投影保留来源失败的值与声明用于展示，并以状态排除其分析用途，见 `context_projection.py:1632`、`context_projection.py:1699`，这属于有意的用途分工。另一个需要保留或明确修正的现状是：`source_failed` 会覆盖先前算出的 `conflicted`，而冲突原因只在最终状态仍为 `conflicted` 时输出，见 `context_projection.py:1751`、`context_projection.py:1632`、`context_projection.py:1707`。这类状态优先级没有明显说明，不应在统一接口时无意丢失冲突信息。

10. **题列函数的其他直接生产调用点如下；主要仍集中在投影派生计算、Worker 核心就绪以及核对函数内部。**

    | 调用位置 | 调用与用途 |
    |---|---|
    | `worker.py:1146`、`worker.py:1183` | `CoreInputValidator`：逐核心核对整段输入历史，失败记为 `source_original_invalid` |
    | `context_projection.py:775` | `_official_or_quoted_claims`：核对 OMO 金额，供净投放派生 |
    | `context_projection.py:898` | `CoreInputValidator`：核对 OMO 到期推算采用的核心行情交易日依据 |
    | `context_projection.py:943`、`context_projection.py:960` | 银行间核对 DR007、官方／原话核对政策利率，供政策利差派生 |
    | `context_projection.py:1097` | `_official_or_quoted_claims`：核对贷款结构月度变化输入 |
    | `context_projection.py:1413`、`context_projection.py:1421` | `_usable_points_by_period`：核对 PMI、国债序列，最新期无效时不退回旧期 |
    | `context_projection.py:2303` | `_official_or_quoted_claims`：核对信用脉冲采用的社融、GDP 父声明 |
    | `official_context.py:410`、`official_context.py:417` | 官方宏观复核内部：TuShare 原件复核后再检查注册契约 |
    | `official_context.py:428` | 官方宏观复核内部：一季度产能利用率累计口径映射检查 |
    | `treasury_context.py:228` | 国债复核内部：对 TuShare 声明调用通用 TuShare 原件检查 |
    | `published_events.py:27` | 降准复核内部：调用命中原话检查 |

11. **full_run_requirements、freshness、gap 清单和 report 没有直接调用题列核对函数；需要区分间接消费与自行做较弱判断。**

    | 位置 | 实际用途 |
    |---|---|
    | `worker.py:990`、`worker.py:1005` | 调 `select_retrieval_input`，判断资讯补齐／本地证据是否完整 |
    | `full_retrieval.py:118`、`full_retrieval.py:412`、`full_retrieval.py:598` | 经 selector 判断本地命中、生成补缺计划、冻结最终采用与缺口 |
    | `targeted_context.py:39`、`targeted_context.py:184` | 经 selector 找缺失仓单品种、判断 TuShare 补齐结果 |
    | `ai_websearch.py:279`、`search_evidence.py:1076` | 经 selector 判断 AI／网页候选是否形成完整模型输入 |
    | `full_run_requirements.py:177` | `_reported_count` 只数维度匹配、已选、有数值且质量合格的点，不复核原件；用途是规划公式所需期数 |
    | `full_run_requirements.py:29` | 日历完整性另行读取日历证据／回执，不是题列家族核对 |
    | `freshness.py:594`、`freshness.py:600` | 时效读取有选中数值的点，不检查家族原件，也未要求 `selection_status == selected` |
    | `freshness.py:557`、`freshness.py:606` | 仓单时效只检查静态必需成员是否出现，不检查最新物理交付的仓库成员数 |
    | `freshness.py:868`、`freshness.py:978` | 缺口清单消费时效、获取失败、计划缺口及投影结果；冲突从投影行收集，见 `freshness.py:1064` |
    | `reports.py:147`、`reports.py:317` | 报告读取已发布投影并归纳缺口，不重新核对来源声明 |

12. **0.5% 冲突首先由证据仓库选值决定，家族原件核对不负责跨来源容差。** `metric_series` 调 `_select_claim_rows`，后者按来源保留最新版本、按 `certified` 优先再按 provider 排序选出声明，并对合格已认证数值调用 `value_conflict_reason`，见 `evidence.py:1048`、`evidence.py:1420`、`evidence.py:1435`。0.5% 与单位倍数错误规则在 `evidence.py:1465`；显式绝对 `tolerance` 会替换该规则，而冲突结果仍保留 `selected_claim_id`，见 `evidence.py:1452`、`evidence.py:1475`。家族核对通常要求声明与自己的原件精确相等，不能把跨来源 0.5% 容差套进原件一致性检查，例如 `official_context.py:383`、`warrant_inputs.py:224`。

13. **但“selected_claim_id 只在 evidence.py 决定”这个前提不成立。** `TargetBoundEvidenceRepository` 会经 `_point_at_target → _selected_among` 按目标日重选，降准还会经 `_official_days_whole` 改成同日整份官方公告优先，见 `context_projection.py:617`、`context_projection.py:627`、`context_projection.py:675`。`_selected_among` 也调用同一个冲突函数，但选源只按 provider 排序、参与冲突的声明也不再检查 certification，和仓库基础选择存在实质口径差异，见 `context_projection.py:730` 对比 `evidence.py:1435`；目标日及降准特殊处理有明确意图，certification 差异未见同样明确的解释。整体仍是“先选值／定冲突，再核对已选声明能否采用”两步，家族复核一般不会在失败后自动改选另一个来源；仓单则额外选择最新完整物理交付。

14. **核对读取的材料并不统一，“注册契约核对”也不等于只查一张契约表。** 共同原件入口是 `evidence.py:366` 的 `source_claim_acquisitions_many`，读取声明关联、已验证回执及 raw／normalized，并通过 `acquisition.py:377` 校验内容哈希。各入口如下：

    | 核对入口 | 实际读取与比较 |
    |---|---|
    | `official_lpr.py:204` | 关联回执、raw／normalized 哈希；`parse_lpr_acquisition` 重解析公告并核对 normalized 哈希，再匹配期限、数值、来源引用与时间，解析入口 `official_lpr.py:174` |
    | `official_context.py:345` | 官方原件重解析、normalized 哈希、指标／维度／期／值／来源时间；解析入口 `official_context.py:285`；TuShare 分支另走其解析器和注册契约 |
    | `interbank_evidence.py:146` | 全部关联 API 响应与 normalized 批次；重解析、比较成员与重复项、关联 ID、目录版本，批次入口 `interbank_evidence.py:80` |
    | `treasury_context.py:206` | 官方 CSV raw／normalized 重解析及来源身份；TuShare `us_tycr` 改走 `tushare_claims_matching_acquisitions`，见 `treasury_context.py:228` |
    | `tushare_context.py:1646` | 按传入 parser 重解析 raw，与 normalized 的经济字段、拒绝字段记录、关联 ID、版本、期／维度／值／单位／时间核对 |
    | `news_rules.py:925` | 读 `claim_matched_quote`，重新运行 `extract(..., recheck=True)` 比较维度和值；不读取原件，也不重新验证保存的正文哈希，见 `news_rules.py:942`、`news_rules.py:952` |
    | `warrant_inputs.py:95` | 回执及两个原件；按提供方重解析 CZCE／TuShare 仓单，再判交付排名、原件冲突、仓库成员完整性；解析分派 `warrant_inputs.py:35` |
    | `published_events.py:17` | 原话表，或每条声明关联的完整公告；公告读取入口 `evidence.py:422`，校验原件并重解析，再检查公告成员齐全 |
    | `evidence.py:475` | 重读 `source_claim` 与关联 ID，重建输入后执行 `_validate_claim`，再进入 `source_contract_review.py:190`；不是简单返回注册表命中 |
    | ECB 特例 `ecb_reference.py:241` | 契约分派最终读取 ECB 回执、raw／normalized，验证交叉汇率两条腿及结果，见 `ecb_reference.py:270` |
    | `source_adapters.py:98` | `CoreInputValidator` 经 `source_claim_originals_many` 读取两种已校验原件，重解析核心行情并精确匹配收盘值，见 `source_adapters.py:120`、`evidence.py:320` |

15. **注册定义的数据库依据是 `registered_metric_catalog` 联接 `model_version`，具体来源契约仍有代码分派。** 定义读取会检查定义哈希和模型清单绑定，见 `catalog_registry.py:94`；BUILTIN 定义则直接来自内置目录，见 `catalog.py:408`。所以统一接口应隐藏“读定义＋执行契约＋必要时再读原件”的组合，而不是抽象成单纯“查询注册契约表”。

16. **已有大量测试可以直接覆盖核对或 selector／projection，不需要完整 Worker；下面列出直接针对核心判断的现有用例。** 表中 `R` 表示 `tests/models/test_registered_model_inputs.py`，每个行号均为测试定义入口。

    | 判断 | 文件、行号与测试名 |
    |---|---|
    | 官方原件：两侧采用及损坏拒用 | `R:1139` — `test_registered_official_original_reaches_selection_and_context`；`R:1754` — `test_admitted_catalog_consumes_cpi_with_separate_categories_and_public_system_times` |
    | 官方合法缺列／成员完整性 | `R:1341` — `test_registered_official_legitimate_missing_columns_are_complete`；`R:1555` — `test_registered_social_financing_completes_only_after_both_original_announcements`；`R:1862` — `test_registered_cpi_requires_cumulative_only_outside_january` |
    | 最新坏期不可退回旧期 | `R:909` — `test_pmi_invalid_latest_period_does_not_restore_older_derived_values` |
    | LPR | `R:1988` — `test_admitted_catalog_consumes_lpr_through_evidence_selection_and_context` |
    | 银行间错绑 API | `R:601` — `test_registered_interbank_rejects_mixed_api_claim_links` |
    | 仓单成员／修订 | `R:234` — `test_registered_warrant_acquisition_preserves_sample_units_and_unknown_public`；`R:331` — `test_warrant_same_day_revision_preserves_public_history_and_replaces_members`；`R:2145` — `test_warrant_history_coverage_counts_only_complete_daily_warehouses` |
    | CZCE 仓单 | `tests/integration/test_czce_warrant_refresh.py:177` — `test_the_consumers_reparse_accepts_the_czce_members`；`:200` — `test_an_older_tushare_claim_for_the_same_warehouse_is_not_selected` |
    | 融资余额 | `R:2524` — `test_registered_margin_selection_requires_readable_originals`；`R:2588` — `test_registered_margin_candidate_selection_respects_publication_cutoff` |
    | 指数行情 | `R:2906` — `test_registered_market_index_selection_requires_its_originals`；`R:2978` — `test_registered_market_indices_respect_publication_cutoff` |
    | 估值 | `R:3059` — `test_registered_valuation_keeps_all_nine_static_members_and_originals`；`R:3255` — `test_registered_valuation_selection_rejects_damaged_index_originals`；`R:3327` — `test_registered_valuation_keeps_missing_members_incomplete`；`R:3397` — `test_registered_valuation_respects_publication_cutoff` |
    | ECB 投影复核 | `tests/integration/test_ecb_reference_acquisition.py:288` — `test_ecb_projection_rechecks_the_original_before_using_a_certified_cross` |
    | ECB 检索与新版本恢复 | `tests/integration/test_worker_ecb_refresh.py:90` — `test_direct_refresh_owns_ecb_original_and_selects_actual_system_without_tushare`；`:213` — `test_fresh_valid_original_recovers_damaged_prior_proof_with_a_new_vintage` |
    | 对齐后的派生输入原件 | `tests/integration/test_inventory_period_alignment.py:164` — `test_registered_common_month_inventory_rechecks_the_aligned_ppi_original` |
    | 核心 SYSTEM／PUBLIC 选择 | `tests/integration/test_full_run_retrieval.py:1029` — `test_full_run_core_selection_preserves_explicit_as_of_mode`；注意此例用 BUILTIN，不能证明注册核心原件复核覆盖 |

17. **官方宏观还有直接调用 `official_claims_matching_acquisitions` 的测试，尤其值得保留那些“哈希合法但语义被改坏”的用例。**

    | 文件 | 直接相关测试名与入口 |
    |---|---|
    | `tests/integration/test_official_metric_fallback.py` | `:69 test_cpi_acquisition_falls_back_only_for_missing_metrics`；`:243 test_cpi_delivery_requires_independent_raw_and_publication_evidence` |
    | `tests/integration/test_official_pmi_fallback.py` | `:77 test_pmi_official_fallback_preserves_other_delivered_metrics`；`:244 test_pmi_revalidation_checks_full_response_and_independent_publication` |
    | `tests/integration/test_official_money_fallback.py` | `:63 test_money_fallback_keeps_required_members_and_delivery_provenance`；`:214 test_money_delivery_rejects_unreviewed_fields_and_unproven_evidence` |
    | `tests/integration/test_official_social_financing_fallback.py` | `:61 test_sf_total_delivery_preserves_annual_flow_period_and_month_end_stock`；`:115 test_sf_total_fallback_preserves_delivered_values_and_component_scope`；`:269 test_sf_total_rejects_legacy_semantics_and_unproven_evidence` |
    | `tests/integration/test_official_gdp_fallback.py` | `:81 test_gdp_delivery_keeps_cumulative_levels_and_audits_disputed_growth`；`:129 test_gdp_batch_links_each_quarter_and_rejection_to_its_physical_response`；`:180 test_gdp_fallback_respects_delivered_period_without_loosening_required_members`；`:412 test_gdp_listing_accepts_each_archived_quarter_title`；`:518 test_gdp_adoption_rechecks_rejected_fields_even_with_valid_artifact_hashes`；`:583 test_gdp_rejects_changed_originals_or_unproven_values_and_publication` |
    | `tests/integration/test_official_full_run_fallback.py` | `:51 test_full_acquisition_discovers_missing_ppi_from_registered_official_listing`，直接走 `FullRunRetrieval`，不是完整 Worker |

18. **资讯与降准也并非只能穿过 Worker 测，但目前主要通过检索组件间接验证，未发现直接调用两个复核函数的独立测试。** `test_tushare_news.py` 的 `full_run` 实际调用 `FullRunRetrieval.retrieve`，见 `tests/integration/test_tushare_news.py:117`；不要被 helper 名称误导。相关测试包括：

    | 文件与入口 | 测试名／覆盖 |
    |---|---|
    | `tests/integration/test_tushare_news.py:138` | `test_cpi_is_filled_from_the_news_and_later_channels_are_not_called` |
    | `tests/integration/test_tushare_news.py:295` | `test_lpr_is_filled_from_the_fixing_day_news`，另直接构建投影 |
    | `tests/integration/test_tushare_news.py:529`、`:657` | `test_an_omo_rate_not_held_is_read_from_the_day_s_operation`；`test_a_held_omo_rate_stays_in_force_through_days_without_a_stated_rate` |
    | `tests/integration/test_tushare_news.py:723` | `test_an_rrr_cut_in_the_news_becomes_the_baseline_the_analysis_reads` |
    | `tests/integration/test_rrr_backtrack.py:398` | `test_on_a_day_the_official_notice_states_its_members_are_all_read_from_it`，覆盖官方与资讯的整份公告取舍 |
    | `tests/adapters/test_rrr_context.py:121` | `test_rrr_incomplete_scope_import_keeps_raw_without_partial_claims`；这是入库解析测试，不是入库后 `select_published_rrr_events` 完整性复核 |
    | `tests/integration/test_tushare_news.py:230` | `test_originals_go_after_three_days_and_the_quotes_stay`；断言留存与仓库值，不等于原件删除后重新执行原话复核 |

19. **目前确实穿过完整 Worker 的相关测试，是这些具体用例；不能据此说领域判断本身只能这样测。**

    | 文件与入口 | 测试名／完整 Worker 覆盖 |
    |---|---|
    | `tests/integration/test_gap_source_repairs.py:274` | `test_treasury_yields_are_held_from_tushare_us_tycr`；共享 fixture 在 `:247` 执行 Worker |
    | `tests/integration/test_worker_registered_catalog.py:299` | `test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report`；含检索采用、投影、报告贯通 |
    | `tests/integration/test_media_page_values.py:91` | `test_cpi_gap_is_filled_from_a_media_page_and_keeps_its_matched_quotes`；helper 在 `:74` 执行 Worker |
    | `tests/integration/test_ai_websearch.py:133` | `test_codex_candidates_fill_the_p1_gap_with_their_quotes`；helper 在 `:112` 执行 Worker |
    | `tests/integration/test_core_official_fill.py:150` | `test_a_csi_core_tushare_misses_is_filled_from_the_official_page`；helper 在 `:144` 执行 Worker |
    | `tests/integration/test_worker_execution.py:213` | `test_core_readiness_ignores_observations_after_historical_target`；但采用 BUILTIN，不能算注册 P0 原件损坏测试 |

20. **冲突规则已有直接测试，但统一接口仍有明确的覆盖空白。** `tests/evidence/test_point_in_time.py:716` 的 `test_reported_values_agree_within_half_a_percent_and_flag_unit_slips`、`:723` 的 `test_explicit_tolerance_replaces_the_relative_tiers`、`:735` 的 `test_query_compares_certified_values_by_relative_tiers`，以及 `tests/integration/test_context_projection.py:1060` 的 `test_certified_sources_within_half_a_percent_agree` 覆盖容差链。静态检索未发现直接实例化 `CoreInputValidator`、直接调用 `news_claims_matching_quotes`／`select_published_rrr_events`／`treasury_claims_matching_acquisitions` 的独立测试，也未发现专门锁定 adoptable 范围、ECB 外层豁免、投影缺少三类原件复核及冲突被 `source_failed` 覆盖的测试。这里应标记“缺少直接回归覆盖”，而不是笼统标记“只能通过 Worker”。

21. **统一接口形状建议：** 输入是冻结目录版本、明确的时间／目标日边界，以及按指标和统计期分组的已选序列，允许一次批量核对多期。输出同时保留选值结果与冲突原因，并返回逐声明的可采用状态、原因码、证据依据，以及逐期／公告／交付的缺失成员和完整性。仓库内部统一家族分派、原件／原话／契约读取，检索和投影继续决定各自要检查哪些期、如何展示或汇总失败。接口必须保留目标日重选、降准整份公告和仓单交付完整性，同时不把时效记录重新变成来源拒收门禁。
