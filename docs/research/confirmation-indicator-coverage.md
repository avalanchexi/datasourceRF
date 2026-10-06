**现有 61 项可以作为这套设计的指标基础，但最近运行的数据还不足以完整支撑它。主要缺口是现有成员的历史期数、事件覆盖和加工规则，不是缺一批新的宏观指标。**

有三个容易误判的地方：

- **社融已有官方 `stock_yoy`，本次投影采用了 2026-08 的 7.2%；但只有一期。**
- **贷款当月增量、OMO 净投放均已有派生实现；前者本次缺上月输入，后者已经算出。**
- **`batch_freshness=current` 不等于动量、斜率和持续期数可计算。** CPI、PPI、工业增加值等最新期是现行的，但库内各只有一期。

全程仅阅读文件和查询 SQLite，没有联网、修改文件、运行项目程序或测试。数据库使用 `python3 sqlite3.connect(..., uri=True)`，URI 为 `file:…?mode=ro&immutable=1`；普通 `mode=ro` 打开失败，确认没有 WAL/SHM 后附加 `immutable=1`。查询临时排序仅使用内存。

**核对口径与 SQL 出处**

指定运行确认为 `completed`，目标日 `2026-09-30`、模型 `model-v0014`、投影 `projection-99c6c8454595864f19b6`。模型目录共 **61 项**。

下表的 **Q1、Q2** 分别指以下查询；各单元格直接列出对应结果。历史按**不同统计期**计数，不把重复抓取、旧目录副本或同一期重跑算成多期。

```sql
-- Q0：运行与目录
SELECT target_business_date, model_version_id, status, projection_set_id
FROM parent_run
WHERE run_id = 'run-cfb8d12142289f56af73';

SELECT json_array_length(manifest_json, '$.metric_definitions')
FROM model_version WHERE model_version_id = 'model-v0014';
-- 结果：2026-09-30 | model-v0014 | completed | 指定投影；61

-- Q1：本次运行时效；下表“持有”就是 held_period，不是数据年龄
SELECT metric_id, status, held_period, source
FROM batch_freshness
WHERE batch_id = 'run-cfb8d12142289f56af73'
ORDER BY metric_id;

-- Q2：当前库内可见的成员历史
SELECT metric_id, dimensions_json, unit,
       COUNT(DISTINCT period_end) AS periods,
       MIN(period_end) AS earliest,
       MAX(period_end) AS latest,
       GROUP_CONCAT(DISTINCT definition_version) AS catalog_versions
FROM source_claim
GROUP BY metric_id, dimensions_json, unit
ORDER BY metric_id, dimensions_json;
```

目录版本不能机械隔离：同一定义可以跨目录选值；本次社融同比和政策利率确实采用了旧目录声明。依据：[same_definition.py:45](/mnt/d/cursor/datasourceRF/src/pring_cycle/same_definition.py:45)、[same_definition.py:67](/mnt/d/cursor/datasourceRF/src/pring_cycle/same_definition.py:67)。下文也区分**当前清理后的库内历史**与**运行时曾取得并计算过的历史**。

判定标准：

- **充分**：主要读法所需原始数据齐全；不表示 ADR-0037 的新确认关系已经实现。
- **需加工**：主要输入已有，需要组合、派生或修正现有读法。
- **缺数据**：至少一个必需读法缺成员、历史或事件覆盖；仍可展示已有水平和局部读法。
- 月度“连续两期改善”通常至少需要 **3 个水平值**；若要求“超过两期宽限后仍持续”，还需第三个信号期。不能把两个水平值产生的一次变化当成两个持续信号。依据：[CONTEXT.md:51](/mnt/d/cursor/datasourceRF/CONTEXT.md:51)、[CONTEXT.md:55](/mnt/d/cursor/datasourceRF/CONTEXT.md:55)。

**逐个关键指标核对**

下面覆盖 `key-indicators.md` 的全部 **23 行**。未适用的读法，例如债券价格的“同比多增”或 PMI 的政策事件，不强行要求。

