# #19 市场 P1 合同交接核对（2026-09-18）

范围是原票要求的 **15 项市场 P1 软件合同**：融资1、确认指数6、估值1、日广度2、窗口广度2、金额广度1、商品2。这里不重做规格、不授予真实认证、不把合成生命周期当真实完整候选。初版索引绑定v5；v5已因磁盘保护中断，v6已因EIA夹具缺独立日历失败。当前v7默认1848项运行中，七组205项文件哈希及节点已逐项重新核对一致，见[本轮索引](verification-19-market-contract-index-v7-20260919.json)。以下是既有实施与冻结测试的对应关系，尚不勾选本票条件。

| 指标 | 已交付的软件合同与必要输入 | 原票实施证据 / 当前测试组 |
|---|---|---|
| `CN_MARGIN_BALANCE` | 沪深北三所原件；全市场融资余额、融资买入两成员；缺所/错期不得凑完整 | [05](implementation-05-registered-margin.md) / margin |
| `CN_EQ_CSI300` | 000300.SH，index_daily，独立日期/close原件，指数点 | [06](implementation-06-registered-indices.md) / indices |
| `CN_EQ_CSI500` | 000905.SH，同上；不能借CSI300原件证明自身 | [06](implementation-06-registered-indices.md) / indices |
| `CN_EQ_CSI1000` | 000852.SH，同上；逐身份核对值与原件 | [06](implementation-06-registered-indices.md) / indices |
| `CN_BOND_FULL_PRICE_CNY030` | 000012CNY030.CSI，完整价格指数身份；不以其他债指替代 | [06](implementation-06-registered-indices.md) / indices |
| `CN_BOND_10Y_930916` | 930916.CSI，自身原件/日期/close与source_code维度 | [06](implementation-06-registered-indices.md) / indices |
| `CN_COMMODITY_BROAD_NHCI` | NHCI.NH，fut_index_daily；与核心NHII不同身份 | [06](implementation-06-registered-indices.md) / indices |
| `CN_INDEX_VALUATION` | CSI300/500/1000 × 静态PE/PB/换手率共9成员；TTM不补静态PE，坏原件只隔离对应指数 | [07](implementation-07-registered-valuation.md) / valuation |
| `CN_EQ_ADV_DEC` | breadth-v0002；已审证券池/事件、合法价格及参与资格；涨/跌/平成员与真实分母 | [08](implementation-08-registered-daily-breadth.md) / daily_breadth |
| `CN_EQ_AD_RATIO` | 同日日广度父项；零参与与缺件保持不可用，不拼入窗口或金额口径 | [08](implementation-08-registered-daily-breadth.md) / daily_breadth |
| `CN_EQ_NEW_HIGH_LOW_120` | breadth-window-v0002；完整120日与隐藏预热、已知调整/换码、每个输出自身必要父项 | [09](implementation-09-registered-window-breadth.md) / window_breadth |
| `CN_EQ_ABOVE_MA120` | 同窗口身份与完整价格链；只取本输出所需历史，不因无关未来原件损坏误伤 | [09](implementation-09-registered-window-breadth.md) / window_breadth |
| `CN_EQ_ADV_AMOUNT_SHARE` | breadth-amount-v0002；全池金额分母、非参与成员金额、互斥覆盖方法及明确不适用证明 | [10](implementation-10-registered-amount-breadth.md) / amount_breadth |
| `CN_COMMODITY_EX_HOG_BASKET` | ex-hog-calendar-settlement-v0002；八品种/四交易所、固定3月6日1000基点、合法选约和同合约结算链；缺件不重分权 | [12](implementation-12-commodity-basket.md) / commodity |
| `CN_COMMODITY_SLEEVE_CONTRIBUTION` | 同篮子父项与公式身份，七袖套贡献；纺织CF/TA各半，权重逐日恢复 | [12](implementation-12-commodity-basket.md) / commodity |

## 可复核的公开边界

市场合同组沿 `model-source-certify` 公开准入、获取/原件与标准化收据、Evidence公开查询及候选选值验证。准入不是直接改生效记录；原完整定义保留，场景采用合成资格，不登记到真实库。当前组件夹具已改为绑定完整获准manifest，见[共同夹具记录](implementation-22-bound-component-fixtures-20260918.md)。组件选值/投影覆盖不冒充完整回放编排，后者仍由test_isolated_lifecycle中的公开准入→校准→120日回放→隔离激活和完整context损坏/恢复用例承担。

六指数当前正例 `test_registered_market_indices_keep_each_identity_value_and_original` 明确核六次独立获取、API与source_code、原字节、日期/单位、真实SYSTEM取得前后及未知PUBLIC；候选选择/损坏/发布时间节点另外覆盖消费行为。融资与估值对应读取、拒绝、PUBLIC边界同样分别留证。商品 `test_registered_basket_is_readable_with_all_seven_contributions` 与 `test_candidate_rechecks_settlement_original_and_recovers_after_restoration` 核对实际采用声明集合、篮子与七贡献，以及损坏所选fut_daily原件后的拒绝/恢复。

[本次冻结发现索引](verification-19-market-contract-index-20260918.json)保存每组文件摘要与实际收集的node ID。它证明这些行为纳入v5默认发现，**不证明尚未执行节点已通过**。最终以当前v7自身全套终态、完整输入不变与两轴审查为准，旧专项通过数不加总。

## 其余范围与未完成项

四项已有认证输入派生例外单列：`CN_DR007_POLICY_SPREAD`、`CN_ORDER_INVENTORY_SPREAD`、`CN_PRODUCTION_ORDER_SPREAD`、`CN_CREDIT_IMPULSE`。它们继续消费各自已选父项与公式/时间/认证身份，不能按缺失网络适配器重新拆解。信用脉冲的GDP分母与已实现美国国债支持继续复用，GDP/UST是相应P2支持，不计入上述15项。

本表不能替代完整目录、维度、原件、点时及派生父项的**独立材料预检**；该软件条件仍开放。真实融资BSE、CNY030官方点位、估值历史、证券池/事件/调整、PP及规则等缺件见[真实来源交接](remaining-source-handoff-20260918.md)，不被本表或合成测试消除。旧目录61项与#27删黄金/ECB替换后的新目录身份分别保留，不能拿旧目录数量强套新迁移结果。

## 交接审查

Standards 与 Spec 独立只读核对，各新增阻断0。七组205个收集节点、文件及collection哈希与v5一致；链接可达。此审查只支持交接索引，不把205个尚待本轮执行的节点计作通过；原票勾选未改变。

预检接缝核实：当前 `prepare_isolated_candidate_inputs` 完成准入及各家族导入后，builder直接进入 `model-accept` 与完整 `model-replay`。`context_replay_gaps` 只检查所需定义的certification_status；完整覆盖、成员、原件与父项检查另在后续评价/选择路径中。不能将该短函数单独包装成已完成的材料预检，也不能把成功回放倒称构建前独立预检。本轮只核代码边界，未新增预检实现。
