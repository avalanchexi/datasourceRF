# Martin Pring 六阶段：公开可复现边界、历史锚点与中国市场验证规范

> 研究日期：2026-08-20  
> 研究范围：只回答 Pring 六阶段本身如何定义、公开算法到哪里为止、有没有可核验的官方历史阶段序列，以及新项目应如何建立不循环的中国市场验证锚点。库存周期和货币/信贷周期的指标体系另见现有研究文档，本篇不重复展开。  
> 来源约束：优先采用 Pring Research、Pring Turner、Martin Pring 本人公开演讲与文章、官方出版社页面；指数与基金事实用 Dow Jones 原始发布材料和 SEC 文件核验。  
> 结论性质：模型设计与验证输入，不是投资建议。

## 一、先给结论

1. **六阶段的定义可公开复现，Pring Turner 的正式 barometer 不可公开复刻。** 六阶段只是债券、股票、商品三类资产“牛/熊”组合的六个典型顺序；正式 barometer 的完整组件、参数和信号细节仍是专有信息。Pring Research 同时公开了一套可复现的简化代理：分别比较长期政府债价格、宽基股票、工业原材料商品与各自的 **12 个月均线**。
2. **六阶段并没有覆盖三种二元状态的全部组合。** Pring 本人把“只有股票为牛”命名为 Stage VII，把“只有股票为熊”命名为 Stage VIII，并称二者为不可归入典型六阶段的 rogue stages；公开研究称两者合计出现时间不到 12%。因此，旧项目若把任意资产组合强制塞进 Stage 1–6，理论上就已经丢失信息。
3. **公开资料没有给出可下载、逐月、连续、可复算的官方阶段序列。** 能找到的是若干官方文章、客户活动、监管报告和当期样刊中的离散快照，以及汇总绩效表和带颜色的历史图。它们足以核验个别美国市场日期与阶段语义，但不能成为中国市场的完整监督标签。
4. **120 个交易日不是 Pring 的公开标准。** 公开简化法使用 12 个月均线；正式 barometer 还会结合长期动量和跨市场关系。120 交易日大约只有半年，适合本项目的“中期”目标，但名称必须是 `Pring-inspired 120d`，不能称为 Pring 原模型。
5. **Neutral/Uncertain 必须保留为一等状态。** Pring 的典型图是二元状态，公开规则没有定义“刚好 50%”“恰好等于均线”或快慢信号冲突时如何裁决。项目引入 `uncertain` 是合理且必要的工程扩展，但不应假装它来自原始六阶段。
6. **阶段可以跳跃、倒退或进入 VII/VIII。** 官方明确提醒阶段可能乱序、跳过，甚至倒退；正确做法是记录这些转移并降低置信度，而不是用只准顺时针的状态机修改事实。

## 二、六阶段的原始公开定义与转折顺序

Martin Pring 把商业周期中的三个金融市场各自划分为主要上升趋势和主要下降趋势。每个市场有一个底部和一个顶部，因而形成六个典型转折。Pring Research 的作者本人说明按以下顺序定义阶段：[Part 1：金融市场转折顺序](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-1/)、[Part 2：六阶段及识别方法](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)。

| 阶段 | 债券价格 | 股票 | 商品 | 进入该阶段的典型转折 |
| --- | --- | --- | --- | --- |
| Stage I | 牛 | 熊 | 熊 | 利率见顶、债券价格先见底转牛 |
| Stage II | 牛 | 牛 | 熊 | 股票见底转牛 |
| Stage III | 牛 | 牛 | 牛 | 商品见底转牛 |
| Stage IV | 熊 | 牛 | 牛 | 债券价格见顶转熊 |
| Stage V | 熊 | 熊 | 牛 | 股票见顶转熊 |
| Stage VI | 熊 | 熊 | 熊 | 商品见顶转熊 |
| 回到 Stage I | 牛 | 熊 | 熊 | 债券再次见底转牛，新一轮开始 |

