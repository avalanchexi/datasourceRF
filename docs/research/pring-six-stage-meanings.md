# Martin Pring 六阶段的含义、机制与中国市场落地边界

> 研究日期：2026-08-20  
> 目的：为本项目的 `PringMarketStage` 定义阶段语义和后续识别规范；正式阶段严格限定为 Stage I–VI。  
> 产品边界：本项目输出趋势、阶段、根因证据、反证与风险提示，不输出资产配置权重。  
> 证据边界：仅采用 Martin Pring / Pring Research / Pring Turner、Martin Pring 本人演讲、官方出版社，以及 NBER、中国人民银行、国家统计局的一手或权威资料。文中凡涉及库存与信贷对应阶段的内容，均明确标为“典型环境”或“项目假说”，不冒充 Pring 的阶段定义。

## 一、结论先行

1. **六阶段不是六种宏观经济状态，而是债券价格、股票和商品三类市场主要趋势的六种典型组合。** 一个典型周期中，每类市场各有一个主要底部和顶部，共形成六个边际转折；顺序通常是债券先转、股票次之、商品最后转。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/) 与 [Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)均以此为核心定义。
2. **阶段身份只由三类资产状态确定。** 库存、货币、信贷、增长和通胀用于解释阶段为何出现、判断证据是否一致、识别供给冲击或金融压力等异常原因；它们不应通过加权分数直接改写 Pring 阶段。
3. **“阶段含义”“阶段识别规则”“资产配置含义”是三个不同对象。** 含义是固定的资产状态组合；识别规则是如何把行情判成牛、熊或不确定；配置是识别后的下游决策。Pring Turner 的正式 barometer 是专有模型，公开可复现的简化识别法是三类资产相对各自 12 个月均线的位置。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)
4. **120 个交易日是本项目的中期识别窗口，不是 Pring 官方参数。** 因此每日主模型应诚实命名为 `China 120d Estimate`；另保留月末 `Public Pring 12M Proxy` 作为透明校准基线。
5. **阶段顺序是典型路径，不是硬状态机。** 官方明确说阶段长度不同，可能跳过一个或两个阶段，也可能倒退。[Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/) 因此系统必须允许任何“数据已经确认的典型六阶段组合”出现，不能为了顺时针而篡改资产状态。
6. **严格只输出 I–VI，不等于把所有观测强塞进 I–VI。** 三种二元资产状态共有八种组合，典型六阶段只覆盖六种。Pring 的公开文章把另两种称为 rogue combinations 并另行编号；本项目不采用这些额外编号，而使用 `noncanonical_combination` 识别状态，当前正式阶段留空，并单列“上一确认阶段”。这既满足六阶段产品约束，也不制造错误映射。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)

### 证据等级

为避免把“常见叙事”误写成“阶段定义”，全文采用三档证据：

| 等级 | 含义 | 本文中的内容 |
| --- | --- | --- |
| A：Pring 定义 | Pring/Pring Research/Pring Turner 直接给出的框架事实 | 三资产组合、六个边际转折、典型领先顺序、可跳跃/倒退、公开 12 月均线代理 |
| B：机制证据 | Pring 对经济机制的解释，或 NBER/PBoC/NBS 对库存、信用与统计口径的一手证据 | 流动性—利率—债券、股票预期、商品供需、库存调整、货币政策传导 |
| C：项目待验证假说 | 为中国市场把 B 级机制落到某一阶段的操作化猜想 | 各阶段典型 PMI、库存、社融、M1/M2、PPI 状态及其领先滞后 |

因此下文每阶段的“三资产身份与边际转折”是 A 级；“典型宏观环境”主要是 B 级；“中国库存/信贷在该阶段通常怎样”是 C 级，必须用 point-in-time 中国数据验证后才能升级为正式确认规则。

## 二、先把三个概念彻底分开

### 2.1 阶段含义：固定的三资产环境

