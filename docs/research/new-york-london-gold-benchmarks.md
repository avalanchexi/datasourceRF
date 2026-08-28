# 纽约金与伦敦金：V1 标准口径、来源与点时规则

> 研究日期：2026-08-20  
> 范围：只使用 CME/COMEX、LBMA、ICE Benchmark Administration、TuShare 与圣路易斯联储的一手页面；未读取或调用任何密钥、付费账号或真实 API。本文只冻结“国际环境指标”的证据口径，不改变中国三资产核心状态、正式阶段或宏观确认。

## 结论

V1 应把用户所说的两项黄金价格拆成两个不可互换的规范指标：

| 页面名称 | 规范指标 | V1 原始值 | 结论 |
| --- | --- | --- | --- |
| 纽约金 | **COMEX Gold Futures (`GC`) 官方 active-month settlement** | 当日官方 active month 的结算价，USD/金衡盎司；同时保存实际年月合约 | 不用“成交最活跃/持仓最大主力连续”，不用收盘价或最后成交价冒充结算价 |
| 伦敦金 | **LBMA Gold Price PM (USD)** | 15:00 London auction 的最终美元基准价，USD/金衡盎司 | PM 为 V1 主序列；AM 是另一项 10:30 基准，不作静默后备 |

二者都是 P2 **国际环境指标**，用于解释避险、实际利率和全球风险偏好，不参与股票、债券或商品核心状态，不参与正式阶段投票。TuShare 当前没有这两个标准序列；`XAUUSD.FXCM` 不能替代其中任一项。

在来源许可和当前账号的 120 日历史、最新值、时点与字段验收完成前，两项均显示 `awaiting_source_certification`，不显示代理值。

## 1. 纽约金：COMEX `GC` 官方 active-month settlement

### 1.1 为什么选择它

