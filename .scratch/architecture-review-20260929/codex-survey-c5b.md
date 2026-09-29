# 候选 5 补充勘察：超出 120 个交易日窗口的回看盘点

来源：Codex 只读勘察（2026-09-29），静态读码、未实测。

1. **结论：当前最新模型并非“所有指标只用 120 个交易日尺度”，仅关闭信用脉冲也不能达到这个目标。**仍有核心趋势至少 140 日输入、有状态确认、12 月代理、250 日广度、商品篮子基日链，以及无期限事件基准；Worker 还有独立于公式开关的长范围取数。以下为静态读码报告，未修改文件、运行测试、执行 `uv sync` 或发起网络请求，也未核查运行库的实际生效指针。

2. **最新模型是 `effective_model_manifest()` 产出的 `model-v0013`，目录为 `metric-catalog-v0005`。**继承链为 v0013 → `model_v0012_manifest` → `certified_120d_model_v0011_manifest` → v0010 → v0009 → v0008 → v0007 → v0006 → `analytical_model_v0003_manifest` → v0002 → `certified_model_v0001_manifest`。证据：`src/pring_cycle/models.py:474`、`src/pring_cycle/models.py:506`、`src/pring_cycle/models.py:561`、`src/pring_cycle/models.py:203`、`src/pring_cycle/models.py:183`、`src/pring_cycle/models.py:174`、`src/pring_cycle/models.py:166`、`src/pring_cycle/models.py:146`、`src/pring_cycle/models.py:126`、`src/pring_cycle/models.py:104`、`src/pring_cycle/models.py:76`。

3. **必须区分“指标尺度超过 120 日”与“计算窗口首日需要窗口前输入”。**例如 30 日趋势、上月差分本身不超过半年，但计算证据窗口最早一天仍可能需要窗口前数据；现有领域定义明确允许这种公式回看，并单独允许事件现行基准。证据：`CONTEXT.md:67`、`CONTEXT.md:123`、`docs/adr/0028-event-metrics-current-baseline-and-discovery.md:18`。

4. **派生公式① `credit_impulse`／`CN_CREDIT_IMPULSE`：显著超过 120 日。**计算需要连续 24 个月社融流量、8 个季度名义 GDP；由累计值差分时，非年初起点可能额外需要一期，成为 25 个月／9 个季度，最新公式版本为 `credit-impulse-ytd-flow-v0002`（`src/pring_cycle/models.py:150`、`src/pring_cycle/full_run_requirements.py:108`、`src/pring_cycle/full_run_requirements.py:149`）。取数在 `src/pring_cycle/worker.py:1863`、`src/pring_cycle/worker.py:1885`，读取与差分在 `src/pring_cycle/context_projection.py:2165`、`:2231`、`:2268`，两段滚动占比之差在 `src/pring_cycle/context_projection.py:2319`、`src/pring_cycle/domain/macro.py:49`。消费方为信用响应 `credit_impulse`、过热 `credit`、库存卡 `credit_physical_inventory`，并间接进入报告（`src/pring_cycle/context_projection.py:61`、`:69`、`:86`）。

5. **派生公式② `dr007_policy_spread`／`CN_DR007_POLICY_SPREAD`：当期 DR007 加现行政策利率，利率基准可能无限早。**需求表虽写双方各 1 期，实际读取“不晚于 DR007 日期的最新可用 OMO 利率”，没有 120 日年龄限制，计算为利率差乘 100 转成基点（`src/pring_cycle/full_run_requirements.py:129`、`src/pring_cycle/context_projection.py:932`、`:948`、`:967`）。DR007 批量取数在 `src/pring_cycle/worker.py:1902`，OMO 新公告复查在 `src/pring_cycle/full_retrieval.py:441`。结果进入政策方向的 `transmission` 角色及报告，因此其长期依赖是“现行基准”，不是多年滚动统计（`src/pring_cycle/context_projection.py:54`、`src/pring_cycle/reports.py:139`）。

