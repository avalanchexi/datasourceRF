# Pring 周期驾驶舱 V1 指标目录

> 状态：冻结候选版；由 Wayfinder 决策票“冻结 V1 指标目录与证据角色”产生。  
> 证据窗口：最近120个中国交易日的起止日期。日频按各自市场日历取窗口内观测；月频、季频只取窗口覆盖月份或季度中截至报告时点已经可得的观测及必要比较基线。  
> 边界：只有三个中国核心价格状态能形成正式 Pring 阶段；P1/P2 永不投票改写阶段。

## 1. 目录合约

每个生产指标定义必须实现以下字段：

```text
metric_id, canonical_name, display_name, priority, evidence_role,
frequency, calendar, unit, raw_fields, formula_version,
primary_source, fallback_policy, release_rule, available_at_rule,
stale_rule, source_certification_status, page_contract, stage_effect
```

优先级：

- `P0`：交易日历、三类核心价格和正式状态所必需；缺失时不生成新阶段。
- `P1`：转折观察、政策/库存/过热/物价特征和宏观确认；缺失必须披露，但不阻塞正式阶段。
- `P2`：国内或国际解释背景；失败到 Exa 为止，不进入 AI WebSearch，也不阻塞驾驶舱。

证据角色：

- `core_barometer`：唯一能决定对应核心资产状态。
- `price_confirmation`：交叉确认价格趋势，不参与核心状态投票。
- `transition_watch`：提示转折方向，不形成正式阶段。
- `macro_confirmation`：已发布数据对周期叙事的事后支持或冲突。
- `signature_card`：库存、过热、物价、政策或信用特征。
- `international_context`：全球利率、风险偏好、能源和避险背景，只解释。
- `governance`：日历、发布、时点、版本和来源治理。

## 2. 通用时点和新鲜度规则

| 规则 | 适用 | `available_at` | `stale_after` |
| --- | --- | --- | --- |
| `CN_DAILY_CLOSE` | 中国指数、股票、期货 | 本系统在收盘后首次取得并通过完整性校验的时间 | 下一中国交易日预期完成时间仍无新值 |
| `CN_T_PLUS_1` | 融资、ETF等次日数据 | 对应数据实际入库并通过校验的时间 | 对应交易日后第二个中国交易日仍无值 |
| `SCHEDULED_MACRO` | NBS CPI/PPI/PMI/工业/GDP等 | 官方首发HTML/XLSX成功解析时间；计划日期不能代替 | 实际/计划发布后一个工作日仍未取得；计划变更则更新日历 |
| `PBC_UNSCHEDULED` | 社融、信贷、政策公告 | 官方页面真实发布时间与首次合格取得时间分别保存 | 超过指标目录的历史发布窗口仍无新值，转人工核验 |
| `FOREIGN_DAILY` | 美国、伦敦及EIA日频 | 源市场已完成且本系统实际取得的时间 | 超过一个完整源市场开放日仍无新值 |
| `EVENT` | 降准、政策制度变化 | 公告时间与生效时间分别保存 | 不前填为每日新事件；监控失败显示源状态 |

尚未发布时继续展示上一期并标记 `awaiting_release`。来源尚未通过语义、历史、字段、授权与许可验收时使用 `awaiting_source_certification`，不得用相似代理填值。

## 3. 治理指标

