**结论：现有 61 个指标已经具备普林格正式阶段识别所需的三资产骨架。22 项缺失需求不应整体升级为接入清单。** 最有价值的增量，是验证债券代理、补齐融资价格传导，以及约束“商品上涨就是需求恢复”等容易出错的解释。

建议首批新增不超过五项：**P04 中国收益率曲线、X12 代理变更监控、P05 成交贷款利率、X01 有限范围的企业信用利差、X04 有限范围的能源供给证据**。三个跨资产相对指标直接复用现有价格；长期 KST、12 个月代理、期限溢价模型和长期结构趋势不纳入当前运行体系。

本研究截至 **2026-10-06**，只读取仓库与公开资料，未修改文件、运行项目程序或调用需账号的接口。以下“接口存在”是官方文档核验，“公开可读”是网页或文件核验，均不等于已经完成账号权限、批量历史或持续运行验证。

**判断口径**

- 正式阶段由债、股、商品的绝对趋势组合决定；宏观证据不能增加一票、强行推进阶段或补全非典型组合。当前绑定为 `CN_BOND_CORE_000012`、`CN_EQUITY_CORE_000985`、`CN_COMMODITY_CORE_NHII`。[models.py:55](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:55)、[stage.py:16](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/stage.py:16)
- 五维指**货币政策、信用、增长、通胀、库存**。“未确认”针对具体判断，例如“私人融资需求恢复”，不意味着整列信用证据全部无效。
- “必需”区分两层：没有哪项新增宏观数据是计算阶段身份的必需输入；但要确认某项具体机制，相应直接证据可能必需。
- 滞后按统计期结束后的**自然日**计算。公告事件没有统一统计期；预测版本也不能按上月实际统计计算滞后。历史起点注明“已核到”的，表示核验下限，不冒充完整最早日期。
- 固定网页表格属于可机器读取入口，但不是承诺稳定性的公开 API。央行报告 PDF 属于可抽取的半结构化资料。
- 本文保留原 P0–P2 标签；它们是项目优先级，不是新增指标的强制程度，原需求文件也明确了这一点。[需求:291](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:291)

---

**1．P0／S08 久期与票息分解**