| 关键指标 | 所需成员（按 key-indicators.md） | 1 目录是否存在：metric_id、维度、单位 | 2 最近运行现行数据、持有期、来源；source_claim 最新期 | 3 历史、所需读法、取数覆盖与缺口 | 4 结论 |
|---|---|---|---|---|---|
| 政策利率 | 7 天逆回购政策利率 | `CN_OMO_7D_RATE`，无维度，`percent`。[metric_contracts.py:271](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:271) | Q1：**stale**，持有 **09-28**，`pbc:omo_notice`。Q2：最新 **09-28**。投影却标 `current`，值 **1.4%**。 | Q2：仅 **09-24、09-28 两期**，均 1.4%，且没有 v0006 新声明。能读当前水平及这两次记录间不变；**不能证明完整近 120 日是否下调过**。现行基准有效至变更，不能按日频简单判过期；还需动作历史和窗口起点基准。 | **缺数据**：缺事件窗口历史；另需修正时效口径冲突。 |
| LPR | 主 `1y`；辅 `5y_plus` | `CN_LPR_1Y_5Y{tenor}`，`percent`。[metric_contracts.py:68](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:68) | Q1：current，持有 **09-30**，`chinamoney:lpr`；Q2：两成员最新均 **09-30**。 | 两成员均仅 **1 期，2026-09**。只能读 3.0%、3.5% 水平；无上期，不能判动作；不能检查近 120 日降息、持续两期。常规缺口计划默认只要求最新一期，须补窗口内报价及窗口前基准。 | **缺数据**：缺月度报价历史。 |
| 降准 | 调整方向、释放资金 | `CN_RRR_EVENT{scope,measure}`；`rrr_change` 为百分点，`released_funds` 为亿元，解析器已有该字段。[models.py:567](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:567)、[official_context.py:2023](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:2023) | Q1：current，持有 **2025-05-15**，`pbc:rrr_notice`。Q2：两个适用范围的 `rrr_change` 最新均此日；**释放资金无声明**。 | 每个范围仅 **1 个事件期**；值为 −0.5、−5 个百分点，不能跨范围相加。该事件在当前 120 交易日窗口外；本轮监测为 `none_stated`，只证明本轮资讯未见新公告，不能替代全窗口事件完备性。旧降准不能当作窗口内宽松动作。 | **缺数据**：释放资金缺成员数据；完整事件覆盖不足。 |
| 流动性投放 | 7 天逆回购净投放；辅月度工具流动性 | `CN_OMO_7D_AMOUNT{measure=injection}`，亿元；`net_injection` 由公式生成。辅 `CN_TOOL_LIQUIDITY_MONTHLY{tool,measure}`，8 工具 × 投放／回笼／净投放。[metric_contracts.py:253](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:253) | Q1：两者 current；持有分别 **09-30、08-31**，来源 `pbc:omo_notice`、`pbc:tool_liquidity`。Q2 最新同持有期。 | 日投放 **21 期，09-01—09-30**；无显式 `maturity` 声明，但已有 7 日期限加交易日历推算。目标日净投放 **−80 亿元**。须逐日重算净额后比较净额变化；当前派生 `direction` 按净额正负，并非较上期变化。月度工具各只有 **8 月一期**，辅助动量缺历史。 | **需加工**：主要净投放可算；补净额序列、变化读法，辅助工具另补历史。 |
| 短端资金价格 | DR007 相对政策利率、升降；辅 SHIBOR 三期限 | `CN_DR007`：%；`CN_DR007_POLICY_SPREAD`：基点；`CN_SHIBOR_ON_1W_3M{tenor=overnight/1w/3m}`：%。[metric_contracts.py:128](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:128)、[full_run_requirements.py:123](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:123) | Q1：DR007 **awaiting_release**，持有 **09-29**，`tushare:repo_daily`；政策利差 **stale**、无持有期；SHIBOR current，持有 **09-30**，`tushare:shibor`。Q2 最新分别 09-29、09-30。 | DR007 **121 个日期，04-09—09-29**；SHIBOR 各 **122 个日期，04-09—09-30**，须按各自有效日历对齐。升降、连续日信号有输入；投影已算利差 **−1.38bp**。需统一事件政策利率有效性及利差 freshness；awaiting_release 不应被写成已有 09-30 观测。 | **需加工**：输入足够，修正时效并对齐日期。 |
| 长端债价 | 930916；辅 CNY030 | `CN_BOND_10Y_930916{source_code=930916.CSI}`、`CN_BOND_FULL_PRICE_CNY030{source_code=000012CNY030.CSI}`，均指数点。[models.py:553](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:553)、Q0 目录定义 | Q1：均 current，持有 **09-30**，`tushare:index_daily`；Q2 最新均 09-30。 | 各 **120 日，04-09—09-30**；可算水平、价格升降、双方分化。按价格上涨／下跌读，不能当收益率。作为观察接口，不计确认度。 | **充分**。 |
| 社融 | 主存量同比；辅累计差分当月增量、政府债／非政府结构 | `CN_SF_TOTAL{stock_yoy,stock_end,ytd_increment}`；同比 %，余额／流量亿元。`CN_SF_COMPONENTS{component,measure}` 有政府债等 8 分项。[metric_contracts.py:206](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:206) | Q1：总量、分项均 current，持有 **08-31**；来源 `tushare:sf_month`、`pbc:social_financing`。Q2：官方 `stock_yoy` 最新 **08-31**，来自人民银行，投影采用 **7.2%**。 | 官方同比 **1 期**；余额 **5 期，04—08 月**；累计增量 **14 期，2025-07—2026-08**；分项各 **1 期，8 月**。同比水平可读，动量／斜率／持续性不可读；余额也缺去年同月。累计差分已有实现，可算总量当月增量；**不能据总量长历史推断结构长历史齐全**。 | **缺数据**：优先补官方同比及分项历史，无需新增总量指标。 |
| 贷款 | 企业中长期当月增量同比多增／少增；辅其他期限、借款人 | `CN_LOAN_STRUCTURE{borrower=enterprise,tenor=long_term,measure=ytd_increment}`，亿元；当月流量为派生 `monthly_change`。[metric_contracts.py:233](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:233) | Q1：current，持有 **08-31**，`pbc:loan_structure`；Q2：9 个借款人／期限组合最新均 08-31。 | 所有组合均只有 **2026-08 一期累计值**。当月派生代码已有，但缺 2026-07；同比多增还缺 **2025-07、2025-08**。本次运行无贷款派生结果。现有公式需求仅 **2 期**，没有去年同期需求。 | **缺数据**：补当月差分基期及去年同期两期；再加工同比差额。 |
| M1/M2 | 主 M1 同比；辅 M2 同比、M1−M2 | `CN_M1_M2{aggregate=m1/m2,measure=yoy/balance}`；同比 %、余额亿元。[metric_contracts.py:200](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:200) | Q1：current，持有 **08-31**，`tushare:cn_m`；Q2：全部成员最新 08-31。 | 各 **5 个连续月，04—08 月**。同比水平、较上月动量、三期斜率、连续信号和有限宽限检查均有输入；M1−M2 是同月同比之差，单位百分点。实际请求从 **2026-01** 开始，范围足够。 | **充分**。 |
| 信用脉冲 | 现有 12 个月派生，仅展示 | `CN_CREDIT_IMPULSE`，无维度，%；公式 `credit-impulse-12m-flow-share-v0003`。[models.py:483](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:483) | Q1：current，持有期为空，来源 `derived:CN_SF_TOTAL+CN_GDP`；无同名 source_claim。投影统计期 **08-31**。 | 总量累计社融 **14 期**、名义累计 GDP **5 季，2025Q2—2026Q2** 支持当前公式；本次结果 **22.9243%**，方向 down。不是社融存量同比，也不单独计票。 | **充分**：已有派生输出及必要父输入。 |
| PMI | 制造业；辅新订单、生产、采购量 | `CN_PMI_ACTIVITY{series=manufacturing/new_orders/production/purchase_volume,measure=level}`，扩散指数点。[metric_contracts.py:114](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:114) | Q1：current，持有 **09-30**，`tushare:cn_pmi`；Q2 四成员最新均 09-30。 | 各 **6 个连续月，04—09 月**。50 线、动量、三期斜率、连续两期信号均可算；实际取数从 **2026-02** 开始。制造业 7—9 月为 **49.2→49.8→50.1**：上升，但增幅收窄。 | **充分**。 |
| 工业增加值 | 当月实际同比；辅累计同比、季调环比 | `CN_INDUSTRIAL_VA{measure=current_month_real_yoy/ytd_real_yoy/mom_seasonally_adjusted}`，%。[metric_contracts.py:165](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:165) | Q1：current，持有 **08-31**，`nbs:industrial_va`；Q2 各成员最新均 08-31。 | 各 **1 期，8 月**。能读当月同比 **5.2%**、官方季调环比 **0.54%**，但不能把后者替代“同比较上月加快／放缓”；缺 7 月动量、6 月斜率基期及宽限历史。常规计划只要求最新期。 | **缺数据**。 |
| GDP | 实际季度同比；辅名义累计 | `CN_GDP{aggregate=total,measure=real_quarter_yoy}`：%；`nominal_ytd_level`：亿元；三产业成员也存在。[metric_contracts.py:144](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:144) | Q1：current，持有 **2026Q2／06-30**，`tushare:cn_gdp`；Q2 实际同比最新为 Q2。 | 当前实际同比各仅 **1 季 Q2**；名义总量有 **5 季**，不能替代实际同比历史。**本次投影已经记录 Q2 实际同比 4.3%、direction=down，并引用 Q1；Q1 声明目前已被清理。** 实际请求起点 **2025Q1**，所以不是请求跨度不足。季度动量、宽限应每轮重新取得正确实际同比上一季。 | **缺数据〔清理后重算口径〕**；本次运行已算过动量，不能误报为当时没算出。 |
| 产能利用率 | 全工业季度水平、同比变化 | `CN_CAPACITY_UTILIZATION{industry=all_industry,measure=quarter_rate/yoy_change/ytd_rate}`；水平 %、同比变化百分点。[metric_contracts.py:191](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:191) | Q1：current，持有 **2026Q2／06-30**，`nbs:capacity_utilization`；Q2 最新同此。 | 各 **1 季 Q2**。水平 **73%**、官方同比变化 **−1pp** 已有，**不需要另取去年 Q2 才能读这个官方同比变化**；但季度间动量、转折持续性和季度宽限仍缺 Q1。当前计划只要求 Q2。 | **缺数据**：缺上一季；“高／低”还需冻结判定规则。 |
| 工业企业盈利 | 利润官方同比；辅营收、成本 | `CN_INDUSTRIAL_FINANCE{item=profit/revenue/cost,measure=official_yoy/ytd_level}`；%、亿元；均为年初至今口径。[metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175) | Q1：current，持有 **08-31**，`nbs:industrial_finance`；Q2 六成员最新均 08-31。 | 各 **2 期，07—08 月**。可比较两次发布的**累计利润同比**，本次 8 月 **15.7%**、方向 down；不是“8 月单月利润下降”。若加三期斜率、连续两次改善及宽限判断，缺 6 月及更早基期。 | **缺数据〔完整持续性要求〕**；基本累计同比动量已可读。 |
| PPI | headline yoy；辅 mom、生产资料、生活资料 | `CN_PPI{category=headline/means_of_production/consumer_goods,measure=yoy/mom/cumulative_average_yoy}`，%。[metric_contracts.py:158](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:158) | Q1：current，持有 **08-31**，`tushare:cn_ppi`；Q2 全部成员最新 08-31。 | 各 **1 期，8 月**。同比水平和官方当月环比可读；同比动量、斜率、宽限不可读。实际 API 请求 **2026-01—09**，因此扩大 start 参数本身不能解决现有历史未进入可用声明的问题。 | **缺数据**。 |
| CPI | headline yoy；辅核心 CPI | `CN_CPI_HEADLINE{category=headline,measure=yoy}`、`CN_CORE_CPI{category=ex_food_energy,measure=yoy}`；另有 mom、累计平均同比，均 %。[metric_contracts.py:280](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:280) | Q1：均 current，持有 **08-31**；来源分别 `tushare:cn_cpi`、`nbs:core_cpi`。Q2 最新均 08-31。 | 各成员只有 **8 月一期**。总体和核心水平可读，月度同比动量、三期斜率、核心黏性持续性、宽限均缺历史。headline 实际请求 **2026-01—09**，范围已经覆盖，但可见声明没有对应历史。 | **缺数据**。 |
| PMI 价格 | 主出厂价格；辅购进价格 | `CN_PMI_PRICES{series=output_prices/purchase_prices,measure=level}`，扩散指数点。[metric_contracts.py:124](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:124) | Q1：current，持有 **09-30**，`tushare:cn_pmi`；Q2 两成员最新均 09-30。 | 各 **6 个连续月，04—09 月**。50 线、动量、分化、持续期数可读；如果新模型加斜率，也有三期以上。与其他 PMI 共用从 2 月开始的取数。 | **充分**。 |
| 上游商品 | NHCI；辅篮子、WTI、Brent；NHII 标同源 | `CN_COMMODITY_BROAD_NHCI{source_code=NHCI.NH}`：指数点；篮子指数点、分项贡献百分点；油价美元／桶。[models.py:534](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:534)、[metric_contracts.py:102](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:102) | Q1：NHCI、篮子、分项 current，持有 **09-30**，`tushare:fut_index_daily/fut_daily`；油价 current，持有 **09-29**，`eia:petroleum_spot`。Q2 最新同持有期。 | NHCI、篮子、7 分项各 **120 日，04-09—09-30**；WTI **120**、Brent **121** 个日期，均始于 04-09、止于 09-29。价格动量及篮子上涨广度可算，先对齐日期；这些价格不能确认供需推动力。 | **充分〔价格观察〕**。 |
| 产成品存货 | 名义同比；辅实际库存近似 | `CN_FINISHED_GOODS_INVENTORY{measure=official_yoy/nominal_end_level}`；%、亿元。[metric_contracts.py:181](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:181) | Q1：current，持有 **08-31**，`nbs:industrial_finance`；Q2 最新同此。 | 两成员各 **2 期，07—08 月**。同比水平 **11%**、较上月方向 up 可读；连续两次变化／超宽限缺更早基期。实际库存近似当前月已生成，但 PPI 只有一期，实际库存近似的历史动量仍不足。 | **缺数据〔完整持续性要求〕**。 |
| PMI 库存 | 主产成品；辅原材料 | `CN_PMI_INVENTORY{series=finished_goods/raw_materials,measure=level}`，扩散指数点。[metric_contracts.py:120](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:120) | Q1：current，持有 **09-30**，`tushare:cn_pmi`；Q2 最新均 09-30。 | 各 **6 个连续月，04—09 月**。50 线、动量、分化、持续性可读；只能辅助库存象限，不能代替产成品存货同比。 | **充分**。 |
| 库存周转 | 同比变化；辅天数 | `CN_INVENTORY_TURNOVER{measure=official_yoy_change/days}`，实际成员单位均为 **days**。[metric_contracts.py:186](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:186) | Q1：current，持有 **08-31**，`nbs:industrial_finance`；Q2 最新均 08-31。 | 各 **2 期，07—08 月**。8 月天数 **21.3**、同比增加 **0.6 天**，二者较上期均 flat。官方同比变化已给，不需重算去年基数；但连续两次变化／宽限缺更早基期，持平不能读成缓和。 | **缺数据〔完整持续性要求〕**。 |
| 仓单 | 8 品种合计；辅各品种 | `CN_FUTURES_WARRANTS{symbol,warehouse,exchange,measure=registered_receipts}`；8 品种齐全，但单位混合。[metric_contracts.py:78](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:78)、[models.py:567](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:567) | Q1：current，持有 **09-30**，`tushare:fut_wsr+czce:warehouse_receipts`；Q2 各品种最新均 09-30。 | v0006：CF、TA 各 **105 日**；CU、PP、RB、RU、SC、SP 各 **119 日**，均始于 04-09；8 品种共有日期 **104 日**。CF/TA 为张，PP 为手，SC 为桶，其他为吨。**不能直接相加**。可先按品种汇总仓库，再做固定规则的标准化变化／方向广度；空缺日不能补零。 | **需加工**：“8 品种合计”必须改为有定义的综合读法。 |