6. **派生公式③ `loan_monthly_change`／`CN_LOAN_STRUCTURE.monthly_change`：最多两个月，窗口边缘只多带上一月。**最新版本用本年累计增量差分，1 月直接用当月累计值，不需要上年 12 月；其他月份必须有连续上一月（`src/pring_cycle/models.py:151`、`src/pring_cycle/context_projection.py:1080`、`:1114`）。取数需求在 `src/pring_cycle/full_run_requirements.py:130`，落实为逐期检索在 `src/pring_cycle/full_retrieval.py:402`，计算读取与相减在 `src/pring_cycle/context_projection.py:1086`、`:1129`。结果消费于信用响应 `loan_structure` 及报告；它不是 12 月或 25 月尺度（`src/pring_cycle/context_projection.py:66`）。

7. **派生公式④ `omo_net_injection`／`CN_OMO_7D_AMOUNT.net_injection`：通常只需前 7 个自然日及休市顺延，不超过半年。**有明确到期量时直接采用，否则把历史投放日加 7 天，再顺延到取得的下一个交易日；所以窗口首日可能需要窗口前投放，而需求表仅写 1 期，未完整表达这项依赖（`src/pring_cycle/full_run_requirements.py:131`、`src/pring_cycle/context_projection.py:885`、`:1186`）。金额读取在 `src/pring_cycle/context_projection.py:768`，交易日输入在 `:835`，到期映射在 `:850`，净额计算在 `:1231`。结果进入政策方向的 `policy_action` 角色及报告（`src/pring_cycle/context_projection.py:48`、`:1881`）。

8. **派生公式⑤ `order_inventory_spread`／`CN_ORDER_INVENTORY_SPREAD`：同一个月两项 PMI，不需要多年回看。**取数在 `src/pring_cycle/worker.py:1844`，读取新订单与产成品库存 PMI 在 `src/pring_cycle/context_projection.py:1017`、`:1033`，计算取最新共同月份并相减在 `:1041`。需求各 1 期，统计月或发布滞后可能使窗口首日所需月份落在窗口之前，但公式本身没有超过 120 日的滚动长度（`src/pring_cycle/full_run_requirements.py:132`）。结果进入库存 `orders_inventory_gap` 特征卡及报告的库存证据，不直接决定库存象限（`src/pring_cycle/context_projection.py:87`、`src/pring_cycle/domain/macro.py:162`、`src/pring_cycle/reports.py:231`）。

9. **派生公式⑥ `production_order_spread`／`CN_PRODUCTION_ORDER_SPREAD`：同月生产 PMI 减新订单 PMI，不超过 120 日尺度。**取数同样在 `src/pring_cycle/worker.py:1844`，两项读取在 `src/pring_cycle/context_projection.py:1017`、`:1025`，共同月份选择与相减在 `:1060`。需求为活动 PMI 1 期，窗口边缘只有统计期／发布时间带来的边界依赖（`src/pring_cycle/full_run_requirements.py:136`）。消费方也是库存 `orders_inventory_gap` 特征卡及报告库存证据（`src/pring_cycle/context_projection.py:88`、`src/pring_cycle/reports.py:231`）。

10. **派生公式⑦ `real_inventory_approximation`／`CN_REAL_FINISHED_GOODS_INVENTORY_PROXY`：同月名义库存除以 `1＋PPI同比/100`，没有自算一年同比。**输入需求各 1 期；库存经逐期检索取得、PPI 另有批量取数，读取在 `src/pring_cycle/context_projection.py:2053`、`:2061`，最新版本在发布月份错位时回找库存月份的 PPI（`src/pring_cycle/full_retrieval.py:402`、`src/pring_cycle/worker.py:1849`、`src/pring_cycle/context_projection.py:2089`）。计算在 `src/pring_cycle/context_projection.py:2115`，通常只是回退一个月来对齐，且对齐查询受可见窗口限制，并非无限回找。结果放入库存投影的 `real_inventory_approximation` 展示字段，不参加库存象限或宏观状态计算（`src/pring_cycle/context_projection.py:449`、`:455`、`:510`）。

11. **派生公式⑧ `ust_2s10s_spread`／`UST_2S10S_SPREAD`：同日两条收益率，不需要长历史。**取数在 `src/pring_cycle/worker.py:1894`，读取在 `src/pring_cycle/context_projection.py:983`，取最新共同日期后计算“10 年收益率－2 年收益率”在 `:997`。这里“2 年／10 年”是债券期限，不是数据回看长度；需求双方各 1 期（`src/pring_cycle/full_run_requirements.py:141`）。结果作为 P2 背景进入 `international_context`，不决定正式阶段，也没有直接进入报告四个宏观结论的证据映射（`src/pring_cycle/context_projection.py:1971`、`src/pring_cycle/reports.py:138`）。