| `metric_id` | 名称 | P/角色 | 来源与字段 | 频率/时点 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_TRADE_CALENDAR` | 中国交易日历 | P0/governance | TuShare `trade_cal`: `cal_date,is_open,pretrade_date` | 日历；官方日历变更生成版本 | 发布日历；决定120日窗口，不投票 |
| `CN_RELEASE_SCHEDULE` | 中国经济数据计划日历 | P1/governance | TuShare `cn_schedule` + NBS/PBOC官方日程 | 持续更新；只生成`next_expected_release` | 发布日历；不能代替`release_at` |
| `SOURCE_OBSERVED_AVAILABILITY` | 来源真实可用时点 | P0/governance | 本地采集日志：`release_at,available_at,fetched_at,content_hash,vintage` | 每次取得 | 所有详情页；防止前视 |

## 4. 三类核心价格与正式趋势输入

所有核心价格保存原始OHLC、源交易日、价格口径和数据质量；30日观察、120日正式轨道及12个月代理由资产趋势模块按独立规则版本派生。本目录不把窗口收益率直接等同于牛熊状态。

| `metric_id` | 名称 | P/角色 | 主来源 | 原始值/单位 | 降级与状态 | 页面与阶段影响 |
| --- | --- | --- | --- | --- | --- | --- |
| `CN_EQUITY_CORE_000985` | 中证全指 | P0/core_barometer | TuShare `index_daily`, `000985.CSI` | `open,high,low,close,pre_close`; 指数点 | 同口径官方源可认证；不得运行时换指数 | 首页/股票详情；唯一决定股票状态 |
| `CN_BOND_CORE_000012` | 上证国债指数 | P0/core_barometer | TuShare `index_daily`, `000012.SH` | 收盘指数点；债券价格方向 | 源失败时留空；未来财富指数只能新模型版本迁移 | 首页/债券详情；唯一决定债券状态 |
| `CN_COMMODITY_CORE_NHII` | 南华工业品指数 | P0/core_barometer | TuShare `fut_index_daily`, `NHII.NH` | 收盘指数点 | 当前与2018-06-01后严格校准区间已认证无`LH`；未来年度/临调失败时仅以新模型版本认证后备，不逐日切换 | 首页/商品详情；唯一决定商品状态 |

每个核心序列派生并版本化：`price_return_30d`、`price_return_120d`、`ma_position`、`trend_slope`、`candidate_state`、`stable_state`、`transition_pending`、月末12个月代理。精确持续期、滞回和斜率公式由“校准120日趋势状态机与稳定性门槛”票冻结。

## 5. 股票确认与市场广度

| `metric_id` | 名称 | P/角色 | 来源/公式 | 频率 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_EQ_CSI300` | 沪深300 | P1/price_confirmation | `index_daily`, `000300.SH` | CN_DAILY_CLOSE | 股票详情；不投票 |
| `CN_EQ_CSI500` | 中证500 | P1/price_confirmation | `index_daily`, `000905.SH` | CN_DAILY_CLOSE | 股票详情；不投票 |
| `CN_EQ_CSI1000` | 中证1000 | P1/price_confirmation | `index_daily`, `000852.SH` | CN_DAILY_CLOSE | 股票详情；不投票 |
| `CN_EQ_ADV_DEC` | 上涨/下跌/平盘家数与涨跌差 | P1/transition_watch | `daily(trade_date)`；按点时上市状态聚合；`adv-dec` | CN_DAILY_CLOSE | 股票广度卡 |
| `CN_EQ_AD_RATIO` | 涨跌比 | P1/transition_watch | `adv / max(dec,1)`；分母为零单独标记 | CN_DAILY_CLOSE | 股票广度卡 |
| `CN_EQ_NEW_HIGH_LOW_120` | 120日新高/新低家数 | P1/transition_watch | 每只股票当前复权价与自身过去120个交易日范围比较 | CN_DAILY_CLOSE；允许窗口前预热 | 股票广度卡 |
| `CN_EQ_ABOVE_MA120` | 120日均线上方股票比例 | P1/transition_watch | `count(close>MA120)/eligible_count`；使用点时股票池 | CN_DAILY_CLOSE；需要预热 | 股票广度卡 |
| `CN_EQ_ADV_AMOUNT_SHARE` | 上涨股票成交额占比 | P1/transition_watch | `sum(amount where pct_chg>0)/sum(amount)` | CN_DAILY_CLOSE | 成交扩散卡 |
| `CN_MARGIN_BALANCE` | 融资余额与融资买入额 | P1/transition_watch | TuShare `margin`，按交易所汇总；亿元 | CN_T_PLUS_1 | 股票风险偏好卡；不投票 |
| `CN_INDEX_VALUATION` | 主要指数PE/PB/股息率/换手率 | P2/解释 | `index_dailybasic`，仅沪深300/中证500/中证1000实际支持字段 | CN_DAILY_CLOSE | 股票估值详情；不投票 |

广度输出只保留最近120个中国交易日；原始个股数据允许读取计算首日所需预热期。十年全市场广度明确不属于V1。

## 6. 债券、政策行动、市场传导与信用定价