**库存象限、价格内部一致性、债券归因与成熟度**

| 关键指标／模块 | 所需成员 | 1 目录是否存在 | 2 最近运行与最新期 | 3 所需读法与缺口 | 4 结论 |
|---|---|---|---|---|---|
| 库存象限——需求线 | PMI 新订单；辅工业营收 | `CN_PMI_ACTIVITY{series=new_orders,measure=level}`：指数点；`CN_INDUSTRIAL_FINANCE{item=revenue,measure=official_yoy/ytd_level}`：%、亿元。[metric_contracts.py:114](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:114)、[metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175) | Q1：均 current；主持有／最新 **09-30**，辅 **08-31**；分别 TuShare PMI、统计局工业财务。 | 主线 **6 期，04—09 月**；辅助 **2 期，07—08 月**。主线水平、动量、斜率、两期信号有输入。新订单 7—9 月 **48.5→50.6→50.5**，最新方向已经转向，不能因“有六期”就判持续改善。 | **充分〔主线〕**；辅助持续性缺历史。 |
| 库存象限——三线联合 | 需求新订单、生产工业增加值、库存产成品存货同比 | 三主成员均存在；生产和库存成员、单位见上表。[CONTEXT.md:411](/mnt/d/cursor/datasourceRF/CONTEXT.md:411) | Q1：三者均 current；统计期分别 **09、08、08 月**。 | **同为月频，可在 8 月对齐**；不能直接拼各自最新期。共同水平期只有 **8 月**；工业增加值缺 7 月，无法形成三线共同动量，更不能做象限持续性。辅 PMI 生产、产成品库存各有六期，不能替代缺失主线。 | **缺数据**：至少补工业增加值 7 月；完整宽限还需共同更早期。 |
| 价格内部一致性 | 三核心相对动量、个股广度、篮子分项 | 三核心：`CN_BOND_CORE_000012`、`CN_EQUITY_CORE_000985`、`CN_COMMODITY_CORE_NHII`，无维度、指数点。广度为 `CN_EQ_ADV_DEC/AD_RATIO/ADV_AMOUNT_SHARE/NEW_HIGH_LOW_90/250/ABOVE_MA90/250`，维度 `measure,universe`，单位家数／比值／%；篮子 7 分项贡献百分点。[models.py:510](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:510)、[breadth.py:35](/mnt/d/cursor/datasourceRF/src/pring_cycle/breadth.py:35) | Q1：以上均 current，持有 **09-30**；来源 `tushare:index_daily/fut_index_daily/daily/stk_factor_pro/fut_daily`。Q2：各成员最新 09-30。 | 各核心、广度及篮子成员都有 **120 日，04-09—09-30**。相对动量公式／期限尚未冻结；若比较 h 日收益率，需 **h+1 个价格点**，20 日需 21 点，120 日需 121 点。现有 120 点支持窗口内短于 120 日的端点收益比较。**行业集中度另缺行业成员**，见后文。 | **需加工〔三核心＋个股广度〕**；“少数行业维持”缺数据。 |
| 债券归因 | 核心债券趋势＋政策轴＋增长通胀轴 | 直接复用上表政策、GDP、工业增加值、PPI 等，不要求新指标编号。[CONTEXT.md:63](/mnt/d/cursor/datasourceRF/CONTEXT.md:63) | 核心债券 current、最新 09-30；政策与宏观时效、统计期见上表。 | 债券趋势有输出，但增长通胀多项缺动量，政策动作史不完整；不能把“部分轴未知”加工为完整归因。具备足够已知轴时可给相应附注，其余保持推动力不明。收益率曲线／信用利差用于细分，不是本版基础两轴的先决条件。 | **缺数据〔完整两轴判定〕**。 |
| 信号成熟度 | 政策利率、LPR、降准、DR007、M1、社融、PMI 新订单；表中还使用流动性、贷款转折 | 对应成员均已有目录／派生定义。[CONTEXT.md:55](/mnt/d/cursor/datasourceRF/CONTEXT.md:55)、[expectation-table.md:9](/mnt/d/cursor/datasourceRF/.scratch/macro-semantics-20261006/expectation-table.md:9) | 各自 Q1 状态及最新期见上表；不能将重跑当新发布。 | **M1、PMI 新订单、DR007** 有足够原始期数供连续变化检查；**社融同比、LPR、贷款** 不够；**政策利率和降准** 缺完整事件覆盖。OMO 可重算后检查，但必须先冻结日／周等信号周期。“多个先行信号同向”可使用齐备子集；不能据此补造缺失主指标的“确认”。 | **缺数据**：不能给所有先行指标完整三级成熟度。 |