阶段含义回答：“此刻债券价格、股票和商品的主要趋势分别是什么？”它是一个环境标签，而不是 GDP、PMI、库存或信贷的加权平均。Martin Pring 本人的 2012 年演讲也把六阶段定义为三类市场主要趋势中的六个转折点；演讲材料将债、股、商品的转折放在理想化经济周期上，但没有把某组宏观指标定义为阶段本身。[CMT Association 的 Martin Pring 演讲与幻灯片](https://cmtassociation.org/video/how-to-use-technical-analysis-to-navigate-the-business-cycle-introducing-the-dow-jones-pring-business-cycle-index-2/)、[官方演讲幻灯片 PDF](https://cmtassociation.org/wp-content/uploads/2024/01/0509-pring-1.pdf)

### 2.2 阶段识别规则：项目必须自定义并验证的 barometer

识别规则回答：“怎样从价格序列判断每类资产是牛、熊还是不确定？”

- Pring Turner 的正式 barometer 综合专有技术指标与跨市场关系，以组件多数的买卖信号判断每类资产牛熊；公开资料没有披露全部组件、参数、权重、平票与缺失处理。[Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)
- Pring Research 公开的简化代理是：长期政府债券**价格**、宽基股票、工业原材料商品分别高于 12 个月均线判牛，低于判熊；官方同时承认均线会 whipsaw，且没有任何均线长度在所有市场和时期都完美。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)
- 2026 年 Pring Research 样刊显示，实务中还参考 12 个月或 65 周均线、长期 KST、相对强弱及其长期动量；这说明“阶段组合”是稳定语义，而“识别 barometer”可以复杂且会演进。[InterMarket Review 官方样刊](https://www.pring.com/sample-imr.pdf)
- 本项目的 30/120 日收益、均线斜率、趋势距离、波动、回撤、滞回带和最短确认期均属于**自定义 barometer**，必须版本化和回测，不能声称是 Pring 专有模型。

### 2.3 资产配置含义：本项目明确不做

Pring 原著《The All-Season Investor》的出版社目录把“跟踪周期”“跟踪阶段”和“资产配置”列为相互关联但不同的章节；Pring Turner 的图示也明确说配置只是一般性示意，不是精确模型。[Wiley 官方出版页](https://www.wiley-vch.de/en/areas-interest/finance-economics-law/the-all-season-investor-978-0-471-54977-2)、[Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)

因此首版输出边界固定为：

```text
三资产状态 -> Pring 阶段 -> 宏观根因/反证 -> 置信度与风险提示
```

不输出股票、债券、商品、现金的配置比例，也不把阶段自动翻译成买卖建议。

## 三、六阶段的严格语义

### 3.1 唯一正式映射

下表中的“牛/熊”均指**主要价格趋势**。债券必须按债券价格或总回报方向判断；只有收益率时要显式反向，不能把“收益率上涨”误写为“债券牛市”。

| 阶段 | 债券价格 | 股票 | 商品 | 进入该阶段的边际转折 | 最简语义 |
| --- | --- | --- | --- | --- | --- |
| Stage I | 牛 | 熊 | 熊 | 利率见顶、债券价格见底转牛 | 通缩/衰退压力下，债券先行修复 |
| Stage II | 牛 | 牛 | 熊 | 股票见底转牛 | 市场开始预期经济触底与恢复 |
| Stage III | 牛 | 牛 | 牛 | 商品见底转牛 | 恢复扩散，周期转向再通胀部分 |
| Stage IV | 熊 | 牛 | 牛 | 债券价格见顶转熊、收益率转升 | 扩张与通胀/信用需求开始压制债券 |
| Stage V | 熊 | 熊 | 牛 | 股票见顶转熊 | 晚周期成本与利率压力开始压制增长预期 |
| Stage VI | 熊 | 熊 | 熊 | 商品见顶转熊 | 需求走弱被商品确认，三资产共同退潮 |
| 回到 Stage I | 牛 | 熊 | 熊 | 债券重新见底转牛 | 新一轮典型顺序开始 |

该顺序直接来自 [Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/) 和 [Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)。

### 3.2 Stage I：债券先于经济与风险资产转强

**阶段身份与转折**

- 组合：`债牛 / 股熊 / 商品熊`。
- 典型进入信号：利率在经济走弱过程中见顶，长期债券价格先见底转牛；股票和商品尚未确认改善。
- Pring 的机制解释是：经济收缩使政策与流动性趋于宽松，利率下降首先支持债券；此时经济和企业消息仍然很差。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)

**典型但非必要的宏观、库存和信用环境**

- 增长：衰退、增长衰退或明显放缓，产出与订单仍弱。
- 通胀：通胀动量下降，商品价格仍处下行主要趋势。
- 库存：销售走弱后出现非意愿库存压力，企业削减新订单与生产，去库存过程启动或加深。
- 货币/信用：政策取向和资金价格可能已转松，但融资需求与信用传导仍弱，信用量未必同步回升。

以上库存描述只能作为典型根因。库存研究表明库存与销售、生产之间存在滞后和持久性，且理论对库存放大还是缓冲总波动没有唯一答案，不能仅凭“库存同比上升/下降”判 Stage I。[Ramey 与 West 的 NBER 综述](https://www.nber.org/papers/w6315)、[Blinder 的 NBER 原始模型](https://www.nber.org/papers/w0460)

**可观测证据**

- 核心：债券价格/总回报的 120 日趋势转正且获得 12 月代理确认；宽基股票和宽基商品趋势仍负。
- 根因：国债收益率趋势回落、资金价格和政策利率方向转松；PMI 新订单和生产仍弱；PPI 与工业原材料价格动量偏弱；库存周转天数上升或产成品库存相对销售偏高。
- 反证：债券上涨只来自短暂避险而利率趋势未变；信用利差急剧扩大；商品广度和 PPI 已持续回升；股票宽度与盈利预期已系统改善。后两项更像 Stage II/III 的前置信号。

### 3.3 Stage II：股票确认触底，商品仍未确认需求恢复

**阶段身份与转折**

- 组合：`债牛 / 股牛 / 商品熊`。
- 典型进入信号：股票见底转牛，加入已经上涨的债券；商品仍熊。
- Pring 将其描述为股票预期下一轮恢复。股票往往在经济消息最差、经济动量接近低点时先于现实数据筑底，因此“经济仍弱”不反驳 Stage II。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)

**典型但非必要的宏观、库存和信用环境**

- 增长：仍处收缩或低位，但边际恶化停止，领先指标先改善。
- 通胀：仍低或继续回落，尚无广泛商品再通胀。
- 库存：去库存后半程；订单可能先于生产改善，产成品库存压力尚未完全消化。
- 货币/信用：宽松的量价条件开始向风险偏好与融资传导；信用脉冲可能企稳，但存量信用增速不一定已明显回升。

**可观测证据**

- 核心：债券与宽基股票 120 日趋势为正、商品为负；股票市场宽度、行业扩散度、成交活跃度和 stock/commodity 相对强弱改善。
- 根因：PMI 新订单环比改善并领先生产；政策利率—DR007—LPR—实际贷款利率链条趋松；社融和贷款的边际变化由弱转稳。人民银行将政策利率、DR007、LPR 和实际贷款利率描述为一条市场化传导链，这正是中国市场应观察“宽松有没有传到信用”的依据。[中国人民银行 2021 年一季度货币政策执行报告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4246985/f13557ddebc344d2951a8c6b24a1ad1b/2021051118023165538.pdf)
- 反证：股票上涨高度集中于少数权重或政策主题；盈利预期、市场宽度和信用传导继续恶化；商品下跌来自供给增加而非需求弱；债券上涨与股票上涨仅是短期流动性交易。

### 3.4 Stage III：商品确认恢复，三资产同时处于上升主要趋势

**阶段身份与转折**

- 组合：`债牛 / 股牛 / 商品牛`。
- 典型进入信号：商品见底转牛，加入债券与股票。
- Pring 的解释是需求与商品供给变得更均衡，经济恢复扩散，周期进入偏通胀的一侧；官方文章把商品/债券相对动量转强视为接近 Stage III 的确认之一。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)

