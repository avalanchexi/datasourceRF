# 剩余 P1 原始来源的新目录消费边界

2026-09-08；HEAD `395dde73b93169d78374bb72a763641144c98dca`，绑定文末实际工作树源码指纹，包含父代理本批尚未提交的 A18 消费实现。本轮仅只读源码、既有研究和原件；没有运行应用/测试、联网、读取生产数据库或凭据、修改认证/模型。父代理的全套与单例复跑结果另行记录，本研究不以其代替来源验证，也不宣称856项一次全过。

**排除指定市场家族后，剩余 P1 原始来源恰为4项：DR007、Shibor、RRR事件、期货仓单。它们都未进入新目录来源消费守卫；其中3项现有 TuShare 实际入口还会更早因目录解析缺少 database_path 而失败。** 可直接实施的最小批次是 TuShare 新版本解析贯通加 DR007/Shibor 的精确来源契约；RRR可复用真实央行原件验证两个范围，但不能自动扩成完整政策状态；仓单还需多仓库选择和真实来源标签处理，不能只增加一个 metric 白名单。

计数依据：[catalog.py 的42项P1](../../src/pring_cycle/catalog.py#L46) = 已实现来源消费的 A18＋LPR共19项 + 本轮4原始指标 + 4派生指标 + 本轮排除的15项市场指标。19项仅表示代码路径已实现，不是19项已正式认证；61项目录登记也不表示全家族已采用。GDP为P2，不混入本轮分母。

## 首拒绝点与已有消费者

| 对象/入口 | 当前确定分支 | 最窄修复/验证边界 |
|---|---|---|
| DR007、Shibor、仓单：`TushareContextAdapter.acquire_scalars` → `ingest_context_scalars` | [tushare_context.py L1203–1206](../../src/pring_cycle/tushare_context.py#L1203) 调 `metric_definition` 未传 database_path；[catalog.py L409–414](../../src/pring_cycle/catalog.py#L409) 对真正新版本报 `KeyError: unknown_metric_definition_version`。即便新定义为 awaiting，仍先受此限制 | 在真实取得/原件收据路径下传数据库解析新目录；不能仅直接构造 SourceClaimInput 绕过实际入口求绿。`targeted_context.py L127` 也走该路径，且其异常分支只捕获 TypeError/ValueError，不能把本例 KeyError说成已被准确分类的语义失败 |
| 4项 certified 声明直接到 EvidenceRepository | [source_contract_review.py L117、L176–177](../../src/pring_cycle/source_contract_review.py#L117)：`official_source_members` 对4项均None，LPR/CPI字典也无4项，报 `registered_source_contract_not_implemented:<metric_id>` | 这是解决上行目录解析后的下一拒绝。来源守卫只由 certified 声明触发；RRR awaiting候选可沿官方路径存储，但不是模型采用 |
| RRR官方导入 | [official_context.py L364–374](../../src/pring_cycle/official_context.py#L364) 已传database_path，故可直接抵达上述守卫；[source_families.py L51](../../src/pring_cycle/source_families.py#L51) 只允许 `中国人民银行 / www.pbc.gov.cn / pbc_rrr_notice` | 不能把CSRC/吉林原件换URL伪装成PBC；PBC回顾原件可做新目录真实纵向测试 |
| 选择器：DR007/Shibor | [search_evidence.py L89–155](../../src/pring_cycle/search_evidence.py#L89)：DR007无维度可用`{}`；Shibor已有overnight/1w/3m三成员 | 数值、质量和认证都合格后还必须满足PUBLIC/SYSTEM与目标日上界。仅有官方值而PUBLIC未知，不能强求历史目标日selector成功 |
| 选择器：RRR | `required_dimension_members`无RRR；有scope/measure维度，先报 `dimension_contract_unavailable` | 两个源范围要可分别选取。不能要求每次事件都含所有历史范围或3个measure；也不能将日常“无新公告”生成0。现event跨期选择只对OMO rate，不可未经语义判断把RRR调整事件当作持续利率 |
| 选择器：仓单 | [metric_contracts.py L40–43](../../src/pring_cycle/metric_contracts.py#L40) 最低成员只有symbol＋registered_receipts；selector L121用维度**精确相等**。真实4键明细因此不能等于2键要求；单改成subset后仍会有多仓库>1条与L152“恰好1条”冲突 | 应按品种/最低measure收集符合身份的多仓库观测，保留每条claim；不能随便选一个仓库或把总计与明细叠加。worker/evaluation已对仓单用subset检查，不能拿其通过当selector一致 |
| 定向仓单取得 | [targeted_context.py L59–85](../../src/pring_cycle/targeted_context.py#L59) 日频方法表没有futures_warrants，返回 `targeted_tushare_family_unavailable`；完整worker另有仓单分支 | 若这一批目标包括“缺口定向补齐”，还需把明确symbol的仓单范围接入实际定向入口；只完成adapter批量取得不等于搜索/定向链已通 |

上述均为静态源码确定分支，没有在本轮执行新RED。当前 `[official_source_members → OFFICIAL_CONTEXT_FAMILY_BY_METRIC]` 路径专为NBS/PBC宏观家族；DR007/Shibor/仓单不在该family map，不能只往成员函数增加它们而遗漏provider路由。TuShare正式交付provider精确为`tushare`，CFETS/交易所官方原件承担抽样证据，不把两个身份合并为同一provider。

## 最窄来源契约

下表采用现有v3的**结构字段**作为新目录比较基线，不继承其certified标签、不更改旧v3或绕过旧guard。四项release_rule均`source_schedule_required`，release_timezone均`Asia/Shanghai`；这些字符串不赋予固定公开时间。

| metric_id | 实际现有provider / API、源字段 | source_codes | unit / allowed_units | frequency / release_event_family | 维度与期次的最窄绑定 |
|---|---|---|---|---|---|
| `CN_DR007` | `tushare`；`repo_daily`，只取`weight`；`ts_code=DR007.IB`且`repo_maturity=DR007` | (`CN_DR007`,) | percent / (percent,) | daily / cn_dr007 | `{}`；business_day；start=end=trade_date |
| `CN_SHIBOR_ON_1W_3M` | `tushare`；`shibor`；on→overnight，1w→1w，3m→3m | (`CN_SHIBOR_ON_1W_3M`,) | percent / (percent,) | daily / cn_shibor_on_1w_3m | 仅`tenor`三成员；business_day；start=end=date；同日三期限分别存在 |
| `CN_RRR_EVENT` | `中国人民银行`；`pbc_rrr_notice`；真实回顾分支`rrr_change_pp` | (`PBC_RRR_NOTICE_HTML_V1`,) | percentage_points / (percentage_points,percent,hundred_million_cny) | event / pbc_rrr_notice | scope＋measure；event；start=end=**生效日**。本轮真实源仅rrr_change→percentage_points，不把3个允许单位都用在rrr_change |
| `CN_FUTURES_WARRANTS` | `tushare`；`fut_wsr`；pre_vol、vol、vol_chg | (`CN_FUTURES_WARRANTS`,) | tonne / (tonne,kilogram,sheet,lot,barrel) | daily / cn_futures_warrants | symbol,warehouse,exchange,measure；business_day；start=end=trade_date；单位按实际品种/源行，不跨单位加总 |

目录字段依据：[catalog.py L113–129](../../src/pring_cycle/catalog.py#L113)、[L341–380](../../src/pring_cycle/catalog.py#L341)、[L501–618](../../src/pring_cycle/catalog.py#L501)、[L661–684](../../src/pring_cycle/catalog.py#L661)。仓单v2主unit是scalar、v3取allowed_units首项tonne；不要用默认v2主单位判断正确新定义。解析依据：[DR007/Shibor L603–649](../../src/pring_cycle/tushare_context.py#L603)、[日标量 L1609–1633](../../src/pring_cycle/tushare_context.py#L1609)、[仓单 L393–466](../../src/pring_cycle/tushare_context.py#L393)、[RRR L1328–1420](../../src/pring_cycle/official_context.py#L1328)。

**DR007/Shibor。** 单位就是百分数年利率，1.3859不是0.013859，也不是138.59bp。DR007不能换成R007、FR/FDR007、Shibor，weight不能换open/close或weight_r。同一期缺一个Shibor期限应未完成，不能复制另一期限。现transmission只对满足DR身份的行生成标量，错行会被过滤；正反例必须从公开取得入口检查缺件，而非要求每一个被过滤行都已有独立异常码。

**RRR。** 真实2025-05-15回顾原件的准确两成员是：

- `{scope:excluding_5_percent_institutions, measure:rrr_change}` → -0.5 percentage_points。
- `{scope:auto_finance_and_financial_leasing_companies, measure:rrr_change}` → -5 percentage_points。

这两个数不能相加成全市场-5.5。当前parser还存在`all_eligible_financial_institutions`分支，以及合成表格的`post_change_rrr→percent`、`released_funds→hundred_million_cny`；它们的代码存在不代表此PBC原件证实了对应字段。CSRC实录对特定两类机构的5%→0%是独立可信事实，但仍不是当前PBC parser的输出，不借它给广范围补后值或资金。当前官方守卫的日期分支只对business_day允许start=end；其他类型按月/季边界检查。**增加RRR时必须给event生效日单独分支**，否则2025-05-15会被当作不合法月界拒绝。不得改成05-01/05-31来迁就代码。

**仓单。** metric已有symbol集合`CF,CU,PP,RB,RU,SC,SP,TA`；TA请求源代码实际为PTA，返回核对PTA后规范为TA。measure准确映射为`previous_registered_receipts / registered_receipts / registered_receipts_change`。原响应某字段空时当前parser省略该scalar，不补0；变化量允许负数。symbol/warehouse/exchange不应空，实际存在的同名仓库跨不同品种不能合并；总计、保税/完税、仓库/厂库层次必须由原表定位约束。

已存目标日快照中CU/RB/RU/SP的exchange为SHFE、CF/TA为CZCE、PP为DCE，**SC也为SHFE**。SC官方场所与TuShare交付标签需明确区分：[旧快照](evidence-13/readonly-checks.json)中弘润油储SC、SHFE、1027000桶与官方明细一致；[现测试 L222–278](../../tests/adapters/test_tushare_context.py#L222)的SC/INE、1200桶是合成形状。不能从该测试推断真实交付一定返回INE，更不能以硬编码SC→INE把真实SHFE标签无说明替换或拒绝。最窄契约保留真实provider标签，官方场所映射如需规范化应另显式记录；不重新冻结未证的郑商所年度、等级、折算维度。

仓单最低模型范围仍为8品种的当前registered_receipts，不缩成已有官方样本的5品种；pre_vol和vol_chg可以按真实披露保存，不能因这两个字段缺列就发明数值。现1000行上限已修：[tushare_context.py L35–37、L468–503](../../src/pring_cycle/tushare_context.py#L468) 满限拆日期、单日满限拒绝；[研究13 L74](research-13.md#L74)记录的1200风险是历史状态，不能再次当当前待修。

## 可用真实原件、独立期望与时间边界

本轮未重做已有全量审计；对下列数值锚点仅复用原表定位和既有对照，并重新只读校验原件字节。旧研究13对DR“缺同期值”的结论已被 [DR增量](dr007-followup.md)更新；没有再请求旧失败URL。

| 家族 | 已有官方原件和独立期望 | 能直接用于的测试 | 仍未知的资格 |
|---|---|---|---|
| DR007 | R1：JSON `data.lastDate=2026-08-28`；records中唯一DR007的`wghtdAvgRepoRate="1.3859"`。R2官方片段表头为加权利率(%)；同一行close=1.3806、open=1.3700 | 确认响应日期、唯一产品和加权字段。错误close导致利差-1.94bp而正确值条件算术为(1.3859−1.4)×100=-1.41bp | head.tstext为9月7日响应生成时间；publishedTime=2200是请求配置，不是目标日首次发布。没有可靠发布日期，不能按统计日次日00:00赋PUBLIC |
| Shibor | R3：records[0].showDateCN=2026-08-28；ON="1.3390"、1W="1.3870"、3M="1.4300"。R4准则原件L436/L482写11:00发布 | 三期限1.339/1.387/1.43 percent，精度不由浮点显示位数改变；缺3M不以1M或3M前值代替 | 常规11:00规则已有，但这份历史JSON没有该日首次/更正版本时刻。head生成时间不是历史发布时间 |
| RRR | R5央行回顾HTML L341逐字载两范围和降幅；生效2025-05-15；可见页头L293为2025-11-11 17:00:09。现fixture与R5字节完全相同 | 当前公开parser已在旧测试/根记录返回两scope、{-0.5,-5}；请求2026-05会被period_identity_mismatch拒绝。用真实R5贯穿新目录导入，无需重下载 | 11月回顾时间可以是该文时间，不能冒充5月原始公布；2026窗口最近前置和完整事件序列、阶段期限终点仍未证 |
| RRR原始公开补证 | R6证监会原实录：2025-05-07日精度、特定机构5%阶段性降至0%；R7吉林官方转载：2025-05-15生效和调整值 | 主机构域、源身份/时间精度错配反例；保留真实URL，不伪装为R5 | 真实PBC原通知宿主仍缺；实录没有本次措施阶段终点；日期可按既定次日本地日规则准备，不能用后期meta或搜索片段时刻增加精度 |
| 仓单 | R8：上期所全品种2026-08-28表，L9统计日，L10说明“期货为已制成仓单的货物数量”。铜分表L22/23吨，国储天威L27/28当前225、L29变化0；SC弘润油储L3065/3066当前1027000、L3067变化0，单位桶 | 双品种/两单位/仓库身份的独立锚点；225吨和1027000桶不可直接相加。R8多处同仓名，必须绑定品种表头 | 已有CU/RB/RU/SP/SC五品种134次同名对照，不是完整行覆盖；PP/CF/TA官方原表与单位/身份、全家族PUBLIC仍缺。统计日及期号不是可靠发布日期 |

官方URL与精确原件路径列于文末R1–R8。DR相关 [source-inspection](evidence-13-dr007-followup/source-inspection.json) 和 [真实取得回执](evidence-13-dr007-followup/receipts.json)、Shibor/仓单的 [原回执](evidence-13/receipts.json)、[研究对照](evidence-13/research-checks.json) 保持原状。仓单原文只列当前及增减的行，不能用当前−变化算出的previous冒充原页直接披露；独立算术可标派生核验，公开API的pre_vol仍按真实返回处理。

重要渠道差别：R1/R3是CFETS结构，R8是官方HTML，**都不是TuShare API响应原件**。现有生产适配器没有CFETS DR/Shibor JSON或SHFE仓单HTML直接消费家族；将其交给`official_context`不会因为官方域就自动成功。最窄实施沿用已授权“TuShare交付＋官方抽样”，不用新增直连适配才能修现入口。测试可用官方独立数值构造明确标为synthetic的TuShare response来验证真实public adapter/receipt链；不能把这个合成response说成真实历史TuShare请求证据。本轮指定材料没有找到可绑定本三家族具体请求/字段的原始TuShare传输回执；旧claim快照不是原API响应。正式来源review时须复用确有的请求原件关联或做一次真实授权取得，不能由研究文档重建过去的SYSTEM时钟。

## 下一批公开测试切片

1. **DR007＋Shibor同一天、两API、四个标量。** 在新已登记目录上调用`TushareContextAdapter.acquire_scalars(... transmission(...))`，仅替换外部transport为明确synthetic的TuShare schema，使用R1/R3独立数值。先复现missing database_path，再复现来源守卫未实现，最后验证四个声明的provider=tushare、字段、单位、日期、receipt原件及definition_version。不要只调用守卫或直接append跳过两个首拒绝。针对单独DR scope，定向入口仍调用两个API再按metric过滤；测试请求分母如实记2，不称一次。
2. **时间正反例准确区分层次。** UNKNOWN PUBLIC的真实来源契约允许新SYSTEM取得后在基础EvidenceRepository.SYSTEM读出合格值，但PUBLIC查询为空。`TargetBoundEvidenceRepository`对SYSTEM也加目标日PUBLIC上界，所以历史target selector仍不可采用；这个失败是应有边界，不靠固定11:00/15:30/22:00填时间取绿。另用明确标识为测试设定的可靠PUBLIC事件做cutoff前后软件行为正例，不能把测试设定宣称R1/R3已补历史PUBLIC。
3. **RRR真实R5，两scope、一个原件/一个回执。** 用新目录调用`ingest_official_context_document`，period请求2025-05、观测事件日2025-05-15、PUBLIC先用回顾页真实11月时间。验证两值、两范围和单位；错误年拒绝，保留原件无部分声明；新值修订没有新公开时间则PUBLIC不得继承。新增event日期分支及scope成员策略后，从select/投影检查两条独立信息。不能为了正例把两类降幅合成数，或将两类机构后值0当全市场后值。
4. **仓单从部分样本开始验证消费，而不宣布8品种完成。** 用R8锚点构造明确标为合成transport的CU/SC响应，保留SC源exchange=SHFE和桶；两品种可入库后，完整8品种scope必须仍显示缺件。对同一品种增加第二仓库，验证selector收集各合格claim而非“只能1条”。再验证总计/分区/明细不能重复合并、缺vol不补0、单日1000条保持不完整、PTA→TA规范化与源symbol核对；CF/TA单位的合成测试不替代其缺官方原表。

RRR成员策略要按已证明事件范围约束，不把所有可能scope做固定每天必需；仓单要按官方身份与交易所形状保持多行。本研究提出的是这些源事实要求的代码边界，没有自行冻结未来所有RRR范围、仓单年度/等级聚合规则，也没有缩小指标家族。

## 派生指标的实际通路

`CN_DR007_POLICY_SPREAD`、`CN_ORDER_INVENTORY_SPREAD`、`CN_PRODUCTION_ORDER_SPREAD`、`CN_CREDIT_IMPULSE`是4项派生，见 [catalog.py L205](../../src/pring_cycle/catalog.py#L205) 与 [source_certification.py L18](../../src/pring_cycle/source_certification.py#L18)。它们若被错误包装成certified原始SourceClaimInput，也会落到未实现守卫；这不是正常的派生消费路径，不能加provider=`derived`来掩盖。

真实派生路径是：[ContextProjectionRules L90–147](../../src/pring_cycle/context_projection.py#L90) 校验公式版本→按新definition_version读取合格父输入→`_difference_row`等计算→[EvidenceRepository.append_derived_observation L904–951](../../src/pring_cycle/evidence.py#L904)保存公式、父claim版本、as_of_mode/cutoff。该方法不走原始来源provider守卫；无父输入会拒绝，公式不在支持列表会拒绝。不能因此推断任意派生值都已认证，必须核父来源/目标日资格。

DR利差在 [context_projection.py L797–828](../../src/pring_cycle/context_projection.py#L797) 用DR007及不晚于其日的7天政策率，百分数差×100=bp；R1的1.3859和已有OMO1.4只给出条件算术-1.41bp。DR历史PUBLIC未知时，历史target缺输入，不输出已验证有效利差。缺DR或OMO不得当0；派生PUBLIC只在全部父输入有PUBLIC时取最大值，见 [L1163–1185](../../src/pring_cycle/context_projection.py#L1163)。其余三项沿已有公式/父输入验收，不在本轮重复研究。

## 最小剩余证据与交付边界

DR007/Shibor可以立即推进软件入口与来源结构验证：同期官方数值已在手；真实PUBLIC、实际交付请求原件和正式review状态仍分别处理。RRR可以推进真实已知事件的消费，完整窗口/最近前置/阶段效力仍未知；先前4公告均非RRR、会议材料未给调整或不调整声明，不能据此宣布无事件。仓单5品种已证片段可验证明细消费，PP/CF/TA与身份/时间缺件继续列缺，不再重复旧挑战、超时地址。

沿用已接受的本机个人非商业使用和官方抽样策略，不要求每历史行再找第二来源、不新增采购或用户批准泛化门。未在本轮读取许可或生产库，不推断用户缺许可。来源结构守卫通过、研究原件校验通过、真实认证/模型采用/120日重放是不同验收；本报告只完成前两者的只读准备。

## 精确输入与原件

| Input | Local path | bytes | SHA-256 |
|---|---|---:|---|
| input | [source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 9540 | `bd721b240abafd36db5b1781052d25612c928b07672b7011d552faeb04489bd7` |
| input | [metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| input | [tushare_context.py](../../src/pring_cycle/tushare_context.py) | 68390 | `e48f670b8f25b596cb4612cfb6e1f587727d59cf98747e9ceacc80c6fa6cb2bd` |
| input | [official_context.py](../../src/pring_cycle/official_context.py) | 80147 | `0e6f57ea5770e3d35b2dbbd3255a8df9e1237296f2c6b97c1d6e2d54dbc20252` |
| input | [catalog.py](../../src/pring_cycle/catalog.py) | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| input | [source_families.py](../../src/pring_cycle/source_families.py) | 2487 | `420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e` |
| input | [targeted_context.py](../../src/pring_cycle/targeted_context.py) | 5936 | `065a5342fc01694cd832c237122f706914a95a9a5a41febaea054a16fbdee25a` |
| input | [search_evidence.py](../../src/pring_cycle/search_evidence.py) | 14229 | `46e2338c6458bd7d26480a6c8fbf8647f1d5fe10d66d6481806155a3087b2a99` |
| input | [evidence.py](../../src/pring_cycle/evidence.py) | 52835 | `5ebc483dacb7ebbfa3a04a2be3e907fb12315aab8a7d13abbf525f531c4b8663` |
| input | [context_projection.py](../../src/pring_cycle/context_projection.py) | 79189 | `b05f0d12ca3e169e49639fef0123117ec75c6f86e5e7bb873febf7b929edfa31` |
| input | [worker.py](../../src/pring_cycle/worker.py) | 57763 | `1dadf9751e7be540a2c06983017b8d3787e7fb7f3233c8cae8eb25624b505f77` |
| input | [model_evaluation.py](../../src/pring_cycle/model_evaluation.py) | 37574 | `b9b9fee837a03c3f8b746eef0006d85d69a4a127963b046e5daf794ab08552df` |
| input | [source_certification.py](../../src/pring_cycle/source_certification.py) | 15659 | `e585ce624de989ec6f9def5ff4f44130ebad22c449d6c8a1a2f0c9d64e44a963` |
| input | [test_rrr_context.py](../../tests/adapters/test_rrr_context.py) | 9981 | `d341cc5468e86ea28c1fa2821c9c936715cc5d3bb10a2f45176335d32365da8c` |
| input | [test_tushare_context.py](../../tests/adapters/test_tushare_context.py) | 32439 | `f4715a16ae1b3a93f7ecec6b18dd26d7635d03a0ff00ee54598490c987a75ae4` |
| input | [research-13.md](research-13.md) | 31765 | `dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1` |
| input | [dr007-followup.md](dr007-followup.md) | 11885 | `8c8776372ecd26ca849275680d8368b73980678d3d5da9504f178a707ae9b462` |
| input | [rrr-original-notices-followup.md](rrr-original-notices-followup.md) | 9049 | `b0128252a6b8bedf89cc607368a1370f39c6daacd74b62dbaaffa43480c74c22` |
| input | [rrr-public-boundary-after.json](rrr-public-boundary-after.json) | 773 | `b46c8358c4c590b72a8948d48d774e4a925782bd2a99f1e00710eaceef823aba` |
| input | [source-inspection.json](evidence-13-dr007-followup/source-inspection.json) | 5497 | `b712ea78e467d75e188a0617c3ef6046141778e5ce002de31d68d58d551c5ee4` |
| input | [receipts.json](evidence-13-dr007-followup/receipts.json) | 3277 | `0b3ff3a02081e9dbb2727d6adebb27b178bf6c49aa18b2aab1ee70ca775014aa` |
| input | [receipts.json](evidence-13/receipts.json) | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| input | [research-checks.json](evidence-13/research-checks.json) | 85434 | `921c7b9de8e5bb75cdadc5809257f5f0fc9e089265c96af0489047f5055922ed` |
| input | [readonly-checks.json](evidence-13/readonly-checks.json) | 1868241 | `8bd95b88c106b8bee6eac44bf1b74d6a12ebcbb827dfab659362c0cefd3090ed` |

| Raw / saved official URL (not requested) | Local path | bytes | SHA-256 |
|---|---|---:|---|
| [R1](https://www.chinamoney.com.cn/ags/ms/cm-u-dlrp/PrDlyBltn?lang=en&indexType=markInterBankVOList&searchDate=2026-08-28&publishedTime=2200) | [raw](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d) | 1425 | `d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d` |
| [R2](https://www.chinamoney.com.cn/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html) | [raw](evidence-13-dr007-followup/b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96) | 10948 | `b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96` |
| [R3](https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/ShiborHis?lang=cn&startDate=2026-08-28&endDate=2026-08-28) | [raw](evidence-13/365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62) | 2112 | `365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62` |
| [R4](https://www.chinamoney.com.cn/chinese/bkshibor/) | [raw](evidence-13/043ae07820bc91ae91b00fd4468cc4f7938eb911ae2d1f75efc5237407c13ae9) | 49650 | `043ae07820bc91ae91b00fd4468cc4f7938eb911ae2d1f75efc5237407c13ae9` |
| [R5](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html) | [raw](evidence-13/7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5) | 31945 | `7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5` |
| [R6](https://www.csrc.gov.cn/csrc/c106311/c7555758/content.shtml) | [raw](evidence-13-rrr-original-notices/d9dd4873a3005ca20a2985a36055f8b3a14f6d0b67977186351857cc4a011846) | 100491 | `d9dd4873a3005ca20a2985a36055f8b3a14f6d0b67977186351857cc4a011846` |
| [R7](https://jr.jl.gov.cn/jrzx/zyjrxxzz/gj/202505/t20250512_3454788.html) | [raw](evidence-13-rrr-original-notices/f1d24e69b5ef8bb4526534fa5cd32f0728a8ff0903b3ff5381d1acb03c06bf83) | 24186 | `f1d24e69b5ef8bb4526534fa5cd32f0728a8ff0903b3ff5381d1acb03c06bf83` |
| [R8](https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_20260828/ZH/all.html) | [raw](evidence-13/aa7493a24425f6f95f9743bc8e53725deb0e2cbba10857d97443758eedef4e39) | 147318 | `aa7493a24425f6f95f9743bc8e53725deb0e2cbba10857d97443758eedef4e39` |

唯一新增文件：`.scratch/pring-data-acquisition-repair/remaining-p1-source-consumers.md`。最终SHA/bytes与本地链接校验结果在交付消息给出。网络请求0；应用/测试执行0；数据库/认证/模型写入0；旧报告、旧CAS和源码未修改。

Input fingerprint observation UTC: `2026-09-08T01:55:27.017271+00:00`. Selected raw files: 8; exact bytes: 368075.
