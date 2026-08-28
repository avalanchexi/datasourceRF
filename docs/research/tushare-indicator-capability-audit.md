# TuShare 对中国 Pring 周期驾驶舱的指标能力审计

> 研究日期：2026-08-20  
> 范围：只审计本项目已经确认的中国 Pring 六阶段驾驶舱所需数据，不做 TuShare 全站接口目录复述。  
> 证据边界：只使用 TuShare 官方文档及指标发布机构的一手资料；本研究工作流未读取 `.env`、token 或旧报告，也未调用任何需要 token 的真实 API。第 2.2 节仅转录根任务在用户授权后独立完成的最小账号验收结果，未包含 token 或完整数据。

## 1. 先区分四种结论

本文所说的“TuShare 有这个接口”，不等于“当前用户账号今天一定能调用”。TuShare 的积分是接口门槛而不是逐次消耗；不同接口还可能需要单独授权，且同一大类接口的文档权限表与端点页偶有不一致。[TuShare 权限说明](https://tushare.pro/document/1?doc_id=108)

能力结论使用以下四种状态：

| 结论 | 含义 |
| --- | --- |
| **官方明确可取** | 官方端点页明确给出所需接口、字段和最低积分；仍不代表当前账号已达到积分门槛 |
| **需权限或账号实测** | 接口存在，但需要单独权限，或目标代码、历史起点、最新一期、频率限制没有在文档中逐项承诺 |
| **只能派生** | TuShare 提供足够的原始字段，但目标指标必须由项目按冻结规则计算，TuShare 不直接发布该指标 |
| **无原生接口／外部补充** | 在当前 TuShare 官方接口导航和目标端点中没有发现语义匹配的结构化数据；应进入已认证官方直连和后续检索链 |

所有实际观测仍应保存：`observation_period`、原发布机构的 `release_at`、系统首次成功取得的 `available_at`、来源和内容哈希。TuShare 返回的统计期或交易日不能代替真实可用时点。

## 2. 结论摘要

### 2.1 可以把 TuShare 作为首选结构化入口的部分

- 股票和指数日线、A 股个股日线、复权因子、指数月度成分、股票及期货交易日历；因此中证全指价格和多数股票广度指标具备原料，但 `000985.CSI`、`399317.SZ`、`000906.CSI`、`000300.CSI` 的代码及完整历史仍要用当前账号验收。[指数日线](https://tushare.pro/document/2?doc_id=95) [A 股日线](https://tushare.pro/document/2?doc_id=27) [指数权重](https://tushare.pro/document/2?doc_id=96)
- `NHII.NH`、`NHCI.NH` 和多个南华单品种指数日线；期货合约、合约日线、主力映射、交易日历及仓单日报也有结构化端点。[南华指数日线](https://tushare.pro/document/2?doc_id=468) [期货日线](https://tushare.pro/document/2?doc_id=138) [主力映射](https://tushare.pro/document/2?doc_id=189) [仓单日报](https://tushare.pro/document/2?doc_id=140)
- `DR007.IB`：`repo_daily` 的官方样例明确包含 DR007，关键值为加权价 `weight`；这不是把交易所 `GC007/R-007` 冒充 DR007。[债券回购日行情](https://tushare.pro/document/2?doc_id=256)
- Shibor、LPR、M0/M1/M2、社融总量、GDP、CPI、PPI 和 PMI 均有原生端点。PMI 字段尤其完整，覆盖订单、生产、采购、原材料库存、产成品库存、购进价格、出厂价格和预期。[Shibor](https://tushare.pro/document/2?doc_id=149) [LPR](https://tushare.pro/document/2?doc_id=151) [货币供应量](https://tushare.pro/document/2?doc_id=242) [社融](https://tushare.pro/document/2?doc_id=310) [PMI](https://tushare.pro/document/2?doc_id=325)
- `cn_schedule` 可提供计划发布日期、发布机构及对应 TuShare API，适合生成 `next_expected_release`；它不提供实际入库时间，也不能证明“待上线”的数据接口已经存在。[经济数据发布日程](https://tushare.pro/document/2?doc_id=461)

### 2.2 当前账号最小验收栏

根任务在不回显 token 的前提下，另行完成了一轮最小 smoke test。下表只记录“这次调用是否成功”，不把成功调用扩张成历史完整性、授权再发布或未来稳定性的承诺；精确首日、缺口和限频仍需在实现任务中固化验收结果。

| 端点／目标 | 当前账号最小实测 | 对能力分类的影响 |
| --- | --- | --- |
| `trade_cal`, `daily`, `daily_basic`, `index_dailybasic` | 成功 | 交易日、个股行情和部分市场指标可进入实现；派生广度仍需点时股票池 |
| `index_daily('000985.CSI')` | 成功 | 中证全指由“代码待证”升级为“账号可调用”；完整历史和缺口仍待验收 |
| `index_daily('000012.SH')` | 成功 | 上证国债指数可作候选债券代理 |
| `fut_index_daily('NHII.NH'/'NHCI.NH')` | 成功 | 两个南华核心／宽基代码当前账号可调用；成分与历史连续性仍不是该调用能证明的事实 |
| `repo_daily('DR007.IB')` | 成功，取得 123 个交易日 | 足够当前 120 日窗口；不足以证明多年回测覆盖 |
| `shibor` | 成功，取得 124 个交易日 | 当前资金传导窗口可用；更长历史仍待验收 |
| `shibor_lpr` | 成功 | 必须按正式变化日去重，不把重复日值当新政策事件 |
| `cn_m`, `sf_month`, `cn_pmi`, `cn_ppi`, `cn_cpi`, `cn_gdp`, `cn_schedule` | 成功 | 当前账号可调用这些宏观端点；`cn_cpi` 仍没有核心 CPI 字段 |
| `fut_mapping` + `fut_daily` | 成功 | 可以开始认证本地连续合约规则；并不等于已有无跳点连续指数 |
| `fx_daily`, `margin`, `moneyflow_hsgt`, `etf_share_size` | 成功 | 可作解释与监控，不取得正式阶段投票权 |
| `yc_cb` | **无权限** | 中债收益率曲线必须进入单独权限或官方直连分支 |
| `fut_index_basic`, `index_moneyflow` | **接口名无效** | 不得把猜测的接口名写入实现；南华元数据与指数资金流需另找已文档化来源 |

### 2.3 不能只靠 TuShare 完成的部分

- **理想债券核心缺失**：TuShare 官方文档有中债国债收益率曲线 `yc_cb`，却没有明确的“中债－国债总指数总值财富／净价”原生端点。收益率曲线不能冒充债券总回报指数。[`yc_cb`](https://tushare.pro/document/2?doc_id=201)
- **新增的 `000012CNY030.CSI` 不是财富指数**：中证官方衍生指数接口把它列为“国债指数(全) / Government Bond Index (Full)”。中证计算细则明确，全价指数只计算“净价 + 应计利息”的样本市值；全收益指数还另外包含派息及再投资。因此 `(全)` 在这里是**全价**，不是全收益、财富或总回报。[中证官方衍生指数映射](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012&lang=zh_CN) [中证债券指数计算细则](https://www.sse.com.cn/market/sseindex/calculation/c/10803806/files/aa42d3a05d9e4fe19d6b3630b965de48.pdf)
- **政策行动缺失**：7 天逆回购政策利率、公开市场净投放、降准和其他政策行动没有与 `repo_daily` 同等明确的结构化指标端点；`monetary_policy` 是季度报告文本，不是及时政策事件流。[央行货币政策执行报告](https://tushare.pro/document/2?doc_id=465)
- **工业实体数据缺口明显**：工业增加值、产能利用率、工业利润、产成品存货金额、库存／营业收入和周转天数没有当前原生指标端点。`cn_schedule` 的 2026 年示例直接把“全国工业产能利用率”和“国民经济运行情况”等标为“待上线”。[经济数据发布日程](https://tushare.pro/document/2?doc_id=461)
- **核心 CPI 缺失**：`cn_cpi` 只有全国、城市、农村的总 CPI 值及环比、同比、累计值，没有扣除食品和能源的核心 CPI，也没有核心服务价格序列。[`cn_cpi`](https://tushare.pro/document/2?doc_id=228) 国家统计局会在正式解读中公布核心 CPI，因此应从国家统计局官方发布补充。[国家统计局对核心 CPI 的官方表述](https://www.stats.gov.cn/sj/sjjd/202601/t20260119_1962345.html)
- **信用结构不足**：`sf_month` 只有社融当月增量、累计增量和期末存量；企业中长期贷款、居民贷款、票据融资和政府债券等结构不能从该端点取得。严格的信用脉冲也不是原生字段。
- **外汇只覆盖海外交易商口径**：`fx_daily` 当前文档只支持 FXCM，示例为离岸 `USDCNH.FXCM`，且交易日按 GMT；它不是人民银行中间价或在岸 USD/CNY 官方收盘价。[外汇基础信息](https://tushare.pro/document/2?doc_id=178) [外汇日线](https://tushare.pro/document/2?doc_id=179)

## 3. 股票、债券、商品与市场广度矩阵

| 指标 | TuShare 接口 | 关键字段 | 频率 | 更新时间／真实可用时点 | 官方文档给出的历史覆盖 | 积分／单独权限 | 角色 | 能力结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 中证全指及交叉宽基价格 | `index_basic` + `index_daily` | `ts_code, trade_date, close, pre_close, pct_chg, vol, amount` | 交易日 | 指数行情官方权限页称交易日 15:00–17:00 更新；正式运行以首次成功抓取为 `available_at` | `index_daily` 权限页称“全部历史”，单个指数受自身发布日期和供应覆盖限制 | 2,000 分起 | **股票核心／验证** | **需账号实测**：接口明确存在；`000985.CSI` 等目标代码、首日、缺口与修订没有逐项承诺。[指数基础](https://tushare.pro/document/2?doc_id=94) [指数日线](https://tushare.pro/document/2?doc_id=95) |
| 股票交易日历 | `trade_cal` | `exchange, cal_date, is_open, pretrade_date` | 日历日 | 定期更新；下一交易日仍需在运行时校验 | 未承诺首年 | 2,000 分 | **治理** | **官方明确可取**。[交易日历](https://tushare.pro/document/2?doc_id=26) |
| 全市场上涨／下跌／平盘家数 | `daily` + `stock_basic` | `ts_code, trade_date, pct_chg`; `list_date, delist_date, list_status` | 交易日 | `daily` 交易日 15:00–16:00 入库；建议收盘批次完整后计算 | `daily` 权限页称全部历史；个股从上市起 | `daily` 基础积分；`stock_basic` 2,000 分 | **股票验证** | **只能派生**：按点时股票池统计 `pct_chg` 正负；TuShare没有原生“上涨家数”字段。[A股日线](https://tushare.pro/document/2?doc_id=27) [股票基础](https://tushare.pro/document/2?doc_id=25) |
| 成分股处于 120 日均线上方比例 | `index_weight` + `daily` + `adj_factor` | `index_code, con_code, trade_date, weight`; `close`; `adj_factor` | 日频结果；权重月频 | 行情 15:00–17:00；复权因子文档称盘前 9:15–9:20；必须使用当时可得的月度成分 | 权重页未承诺逐指数历史起点 | `index_weight` 2,000；`adj_factor` 2,000 起 | **股票验证** | **只能派生且需账号实测**：需验证中证全指权重历史是否完整。[指数权重](https://tushare.pro/document/2?doc_id=96) [复权因子](https://tushare.pro/document/2?doc_id=28) |
| 新高／新低和成交广度 | `daily` + `adj_factor`；可参考 `daily_info` | 复权 OHLC、`amount`; 市场 `amount, vol, com_count` | 交易日 | 收盘数据完整后本地计算 | 个股历史同 `daily`；`daily_info` 各板块起点不同，文档列示 1991–2019 年不等 | 2,000；`daily_info` 600 分 | **股票验证／解释** | **只能派生**。`daily_info` 只有市场总量，不提供新高新低或涨跌家数。[市场交易统计](https://tushare.pro/document/2?doc_id=215) |
| 上证国债指数 `000012.SH` | `index_daily` | 指数 OHLC、`close, pct_chg` | 交易日 | 15:00–17:00 窗口；按首次成功抓取冻结 | 指数自身自 2003 年发布，但 TuShare 未逐代码承诺完整覆盖 | 2,000 分起 | **债券首版代理／备用核心** | **需账号实测**：通用接口存在，不代表目标代码一定无缺口。[指数日线](https://tushare.pro/document/2?doc_id=95) [上交所债券指数说明](https://bond.sse.com.cn/market/indexv/indicies/) |
| `000012CNY030.CSI` 国债指数(全价) | `index_daily` | 指数 OHLC、`close, pct_chg` | 交易日 | 同指数日线 | 当前账号取得 152 个交易日，尚不足以回测多个周期 | 2,000 分起；当前账号成功 | **债券价格确认候选** | **账号可取，但不是财富／总回报**。中证官方把它映射为 `Government Bond Index (Full)`；全价只含净价与应计利息，不含派息再投资。[官方映射](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012&lang=zh_CN) [计算细则](https://www.sse.com.cn/market/sseindex/calculation/c/10803806/files/aa42d3a05d9e4fe19d6b3630b965de48.pdf) |
| `930916.CSI` 中证10年期国债指数 | `index_daily` | 指数 OHLC、`close, pct_chg` | 交易日 | 同指数日线 | 基日 2008-12-31，发布日 2016-12-05；TuShare账号可取，完整历史仍待验 | 2,000 分起；当前账号成功 | **债券期限确认** | **账号可取，但不是全期限国债核心**。官方样本只含同时在银行间和上交所挂牌、剩余期限 8.5–10 年的国债，当前事实单只有 7 只样本。[中证事实单](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/930916factsheet.pdf) |
| 中债－国债总指数财富／净价 | 当前文档未发现语义匹配端点 | 应需要日期、财富／净价点位、久期等 | 交易日 | 中债官方发布时点；TuShare 无可确认时点 | — | — | **理想债券核心** | **无原生接口／外部补充**。不能用 `yc_cb` 的收益率替代总回报价格。[中债指数查询](https://indices.chinabond.com.cn/cbweb-mn/indices/single_index_query?locale=zh_CN) |
| 中债国债收益率曲线、10Y | `yc_cb` | `trade_date, curve_type, curve_term, yield` | 交易日 | TuShare 未写具体入库时刻；中债官方曲线约盘后发布，系统以首次成功取得为准 | 端点页未承诺首日；样例含完整期限点 | **单独权限**，单次最多 2,000 | **债券方向验证** | **需单独权限与账号实测**。只可反向验证债券价格方向。[`yc_cb`](https://tushare.pro/document/2?doc_id=201) |
| 国债 ETF | `fund_daily` | `trade_date, close, pct_chg, vol, amount` | 交易日 | 每日收盘后 | 接口整体超过 10 年；单只基金受成立日限制 | 当前端点页 5,000 分；旧总表写 2,000，存在文档冲突 | **监控** | **需账号实测**，不得代替可得的债券价格核心。[ETF日线](https://tushare.pro/document/2?doc_id=127) |
| 南华工业品 `NHII.NH`、宽基 `NHCI.NH` | `fut_index_daily` | `trade_date, open, high, low, close, pre_close, pct_chg, vol, amount` | 交易日 | 官方权限表称每日盘后；真实完成时刻以首次成功抓取为准 | 南华指数接口整体“超过 10 年”，单个代码首日和缺口未承诺 | 2,000 分 | **商品核心／宽基验证** | **需账号实测**：端点代码表明确列出二者，但仍需验证完整历史、最新日与授权范围。[南华指数日线](https://tushare.pro/document/2?doc_id=468) [权限说明](https://tushare.pro/document/1?doc_id=108) |
| 七袖套南华单品种指数 | `fut_index_daily` | 同上 | 交易日 | 每日盘后 | 取决于品种上市及南华指数可用期 | 2,000 分 | **后备商品核心原料** | **部分官方明确、部分需实测**：当前代码表明确列出 `CU/RB/PP/CF/TA/RU/SP/SC/FU/BU.NH`；没有列出 `LU.NH`、`PG.NH`，后两者不能假定可用。[代码表](https://tushare.pro/document/2?doc_id=468) |
| 自建连续合约与换月映射 | `fut_basic` + `fut_daily` + `fut_mapping` + `fut_trade_cal` | 合约上市退市；OHLC/结算/持仓；`mapping_ts_code`; 交易日历 | 交易日 | 日线盘后；映射和日历精确入库时刻未说明 | 期货日线接口整体自 1996 年；单品种从上市起；映射首日未承诺 | 各 2,000 分 | **后备核心治理** | **只能派生且需实测**：映射端点不等于已完成回溯调整的连续收益序列，换月和跳空规则必须本地冻结。[合约信息](https://tushare.pro/document/2?doc_id=135) [期货日线](https://tushare.pro/document/2?doc_id=138) [主力映射](https://tushare.pro/document/2?doc_id=189) [期货日历](https://tushare.pro/document/2?doc_id=467) |
| 交易所注册仓单 | `fut_wsr` | `trade_date, symbol, warehouse, pre_vol, vol, change, unit, exchange` | 交易日 | 每日盘后 | 接口总体自 2006 年；单品种、交易所和单位连续性需实测 | 2,000 分 | **实物库存验证** | **官方明确可取，但只能代表注册仓单**；不能当作全社会库存。[仓单日报](https://tushare.pro/document/2?doc_id=140) [权限说明](https://tushare.pro/document/1?doc_id=108) |

## 4. 货币政策、资金市场、信用与外汇矩阵

| 指标 | TuShare 接口 | 关键字段 | 频率 | 更新时间／真实可用时点 | 官方文档给出的历史覆盖 | 积分／单独权限 | 角色 | 能力结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DR007 | `repo_daily`，查询 `ts_code='DR007.IB'` | `trade_date, repo_maturity, weight, amount, num`；主值用 `weight` | 交易日 | 端点未承诺 TuShare 入库时刻；市场日值发布后，以首次成功抓取为准 | 端点未承诺首日；官方样例证明 2020-08-04 可取 | 2,000 分 | **市场传导验证** | **官方明确可取，账号历史需实测**。样例同时列出 DR007、R007 和交易所 GC007，必须按代码隔离。[债券回购日行情](https://tushare.pro/document/2?doc_id=256) |
| Shibor 各期限 | `shibor` | `date, on, 1w, 2w, 1m, 3m, 6m, 9m, 1y` | 交易日 | 官方说明 11:00 发布；TuShare 权限表称每日 12:00 更新 | 自 2006 年 | 单页写 120 分、总权限表写 2,000 分，存在冲突 | **市场传导验证** | **官方明确可取**；当前账号已完成最小调用，实际限频仍待验收。[Shibor](https://tushare.pro/document/2?doc_id=149) [权限说明](https://tushare.pro/document/1?doc_id=108) |
| 7 天逆回购政策利率、公开市场净投放、降准 | 当前文档未发现指标型原生端点 | 应需要生效时点、操作期限、利率、数量、到期量、政策类型 | 事件／交易日 | 以人民银行真实公告为准 | — | — | **政策行动／领先观察** | **无原生接口／官方直连补充**。不能从 DR007 或新闻摘要反推出正式政策动作。 |
| LPR 1Y／5Y+ | `shibor_lpr` | `date, 1y, 5y` | **当前制度为月度发布** | TuShare 页面仍保留旧的“每交易日 11:30”描述和重复日值样例；中国货币网当前规则为每月 20 日（节假日顺延）9:00 发布，下一次发布前有效 | 权限页称自 2013 年；2019 年改革前后口径需分段 | 120 分 | **信用定价响应** | **官方明确可取但必须去重为发布事件**；不能把每日重复值当成每日新政策证据。[TuShare LPR](https://tushare.pro/document/2?doc_id=151) [中国货币网现行规则](https://www.chinamoney.com.cn/chinese/bklpr/?tab=2) |
| 央行货币政策执行报告 | `monetary_policy` | `pub_date, title, url, pdf_url, content_html` | 季度 | 实际报告发布日期 | 自 2001 年、每年四篇 | **单独权限** | **政策解释** | **需单独权限**；是滞后的报告文本，不是政策动作状态接口。[官方端点](https://tushare.pro/document/2?doc_id=465) |
| M0／M1／M2 | `cn_m` | 余额、`m0/m1/m2_yoy`、`*_mom` | 月度 | 按人民银行实际发布；TuShare未承诺精确入库时刻 | 未承诺首月 | 600 分 | **信用响应／验证** | **官方明确可取；最新期、修订和口径断点需账号与发布源校验**。[货币供应量](https://tushare.pro/document/2?doc_id=242) |
| 社融总量 | `sf_month` | `month, inc_month, inc_cumval, stk_endval` | 月度 | 按人民银行实际发布；TuShare未承诺精确入库时刻 | 端点样例至少覆盖至 2021 年；未承诺首月 | 2,000 分 | **信用响应／验证** | **官方明确可取**，但只有总量三字段。[社融月度](https://tushare.pro/document/2?doc_id=310) |
| 社融和贷款结构 | 当前指标导航未发现对应结构化端点 | 企业中长期贷款、居民贷款、票据、政府债券等 | 月度 | 人民银行实际发布 | — | — | **信用特征卡** | **无原生接口／外部补充**。`sf_month` 不能满足结构分析。 |
| 信用脉冲 | `sf_month` + `cn_gdp`，必要时外部结构数据 | 社融流量、存量、滚动名义 GDP | 月／季派生 | 只在两类输入均已发布后更新 | 受较短输入序列和修订影响 | 2,000 + 600 分 | **转折观察** | **只能派生**；TuShare 不发布唯一标准的 `credit_impulse`，必须冻结公式并保存输入版本。 |
| 离岸美元／人民币 | `fx_obasic` + `fx_daily` | `USDCNH.FXCM`; bid/ask OHLC、`tick_qty`, `trade_date` | 日频 | 每日更新，具体时刻未说明；日期为 GMT，必须转换并避免与北京时间错日 | 权限页称全部历史；代码实际首日需实测 | 2,000 分 | **外汇解释** | **官方明确可取为 FXCM 离岸报价**，不是中国官方汇率。[基础信息](https://tushare.pro/document/2?doc_id=178) [日线](https://tushare.pro/document/2?doc_id=179) |
| 在岸 USD/CNY、中间价、CFETS 人民币指数 | 当前外汇文档未发现相应官方口径端点 | 官方中间价、收盘价、指数点位 | 交易日 | 中国货币网／人民银行真实发布 | — | — | **外汇解释／政策压力** | **无原生接口／官方直连补充**。不能用 `USDCNH.FXCM` 静默替代。 |

## 5. PMI、库存、工业、通胀、GDP 与发布日历矩阵

| 指标 | TuShare 接口 | 关键字段 | 频率 | 更新时间／真实可用时点 | 官方文档给出的历史覆盖 | 积分／单独权限 | 角色 | 能力结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 制造业／非制造业／综合 PMI | `cn_pmi` | `month, pmi010000, pmi010400, pmi010500, pmi010900, pmi011000, pmi011100, pmi011500, pmi011600, pmi020100, pmi020200, pmi030000` | 月度 | 国家统计局计划日通常 9:30；TuShare未承诺入库时刻，以实际发布和首次抓取为准 | 未承诺首月；端点样例含 2023–2024 | **5,000 分** | **过热／需求观察与验证** | **官方明确可取，当前账号需验证积分**。[PMI](https://tushare.pro/document/2?doc_id=325) [国家统计局日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) |
| PMI 原材料和产成品库存 | `cn_pmi` | `pmi010700` 原材料库存、`pmi011400` 产成品库存、`pmi020900` 非制造业存货 | 月度 | 同 PMI | 同上 | 5,000 分 | **库存早期／同步特征卡** | **官方明确可取**；它是扩散指数，不是库存数量。 |
| 订单－库存差、生产－订单差 | `cn_pmi` | 新订单、生产、原材料库存、产成品库存 | 月度派生 | 仅在该期 PMI 正式发布后更新 | 同 `cn_pmi` | 5,000 分 | **库存转折观察** | **只能派生**；不得把差值伪装为官方发布指标。 |
| PMI 投入和出厂价格 | `cn_pmi` | `pmi011200, pmi011300, pmi020300, pmi020400` | 月度 | 同 PMI | 同 `cn_pmi` | 5,000 分 | **物价压力同步验证** | **官方明确可取**。 |
| 工业增加值 | 当前导航未发现原生端点；`cn_schedule` 对应“国民经济运行情况”为待上线 | 应需当月／累计同比及行业分项 | 月度 | 国家统计局日程约 10:00，实际页面为准 | — | — | **过热同步验证** | **无原生接口／官方直连补充**。[TuShare 日程端点](https://tushare.pro/document/2?doc_id=461) [国家统计局日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) |
| 工业产能利用率 | `cn_schedule` 示例明确标为“待上线” | 总体及行业利用率 | 季度 | 国家统计局季度发布日约 10:00 | — | — | **过热验证** | **无原生接口／官方直连补充**。[经济数据发布日程](https://tushare.pro/document/2?doc_id=461) |
| 工业企业利润／利润率 | 当前导航未发现宏观原生端点 | 利润总额、营业收入、成本、利润率；累计与单月估算 | 月度 | 国家统计局计划日通常 9:30 | — | — | **滞后确认** | **无原生接口／官方直连补充**。上市公司财务接口不能替代全国规模以上工业企业口径。[国家统计局日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) |
| 工业产成品存货、库销与周转 | 当前导航未发现宏观原生端点 | 产成品存货、营业收入／成本、产成品周转天数 | 月度 | 随工业经济效益报告 | — | — | **库存滞后确认** | **无原生接口／官方直连补充**。不能用期货仓单或 PMI 库存替代全国工业存货。 |
| CPI 总指数 | `cn_cpi` | 全国／城市／农村 `*_val, *_yoy, *_mom, *_accu` | 月度 | 国家统计局计划日 9:30；TuShare未承诺入库时刻 | 未承诺首月 | 600 分 | **物价压力确认** | **官方明确可取**。[CPI](https://tushare.pro/document/2?doc_id=228) [国家统计局日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) |
| 核心 CPI、服务价格 | `cn_cpi` 不含这些字段 | 扣除食品能源后的同比／环比、服务价格 | 月度 | 国家统计局 CPI 发布页及解读 | — | — | **消费端滞后确认** | **无原生接口／官方直连补充**。不能从总 CPI 精确反推核心 CPI。[CPI字段表](https://tushare.pro/document/2?doc_id=228) [国家统计局核心CPI表述](https://www.stats.gov.cn/sj/sjjd/202601/t20260119_1962345.html) |
| PPI 及生产／生活资料分项 | `cn_ppi` | `ppi_yoy, ppi_mom`; `ppi_mp_*`; 采掘／原料／加工；`ppi_cg_*` 及食品／衣着／日用品／耐用品 | 月度 | 国家统计局计划日 9:30；TuShare未承诺入库时刻 | 未承诺首月 | 600 分 | **物价压力验证／确认** | **官方明确可取**；字段丰富，但没有工业生产者购进价格的完整行业表。[PPI](https://tushare.pro/document/2?doc_id=245) |
| GDP 总量和三次产业 | `cn_gdp` | `quarter, gdp, gdp_yoy, pi/si/ti, *_yoy` | 季度 | 初步核算一般季后约 15 日；以国家统计局日程和实际发布为准 | 文档样例到 1952Q4；实际账号完整性和历史修订需实测 | 600 分 | **增长确认／信用脉冲分母** | **官方明确可取，但没有发布时点和 vintage 字段**。[GDP](https://tushare.pro/document/2?doc_id=227) [国家统计局核算说明](https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html) |
| 中国经济数据发布计划 | `cn_schedule` | `month, publish_date, title, issuing_org, data_api` | 持续更新的月度日历 | 只给计划日期，不给时间和实际到库时间；计划可能调整 | 未承诺历史首月 | 2,000 分 | **治理** | **官方明确可取为计划日历**，不能代替真实 `release_at/available_at`。[经济数据发布日程](https://tushare.pro/document/2?doc_id=461) |
| 真实发布时间、首次可用时间和数据版本 | 无单一 TuShare 端点 | 原页面发布时间、首次成功抓取、修订／vintage | 事件 | 由项目采集器记录 | 从项目启用后形成 | — | **治理** | **必须本地生成并配官方发布页**。国家统计局明确称年度日程为初步计划，届时可能调整。[2026 发布日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) |

## 6. 对本项目七张库存特征卡的实际覆盖

| 特征卡 | TuShare 可直接提供 | 仍需外部官方数据或派生 |
| --- | --- | --- |
| 订单－库存差 | PMI 新订单、原材料库存、产成品库存 | 差值由本地派生 |
| 原材料－产成品库存差 | 两个 PMI 库存扩散指数 | 差值由本地派生；不能解释为数量差 |
| 实际库存 | PPI 可作价格调整因子的一部分 | 工业产成品存货名义余额缺失；实际库存必须外补后派生 |
| 库销与周转 | 无宏观原生字段 | 工业营业收入／成本、库存比、周转天数外补或派生 |
| 价格－利润 | PMI 购进／出厂价、PPI | 工业利润、利润率缺失 |
| 产能 | PMI 生产和订单 | 工业增加值、产能利用率缺失 |
| 信用与实物库存 | M1/M2、社融总量、期货仓单 | 企业中长期贷款和广义产业实物库存缺失；信用脉冲本地派生 |

因此，TuShare 足以承担库存周期的**调查先行层**和一部分交易所实物验证，却不足以单独完成四象限的“实际库存、库销、利润、产能”确认层。

## 7. 文档不一致和口径陷阱

1. **端点存在不等于代码存在**：`index_daily` 能取指数，不代表 `000985.CSI`、`000012.SH` 的完整历史已经写入当前账号可见库；`fut_index_daily` 同理。
2. **DR007 可取，但必须用对代码**：`repo_daily` 同时返回交易所 `GC007/R-007`、银行间 `R007.IB` 和 `DR007.IB`。本项目的市场传导指标必须固定 `DR007.IB`，不能按“7天回购”中文模糊匹配。[回购日行情](https://tushare.pro/document/2?doc_id=256)
3. **LPR 文档含旧制度描述**：TuShare 页面仍写每日 11:30，并展示连续交易日重复值；现行官方制度是月度发布。入库时应只在数值的正式发布日期创建新观测，其他日期不重复投票。[中国货币网 LPR](https://www.chinamoney.com.cn/chinese/bklpr/?tab=2)
4. **总权限表可能滞后**：例如 `fund_daily` 当前端点页要求 5,000 分，而总权限表仍写 2,000；`index_dailybasic` 当前端点页写 2,000，总表写 4,000；`shibor` 单页写 120 分、总表写 2,000。实现不能把静态表格当成账号权限真值，应以账号 smoke test 和明确错误分类为准。[ETF日线](https://tushare.pro/document/2?doc_id=127) [大盘每日指标](https://tushare.pro/document/2?doc_id=128) [Shibor](https://tushare.pro/document/2?doc_id=149) [权限说明](https://tushare.pro/document/1?doc_id=108)
5. **南华总权限表接口名滞后**：总表把南华指数写作 `index_daily`，专用端点实际名为 `fut_index_daily`；实现应以端点页和 SDK 实测为准。[南华指数端点](https://tushare.pro/document/2?doc_id=468)
6. **连续合约映射不是连续收益率**：`fut_mapping` 只说明某日映射到哪个月合约，不提供换月收益拼接、回溯调整或展期处理字段。
7. **计划日期不等于真实可用时间**：`cn_schedule.publish_date` 只是一张持续更新的计划表。统计局也明确注明计划可能调整；程序必须记录首次成功取得时点。[国家统计局日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html)

## 8. 最小账号实测后仍待回答的问题

根任务的最小 smoke test 已证明多个目标端点对当前账号可调用，但一次成功调用不能回答以下问题。本研究工作流没有为追查这些问题读取 token：

1. 当前账号的准确积分、各端点实际限频和数据再发布边界；
2. `399317`、`000906`、`000300` 等交叉验证指数的规范代码、真实首日、缺口、重复值、最新交易日和历史修订；`000985.CSI` 虽已成功调用，仍需同样的完整性检查；
3. `000012.SH`、`000012CNY030.CSI` 和 `930916.CSI` 的完整历史与缺口；其中 `CNY030` 当前只取得 152 个交易日；
4. `NHII.NH`、`NHCI.NH` 及七袖套单品种指数的真实首日、连续性、最新日、成分漂移和授权边界；
5. `LU.NH`、`PG.NH` 是否已存在但尚未写入公开代码表；
6. `DR007.IB` 在当前 123 个交易日之前的历史、节假日前后覆盖和 TuShare 真实入库时刻；
7. `yc_cb` 当前已确认无权限；若未来开通，仍需验收政府债曲线、10Y 到期收益率和历史完整性；
8. `cn_pmi` 所有目标字段在早期月份是否都有值，以及 `cn_cpi/cn_ppi/cn_m/sf_month/cn_gdp` 的首期、修订方式和真实入库延迟；
9. `shibor_lpr` 在 2019 年改革后的重复日值方式、5Y 字段起始日与正式数值变化日；
10. `cn_schedule` 的历史范围、临时调整覆盖和“待上线”状态是否会追溯变化；
11. `fx_daily` 的最近连续性、GMT 日期规则和 FXCM 数据授权边界。

## 9. 建议的账号验收顺序

后续若用户授权测试，应通过安全注入的 token 在独立命令中只打印状态、行数、首末日期、缺口数和字段名，不打印 token 或完整数据：

1. **P0 核心价格**：`index_basic/index_daily` → `NHII.NH/NHCI.NH` → 单品种南华指数；
2. **P0 债券可用性**：`000012.SH` → `yc_cb` 权限；理想中债财富指数继续走官方直连；
3. **P1 政策传导**：`DR007.IB`、Shibor、LPR；
4. **P1 宏观**：PMI、CPI、PPI、M、社融、GDP、发布日历；
5. **P2 解释数据**：外汇、ETF、仓单和市场总量。

任何端点失败都必须分类为：`permission_denied`、`rate_limited`、`unsupported_code`、`not_yet_released`、`empty_coverage`、`source_failed` 或 `schema_changed`。不能把“无权限”“尚未发布”和“指标不存在”混成同一个空值。

## 10. 最终能力边界

TuShare 可以覆盖本项目大部分**价格核心、市场广度原料、资金市场传导、PMI、总量信用和价格指数**。最关键的正面发现是 `DR007.IB` 已有原生结构化行情，`NHII.NH` 也在官方代码表中；最关键的缺口则是**中债国债总财富／净价核心、正式政策行动、工业库存与利润／产能、核心 CPI 与服务价格、贷款结构和官方在岸汇率**。

因此，合理的第一版不是“所有指标都先 TuShare 再说”，而是：

```text
TuShare 原生端点
  ├─ 直接保存：核心价格、DR007、Shibor、PMI、CPI/PPI、M、社融总量、GDP
  ├─ 本地派生：广度、均线、新高新低、订单库存差、信用脉冲、连续合约
  └─ 官方外补：中债财富/净价、政策行动、工业实体库存/利润/产能、核心CPI、信用结构、在岸汇率
```

这既能最大化 TuShare 的结构化价值，也不会把“接口存在”“账号有权”“目标语义正确”和“数据已经发布”四件事混为一谈。