**几项特别核实的结论**

**社融：官方同比存在，默认必需成员却把它排除了。**  
`official_source_members` 包含 `stock_yoy`，人民银行解析器也会生成；但 `required_dimension_members` 对 `CN_SF_TOTAL` **显式排除 `stock_yoy`**。TuShare 总量字段只取 `inc_cumval`、`stk_endval`。因此当前“社融数据齐全”并不保证新设计的主要成员齐全。最小修正是把官方存量同比及其历史纳入必需成员，不必优先新增余额同比公式。[metric_contracts.py:304](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:304)、[source_families.py:30](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_families.py:30)、[official_context.py:2218](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:2218)

总量累计转当月流量已在信用脉冲中实现，含年初重置和连续月检查；但这不等于已经有独立的社融当月流量展示行，也不等于分项历史齐全。[credit_impulse.py:761](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:761)

**贷款：已有 `monthly_change`，本次没有足够输入生成。**  
代码用同一借款人／期限的连续累计值差分，1 月直接采用当年累计值；非 1 月缺前月就跳过。本次最终计划明确将 **2026-07 标为 `model_input_missing`**，8 月为 `local_complete`。目标期同比多增最少需要：

\[
(YTD_{2026-08}-YTD_{2026-07})
-
(YTD_{2025-08}-YTD_{2025-07})
\]