这个表描述的是**金融市场主要趋势**，不是 GDP、库存或信贷指标的六种组合。Pring Turner 的公开总览同样明确：Stage I 是 `债牛/股熊/商品熊`，Stage II 是 `债牛/股牛/商品熊`，Stage III 三者皆牛，Stage IV–VI 依次反转；阶段从经济放缓时债券筑底开始，到商品最终见顶结束。[Pring Turner 官方六阶段说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)

### 六阶段之外还有两个二元组合

三类资产各自只有牛/熊时，数学上共有 `2³ = 8` 种组合，典型六阶段只占六种。Pring Research 在公开识别文章中明确列出另两种：[12 个月均线法与 Stage VII/VIII](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)。

| 状态 | 债券 | 股票 | 商品 | 官方公开称呼 |
| --- | --- | --- | --- | --- |
| 非典型组合 1 | 熊 | 牛 | 熊 | Stage VII：只有股票为牛 |
| 非典型组合 2 | 牛 | 熊 | 牛 | Stage VIII：只有股票为熊 |

官方文章把 VII/VIII 称为不可分类的 rogue stages，并称二者合计不到历史时间的 12%。这带来两个直接工程约束：

- `(-, +, -)` 不能“就近”改写成 Stage II 或 IV；`(+, -, +)` 也不能改写成 Stage I、III 或 V。
- 如果项目坚持产品界面只展示 1–6，应在内部仍保存 `noncanonical_7` / `noncanonical_8`，页面显示“非典型组合”，不能篡改底层资产状态。

### 顺序是参考，不是硬约束

官方说明同时强调：不同周期的领先/滞后长度不相同；阶段可能乱序、跳过一个或两个，甚至退回前一阶段。Pring Research 进一步建议把阶段视为“环境定义”，用市场行为反向核验当前判断，而不是教条地假定下一阶段一定顺时针到来。[Pring Research 的 “trust but verify” 说明](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)、[Pring Turner 对跳跃和倒退的说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)

因此，`Stage II → Stage IV`、`Stage IV → Stage III` 在数据上都可以成立；系统应将其分别标为 `skip`、`retrograde` 并解释原因，而不是拒绝这次状态变化。

## 三、bull/bear 判据公开到什么程度

### 1. 正式 barometer：只公开总体结构与多数边界

