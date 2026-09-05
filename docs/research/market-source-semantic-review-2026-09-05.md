# P1 市场渠道官方语义与样本复核

> 复核日期：2026-09-05，Asia/Shanghai。最后核对时点：16:20。
> 范围：`_TUSHARE_MARKET_P1` 的 15 项指标、5 个 Schema family。
> 方法：读取领域上下文、ADR-0013、现有研究及适配器；查阅 TuShare 和发布机构的一手资料；匿名读取官方公开 JSON、XLS、PDF 并对响应原始字节计算 SHA-256。没有读取凭据、调用账户 API、变更数据库或激活模型。
> 产物边界：本次只写本文件。下列官方响应在内存中读取，未作为原始附件落盘；哈希是已实际读取字节的摘要，不是已经进入运行时认证包的证明。

## 1. 当前裁决

**本轮取得了可供认证使用的真实官方样本，但尚不能把整个市场包标记为认证完成。** 沪深 300、中证 500、中证 1000、930916、NHCI、沪深融资汇总和上期所合约日行情都有明确样本；CNY030 的身份及全价语义已核实，当前查询未取得其官方日线点位。广度和商品袖套是项目派生值，没有可以冒充其发布机构的“官方广度值”或“官方七袖套指数”。估值端点明确由 TuShare 社区计算，不能仅凭字段名相同认定它等于中证官方口径。

本文件遵循 [ADR-0013](../adr/0013-tushare-delivery-with-official-sampling.md)：**官方抽样用于认证交付渠道的语义与字段，不要求每条正式日观测都具备第二来源。** 一个已认证 family 可以继续通过 TuShare 交付；未解决的 family 必须保持 `awaiting_source_certification`。取得样本、样本比较通过、历史质量通过、发布时间证据通过和许可范围通过是不同检查，不能互相替代。

检查时的 [tushare_context.py](../../src/pring_cycle/tushare_context.py) SHA-256 为 `266e3f2f3fa3b26ca48f3cb697174c06fd76fa9432c7a9c2ad540d97f224e7b0`。下文“当前代码”均指该版本；本轮其他工作可能继续修改适配器。

## 2. 指标、字段和 family 的精确映射