| `metric_id` | 名称 | P/角色 | 来源/字段或公式 | 频率/时点 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_BOND_FULL_PRICE_CNY030` | 国债全价指数 | P1/price_confirmation | `index_daily`, `000012CNY030.CSI` | CN_DAILY_CLOSE | 债券详情；不是财富/总回报 |
| `CN_BOND_10Y_930916` | 中证10年国债指数 | P1/price_confirmation | `index_daily`, `930916.CSI` | CN_DAILY_CLOSE | 债券详情；只代表8.5–10年期限 |
| `CN_DR007` | 银行间DR007加权利率 | P1/市场传导 | `repo_daily`, `DR007.IB`, `weight`; % | 交易日，实际入库 | 政策方向卡；不是政策行动 |
| `CN_OMO_7D_RATE` | 7天逆回购操作利率 | P1/政策行动 | PBOC OMO公告：操作日、期限、利率 | EVENT | 政策行动时间线 |
| `CN_OMO_7D_AMOUNT` | 7天逆回购操作量/到期/净投放 | P1/政策行动 | PBOC公告；净投放由认证操作账本派生；亿元 | 操作日 | 政策行动卡 |
| `CN_DR007_POLICY_SPREAD` | DR007－7天逆回购利差 | P1/transition_watch | `DR007 - OMO_7D_RATE`; bp | 两输入都可得后 | 市场传导卡 |
| `CN_SHIBOR_ON_1W_3M` | Shibor隔夜/1周/3月 | P1/市场传导 | TuShare `shibor`: `on,1w,3m`; % | 官方11:00后，首次取得 | 市场传导卡 |
| `CN_LPR_1Y_5Y` | LPR 1年/5年以上 | P1/信用定价响应 | `shibor_lpr`或CFETS官方；只保存正式发布变化，不重复日值 | 月度9:00发布后 | 信用响应卡；不称央行操作 |
| `CN_RRR_EVENT` | 降准/升准事件 | P1/政策行动 | PBOC公告：`announced_at,effective_date,change_pp,scope` | EVENT | 政策时间线；不压成统一每日水平 |
| `CN_TOOL_LIQUIDITY_MONTHLY` | 央行各工具月度投放 | P1/政策行动 | PBOC月表：投放、回笼、净投放；亿元 | 月度PBC_UNSCHEDULED | 政策行动卡；2025-06前不伪造全工具序列 |

`yc_cb`当前账号无权限，不是V1上线条件；以后取得的收益率曲线只可作反向方向确认，不能替换债券价格核心。

## 7. 商品核心确认、后备篮子与仓单

| `metric_id` | 名称 | P/角色 | 来源/公式 | 频率 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_COMMODITY_BROAD_NHCI` | 南华商品指数 | P1/price_confirmation | `fut_index_daily`, `NHCI.NH` | CN_DAILY_CLOSE | 商品详情；不投票 |
| `CN_COMMODITY_EX_HOG_BASKET` | 七袖套去生猪篮子 | P0条件后备/或P1确认 | CU、RB、PP、CF/TA、RU、SP、SC；固定权重13⅓%×6+SC20%；连续收益按模型版本 | CN_DAILY_CLOSE | NHII认证失败时只能通过新模型版本成为核心 |
| `CN_COMMODITY_SLEEVE_CONTRIBUTION` | 七袖套贡献 | P2/解释 | 各袖套版本化收益×固定权重 | CN_DAILY_CLOSE | 商品贡献分解；若篮子为核心不得再次验证 |
| `CN_FUTURES_WARRANTS` | 交易所注册仓单 | P1/signature_card | TuShare `fut_wsr`: `symbol,warehouse,pre_vol,vol,change,unit,exchange`；白名单限七袖套相关品种 | CN_DAILY_CLOSE | 实物库存卡；必须称注册仓单，不称产业总库存 |

明确排除：生猪`LH`、黄金、燃料油`FU`、低硫燃料油`LU`、沥青`BU`、LPG`PG`。原油`SC`是唯一能源袖套。若自建篮子成为正式核心，其成分、袖套广度和贡献只能解释，不能用来确认自身。

## 8. PMI、库存、过热与物价白名单