12. **核心资产趋势的单日测量实际需要 140 个交易日，超过 120 日 20 个交易日。**`window_days=120`、`slope_days=20`，计算当前 MA120 与 20 日前 MA120；`volatility_days=20` 只额外表达 20 个收益率、21 个价格，已被上述 140 日覆盖（`src/pring_cycle/models.py:39`、`src/pring_cycle/domain/trend.py:64`、`:85`、`:90`）。取数由 `src/pring_cycle/worker.py:2122` 调用，实际价格范围截为最近 160 个交易日在 `src/pring_cycle/core_history.py:91`、`:102`，计算入口在 `src/pring_cycle/worker.py:1196`。三核心稳定状态直接进入 P0 正式阶段及报告（`src/pring_cycle/p0.py:82`、`src/pring_cycle/reports.py:215`）。

13. **`persistence_days=8` 使首次确认理论上最早需要 147 个价格点，但 147 点并不保证确认。**第 140 个点才有首个信号，连续 8 次同向信号才能确认，噪声或反复会继续延长；稳定状态还会在后续无信号时沿用，因而无法用固定“最后 147 日”保证复现更早历史初始化的状态（`src/pring_cycle/domain/trend.py:80`、`:84`、`:99`、`:112`）。Worker 读取该模型目录下目标日前全部持有核心序列，而非只读显示用的 120 条，并把完整输入 ID 单独保留（`src/pring_cycle/worker.py:1135`、`:1197`、`:1211`）。这就是所谓有状态趋势的“完整预热”，其消费仍是 P0 状态与阶段史。

14. **30 日转折观察实际需要 31 个价格点，不超过 120 日，但计算窗口首日需前 30 个交易日。**`_simple_track` 比较当前 MA30 与前一日 MA30，使用同一核心取数序列（`src/pring_cycle/domain/trend.py:123`、`:199`、`src/pring_cycle/worker.py:1203`）。结果进入核心资产展示和阶段史的候选事件，不替代正式阶段的稳定状态（`src/pring_cycle/p0.py:325`）。此外，它位于 140 点总门槛之后，即使已经有 31 点，当前实现仍可能整体返回 `insufficient_history`（`src/pring_cycle/domain/trend.py:65`）。

15. **`proxy_12m` 明确超过半年，而且实现要求至少 13 个不同月份。**它从全部核心输入中取每月最后一个已取得价格，门槛是 13 月，实际均值只用最近 12 月；本月未结束时也会纳入本月最新点，严格说并不完全等于文档的“月末价格”（`src/pring_cycle/domain/trend.py:211`、`CONTEXT.md:127`）。没有独立长历史取数，仍依赖 Worker 的核心序列，因此正常仅取得 160 个交易日时通常算不出来（`src/pring_cycle/worker.py:2128`、`:1204`）。结果进入核心页面和候选事件记录，不参与 P0 正式阶段映射（`src/pring_cycle/dashboard.py:874`、`src/pring_cycle/p0.py:331`、`:82`）。

16. **`history_input_start="2017-01-01"` 仍被最新 manifest 继承，但当前生产代码没有读取它。**全源码检索只找到两处赋值，Worker 实际采用“目标日前 280 个自然日日历＋最近 160 个交易日价格”，不能把这个字段解释为运行时仍从 2017 年拉数据（`src/pring_cycle/models.py:108`、`:132`、`src/pring_cycle/worker.py:2104`、`:2128`）。`worker.py:1212` 的“完整预热”描述的是全部已持有输入，不是按此字段保证取得完整历史。

17. **首次初始化的输入长度与“窗口内每天都能算出趋势”并不匹配。**若只取得 160 个交易日，120 日证据窗口首日仅有 41 个价格点；要让首日达到 140 点测量门槛，需要总共 259 点，要在理想连续信号下达到首次稳定确认则需 266 点。代码确实逐日补算，但没有逐日扩展核心取数，故早期日期会缺历史或无稳定状态；这是由代码直接推得的限制，未实测（`CONTEXT.md:72`、`src/pring_cycle/worker.py:548`、`:587`、`:2128`、`src/pring_cycle/domain/trend.py:64`、`:112`）。