COMEX Gold Futures 的产品代码为 `GC`，报价为美元/金衡盎司，标准合约规模为 100 金衡盎司。[CME Gold Futures 合约规格](https://www.cmegroup.com/markets/metals/precious/gold.contractSpecs.html)

CME 的黄金日结算程序把 **active month** 作为先行定价合约：正常情况下根据 CME Globex 在 13:29:00–13:30:00 ET 的成交计算，第一层规则为该窗口成交的 VWAP，缺少成交时再依次采用最近成交、买卖盘与前结算等规则；其他月份还会使用价差关系定价。2026 年生效版本列出的基准月份为 2、4、6、8、10、12 月；active month 是非当前交割月中最近的基准合约。[CME 2026 Gold Futures 日结算程序](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/06/ser-9637r.pdf)

因此 V1 的“纽约金”不是以下任一概念：

- 交易商给出的 `GC1!`、`GC=F` 等连续代码；
- 当天成交量或持仓量最大的“主力合约”；
- GC 的最后成交、收盘价、盘中价或 CFD；
- CME 的 Asia/London marker 或其他黄金参考率。

这些序列的选约、换月或观察时点都与 CME 的 official active-month settlement 不同。

### 1.2 原始记录与连续化

规范名称建议为 `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT`。每条原始记录至少保存：

- `trade_date`：CME 交易日；
- `contract_code`、`contract_month`：当天实际被选中的年月合约；
- `settlement`，单位 `USD/ozt`；
- `settlement_rule_version`、`roll_effective_date`；
- `source`, `release_at`, `available_at`, `retrieved_at`, `content_hash`。

“active month”规则可能修订，历史选择必须使用当时生效的 CME 日结算程序和 First Position Date/spot-month 规则，不能拿今天的月份表回算全部历史。

跨合约直接拼接结算价会把期限结构和持有成本造成的价差误当成黄金涨跌。V1 应同时保留两种对象：

1. **官方原始结算价**：逐日保存实际合约，不调整，页面明确标注换月；
2. **项目派生的换月中性收益指数**：非换月日用同一合约结算价收益；换月日用新合约自身相邻两日结算价，或用新旧合约同日重叠价差做回调。公式和版本必须冻结，名称中写 `roll_adjusted`，不得称为“CME 官方连续价”。

纽约金的方向图和 120 日变化使用派生收益指数；最新点位卡仍展示实际 active-month 合约及官方结算价。这样既避免换月跳空污染趋势，又保留可核对的交易所原值。

### 1.3 发布时间、API 与授权

CME 说明，结算值在计算前后会进入其许可的实时市场数据渠道；延迟渠道约在初始发布 10 分钟后提供。公开产品页直到 **midnight CT** 才免费显示结算数据。DataMine 可以通过 flat file、API、SFTP 或文件浏览器交付；DataMine API 只访问账号已获授权的文件。[CME Settlement Data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html) [CME DataMine API](https://www.cmegroup.com/datamine/datamine-api.html) [CME 市场数据许可](https://www.cmegroup.com/market-data/license-data.html)

关于 midnight CT 文件，官方材料存在必须在账号验收中消解的边界：2023/2024 迁移公告把 midnight settlement files 描述为 free of charge；当前 Settlement Data FAQ 同时把 DataMine End of Market 的机器交付列为订阅/许可产品并列出费用。故 V1 不能从“网页午夜免费查看”推导出“匿名免费历史 API”。[CME 结算文件迁移公告](https://www.cmegroup.com/notices/clearing/2023/09/Chadv23-272.html) [CME Settlement Data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)

适合个人本地 V1 的合规顺序为：

1. **首选**：订阅 CME DataMine 的 COMEX settlement/End of Market 数据，或使用 CME 授权经销商中明确包含 `GC` official settlement 与历史的个人许可；
2. 只保存本地私用所需的 120 中国交易日覆盖和必要预热，遵守具体合同的缓存、展示和派生数据条款；
3. 上线前实测账号是否能取 `comex.settle`/对应数据集的最近至少 120 中国交易日覆盖、actual contract、settlement 和发布时间；
4. 若尚未完成订阅、许可与实测，状态为 `awaiting_source_certification`。公开网页可人工核对，但不据此假定允许自动抓取、缓存或批量历史回填。

## 2. 伦敦金：LBMA Gold Price PM (USD)

### 2.1 PM 而不是 AM

IBA 为 spot、unallocated、loco London gold 运行电子竞价；两场竞价分别在 10:30 和 15:00 London time **开始**，最终美元价格分别发布为 **LBMA Gold Price AM** 和 **LBMA Gold Price PM**。竞价轮数可变，不能把 15:00 当成保证到分钟的最终发布时间。美元是竞价形成货币，GBP/EUR 值是换算/结算参考而非直接竞价结果。[ICE Developer Portal：LBMA Gold Price](https://developer.ice.com/fixed-income-data-services/catalog/lbma-gold-price) [LBMA 每日竞价说明](https://www.lbma.org.uk/prices-and-data/about-lbma-daily-auction-prices)

V1 选择 PM，原因是它是同一伦敦营业日中更晚、更接近日终的标准基准，适合作为每日国际环境观察。规范名称建议为 `LBMA_GOLD_PRICE_PM_USD_OZT`。

AM 不是 PM 的缺失值后备。若 PM 因周末、英国银行假日或来源问题没有发布，保持上一条观测并显示来源日期和新鲜度；不要把 AM 填入 PM 字段。LBMA 明确说明周末和英国银行假日不发布这些基准。[LBMA Precious Metal Prices](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices)

### 2.2 与泛 `XAU/USD spot` 的区别

`LBMA Gold Price PM` 是 IBA 管理、在规定时点由电子竞价形成的单一受监管基准，标的是伦敦交割的非分配黄金。泛称 `XAU/USD spot` 的日线则必须依赖具体交易商、数据商、买卖方向、截点和时区；它没有自动等同于 15:00 LBMA auction final price。

TuShare 的 `XAUUSD.FXCM` 尤其不能称“伦敦金”：TuShare 官方页说明海外外汇/金属当前只有 **FXCM 交易商**，其日线返回 `bid_open/bid_close/bid_high/bid_low`，交易日按 GMT；它没有 LBMA 的 `AM/PM` auction 字段。[TuShare 海外外汇基础信息](https://tushare.pro/document/2?doc_id=178) [TuShare 外汇日线](https://tushare.pro/document/2?doc_id=179)

### 2.3 历史、API 与授权

LBMA 已把历史表移到 MyLBMA Portal，并明确要求持有 IBA 相关许可；ICE 目录列出的正式交付方式包括 ICE Connect、ICE Data API、ICE Data Files 和 ICE Global Network。LBMA Gold Price 的 IBA 口径历史从 2015 年 3 月开始，足够覆盖 V1 的 120 日窗口，但“历史足够长”不等于“有权自动取得和保存”。[LBMA 历史表与许可说明](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices) [ICE Developer Portal：LBMA Gold Price](https://developer.ice.com/fixed-income-data-services/catalog/lbma-gold-price)

IBA 提供实时、4 小时延迟和 London midnight 延迟档；使用、估值或再分发的具体许可必须以 IBA 合同为准。[ICE/IBA Licensing & Data](https://www.ice.com/iba/licensing) [LBMA Gold Price FAQ](https://www.lbma.org.uk/prices-and-data/lbma-gold-price/lbma-gold-price)

圣路易斯联储 FRED 不能作为当前免费后备：FRED 已于 2022-01-31 删除 IBA 的 LBMA Gold/Silver Price 数据；即使 FRED 提供第三方序列，其 API 条款也不会覆盖原数据所有者的版权或许可要求。[FRED 删除 IBA 数据公告](https://news.research.stlouisfed.org/2022/01/ice-benchmark-administration-ltd-iba-data-to-be-removed-from-fred/) [FRED API 条款](https://fred.stlouisfed.org/docs/api/terms_of_use.html)

适合个人本地 V1 的合规方案是：从 IBA 或其授权再分发商取得明确包含 `LBMA Gold Price PM USD`、历史访问、本地缓存和私有展示的许可，再接入相应 API/file feed。许可与账号实测完成前显示 `awaiting_source_certification`；不抓取登录门户、不从搜索摘要回填，也不以 FXCM 报价静默替代。

## 3. TuShare 原生能力结论

结论为 **两项均无原生标准序列**，不是“有数据但名字不同”：

- TuShare `fut_basic`/`fut_daily` 的官方交易所参数是中国期货交易所集合，没有 COMEX；因此不能取得 GC 年月合约的 COMEX 官方 settlement。[TuShare 期货合约信息](https://tushare.pro/document/2?doc_id=135) [TuShare 期货日线](https://tushare.pro/document/2?doc_id=138)
- TuShare `fx_obasic`/`fx_daily` 当前只有 FXCM；`XAUUSD` 是 FXCM 金属报价，不含 LBMA AM/PM 基准标识，也不含 COMEX 合约与 settlement。[TuShare 海外外汇基础信息](https://tushare.pro/document/2?doc_id=178) [TuShare 外汇日线](https://tushare.pro/document/2?doc_id=179)

所以检索降级链在这两项上应从“TuShare 无语义匹配”直接进入**已认证官方/授权直连**，不能把 TuShare 的 FXCM 结果当成成功命中。

## 4. 120 中国交易日窗口与无前视对齐

### 4.1 时区事实

- COMEX active-month settlement 的计算窗口止于 13:30 `America/New_York`，即北京时间次日约 01:30（美国夏令时）或 02:30（冬令时）；公开网页/midnight-CT 档约在北京时间次日 13:00 或 14:00 才到达。具体到达时间以来源实测为准。[CME 2026 Gold Futures 日结算程序](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/06/ser-9637r.pdf) [CME Settlement Data FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)
- LBMA PM auction 于 15:00 `Europe/London` 开始，即北京时间约 22:00（英国夏令时）或 23:00（冬令时）；midnight-London 延迟档约为次日北京时间 07:00 或 08:00。[ICE Developer Portal：LBMA Gold Price](https://developer.ice.com/fixed-income-data-services/catalog/lbma-gold-price)

代码必须使用 IANA 时区 `America/New_York`、`America/Chicago`、`Europe/London` 和 `Asia/Shanghai`，不得全年硬编码固定 UTC 偏移。

### 4.2 V1 选择规则

对每个中国交易日盘后报告 `R`：

1. 先由中国交易所日历确定最近 120 个中国交易日的首尾日期 `[D-119, D]`；国际指标不需要恰好有 120 条，也不按中国日期伪造观测。
2. 报告截止点 `report_cutoff` 使用带时区时间戳。只允许 `available_at <= report_cutoff` 的观测进入证据包；`available_at` 取系统首次成功取得合格数据的真实时间，不能用预定竞价/结算时刻倒填。
3. COMEX 通常使用上一个美国交易日、但已在中国报告截止前到达的 official settlement；保留 CME `trade_date` 和实际合约。
4. LBMA 通常使用上一个伦敦营业日、但已在截止前到达的 Gold Price PM；保留 LBMA pricing date。中国 15:00 盘后不能使用尚未举行的当日 London PM auction。
5. 页面在中国交易日网格上可做 `as-of` 展示，但只携带“最近已可用值 + 原始观察日 + 年龄”；不得插值、把休市日复制成新证据，或把中美英日期改写成同一天。
6. 若最新值超过各自预期日历一个完整开放日仍未到达，标 `stale`；来源未授权/未通过历史和字段验收则标 `awaiting_source_certification`，二者不得降级到 FXCM。

## 5. 可直接写入 V1 指标目录的冻结建议

| 字段 | 纽约金 | 伦敦金 |
| --- | --- | --- |
| canonical name | `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | `LBMA_GOLD_PRICE_PM_USD_OZT` |
| priority / role | P2 / 国际环境解释 | P2 / 国际环境解释 |
| frequency | COMEX 交易日 | London pricing day |
| unit | USD/ozt | USD/ozt |
| raw value | actual `GC` contract official settlement | LBMA Gold Price PM final USD auction price |
| main source | CME DataMine/许可市场数据渠道 | IBA/授权再分发商 |
| fallback | 另一条已认证且同口径的 CME 授权渠道 | 另一条已认证且同口径的 IBA 授权渠道 |
| forbidden substitute | OI/volume 主力连续、last/close、CFD | LBMA AM、泛 XAU/USD、`XAUUSD.FXCM` |
| state before certification | `awaiting_source_certification` | `awaiting_source_certification` |
| stage effect | 无 | 无 |

上线认证还需两次最小账号验收，本文未替用户完成：一是 CME 渠道能否按许可自动取回 `GC` 结算、实际合约和至少 120 中国交易日覆盖；二是 IBA/经销商许可是否明确允许取得、缓存并在个人本地页面展示 LBMA Gold Price PM 历史。验收只记录字段、首末日、缺口、延迟和许可编号，不记录凭据。