| `metric_id` | 名称/字段 | P/角色 | 来源 | 频率/时点 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_PMI_ACTIVITY` | 制造业PMI、新订单、生产、采购量 | P1/transition_watch+signature_card | TuShare `cn_pmi`白名单字段 | 月度SCHEDULED_MACRO | 过热/库存卡 |
| `CN_PMI_INVENTORY` | 原材料库存、产成品库存 | P1/signature_card | `cn_pmi` | 月度 | 库存卡；扩散指数，不是库存数量 |
| `CN_PMI_PRICES` | 购进价格、出厂价格 | P1/signature_card | `cn_pmi` | 月度 | 物价压力卡 |
| `CN_ORDER_INVENTORY_SPREAD` | 新订单－原材料库存、新订单－产成品库存 | P1/transition_watch | PMI同一期差值；公式版本化 | 月度，PMI发布后 | 库存转折卡；明确标派生 |
| `CN_PRODUCTION_ORDER_SPREAD` | 生产－新订单 | P1/signature_card | PMI同一期差值 | 月度 | 被动累库/去库解释 |
| `CN_CPI_HEADLINE` | 全国CPI环比、同比、累计平均 | P1/macro_confirmation | TuShare `cn_cpi`; % | 月度SCHEDULED_MACRO | 物价压力卡 |
| `CN_CORE_CPI` | 核心CPI环比、同比、累计平均同比 | P1/macro_confirmation | NBS正式表“不包括食品和能源” | 月度9:30首发后 | 消费端滞后确认；不能反推 |
| `CN_PPI` | PPI总项、生产资料、生活资料环比/同比 | P1/signature_card+macro_confirmation | TuShare `cn_ppi`; % | 月度SCHEDULED_MACRO | 上游到消费传导卡 |
| `CN_INDUSTRIAL_VA` | 工业增加值当月/累计实际同比、季调环比 | P1/signature_card | NBS工业生产HTML/XLSX | 月度；1月不伪造单月 | 过热与增长卡；季调值保留vintage |
| `CN_INDUSTRIAL_FINANCE` | 利润、营业收入、成本累计值及官方同比 | P1/macro_confirmation | NBS工业利润HTML/XLSX | 月度PBC_UNSCHEDULED式真实发布 | 利润/成本卡；不得用两期金额重算官方同比 |
| `CN_FINISHED_GOODS_INVENTORY` | 产成品存货余额、官方可比同比 | P1/signature_card | NBS工业利润表 | 月末/月度 | 名义库存卡；不称实物库存 |
| `CN_INVENTORY_TURNOVER` | 产成品周转天数及同比变化 | P1/signature_card | NBS工业利润表 | 月末/月度 | 库销与周转卡 |
| `CN_CAPACITY_UTILIZATION` | 工业产能利用率及同比百分点 | P1/signature_card | NBS季度表 | 季度SCHEDULED_MACRO | 过热/产能卡；2017Q1起，不前造季度值 |

细行业PMI、CPI、PPI、利润和产能分项不进入V1主页面；只在来源解析所需白名单或后续模型版本中增加。

## 9. 货币、社融、贷款结构与增长

| `metric_id` | 名称 | P/角色 | 来源/公式 | 频率 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_M1_M2` | M1/M2余额、同比、环比 | P1/信用响应 | TuShare `cn_m` | 月度PBC_UNSCHEDULED | 信用响应卡 |
| `CN_SF_TOTAL` | 社融当月增量、累计增量、期末存量 | P1/信用响应 | TuShare `sf_month` | 月度 | 信用响应卡 |
| `CN_SF_COMPONENTS` | 人民币贷款、政府债、企业债、表外融资等主要分项 | P1/signature_card | PBOC社融增量/存量官方表 | 月度 | 信用结构卡；保存口径版本 |
| `CN_LOAN_STRUCTURE` | 居民/企业短期、中长期贷款和票据融资 | P1/signature_card | PBOC人民币信贷收支表；月末存量 | 月度 | 信用结构卡；增量由同口径存量派生 |
| `CN_CREDIT_IMPULSE` | 信用脉冲 | P1/transition_watch | 社融流量相对滚动名义GDP的变化；最终年化、窗口和分母vintage由公式版本冻结 | 月/季输入齐备后 | 信用转折卡；不称官方指标 |
| `CN_GDP` | GDP总量/同比及三次产业 | P2/宏观背景 | TuShare `cn_gdp` | 季度SCHEDULED_MACRO | 背景与信用脉冲分母；不每日投票 |

## 10. 汇率与国内P2解释

| `metric_id` | 名称 | P/角色 | 来源 | 频率 | 页面与影响 |
| --- | --- | --- | --- | --- | --- |
| `CN_USDCNY_CENTRAL_PARITY` | USD/CNY官方中间价 | P2/解释 | PBOC镜像CFETS公告；人民币元/美元 | 工作日9:15后 | 外汇压力卡；不称在岸收盘价 |
| `CN_USDCNH_FXCM` | FXCM离岸USD/CNH报价 | P2/解释 | TuShare `fx_daily`, `USDCNH.FXCM`; GMT bid OHLC | FOREIGN_DAILY | 外汇压力卡；明确离岸和交易商口径 |
| `CN_USDCNY_CLOSE_1630` | USD/CNY 16:30在岸收盘价 | P2/解释 | 仅CFETS持牌源 | 日频 | 未授权时`awaiting_source_certification`；禁止中间价/CNH替代 |

沪深港通、ETF份额和更广泛估值字段保留在候选附录，不参与V1股票验证；以后纳入必须经过模型版本变更。

## 11. 国际环境指标

这些指标全部为P2 `international_context`。中国盘后报告只使用`available_at <= report_cutoff`且已经完整发布的最近一期；通常是前一美国或伦敦营业日。不得使用盘中值、按中国日期前填成新证据或改变中国三资产状态。