18. **同比／环比通常读取来源已发布值，不要求本地再取去年同期。**CPI、PPI、M1/M2 直接映射来源字段，工业增加值、工业财务、库存和周转也读取官方同比／环比；最新模型的批量 M1/M2 请求关闭 `mom` 字段，但定向补缺路径仍使用适配器默认值（`src/pring_cycle/tushare_context.py:406`、`:441`、`src/pring_cycle/worker.py:1859`、`src/pring_cycle/targeted_context.py:67`、`src/pring_cycle/official_context.py:1397`、`:1469`、`:1645`、`:1667`）。GDP 的 TuShare 同比因语义未核实而拒收，官方解析器直接读取实际单季同比，并不以名义 GDP 自算替代（`src/pring_cycle/tushare_context.py:1602`、`src/pring_cycle/official_context.py:1307`）。因此“保留官方同比”与“不回拉一年原始数据”可以同时成立，但同比指标本身仍描述年度变化。

19. **普通宏观方向判断使用“当前值与上一期比较”，不是重新计算同比。**除 PMI 与净投放／降准变化等按阈值或正负判断外，其余方向取同维度最后两期，消费于政策、信用、过热、物价及库存角色（`src/pring_cycle/context_projection.py:1613`、`:1795`、`:436`）。月频通常只需前一月、季频只需前一季，不是超过半年的统计公式；不过当前普通行先经过可见窗口裁剪，不会自动附带窗口外上一期，缺上一期时方向变成 `unknown`（`src/pring_cycle/context_projection.py:295`、`:641`、`:1808`）。这与 `CONTEXT.md:124` 所述“按比较需要附带上一期”并未完全一致，不能把文档期待当成已实现取数。

20. **市场广度：90 日两项不超过半年，250 日两项超过，但本地都不回拉对应长度的股价。**`CN_EQ_NEW_HIGH_LOW_90/250`、`CN_EQ_ABOVE_MA90/250` 使用当天 TuShare 的 `topdays/lowdays`、`close_qfq/ma_qfq_N`，读取在 `src/pring_cycle/breadth.py:327`、`:330`，计算在 `:258`，因此 250 日长尺度隐藏在来源因子中。为验证上市满 N 个交易日，另取目标日前 **600 个自然日**日历及 L/D/P 上市记录，这确实读取窗口前资料（`src/pring_cycle/breadth.py:299`、`:317`、`:253`）。它们是 P1 背景，不进入宏观卡片或 P0，消费主要是取数完整性、时效、缺口和警告；这与 ADR-0030 一致，但“不需要回看”只能指股价回拉，不能覆盖日历（`docs/adr/0030-breadth-and-basket-from-tushare-inputs.md:9`、`:15`、`src/pring_cycle/worker.py:1276`）。

21. **日涨跌广度与上涨成交额占比只需当日交付中的前收盘，不超过 120 日尺度。**`CN_EQ_ADV_DEC`、`CN_EQ_AD_RATIO`、`CN_EQ_ADV_AMOUNT_SHARE` 直接比较 `close/pre_close` 并累计 `amount`，窗口首日的前收盘由当天记录携带，不另请求上一日行情（`src/pring_cycle/breadth.py:177`、`:184`、`:199`、`:327`）。其消费与上一条相同，不参与正式阶段或宏观状态计算（`docs/adr/0030-breadth-and-basket-from-tushare-inputs.md:9`、`src/pring_cycle/context_projection.py:175`）。

22. **商品篮子与袖套：日收益只需当天结算／前结算，但指数水平可能回看至固定基日 2026-03-06。**有已持有指数水平时从锚点续算，无锚点则从基日重建，所需历史会随时间增长、可能超过 120 个交易日；期货日历始终从基日取得，行情取数范围按所需合约日期确定（`src/pring_cycle/basket.py:27`、`:179`、`:199`、`:295`）。计算为分品种日收益、袖套加权贡献及链式累乘，袖套输出也共用这条链（`src/pring_cycle/basket.py:237`、`:246`、`:249`）。两项不进入价格压力卡或 P0，仅作背景完整性／缺口消费，不能声称它们在增强商品状态判断（`docs/adr/0030-breadth-and-basket-from-tushare-inputs.md:20`、`:21`、`src/pring_cycle/context_projection.py:76`）。