**典型但非必要的宏观、库存和信用环境**

- 增长：经济从底部恢复，需求、生产和利润改善范围扩大。
- 通胀：价格动量由降转稳或回升，但利率压力尚不足以扭转债券价格主要趋势。
- 库存：被动去库存接近结束，企业补充原材料或主动补库存开始；需要订单、生产、库存和周转共同确认。
- 货币/信用：融资条件仍支持扩张，贷款和社融改善，信用由金融体系向实体活动传导。

**可观测证据**

- 核心：三类资产 120 日趋势均为正；商品上涨有工业原材料和品种广度确认，而不是单个能源或贵金属拉动。
- 根因：PMI 新订单、生产、采购量与原材料库存共同改善；PPI 环比/同比方向企稳；工业增加值与盈利改善；信用量和融资价格共同支持恢复。
- 反证：商品上涨由战争、天气、减产等供给冲击单独驱动；股票上涨无宽度或盈利确认；债券上涨来自衰退避险而非良性低通胀；信用仍收缩、订单与生产继续下降。供给冲击型商品牛市不能自动被解释为需求恢复。

### 3.5 Stage IV：债券先转熊，扩张与通胀压力抬升

**阶段身份与转折**

- 组合：`债熊 / 股牛 / 商品牛`。
- 典型进入信号：长期债券价格见顶转熊，收益率转升；股票和商品仍保持牛市。
- Pring 的机制是经济继续增强、信用需求上升、产能趋紧与价格压力增加，从而推高利率并先压制债券。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)