| `metric_id` | 标准名称 | 主来源/原始字段 | 单位/频率 | 来源状态与禁止替代 | 页面 |
| --- | --- | --- | --- | --- | --- |
| `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | 纽约金：COMEX GC活跃月官方日结算 | CME许可渠道：实际`contract_month,settlement`; 项目另建换月中性收益序列 | USD/ozt；COMEX交易日 | `awaiting_source_certification`；禁止FXCM、成交量主力、last/close冒充 | 国际环境/避险 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | 伦敦金：LBMA Gold Price PM | IBA/授权源：PM最终美元拍卖价 | USD/ozt；London pricing day | `awaiting_source_certification`；AM不是后备，禁止泛XAU/USD替代 | 国际环境/避险 |
| `EIA_BRENT_RBRTE` | Brent Europe现货 | EIA `RBRTE` | USD/bbl；日频 | 官方直连接入；TuShare/FXCM油价停更，不得替代 | 国际能源/通胀 |
| `EIA_WTI_RWTC` | Cushing WTI现货 | EIA `RWTC` | USD/bbl；日频 | Brent辅助，不与其平均成一个油价 | 国际能源/通胀 |
| `UST10Y_NOMINAL_YIELD` | 美国10年期国债名义收益率 | TuShare `us_tycr.y10` | %；美国工作日 | 已通过当前账号最小实测；是收益率，不是债券价格 | 全球利率 |
| `UST2Y_NOMINAL_YIELD` | 美国2年期国债名义收益率 | TuShare `us_tycr.y2` | %；美国工作日 | 同上 | 全球利率 |
| `UST_2S10S_SPREAD` | 美债10Y－2Y期限利差 | `y10-y2` | bp；两输入可得后 | 项目派生；曲线倒挂不等于单独阶段 | 全球利率 |
| `CBOE_VIX_INDEX` | Cboe现金VIX指数 | Cboe官方日OHLC | 指数点；美国交易日 | TuShare不可取；官方适配器认证前`awaiting_source_certification`，禁止VOLX期货CFD | 全球风险偏好 |
| `NASDAQ_SOX_INDEX` | Nasdaq PHLX半导体指数 | Nasdaq官方指数历史 | 指数点；美国交易日 | 接口/授权验收前`awaiting_source_certification`；禁止SOXX/SMH/IXIC替代 | 全球科技周期 |

## 12. 候选附录与明确排除

以下项目不进入V1正式目录或主页面：

- 沪深港通资金流、ETF份额、全球宽基股指、新闻情绪和未经角色审核的新TuShare字段。
- `yc_cb`（当前账号无权限）；未来只能作为债券收益率方向确认。
- CFETS 16:30收盘价在未授权前没有数值，但其冻结定义保留在目录。
- `XAUUSD.FXCM`、`USOil.FXCM`、`UKOil.FXCM`；它们不能替代纽约金、伦敦金或EIA油价，且两条油价已停更。
- 生猪、国内黄金、FU/LU/BU/PG，以及更细商品内部燃料观察。
- 细行业宏观分项、贷款投向自然语言长尾、把PMI库存称作库存数量、把名义产成品存货称作实物库存。

## 13. 降级、页面和阶段影响总则

1. 主来源不可用时，只允许使用已认证且**同语义、同单位、同时间口径**的后备来源；不做不同指标之间的静默替换。
2. P0失败：`current_stage`不产生新值，保留`last_confirmed_stage`并披露核心缺口。
3. P1失败：转折观察或特征卡显示缺失/源失败，正式阶段照常由有效核心价格产生。
4. P2失败：国际或解释卡显示缺口，不触发AI WebSearch，不阻塞页面与报告。
5. 同一原始观测可承担多个动态角色，但只保存一次；角色变化引用同一`evidence_observation_id`。
6. 月季值不按交易日复制成新票；页面as-of展示上一已发布值时保留原统计期、发布日期和年龄。
7. 公式、来源或核心代理变化生成新的`metric_definition_version`或`model_version`，不得覆盖历史快照。

## 14. 来源依据

- [TuShare指标能力审计](../../../docs/research/tushare-indicator-capability-audit.md)
- [官方缺口数据源审计](../../../docs/research/official-gap-source-audit.md)
- [纽约金与伦敦金标准口径](../../../docs/research/new-york-london-gold-benchmarks.md)
- [股票核心代理](../../../docs/research/china-equity-core-proxy.md)
- [债券核心代理](../../../docs/research/china-bond-core-proxy.md)
- [商品核心代理](../../../docs/research/china-commodity-core-proxy.md)
- [库存与通胀敏感商品篮子](../../../docs/research/china-inventory-inflation-sensitive-commodity-basket.md)
