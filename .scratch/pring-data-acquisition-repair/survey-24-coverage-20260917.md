# 调查：缺口 × 覆盖面（2026-09-17）

为[票24](issues/24-non-official-adoptable-sources.md)准备。上一轮我问用户"哪家数据商对应哪些指标"，**问早了**——按 `/grilling` 的规矩，找事实是我的职责。这份表先把事实摆出来，剩下真正需要决定的才交给用户。

纯只读调查，未改任何代码。数据取自 `catalog.py` 的注册目录、`source_families.py` 的官方族、`source_adapters.CORE_API_IDENTITIES`、`tushare_context.py` 的指标引用。

## 第一个发现：缺的远不止三项

**61 个指标里只有 5 个是 `certified`，56 个是 `awaiting_source_certification`。**

| | 指标 |
|---|---|
| 已认证（5） | `CN_TRADE_CALENDAR`、`CN_EQUITY_CORE_000985`、`CN_BOND_CORE_000012`、`CN_COMMODITY_CORE_NHII`（前四项经 TuShare）、`CN_LPR_1Y_5Y`（CHINAMONEY 官方） |

票13 的"三项历史原件"只是这 56 项里最难的三项。**把它们解决了，另外 53 项仍然未认证**——它们卡的不是同一件事，所以不能指望票24 一把解决全部。

## 按现有采集通道分类的 56 项

| 类别 | 数量 | 含义 |
|---|---|---|
| **派生**（认证父项即可） | 5 | `CN_CREDIT_IMPULSE`、`CN_DR007_POLICY_SPREAD`、`CN_ORDER_INVENTORY_SPREAD`、`CN_PRODUCTION_ORDER_SPREAD`、`UST_2S10S_SPREAD` |
| **官方页 + TuShare 双通道** | 8 | `CN_CPI_HEADLINE`、`CN_M1_M2`、`CN_PMI_ACTIVITY/INVENTORY/PRICES`、`CN_PPI`、`CN_SF_TOTAL`、`CN_GDP` |
| **仅官方页** | 13 | `CN_CAPACITY_UTILIZATION`、`CN_CORE_CPI`、`CN_FINISHED_GOODS_INVENTORY`、`CN_INDUSTRIAL_FINANCE`、`CN_INDUSTRIAL_VA`、`CN_INVENTORY_TURNOVER`、`CN_LOAN_STRUCTURE`、`CN_OMO_7D_AMOUNT/RATE`、`CN_RRR_EVENT`、`CN_SF_COMPONENTS`、`CN_TOOL_LIQUIDITY_MONTHLY`、`CN_USDCNY_CENTRAL_PARITY` |
| **仅 TuShare** | 20 | `CN_DR007`、`CN_SHIBOR_ON_1W_3M`、`CN_FUTURES_WARRANTS`、`CN_MARGIN_BALANCE`、`CN_INDEX_VALUATION`、五项广度指标、三项 CSI 指数、两项债券指数、两项商品篮、`CN_COMMODITY_BROAD_NHCI`、`UST10Y/2Y_NOMINAL_YIELD` |
| **EIA 页面通道**（票14 已落地） | 2 | `EIA_BRENT_RBRTE`、`EIA_WTI_RWTC` |
| **系统内部，非采集** | 2 | `CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY`（只出现在 `full_retrieval.py`） |
| **真空：无任何既有通道** | 6 | `CBOE_VIX_INDEX`、`NASDAQ_SOX_INDEX`、`LBMA_GOLD_PRICE_PM_USD_OZT`、`COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT`、`CN_USDCNH_FXCM`、`CN_USDCNY_CLOSE_1630`（只在 `catalog.py` 出现，无适配器） |

## 第二个发现：TuShare 已经覆盖 28 项

**TuShare 已接入、令牌有效，且 `tushare_context.py` 已经为 28 个指标写了取数路径**（20 项独家 + 8 项与官方页双通道）。也就是说：

- 用户放开非官方可信源后，**这 28 项不需要新增任何数据商**——通道已经在跑，缺的只是"允许它们以非官方身份被采用"这个语义。
- 真正可能需要外部数据商的，是**真空那 6 项**（全部 P2 国际行情：VIX、费城半导体、伦敦金、COMEX 黄金、离岸人民币、在岸收盘价）。

## 因此需要用户决定的，从"挑数据商"缩成两件

1. **那 6 项 P2 国际行情怎么办**——是接一家商业数据商，还是干脆不纳入模型（它们全是 P2 国际背景，不是核心）？在拿到答案前，**不需要**决定 Wind / 同花顺 / 东方财富。
2. **双通道那 8 项的优先级**：官方页与 TuShare 都有时，谁优先？官方页取不到时是否自动降级到 TuShare（并标为非官方）？

原先"哪家数据商对应哪些指标"的问题，在拿到这张表后基本消解了——**TuShare 就是那份清单的主体**。

## 这份调查没有回答的

- 上述 28 项 TuShare 通道**当前是否真能取到数**（令牌权限、接口配额、历史深度）。本次是静态代码调查，未发请求。
- 官方页那 21 项**当前是否可达**（票14 已证明 EIA 需要页面回退，官方页也可能有同类问题）。
- 各通道的**发布时刻口径**——这正是票13 三项缺件的根源，很可能不止那三项有这个问题。

这三条要动网络，属票24 实现阶段的事，不在本次只读调查范围内。