Pring Turner 公开说明每个资产各有一个模型或 barometer，由技术指标和跨市场关系组成；当组件中**多数**为买入信号时，资产判为 bullish，多数为卖出信号时判为 bearish。[Pring Turner 官方说明](https://www.pringturner.com/pring-turner-approach-to-business-cycle-investing/)

公开当期样刊可以确认部分构造思路，但不能还原全部公式：2026 年 4 月样刊披露股票模型从 100% 降至 83%，原因包括股票/商品比率和 S&P 长期 KST 转熊；它还使用 12 个月或 65 周均线、长期 KST、相对强弱及其长期 KST。样刊同时把完整阶段模型称为 barometer，并把三市场相对各自 12 个月均线的方法称为 “poor man model”。[Pring Research 2026 年 4 月 InterMarket Review 样刊](https://www.pring.com/sample-imr.pdf)

Pring 本人对长期 KST 的说明也强调：它把多个不同周期的平滑 ROC 合成，以降低假信号，代价是信号变慢；KST 仍可能在单边线性趋势中给出过早或错误信号，而且动量信号应由价格趋势反转确认。[Pring Research：Long-term KST](https://www.pring.com/long-term-kst/)

以下细节在本次可访问的官方公开材料中**没有完整披露**：

- 三个正式 barometer 各自全部组件的名单、方向变换与数据源；
- 每个组件的参数、权重、缺失处理、修订规则；
- `50%` 恰好平票时的统一处理；
- 信号是否需要持续若干期、是否使用滞回带；
- 1955 年以来每次组件变化和最终阶段的逐月机器可读数据。

公开措辞对边界还存在需要谨慎处理的细微差异：2016 年总览使用“多数”这一严格概念；2023 年客户活动用“高于 50 为正、低于 50 为负”；2025 年商品文章则把“50% 或以上”描述为 bullish。[2023 年客户活动](https://www.pringturner.com/2023-summer-client-event-summary/)、[2025 年商品/通胀文章](https://www.pringturner.com/there-is-an-eighth-member-of-the-fomc-and-his-name-is-mr-market/)。这不足以推断正式模型在精确等于 50 时的专有实现。

### 2. 公开可复现的简化法：12 个月均线

Pring Research 为非订阅者公开了一个明确、可复现的替代方法：[Identifying the Stages Using Moving Averages](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)。

- 债券代理：长期政府债券**价格**；
- 股票代理：S&P Composite；
- 商品代理：CRB Spot Raw Industrials，无法取得时可用 CRB Composite；
- 每个市场高于自身 12 个月均线即 bullish，低于即 bearish；
- 三个资产状态按前述八种组合映射到 Stage I–VIII。

Pring 明确说不存在对所有市场、所有时期都完美的均线长度，只是 12 个月总体测试较好，也仍会产生 whipsaw；使用该简化法时，阶段乱序并不罕见。这套规则是最适合新项目建立“公开 Pring 基准线”的方法，但它不是专有 barometer 的复刻。

### 3. 公开的第二类近似：跨资产长期动量

同一篇官方文章还用平滑长期 KST 观察债券/商品、股票/商品、商品/债券等跨资产比率，以提前观察 Stage I、II、III 附近的转折；文章明确把这些信号描述为对正式模型阶段的**近似**，并承认例外和假信号。[Pring Research：Inter-Asset Momentum](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)

所以公开资料允许新项目实现两种诚实命名的东西：

1. `Pring public 12M-MA proxy`：可复现的官方公开简化法；
2. `Pring-inspired custom barometer`：把公开思想适配到中国市场和 120 交易日目标的自有实现。

不能诚实声称的是：仅凭公开网页就复刻了 `Pring Turner proprietary barometer`。

## 四、是否有可核验的历史阶段日期或公开序列

### 公开可核验的离散快照

本次调查找到以下一手或监管存档快照。日期是文章/报告明确给出的 `as of` 或发布日期，不应再向前回填：

| 时点 | 公开判断 | 能核验的内容 | 来源 |
| --- | --- | --- | --- |
| 2012-03 至 2013-01-25 | Stage II | 2013 年 1 月文章称自 2012 年 3 月起处于 Stage II，并接近 III 或 IV | [Pring Turner 2013 年 1 月评论](https://www.pringturner.com/new-year-new-milestones-same-investment-challenges/) |
| 2013-07-15 | Stage IV | 文章明确把当时环境定义为 Stage IV | [Pring Turner 2013 年 7 月评论](https://www.pringturner.com/volatility-resumes-whats-next-for-investors/) |
| 2014-01-16 | Stage IV | 文章称其周期工作继续指向 Stage IV，但商品价格尚未完全配合 | [Pring Turner 2014 年展望](https://www.pringturner.com/2013-a-surprising-year/) |
| 2014-06 | Stage IV | DBIZ 基金年度报告称截至 2014 年 6 月，专有阶段工作处于 Stage IV | [SEC EDGAR 2014 年年度报告](https://www.sec.gov/Archives/edgar/data/1408970/000114420414054452/v384013_ncsr.htm) |
| 2015-06 | Stage II | DBIZ 基金年度报告称截至 2015 年 6 月，专有阶段工作处于 Stage II | [SEC EDGAR 年度报告](https://www.sec.gov/Archives/edgar/data/1408970/000114420415058933/v421751_ncsra.htm) |
| 2020-01-06 | 接近 Stage III | 官方文章给出债券 2018-10 见底、股票 2018-12 见底，下一候选转折为商品低点；标题和正文只说“接近 III”，不宜改写成已确认 III | [Martin Pring 2020 年文章](https://www.pringturner.com/business-cycle-stage-3-which-market-bullish-for/) |
| 2023-06-16 | Stage II | 债券和股票 barometer 为正、商品/通胀 barometer 为负 | [Pring Turner 2023 客户活动](https://www.pringturner.com/2023-summer-client-event-summary/) |
| 2024-08-07 | Stage IV | 债券负、股票和通胀 barometer 正 | [Pring Turner 2024 年中展望](https://www.pringturner.com/2024-mid-year-outlook/) |
| 2025-02-05 | Stage III，近期曾在 III/IV 间切换 | 三个模型均 bullish；文章称 1 月债券模型几乎使其转为 IV，过去一年曾数次在 III/IV 间切换 | [Martin Pring 2025 年文章](https://www.pringturner.com/why-a-firming-in-the-cpi-may-be-closer-than-you-think/) |
| 2025-09-10 | Stage IV | 文章明确称专有模型当前处于 Stage IV，商品 barometer 月末为 100% | [Martin Pring 2025 年 9 月文章](https://www.pringturner.com/there-is-an-eighth-member-of-the-fomc-and-his-name-is-mr-market/) |
| 2026-03-31 / 2026-04 样刊 | Stage IV | 股票和商品正、债券负；样刊署名日期 3 月 31 日 | [Pring Research 2026 年 4 月样刊](https://www.pring.com/sample-imr.pdf) |

这些快照有三个用途：

- 检查阶段组合映射是否写对，例如 `债负/股正/商品正 → Stage IV`；
- 验证项目是否正确表达“接近”“切换”“尚未确认”，而不是把候选当真值；
- 作为美国市场的外部语义参考，比较公开 12 个月均线代理与官方专有快照的差异。

它们**不能**直接作为中国市场真值，也不能由发布日期之间的空白推断每一个月的阶段。

### 没有发现连续、机器可读的官方阶段序列

截至研究日，在以下公开范围内没有找到包含 `date, bond_state, stock_state, commodity_state, stage` 的连续官方 CSV、表格或 API：

- Pring Turner 官方公开文章目录及其公开站点索引；
- Pring Research 的公开文章、当前 InterMarket Review 样刊和产品页；
- Martin Pring 2012 年为 CMT Association 所作演讲及幻灯片；
- Dow Jones Pring 指数发布材料和 DBIZ 的 SEC 文件。

搜索边界可由官方公开入口复核：[Pring Turner 文章站点地图](https://www.pringturner.com/post-sitemap.xml)、[Pring Research 文章入口](https://www.pring.com/articles/)、[InterMarket Review 产品说明](https://www.pring.com/shopsite_sc/store/html/page5.html)。

官方确实公开过历史汇总而非日期序列：

- 2026 样刊称 Stage IV 在 1950 年代中期至 2011 年共有 32 次信号、平均持续 6.8 个月，但没有列出每次起止日。[InterMarket Review 样刊](https://www.pring.com/sample-imr.pdf)
- Martin Pring 的 2012 CMT 演讲展示了债券、股票、商品 barometer 的历史着色图和 1956–2012 年 DJPRING 表现图，但幻灯片没有给出可下载的逐月阶段表。[CMT Association 演讲与官方幻灯片](https://cmtassociation.org/video/how-to-use-technical-analysis-to-navigate-the-business-cycle-introducing-the-dow-jones-pring-business-cycle-index-2/)
- Dow Jones 2012 年发布的 DJPRING 是按专有策略动态配置资产的指数；发布材料说明按月响应模型信号再平衡，却没有公开阶段字段。[Dow Jones Indexes 原始发布稿](https://www.globenewswire.com/news-release/2012/03/14/470794/4127/en/Dow-Jones-Indexes-to-Launch-Dow-Jones-Pring-U-S-Business-Cycle-Index.html)
- SEC 招股材料也把该指数描述为基于专有模型；指数点位或基金净值是配置后的结果，不等于阶段标签，无法从单一指数值反推出当月三个 barometer。[SEC EDGAR：DBIZ 招股材料](https://www.sec.gov/Archives/edgar/data/1408970/000114420412021453/v309294_485apos.htm)

严格结论是：**本次检索没有发现可作为 Q12 完整真值的公开官方序列；只能找到稀疏的美国市场官方快照。** 不能把“未发现”写成“世界上绝对不存在”，但在取得付费历史数据或 Pring Research 授权前，新项目不应假设有这样一套免费真值。

## 五、如何为中国市场建立非循环的人工锚点

### 先分清三种基准

| 基准 | 生成方法 | 用途 | 是否是中国阶段真值 |
| --- | --- | --- | --- |
| 公开规则基准 | 中国三类资产相对 12 个月均线的位置 | 检查公开 Pring 代理是否实现正确 | 否，是透明规则输出 |
| 人工锚点 | 人工只看时点前原始资料，独立标注三资产主要趋势 | 评估自有 120d 模型是否符合人的可解释判断 | 是，属于项目约定真值 |
| 事后结果 | 标签后 20/60/120 日收益、回撤、相对表现 | 衡量标签后的经济/投资结果 | 否，只能评价，不能生成标签 |

把公开 12 个月均线规则产生的标签再拿来证明自己的均线模型“准确”，属于循环验证；用未来 120 日收益决定今天是牛还是熊，则属于前视偏差。两者都不能回答改版后为什么不准。

### 推荐人工锚点协议

1. **冻结资产代理和时点。** 先选定一个可回放的中国长期政府债价格/总回报代理、一个宽基股票代理、一个规则稳定的宽基商品代理。每个锚点都有唯一 `as_of`，只允许使用当时已收盘、已发布的数据版本。
2. **只给标注者看截至 `as_of` 的原始证据。** 不展示旧模型、新模型、30/120 分数、候选阶段或未来收益。月度宏观资料必须按真实发布日期截断。
3. **先独立标三类资产，不直接猜阶段。** 至少两名标注者分别给债券、股票、商品标 `bull / bear / uncertain`，同时记录转折是否已确认、依据和置信度。债券必须按**债券价格/总回报**方向标注，不能把收益率上涨误当债券牛市。
4. **阶段机械派生。** 三个资产均为二元且组合属于典型六种时，机械映射 Stage I–VI；落入另两种组合时标 Stage VII/VIII；任一资产为 `uncertain` 时不强制生成确定阶段，只给候选集合。
5. **库存和货币/信贷另行标注。** 它们用来解释“为什么市场出现这个阶段”以及证据是否一致，不参与人工 Pring 阶段标签本身。否则再用库存/信贷模型去验证同一个混合标签，会再次形成循环。
6. **分歧由第三人盲审。** 第三人可看匿名理由和同一时点资料，但仍不能看模型输出和未来数据。保留原始分歧，不能只保存最后多数票。
7. **锚点抽样防止挑案例。** 主评估集采用固定月末网格或预先随机抽样；转折点附近和已知误判日期另建 `edge_case` 集。两套结果分开报告，不能只展示最容易证明新版更好的日期。
8. **在测试前冻结规则。** 开发、验证、完全未见测试期按时间分割。阈值、滞回和持续天数只在开发/验证期选择，最终测试期只运行一次。

建议每条人工锚点至少保存：

```text
anchor_id
as_of
data_snapshot_id
bond_label / stock_label / commodity_label
derived_stage                 # I-VIII / uncertain
candidate_stages
annotator_id
annotated_at
evidence_urls
rationale
confidence
adjudication_status
model_outputs_hidden = true
future_data_hidden = true
```

### Q12 应如何落地

Q12 不应再要求用户先凭记忆报出三个“正确阶段”。更可靠的流程是：

1. 从旧报告中抽取改版前后全部阶段变更日期；
2. 再加入固定月末样本和几段显著市场转折窗口；
3. 用上述盲标协议形成至少一批人工锚点；
4. 最后才揭示旧版、新版输出，逐项比较错误来自数据、单资产状态、组合映射还是阶段稳定机制。

官方美国快照可以作为映射单元测试和研究参考，但不能代替这套中国市场人工锚点。

## 六、旧项目相关的理论与工程边界

### 1. Neutral / Uncertain

Pring 的公开典型阶段使用 bull/bear 二元语言；公开材料没有定义第三类 Neutral，也没有可靠披露正式 barometer 在严格平票时如何处理。项目可以并且应该增加 `uncertain`，但要明确它是工程扩展。

最低约束如下：

- 类型必须是显式枚举，禁止 `bool("Neutral")`、`bool(None)` 或把非 Bullish 一律当 Bearish；
- `uncertain` 表示“当前证据不足以改变主要趋势判断”，不是零收益、横盘或资产配置中性的同义词；
- 任一资产 `uncertain` 时同时输出 `last_confirmed_state`、`candidate_state` 和原因；
- Stage VII/VIII 与 `uncertain` 不同：VII/VIII 是三个状态都很明确、但组合非典型；`uncertain` 是至少一个资产方向尚未确认。

### 2. 30 / 120 交易日窗口

Pring 的公开简化基准是 12 个月均线，当前样刊还反复使用 12 个月、65 周均线和长期 KST。[公开 12 个月均线法](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)、[2026 年样刊](https://www.pring.com/sample-imr.pdf)。120 个交易日约为六个月，30 个交易日约为一个半月；它们不是公开 Pring 参数。

对本项目最清楚的职责划分是：

- `120d`：项目的主要中期趋势候选，负责提出 bull/bear/uncertain；
- `30d`：转折预警和加速/减速证据，只产生 `warning`，不与 120d 等权投票决定阶段；
- `12M monthly`：公开 Pring 代理基准，用于对照模型是否因缩短窗口而过度敏感；
- 30d 与 120d 冲突时输出 `transition_pending`，而不是求平均后强制二值化。

如果把 30d 和 120d 都当“独立指标”直接多数投票，同一价格序列会被重复计权；如果只看 120 日首尾收益，又会忽略路径、均线斜率和假突破。正式规格至少应区分“价格相对趋势线”“趋势线方向”“短期动量预警”三个语义。

### 3. 滞回与确认

Pring 公开承认均线会 whipsaw；长期 KST 通过多周期和平滑减少假信号，但代价是更慢，且仍需价格确认。[Pring Research 12 个月均线说明](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)、[Long-term KST](https://www.pring.com/long-term-kst/)

官方没有公开一个可照抄的滞回宽度或最短持续天数。因此以下只能是待验证的项目工程规则：

- 为每个资产产生 `raw_state` 与 `confirmed_state` 两层；
- 价格距离趋势线处在资产特定噪声带内时，`raw_state=uncertain`；
- 候选 bull/bear 连续满足 `k` 个交易日后才更新 `confirmed_state`；
- 在确认期继续显示上一 `confirmed_stage`，同时醒目标出 `candidate_stage` 与剩余确认天数；
- 噪声带和 `k` 必须在开发期冻结，再做时间外验证，不能每次误判后人工移动阈值。

滞回应施加在**每个资产的趋势确认**上，而不是以“Stage 至少维持 N 天”为理由压制真实资产转折。后者会把多资产同时快速反转误报为旧阶段。

### 4. 阶段跳转

阶段状态机只能负责**描述**，不能负责把市场修改成理想顺序：

```text
transition_type = sequential | skip | retrograde | rogue_7 | rogue_8 | pending
```

- 典型顺时针变化标 `sequential`；
- 跨过一个或多个阶段标 `skip`；
- 回到前一阶段标 `retrograde`；
- 明确落入 VII/VIII 时保留该状态；
- 含 `uncertain` 或尚未通过持续确认时标 `pending`。

官方明确允许乱序、跳过和倒退，因此不能给 `sequential` 人为最高真值权重，也不能因为转移“不漂亮”就拒绝更新。

### 5. 日更与月更的边界

Pring Research 说明正式模型在月度 InterMarket Review 中更新；DJPRING 原始发布材料也说明指数按月响应模型信号再平衡。[Pring Research](https://www.pring.com/how-to-use-the-business-cycle-as-a-pro-active-risk-management-investment-tool-part-2/)、[Dow Jones 发布稿](https://www.globenewswire.com/news-release/2012/03/14/470794/4127/en/Dow-Jones-Indexes-to-Launch-Dow-Jones-Pring-U-S-Business-Cycle-Index.html)

本项目可以每日刷新市场数据和 30/120 日特征，但每日输出应称为项目的 `daily estimate`。如果同时计算公开 12M 基准，建议只在月末收盘更新其正式状态，日内仅展示“距月末阈值的当前距离”。这样不会把日频噪声伪装成 Pring 官方月度阶段。

## 七、可供选择的最小 Pring-inspired 规范

### 方案 M0：公开 Pring 基准（最忠于公开资料）

```text
频率：月末
资产：一个中国长期政府债价格/总回报代理、一个宽基股票代理、一个宽基商品代理
规则：月末价格 > 12个月SMA => bull；< => bear；相等/缺失 => uncertain
映射：Stage I-VIII；有 uncertain 时不强制阶段
用途：审计基线，不承担每日中期预警
```

优点是规则公开、简单、可与 Pring 本人文章直接对照；缺点是慢，不完全满足用户希望观察 120 交易日中期变化的目标。

### 方案 M1：120 日中期主模型（推荐作为产品主视图）

```text
频率：每日收盘后
主要趋势：价格相对 120日趋势线 + 120日趋势线方向
短期预警：30日收益/斜率，只标 warning，不直接投票改阶段
当前状态：bull / bear / uncertain
确认：候选方向持续 k 日；噪声带与 k 在开发期确定并冻结
映射：Stage I-VIII；含 uncertain 时输出 confirmed_stage + candidate_stages
转移：允许 sequential / skip / retrograde / rogue / pending
```

这最贴近本项目“120 市场中期趋势”的产品目标，但必须命名为 `Pring-inspired China 120d`。参数 `k`、噪声带和各资产代理要通过中国市场人工锚点与时间外样本确定，不能直接从美国材料抄一个数字。

### 方案 M2：M0 + M1 双轨（推荐的首版交付形式）

Web 页面并列显示：

- `Public Pring 12M Proxy`：慢、透明、月度；
- `China 120d Estimate`：快、项目自有、每日；
- 两者一致/背离及背离持续时间；
- 三资产原始状态、Stage VII/VIII、uncertain、候选阶段和变更原因。

M2 只比 M1 多一个很便宜的月度透明基线，却能立刻回答“不准确是因为 120 日窗口太快，还是资产代理/组合映射真的错了”。因此建议首版选择 **M2**，但产品主结论仍以 M1 为主，M0 只作校准参照。

### 首版明确不做

- 不试图猜测或逆向工程 Pring 专有 barometer 的完整组件；
- 不把库存、货币或信贷评分加到三个资产状态后求平均；
- 不让 Codex CLI 或 Claude Code CLI 改写确定性阶段；两者只生成带来源的解释、发现缺数并按白名单取数；
- 不用未来收益生成今日阶段；
- 不把 Stage VII/VIII、uncertain、skip 或 retrograde 当成“算法异常”静默修正。

## 八、对下一轮问答的具体建议

研究已经把 Q12 从“找三个官方正确日期”改写成一个可执行决策：**公开官方日期只能做美国语义参照，中国市场必须建立独立人工锚点。** 下一轮只需用户确认以下三项：

1. 是否采用 **M2 双轨**：12M 公开基准 + 120d 中国主模型；
2. 是否接受 Stage VII/VIII 以及 `uncertain` 为合法输出，而不是强制 1–6；
3. 是否同意先从旧报告中抽取变更日期，再进行盲标，形成 Q12 的首批人工锚点。

这三项确认后，才进入中国债券、股票、商品代理选择与锚点样本设计；此时再分析旧项目改版前后误判，能够把理论争议、数据问题和代码缺陷分开。
