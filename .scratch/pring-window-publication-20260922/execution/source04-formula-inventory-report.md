**1．结论与调查边界**

04 的最小工作是补齐**公式父需求与预检诊断**，不是重写派生计算。现有信用脉冲、利差、PMI、贷款、OMO 已有真实解析、原件校验、点时选择及拒收测试。

当前预检的实际错误名是 `formula_inputs_unavailable`，不是 `derived_formula_unavailable`；问题在于多数失败的 `missing_input_periods`、`invalid_parent_claims` 仍可能为空，且不携带维度和具体派生失败原因。依据：`src/pring_cycle/material_preflight.py:374`、`:390`。

本次只读了文档、源码和相关测试；未改文件、运行测试、构建材料、联网或读取凭据。以下行为结论均为**读码推断**，不构成测试通过或票完成证明。

**2．公式与父输入矩阵**

统一约定：

- `D` 是每个被检查交易日，消费 cutoff 为 `D 23:59:59.999999 Asia/Shanghai`；预检逐日使用 PUBLIC。依据：`material_preflight.py:293`、`metric_contracts.py:16`。
- 730／95／62／10 是 `context_replay_scope.py:150` 的**自然日回看配置**，不是交易日或父项条数；预检使用 `timedelta(days=...)`，见 `material_preflight.py:223`。
- 新窗口首日对应的回看起点分别为 **2024-04-01／2025-12-27／2026-01-29／2026-03-22**。它们只是当前范围配置，不能替代实际期次、维度和版本检查。
- 可准入候选要求以下 **8 个公式键完整存在**：`candidate_admission.py:317`。版本必须读候选注册 manifest；当前 v0011 模板继承信用／贷款 v2，升级 OMO v2；完整生命周期夹具另将库存升级为共同月份 v2。依据：`models.py:145`、`:205`、`:261`；`tests/models/test_isolated_lifecycle.py:99`。本次没有读取真实运行库，不能把模板或夹具冒充某个真实候选。

以下源码简称 `CP = src/pring_cycle/context_projection.py`；测试简称 `CA = tests/models/test_candidate_admission.py`。

