# 注册来源、频率与发布滞后盘点（票 02）

> 研究日期：2026-09-23。只读：未改 `src/`、`tests/`、`docs/`，未跑 pytest，未读取任何密钥。
> 代码大范围通读由 `codex exec -s read-only` 完成（原始输出留在会话 scratchpad，未入库），下面引用的 file:line 都已抽查核对。
> 文件路径相对 `src/pring_cycle/`，另有说明的除外。

## 结论先行

1. **当前生效目录共 59 项：P0 6、P1 41、P2 12。P1 是 41，不是 42。** 目录没有单独的资产文件，由代码组装：内置 `metric-catalog-v0002`（`catalog.py:11`，`_P0/_P1/_P2` 在 `catalog.py:38/46/90`，共 61 项），再应用迁移 `cny030-optional-ecb-margin-v0001`（`candidate_admission.py:52-60`，组装在 `:68-84`）。迁移内容：删除 COMEX、LBMA 两项黄金；`CN_USDCNH_FXCM` 改为 `CN_USDCNY_ECB_REFERENCE_CROSS`；`CN_MARGIN_BALANCE` 改为 `CN_MARGIN_BALANCE_SSE_SZSE`；CNY030 从 P1 降为 P2。数量有测试断言：`tests/models/test_cny030_optional_migration.py:110-112`（59 / 41 / 12）。旧记录里的“P1 仍 42”是 CNY030 降级之前的数（见 `.scratch/pring-data-acquisition-repair/continuation-status.md:18`）。运行数据库里实际登记的目录版本名本次没有读取，状态为**未证实**。
2. **来源分布（59 项）：**
   - TuShare 交付（含基于 TuShare 原料的广度和篮子）31 项：核心 3 项、交易日历、指数 6 项（其中 CNY030 属 P2）、广度 5 项、估值、DR007、Shibor、期货篮子 2 项、仓单、PMI 3 项、CPI、PPI、M1/M2、社融总量、GDP、美债 2 项。
   - 官方直连适配器 17 项：LPR、OMO 2 项、降准、工具流动性、核心 CPI、工业增加值、工业财务 3 项、产能利用率、社融分项、贷款结构、人民币中间价、ECB 交叉汇率、EIA 2 项。
   - 本地派生 5 项：DR007−OMO 利差、订单−库存差、生产−订单差、信用脉冲、美债 2s10s。
   - 运维证据 2 项：`CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY`。
   - **没有注册取数路径的 4 项**：`CN_USDCNY_CLOSE_1630`、`CBOE_VIX_INDEX`、`NASDAQ_SOX_INDEX`、`CN_MARGIN_BALANCE_SSE_SZSE`。第 4 项的 TuShare `margin` 接口本身能取沪深两所数据，只是新 ID 还没接线。
3. **代码里没有逐来源的“发布滞后 / 宽限”注册表。** 现有的只有四样东西：
   - 目录上的 `frequency` / `release_rule` / `release_event_family` / `release_timezone`。除 LPR、交易日历和三核心外，`release_rule` 一律是 `source_schedule_required`（`catalog.py:671-678`）。
   - LPR 的一个具体发布窗口（`release_calendar.py:137-162`：每月 20 日 09:00，窗口 5 分钟，宽限 3 小时）。
   - 通用最大陈旧期 `evidence_max_age_days`（`metric_contracts.py:43-49`，按自然日：日频 10、月频 95、季频 190、事件 370、降准 730）。
   - 核心资产的一条硬约束：最新值必须是目标交易日（`worker.py:943`）。
   按票 04 的“频率＋滞后＋宽限登记”要求，需要新建一张登记表。最自然的挂点是 `MetricDefinition`，或者一张与 `OFFICIAL_CONTEXT_FAMILIES` 平行的表。