| Family | Metric ID | 当前交付与字段 | 规范单位／维度 | 认证所需的官方锚点与当前裁决 |
|---|---|---|---|---|
| `market_indices` | `CN_EQ_CSI300` | `index_daily(000300.SH).close` | `index_points`；`source_code` | 中证 `000300` 收盘点位；已取同日官方样本 |
| `market_indices` | `CN_EQ_CSI500` | `index_daily(000905.SH).close` | 同上 | 中证 `000905` 收盘点位；已取同日官方样本 |
| `market_indices` | `CN_EQ_CSI1000` | `index_daily(000852.SH).close` | 同上 | 中证 `000852` 收盘点位；已取同日官方样本 |
| `market_indices` | `CN_BOND_FULL_PRICE_CNY030` | `index_daily(000012CNY030.CSI).close` | 同上 | 国债指数全价系列；身份与方法可证，官方点位样本仍缺 |
| `market_indices` | `CN_BOND_10Y_930916` | `index_daily(930916.CSI).close` | 同上 | 中证 10 年期国债指数；已取同日官方样本 |
| `market_indices` | `CN_COMMODITY_BROAD_NHCI` | `fut_index_daily(NHCI.NH).close` | 同上 | 南华综合指数 NHCI；已取官方日报样本，不能套用 NHII 的无生猪范围结论 |
| `market_breadth` | `CN_EQ_ADV_DEC` | `daily.pct_chg` 正、负、零及净家数 | `count`；`measure, universe` | 原始日线、当日股票池和冻结计数规则；派生结果无独立官方发布者 |
| `market_breadth` | `CN_EQ_AD_RATIO` | `advances / max(declines, 1)` | `ratio`；同上 | 零分母处理是项目规则，需单独验收，不能称官方涨跌比 |
| `market_breadth` | `CN_EQ_NEW_HIGH_LOW_120` | 连乘日涨跌幅后，最近 120 条有效观测的最高／最低 | `count`；同上 | 当前为每只股票 120 条交易观测，不自动等于最近 120 个市场交易日 |
| `market_breadth` | `CN_EQ_ABOVE_MA120` | 连乘价格高于最近 120 条均值的比例 | `percent`；同上 | 资格分母、停牌、上市不足 120 日、除权规则均需冻结 |
| `market_breadth` | `CN_EQ_ADV_AMOUNT_SHARE` | 上涨股票 `amount` / 所有有效股票 `amount` × 100 | `percent`；同上 | 日成交额和盘后成交额边界需冻结，不能自行补入官方未映射字段 |
| `margin_financing` | `CN_MARGIN_BALANCE` | `margin.rzye`、`margin.rzmre` 求和后除以 1e8 | `hundred_million_cny`；`financing_balance`、`financing_buy_amount`，`scope` | SSE、SZSE 两地汇总字段均已取得；覆盖和发布时间有代码缺口 |
| `index_valuation` | `CN_INDEX_VALUATION` | 3 个指数的 `index_dailybasic.pe,pb,turnover_rate` | `multiple` 或 `percent`；`index, measure` | TuShare 自算口径，PE/PB/换手率算法及 CSI1000 支持仍需补证 |
| `commodity_basket` | `CN_COMMODITY_EX_HOG_BASKET` | 8 个连续代码 `fut_daily.close/pre_close-1` 加权累计 | `index_points`；`formula_version` | 交易所发布月合约价格，不发布本项目连续合约拼接和袖套指数；尚未认证 |
| `commodity_basket` | `CN_COMMODITY_SLEEVE_CONTRIBUTION` | 袖套权重 × 日收益 × 100 | `percentage_points`；`formula_version,sleeve` | 同上；可认证冻结公式及输入血缘，不能用南华 NHII 方法代为证明 |