| 公式／实际版本 | 父指标、维度、频率 | 必需期次、比较基线与回看 | 实际消费及现有测试 |
|---|---|---|---|
| `credit_impulse`／`credit-impulse-ytd-flow-v0002` → `CN_CREDIT_IMPULSE` | `CN_SF_TOTAL`：`measure=ytd_increment`，月累计；`CN_GDP`：`aggregate=total, measure=nominal_ytd_level`，季累计。兼容路径支持社融 `monthly_increment`、GDP `nominal_quarterly_level` | **24 个连续月流量＋8 个连续季度水平**；累计差分若首月非一月、首季非 Q1，还需前一期，通常为 **25 月＋9 季原始父项**。当前12月/4季与前12月/4季分别求比再作差。回看 **730自然日** | 每个父版本均须在 D cutoff 可见；GDP累计差分还须与该发布中的当季值相容。CP`:2139`、`:2194`、`:2230`、`:2260`、`:2280`。CA`:5595` 已覆盖不兼容GDP、最新父项质量/认证问题、旧窗口掩盖、中间基线；`:6057` 覆盖兼容数值修订与未知 PUBLIC；`:6162` 覆盖最新月差分基线 |
| `dr007_policy_spread`／`dr007-policy-spread-v0001` → `CN_DR007_POLICY_SPREAD` | `CN_DR007 {}`，日频；`CN_OMO_7D_RATE {}`，**实际为生效至变更的事件** | 最新可用 DR007 日值；政策利率必须是**不晚于该 DR007 日期**的有效事件。`100×(DR007−政策利率)`，bp。回看 **10自然日**，并不要求10次利率事件 | 两父项均受 D cutoff；不能使用 DR007 之后的新政策事件。CP`:884`、`:900`；事件语义见 `metric_contracts.py:9`。CA`:5097` 已覆盖最新政策利率／DR007原件损坏；`:5278` 覆盖零操作日沿用有效政策事件 |
| `loan_monthly_change`／`loan-ytd-monthly-change-v0002` → `CN_LOAN_STRUCTURE` 的 `monthly_change` | 同指标 `measure=ytd_increment`，月累计；按 `(borrower,tenor)` **9组分别计算**：住户 total/short_term/long_term；企业 total/short_term/long_term/bill_financing；非银 total；全部人民币贷款 total | 同组当月−同年上月；**一月直接使用当月累计，不需要上年十二月**。旧 stock v1 为相邻月存量差。回看 **62自然日** | 最新期和差分父期均须合法，不能跳过缺月。CP`:1032`、`:1062`；完整9组见 `metric_contracts.py:218`。CA`:4625` 已覆盖5/6/7月 raw、normalized、质量异常，并验证不恢复旧派生 |
| `omo_net_injection`／`repo-net-injection-trading-calendar-v0002` → `CN_OMO_7D_AMOUNT` 的 `net_injection` | `CN_OMO_7D_AMOUNT`：`measure=injection/maturity`，操作日；另有 **manifest股票核心序列提供的交易日期父项**，当前映射000985 | 优先同日显式到期额；否则历史投放日 **+7自然日，再顺延到可用交易日期**，汇总该日到期投放。净投放＝当日投放−到期额。回看 **10自然日** | 操作原件和实际采用的日期父项都受 cutoff／原件门。CP`:786`、`:803`、`:837`、`:848`、`:1105`、`:1138`。CA`:4783` 已覆盖到期投放、当前投放及日期父项坏原件。**现有公式父表遗漏股票核心依赖** |
| `order_inventory_spread`／`pmi-order-inventory-spread-v0001` → `CN_ORDER_INVENTORY_SPREAD` | `CN_PMI_ACTIVITY {series=new_orders,measure=level}`；`CN_PMI_INVENTORY {series=finished_goods,measure=level}`；均月频 | **同月**新订单−产成品库存，扩散指数点；不需要同比历史。回看 **62自然日** | 取共同月份；最新已出现父项损坏不能退回旧派生。CP`:969`、`:993`、`:1351`。CA`:4310` 同时覆盖两个PMI公式，独立核对7月 `48.5−48.6=-0.1`；`:4194` 覆盖日期精度、未知时间及修订 |
| `production_order_spread`／`pmi-production-order-spread-v0001` → `CN_PRODUCTION_ORDER_SPREAD` | 同一 `CN_PMI_ACTIVITY` 的 `production/level` 与 `new_orders/level`，月频 | **同月**生产−新订单；回看 **62自然日** | CP`:977`、`:1012`。CA`:4310` 核对7月 `49.9−48.5=1.4`；不能仅证明“该指标本月有记录”就认为两个维度齐备 |
| `real_inventory_approximation`／`inventory-ppi-v0001` 或已采用的 `inventory-ppi-common-month-v0002` → `CN_REAL_FINISHED_GOODS_INVENTORY_PROXY` | `CN_FINISHED_GOODS_INVENTORY {measure=nominal_end_level}`；`CN_PPI {category=headline,measure=yoy}`，月频 | `名义库存/(1+PPI同比/100)`；PPI同比是官方标量，**无需重新索取去年价格水平**。v1要求当前两行同月；v2以库存月份找同月PPI，允许PPI已有更新月份。回看 **95自然日** | 分母须正；两个实际父版本都有血缘。CP`:2013`、`:2054`、`:2074`。`tests/integration/test_context_projection.py:1592` 已验证使用名义库存而非官方同比；共同月份v2在完整夹具启用，但本次未定位到专门的注册目录预检反例 |
| `ust_2s10s_spread`／`ust-2s10s-spread-v0001` → `UST_2S10S_SPREAD` | `UST2Y_NOMINAL_YIELD {}` 与 `UST10Y_NOMINAL_YIELD {}`，日频 | **同一天**，`100×(10Y−2Y)`，bp；回看 **10自然日** | CP`:935`。CA`:979` 已有 SYSTEM 数值41bp、未知 PUBLIC 拒收；`:1205` 校验原件/规范化合同。**当前注册 Treasury CSV 合同要求发布时间为空**，见 `treasury_context.py:233`；不能靠给声明注入 PUBLIC 时间构造正例 |

库存预检还有一个标识差异：`context_replay_scope.py:35` 将公式映射到源指标 `CN_FINISHED_GOODS_INVENTORY`，而 `full_run_requirements.py:125` 和实际派生使用 `CN_REAL_FINISHED_GOODS_INVENTORY_PROXY`。后续诊断宜同时记录**目录归属指标**与**受影响派生结果**，不能混用二者进行优先级分类。

**3．货币、广度及其他计算不能误纳入上述8键**