**公开可得性。** 中债确实公开说明了同一指数的净价、全价、财富指数及修正久期、凸性、到期收益率等指标体系，按交易日计算。但“存在这些字段”不等于“当前核心代理有免费、稳定、完整历史接口”。网页查询与授权交付并存，未核到所有所需字段的免费 API 和固定发布时间承诺。[中债指数说明](https://indices.chinabond.com.cn/cbweb-mn/int/int_yield_zs_doc)

仓库此前对中债候选系列核到过 **2002-01-03 起**的历史，但这是另一组候选指数，不能把它们的久期移植到上证国债指数。当前 `000012` 基日为 2002-12-31，样本为剩余期限一年以上的合资格国债，期限结构会变化。[债券代理研究:24](/mnt/d/cursor/datasourceRF/docs/research/china-bond-core-proxy.md:24)、[上交所编制方案](https://www.sse.com.cn/market/sseindex/indexlist/indexdetails/indexmethods/c1/000012_000012hbook_CN.pdf)

**现有替代。** 可使用：

- `CN_BOND_CORE_000012`：`source_code=000012.SH`，核心收盘指数。
- `CN_BOND_FULL_PRICE_CNY030`：`source_code=000012CNY030.CSI`，全价指数。
- `CN_BOND_10Y_930916`：`source_code=930916.CSI`，另一债券**价格指数**。

前两者在同组合、同日期和方法得到验证后，可以辅助观察收益计算方式的差异；**仍不能完成净价、应计利息、票息再投资、久期和调样贡献的完整分解**。`930916` 不能当作国债收益率。仓库也保留了 CNY030 官方数值样本尚待核验的限制。[市场源语义研究:62](/mnt/d/cursor/datasourceRF/docs/research/market-source-semantic-review-2026-09-05.md:62)

**必要性及影响。** 阶段：增强代理解释；五维：可有可无；转折：增强；异常：确认“票息支撑掩盖价格走弱”“久期漂移导致转向”时必需。缺失时，I 阶段的“长端利率下行”、IV 阶段的“长久期价格见顶”只能由曲线交叉观察，不能声称已经完成收益归因。

**结论：暂缓完整分解。** 先采用 P04；保留当前债券代理，明确它是宽期限国债指数，而非固定久期长债。只有取得**同组合**净价、全价、财富及久期历史后，才值得做精确归因。

---

**2．P0／X12 代理变更监控**

**公开可得性。** 南华年度权重、临时调整和方法公告，以及交易所指数编制方案都有官方入口。发布为年度加不定期事件，公告日与生效日不同，不适合填写统一“滞后几天”。机器入口主要是公告 HTML、PDF、XLS，尚无经核验的统一事件 API。[南华指数公告](https://www.nanhua.net/subpage/nanhuaIndex/index-bulletin.html)

仓库已核到南华 **2004—2017 年回溯权重、2018 年当期公告、2019—2026 年年度材料**，以及若干临时调整；早期回溯文件不能当作当时已公开的信息。不同材料中的展期规则还存在需要逐版本解释的差异。[南华历史研究:12](/mnt/d/cursor/datasourceRF/docs/research/nhii-historical-constituents-and-methods.md:12)

TuShare [`index_weight`](https://tushare.pro/document/2?doc_id=96) 文档存在，要求 **2000 积分**，提供月度成分权重；它不能覆盖全部临时生效事件，也不能替代南华期货指数展期规则。

**现有替代。** 三核心价格，以及 `CN_COMMODITY_SLEEVE_CONTRIBUTION` 的 `copper/rebar/polypropylene/textiles/rubber/pulp/crude_oil` 成员，只能观察价格贡献，不能知道外部方法是否改变。计算公式版本也不等于官方指数方法版本。[metric_contracts.py:102](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:102)

**必要性及影响。** 阶段：增强，其代理身份治理是必需；五维：可有可无；转折：增强；异常：必需。缺失时，任何阶段的异常拐点都无法排除调样、展期或期限漂移；III—V 的商品广度解释尤其需要保留这一限制。

**结论：采用，但采用轻量事件记录。** 记录发布日、生效日、受影响代理、变更内容和官方来源即可。无需把所有公告做成新的数值指标，也无需完整复刻指数。

---

**3．P1／P04 中国收益率曲线**

**公开可得性。** 中债—央行公开表提供国债多个期限收益率，**每个工作日北京时间 17:30** 发布，当日滞后为 **0 天**。固定 HTML 表格及历史查询入口存在，适合首先验证 1、3、5、10、30 年期限。[中债公开曲线表](https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/more?locale=cn_ZH)

中债曲线体系始于 1999 年，此后升级；财政部关键期限国债曲线公开发布可追溯至 2014 年。体系成立年份不代表每个期限都有同起点、同方法历史。[中债曲线说明](https://valuation.chinabond.com.cn/cbweb-mn/int/int_yield_syl_doc)、[财政部发布说明](https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/201411/t20141104_1155910.htm)

TuShare [`yc_cb`](https://tushare.pro/document/2?doc_id=201) 文档存在：目前文档列出国债 `1001.CB`，区分到期和即期曲线；**需单独权限，没有给出可直接套用的积分门槛**。文档没有保证所有期限的历史起点。

**现有替代。** `CN_DR007`、`CN_SHIBOR_ON_1W_3M{tenor=overnight/1w/3m}`只能描述资金端；`CN_BOND_10Y_930916` 是价格，不能替代收益率。`UST10Y_NOMINAL_YIELD`、`UST2Y_NOMINAL_YIELD`、`UST_2S10S_SPREAD` 是美国曲线，不能代替中国。[metric_contracts.py:128](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:128)、[catalog.py:233](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:233)

**必要性及影响。** 阶段：增强债券交叉验证；五维：增强；转折：增强；异常：识别长短端背离时必需。缺失时，I／II“宽松传向长端”、IV“长端融资条件收紧”、VI“短端宽松但长端未响应”等判断只能部分观察。

**结论：采用。** 固定同一曲线类型，先观察收益率方向及 10Y−1Y、30Y−10Y。曲线斜率不能直接命名为期限溢价。

---

**4．P1／X01 信用利差**

**公开可得性。** 上述公开表同时提供 **AAA 中短期票据**和 **AAA 商业银行普通债**收益率。前者样本包括超短融、短融、中票；后者包括同业存单和银行债，不能混为企业信用。两者与国债同日发布，可构造同期限利差。[中债公开曲线表](https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/more?locale=cn_ZH)

已核到 AAA 中短期票据历史查询至少覆盖 **2022 年**；完整最早起点、低评级历史和批量稳定性未全部核实。[官方历史查询样例](https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery?endDate=2023-02-03&gjqx=0&locale=cn_ZH&qxId=zdqpjsylqx&startDate=2022-02-03)

TuShare `yc_cb` 的公开文档**不能作为信用曲线已经开放的证据**。利差也包含流动性、税收、样本构成等影响，不能解释成纯违约概率。

**现有替代。** `CN_SF_COMPONENTS{component=corporate_bonds; measure=stock_end/stock_yoy/ytd_increment}`提供数量；`CN_DR007_POLICY_SPREAD`提供资金市场相对政策利率的偏离；二者都没有企业债风险定价信息。[metric_contracts.py:206](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:206)

**必要性及影响。** 阶段：可有可无；五维：增强信用确认；转折：增强；异常：确认债券信用风险重新定价时必需。缺失时，I／VI“宽货币但信用压力仍大”、IV／V“融资压力上升”中的市场风险价格部分未确认。

**结论：采用限定版。** 先做 **AAA 中短期票据 1Y、3Y－同期限国债**；收益率以百分数表示时，差值乘 100 得基点。明确命名为“高等级企业信用利差”，不据此确认低评级、民营企业或房地产信用风险已经缓解。

---

**5．P1／P05 成交贷款利率**

**公开可得性。** 央行货币政策执行报告持续披露贷款加权平均利率或新发放贷款利率。报告按季，主要是**季末月份成交情况**，不是完整月度序列，也不是季度平均。近期报告通常在季末后约 **35—60 天**发布；2026 年一、二季度报告分别为 **41、43 天**。[央行报告目录](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/index.html)

入口是 HTML 摘要及 PDF 表格；历史报告目录可至 2001 年，贷款利率表本轮至少核到 2008 年，但一般贷款、新发放企业贷款、按揭等子序列不可混接。[2008 年四季度报告](https://wuhan.pbc.gov.cn/eportal/fileDir/history_file/files/att_11634_1.pdf)

TuShare [`monetary_policy`](https://tushare.pro/document/2?doc_id=465) 有文档、需单独权限，提供报告文本／链接，**并非结构化成交贷款利率接口**。

**现有替代。** `CN_LPR_1Y_5Y{tenor=1y/5y_plus}`、`CN_OMO_7D_RATE`、`CN_DR007`只能观察报价和资金价格。LPR 下降不能证明成交利率同步下降。[metric_contracts.py:68](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:68)

**必要性及影响。** 阶段：可有可无；五维：确认“宽松已传到实体融资价格”时必需；转折：增强；异常：增强。没有它，I／II 的传导、III 的融资支持以及 IV／V 的实体融资价格压力只能部分确认。

**结论：采用。** 首先保留同口径的新发放企业贷款利率，其他分类分列。这里的“实际”指**实际成交的名义利率**，不是扣除通胀后的实际利率；它也不包含所有费用，更不能自动排除借款人结构变化。

---

**6．P1／C05 贷款需求与审批**

**公开可得性。** 央行银行家问卷报告确有贷款总体需求、分规模需求和贷款审批指数。调查始于 **2004 年**，按季；2025 年四季度 PDF 内含近三年季度表。[官方报告及历史表](https://www.pbc.gov.cn/diaochatongjisi/116219/116227/2026012320124966002/2026012320124966002.pdf)

2025 年二、三、四季度目录日期对应季后 **25、24、23 天**；但目录也存在明显晚登或补登记录，因此不能把目录时间全部认定为首次公开时间。**截至本轮核验，未在该目录确认 2026 年连续更新**，这不等于宣布停发。[央行调查目录](https://www.pbc.gov.cn/diaochatongjisi/116219/116227/index.html)

PDF 表可抽取，未核到稳定 CSV/API 或直接对应的 TuShare 官方文档。审批指数表示受访银行认为审批趋松或趋紧的扩散情况，**不是实际获批率**；需求指数也不是申请金额。

**现有替代。** `CN_LOAN_STRUCTURE{borrower=enterprise; tenor=short_term/long_term/bill_financing; measure=ytd_increment}`、`CN_PMI_ACTIVITY{series=new_orders; measure=level}`、`CN_CREDIT_IMPULSE`可观察融资结果和订单，无法区分需求不足与银行供给收缩。[metric_contracts.py:233](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:233)、[models.py:483](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:483)

**必要性及影响。** 阶段：可有可无；五维：增强；转折：增强；异常：对信贷供需区分很有价值。缺失时，I／II“宽货币弱信用源于需求不足”、IV／V“贷款需求旺盛但审批趋紧”、VI“信用收缩主因”均未确认。

**结论：暂缓常态接入。** 历史研究可使用已核对的季度版本；在最新连续性恢复验证前，不宜作为当前季度必到的确认项，更不能无限沿用旧值。

---

**7．P1／C06 私人及民营信用**

**公开可得性。** 央行贷款投向报告按季公开普惠小微、住户经营贷款等数据；民营企业所有制口径另见专题和发布会，未核到可覆盖整个需求的统一稳定月度表。2025 年四季度报告在官方转载页于 2026-01-28 可见，即季后 **28 天内已有公开版本**；这不是原始首发时间的精确证明。[央行报告官方转载](https://jrj.sh.gov.cn/SCGK194/20260128/c5f07c0ef6604c599a0dd3bb711d0697.html)

HTML 可读取，但不能把“普惠小微”“私人部门”“民营企业”当作同一统计对象。报告明确 **2024 年 10 月调整普惠小微口径**；报告内同比可比，不代表旧版本绝对额可以直接拼接。民营完整同口径历史长度与直接 TuShare 接口未核实。

**现有替代。** 可以组合：

- `CN_SF_COMPONENTS{component=government_bonds; measure=ytd_increment/stock_end}`，识别政府债贡献。
- `CN_LOAN_STRUCTURE{borrower=household; tenor=short_term/long_term}`及 `{borrower=enterprise; tenor=short_term/long_term/bill_financing}`，均用 `measure=ytd_increment`。
- `CN_SF_COMPONENTS{component=corporate_bonds/renminbi_loans}`，观察非政府融资渠道。

这些足以识别部分“总量改善主要由政府债推动”，但**剔除政府债后的社融仍含国企融资，企业贷款也不是民营贷款**。[metric_contracts.py:206](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:206)

**必要性及影响。** 阶段：可有可无；五维：确认所有制层面的恢复时必需；转折、异常：增强。II／III“私人部门自主扩张”、V／VI“民营信用收缩或修复”仍未确认。

**结论：用现有指标部分替代。** 把输出限定为“政府债与其他融资贡献”“住户与企业贷款结构”，放弃把它升级为私人部门复苏结论。普惠小微可另作专题，暂不为凑足所有制解释而接入。

---

**8．P1／X03 政府债期限供给**

**公开可得性。** 财政部提供国债发行计划、结果，以及地方债发行、到期偿还、平均发行期限和剩余期限等月度资料。计划是前瞻事件，结果按公告时间；月度统计发布存在波动，近期目录样本约为月后 **24—42 天**。[财政部债务管理司](https://zwgls.mof.gov.cn/)、[统计目录](https://zwgls.mof.gov.cn/tjsj/)

固定 HTML 表与附件可读取；部分市场报告有 **2015 年以来**的期限结构比较，但未核到完整的逐券发行—到期—托管—久期一体化免费 API。[地方债统计示例](https://yss.mof.gov.cn/zhuantilanmu/dfzgl/sjtj/202508/t20250828_3970990.htm)、[国债市场报告](https://kjhx.mof.gov.cn/yjbg/202509/t20250903_3971408.htm)

**现有替代。** `CN_SF_COMPONENTS{component=government_bonds; measure=ytd_increment/stock_end}`提供规模；`CN_TOOL_LIQUIDITY_MONTHLY{tool=公开市场国债买卖; measure=injection/withdrawal/net_injection}`提供央行相关操作。二者没有期限或久期权重。[metric_contracts.py:253](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:253)

**必要性及影响。** 阶段：可有可无；五维：增强；转折：可有可无；异常：确认“长债下跌主要由久期供给冲击引起”时必需。IV／V 的货币与通胀解释不能仅凭债熊成立；VI 债券未转牛的供给解释也只能观察。

**结论：暂缓完整期限供给模型。** 常态使用已有政府债融资规模，重大超长期发行按官方事件注释。发行总额、净融资和市场新增 DV01 是不同对象，不能用一个替代另外两个。

---

**9．P1／X04 能源供给冲击**

**公开可得性。** EIA 周度石油报告有美国原油产量、商业库存、进出口和炼厂投入等公开 CSV/XLS 表，无须账号下载。统计周通常止于周五、下周三发布，滞后 **5 天**，节假日延后。[EIA 周报](https://www.eia.gov/petroleum/supply/weekly/)、[发布日程](https://www.eia.gov/petroleum/supply/weekly/schedule.php)

商业原油库存部分系列可回溯至 **1982 年**；各成员起点不同，租赁库存、产品分类等存在历史调整，须按具体序列注释处理。[EIA 库存历史](https://www.eia.gov/dnav/pet/pet_stoc_wstk_dcu_nus_w.htm)

中国原油、煤炭、天然气产量和进口可用统计局月度能源资料，通常月后约 **15—19 天**、1—2 月合并。EIA 是美国证据，不能单独代表中国或全球供给。[统计局能源生产](https://www.stats.gov.cn/sj/zxfbhjd/202604/t20260417_1963344.html)

**现有替代。** `EIA_BRENT_RBRTE`、`EIA_WTI_RWTC`是油价；`CN_COMMODITY_SLEEVE_CONTRIBUTION{sleeve=crude_oil}`是价格贡献；`CN_FUTURES_WARRANTS{symbol=SC; measure=registered_receipts}`是注册仓单，均非完整实物供需。[catalog.py:102](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:102)、[metric_contracts.py:78](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:78)

**必要性及影响。** 阶段：可有可无；五维：增强增长、通胀确认；转折：增强；异常：供给冲击归因必需。III／IV“商品上涨反映需求扩张”、V“成本压力延续”的原因，在没有数量或事件证据时只能观察。

**结论：采用限定版。** 首先采用 EIA 商业原油库存、产量及必要的进出口／炼厂投入背景，配合国内能源数量和官方减产、停产事件。库存下降可能来自需求、出口或供给变化，**不能单独认定供给冲击**。

---

**10．P1／X09 定向干预事件**

**公开可得性。** 央行、证监会和交易所政策公告公开可得，按事件发布，没有统一统计滞后；公告、实施、实际使用量可能相隔数周或数月。HTML/PDF 可读取，未核到覆盖全部市场工具的统一结构化 API。

例如股票回购增持再贷款等工具有正式通知和后续报告，相关工具历史从推出时开始，不能制造推出前“零值”来代表同一制度。[央行政策通知](https://www.pbc.gov.cn/redianzhuanti/118742/5444129/5444142/481faf4556cb42a5b444677b9673ea5c/index.html)、[2025 年金融稳定报告](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025122616592613805/2025122616590775273.pdf)

**现有替代。** `CN_RRR_EVENT`、`CN_OMO_7D_RATE`及 `CN_TOOL_LIQUIDITY_MONTHLY{tool=其他结构性货币政策工具/公开市场国债买卖; measure=net_injection}`只能覆盖部分货币动作，不能定位全部股票或债券专属政策。[metric_contracts.py:253](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:253)

**必要性及影响。** 阶段：可有可无；五维：增强；转折：增强；异常：判断特定干预是否存在时必需，但确认其价格贡献仍需更多证据。II／III“股牛代表广泛增长恢复”、I“债牛代表一般宽松传导”不能由受定向支持的价格单独确认。

**结论：采用事件注释，不建立政策强度打分。** 保存公告、实施、使用量三个时间及证据；额度不是投放量，工具推出不是资产上涨原因已经得到证明。

---

**11．P1／T01 商品／债券相对动量**

**公开可得性。** 无需新增外部序列；由共同交易日的价格派生，新增数据滞后 **0 天**，最终可用时间取较慢父序列。TuShare [`index_daily`](https://tushare.pro/document/2?doc_id=95)、[`fut_index_daily`](https://tushare.pro/document/2?doc_id=468) 均有文档，页面要求 **2000 积分**；不能据此承诺每个指定代码的完整历史。

**现有替代。** 完全复用 `CN_COMMODITY_CORE_NHII{source_code=NHII.NH}`与 `CN_BOND_CORE_000012{source_code=000012.SH}`。可以观察：

\[
\Delta\log(NHII/000012)
=\Delta\log(NHII)-\Delta\log(000012)
\]

这满足相对表现观察需求，但若不用 Pring 的长期平滑方案，就不能称为复刻其长期 KST。[Pring 跨资产转折说明](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)

共同历史受 NHII 限制，仓库核到其价格从 **2006-01-04**起；早期方法资料完整性弱于近期。股票、债券和期货指数的收益构造也不完全相同。[南华研究:23](/mnt/d/cursor/datasourceRF/docs/research/nhii-historical-constituents-and-methods.md:23)

**必要性及影响。** 阶段：可有可无；五维：可有可无；转折：增强；异常：增强。缺失只减少 I、III 附近的相对动量观察，**不应把任何宏观格降为未确认**。

**结论：用现有指标替代，增加派生观察即可。** 必须同时保留两个父资产的绝对趋势；比值上升也可能只是债券跌得更快。

---

**12．P1／G07 行业与盈利扩散**

**公开可得性。** 官方行业指数、交易所财报、业绩预告和快报均存在。行业指数为日频；企业实际财务披露为季度／半年／年度，现行上交所规则一般要求年报年度结束后四个月内、半年报两个月内、一／三季报一个月内，即约 **120—121、61—62、30—31 天上限**。[上交所上市规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/mainipo/c/c_20260424_10816589.shtml)

TuShare [`forecast`](https://tushare.pro/document/2?doc_id=45)、[`express`](https://tushare.pro/document/2?doc_id=46) 有文档：常规接口 **2000 积分**，对应 VIP 批量接口 **5000 积分**。业绩预告不是分析师一致预期，披露条件造成样本选择偏差。行业指数起点、财务历史长度随代码和公司不同，不能给统一起点；分类调整、上市退市及财务重述需要时点处理。

**现有替代。** 已有：

- `CN_EQ_ADV_DEC`、`CN_EQ_AD_RATIO`、`CN_EQ_ADV_AMOUNT_SHARE`；
- `CN_EQ_NEW_HIGH_LOW_90/250{measure=new_highs/new_lows}`；
- `CN_EQ_ABOVE_MA90/250{measure=above_ma_share}`，使用时点 A 股交易集合；
- `CN_EQ_CSI300/500/1000`，分别为 `000300.SH/000905.SH/000852.SH`；
- `CN_INDUSTRIAL_FINANCE{item=profit/revenue; measure=official_yoy/ytd_level}`。

它们可以检查股牛是否广泛、工业利润总量是否配合，不能确认**行业盈利扩散或未来盈利修正**。[breadth.py:28](/mnt/d/cursor/datasourceRF/src/pring_cycle/breadth.py:28)、[metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175)

**必要性及影响。** 阶段：可有可无；五维、转折、异常：增强。II／III 增长格可确认“股价宽度改善”“工业总利润改善”，但“多数行业盈利同步复苏”仍未确认；IV／V 盈利见顶的行业广度也一样。

**结论：用现有指标部分替代。** 当前没有必要建设全市场、时点一致的行业盈利数据库。

---

**13．P2／T02 股债相对强弱**

**公开可得性。** 复用日频价格，新增滞后 0 天；接口文档及积分同 T01。`000985` 基日为 **2004-12-31**，正式发布为 **2011-08-02**；此前属于回溯历史，不能当作实时发布记录。[股票代理研究:26](/mnt/d/cursor/datasourceRF/docs/research/china-equity-core-proxy.md:26)

**现有替代。** `CN_EQUITY_CORE_000985{source_code=000985.CSI}`÷`CN_BOND_CORE_000012{source_code=000012.SH}`，配合现有股票宽度即可完全覆盖相对表现需求。股价指数与债券收益计算方法不同，因此命名为“核心代理相对强弱”，不要解释成两种可投资总回报的严格比较。

**必要性及影响。** 阶段、五维：可有可无；转折、异常：增强。II 附近风险偏好改善、IV 附近股票相对债券占优可多一项观察；缺失不影响宏观确认格。[需求:309](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:309)

**结论：用现有指标替代。** 不新增外部源，不额外参与阶段投票。

---

**14．P2／T03 股商相对动量**

**公开可得性。** 复用日频父序列，新增滞后 0 天；共同历史下限受 NHII 约束，约为 2006 年起，早期可比性限制同 T01。

**现有替代。** `CN_EQUITY_CORE_000985{source_code=000985.CSI}`÷`CN_COMMODITY_CORE_NHII{source_code=NHII.NH}`，完全覆盖相对表现观察；不等价于股票盈利增长减去通胀，也不等价于相同风险预算下的投资组合收益。[models.py:55](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:55)

**必要性及影响。** 阶段、五维：可有可无；转折、异常：增强。主要辅助 II 的股市领先恢复，以及 V 的股票与商品分化；缺失不令宏观格自动未确认。[语义底稿:114](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:114)

**结论：用现有指标替代。** 与 T01、T02 共用日期对齐及动量定义，避免三个近似信号重复计权。

---

**15．P2／G05 终端需求与资本开支**

**公开可得性。** 统计局地产销售、投资、新开工和固定资产投资等按月公开，1—2 月通常合并；主要经济活动数据通常月后 **15—19 天**发布，有固定 HTML 表及数据库入口。[统计局发布日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html)、[房地产发布示例](https://www.stats.gov.cn/zwfwck/sjfb/202601/t20260119_1962324.html)

历史较长，但当前可比口径不能无限拼接：固定资产投资 **2011 年项目统计起点由 50 万元提高到 500 万元**，后续还涉及修订。累计名义投资不是单月实际资本开支，地产销售不是整体终端需求。[统计局投资口径说明](https://www.stats.gov.cn/sj/ndsj/2023/html/sm10.htm)

本轮未核到一个直接覆盖该复合需求的 TuShare 同口径接口；不能因此宣称所有相关接口不存在。

**现有替代。** `CN_PMI_ACTIVITY{series=new_orders/production/purchase_volume; measure=level}`、`CN_INDUSTRIAL_VA{measure=current_month_real_yoy/mom_seasonally_adjusted/ytd_real_yoy}`、`CN_CAPACITY_UTILIZATION{industry=all_industry; measure=quarter_rate/yoy_change}`，以及住户、企业中长期贷款增量，可覆盖总体需求—生产—产能链条。[metric_contracts.py:114](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:114)、[metric_contracts.py:165](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:165)

**必要性及影响。** 阶段：可有可无；五维：增强；转折、异常：增强。II／III“地产、耐用品、资本开支广泛复苏”、IV“利率敏感需求过热”、V“终端需求因利率而收缩”仍未确认；总体增长方向可以由已有指标判断。

**结论：用现有指标部分替代。** 放弃细行业传导承诺，比把多个低频累计指标塞进通用方向规则更可靠。

---

**16．P2／I07 应收与回款压力**

**公开可得性。** 统计局工业企业利润发布包含应收账款余额、增长率、平均回收期，通常月后 **27 天**发布，1—2 月合并。固定 HTML 表可读取，与现有工业财务源家族接近。[发布示例](https://www.stats.gov.cn/zwfwck/sjfb/202601/t20260127_1962382.html)

有明确断点：**2019 年使用“应收票据及应收账款”，2020 年恢复“应收账款”及相关指标**。因此 2020 年以来更适合构建同名历史段，旧段单独处理；规上企业样本也会变化。[2019 年口径说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/201911/t20191127_1767552.html)、[2020 年口径说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202011/t20201127_1805671.html)

平均回收期是由财务总量构造的周转比率，不是逐笔逾期天数。未核到直接同口径 TuShare 文档。

**现有替代。** `CN_INDUSTRIAL_FINANCE{item=revenue/cost/profit; measure=ytd_level/official_yoy}`、`CN_FINISHED_GOODS_INVENTORY{measure=nominal_end_level/official_yoy}`、`CN_INVENTORY_TURNOVER{measure=days/official_yoy_change}`可以观察销售、利润、库存压力，**不能替代回款**。[metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175)

**必要性及影响。** 阶段：可有可无；五维：增强库存确认；转折、异常：增强。IV／V 被动累库可由订单、生产和库存共同判断，但“赊销增加、回款恶化”未确认；VI“现金回收改善”也未确认。

**结论：暂缓，作为后续低成本增强的优先候选。** 数据可靠且接入相邻，但对当前阶段和五维基本确认不是首批必需。

---

**17．P2／X05 农产品与天气**

**公开可得性。** USDA WASDE 月度报告有 PDF、XML、Excel、文本及整合 CSV；报告档案可至 **1973 年**，整合 CSV 覆盖 **2010 年以来**，通常在报告发布次日提供。[USDA WASDE](https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report)

WASDE 是作物年度供需**预测版本**，不能把每月约 9—12 日发布解释为“上月实际数据滞后十天”。天气灾害另需气象机构事件资料；品种、地域、营销年度和预测修订都影响可比性。

**现有替代。** `CN_CPI_HEADLINE{category=headline}`与 `CN_CORE_CPI{category=ex_food_energy}`的 `mom/yoy`可观察食品能源与核心价格分化，但不能把食品和能源分开。`CN_COMMODITY_BROAD_NHCI`与核心工业商品的比较也只能提示构成差异；`CN_FUTURES_WARRANTS{symbol=CF}`不等于棉花完整供需。[metric_contracts.py:280](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:280)

**必要性及影响。** 阶段：可有可无；五维：增强消费通胀解释；转折：可有可无；异常：发生特定农业冲击时增强。III—V 通胀格不得据 CPI 单独确认工业需求或成本扩散；“天气导致食品通胀”仍未确认。

**结论：不采用常态农业天气数据包。** 当前核心是工业商品，完整农业供需体系成本与目标不匹配。出现明显食品价格异常时，再引用具体官方事件；这不要求日常维护整套指标。

---

**18．P2／X06 运输、贸易及外需冲击**

**公开可得性。** 海关重点商品量值、贸易方式和地区数据公开；月度快讯通常早于正式明细。常见发布节奏为月后约 **7—14 天快讯、18—20 天明细／查询开放**，具体月份须按当年日程，春节月份存在合并发布。本轮核到 2026 年官方日程公告，但附件抓取未成功，因此不将该区间视为已逐月验证的 2026 年承诺。[海关公告官方转载](https://www.mofcom.gov.cn/zcfb/zgdwjjmywg/art/2026/art_f1be0183462142a28dbd9fd727220e3e.html)、[海关月度表目录](https://english.customs.gov.cn/statics/report/monthly.html)

历史公开明细本轮至少核到 **2018 年**。HS 分类版本、人民币／美元口径、数量单位和修订都需分开管理。在线查询不等于无条件稳定 API；部分商务部转引页此次只返回表头，不能据搜索摘要承诺可持续抓取。

PMI 新出口订单、进口和供应商配送时间是更轻量入口。TuShare [`cn_pmi`](https://tushare.pro/document/2?doc_id=325) 明确存在，要求 **5000 积分**；历史总体超过十年，但样本于 **2013 年扩容**，各成员起点需分别确认。[统计局样本调整说明](https://www.stats.gov.cn/english/PressRelease/201302/t20130201_72257.html)

**现有替代。** `CN_PMI_ACTIVITY{series=new_orders/production/purchase_volume}`没有区分内外需；其当前成员**不含新出口订单、进口和配送时间**。`CN_USDCNY_CENTRAL_PARITY`、`CN_USDCNY_CLOSE_1630`也不是外需或物流数量。[metric_contracts.py:114](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:114)

**必要性及影响。** 阶段：可有可无；五维：增强增长、库存解释；转折、异常：增强。II／III 增长改善的内外需来源、IV／V 输入成本和运输瓶颈、V／VI 库存受出口拖累的原因仍未确认。

**结论：暂缓完整贸易运输体系。** 若后续确有外需归因需求，先扩 PMI 的三个成员，再增加少量海关实物量；不恢复一个 BDI 就宣称覆盖该需求。

---

**19．P2／X02 期限溢价分解**

**公开可得性。** 本轮未核到可直接采用、持续更新、同口径的中国官方公开期限溢价序列。纽约联储 ACM 数据有美国 **1961 年以来**日频／月频估计及下载，但这是美国国债模型估计，不是中国数据，也不是直接观测量。[纽约联储 ACM](https://www.newyorkfed.org/research/data_indicators/term-premia-tabs)

中国若自行估计，滞后取决于曲线和模型输入；历史、参数、样本窗口及重估都会改变结果，不能填写统一官方发布滞后。长端期限溢价对估计方法敏感。[美联储方法研究](https://www.federalreserve.gov/econres/notes/feds-notes/robustness-of-long-maturity-term-premium-estimates-20170403.html)

**现有替代。** `UST_2S10S_SPREAD`不是美国期限溢价，更不能替代中国；`CN_DR007_POLICY_SPREAD`也不对应期限溢价。新增 P04 后可以观察中国长短端斜率，但仍不能分离利率预期与风险补偿。

**必要性及影响。** 阶段、五维、转折：可有可无；异常：增强模型解释。IV／V 或 VI 的“收益率异常由期限溢价上升造成”应保持未确认；普通增长、通胀、信用观察不因此失效。

**结论：不采用当前运行模型。** 保留“长端与短端／宏观背离、原因未确认”的描述，比输出一个难以验证的期限溢价数字更可靠。

---

**20．P2／S05 12 个月代理**

**公开可得性。** 三核心月末价格均可由已有日线得到；月末数据完成后没有额外发布滞后。历史范围同 T01—T03，计算 12 个月均线需要相应预热历史，不需要新数据供应商。

**现有替代。** 现有三核心价格完全覆盖数据需求；当前 MA120 趋势规则覆盖本项目的运行目标，但**不等价于 Pring 12 个月代理结果**。这项功能在 `model_v0014` 中明确关闭，不是遗漏接入。[models.py:499](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:499)

**必要性及影响。** 阶段、五维、转折、异常：对当前约定尺度均可有可无。缺失不令任何五维格未确认；只意味着不能声称完成了 Pring 月线版本的一致性校准。

**结论：不采用当前运行体系。** 如未来另立方法比较研究，可从已有价格重算；不能以新增源的名义绕过已经确定的范围。[ADR-0035:11](/mnt/d/cursor/datasourceRF/docs/adr/0035-metric-horizon-at-most-one-year.md:11)

---

**21．P2／S06 KST**

**公开可得性。** Pring Research 公开 KST 方法，基于多个平滑变化率组合，并区分适用周期；它不是需要购买的独立原始数据。数据频率与滞后随所选父序列，新增滞后为 0；所需历史取决于最长变化率和多层平滑窗口。[Pring KST 方法](https://www.pring.com/long-term-kst/)

长期版本不能仅凭“一年价格足够算 ROC”就宣称覆盖完整预热。改变周期参数得到的是另一个技术定义，不应继续宣称与原长期方案等价。

**现有替代。** 三核心价格、当前趋势与斜率，以及拟派生 T01—T03，部分覆盖方向、相对动量和背离观察；无法完整替代特定 KST 的平滑和交叉时点。[models.py:38](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:38)

**必要性及影响。** 阶段、五维：可有可无；转折：增强；异常：可有可无。没有 KST 只是少一种转折辅助方法，不使五维任何格失去确认资格。

**结论：不采用长期 KST；当前也不单独新增短期 KST。** 先把已有趋势和相对表现解释清楚，避免多个高度相关技术指标重复计权。

---

**22．P2／X10 长期结构趋势**

**公开可得性。** 官方多年价格、利率、通胀及制度公告都存在，但频率从日度到年度、发布滞后从当日到数月不等，不存在统一的“长期结构趋势官方数据集”或统一 API。

关键限制在可比性：A 股指数回溯与正式发布历史不同；南华早期权重资料部分是事后回溯；制度、统计范围和指数方法也会改变。即使有几十年数值，也不自动有几十年同口径实时证据。[股票代理研究:62](/mnt/d/cursor/datasourceRF/docs/research/china-equity-core-proxy.md:62)、[南华研究:12](/mnt/d/cursor/datasourceRF/docs/research/nhii-historical-constituents-and-methods.md:12)

**现有替代。** 当前三资产、`CN_CPI_HEADLINE/CN_CORE_CPI`、`CN_PPI`、政策及信用数据可以解释近期环境；受现行尺度限制，不能确认数十年结构周期。X12 可以保留必要的制度和代理版本元数据，但不能替代长期研究。

**必要性及影响。** 阶段、五维、转折：当前范围内可有可无；异常：可增强长期解释，但不适合自动运行。缺失不影响当期五维确认，只限制“长期通胀制度切换”“几十年债牛终结”等跨制度结论。

**结论：不采用当前运行体系。** 如有明确长期问题，另建研究数据集和可比性规则；现行边界不应被背景解释悄然突破。[ADR-0035:11](/mnt/d/cursor/datasourceRF/docs/adr/0035-metric-horizon-at-most-one-year.md:11)

---

**汇总表**

“高”表示已有明确官方公开入口或可直接复用原料；不代表完整需求已经有稳定 API。“中”表示主要事实公开，但历史、成员、时点或交付还需额外治理。

| 缺失项 | 优先级 | 可得性 | 及时性 | 可替代 | 结论 |
|---|---|---|---|---|---|
| S08 久期与票息分解 | P0 | 中 | 日频；完整字段发布时间未核定 | 部分，不能精确归因 | 暂缓完整分解 |
| X12 代理变更监控 | P0 | 中 | 年度／临时事件；按公告与生效日 | 否 | 采用轻量事件记录 |
| P04 中国收益率曲线 | P1 | 高 | 工作日 17:30，当日 | 否 | 采用 |
| X01 信用利差 | P1 | 中；AAA 子集高 | 工作日日终，当日 | 否 | 采用 AAA 同期限企业利差 |
| P05 成交贷款利率 | P1 | 高 | 季度，通常季后约 35—60 天 | 部分 | 采用同口径子序列 |
| C05 贷款需求与审批 | P1 | 中 | 近期历史约 23—25 天；最新连续性未确认 | 部分，不能分供需 | 暂缓常态接入 |
| C06 私人及民营信用 | P1 | 中 | 季度／专题；无统一民营发布时限 | 部分 | 用融资结构替代，限制结论 |
| X03 政府债期限供给 | P1 | 中 | 事件＋月度，近期约 24—42 天 | 部分，只替规模 | 暂缓完整期限模型 |
| X04 能源供给冲击 | P1 | 高，限定地域品种 | EIA 通常 5 天；国内月度约 15—19 天 | 部分，价格不能替数量 | 采用有限证据集 |
| X09 定向干预事件 | P1 | 中 | 公告即时；使用量另有滞后 | 部分 | 采用事件注释 |
| T01 商品／债券动量 | P1 | 高 | 随父序列，无新增滞后 | 完全替代原料需求 | 用现有价格派生 |
| G07 行业与盈利扩散 | P1 | 中 | 股价日频；财报约 30—121 天 | 部分 | 用宽度＋总量利润替代 |
| T02 股债相对强弱 | P2 | 高 | 随父序列，无新增滞后 | 完全 | 用现有价格派生 |
| T03 股商相对动量 | P2 | 高 | 随父序列，无新增滞后 | 完全 | 用现有价格派生 |
| G05 终端需求与资本开支 | P2 | 高 | 月度约 15—19 天 | 部分 | 用订单、生产、产能替代 |
| I07 应收与回款压力 | P2 | 高 | 月度通常 27 天 | 部分，不能替回款 | 暂缓；后续优先增强 |
| X05 农产品与天气 | P2 | 高，但分散 | 月度预测版本／事件；非统一统计滞后 | 部分 | 不采用常态数据包 |
| X06 运输贸易冲击 | P2 | 中 | 海关约 7—20 天；PMI 更快 | 部分 | 暂缓完整体系 |
| X02 期限溢价分解 | P2 | 低，中国直接序列未核到 | 自建模型，无统一发布时限 | 否 | 不采用 |
| S05 12 个月代理 | P2 | 高 | 月末，无新增滞后 | 原料完全具备 | 不采用当前功能 |
| S06 KST | P2 | 高，原料与方法公开 | 随父序列；需预热 | 部分替代用途 | 不采用当前功能 |
| X10 长期结构趋势 | P2 | 中 | 多频率、多滞后 | 仅近期解释可替 | 不采用当前运行体系 |

**最小可靠集合**

这里应区分“识别阶段需要什么”和“首批值得补什么”。

阶段识别仍以现有三核心价格及其有效性检查为基础。五维基本确认已有可用骨架：政策利率与资金价格、社融与贷款结构、PMI 与工业活动、CPI/PPI 与采购出厂价格、订单—生产—库存—周转。**有指标合同不等于当期已经取得有效数据；缺失、过期或口径不匹配时仍须降级。**

建议首批新增以下 **5 项需求**，按价值与可靠性排序：

| 排序 | 首批采用项 | 最小范围 | 直接解决的问题 |
|---|---|---|---|
| 1 | **P04 中国收益率曲线** | 国债 1／3／5／10／30 年到期收益率 | 避免把债券指数当收益率，验证长短端是否一致 |
| 2 | **X12 代理变更监控** | 三核心代理的重大方法、样本、权重和展期事件 | 防止代理含义变化被当作经济转折 |
| 3 | **P05 成交贷款利率** | 季度发布、同口径的新发放企业贷款利率 | 验证政策和报价是否传到实体融资价格 |
| 4 | **X01 有限信用利差** | AAA 中短票 1Y／3Y 减同期限国债 | 增加企业风险价格证据，识别资金宽松与信用分化 |
| 5 | **X04 有限能源供给证据** | EIA 库存、产量及必要供需背景；国内数量与官方事件 | 约束商品牛市的需求归因 |

T01—T03 是已有数据的派生工作，不构成新增外部数据集合。X09 可在重大事件发生时补充人工注释，但不挤占首批数据工程。若后续增加第六项数值需求，优先考虑 I07；若 C05 恢复确认最新连续发布，其信用供需解释价值可能高于 I07。

**可以放弃什么，预期表必须怎样标注**

| 可放弃或暂不承诺的范围 | 仍然能够判断 | 需要保留的标注 |
|---|---|---|
| S05、长期 S06 | 当前约定尺度的三资产阶段、绝对及相对趋势 | “未进行 12 月／长期 KST 一致性校准”；无需将五维降级 |
| X02 中国期限溢价模型 | 曲线变化、债价变化、宏观背离 | IV／V／VI：“期限溢价归因未确认” |
| X10 长期结构周期 | 当期阶段及近期宏观背景 | “跨制度、长期结构结论不在本模型确认范围” |
| X05 常态农业天气体系 | 工业商品周期、核心与总体 CPI 分化 | III—V：“食品／天气原因未确认”；不得用 CPI 独证工业需求 |
| C06 完整所有制信用体系 | 政府债贡献、住户与企业融资结构 | II／III：“私人部门自主恢复未确认”；V／VI：“民营信用修复未确认” |
| G07 完整行业盈利体系 | 股价扩散、工业利润总量 | II—IV：“行业盈利扩散未确认”；IV／V：“盈利见顶广度仅观察” |
| G05 全套终端行业数据 | 总体订单、生产、产能及融资结构 | II—V：“地产／耐用品／资本开支传导未确认” |
| S08 精确久期票息归因 | 核心债券趋势及收益率交叉验证 | I／IV：“票息、久期和价格贡献未分解” |
| X03 完整久期供给模型 | 政府融资规模、重大发行事件 | IV—VI：“期限供给的价格贡献未确认” |
| C05 未验证的最新季度数据 | 信用数量及订单结果 | I／II／V／VI：“需求不足与银行供给收缩未区分” |
| I07 应收指标 | 库存压力、销售和利润变化 | IV—VI：“回款压力仅观察，现金兑现未确认” |
| X06 完整贸易运输体系 | 总订单、总生产、价格和库存变化 | II／III：“内外需来源未区分”；IV—VI：“运输或贸易归因未确认” |

最后，预期表需要遵守三条比“补齐 22 项”更重要的约束：

1. **缺数据不等于中性，更不等于宽松。**
2. **有数据不等于支持预期；累计值、同比、环比、扩散指数和事件不能套用同一种方向规则。**
3. **价格不能自我确认原因：NHII 上涨决定商品趋势，但不能再单独证明需求扩张；股票宽度证明价格扩散，但不证明盈利扩散。**

这些正是旧模型审计暴露的核心解释风险。解决它们，才能让有限而可靠的数据真正满足普林格识别目标。[旧审计:498](/mnt/d/cursor/datasourceRF/docs/research/legacy-pring-model-audit.md:498)、[六阶段预期修正:547](/mnt/d/cursor/datasourceRF/docs/research/legacy-pring-model-audit.md:547)