四个累计端点中，当前仅有 2026-08。要进一步判断“少增收窄”，还要算上一月同比差额，需增加相应基期。[context_projection.py:1098](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1098)、[full_run_requirements.py:124](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:124)

**OMO：到期量是推算的，不是现有 `maturity` 原始成员。**  
v0014 使用 `repo-net-injection-trading-calendar-v0002`：历史投放日加 **7 个自然日**，顺延至代码采用的交易日；同日到期投放求和，再从当日投放中减去。本次父输入为 **09-23 投放 80、09-30 投放 0、09-30 核心股票交易日价格声明**，结果 −80，`maturity_basis=derived_7d_trading_calendar`。[context_projection.py:849](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:849)、[context_projection.py:1200](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1200)

这支持**限定为七天逆回购的推算净投放**，不是全部央行工具净投放。需检查操作历史完整性，缺投放记录不能默认为零；银行操作／到期日历与当前使用的股票交易日日历也应明确契约。现有派生行按净额正负赋方向，需改为同时给“净投放／净回笼”和“较前期增加／减少”。[context_projection.py:1245](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1245)

**GDP：上一季在取数范围内，但运行后未必仍在明细库。**  
本次 `cn_gdp` 起点为 **2025Q1**；Q2 实际同比的投影方向是 down，其前期引用 `4dd1…eb9e` 在当前 `source_claim` 中查询为 **0 行**。名义总量的五季因信用脉冲父输入留存，实际同比 Q1 不享有这个派生父输入关系，已被清理。因此应每次重新取得，而不是扩大永久留存。另不能直接将 TuShare 的 GDP yoy 字段当正确季度实际同比：当前适配器因期别语义未核实会拒收该字段。[tushare_context.py:1819](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1819)、[retention.py:154](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:154)