23. **`EFFECTIVE_UNTIL_CHANGED_METRICS` 只有 OMO 利率与降准事件，现行值允许无限早。**选择时按成员取截止日以前最新事件，展示时豁免窗口裁剪，时效直接视为 `current`，清理时保留每个成员最新一期（`src/pring_cycle/metric_contracts.py:14`、`src/pring_cycle/search_evidence.py:159`、`src/pring_cycle/context_projection.py:631`、`src/pring_cycle/freshness.py:740`、`src/pring_cycle/retention.py:150`）。两者进入 `policy_action`，OMO 利率还进入 DR007 利差；这是 ADR-0028 明确规定的例外，不应误称为长期趋势指标（`src/pring_cycle/context_projection.py:48`、`:948`、`docs/adr/0028-event-metrics-current-baseline-and-discovery.md:18`）。若改为“一律不读取窗口前任何数据”，该决定还需要明确覆盖这个例外。

24. **从未持有降准时，追溯发现没有 120 日上限。**Worker 检查是否已持有，否则沿央行大事记新到旧翻页，找到最近有效降准即停止；取数入口在 `src/pring_cycle/full_retrieval.py:229`、`:251`，追溯循环与采用在 `src/pring_cycle/official_context.py:917`、`:925`。结果形成上述政策现行基准；与 OMO 每轮查最新公告不同，降准可能确实追到数年前（`docs/adr/0028-event-metrics-current-baseline-and-discovery.md:9`、`:14`）。

25. **LPR 不是上述无限期基准例外。**其取数按月定盘期，20 日前使用上月，方向沿用普通前后两期比较；统计尺度一般只多一个月，消费于信用响应的 `credit_price`（`src/pring_cycle/full_retrieval.py:515`、`src/pring_cycle/context_projection.py:62`、`:1613`、`:1908`）。不要把所有“政策相关利率”都等同于 OMO 的生效至变更语义（`src/pring_cycle/metric_contracts.py:14`）。

26. **除公式需求外，Worker 还无条件为 PMI、CPI/PPI、M1/M2 请求约 25 个月。**共同起点为目标年份减二、同月月初，到目标月为止，实际已发布记录数由来源决定；取数在 `src/pring_cycle/worker.py:1771`、`:1844`、`:1849`、`:1854`。这些数据分别用于过热需求／PMI库存／物价压力、消费者与生产者压力、信用货币角色，但相应计算通常只取当前或前一期，不能把这段请求长度说成公式必需（`src/pring_cycle/context_projection.py:61`、`:69`、`:76`、`:86`、`:1613`）。

27. **其他日频背景也统一请求目标日前 220 个自然日，通常超出 120 个交易日窗口。**包括市场指数、融资余额、估值、仓单、美国国债收益率、DR007/Shibor，以及 EIA、ECB 和官方行情源；取数在 `src/pring_cycle/worker.py:1778`、`:1810`、`:1829`、`:1834`、`:1877`、`:1896`、`:1904`、`:1587`、`:1693`、`:1739`。其消费是背景完整性、政策传导、物价、库存或 P2 展示，计算通常是当期、上一期或窗口内覆盖检查，并没有统一“220 日指标公式”（`src/pring_cycle/context_projection.py:54`、`:76`、`:86`、`:1613`、`src/pring_cycle/worker.py:1313`）。具体超出多少必须按该次上交所日历计算，不能把自然日机械等同交易日。

28. **关闭信用脉冲后，过热判断在正常派生输入路径下将持续为 `insufficient_data`。**删除公式键会让 `_credit_impulse_proxy` 返回 `disabled_by_model` 且不生成观测，但 `_OVERHEAT` 仍把信用脉冲作为唯一 `credit` 角色，`derive_overheat_state` 又强制要求 `demand/production/credit` 全齐（`src/pring_cycle/context_projection.py:2161`、`:69`、`src/pring_cycle/domain/macro.py:109`）。所以需求、生产再完整也不能得到 heating/cooling/overheated，并产生过热上下文降级警告；此结论假设没有另外写入可用的信用脉冲来源声明（`src/pring_cycle/context_projection.py:554`）。