**典型但非必要的宏观、库存和信用环境**

- 增长：较充分扩张，需求和生产仍强。
- 通胀：工业原材料、PPI 或通胀预期上升，政策开始关注价格和杠杆。
- 库存：主动补库存较常见，但接近后段时可能出现销售减速、库存继续累积的背离。
- 货币/信用：信用需求旺盛，市场利率上行；政策可能从宽松转为中性或收紧，但信用量可能仍高。

**可观测证据**

- 核心：债券价格/总回报 120 日趋势负，股票与商品正；12 月代理和收益率方向交叉核验。
- 根因：国债收益率、DR007、LPR 或实际贷款利率向上；PPI、原材料购进价格、商品广度和生产经营活动偏强；信用需求与资本开支改善。
- 反证：收益率上升主要来自财政供给、信用风险或期限溢价，而增长与通胀继续走弱；商品上涨是外部供给冲击；股票仅靠流动性或少数行业维持。Pring Research 自己也举过信用恐慌导致收益率行为偏离一般利率机制的例外，说明“债熊”必须解释其驱动。[InterMarket Review 官方样刊](https://www.pring.com/sample-imr.pdf)

### 3.6 Stage V：股票确认晚周期转弱，商品仍在上涨

**阶段身份与转折**

- 组合：`债熊 / 股熊 / 商品牛`。
- 典型进入信号：股票见顶转熊，加入已经下跌的债券；商品仍保持牛市。
- Pring 的解释是股票提前折现下一轮放缓；较高利率和商品成本逐渐压缩需求与利润，而商品作为滞后市场尚未见顶。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)

**典型但非必要的宏观、库存和信用环境**

- 增长：经济水平可能仍高，但增长动量见顶或下降。
- 通胀：商品和成本压力仍强，价格数据可能保持高位。
- 库存：销售开始慢于预期，库存与应收压力上升；企业由主动补库存逐渐转向被动累库。
- 货币/信用：融资价格高、信用条件边际收紧，信用扩张质量或结构恶化；政策仍可能偏紧。

**可观测证据**

- 核心：债券与宽基股票 120 日趋势负、商品正；股票宽度、周期行业相对强弱、盈利预期和估值承压。
- 根因：PMI 新订单先于生产回落，新订单减库存或新订单减产成品库存恶化；库存周转天数上升；信用脉冲回落、贷款结构转弱、实际融资成本上升。
- 反证：股票下跌只因单一监管、行业或估值事件，而订单、盈利、市场宽度与信用仍全面扩张；商品上涨完全由供给冲击；债券下跌只是短暂供给扰动。

### 3.7 Stage VI：商品确认需求走弱，三资产共同处于下降主要趋势

**阶段身份与转折**

- 组合：`债熊 / 股熊 / 商品熊`。
- 典型进入信号：商品见顶转熊，加入已经下跌的债券与股票。
- Pring 将其置于经济由扩张转向收缩、需求恶化开始压低商品的阶段；随后当债券重新转牛，才进入下一轮 Stage I。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)

**典型但非必要的宏观、库存和信用环境**