**工业盈利：可读“累计同比的月度发布变化”，不能冒充单月利润动量。**  
保持既定主要成员时，使用 \(g_t^{累计同比}-g_{t-1}^{累计同比}\)。累计金额差分可以得到单月金额，但累计同比百分数不能直接差分成单月同比；即便反推去年累计基数，也须处理可比口径、修订和舍入，不能标为官方单月同比。[metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175)

以上投影与派生结果可用下列查询复核：

```sql
-- Q3：指定投影中的关键结果
SELECT
  json_extract(document_json, '$.credit.evidence[7]') AS sf_stock_yoy,
  json_extract(document_json, '$.policy_action.evidence[2]') AS omo_net,
  json_extract(document_json, '$.international_context[8]') AS gdp_real_yoy
FROM analytical_dataset
WHERE projection_set_id='projection-99c6c8454595864f19b6'
  AND dataset_name='macro';
-- 结果摘要：
-- 社融：2026-08-31，stock_yoy=7.2，direction=unknown，status=current
-- OMO：2026-09-30，net_injection=-80，maturity_amount=80，
--      maturity_basis=derived_7d_trading_calendar
-- GDP：2026-06-30，total/real_quarter_yoy=4.3，direction=down

SELECT COUNT(*) FROM source_claim
WHERE claim_id='4dd1bad5778d1da80edbfe43fa966282735f4184c0be3fbf0f8d14ff7f0aeb9e';
-- 0：GDP 投影引用的前期声明当前已不在明细库

SELECT metric_id, formula_version, COUNT(*)
FROM derived_observation
WHERE batch_id='run-cfb8d12142289f56af73'
  AND metric_id IN ('CN_LOAN_STRUCTURE','CN_OMO_7D_AMOUNT','CN_CREDIT_IMPULSE')
GROUP BY metric_id, formula_version;
-- OMO 1 行，信用脉冲 1 行；贷款 0 行
```