| 实际启用项 | 父项／基线／频率与 cutoff | 已实现与04边界 |
|---|---|---|
| `CN_M1_M2` | 月频 `m1/m2 × balance/yoy` **4成员**；同比直接来自官方，不是本地 M1−M2 公式。方向使用同维度上一可见观测；没有可用上一项时方向为 unknown。上下文公式回看表返回 **0** | `metric_contracts.py:185`；CP`:1564`、`:1592`、`:1768`。`tests/integration/test_worker_reviewed_context.py:107` 已验证4成员与未知 PUBLIC，`:285` 保留旧目录6成员。04不应新增“货币剪刀差”公式，也不能将旧目录 mom 成员恢复为新目录必需项 |
| 日广度 `CN_EQ_ADV_DEC`、`CN_EQ_AD_RATIO` | 当日行情、停复牌、点时普通A股成员及参考价证据；维度 `measure`＋`universe=point_in_time_traded_a_shares`。涨/跌/平、净涨、参与数和涨跌比；不是120日回看 | `market_breadth.py:287`、`:658`、`:678`。CA`:12387` 已测发布时间，`:12461` 已测 PUBLIC 消费重查原件；复用来源合同 |
| 窗口广度 `CN_EQ_NEW_HIGH_LOW_120`、`CN_EQ_ABOVE_MA120` | 每个结果实际消费 **120个交易日**行情、身份连续性、调整事件及证据；停牌承接可能另需窗口前参考行情。常规连续覆盖120个结果需要239日基础行情，不能套核心259日 | `market_breadth.py:964`、`:974`、`:1059`、`:1132`；公式 `ordinary-a-market-window-v0002`。CA`:12859`、`:13606`、`:13676` 已覆盖隐藏预热、120日输出、逐结果实际输入；`:13874` 排除未消费未来事件原件 |
| 成交额广度 `CN_EQ_ADV_AMOUNT_SHARE` | 同日上涨证券成交额／完整成员口径总成交额；分母包含非上涨成员，不可仅保留上涨成员。维度 `advancing_amount_share`＋上述universe；公共时间取实际父证据最大值，任一未知则未知 | `market_amount.py:265`、`:283`、`:295`。CA`:14196`、`:14258`、`:14516`、`:14572` 已覆盖分母、未知金额、发布时间和原件 |
| 去猪商品篮子／分项贡献 | 来源合同中的 `ex-hog-calendar-settlement-v0002`；8品种、7组权重；固定 **2026-03-06** 基期与此后实际开市链，消费选约、日历、settle/pre_settle。不是上下文零回看即可无历史 | `commodity_basket.py:31`、`:182`、`:223`、`:249`。04应复用家族消费守卫，不另造259日要求 |
| ECB人民币参考交叉汇率 | 已批准新身份下，同日 EUR/CNY 与 EUR/USD 求比；来源公式 `ecb-eur-reference-cny-usd-cross-v0001` | `ecb_reference.py:34`、`:174`。属于来源合同计算，非上述8键；不能恢复旧FXCM身份 |

广度原件验证已经按实际结果期次重建父输入，见 `market_breadth.py:768`。因此“它没有出现在 `CONTEXT_FORMULA_INPUTS`”不等于“它没有父输入守卫”。

**4．真实最小缺口、公开反例与测试重量**

当前共同缺陷位于 `material_preflight.py:508`：

- 只收集每个**指标**有哪些期次，忽略维度、累计/当期口径及实际采用分支。
- `formula_requirements()` 仅返回计数；贷款固定2期，OMO固定1期，库存与PMI没有共同期关系。依据：`full_run_requirements.py:115`。
- 原件诊断只检查是否取得哈希合格的 acquisition；这不等于家族语义校验或GDP修订相容性。依据：`evidence.py:317`、`:350`。
- 公式可用时只要求“存在一个可用文档且父ID列表非空”，没有输出逐需求的成功血缘。依据：`material_preflight.py:374`。

