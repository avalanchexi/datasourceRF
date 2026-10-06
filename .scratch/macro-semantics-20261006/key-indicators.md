# 关键指标、主要成员与读法（访谈 Q11，2026-10-06 用户确认）

全部来自现有 61 个指标，不新增指标。规则见 `CONTEXT.md`「关键指标」「方向读法」「确认关系」「确认度」「价格内部一致性」。

| 维度 | 关键指标 | 主要成员 | 读法（水平／动量） | 辅助成员（仅展示一致度） |
|---|---|---|---|---|
| 政策 | 政策利率 | `CN_OMO_7D_RATE` | 动作：下调／上调／不变 | — |
| 政策 | LPR | `CN_LPR_1Y_5Y` tenor=1y | 动作：下调／上调／不变 | 5y_plus |
| 政策 | 降准 | `CN_RRR_EVENT` | 动作：降／升；释放资金 | — |
| 政策 | 流动性投放 | `CN_OMO_7D_AMOUNT` 净投放 | 动量：净投放增减 | `CN_TOOL_LIQUIDITY_MONTHLY` |
| 政策 | 短端资金价格 | `CN_DR007` | 水平：相对政策利率（`CN_DR007_POLICY_SPREAD`，派生）；动量：升降 | `CN_SHIBOR_ON_1W_3M` |
| 政策 | 长端债价 | `CN_BOND_10Y_930916`（按价格读） | 动量：债价走强／走弱 | `CN_BOND_FULL_PRICE_CNY030` |
| 信用 | 社融 | `CN_SF_TOTAL` 存量同比 | 水平；动量 | 当月增量（累计差分）；`CN_SF_COMPONENTS` 政府债／非政府 |
| 信用 | 贷款 | `CN_LOAN_STRUCTURE` 企业中长期当月增量 | 动量：同比多增／少增 | 其他期限与借款人 |
| 信用 | M1/M2 | `CN_M1_M2` m1 yoy | 水平；动量 | m2 yoy；M1−M2（派生） |
| 信用 | 信用脉冲 | `CN_CREDIT_IMPULSE`（派生，不单独计数） | 展示 | — |
| 过热 | PMI | `CN_PMI_ACTIVITY` manufacturing | 水平：50 线；动量：较上月 | new_orders、production、purchase_volume |
| 过热 | 工业增加值 | `CN_INDUSTRIAL_VA` 当月实际同比 | 水平；动量 | 累计同比、季调环比 |
| 过热 | GDP | `CN_GDP` 实际季度同比 | 水平；动量 | 名义累计 |
| 过热 | 产能利用率 | `CN_CAPACITY_UTILIZATION` 全工业季度 | 水平：高低；动量：同比变化 | — |
| 过热 | 工业企业盈利 | `CN_INDUSTRIAL_FINANCE` 利润官方同比 | 动量 | 营收、成本 |
| 物价 | PPI | `CN_PPI` headline yoy | 水平：正负；动量 | mom；生产资料、生活资料 |
| 物价 | CPI | `CN_CPI_HEADLINE` yoy | 水平；动量 | `CN_CORE_CPI` |
| 物价 | PMI 价格 | `CN_PMI_PRICES` output_prices | 水平：50 线；动量 | purchase_prices |
| 物价 | 上游商品 | `CN_COMMODITY_BROAD_NHCI` | 动量 | 商品篮子、`EIA_WTI_RWTC`、`EIA_BRENT_RBRTE`；NHII 标"与核心同源" |
| 库存 | 产成品存货 | `CN_FINISHED_GOODS_INVENTORY` 名义同比 | 水平；动量 | 实际库存近似（派生） |
| 库存 | PMI 库存 | `CN_PMI_INVENTORY` finished_goods | 水平：50 线；动量 | raw_materials |
| 库存 | 库存周转 | `CN_INVENTORY_TURNOVER` 同比变化 | 动量 | 天数 |
| 库存 | 仓单 | `CN_FUTURES_WARRANTS` 各品种变化率中位数与方向广度（O2） | 动量 | 七品种折算吨数合计；SC 桶数单列 |

- 派生不单独计数：PMI 订单库存差与生产订单差、信用脉冲、M1−M2、DR007 政策利差、实际库存近似。
- 库存象限：需求取 PMI 新订单、生产取工业增加值、库存取产成品存货三者的主要读法联合推出；三者不一致为"未分类"。