**汇总**

以 `key-indicators.md` 的 **23 行**为互斥统计单位，按照上表“完整读法及适用持续性”的严格口径：

| 结论 | 数量 | 清单 |
|---|---:|---|
| 充分 | **7** | 长端债价、M1/M2、信用脉冲、PMI、PMI 价格、上游商品、PMI 库存 |
| 需加工 | **3** | 流动性投放、短端资金价格、仓单 |
| 缺数据 | **13** | 政策利率、LPR、降准、社融、贷款、工业增加值、GDP、产能利用率、工业企业盈利、PPI、CPI、产成品存货、库存周转 |

其中盈利、产成品存货、周转已经能读一次月度变化；GDP 本次运行已经算过季度动量。归入缺数据，不代表这些指标完全不可用。

组合模块不重复加进这 23 项：需求主线充分；库存象限、完整债券归因、全套信号成熟度缺数据；基础价格内部一致性需加工，行业集中度缺成员。

这也是**可得性盘点数量，不是确认度票数**。按既定观察接口和库存合并规则，六阶段表的基本计数单元为政策 5、信用 3、过热 5、物价 3、库存象限 1，共 **17 项**；价格观察和派生不额外计票。[expectation-table.md:7](/mnt/d/cursor/datasourceRF/.scratch/macro-semantics-20261006/expectation-table.md:7)、[ADR-0037:14](/mnt/d/cursor/datasourceRF/docs/adr/0037-confirmation-counts-key-indicators-against-stage-narrative.md:14)

**是否需要新增指标**

**基础确认度第一版：不必新增宏观 `metric_id`，但必须补采现有成员和历史。** 最小补齐集合是：

1. 社融官方 `stock_yoy` 最近至少三期，并升级为必需成员；分项历史用于政府债／非政府分化。
2. 企业中长期贷款今年与去年同期的累计差分端点，并为持续性追加必要比较期。
3. 工业增加值、CPI／核心 CPI、PPI 的连续月历史；GDP 实际同比、产能利用率的上一季度。
4. 盈利、存货、周转的更早基期，以支持持续两次变化和宽限。
5. 政策利率、LPR 的窗口动作史与窗口前基准；降准释放资金及事件覆盖。
6. 将净投放变化、库存三线共同月份、仓单标准化组合、三项相对动量写成明确加工规则。

**有一个按现有文案必须补的数据成员：行业广度。**  
预期表第 125 行要求判断“股票靠少数行业维持”，但现有广度只有全市场个股汇总，`stock_basic` 取数字段也没有行业。全市场广度不能识别行业集中度。若保留这句断言，最小新增是**适时有效的股票行业映射＋按行业计算的涨跌／趋势广度成员**，可扩展广度维度或新增派生指标；若将文案收窄为“上涨集中于较少个股”，现有成员即可支持。不能直接把个股集中写成行业集中，也不能仅凭广度低就确认权重贡献。[breadth.py:35](/mnt/d/cursor/datasourceRF/src/pring_cycle/breadth.py:35)、[breadth.py:58](/mnt/d/cursor/datasourceRF/src/pring_cycle/breadth.py:58)、[expectation-table.md:125](/mnt/d/cursor/datasourceRF/.scratch/macro-semantics-20261006/expectation-table.md:125)

**增强项仍按已定扩充准入处理：**