- 增长：明显放缓，衰退或增长衰退风险上升。
- 通胀：商品与 PPI 动量下降，但服务通胀或政策利率可能滞后，因此债券未必立刻转牛。
- 库存：被动累库后进入削减订单、生产和库存的调整；去库存尚未完成。
- 货币/信用：信用需求走弱、融资活动降温；政策可能仍在观察，也可能刚开始宽松，尚未足以扭转债券趋势。

**可观测证据**

- 核心：三类资产 120 日趋势均负；商品下跌由工业原材料、能源和品种广度共同确认。
- 根因：PMI 新订单、生产与采购走弱；PPI 与商品动量下降；工业盈利与库存周转恶化；信用量价与传导共同转弱。
- 反证：商品下跌源于供给快速增加而需求、股票和盈利仍强；债券下跌来自通胀或财政风险但信用和增长不弱；任一资产已经形成可靠上升主要趋势。尤其债券确认转牛时，组合已经是 Stage I，而不是“仍在 Stage VI”。

## 四、领先顺序背后的机制，以及它为什么会失效

### 4.1 典型机制

Pring 的原始顺序可以概括为：

```text
经济走弱/流动性转松
  -> 利率见顶、债券价格先见底
  -> 股票预期未来恢复而见底
  -> 需求恢复扩散，商品见底
  -> 信用需求、产能约束和通胀推高利率，债券见顶
  -> 股票预期未来放缓而见顶
  -> 需求真正走弱，商品最后见顶
  -> 下一轮债券见底
```

这条链条来自市场定价速度与经济部门反应速度的不同：债券对利率、通胀与流动性最敏感；股票折现未来盈利并提前反映恢复或放缓；商品更依赖当期或近期的实物供需。Pring 同时指出，信用需求回升会提高资金价格，销售下降快于库存时企业会削减订单，从而把经济推向收缩。[Pring Research Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)

### 4.2 失效或变形的主要原因