| 缺口 | 推荐的公开边界反例／正例配对 | 轻重判断 |
|---|---|---|
| **信用脉冲：维度、未知父项和修订失败原因未贯通预检** | 复用合法34父项材料；保留同月社融存量发布，单独不提供必要累计流量发布，确保不能被“该指标该月存在”掩盖。另复用 CA`:5595` 的不兼容GDP与`:6057` 的兼容修订，要求预检指出具体父期、口径及受影响公式；兼容修订只影响新cutoff，旧结果不变 | 合法注册候选＋官方解析＋公开选择/投影可轻量做；现有 `test_material_preflight.py:484`、`:675` 已有缺基线／坏GDP原件反例，该文件按规则属于heavy |
| **贷款：固定2期不表达一月重置和9组维度** | 仅提供合法一月贷款发布，验证不要求上年十二月；另提供五月、七月而缺六月，要求列出六月各借款人/期限父项，不能采用旧月份差分 | 可轻量；复用 CA`:4625` 的公开导入与投影路径，不直接捏造选中状态 |
| **两项PMI：指标存在不等于所需维度／共同月份存在** | 合法导入两个连续月，损坏最新月原件；沿 CA`:4310` 验证两公式不恢复旧结果，并通过预检读回最新月所需 `production/new_orders/finished_goods` 维度。缺字段原件应由解析入口拒收，不能直接植入半套声明 | 可轻量；现有拒收逻辑复用，新增的是预检诊断断言 |
| **库存：共同月份和受影响输出标识缺失** | 库存七月、PPI七月与八月均合法：v2必须采用七月PPI；仅令七月PPI未知/未来或损坏，八月PPI仍好，验证不能错配八月，也应明确七月 `headline/yoy` 缺口。同时核对v1保持自身冻结语义 | 可轻量，需通过完整注册目录审核后启用v2；不直接修改已注册manifest |
| **OMO：漏到期投放及股票日期父依赖** | 复用 CA`:4783`，仅损坏实际到期投放或所采用日期父项，当前投放保持有效；预检应指出历史操作日／日期父项及受影响净投放日，不能只列“当前金额1期” | 可轻量；涉及03股票核心输入，只消费03接口，04不改核心校验分支 |
| **政策利差：事件与结果日期关系未进入父需求** | 复用 CA`:5097` 的最新有效利率坏原件；再保留一份 DR007 日期之后的新利率公告，确认不能用它替代旧日有效利率。诊断必须列DR007日及应采用的政策事件日 | 可轻量；已有利差计算与原件守卫复用 |
| **美债可选／GDP必需分类需经预检证明** | 同一合法完整目录：Treasury未知PUBLIC只进入 `optional_gaps`；信用脉冲所需GDP虽目录P2，缺失仍进入必需 `gaps`。沿现有Treasury合法CSV验证拒收，不伪造PUBLIC成功值 | 分类反例可轻量。**当前合同下不能合法制造Treasury PUBLIC正例；heavy也不能消除这个合同限制** |
| **货币／广度：已有家族失败未关联实际比较或预热父项** | 货币当前4成员有效而上一可比发布不可见：当前标量仍可见、方向unknown，不凭空添加12个月同比要求。广度复用 CA`:13676`、`:14572`，只损坏实际消费的窗口行情／金额父原件；未消费未来原件不应阻断 | 可用小证券集合＋真实120交易日期fixture轻量验证选择边界。完整Worker、投影持久化和回放验收仍须heavy；不在04重建整个市场家族 |

特别注意：**未来或未知的新修订，不应自动破坏仍合法可见的旧版本**。需要失败的是“该结果必需的父输入不存在合法可见版本”，不是“数据库里出现过未来声明”。已有 `test_material_preflight.py:527` 和 CA`:6057` 可复用这个区别。

现有重型名单明确包含 `tests/models/test_material_preflight.py`，见 `tools/check.py:15`。新建轻量诊断文件可以复用 `tests/models/test_fixed_window_preflight.py:25` 的合法准入方式，以及 `tests/fixtures/public_context.py:24` 的公开选择／投影边界；不要把完整生命周期构建换个文件名冒充轻量。必要整合heavy及最终同版本全套由主代理统一调度。

**5．精确改动落点与03／06整合边界**

当前源码仍只有 `src/pring_cycle/material_preflight.py`，**尚不存在上下文预检子模块**。建议04新增 `src/pring_cycle/material_preflight_context.py`，集中承接：

1. `material_preflight.py:508` 的父诊断：升级为按**公式版本、结果期次、父维度、基线关系、消费cutoff**生成需求，再复用真实家族选择和原件守卫。
2. `material_preflight.py:353` 的上下文投影检查与失败解释：保留具体派生状态，如 `incomparable_gdp_vintages`、`period_mismatch`，并返回实际父版本血缘。
3. 上下文 `input_warmup_missing` 的范围说明：保留自然日单位，把粗略最早日期检查与“实际父需求已满足”明确分开。
4. 必需／可选仍交由现有 `ContextReplayScope` 决定；GDP作为必需公式父项不能因目录P2被放进可选缺口。依据：`context_replay_scope.py:94`。

建议需求记录至少包含：

`formula_key/version、catalog_owner_metric、output_metric/dimensions/period、parent_metric/dimensions/period、baseline_relation、lookback_unit、consumer_business_date/cutoff、selected_claim_id、original_identity、reason`。

03继续拥有 `material_preflight.py:431` 的核心历史分支；06继续拥有融资来源、维度和选值合同。04不要改二者，也不要重写01的日历、持久预检收据及读取入口（`:43`、`:79`）。由主代理顺序接入上下文子模块调用即可。

04完成父需求诊断也不能直接将整体 `checks_complete` 改为 true：当前仍保留其他未完成检查，见 `material_preflight.py:409`；完整目录预检就绪判定应留给后续整合票。