29. **库存周期不会因停用信用脉冲而必然失效。**`credit_physical_inventory` 同时接信用脉冲和期货仓单，仓单有效时该卡仍可为 `support`，但卡片不会自动移除信用脉冲缺失行（`src/pring_cycle/context_projection.py:95`、`:1956`、`src/pring_cycle/domain/macro.py:187`）。库存象限只依赖需求、生产、库存方向，库存方向优先从实物库存、周转、PMI库存角色取得，因此不直接依赖信用脉冲（`src/pring_cycle/domain/macro.py:162`、`src/pring_cycle/context_projection.py:1934`）。仓单冲突、待发布或缺失时，特征卡按自身规则退化，不等同于整个库存周期不足。

30. **信用响应仍可以计算，但有效证据组合会改变。**它强制要求的是 `money/social_financing/loan_structure`，信用脉冲的 `credit_impulse` 角色只是附加证据，去掉后可能改变 expanding/contracting/mixed 的结果，但不会单独导致必然不足（`src/pring_cycle/domain/macro.py:87`）。当前映射和展示仍保留信用脉冲缺失项，宏观信用文档另含 `formula.status=disabled_by_model`（`src/pring_cycle/context_projection.py:67`、`:477`、`:2161`）。仅删公式键也不能顺手删掉指标定义，否则固定角色集合检查会报 `context_model_metric_missing`（`src/pring_cycle/context_projection.py:175`、`:290`）。

31. **报告会继承新的宏观结果与缺失异常，P0 正式阶段不会因此改变。**报告读取信用响应、过热、库存象限以及相关证据异常；信用脉冲缺失行会产生 `gap:CN_CREDIT_IMPULSE`，即便公式文档已标记停用，也没有报告侧统一豁免（`src/pring_cycle/reports.py:138`、`:210`、`:231`、`:302`）。周期总览的宏观事后确认会省略 `insufficient_data` 的过热项，P0 仍只由三核心状态映射（`src/pring_cycle/p0.py:233`、`:82`）。旧投影和旧报告不会因新模型停用公式而被重算。

32. **缺口清单不会因为删除公式键而完整、自动地“干净消失”。**长回看需求会从 `formula_requirements` 消失，但因指标仍存在于 `DERIVED_INPUTS`，完整运行计划会留下 `required_input_rule_unavailable`、空父需求的派生条目（`src/pring_cycle/full_run_requirements.py:146`、`src/pring_cycle/full_retrieval.py:380`）。投影缺口补充器把 `disabled_by_model` 当作可接受状态，因此不会仅因停用新增 `derived_failed`；不过它不会删除已有的父指标时效所造成缺口（`src/pring_cycle/freshness.py:975`、`:1019`、`:1045`）。报告中的缺失异常与这份运行缺口清单是两条路径，不能混为一谈。

33. **`freshness.py:204` 的时效父映射仍生效，与公式开关无关。**只要目录还含 `CN_CREDIT_IMPULSE`，批次时效就继续取社融和 GDP 的最差状态，因此公式已停用时仍可能显示 current、missing 或 stale（`src/pring_cycle/freshness.py:204`、`:512`、`:527`）。父指标缺失／落后仍可把信用脉冲带入运行缺口，此外解释性完整性检查仍把没有 current 观测的信用脉冲计入 P1 不完整（`src/pring_cycle/freshness.py:892`、`src/pring_cycle/worker.py:1281`、`:1320`）。

34. **Worker 关闭信用脉冲后仍会取 25 个月／9 个季度，甚至请求范围延伸到尚未发布的当前期。**`refresh_context_sources` 无条件调用 `_credit_lookback_starts(target)`，该函数只按最新应有社融月／GDP季倒数 25／9 期，完全不接收 `derived_formula_versions`（`src/pring_cycle/worker.py:1775`、`:1979`、`src/pring_cycle/full_run_requirements.py:117`）。随后又与“目标日前两年”的起点取更早者，并仍执行社融和 GDP 家族请求，所以删除公式键只影响计算与补缺需求，不能停止这段批量请求（`src/pring_cycle/worker.py:1776`、`:1863`、`:1885`）。