| 增强项 | 能补什么 | 不补时的边界 |
|---|---|---|
| 中国国债收益率曲线 | 长短端方向、曲线变化 | 债价仍可观察，曲线归因未确认 |
| AAA 同期限信用利差 | 高等级企业信用风险价格 | 不能把资金宽松直接等同信用风险缓解 |
| 社零 | 库存需求线中的消费验证 | PMI 订单主线仍可用，消费分支未确认 |
| EIA 石油收支子集 | 限定地域、品种的实物供需检验 | 油价、篮子、仓单只能提供价格／注册库存观察 |
| 新发放企业贷款利率 | 实体成交融资价格传导 | LPR 不能替代成交融资成本 |
| 应收与回款数据 | 回款压力、现金兑现 | 营收、利润、库存不能替代回款 |

前四项在扩充表中已有采纳方向，新发放贷款利率仍待解析复杂度核实；不应为填满当前确认表而提前假定已接入。[expectation-table.md:203](/mnt/d/cursor/datasourceRF/.scratch/macro-semantics-20261006/expectation-table.md:203)、[expectation-table.md:166](/mnt/d/cursor/datasourceRF/.scratch/macro-semantics-20261006/expectation-table.md:166)、[缺失指标研究:265](/mnt/d/cursor/datasourceRF/docs/research/pring-missing-indicator-availability.md:265)

**需要调整的取数范围与回看**

现有两个机制没有完整表达新设计的历史要求：

- `full_run_requirements.py` 只为现有公式声明期数；贷款为 2，多个其他输入为 1，没有普遍的三期斜率、同比差额和成熟度需求。[full_run_requirements.py:119](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:119)
- `full_retrieval.py` 对没有专门历史需求的低频指标默认只要求 **1 期**。Worker 的常规 API 起点则是窗口首日当时最新已发布期再往前一期，两者并不保证“每个所需成员的历史已成功采用”。[full_retrieval.py:416](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:416)、[worker.py:1344](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1344)

应按**成员＋读法＋实际发布期**建立最小回看：

| 读法 | 最小输入 | 调整方式 |
|---|---|---|
| 水平 | 当前有效一期 | 保持；事件用有效基准 |
| 月度动量 | 连续两期同口径值 | 对官方直连成员同样要求，不只给 TuShare 设置起点 |
| 斜率变化 | 连续三期 | 窗口首日也需两期前置历史 |
| 连续两期变化信号 | 通常三个水平值 | 按独立统计期计数，不能按运行次数 |
| 超过月度两期／季度一期宽限 | 起始信号及后续发布历史 | 保存或重新计算信号起点；不能从当前一个符号猜持续期数 |
| 存量同比，若自行计算 | \(S_t,S_{t-12}\) | 13 个月度时间点包含首尾；优先采用官方同比 |
| 当月流量同比多增 | \(Y_t,Y_{t-1},Y_{t-12},Y_{t-13}\) | 累计口径通常需最远 **t−13** 的差分基点，不能笼统写“13 期就够” |
| 季度动量 | 当前、上一季度同口径值 | GDP 实际同比与名义累计分开验收；季度官方同比变化可直接采用 |
| 七天逆回购净投放变化 | 当前及前期投放、各自到期来源、完整日历 | 获取足够前置操作历史；区分没操作与漏数据 |
| h 日相对动量 | 对齐后的 h+1 个核心价格点 | 冻结 h；如采用 120 日收益，补第 121 点，不能将 120 点当 120 个收益间隔 |

**13 个月取数不自动违反 ADR-0035。** 应区别“一期指标的经济尺度”和“取得端点／差分基期的范围”：

- 存量同比比较相隔一年的两个余额，覆盖一年；包含首尾的 **13 个观测点**不等于 13 个月指标尺度。
- 累计转当月同比差额还需额外差分基期。ADR-0035 已为信用脉冲采用同类处理；当前代码明确要求 **13 个流量期，再视年初位置追加一期累计基期**，本次为社融 14 期、GDP 5 期。[credit_impulse.py:94](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:94)、[credit_impulse.py:158](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:158)
- 为计算整个 120 交易日窗口而合并各日回看，实际最早请求日期还会更早。本次社融取到 **2025-01**、GDP 取到 **2025Q1**，并不表示每一期公式改成超过一年。[credit_impulse.py:186](/mnt/d/cursor/datasourceRF/src/pring_cycle/credit_impulse.py:186)
- 应在新公式契约中明确列出这些基期，而不是把所有辅助指标统一扩成长期历史；超留存部分每轮重取、用后清理。仍在留存期的派生读法若登记父声明，可按既有例外随派生结果保留，无需扩大 120 交易日留存。[ADR-0035:11](/mnt/d/cursor/datasourceRF/docs/adr/0035-metric-horizon-at-most-one-year.md:11)、[ADR-0022:15](/mnt/d/cursor/datasourceRF/docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:15)

另有三项需要在模型规格中定清：**“近 120 日”是自然日还是交易日、相对动量的具体期限、“高位／低位／明显”的判定方式**。这些属于规则缺口，不能靠补数据自行决定；尤其不能为“高低位”悄悄引入多年分位数而突破一年尺度。