4. **TuShare 官方文档只给出了部分接口的更新时点**：
   - `daily` 交易日 15:00–16:00 入库；`index_daily` 15:00–17:00 更新。
   - `margin` 次日约 09:05 更新完，深交所、北交所的周五数据要到周一上午。
   - `shibor` 11:00 计算发布，权限表写每日 12 点。
   - `index_dailybasic`、`fut_daily`、`fut_wsr` 只写“每日盘后”（权限表）。
   - `repo_daily`、`fut_index_daily`、`cn_m`、`sf_month`、`cn_pmi`、`cn_cpi`、`cn_ppi`、`cn_gdp`、`us_tycr`、`fut_mapping` 的文档页**没有写更新时点**。这些宏观接口的时效只能按官方发布日程推定，再加一个 TuShare 入库宽限；这个宽限的大小**未证实**。
5. **两个需要票 04/05 注意的风险：**
   - `index_dailybasic` 的文档写明“目前只提供上证综指，深证成指，上证50，中证500，中小板指，创业板指”，而代码要求的是 000300、000905、000852 三个指数（`tushare_context.py:59`、`metric_contracts.py:80-85`）。其中沪深 300 和中证 1000 **不在文档声明的覆盖范围内**。
   - `shibor_lpr` 的文档还写着旧制度“每个交易日……11:30 对外发布”。现行制度是每月 20 日 09:00（中国货币网）。代码已改用 chinamoney 官方直连，不走 TuShare。

## 主表（59 项）

频率取自目录（`catalog.py:540` 的 `_frequency`）。“滞后”对日频指标指更新时点；对月、季频指标指发布日距统计期末的天数，按 2026 年日程计算。