35. **GDP 本身还有独立消费者，不能与信用脉冲一起视为无用输入。**它是 P2 指标，会作为普通观测进入 `macro.international_context`，沿用最新值／上一期方向，并参加完整性、时效、检索缺口及 P2 降级警告（`src/pring_cycle/catalog.py:95`、`src/pring_cycle/context_projection.py:175`、`:1613`、`:1971`、`:565`）。没有发现它直接参与其他宏观状态或 P0 正式阶段；现行报告四个宏观结论也没有直接消费这组 P2 展示行，但报告会消费运行缺口摘要（`src/pring_cycle/context_projection.py:48`、`src/pring_cycle/reports.py:138`、`:241`）。停用信用脉冲后，GDP 这条独立链仍然存在，只是不再有计算信用脉冲所需的两年历史理由。

36. **“公式回看不入库”与当前实现明确不符。**核心 160 日全部追加为来源声明，上下文批量结果也统一入库，成功运行末尾才按窗口清理；`retention.py` 顶部实际上承认“取回、使用、末尾删除”的实现（`src/pring_cycle/core_history.py:155`、`:186`、`src/pring_cycle/tushare_context.py:335`、`src/pring_cycle/worker.py:527`、`src/pring_cycle/retention.py:12`）。这不同于 `CONTEXT.md:68` 和 `docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7` 的“不入库”，不能用留存期 120 日证明运行中未读取、未写入更老明细。事件基准则是 ADR-0028 授权的保留例外，不属于这一实现偏差。

37. **GDP 可比性检查的文档措辞也不准确。**文档说“与官方同比基期核对”，当前代码实际对不同交付差分出的季度 GDP，核对官方同份表直接公布的名义当季量；同一交付得到的季度值走另一条可比性路径（`CONTEXT.md:166`、`src/pring_cycle/context_projection.py:2254`、`:2310`、`src/pring_cycle/official_context.py:435`、`:462`）。该检查没有额外要求再取一年前同比基期，不能据文档再加一年回看。

38. **新增模型应照 `effective_model_manifest()` 的“继承当前清单、修改规则、赋新版本号”做法。**例如新函数以当前 v0013 为基底，再设置新的 `model_version_id`；只改公式时可保留原指标目录，若修改指标定义则必须另起目录版本并同步各定义的 `definition_version`，因为模型与目录都不可原地改写（`src/pring_cycle/models.py:484`、`:504`、`:268`、`src/pring_cycle/catalog_registry.py:53`）。当前旧 `catalog.validate_model_catalog` 虽仍要求八公式齐全，但没有生产调用方；CLI 注册校验允许公式子集，运行时同名的 repository 校验仅检查已注册绑定，不能误判为“删公式必被八公式校验拦截”（`src/pring_cycle/catalog.py:950`、`src/pring_cycle/cli.py:291`、`src/pring_cycle/context_projection.py:164`、`src/pring_cycle/evidence.py:472`）。

39. **运行时注册必须显式执行，新增 Python 函数本身不会注册或生效。**现行命令是 `pring-cycle model-register --manifest /path/model.json --json`，CLI 读取 JSON、校验上下文规则，再由 `ModelRepository.register` 在同一事务写入版本和非内置目录（`src/pring_cycle/cli.py:287`、`src/pring_cycle/models.py:238`）。初始化只登记 v0001–v0003，不会自动登记最新构造函数（`src/pring_cycle/runtime.py:268`）。这里仅说明现行操作，未创建 JSON 或执行注册。

40. **切换生效指针使用 `pring-cycle model-activate --model 新版本号 --confirm --json`。**激活检查显式确认及来源契约，在事务中更新 `active_model`、旧版本状态与激活历史，不要求回放或验收；之后提交的运行读取该指针，发布前还检查指针是否在运行期间变化（`src/pring_cycle/cli.py:295`、`src/pring_cycle/models.py:288`、`:309`、`:316`、`src/pring_cycle/cli.py:302`、`src/pring_cycle/worker.py:473`）。因此，要实现本次“仅保留 120 日尺度”的决定，至少需同时处理模型公式与角色、独立取数范围、250 日广度／12 月代理，并明确是否继续允许短期公式回看和事件现行基准；只新增一个删掉 `credit_impulse` 的 manifest 不够。