1. **周期本来就不是匀速钟表。** 官方明确说领先与滞后会变化，阶段长度不等，增长放缓而非衰退时转折可能加速，阶段可能跳跃或倒退。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)
2. **供给冲击会让商品脱离需求周期。** 战争、天气、减产、运输或制裁可使商品上涨，而增长和信用并未改善；反之，供给扩张可压低商品而需求仍强。此时商品状态仍是阶段输入，但“需求恢复/走弱”的根因解释必须标记为未确认。
3. **信用风险会破坏“经济弱—收益率降—债券涨”的简单链条。** 信用利差可能在衰退期急升，低质量债价格下跌；财政供给和期限溢价也可使无风险收益率上行。官方样刊明确展示过由信用恐慌而非一般利率水平驱动的例外。[InterMarket Review 官方样刊](https://www.pring.com/sample-imr.pdf)
4. **长期结构趋势会改变周期波幅。** Martin Pring 的演讲和样刊都强调世俗趋势会增强顺势的主要趋势、削弱逆势周期，所以同一阶段在不同通胀/利率时代的强度和持续时间可能不同。[Martin Pring 官方演讲幻灯片](https://cmtassociation.org/wp-content/uploads/2024/01/0509-pring-1.pdf)、[InterMarket Review 官方样刊](https://www.pring.com/sample-imr.pdf)
5. **库存关系不是一个固定四象限。** NBER 原始研究区分产出、最终销售、库存水平和库存变化，并发现库存有持久性；不同模型甚至对库存究竟放大还是缓冲总波动给出不同答案。[Blinder 1980](https://www.nber.org/papers/w0460)、[Ramey 与 West 1997](https://www.nber.org/papers/w6315) 因此 PPI 同比与产成品库存同比只能是摘要，不是阶段真值。
6. **金融周期与商业周期不同步。** 人民银行工作论文以私人部门信贷/GDP 衡量金融周期，并把高涨、衰退和正常期另行识别；其跨国证据还指出过热与过冷都可能伴随较低增长和较高金融风险。该论文明确声明只代表作者研究观点，但足以说明信用状态不能机械映射到某个 Pring 阶段。[中国人民银行工作论文 No.2016/5](https://www.pbc.gov.cn/yanjiuju/fileDir/resource/cms/2016/04/2016040818085153098.pdf)
7. **识别方法会产生 whipsaw。** Pring 的公开 12 月均线法也会短期来回翻转；120 日窗口更短，更需要滞回、持续期和阈值距离，但具体参数必须用中国历史做时间外验证。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)
8. **数据发布时间和修订会制造假历史。** 月度或季度宏观数据只能从真实发布日期起参与解释；不能把所属月份当作当时已知。发布前沿用上一期并标 `awaiting_release`，超过新鲜度阈值才转 `stale`。

## 五、中国市场：可以直接移植与必须自定义的部分

### 5.1 可以直接移植

- 三类资产的语义顺序与六种正式组合。
- 债券按价格/总回报方向、不能按收益率同号判断。
- 阶段由资产 barometer 派生，库存与信用只作根因、确认或反证。
- 阶段长度不等，允许跳跃、倒退和乱序。
- `Public Pring 12M Proxy` 的透明校准思想：月末比较三类资产与各自 12 个月均线。
- 阶段环境与识别算法分版本保存，不能把自定义参数冒充理论定义。

### 5.2 必须为中国市场自定义并验证

1. **资产代理。** 债券要选择可长期回放的中国国债价格/总回报代理；股票要选择宽基且成分规则稳定的代理；商品要冻结宽基商品指数或期货连续合约的换月、复权和权重规则。
2. **120 日 barometer。** 30/120 日收益、均线、斜率、回撤、波动、阈值、滞回、最短持续期和 `uncertain` 规则都是项目参数。
3. **政策与信用传导。** 中国应按政策利率、DR007、LPR、实际贷款利率、M1/M2、社融和贷款结构观察量价传导，而不是把美国政策利率经验直接搬来。人民银行还明确说明结构性工具会定向引导信贷资源，意味着总量宽松和结构传导可能背离。[中国人民银行货币政策执行报告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4246985/f13557ddebc344d2951a8c6b24a1ad1b/2021051118023165538.pdf)
4. **商品根因。** 中国商品价格同时受到全球美元、海外供给、汇率、国内地产与基建需求、期货换月影响；必须用工业原材料广度与国内订单交叉验证，不能让黄金或原油单品支配商品 barometer。
5. **股票根因。** 政策、风险溢价、行业集中度和制度变化可能让股票提前量不稳定；需要宽度、行业扩散度和盈利预期反证。
6. **库存引擎。** 国家统计局 PMI 是经季调的月度环比扩散指标，50 是扩张/收缩临界点；产成品库存指数高于 50 表示环比上升。它不能与产成品存货名义余额同比直接混算。[国家统计局 PMI 官方问答](https://www.stats.gov.cn/hd/cjwtjd/202302/t20230207_1902267.html)
7. **工业库存口径。** 产成品存货周转天数是库存相对营业成本的比率型指标，规上工业调查范围也会调整；优先使用官方可比同比与官方周转指标，不要用两个不可比余额自行重算。[国家统计局工业企业指标说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202007/t20200727_1778653.html)
8. **价格口径。** PPI 反映工业品首次出售时的出厂价格总体变化，是价格证据，不等于实物需求或库存数量。[国家统计局 PPI 指标解释](https://www.stats.gov.cn/zs/tjws/tjzb/202301/t20230101_1903637.html)

## 六、指标频率与 120 日分析视角

“120 日”是统一分析视角，不是要求所有指标都变成 120 条日数据。

| 指标类别 | 原始频率 | 在 120 日视角中的处理 | 发布期约束 |
| --- | --- | --- | --- |
| 债券、股票、商品行情 | 日频 | 当日、30 交易日、120 交易日趋势与转折 | 收盘并完成数据源更新后可用 |
| PMI 及分项 | 月频 | 使用 120 自然日内约 4 次发布，分析方向、连续改善/恶化与分项背离 | 国家统计局说明通常在调查月最后一天 9:30 发布；发布前沿用上一期 |
| PPI、工业增加值、工业利润与库存 | 月频/累计月频 | 最新、上期、环比、官方可比同比和 120 日内发布轨迹 | 仅从实际发布日期起可用；修订与调查范围变化要留版本 |
| M1/M2、社融、贷款、LPR | 月频或事件频 | 最新、上期、同比/增量、量价传导和结构变化 | 使用人民银行实际发布时点；未发布时沿用上一期并标等待 |
| GDP 等 | 季频 | 120 日内通常只有 1–2 次发布，用最新与上期/同比/环比解释 | 不重复按日增加权重 |

国家统计局说明 PMI 为月度、经季调、反映本月相对上月变化，并通常于月末发布。[国家统计局 PMI 官方问答](https://www.stats.gov.cn/hd/cjwtjd/202302/t20230207_1902267.html) 因此所有低频指标都应采用阶梯式状态：新值只在发布时改变状态，之后只是“沿用最新有效值并增加数据年龄”，不能每天重复制造一条新证据。

## 七、每阶段的证据结构：核心、根因、反证必须分栏

Web 页面和模型产物对每一阶段都应保留三组独立证据：

```text
core_evidence
  bond_barometer
  stock_barometer
  commodity_barometer

root_cause_evidence
  growth
  inflation
  inventory
  money_and_credit

counter_evidence
  supply_shock
  credit_stress
  market_breadth_conflict
  data_freshness_or_revision
```

- `core_evidence` 决定阶段身份。
- `root_cause_evidence` 解释为何形成，并影响根因置信度。
- `counter_evidence` 指出“资产组合虽然成立，但常见经济解释可能不成立”。
- 宏观根因与资产阶段背离时，页面应显示背离，不能让宏观指标覆盖三资产结果。

## 八、严格六阶段输出时的异常处理

### 8.1 推荐状态字段

```text
bond_state / stock_state / commodity_state  # bull | bear | uncertain
observed_combo                              # 原样保存三资产状态
stage_status                                # confirmed | pending_confirmation |
                                            # noncanonical_combination |
                                            # insufficient_data
current_confirmed_stage                     # I..VI | null
last_confirmed_stage                        # I..VI | null，仅历史信息
candidate_stages                            # 仅从 uncertain 的可能取值机械枚举
reason_codes
as_of / data_snapshot_id / model_version
```

### 8.2 处理规则

1. 三个资产 barometer 独立计算，不得先猜阶段再回填资产方向。
2. 只有完整、足够新鲜且精确命中六种正式组合时，才产生 Stage I–VI 的 `observed_stage`。
3. `observed_stage` 经过待验证的持续期或阈值距离规则后，成为 `current_confirmed_stage`。持续多少交易日、阈值多大属于模型参数，不能从 Pring 理论臆造。
4. 任一资产为 `uncertain` 时，`current_confirmed_stage = null`，状态为 `pending_confirmation` 或 `insufficient_data`；可机械枚举与已知资产方向一致的六阶段作为候选，但不得选最近阶段强行填充。
5. 对两种未被典型六阶段覆盖的完整二元组合，状态为 `noncanonical_combination`，`current_confirmed_stage = null`。产品不引入 Stage VII/VIII，也不把它们映射为 I–VI。
6. `last_confirmed_stage` 可以展示，但必须写成“上一确认阶段”，不能伪装成当前阶段。
7. 新的完整组合即使跳阶段或倒退，也按证据确认；同时记录 `transition_type = sequential | skip | retrograde`，不阻止转换。
8. 库存、信用或 AI 文字分析不能把 `null` 补成某个阶段；它们只能解释候选与冲突。

这种做法遵守“正式阶段只允许 I–VI”，同时尊重 Pring 官方对非典型组合、跳阶段和倒退的事实描述。[Pring Research Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)、[Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)

## 九、供下一轮确认的阶段语义与转换条件草案

### 9.1 正常单边转换

| 当前阶段 | 下一典型阶段 | 唯一边际转折 | 转换后组合 | 根因确认只做什么 |
| --- | --- | --- | --- | --- |
| VI | I | 债券由熊转牛 | `债牛 / 股熊 / 商品熊` | 解释利率、通胀和流动性是否支持，不决定阶段 |
| I | II | 股票由熊转牛 | `债牛 / 股牛 / 商品熊` | 解释增长预期、宽度、信用传导是否改善 |
| II | III | 商品由熊转牛 | `债牛 / 股牛 / 商品牛` | 排除单品和供给冲击，判断恢复是否扩散 |
| III | IV | 债券由牛转熊 | `债熊 / 股牛 / 商品牛` | 区分增长/通胀/信用需求与财政/风险溢价冲击 |
| IV | V | 股票由牛转熊 | `债熊 / 股熊 / 商品牛` | 判断晚周期放缓还是股票特有冲击 |
| V | VI | 商品由牛转熊 | `债熊 / 股熊 / 商品熊` | 判断需求走弱还是供给增加导致商品下跌 |

### 9.2 转换判定草案

```text
输入：三个独立资产 barometer、数据新鲜度、模型版本

1. 计算当日 observed_combo。
2. 若任一状态 uncertain 或数据超龄：不确认阶段。
3. 若组合不在 I–VI 映射表：标 noncanonical_combination，不确认阶段。
4. 若组合在 I–VI：生成 observed_stage。
5. 只有达到预先冻结、经时间外验证的确认条件，才更新 current_confirmed_stage：
   - 连续确认期 N（待回测）；和/或
   - 越过滞回带的趋势距离 H（待回测）；
   - 不存在关键数据质量失败。
6. 记录从 last_confirmed_stage 到新阶段是 sequential、skip 还是 retrograde；三者均允许。
7. 库存、货币/信用、增长、通胀生成 root_cause_confidence 和 counter_evidence，
   但不参与第 3–5 步的阶段映射。
```

### 9.3 建议用户下一轮明确确认的五项

1. 是否接受“当前正式阶段可以为空，但上一确认阶段仍展示”，以避免非典型组合被强映射？
2. 中国债券核心代理是总回报指数、净价指数，还是用 10 年国债收益率反向近似？
3. 中国股票核心代理选哪个宽基，是否用市场宽度只作 barometer 内部确认？
4. 中国商品核心代理及期货连续合约换月规则如何冻结？
5. 120 日主模型的 `N`（持续期）和 `H`（滞回带）用哪段历史做开发、验证和完全未见测试？

## 十、来源清单与证据限制

本研究使用 13 个核心一手/权威来源：

1. [Pring Research：Business Cycle Part 1](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)
2. [Pring Research：Business Cycle Part 2](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)
3. [Pring Turner：Approach to Business Cycle Investing](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)
4. [Martin Pring 2012 年 CMT 演讲页面](https://cmtassociation.org/video/how-to-use-technical-analysis-to-navigate-the-business-cycle-introducing-the-dow-jones-pring-business-cycle-index-2/)
5. [Martin Pring 2012 年官方演讲幻灯片](https://cmtassociation.org/wp-content/uploads/2024/01/0509-pring-1.pdf)
6. [Pring Research：2026 年 InterMarket Review 样刊](https://www.pring.com/sample-imr.pdf)
7. [Wiley：《The All-Season Investor》官方出版页](https://www.wiley-vch.de/en/areas-interest/finance-economics-law/the-all-season-investor-978-0-471-54977-2)
8. [NBER：Ramey & West, Inventories](https://www.nber.org/papers/w6315)
9. [NBER：Blinder, Inventories in the Keynesian Macro Model](https://www.nber.org/papers/w0460)
10. [中国人民银行工作论文：金融周期和金融波动如何影响经济增长与金融稳定](https://www.pbc.gov.cn/yanjiuju/fileDir/resource/cms/2016/04/2016040818085153098.pdf)
11. [中国人民银行：2021 年一季度货币政策执行报告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4246985/f13557ddebc344d2951a8c6b24a1ad1b/2021051118023165538.pdf)
12. [国家统计局：PMI 官方问答](https://www.stats.gov.cn/hd/cjwtjd/202302/t20230207_1902267.html)
13. [国家统计局：工业企业指标与调查说明](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202007/t20200727_1778653.html)

国家统计局 [PPI 指标解释](https://www.stats.gov.cn/zs/tjws/tjzb/202301/t20230101_1903637.html) 作为补充口径资料使用，未计入上述 13 个核心来源。

最重要的限制是：公开资料足以定义六阶段语义和一套 12 月均线代理，但不足以复刻 Pring Turner 专有 barometer。库存、货币与信用对每阶段的描述是待中国数据验证的解释层，不是官方六阶段的组成公式。