代码入口：`MARKET_INDEX_IDENTITIES`、`VALUATION_INDEX_CODES`、`FUTURES_SLEEVE_CODES`、`market_indices()`、`market_breadth()`、`margin_financing()`、`index_valuation()`、`commodity_basket()`；认证范围见 [source_certification.py](../../src/pring_cycle/source_certification.py)。TuShare 字段定义分别见 [指数日线](https://tushare.pro/document/2?doc_id=95)、[A 股日线](https://tushare.pro/document/2?doc_id=27)、[融资汇总](https://tushare.pro/document/2?doc_id=58)、[指数每日指标](https://tushare.pro/document/2?doc_id=128)、[期货日线](https://tushare.pro/document/2?doc_id=138)、[南华日线](https://tushare.pro/document/2?doc_id=468)。

## 3. 实际取得的官方样本及原始字节摘要

以下链接直接指向本次实际读取的官方响应。历史请求参数不代表文件不可变；以后重取若哈希不同，应保留新的 vintage，不能覆盖旧证据。

| 编号 | 官方响应与格式 | 交易／观察日期 | 本次字节数 | SHA-256 |
|---|---|---|---:|---|
| S1 | [中证 CSI300 日线 JSON](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000300&startDate=20260828&endDate=20260828&lang=zh_CN) | 2026-08-28 | 392 | `bf7a94b4c16e7028e0f52c3cc76f471d6bf38764b1b43fd978c9f320f4640993` |
| S2 | [中证 CSI500 日线 JSON](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000905&startDate=20260828&endDate=20260828&lang=zh_CN) | 2026-08-28 | 408 | `3ee5ded6b49016d283c332a4b9d419c3e11de9cb060c3e68f1d73acdacef9127` |
| S3 | [中证 CSI1000 日线 JSON](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000852&startDate=20260828&endDate=20260828&lang=zh_CN) | 2026-08-28 | 398 | `5dbec25a4c40fe81ad1b8e2be562167ef36c128676cc98a9718b08b06dae5c93` |
| S4 | [中证 930916 日线 JSON](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=930916&startDate=20260828&endDate=20260828&lang=zh_CN) | 2026-08-28 | 418 | `7ee3df45a061a9e882e238d10b8a0ed5c43818a4fb831a73dc44cf914c6022b8` |
| S5 | [南华商品指数日报 PDF，表 1](https://www.nanhua.net/cmsbigfile/2026/01/5fa372e8-12bb-4fe9-ad3f-7b088acebc58/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260122.pdf) | 2026-01-22 | 1,202,499 | `a40999baf0d448e55fd07d431544e8f7bb68ddee0bc9b95a49927e03ba6d2d05` |
| S6 | [上交所融资汇总及明细 XLS](https://www.sse.com.cn/market/dealingdata/overview/margin/a/rzrqjygk20260828.xls) | 2026-08-28 | 480,768 | `f08df98c68e6ab89538af45beedfe08b6bd1a29cfd9a30acf99c2f89d5ed94ac` |
| S7 | [上交所融资汇总 JSON](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260828&endDate=20260828&isPagination=false) | 2026-08-28 | 804 | `fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed` |
| S8 | [深交所融资汇总 JSON，tab1](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-08-28&tab1PAGENO=1) | 2026-08-28 | 8,383 | `c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277` |
| S9 | [上期所日行情 DAT，JSON 编码](https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260828.dat) | 2026-08-28 | 123,009 | `09820b4ff6132309da7ac0690519e5108cf4b429bbbd27ee10989524135f3ae3` |
| M1 | [中证国债衍生系列身份 JSON](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012&lang=zh_CN) | 元数据，无日线统计期 | 358 | `0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8` |
| M2 | [上期所品种配置 DAT，JSON 编码](https://www.shfe.com.cn/data/config/product_config.dat) | 当前元数据 | 59,147 | `99906f7461e5a4078839e2e14112830e88a3d5c2371cc9ecf86863d0c7f8784c` |

S1—S4 的 API 路由由[中证官网当前应用脚本](https://www.csindex.com.cn/static/js/app.5663471f.js)的 `stockIndexQuotes` 和 `/csindex-home` 请求前缀定位；S6—S7 由[上交所页面脚本](https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_otherData_2021.js)的 `RZRQ_HZ_INFO` 和 XLS 下载路径定位。S8 的 `1837_xxpl` 来自[深交所融资交易页面](https://www.szse.cn/disclosure/margin/margin/index.html)的 `data-s-catalog-id`，返回元数据再次确认了日期、字段和单位。S9、M2 路径来自[上期所官方 API 路由脚本](https://www.shfe.com.cn/images/api.js)。这些公开网站后台接口未承诺为稳定外部 API，应保留来源页面、响应类型和字段校验。

M1、M2 只能计入语义／身份材料，不能冒充数值抽样。S5 在 ADR-0013 的 2026-03-09 起始认证窗口之前，可以证明 NHCI 字段含义并用于同日抽样，但不能证明 120 日窗口内覆盖完整。所有 S 编号样本尚未与本账户 TuShare 同日响应进行比对。

## 4. Market indices：收盘身份可证，时间与 CNY030 点位仍缺

S1—S4 均有明确的 `tradeDate,indexCode,indexNameCnAll,close`；2026-08-28 官方 `close` 分别为 CSI300 **4609.18**、CSI500 **7895.45**、CSI1000 **7705.03**、930916 **184.59**，均为点位。对比 TuShare 时先绑定指数本体和日期，再按官方展示精度规定误差；不能把中证 API 的纯代码直接同 TuShare `.SH/.CSI` 字符串比较。TuShare 本身要求从 `index_basic` 取得代码身份，不支持仅凭后缀猜测。[TuShare 指数日线说明](https://tushare.pro/document/2?doc_id=95)

中证[930916 基本信息](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/930916?lang=zh_CN)明确其样本为同时在银行间和上交所挂牌、剩余期限 8.5—10 年的国债。它是期限确认序列，不是全期限国债集合；S4 当日 `consNumber=8`，不应沿用旧事实单中的 7 只样本描述。

M1 把 `000012CNY030` 明确列为国债指数的全价派生系列。[中证债券指数计算与维护细则 V4.0](https://www.sse.com.cn/market/sseindex/calculation/c/10803806/files/aa42d3a05d9e4fe19d6b3630b965de48.pdf)第 3.1.4、3.1.7 节区分全收益和全价：全价含净价及应计利息，全收益另含派息及再投资。因此不能把 CNY030 称为财富或总回报指数。本次 `index-perf` 查询 CNY030 的 2026-08-28 和 2026-03-09—2026-09-04 区间均返回成功但空数组；`index-perf-teshu` 同日也为空。**空数组不是值为零，不证明系列不存在，也不能完成抽样。** 原有 CSI factsheet PDF 地址在此次直接读取中多次超时，未将旧缓存 PDF 当作本次新取得附件。

S5 表 1 明确 `NHCI` 当日收盘 **2754.30**、前收盘 **2734.17**，同表 `NHII` 收盘为 **3624.02**。这直接证明两个序列不能混用。现有 [NHII 成分与方法研究](nhii-historical-constituents-and-methods.md)核验的是工业品核心，其“不含生猪”结论不覆盖 NHCI。NHCI 作为宽基确认值应绑定自己的指数身份和方法版本。[南华日线代码及字段](https://tushare.pro/document/2?doc_id=468)

当前 `market_indices()` 统一写 `release_at=trade_date 15:30`，但日线样本的 `tradeDate` 只代表交易日。中证日线响应没有真实首次公开时间，南华日报日期也不能自行变成 15:30 发布事实。中证细则只确认收盘指数通常逐交易日发布，没有保证这一统一时刻。应按实际发布证据给 `public_available_at`；只有可信发布日期时遵循 `CONTEXT.md` 的次日本地日边界，无可靠日期则为空。系统第一次成功校验时间仍独立记录为 `available_at`。

## 5. Market breadth：认证原料与冻结规则，不能寻找虚构官方成品

[TuShare daily](https://tushare.pro/document/2?doc_id=27)明确日线未复权、停牌时不返回记录，`pct_chg` 基于除权后的前收盘价，`amount` 以千元计。页面新增的 `ah_amount` 自 2026-07-06 起提供盘后成交额，但没有在本次证据中充分解释它与 `amount` 是否包含关系；当前项目不取 `ah_amount`，不能宣称已覆盖全部盘后成交。

当前 `universe=point_in_time_traded_a_shares` 实际表示“当天 API 返回且 `pct_chg,amount` 有效的记录”。它不等于所有上市 A 股、某个官方指数成分股或独立验证过的完整股票池。适配器未读取[股票基础信息](https://tushare.pro/document/2?doc_id=25)、[历史每日股票列表](https://tushare.pro/document/1?doc_id=262)或交易所历史证券名单来核验代码资格及漏行；返回行数非零不足以排除截断和部分市场缺失。

需绑定以下冻结输入／规则，才可能认证 5 个广度指标：

1. 样本范围：沪深或沪深北、A 股／存托凭证、ST、新股、停牌、退市、无成交、无效字段及重复代码如何处理；按交易日保存股票池内容哈希。
2. 原始日线：保存日批次行数、唯一代码、市场覆盖、`pct_chg` 除权语义和 `amount` 单位；至少取得交易所原始证券行情及名册的代表性样本，覆盖普通日、除权日和停复牌边界。本轮没有取得这套完整股票样本与点时名册，保持未认证。
3. 120 日定义：当前 deque 累积 120 条个股有效行情，停牌日不会入队；它可能跨越超过 120 个市场交易日。需要明确指标合同是 120 条个股交易观测还是固定 120 日窗口。不能把二者静默视为同义。
4. 新高低算法：当前由四舍五入后的 `pct_chg` 连乘构造归一化价格，再比较含当日的最高／最低，平顶／平底可重复计数；这与用精确复权收盘价或“严格突破此前 120 日”不同。MA 分母也只含已积累满窗口的当日有效股票。
5. AD 比：`declines=0` 时当前用 1 代替零分母，是可审计的项目政策，但应由指标定义明确；“无下跌股”不是一个实际下跌股。

这些是从适配器直接得到的工程判断，不是交易所对项目派生指标的背书。认证包应保存原料官方样本、TuShare 同日原料、点时股票池、公式版本及派生输入血缘；无需给每个派生广度结果配一个不存在的官方相等值。

## 6. Margin financing：沪深字段已闭合，覆盖与发布时间需修复

S6 第一张表的前两列直接写明融资余额和融资买入额以元计；对应 S7 为 `rzye,rzmre`。S8 `tab1` 的字段为 `jrrzye,jrrzmr`，表头单位是**亿元**，并带 `metadata.subname=2026-08-28`：

| 交易所 | 日期 | 官方融资余额 | 官方融资买入额 | 官方单位／精度 |
|---|---|---:|---:|---|
| SSE | 2026-08-28 | 1,342,943,855,079 | 94,338,686,041 | 元，整数 |
| SZSE | 2026-08-28 | 12,789.73 | 954.31 | 亿元，两位小数 |

TuShare 的 `rzye,rzmre` 均以元交付，项目除以 1e8 转为亿元，转换方向正确。**深交所官方展示经两位小数舍入，比较应采用不超过半个最小显示单位的精度容差，而不是元级相等**：采用普通四舍五入时边界为 0.005 亿元；若上游具体舍入规则未知，应记录该假设并复核边界样本。SSE 可用元级比较。禁止把 `rzrqye` 两融总余额映射成 `rzye` 融资余额。[TuShare margin](https://tushare.pro/document/2?doc_id=58)

[SSE 汇总说明](https://www.sse.com.cn/market/othersdata/margin/sum/)与 S8 footer 均确认汇总包含调出标的范围后的余额，深交所注明该边界自 2014-09-22 实施。因此当前标的证券明细求和不是等价替代源。统计来自券商报送，不应把该来源描述为独立逐笔交易实时余额。

当前代码只检查返回交易所集合是 `{SSE,SZSE,BSE}` 的子集，漏掉任一市场仍可输出 `scope=all_exchanges`；同一日期／交易所重复行也会再次相加。需要精确约定预期集合并校验每个成员恰好一次。若合同为沪深总量，则明确 `SSE+SZSE`；若合同为沪深北总量，则另补 BSE 官方样本、该市场适用起点及完整性证据。本次沪深样本不能授权将 BSE 缺失当作零。

发布时间不能采用当前的 `trade_date + 1 calendar day 00:00`。TuShare 官方说明交易所通常次日上午约 08:30 更新、渠道最晚约 09:05 完成，深交所及北交所周五数据到次周一上午更新；[深交所 2023 业务指南第六章](https://docs.static.szse.cn/www/lawrules/service/member/W020230901534859402978.pdf)要求每交易日开市前披露前一交易日信息。上述时刻描述是正常发布窗口，**不是每份历史响应的实际发布时间**。特别是 2026-08-28 为周五，不能把深市数据公开时间写成周六凌晨；应使用真实发布证据，或明确标记保守点时规则及它的证明边界。

## 7. Index valuation：不能用中证价格样本认证 TuShare 自算估值

[TuShare index_dailybasic](https://tushare.pro/document/2?doc_id=128)明确来源为社区统计计算；页面区分 `pe`、`pe_ttm`、`pb`、`turnover_rate`、`turnover_rate_f`。示例确有 `000300.SH`、`000905.SH`，但描述与样例不完全一致，且未逐项保证 `000852.SH`。当前代码只取 `pe`，不是 `pe_ttm`；若某字段为空就跳过，可能把缺少 PB 或整个指数的半套结果当成成功。

本次亦取得[中证官方历史估值字段响应](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000300&startDate=20260828&endDate=20260828&lang=zh_CN)：139 bytes，SHA-256 `dbd08f3b7bd029a085d3b29303774e9ff396547fd45f30333232c2ca4218ca85`，返回 2026-08-28、沪深 300、`peg=14.42`。**本轮未确认 `peg` 对应的正式中文表头及完整算法，不能擅自把它映射成 TuShare `pe`，更不能当成 PB 或换手率证据。** S1 中也出现同字段，不改变这个限制。

完成本 family 仍需：确认 3 指数实际历史覆盖；PE 使用静态年报还是 TTM、亏损公司及负净资产处理、财报公开时点、聚合权重和分母；PB 净资产口径；换手率基于流通股本还是自由流通股本、单位是百分数还是比值；取得各字段官方样本及与 TuShare 算法差异的审查。若最终采用 TuShare 自算指标，应在指标定义中如实命名并冻结方法，不应仅通过放宽数字误差将它标为中证官方同口径交付。当前统一 15:30 也无发布证据。

## 8. Commodity basket：真实月合约行情可以抽样，连续收益尚未认证

S9 的 `report_date=20260828`、`update_date=20260828 15:34:05`；该时刻是此响应声明的更新时间，不是已证明的首次发布时刻。`o_curinstrument` 包含月合约行情：

| 月合约 | `CLOSEPRICE` 收盘 | `SETTLEMENTPRICE` 结算字段 | `PRESETTLEMENTPRICE` 前结算 | 原始计价 |
|---|---:|---:|---:|---|
| CU2609 | 109,240 | 109,010 | 108,760 | 元／吨 |
| CU2610 | 108,900 | 108,620 | 108,390 | 元／吨 |

[官方日行情页面](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/)把 `CLOSEPRICE` 标为收盘价、`PRESETTLEMENTPRICE` 标为前结算，`SETTLEMENTPRICE` 页面列名为结算参考价，并说明显示交易期数后为结算后数据。S9 含期数元数据。M2 明确 CU、RB、RU、SP 为人民币／吨，SC 为人民币／桶；合约乘数分别为 5、10、10、10、1000，不能把乘数乘入单位价格后再同 TuShare 原价比较。

TuShare [fut_daily](https://tushare.pro/document/2?doc_id=138)分列 `pre_close,pre_settle,close,settle`；金额以万元、数量以手交付。S9 可对齐真实月合约 `settle/pre_settle`，但其月合约行不含独立前收盘字段，不能用前结算假充 `pre_close`。[fut_mapping](https://tushare.pro/document/2?doc_id=189)提供连续代码与实际月份合约的日期映射，文档没有保证连续代码已采用某种后复权收益或无跳点规则。

当前 7 袖套为 CU、RB、PP、CF/TA 等权子组合、RU、SP、SC；除原油 1/5 外，其余 6 袖套各 2/15。代码直接消费 `CU.SHF,RB.SHF,PP.DCE,CF.ZCE,TA.ZCE,RU.SHF,SP.SHF,SC.INE` 的 `close/pre_close`，没有保存 `fut_mapping`、实际持有月合约、展期日或结算价输入。这是本项目定义的派生篮子；交易所只发布实际合约行情，不能从 S9 推出其连续拼接规则正确。

还需解决的代码合同包括：选择收盘收益或结算收益且全链一致；换月信号何时可知、持仓如何转换、跨月价差如何处理、交易成本是否包括；按真实合约身份保存原始行情和映射哈希；PP/CF/TA 对应的大商所／郑商所官方原始行情及单位样本；各品种交易日并集／交集及缺口政策。当前只取 8 序列日期交集，会丢掉任何单品种缺失日；用交集数量达到阈值不能证明目标交易日覆盖。

另一个复现问题是当前每次从传入区间首日重新设基数 1000 并累计，再截取最后 `output_days`：改变查询起日会改变同一交易日指数绝对值。需固定基日／锚点和最小预热合同；袖套贡献则需保存每个输入收益与权重血缘。这些差异应产生新的公式／模型版本，不能改写已发布历史。

[南华 2025 编制细则](https://www.nanhua.net/cmsbigfile/2025/05/a3eb91a3-d6fc-4d71-b652-d55a60e0b10d/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E2%80%94%E2%80%94%E7%BC%96%E5%88%B6%E7%BB%86%E5%88%99%282025%29.pdf)约束南华指数本身，不是上述项目袖套的官方规则。无需试图让每个派生袖套数值等于南华成品指数；应验证冻结公式与其可追踪输入。

## 9. 许可与认证包落地边界

[TuShare 数据服务协议](https://tushare.pro/document/1?doc_id=405)第二节提供个人、不可转让、非商业、可撤销且有期限的使用许可，并限制账户分享；第三方服务可能有独立使用规定。它支持 ADR-0013 约定的本地个人使用边界，不支持把数据批量向外再分发。此次没有查阅账户专属合同或期限，不能把公开协议摘要写成“已验证本账户所有上游授权”。

南华细则限制未经授权发布和商业使用；其公开条款不构成对本项目公开发布的授权。上期所日行情栏目的使用声明说明数据准确性与完整性责任边界，并未在该页面给予无条件再分发许可。官方站点公开可读取只证明样本来源和可访问性。应把来源署名、`private_local_noncommercial`、禁止未授权再分发及另有许可的例外绑定到具体渠道；本次没有扩大使用范围。[南华方法及发布条款](https://www.nanhua.net/cmsbigfile/2025/05/a3eb91a3-d6fc-4d71-b652-d55a60e0b10d/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E2%80%94%E2%80%94%E7%BC%96%E5%88%B6%E7%BB%86%E5%88%99%282025%29.pdf)、[上期所日行情使用声明](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/)

| Family | 本轮已经补齐 | 仍阻止认证完成的证据／行为 |
|---|---|---|
| `market_indices` | 四个中证官方日值、NHCI 日报、CNY030 身份和全价方法 | CNY030 数值样本；同日渠道比较；具体代码历史覆盖；真实／保守公开时间证据；渠道许可验收 |
| `market_breadth` | 原始字段、停牌及除权语义，现有派生算法核对 | 官方日线与点时股票池样本；缺行完整性；固定 120 日定义、边界政策和输入血缘 |
| `margin_financing` | 沪深同日原始样本、单位、汇总范围、发布窗口 | 预期交易所集合、缺失／重复拒绝、BSE 如需纳入的证据；同日渠道比較；不能提前到次日零点 |
| `index_valuation` | 自算来源及字段区分已确认 | PE/PB/换手率具体算法及单位、三指数覆盖、可比官方样本、发布时间 |
| `commodity_basket` | 上期所真实月合约价、结算／前结算和单位样本 | DCE/ZCE 样本；连续映射／展期／基点合同；缺日规则、派生血缘和发布时间 |

认证时应把实际原始附件落入项目允许的不可变证据存储，记录来源 URL、抓取时点、真实发布日期证据、字节哈希、字段／单位／身份映射、抽样结果和审查文件哈希。**不能只把本研究文件的哈希填入 `official_sample_hashes`，也不能把 M1/M2 或成功但空数组的响应算作数值抽样通过。** 若任一 family 尚未闭合，认证创建或正式切换必须拒绝；已有代码运行成功、页面非空和烟雾测试成功不改变这一状态。
