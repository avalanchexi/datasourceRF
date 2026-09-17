# 调查：6 项 P2 国际行情的标准口径发布方（2026-09-17）

用户 2026-09-17 答复：真空那 6 项"可通过 AI websearch 获取，顺便帮我找一下，比较靠谱的数据发布方作为标准口径。可以是资讯平台。"

本次用 WebSearch 只做发布方与获取条件的核实，**未发起任何数据抓取**。

## 一个先于建议的结论

**这 6 项里有 4 项存在明确的官方发布方**——不是"找个靠谱资讯平台"的问题，而是本来就能走官方认证路径。只有 2 项真正需要退到非官方口径。这改变了票24 对它们的处理方式。

| 指标 | 权威发布方 | 获取条件 | 建议身份 |
|---|---|---|---|
| `CBOE_VIX_INDEX` | **Cboe Global Markets**（指数编制方） | **免费公开 CSV**，1990 至今：`cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | **官方认证** |
| `NASDAQ_SOX_INDEX` | **Nasdaq**（PHLX Semiconductor Sector 指数编制方） | 官方指数站 `indexes.nasdaq.com/Index/History/SOX` 提供历史；需核实是否可程序化取用 | **官方认证**（待核实取用方式） |
| `CN_USDCNY_CLOSE_1630` | **中国外汇交易中心（CFETS）/ 中国货币网** | 官方站点 `chinamoney.com.cn`；本项目已有 CFETS 通道（`CN_LPR_1Y_5Y` 即走该域且**已认证**） | **官方认证** |
| `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | **CME Group**（结算价由 CME 员工按 13:29–13:30 ET 结算窗口确定） | 官网每日结算页公开；**历史批量需 CME DataMine（付费）** | 官方认证（当日）/ 历史受限 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | **ICE Benchmark Administration（IBA）** 管理，LBMA 发布 | **历史数据需 IBA 授权**，LBMA 站上的历史序列已应 IBA 要求下架；免费替代是 **FRED** 的 `GOLDPMGBD228NLBM`（美联储圣路易斯分行转发） | **非官方**（FRED 转发） |
| `CN_USDCNH_FXCM` | 离岸人民币**无单一官方即期价**。最接近的基准是香港**财资市场公会（TMA）**的 USD/CNH 即期定盘；目录里现写的 "FXCM" 是一家零售经纪商，**不是基准发布方** | TMA 定盘由指定计算代理发布；FXCM 报价属经纪商自有 | **非官方**，且**口径需重新定义** |

## 必须指出的一处目录缺陷

`CN_USDCNH_FXCM` 这个指标 id 把**经纪商名字焊进了口径**。FXCM 是零售经纪商，它的报价是自家撮合价，不是任何基准。拿它当"离岸人民币"的标准口径，等于把一家券商的报价当市场基准——这与票13 最初"数值对得上不等于口径有依据"是同一类问题。

**建议在票24 里把它重新定义**（例如改用 TMA 的 USD/CNH 即期定盘，或明确它只是参考价而非基准），而不是照原样接一个数据源。这需要用户决定。

## 与 `COMEX_GC` / `LBMA_GOLD` 的重叠

两者都是黄金价格，一个是 COMEX 期货结算价、一个是伦敦现货定盘。**都要、还是只要一个**，也需要确认——两项都取意味着两条受限通道（CME DataMine 付费、IBA 授权），而它们的信息量高度重叠。

## 本次没做的

- 未验证任一 URL 当前可达（只核实了发布方与授权条件）。
- 未核实 TuShare 是否已覆盖其中某几项（它有 `index_global`、`fx_daily` 等接口，**可能已覆盖 VIX / SOX / 汇率**）。这一步应在接任何新源之前做——与调查一的结论同理：先看既有通道，再谈新增。

**Sources:** [Cboe VIX 历史数据](https://www.cboe.com/tradable-products/vix/vix-historical-data)、[FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS)、[Nasdaq SOX 历史](https://indexes.nasdaqomx.com/Index/History/SOX)、[LBMA 金价 FAQ](https://www.lbma.org.uk/prices-and-data/lbma-gold-price/lbma-gold-price)、[ICE 贵金属基准](https://www.ice.com/iba/lbma-precious-metals)、[CME 每日结算](https://www.cmegroup.com/market-data/daily-settlements.html)、[CME 黄金结算](https://www.cmegroup.com/markets/metals/precious/gold.settlements.html)、[中国货币网](https://www.chinamoney.com.cn/chinese/bkrmbidx/)、[HKMA CNH HIBOR 定盘](https://www.hkma.gov.hk/eng/news-and-media/press-releases/2013/04/20130425-3/)、[HKEX USD/CNH 期货](https://www.hkex.com.hk/Products/Listed-Derivatives/Foreign-Exchange/USD-CNH-Futures?sc_lang=en)