| 指标 ID | 优先级 | 当前来源 | 频率 | 统计期粒度 | 上游发布滞后 / 日频更新时点 | 依据 |
|---|---|---|---|---|---|---|
| CN_TRADE_CALENDAR | P0 | TuShare `trade_cal`(SSE) | daily | 日 | 文档写“定期更新”，无具体时点 | 取数 `source_adapters.py:164`；[trade_cal](https://tushare.pro/document/2?doc_id=26) |
| CN_RELEASE_SCHEDULE | P0 | 运维证据，无标量取数（Worker 只组装 LPR 日历） | event | 事件 | 不适用；TuShare `cn_schedule` 只给计划日期，不给时刻，代码未接 | `full_retrieval.py:212`、`worker.py:870`；[cn_schedule](https://tushare.pro/document/2?doc_id=461) |
| SOURCE_OBSERVED_AVAILABILITY | P0 | 运维证据 | daily | 采集记录 | 不适用 | `full_retrieval.py:212` |
| CN_EQUITY_CORE_000985 | P0 | TuShare `index_daily` 000985.CSI | daily | 日 | T 日 15:00–17:00 | `source_adapters.py:18,176`；[权限表](https://tushare.pro/document/1?doc_id=108)“交易日15点～17点更新” |
| CN_BOND_CORE_000012 | P0 | TuShare `index_daily` 000012.SH | daily | 日 | T 日 15:00–17:00 | `source_adapters.py:20,176`；同上 |
| CN_COMMODITY_CORE_NHII | P0 | TuShare `fut_index_daily` NHII.NH | daily | 日 | 文档页没有写时点；旧审计引用权限表“每日盘后”，本次在权限表中未找到南华条目，**未证实** | `source_adapters.py:21,176`；[fut_index_daily](https://tushare.pro/document/2?doc_id=468) |
| CN_EQ_CSI300 | P1 | TuShare `index_daily` 000300.SH | daily | 日 | T 日 15:00–17:00 | `tushare_context.py:52,824`；权限表 |
| CN_EQ_CSI500 | P1 | TuShare `index_daily` 000905.SH | daily | 日 | T 日 15:00–17:00 | `tushare_context.py:53` |
| CN_EQ_CSI1000 | P1 | TuShare `index_daily` 000852.SH | daily | 日 | T 日 15:00–17:00 | `tushare_context.py:54` |
| CN_EQ_ADV_DEC | P1 | TuShare `daily`+`suspend_d`+`stock_basic`+`trade_cal` 派生 | daily | 日 | `daily` 在 T 日 15:00–16:00 入库；`suspend_d` 文档写“不定期” | `tushare_context.py:1004,1188,1222`；[daily](https://tushare.pro/document/2?doc_id=27)、[suspend_d](https://tushare.pro/document/2?doc_id=214) |
| CN_EQ_AD_RATIO | P1 | 同上派生 | daily | 日 | 同上 | `market_breadth.py:288` |
| CN_EQ_NEW_HIGH_LOW_120 | P1 | 同上派生（回看 120 日） | daily | 日 | 同上 | `tushare_context.py:1205`、`market_breadth.py:897` |
| CN_EQ_ABOVE_MA120 | P1 | 同上派生（回看 120 日） | daily | 日 | 同上 | `market_breadth.py:900` |
| CN_EQ_ADV_AMOUNT_SHARE | P1 | `daily` 成交额派生 | daily | 日 | 同上 | `tushare_context.py:1155`、`market_amount.py:26` |
| CN_MARGIN_BALANCE_SSE_SZSE | P1 | **新 ID 未接线**。接口本身可用：TuShare `margin`(SSE、SZSE)；旧 `margin` 路径仍产出旧 ID | daily | 日 | T+1 日约 09:05（“交易所于每天8点30左右更新上一日数据，本接口最晚9点05分会更新完”）；深交所、北交所的周五数据到周一上午 | `tushare_context.py:885`（旧 ID）、`targeted_context.py:77`、`evidence.py:38-47`；[margin](https://tushare.pro/document/2?doc_id=58) |
| CN_INDEX_VALUATION | P1 | TuShare `index_dailybasic`(000300/000905/000852) | daily | 日 | 权限表写“每日盘后更新”；**文档声明的覆盖不含 000300、000852** | `tushare_context.py:59,959`；[index_dailybasic](https://tushare.pro/document/2?doc_id=128) |
| CN_BOND_10Y_930916 | P1 | TuShare `index_daily` 930916.CSI | daily | 日 | T 日 15:00–17:00 | `tushare_context.py:56` |
| CN_DR007 | P1 | TuShare `repo_daily` DR007.IB，字段 `weight` | daily | 日 | TuShare 文档没有写时点，CFETS 的发布时点本次也未取证，**未证实** | `tushare_context.py:812,2438`；[repo_daily](https://tushare.pro/document/2?doc_id=256) |
| CN_OMO_7D_RATE | P1 | 官方直连：PBoC 公开市场业务交易公告 → `_parse_omo_notice` | daily，证据语义按事件、有效至下次变更 | 日记录 | 当日约 08:45–09:10。依据是 2026-09-18 至 09-23 各公告 URL 内嵌的时间戳（08:45:26–09:07:05） | `official_context.py:1563`、`metric_contracts.py:13`；[PBoC OMO 列表](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html) |
| CN_OMO_7D_AMOUNT | P1 | 同上 | daily | 日 | 同上 | 同上 |
| CN_DR007_POLICY_SPREAD | P1 | 派生：DR007 − OMO | daily | 日 | 取两个输入中较晚的一个 | `context_projection.py:917,1284` |
| CN_SHIBOR_ON_1W_3M | P1 | TuShare `shibor` | daily | 日 | T 日 11:00 计算发布，TuShare 权限表写“每日12点” | `tushare_context.py:817`；[shibor](https://tushare.pro/document/2?doc_id=149)、权限表 |
| CN_LPR_1Y_5Y | P1 | 官方直连：chinamoney `rdgz` 正文 → `refresh_lpr_release` | monthly | 月 | 每月 20 日（遇节假日顺延）09:00，滞后为当月、0 天；代码窗口 09:00–09:05，宽限到 12:00 | `official_lpr.py:379`、`release_calendar.py:137-162`；[中国货币网 LPR](https://www.chinamoney.com.cn/chinese/bklpr/?tab=2) |
| CN_RRR_EVENT | P1 | 官方直连：PBoC 降准公告 → `_parse_rrr_notice` | event | 事件 | 不定期，无日程 | `official_context.py:1680`、`metric_contracts.py:45` |
| CN_TOOL_LIQUIDITY_MONTHLY | P1 | 官方直连：PBoC 工具流动性 → `_parse_tool_liquidity` | monthly | 月 | 次月第 2–7 日左右，约 16:50–18:00。依据是既有研究记录的 2026 年 1–8 月 URL 时间戳（如 `5727710/2026010517563068096` … `2026080416515912098`）。无公开日程，本次访问列表页返回 403，**未独立复核** | `official_context.py:1775`；`.scratch/pring-data-acquisition-repair/p1-tool-liquidity-full-value-audit.md` |
| CN_COMMODITY_BROAD_NHCI | P1 | TuShare `fut_index_daily` NHCI.NH | daily | 日 | 同 NHII，**未证实** | `tushare_context.py:57` |
| CN_COMMODITY_EX_HOG_BASKET | P1 | TuShare `fut_daily`（另有 `fut_basic`+`fut_trade_cal`+`fut_daily` 结算价路径） | daily | 日 | 权限表写“每日盘后更新”；`fut_daily` 文档页未写时点 | `tushare_context.py:65,1341`、`futures_inputs.py:519`；[fut_daily](https://tushare.pro/document/2?doc_id=138) |
| CN_COMMODITY_SLEEVE_CONTRIBUTION | P1 | 同上派生 | daily | 日 | 同上 | `commodity_basket.py:33,433` |
| CN_FUTURES_WARRANTS | P1 | TuShare `fut_wsr`（8 个品种，TA 映射为 PTA） | daily | 日 | 权限表写“每日盘后更新” | `tushare_context.py:660,713`；[fut_wsr](https://tushare.pro/document/2?doc_id=140) |
| CN_PMI_ACTIVITY | P1 | TuShare `cn_pmi`（另有 NBS 直连解析器 `_parse_pmi`） | monthly | 月 | 统计期当月最后一天 09:30，滞后 0 天；2026 年 2 月一期例外，日程标 3 月 4 日（注 5） | `tushare_context.py:546`、`official_context.py:906`；[NBS 2026 日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html)；`cn_pmi` 文档未写时点 |
| CN_PMI_INVENTORY | P1 | 同上 | monthly | 月 | 同上 | 同上 |
| CN_PMI_PRICES | P1 | 同上 | monthly | 月 | 同上 | 同上 |
| CN_ORDER_INVENTORY_SPREAD | P1 | 派生：PMI 新订单 − 产成品库存 | 目录写 **daily**，实际是月 | 月 | 同 PMI | `context_projection.py:993`；目录频率不一致见 `catalog.py:540` |
| CN_PRODUCTION_ORDER_SPREAD | P1 | 派生：PMI 生产 − 新订单 | 目录写 **daily**，实际是月 | 月 | 同 PMI | `context_projection.py:1012` |
| CN_CPI_HEADLINE | P1 | TuShare `cn_cpi`（`nt_yoy/nt_mom/nt_accu`） | monthly | 月 | 次月 9–14 日 09:30，约 9–14 天（2026 年：1/9、2/11、3/9、4/10、5/11、6/10、7/9、8/9、9/9、10/14、11/9、12/9） | `tushare_context.py:558`；NBS 2026 日程；`cn_cpi` 文档未写时点 |
| CN_CORE_CPI | P1 | 官方直连：NBS → `_parse_core_cpi` | monthly | 月 | 与 CPI 同日 09:30 | `official_context.py:848`；NBS 日程 |
| CN_PPI | P1 | TuShare `cn_ppi` | monthly | 月 | 与 CPI 同日 09:30 | `tushare_context.py:583`；NBS 日程 |
| CN_INDUSTRIAL_VA | P1 | 官方直连：NBS → `_parse_industrial_value_added` | monthly | 月（1–2 月合并） | 次月 15–19 日 10:00，约 15–19 天；1–2 月合并数据于 3/16 发布 | `official_context.py:1072`；NBS 日程“规模以上工业生产月度报告” |
| CN_INDUSTRIAL_FINANCE | P1 | 官方直连：NBS → `_parse_industrial_finance` | monthly | 月（年初累计） | 次月 27 日 09:30，约 27 天（9 月为 28 日）；1–2 月合并数据于 3/27 发布 | `official_context.py:1190`；NBS 日程“工业经济效益月度报告” |
| CN_FINISHED_GOODS_INVENTORY | P1 | 同上 | monthly | 月 | 同上 | 同上 |
| CN_INVENTORY_TURNOVER | P1 | 同上 | monthly | 月 | 同上 | 同上 |
| CN_CAPACITY_UTILIZATION | P1 | 官方直连：NBS → `_parse_capacity_utilization` | quarterly | 季 | 季后 15–19 天 10:00（1/19、4/16、7/15、10/19） | `official_context.py:1473`；NBS 日程“工业产能利用率季度报告” |
| CN_M1_M2 | P1 | TuShare `cn_m`（另有 PBoC 直连 `_parse_money`） | monthly | 月 | PBoC 金融统计通常在次月约 10–15 日发布，无公开固定日程。实例：6 月数据 2026-07-15 15:00:09 发布；11 月数据 2025-12-12 发布。固定日程**未证实** | `tushare_context.py:593`；[2026 上半年金融统计数据报告](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026071512340454869/index.html)；`cn_m` 文档未写时点 |
| CN_SF_TOTAL | P1 | TuShare `sf_month`（另有 PBoC 直连） | monthly | 月 | 同 M1/M2 | `tushare_context.py:614`；同上 |
| CN_SF_COMPONENTS | P1 | 官方直连：PBoC → `_parse_social_financing` | monthly | 月 | 同 M1/M2 | `official_context.py:1845` |
| CN_LOAN_STRUCTURE | P1 | 官方直连：PBoC → `_parse_loan_structure` | monthly | 月（年初累计） | 同 M1/M2；**未证实**是否与金融统计数据同日 | `official_context.py:2024` |
| CN_CREDIT_IMPULSE | P1 | 派生：社融总量 + GDP | monthly | 月（含季频 GDP） | 取社融与 GDP 中较晚的一个 | `context_projection.py:2115,2327` |
| CN_BOND_FULL_PRICE_CNY030 | **P2** | TuShare `index_daily` 000012CNY030.CSI | daily | 日 | T 日 15:00–17:00 | `tushare_context.py:55`；`candidate_admission.py:59,79-84` |
| CN_GDP | P2 | TuShare `cn_gdp`（另有 NBS 直连 `_parse_gdp`） | quarterly | 季（年初累计） | 季后 15–19 天 10:00，与季度国民经济运行情况同日 | `tushare_context.py:742`；NBS 日程；`cn_gdp` 文档未写时点 |
| CN_USDCNY_CENTRAL_PARITY | P2 | 官方直连：PBoC 中间价公告 | daily | 日 | T 日约 09:15。依据：CFETS 受权公布；PBoC 公告 URL 时间戳如 `2026051509130025397` | `official_context.py:2183`；[PBoC 中间价公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026051509130025397/index.html) |
| CN_USDCNY_ECB_REFERENCE_CROSS | P2 | 官方直连：ECB `eurofxref-hist.zip`（CNY/USD 交叉） | daily | 日 | TARGET 工作日约 16:00 CET，即北京时间 22:00–23:00 | `ecb_reference.py:36,190`；[ECB 参考汇率](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) |
| CN_USDCNY_CLOSE_1630 | P2 | **仅搜索**（无注册来源） | daily | 日 | 按指标名是 T 日 16:30 收盘价；官方时点本次未查证 | `catalog.py:94`；B 节 |
| EIA_BRENT_RBRTE | P2 | 官方直连：EIA API v2 `petroleum/pri/spt`（另有 HTML 历史页） | daily | 日 | **每周发布一次**（Release 9/16/2026，Next 9/23/2026），日值最多滞后约 1–2 周 | `eia_context.py:99`、`eia_html.py:247`；[EIA 现货价](https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm) |
| EIA_WTI_RWTC | P2 | 同上（RWTC） | daily | 日 | 同上 | 同上 |
| UST10Y_NOMINAL_YIELD | P2 | TuShare `us_tycr.y10`（Worker 默认；另有 Treasury CSV 直连） | daily | 日 | Treasury 通常在交易日 18:00 ET 前发布，即北京时间次日 06:00–07:00；TuShare 入库时点**未证实** | `tushare_context.py:766`、`worker.py:1622`、`treasury_context.py:75`；[Treasury 方法说明](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)、[us_tycr](https://tushare.pro/document/2?doc_id=219) |
| UST2Y_NOMINAL_YIELD | P2 | TuShare `us_tycr.y2` | daily | 日 | 同上 | 同上 |
| UST_2S10S_SPREAD | P2 | 派生：10Y − 2Y | daily | 日 | 同上 | `context_projection.py:949` |
| CBOE_VIX_INDEX | P2 | **仅搜索** | daily | 日 | 未查证 | `catalog.py:102` |
| NASDAQ_SOX_INDEX | P2 | **仅搜索** | daily | 日 | 未查证 | `catalog.py:103` |

补充说明：
- **同时有 TuShare 和官方直连的 7 项**（PMI 3 项、CPI、PPI、M1/M2、社融总量、GDP）：v0002 目录有意不把这些指标挂到官方 family（`catalog.py:192-203`），交付身份登记在 `source_families.py:14-23` 的 `TUSHARE_OFFICIAL_DELIVERY_CODES`。这与 ADR-0013 一致：TuShare 负责交付，官方页面用于抽样复核。
- NBS 日程页写明年度日程是“初步计划，届时可能调整”，所以推定的公开时点应当允许按实际发布日更正。

## 代码中可复用的频率、发布窗口和宽限登记

| 位置 | 内容 | 可复用程度 |
|---|---|---|
| `catalog.py:20-35` `MetricDefinition` | 字段有 `frequency`、`release_event_family`、`release_rule`、`release_timezone`，**没有滞后或宽限字段** | 可以在这里加滞后和宽限字段 |
| `catalog.py:540` `_frequency` | 目录频率规则。两项 PMI 派生差值被错误地落到 daily | 直接复用，需修正这两项 |
| `catalog.py:661` / `:671-678` / `:681` | family、`release_rule`（仅 LPR、交易日历、三核心有具体规则，其余是 `source_schedule_required`）、时区 | 可以沿用规则名空间 |
| `candidate_admission.py:52-60,116-141` | 迁移覆盖了新 ID、优先级、ECB 时区和 family | 目录来源 |
| `source_families.py:70-137` `OFFICIAL_CONTEXT_FAMILIES` | 只有 provider、host、metric_ids，没有时点 | 适合平行建一张“发布日程表” |
| `source_families.py:14-23` | TuShare 官方抽样交付的身份 | 可复用 |
| `release_calendar.py:12-20` `ReleaseExpectation` | `window_start/window_end/grace_until/timezone/rule_version` | **正好是需要的结构** |
| `release_calendar.py:63-135` `assess_release_state` | 根据窗口和宽限判定 current、awaiting_release、stale | 可直接泛化 |
| `release_calendar.py:137-162` `lpr_release_expectation` | 唯一实现的窗口：20 日顺延，09:00 起 5 分钟，宽限 3 小时 | 模板 |
| `release_calendar.py:166` `lpr_release_calendar` | 只组装 LPR 日历 | 需要泛化 |
| `metric_contracts.py:13,37-49` | `EFFECTIVE_UNTIL_CHANGED_METRICS`（把 OMO 利率按事件处理）；`evidence_max_age_days`（自然日：日 10 / 月 95 / 季 190 / 事件 370 / 降准 730） | 当前唯一的时效阈值。它是陈旧上限，不是发布滞后 |
| `metric_contracts.py:16` `china_business_day_end` | 目标日末时点（Asia/Shanghai） | 可复用 |
| `context_projection.py:137` `ContextProjectionRules` | 只有版本、定义、公式三项，没有时效配置 | — |
| `context_projection.py:389` `terminal_period_metrics`；`:1709-1738` `_evidence_status` / `_period_freshness` | 派生项按父指标末期判断陈旧；只有 LPR 走发布日历，其余走通用陈旧上限 | 时效判定的挂点 |
| `evidence.py:50` `publication_times` | 有 datetime 就按 datetime；只有日期时取来源时区的次日零点；缺失则为空 | 推定公开时点的现成规则 |
| `worker.py:635`、`:943`、`:1266` | LPR 预期窗口；核心必须是目标交易日；目标时效复用陈旧上限 | 门禁挂点 |
| `full_retrieval.py:331` `_period` | 按频率决定目标统计期（日频取目标日；月、季频取最新已有期或上一期） | 可复用 |
| `eia_html.py:247,421` | 解析 EIA 页面的 Release Date 和 Next Release Date | 可复用于 EIA 的周频滞后 |
| `run_cutoffs.py:29,44` | 运行截止合同，不是来源滞后 | 不相关 |

## 目前只能靠 Tavily、Exa 或 AI WebSearch 的指标

- `CN_USDCNY_CLOSE_1630`、`CBOE_VIX_INDEX`、`NASDAQ_SOX_INDEX`（均为 P2）：只有目录声明（`catalog.py:94,102,103`），TuShare 路由表（`targeted_context.py:74-90`）和官方 family（`source_families.py:78`）里都没有。更要紧的是，搜索也兜不住：
  - 候选验证器只有 LPR 和官方 family 两条解析路径（`search_evidence.py:567-585`），这三项搜到页面也无法解析入库。
  - 取数链路 `retrieval.py:95-96` 只在 priority 不是 P2 时才追加 `ai_websearch`。Worker 实际只登记了 Tavily 和 Exa（`worker.py:747-760`）。
  - 结论：这 3 项目前**实际上取不到**。
- `CN_MARGIN_BALANCE_SSE_SZSE`（P1）：代码里不属于“仅搜索”，但新 ID 没有交付路径。旧 `margin` 只产出 `CN_MARGIN_BALANCE`（`tushare_context.py:885`）；`evidence.py:38-47` 禁止把旧声明改标成新 ID；`search_evidence.py:457-462` 跳过了它的材料检查。在新门禁下它会一直是 P1 缺口，除非为它接上 TuShare `margin`(SSE+SZSE) 的交付合同。
- 派生 5 项和运维证据 2 项不属于“仅搜索”（`full_run_requirements.py:115`、`full_retrieval.py:212`）。

## 未证实或需后续确认

- 运行数据库中实际登记的目录版本名与 manifest（本次没有读 SQLite）。
- TuShare 宏观接口（`cn_m`、`sf_month`、`cn_pmi`、`cn_cpi`、`cn_ppi`、`cn_gdp`）在官方发布后多久入库：文档没写，需要实测或保守设宽限。
- `repo_daily`（DR007）、`fut_index_daily`（南华）、`us_tycr` 的入库时点。
- PBoC 金融统计和工具流动性没有公开固定日程，现有滞后只是实例归纳。
- `index_dailybasic` 对 000300、000852 是否实际有返回：文档说不覆盖，需要以账号实测或既有材料为准。
- VIX、SOX、16:30 收盘价的官方发布时点：没有注册来源，本次未查。
