**现有数据具备“需求一致性检验”和“供给冲击嫌疑提示”的条件，但不具备稳定确认商品涨价主要由供给还是需求驱动的条件。**最关键的缺口是与价格相匹配的实物产量、使用量、进出口量及库存收支，而非更多价格指标。仓库对 X04—X06 的缺口认定与这一结论一致。[仓库指标需求](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:174)

尤其需要修正两条直觉：

- **涨价＋去库存不等于需求恢复。**消费增加和供给减少都可能使库存下降。
- **涨价＋累库存不等于供给冲击。**主动补库、预防性囤货、进口到货和库存转移均可能造成这一组合。Känzig 的研究甚至发现，负面的石油供给消息可以同时推高油价和库存，而实际产量随后才下降。[Kilian、Murphy：库存与石油市场识别](https://cepr.org/publications/dp7753)、[Känzig，2021，AER](https://www.aeaweb.org/articles?id=10.1257/aer.20190964)

本文核对了源码、项目研究文档及公开官方资料；未修改文件、运行项目程序或调用需账号的接口。以下评价的是**指标口径上的可实现性**，没有验证运行库中的历史完整性，也不对当前行情作归因。

**1．方法综述：必须区分“市场变紧”和“为什么变紧”。**

首先应保留至少四种解释：**实体需求扩张、实际供给收缩、库存／预期需求增加、混合或尚未识别**。其中，担忧未来断供而囤油，在商品市场模型中属于一种需求冲击，却不能用来确认普林格阶段Ⅲ所指的实体需求恢复。Kilian 2009 将原油供给、全球工业商品总需求和原油特有需求分别识别，正是为了避免把所有油价上涨赋予相同的宏观含义。[Kilian，2009，AER](https://ftp.aeaweb.org/articles?id=10.1257%2Faer.99.3.1053)

| 方法 | 逻辑与所需数据 | 可靠性与局限 |
|---|---|---|
| **价格—数量符号约束** | 在其他条件不变时，需求扩张通常使价格、交易的实物数量同升；供给收缩通常使价格升、数量降。需要同品种、同地域、同期的价格、产量／使用量，最好加入经济活动。 | 是结构模型的识别条件，**不能直接把两条原始序列的涨跌当作冲击识别**。现实中多种冲击同时发生，库存会缓冲使用量，供给反应也有时滞。期货成交量、持仓量、仓单和 PMI 点数均不是这里的实物交易数量。[IMF WP/14/218](https://www.elibrary.imf.org/view/journals/001/2014/218/article-A001-en.xml) |
| **库存与实物收支联合分析** | 检查“期末库存−期初库存＝产量＋进口−出口−使用量＋调整项”。去库究竟来自供应减少还是使用增加，必须拆开收支。 | 收支表对解释紧张来源很有价值；仅看库存符号则很弱。库存可能是主动持有、预防性储备或被动积压；部分库存不在统计范围内。EIA 的消费代理也是收支推算值，并非独立调查的终端消费量。[EIA 消费代理说明](https://www.eia.gov/todayinenergy/detail.php?id=63184)、[Kilian、Murphy](https://cepr.org/publications/dp7753) |
| **期限结构、基差和便利收益** | 同一天比较近远月：近月高于远月通常反映即时交付更有价值；现货−期货基差走强也可提示现货紧张。需要分合约结算价、到期日；真正基差还需交割口径相匹配的现货价。 | 对“当前货源紧不紧”较有解释力，对“需求还是供给”辨识力有限。需求激增与断供均可造成反向市场；利率、仓储成本、季节性、交割挤压也影响曲线。[CME 期限结构说明](https://www.cmegroup.com/education/courses/introduction-to-ferrous-metals/what-is-contango-and-backwardation)、[NBER：商品期货收益的基本面](https://www.nber.org/papers/w13249.pdf) |
| **上涨广度、贡献与相关性** | 检查是否跨金属、黑色、化工等产业扩散，还是集中在少数能源／农业品种。需要分品种收益、权重、成分与展期规则。 | 广泛上涨更符合共同需求改善，但也可能来自能源成本传导、共同供给瓶颈、汇率或金融因素。相关性上升不能证明共同需求冲击；同一产业链多个品种上涨也不等于多个独立证据。[BIS：商品市场冲击与溢出](https://www.bis.org/publications/qr-202209/commodity-markets-shocks-and-spillovers)、[南华官方指数规则与公告入口](https://nanhua.net/subpageAged/researchIndex.html) |
| **实体需求指标对照** | 比较订单、采购、实际产出、加工量、销售、产能利用率，观察上涨是否得到实体活动支持。 | 很适合检验阶段Ⅲ叙事；但只能先确认“需求改善同时发生”，不能自动证明需求主导涨价。中国 PMI 不能代表全球需求，生产增加也可能来自供给恢复。[统计局 PMI 方法说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202303/t20230331_1938273.html)、[Pring 对恢复扩散的解释](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/) |
| **事件、公告与高频识别** | 将意外减产、停产、运输中断等事件，与公告前后价格变化、后续实际损失对应。严格研究可用公告窗口内期货价格意外变化作外部工具变量。 | 确认某次断供事实可以很强；确认其主导整段行情则仍需量化。战争新闻可能早被预期，减产也可能是对需求走弱的反应。普通新闻标签不能替代“意外冲击”。[Känzig，2021](https://www.aeaweb.org/articles?id=10.1257/aer.20190964)、[ECB：叙事符号约束研究](https://www.ecb.europa.eu/press/conferences/shared/pdf/20160922_dsge/Narrative_Sign_Restrictions_for_SVARs.pdf) |
| **结构 VAR、历史分解与工具变量方法** | 将实质价格、全球产量、经济活动、库存纳入动态模型，通过递归、符号、弹性、叙事或外部工具限制识别，再估算各类冲击贡献。 | 能给出“在这些假设下由哪类冲击主导”的统计结论，但结果依赖模型、样本和数据修订。Kilian 2009 的原始识别主要采用递归限制，不能简单称作价格—数量符号分类器；后续库存模型进一步分离预期需求。[Dallas Fed 对原始模型的说明](https://www.dallasfed.org/~/media/documents/research/papers/2009/wp0905.pdf)、[IMF 对库存扩展模型的讨论](https://www.elibrary.imf.org/view/journals/001/2023/160/article-A001-en.xml) |

因此，本文将“确认”分为三个层次：**确认观测事实、支持经济叙事、在明确假设下识别主要驱动**。这三个层次不能互换；增加数据主要改善后两个层次，不会消除全部因果不确定性。[IMF 关于识别限制的说明](https://www.elibrary.imf.org/view/journals/001/2014/218/article-A001-en.xml)

**2．现有指标可以构造以下判别信号，但组合规则本身属于研究建议。**

先固定现有数据的实际边界：

| 数据组 | 核实到的口径及限制 |
|---|---|
| **商品价格与贡献** | 自建篮子为七个袖套、八个品种：铜 CU、螺纹 RB、PP、纺织 CF＋TA、橡胶 RU、纸浆 SP、原油 SC。SC 权重 **20%**，其他袖套各 **2/15**；纺织内部 CF、TA 等权。贡献是每日收益贡献百分点，不是 NHII 官方成分贡献。[篮子定义](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:25)、[贡献计算](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:243) |
| **仓单** | `CN_FUTURES_WARRANTS{symbol=CF/CU/PP/RB/RU/SC/SP/TA, measure=registered_receipts}`。只代表注册仓单；需逐品种处理计量单位，不能直接相加，也不能视为全社会库存。[成员契约](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:78)、[TuShare 仓单字段](https://tushare.pro/document/2?doc_id=140) |
| **PMI** | 活动成员为 `manufacturing/new_orders/production/purchase_volume`；库存为 `raw_materials/finished_goods`；价格为 `purchase_prices/output_prices`，均取 `measure=level`。PMI 是扩散指数，49→49.8 表示仍收缩但改善，不能读作实物量增长。[成员契约](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:114)、[统计局方法说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202303/t20230331_1938273.html) |
| **工业与库存** | 工业增加值已有实际同比和季调环比；产成品存货为名义余额与官方同比；另有周转天数、工业收入／成本／利润、季度产能利用率。它们可以补充总量判断，但不能代替某一商品的产销存。[官方成员契约](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:165) |
| **国际油价与汇率** | WTI、Brent 是现货价格；可用目录中的人民币汇率检查币种影响，但不能把 SC 期货与 WTI／Brent 现货的差直接叫作基差。[价格口径要求](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:139)、[汇率目录](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:821) |

以下“中等／较弱”是证据强弱描述，**不是概率，也不是项目的“确认度”计数**。

| 可构造信号 | 所需指标与逻辑 | 时滞、误判及结论上限 |
|---|---|---|
| **① 工业商品上涨，订单、采购、生产同步改善，实际工业产出跟进** | `CN_COMMODITY_CORE_NHII`；`CN_PMI_ACTIVITY{new_orders,purchase_volume,production}`；`CN_INDUSTRIAL_VA{mom_seasonally_adjusted,current_month_real_yoy}`。可再检查非原油袖套是否扩散。 | **对需求恢复有中等支持，对涨价主因仍未确认。**商品可能领先月度数据；工业产出也可能是复工或供给恢复；全球供给冲击可与中国复苏同时发生。不能用工业增加值总量替代铜／钢消费量。[Pring](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[统计局工业增加值口径](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965308.html) |
| **② 涨价＋对应仓单下降＋订单／采购改善** | 对 CU、RB、PP、RU、SP、SC，将对应袖套收益与该品种仓单配对，再看 PMI 需求。比单独涨价更符合下游吸收货源。纺织袖套只能分别展示 CF、TA 仓单，不能从袖套平均收益反推出二者各自价格。 | **需求型提示，不能确认。**断供也会造成涨价去库；仓单注销、交割到期、移库可能没有实际消费。月度 PMI 不能解释每一天仓单下降。[仓库篮子计算](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:243)、[TuShare 仓单口径](https://tushare.pro/document/2?doc_id=140)、[库存识别研究](https://cepr.org/publications/dp7753) |
| **③ 涨价＋仓单／产成品库存上升＋订单、采购走弱** | 仓单按品种观察；`CN_PMI_INVENTORY{finished_goods}`、`CN_FINISHED_GOODS_INVENTORY{official_yoy}`、`CN_INVENTORY_TURNOVER{days,official_yoy_change}`与订单联合使用。 | 应输出 **“需求解释不足／被动累库嫌疑”**，不能直接输出“供给型”。还可能是预防性囤货、进口集中到港、期货预期先行或名义库存受价格抬升。产成品存货是下游库存，不能与原料仓单互换。[仓库库存口径](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:147)、[Känzig](https://www.aeaweb.org/articles?id=10.1257/aer.20190964) |
| **④ 涨价＋原料库存回升＋订单、采购、生产改善，周转不恶化** | `CN_PMI_INVENTORY{raw_materials}`、活动三成员及周转天数。用于识别主动补库，从而避免把所有累库都认作坏信号。 | **支持主动补库叙事，因果仍未确认。**抢购避险也会同时推升采购与原料库存；必须看到订单、生产或销售消化。库存可随需求扩张而增加，没有“需求型上涨必去库”的必要条件。[Pring 库存与销售机制](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[项目阶段Ⅲ解释](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:118) |
| **⑤ SC 贡献集中，WTI／Brent 同涨，国内订单／产出未改善** | `CN_COMMODITY_SLEEVE_CONTRIBUTION{crude_oil}`、其他六袖套、两项 EIA 油价和国内活动。 | **能源驱动较明确，能源供给冲击仅为嫌疑。**海外需求增长也能造成同样组合。SC、PP、TA 的联动还可能是同一能源成本链，不能当三份独立需求证据；不应把没有原油袖套贡献等同于没有能源成本影响。[Kilian 2009](https://ftp.aeaweb.org/articles?id=10.1257%2Faer.99.3.1053)、[BIS 跨商品传导](https://www.bis.org/publications/qr-202209/commodity-markets-shocks-and-spillovers) |
| **⑥ 多个非原油袖套上涨，同时订单和真实产出改善** | 铜、螺纹、PP、纺织、橡胶、纸浆的窗口收益；上涨袖套占比；PMI 与工业增加值。可同时检查收益相关性，但应使用收益而非价格水平计算。 | 比“只有油涨”更支持广泛复苏，仍只有**中等一致性证据**。共同能源成本、汇率及运输瓶颈也可能造成广泛上涨；六袖套覆盖有限，不能冒称 NHII 全成分广度。[篮子范围](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:25)、[BIS](https://www.bis.org/publications/qr-202209/commodity-markets-shocks-and-spillovers) |
| **⑦ 购进价格明显强于出厂价格，订单走弱、利润或周转恶化** | `CN_PMI_PRICES{purchase_prices,output_prices}`；`CN_PPI{means_of_production,consumer_goods; mom,yoy}`；活动指标；`CN_INDUSTRIAL_FINANCE`、周转指标。 | **支持成本挤压，提示输入性／供给压力。**PMI 两个扩散指数的差不是利润率；PPI 同比回升可能只是基数变化；工业利润是累计且滞后。需求强劲也可能先抬升上游价格。[项目价格与利润成员要求](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:139)、[工业财务成员](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175) |
| **⑧ 国内商品与国际原油背离** | NHII、非原油袖套与 WTI／Brent 的同窗口变化；人民币汇率辅助。油涨而国内工业品弱，提示外部油市冲击；国内非油品强、油弱且国内订单升，较支持中国局部需求改善。 | **只作地域／品种分化附注。**差异可能来自全球与中国周期不同、汇率、原油品质、运输、期现期限。人民币折算只能消除部分币种影响，不能消除市场分割。[BIS 商品与美元研究](https://www.bis.org/publications/working-paper-1083-commodity-prices-and-us-dollar)、[现有价格口径](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:139) |
| **⑨ 商品持续上涨，但新订单先转弱、生产随后放缓、周转恶化** | 活动成员、`CN_ORDER_INVENTORY_SPREAD`、`CN_PRODUCTION_ORDER_SPREAD`、产成品库存与周转。 | **阶段Ⅴ式晚周期也是备选解释。**不能因为需求动量下降就自动归为供给冲击；商品可能滞后于需求拐点。须区分“仍扩张但减速”和“已收缩”。[阶段Ⅴ定义](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:160) |
| **⑩ NHCI 强于 NHII，或纺织袖套异常突出** | 两项指数及 `textiles` 贡献、CF／TA 仓单。可定位到“工业品以外或纺织相关因素需调查”。 | **无法确认天气或农产品供给冲击。**两个加权指数之差不是农产品指数；纺织又混合棉花和 PTA。缺分品种供需与成分归因，最多列 X05 待核查；不得据此突破项目排除生猪的边界。[X05 缺口](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:178)、[商品边界](/mnt/d/cursor/datasourceRF/docs/adr/0002-stable-commodity-core-and-certified-fallback.md) |

计算和时间对齐还需遵守三点：

- **先还原收益，再比较广度。**若袖套日贡献为 \(c_{s,t}\) 个百分点、权重为 \(w_s\)，则袖套日收益为 \(c_{s,t}/(100w_s)\)。窗口收益应逐日复合；不能直接比较 SC 与其他袖套的贡献大小来判断谁涨得更多。若要精确拆解窗口篮子涨幅，可用  
  \[
  C_s=\sum_t\frac{B_{t-1}}{B_0}c_{s,t},
  \]
  此时各袖套贡献之和等于篮子窗口涨幅的百分点。不要用“SC 贡献÷净总贡献”衡量集中度：其他袖套抵消时，该比值会失真。[现行贡献公式](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:243)

- **价格窗口与经济统计期分开。**可展示近 20／60 交易日的袖套变化作为研究观察，但不替代正式 120 日趋势。PMI 通常在当月末发布，工业产出在次月中旬，工业财务与库存通常在次月下旬；春节还有合并期和延期。新一期发布前应是“等待验证”，不能把旧 PMI 自动当成本轮涨价的反证。[统计局发布日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html)、[ADR-0035](/mnt/d/cursor/datasourceRF/docs/adr/0035-metric-horizon-at-most-one-year.md)

- **建议观察最近两次独立月度发布的持续性，但不把“两期”包装成已验证阈值。**所有历史判断应使用当时可见版本；工业季调环比会修订。名义存货用 PPI 简单折算，也只能得到粗略代理，不能冒充真实库存量。[统计局对环比修订的说明](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965308.html)、[项目时间与修订要求](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:221)

**3．数据缺口：最低要求是为目标品种补上实物收支，而不是存在一套通用于所有商品的“三指标答案”。**

若目标是“有条件地识别主要驱动”，至少需要同一市场的**供给数量、使用／需求数量、库存变化**，再结合价格和事件；跨境商品还需贸易流。期限结构可增强紧张程度判断，但不能替代这些数量。供给减少和需求增加并存时，应允许“混合驱动”，并明确采用什么方法判断主次。[EIA 收支框架](https://www.eia.gov/todayinenergy/detail.php?id=53399)、[IMF 结构识别方法](https://www.elibrary.imf.org/view/journals/001/2014/218/article-A001-en.xml)

下表优先级是针对本项目的研究建议：**P1＝优先补充，P2＝第二批／针对异常补充**，不改变仓库现有来源等级。

| 补充数据及作用 | 公开渠道／TuShare 官方文档 | 频率与及时性 | 接入难度、优先级与限制 |
|---|---|---|---|
| **EIA 美国石油实物收支**：商业原油库存（排除 SPR）、SPR、产量、进出口、炼厂原油投入、利用率、汽油／馏分油库存及 product supplied | [WPSR 表1、2、4、7、9，CSV／XLS](https://www.eia.gov/petroleum/supply/weekly/)。网页文件无需账号；API 要 key，批量下载不需要。[授权说明](https://www.eia.gov/opendata/register.php) | 周度；通常周三美东 10:30 发布上周五资料，节假日调整。[日程](https://www.eia.gov/petroleum/supply/weekly/schedule.php) | **低—中，P1。**至少按四周均值看使用量和贸易。周度产量含估算，product supplied 是消费代理。美国覆盖不能外推全球；炼厂停工可能表现为原油累库、成品油去库，必须分开看。[EIA 方法](https://www.eia.gov/todayinenergy/detail.php?id=63184) |
| **OPEC／DoC 实际产量及全球油市平衡**：成员实际产量、非成员供应、全球／区域需求、库存与修订；配套正式产量决定 | [OPEC MOMR，公开报告及 Excel 附表](https://www.opec.org/monthly-oil-market-report.html)；产量表区分机构汇编估计与成员直接报送。[官方产量章节示例](https://publications.opec.org/momr/chapter/140/2607) | 月度，通常次月上中旬报告上月产量；需求和库存的统计期、估计程度各异。 | **中，P1。**为美国以外的供给补缺。**配额／宣布减产≠实际减产**；直接报送与汇编估计应保留不同来源标签。需求预测修订不等于当月实测需求。不能把 OPEC 原油量与全球全部液体燃料量直接相减。 |
| **中国重点商品产量与加工量**：优先原油产量／加工量、粗钢／钢材及相关下游实物产量；细分铜等须核对具体系列 | [统计局能源生产月报](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965312.html)、[工业生产月报及产品产量](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965308.html)、[国家数据](https://data.stats.gov.cn/) | 月度，通常次月中旬；1—2月部分项目合并。数据库更新可能晚于新闻稿约三个工作日。[日程说明](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) | **中，P1。**已有工业增加值总量不能替代。加工量是原料使用证据，但仍不是终端消费；出口、检修与成品库存影响解释。公开标准 TuShare 对应接口本次未核实，优先官方。 |
| **海关重点商品进出口数量**：原油／成品油、铜矿与铜材、钢材、纸浆、橡胶等；保留数量、金额和单位 | [海关重点进口量值表](https://english.customs.gov.cn/Statics/61af7ea9-7882-484e-a2ba-46a74787858f.html)、[月度统计栏目](https://english.customs.gov.cn/statics/report/monthly.html)。公开表不要求账号；本次未核实可直接替代的 TuShare 标准接口。 | 月度；重点表通常次月上中旬，细分统计按实际发布日期，不能统一假定固定一天。 | **中，P1。**进口增加可能用于补库，不能直接当消费。重点表“天然及合成橡胶”“未锻轧铜及铜材”等口径不能直接对应 RU、CU；细分需 HS 匹配。金额／数量是混合单位价值，也不等于恒定品质现货价格。 |
| **同品种近远月期货结算价**：至少两个可比交割月及到期信息 | [TuShare `fut_daily`](https://tushare.pro/document/2?doc_id=138)＋[`fut_basic`](https://tushare.pro/document/2?doc_id=135)，文档当前均列至少 2000 积分；或[交易所日行情](https://www.shfe.cn/reports/tradedata/dailyandweeklydata/)。 | 日度、盘后；供应商入库时间须另验。 | **低—中，P2；工程上容易先做。**现有篮子已使用这些来源，但现有输出不等于拥有完整期限结构。需扩展合约覆盖，固定剩余期限／月份配对，排除交割挤压和无流动性报价。不能由连续主力指数还原完整曲线。 |
| **交易所库存小计与注册仓单分开** | [上期所库存周报](https://www.shfe.cn/reports/tradedata/dailyandweeklydata/)；[TuShare `fut_inv_weekly`，doc_id=495](https://tushare.pro/document/2?doc_id=495)，含 `cur_total`、`cur_futures`，当前列 5000 积分。 | 周度，按交易所发布；TuShare 同步时刻与历史起点未实测。 | **低—中，P2。**可识别“仓单减少但仓库库存未减少”。TuShare 文档明确描述上期所范围，不能默认覆盖全部八品种；库存小计仍不是全社会库存，也不能与其中的仓单再相加。 |
| **现货价格／基差** | [统计局流通领域生产资料价格](https://www.stats.gov.cn/sj/zxfb/202606/t20260603_1963874.html)可补铜、螺纹、PP 等现货方向；真正每日基差仍须取得与交割等级、地点、税费匹配的报价。 | 统计局为旬度，原则上每月4、14、24日发布，节假日例外。[日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html) | **方向对照低—中；严格基差中—高，P2。**全国旬均批发价只能作粗略现货对照，不能冒称交割基差；`fut_daily` 不含所需现货价，仓单接口的 `pd` 也不能当市场即时基差。 |
| **PMI 配送、新出口订单和进口分项** | [TuShare `cn_pmi`](https://tushare.pro/document/2?doc_id=325)：`pmi010600` 配送、`pmi010900` 新出口订单、`pmi011000` 进口；当前列 5000 积分。官方月报可交叉核对。 | 月度，通常当月末；春节可能延期。 | **低，P2，适合低成本扩展。**补 X06。中国官方配送指数低于50表示交付变慢，但需求旺盛同样会拖慢配送，不能单独认定断供；合成 PMI 对配送指数还作反向处理。[统计局配送解释](https://www.stats.gov.cn/sj/zxfb/202303/t20230301_1919136.html) |
| **农业供需与天气**：优先棉花，再按需扩展非生猪粮油品种；产量、单产、消费、贸易、期末库存／库存消费比 | [USDA WASDE](https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report)，公开 PDF、Excel、XML，历史 CSV；同页提供周度天气与作物公报入口。 | WASDE 月度，通常每月上中旬美东12:00；汇总历史 CSV 通常次日更新。数据反映作物年度估计，不是“当月产量”。 | **中，P2；纺织异常时提高优先级。**需区分产量下修和消费上修导致的库存消费比下降。全球报告不能完整刻画国内储备、进口配额和地方天气；WASDE 也不能解释 PTA。 |
| **全球实际活动背景** | [Dallas Fed 全球实际经济活动指数 IGREA](https://www.dallasfed.org/research/igrea)，公开下载。 | 月度更新，实际可见期有滞后，应记录发布日。 | **低，P2；正式做全球结构模型时重要。**填补“中国 PMI 不等于全球需求”的地域缺口。但它来自干散货运价，运输供给与拥堵也会影响它，宜配合全球工业产出等数量指标，不能机械视为纯需求。 |

**国内全社会库存和高频开工率仍是难点。**本次未找到一个符合“公开、权威、无需账号”条件且稳定覆盖 CU／RB／PP／CF／TA／RU／SP／SC 全部品种的统一来源。可确认的公开替代是交易所库存、统计局产品产量及季度行业产能利用率；这些口径不能被重新命名为“社会库存”或“周度装置开工率”。[TuShare 库存覆盖说明](https://tushare.pro/document/2?doc_id=495)、[统计局发布日程](https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html)

**IEA 可作交叉核验，但不宜作为首批免费实时全量源。**其当期完整 OMR 属订阅产品，公开摘要与延迟公开报告不能等同于免费获得当期完整供需历史。TuShare 也应明确区分“文档公开”与“接口调用需 token／积分”；上表权限来自文档，未做账号实测。[IEA OMR 产品说明](https://www.iea.org/data-and-statistics/data-product/oil-market-report-omr)

**4．建议保留正式阶段，将冲击识别作为叙事确认和异常附注。**

项目的正式阶段由股、债、商品核心价格机械决定。因此，即使发现供给型商品牛市，也不应改写阶段Ⅲ／Ⅳ／Ⅴ，而应说明该阶段的典型经济解释获得多少支持。这里的“确认度”是关键经济命题的证据计数，不是阶段正确概率，更不是供需归因概率。[ADR-0001](/mnt/d/cursor/datasourceRF/docs/adr/0001-price-only-formal-pring-stage.md)、[领域定义](/mnt/d/cursor/datasourceRF/GLOSSARY.md:29)

| 建议规则 | 可输出的判断 | 是否计入确认度 |
|---|---|---|
| **只有 NHII、篮子、国际油价上涨，或上涨广度扩大** | “商品价格上涨／上涨扩散”；驱动未确认。 | **只作价格观察。**同类价格、袖套贡献、相关性和广度不新增确认票。[观察接口与价格内部一致性](/mnt/d/cursor/datasourceRF/GLOSSARY.md:41) |
| **订单、采购、生产持续改善，实际工业产出跟进** | “国内实体需求恢复获得支持；与商品上涨相容”。 | **可按原有独立关键指标支持需求／活动命题。**不能再把组合规则计一票，也不能把结论升级为“涨价由需求主导”。[指标成员与阶段Ⅲ要求](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:95) |
| **商品涨而需求成员走弱，成本压力增大** | “需求恢复解释不足；供给、预期或晚周期因素待查”。 | 需求指标在时序允许范围外持续背离，可作**对应经济命题的反证**；“供给嫌疑”本身只作附注。[确认关系与时序定义](/mnt/d/cursor/datasourceRF/GLOSSARY.md:33) |
| **涨价与仓单下降／上升相伴，但缺实物收支** | “注册库存变化”；来源未识别。 | **仓单—价格组合只作附注。**已有库存指标只能支持其自身库存命题，不能据此确认供需归因。[仓单边界](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:150) |
| **补数后，实际供给或到货下降，有独立停产／中断证据，使用量未显示扩张** | 可确认“供给收缩发生”；若时序与市场覆盖吻合，可给出“供给驱动得到较强支持”。 | 可作为阶段Ⅲ“需求型商品上涨”叙事的冲突证据；**确认供给事件不等于确认其解释全部涨幅**。计入方式须由新模型规则明确。[事件识别研究](https://www.aeaweb.org/articles?id=10.1257/aer.20190964) |
| **补数后，真实使用量、订单和生产扩张，供给未见相应收缩，库存收支能解释紧张** | “需求驱动得到较强支持”；限定品种、地域和时间窗口。 | 数量证据可支持相应需求命题，但收支恒等式派生量不能和其组成项重复计数。未排除重大供给／预期冲击时，仍不作排他归因。[EIA 消费代理与收支关系](https://www.eia.gov/tools/Faqs/faq.php?id=1394&t=9) |
| **供给收缩与需求扩张同时存在，或关键数据缺失／过期** | 分别输出“混合驱动”或“未确认”。 | 不强行二选一；缺失不能解释为“没有供给冲击”。[Kilian 2009](https://ftp.aeaweb.org/articles?id=10.1257%2Faer.99.3.1053)、[项目确认关系](/mnt/d/cursor/datasourceRF/GLOSSARY.md:49) |

**首批建议做三项接入任务；每项包含必要字段，不是只补三个标量。**

1. **EIA 周度石油完整收支子集。**一起取得商业／战略库存、产量、进出口、炼厂投入和成品油需求代理。只补“原油库存＋美国原油产量”仍无法区分炼厂检修、出口变化和需求增长。[EIA WPSR](https://www.eia.gov/petroleum/supply/weekly/)

2. **OPEC 月报的实际产量与全球供需背景。**补上美国以外的供应，保留实际产量、政策目标、估计值和预测值的区别；用官方公告解释事件时序。[OPEC MOMR](https://www.opec.org/monthly-oil-market-report.html)

3. **中国原油月度实物流量对照，先做一个品种。**这项明确需要两个官方来源：统计局的原油产量／加工量，海关的原油进出口量及成品油贸易。它能检验国内加工需求是否跟随油价；“国内产量＋净进口−加工量”只能标为含统计差异的库存变化残差，不能称为官方库存。验证口径后再扩到其他工业品。[统计局能源生产](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965312.html)、[海关重点商品量值](https://english.customs.gov.cn/Statics/61af7ea9-7882-484e-a2ba-46a74787858f.html)

这三项优先解决 **X04 能源上涨被误当作国内需求恢复**的问题；不能宣称已经覆盖所有工业品、农业天气和运输冲击。期限结构、交易所库存及 PMI 新分项接入较容易，但它们主要增强预警，无法替代上述实物数量。[X04—X06 的覆盖边界](/mnt/d/cursor/datasourceRF/docs/research/pring-indicator-requirements.md:177)

若以后要求输出“某段上涨中供给冲击贡献多少”，则需要另设结构识别研究，使用多年数据、发布版本和识别稳健性分析。不能在当前约一年以内的辅助指标尺度上直接估计 Kilian 式模型，也不能把篮子价格贡献当成经济冲击贡献；这涉及现行 ADR-0035 的研究与运行边界调整。[ADR-0035](/mnt/d/cursor/datasourceRF/docs/adr/0035-metric-horizon-at-most-one-year.md)、[结构识别研究](https://www.elibrary.imf.org/view/journals/001/2014/218/article-A001-en.xml)
