# A18 逐值核验后的认证输入与下一公开入口

研究日期：2026-09-08，Asia/Shanghai。最终复核基点 HEAD 为 `6341dd2be0699734512e672c4ff2618ca624d4fc`；`official_context.py` 的产能列宽、M1/M2 换算及 parser v0004 已随该提交完成。本文最初读取发生在前一基点 ca27807 的实施阶段，最终交付已重新读取变化输入并对齐 6341dd2，不保留过期工作树状态作为当前结论。本文只读规范、源码、既存 JSON/官方 CAS，用 Windows 标准库检查身份和统计；没有调用应用、网络、账户、数据库、认证、模型或生产。唯一新增文件是本文，不重写原准备包及其审计状态。

**可以立即形成新的不可变 A18 只读复算准备包。数值核验已不再是笼统的“1840 格待审”：根代理逐格复核覆盖全部 1858 个旧标量，其中 1856 严格字面相符，1 个 M2 旧表示尾差已由当前 v0004 修复，1 个 Q1 产能累计属于既有同区间源列复用。后两项必须分别保留，不能给旧包改为全绿。新准备包仍不是来源认证包、新目录、候选模型或生产入库。**

旧包的 [准备说明](p1-official-preparation.md#L3) 与 [preparation.json](evidence-13-preparation/preparation.json) 是历史状态，不能原地更新。最新依据是各家族原值审计及根复核：[贷款 279](verification-official-parsing/research-verification.json)、[社融 837](verification-official-parsing/social-financing-verification.json)、[OMO 252](verification-official-parsing/omo-verification.json)；其他已完成家族见下表。本研究没有重做这些逐格审计，而是核对其输入边界和认证承接能力。

## 已经具备什么，以及真正仍缺什么

[规格第 3—8 条](spec.md#L93) 要求原件/标准化分开、真实接收与验证时间、可靠 PUBLIC 依据，以及来源认证、数值有效、点时可见分别判断；[第 13 条](spec.md#L103) 沿用官方抽样认证渠道，不要求每条历史值另找第二来源。[票 13 的五项验收](issues/13-remaining-p1-evidence.md#L17) 还要求发布制度、必要历史、派生和实际候选矩阵。[票 19](issues/19-immutable-candidate-catalog.md#L16) 才承接完整目录、机器拒绝和新候选；本研究不替代该票，更不重新冻结待定业务规则。

| 认证输入轴 | 已有、可写入新准备包的事实 | 真正仍缺或需要明确的条件 | 不构成什么阻断 |
|---|---|---|---|
| 字段、身份、数值、单位 | 250 件精确原件，268 个家族结果，11 家族/18 指标/1858 标量；逐格原文定位、负数/真零、统计起止和实际成员均有审计材料 | M2 用最终解析器重新产生新结果；Q1 产能累计明确映射到当季同一源格，不能当作独立累计列。完整范围还须绑定所采用定义和家族成员规则 | 不再需要把已通过的贷款/社融等全部重复当“没有官方数值”；也不要求新增逐值双来源对账 |
| 原始取得及验证 | 旧包记录原件 SHA/字节/URL；另有九件原件复制时刻、旧清单与执行身份。本轮重验 250/250 CAS 摘要相符、总计 20,069,217 字节 | 已读取文件中没有 A18 的逐请求原始接收/验证回执。若其他已有存储有严格关联记录，可继续只读恢复；不能由文件 mtime、复制或本次解析时钟补造。新导入可以产生新的真实 SYSTEM 资格，但不能恢复 2026-03—08 的旧 SYSTEM | 不阻止对已有字节再作纯解析、形成新研究准备包；不要求为了补一个过去时钟重新下载同页 |
| 页面标示的公开日期/时间 | 原页可见栏及 meta 已保存，268 个旧解析结果都有时间词法对应；不是完全没有发布时间材料。NBS 多为分钟，PBC 有秒级文本；具体反例见下节 | 把“保存页上写了什么”与“该时间适用于哪一版内容”分开。逐版本保留时间证据位置、精度、项目时区解释及是否可靠的判断，冲突/未证不得自动升级 | 本次未要求每个历史 PUBLIC 都必须有当日由本系统抓取的 HTTP 回执；SYSTEM 抓取记录不是历史 PUBLIC 的唯一证明方式 |
| 首发版本、修订/回溯 | 每个已存原件哈希就是具体字节版本；初步数、可比口径、M1 回溯和迁站 createDate 等信息可直接加入版本说明 | 对声称的历史 cutoff，需可靠发布事件与该数值版本的关联，或能解释后续修订/回填的官方版本依据。已知改变值的页面不能继承旧时间。现有材料尚未给全部 cutoff 作这种认证结论 | “未发现修订”不等于已经证明未修订；但 createDate 较晚也不能反过来直接断言发生数值修订，更不能无证把全部页面一律判假 |
| 渠道、定义认证 | 官方域/家族、原字段与单位、已审原件、原代码及当前代码指纹可形成家族材料。NBS/PBC 直取与 TuShare 交付是不同渠道 | 正式绑定来源/定义版本、官方语义/时间/必要历史、实际使用范围；走 TuShare 的重叠指标另关联 TuShare 原件与官方抽样，不能用官方直取通过覆盖全部交付路径 | ADR0013 已接受本地个人、非商业、不可转让、未经许可不再分发，不应重复索要同一授权；也不应凭普通版权署名推断必须采购 |
| 新模型采用 | 来源准备材料可独立完成；已有确定性修复/回归可作为代码证据，不能充当真实采用 | 新目录/定义、选择与时间规则、公式、执行指纹、完整认证范围及候选实际读取仍待票 19 及前置验收；42 P1/61 项范围不是 A18 | 不必等五个市场家族、RRR、仓单全部补完才整理 A18；也不能为绕过 v3 拒绝只换一个模型 ID |

源认证的领域定义明确包括语义、字段、历史、时点、权限与使用许可；一次烟测或校验后的候选值不构成认证包。[CONTEXT.md](../../CONTEXT.md#L255) 同时规定实际取得/公开时点及不可变修订。[双点时 ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[官方抽样 ADR](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) 继续适用。

## 11 个家族逐项承接边界

下列数值分母都是旧准备包中的实际标量，不能相加为交易日数，也不声称覆盖全部原表字段。每行列出的材料可进入新包；右栏是来源/采用时仍须维持的具体边界，不是要求重新做一遍已完成审计。

| 家族 / A18 指标 | 可直接复用的独立结果 | 新包应保留的字段与定义边界 |
|---|---|---|
| `nbs_core_cpi`：`CN_CPI_HEADLINE`、`CN_CORE_CPI` | [8 月 46 格](p1-cpi-full-value-audit.md)，全部相符；同比/环比/累计平均涨幅、总体/扣食品能源身份 | 2026-01 每指标只有 MoM/YoY 两列，不造累计平均或 level；2026 基期与可比口径脚注随原件保留。旧 PUBLIC 只取到 6 月是选值/时间后续验收，不代表 7 月原件缺失 |
| `nbs_pmi`：`CN_PMI_ACTIVITY`、`CN_PMI_INVENTORY`、`CN_PMI_PRICES` | [7 月 56 格](p1-pmi-full-value-audit.md)，全部相符；每月活动4、库存2、价格2 | 原表 % 是扩散指数标度，规范单位为指数点，不是同比涨幅；原发布目标月份与后页回列的历史值分开；同月输入及调查口径保留 |
| `nbs_ppi`：`CN_PPI` | [8 月 69 格](p1-ppi-full-value-audit.md)，全部相符；出厂总体/生产资料/生活资料 | 1 月各类别少累计列是实际原表形状，不凑 72；2025 基期在 2026 启用的说明须随定义/版本保留；购进价不能替代出厂价 |
| `nbs_industrial_value_added`：`CN_INDUSTRIAL_VA` | [7 期 20 格](p1-industrial-va-full-value-audit.md)，全部相符 | 1—2 月合并累计实际同比与 2 月季调环比，不是独立 2 月实际同比。季调历史修订须按所用版本读取；2026-07 原页 15:00 不换为常见日程 10:00 |
| `nbs_industrial_finance`：`CN_INDUSTRIAL_FINANCE`、`CN_FINISHED_GOODS_INVENTORY`、`CN_INVENTORY_TURNOVER` | [7 期 70 格](p1-industrial-finance-full-value-audit.md)，全部相符；财务42、库存14、周转14 | 规上企业范围、累计收入/成本/利润、月末名义库存及周转天数原定义分别保留；官方可比同比不由跨页金额反算。周转天差不是百分比；价格调整库存的同期要求是另一层派生 |
| `nbs_capacity_utilization`：`CN_CAPACITY_UTILIZATION` | [3 季 9 个准备身份](p1-capacity-utilization-full-value-audit.md)：8 个独立字面格相符，Q1累计1个复用 | Q1当季和年初至季末同区间，数值可解释，但原表无第二个累计格；正式映射必须标明同源列关系及所绑定版本。当前修复仅拒绝非Q1缺累计列/坏同名行，未新增该源映射认证 |
| `pbc_money`：`CN_M1_M2` | [7 月 28 格](p1-money-full-value-audit.md)，27旧值严格相符，1个2026-02 M2应为3492200亿元；[当前修复](implementation-official-parsing.md#L22) 已有真实原件入口正负证据 | 新包保留原字面349.22万亿元、×10000、旧值3492200.0000000005及v4新值，不容差抹平旧包。M1新口径与历史可比回溯说明不能外推为其他家族已认证；不加入M0 |
| `pbc_social_financing`：`CN_SF_TOTAL`、`CN_SF_COMPONENTS` | [51 篇 / 31 月 837 格](p1-social-financing-full-value-audit.md)，全部相符；存量、存量同比、YTD增量及8分项 | 20个月存量/增量分篇、11个月合篇按真实发布各自关联；`stock_end_trillion`字段名不改变已规范为亿元的单位。8组成不是所有社融细项，不强制求和填缺；存量差不冒充当月融资，YTD转换另绑版本 |
| `pbc_loan_structure`：`CN_LOAN_STRUCTURE` | [31 月 279 格](p1-loan-structure-full-value-audit.md)，全部相符；主体×期限9成员，49真实负数 | 企（事）业单位、金融统计全口径人民币贷款不能替换为同页社融实体经济贷款。逐月YTD、万元/亿元/万亿元语义不混淆；本样本只有亿元/万亿元。1月自身及同年差分用既定公式，不产生伪零父项 |
| `pbc_tool_liquidity_monthly`：`CN_TOOL_LIQUIDITY_MONTHLY` | [8 月 × 8 工具 × 3 格 = 192](p1-tool-liquidity-full-value-audit.md)，全部相符；19负数、28真零 | 投放/回笼/官方净投放各有原文字面，净额算术只是附加核验；RRR行24个“-”不填0；月工具表不能拿来补每日OMO到期台账 |
| `pbc_omo_notice`：`CN_OMO_7D_AMOUNT`、`CN_OMO_7D_RATE` | [131 原件 / 252 格](p1-omo-full-value-audit.md)，全部相符；金额131、利率121；10个真实零操作无利率列 | 投放是7天期当日流量，不并入隔夜；无利率列不是0%或新政策事件。政策沿用/有效期、日历、到期及完全无记录是否表示0仍需各自证据，252字面核验不解决日净投放台账完整性 |

18 指标之外的 LPR、DR007、Shibor、RRR、仓单、4 项纯派生和 GDP 不进入 A18 分母。依据 [准备清单](p1-certification-readiness.md#L30)，DR007 同期官方数值已补，不能再报缺值；DR007/Shibor 的历史 PUBLIC 和适用渠道条款是独立问题。RRR 仍缺事件范围/阶段效力、仓单仍缺 PP/CF/TA 等官方范围材料；不缩范围替代认证。信用脉冲的 GDP P2 分母另验，不新增第19个 A18 或第28个 P1；OMO 日净投放的无记录完整性见 [边界研究](omo-missing-flow-boundary.md)。

## 取得、页头、首发三个时间事实的精确区别

本研究以标准库直接读旧准备及 [原 HTTP 回执](evidence-13/receipts.json)、[复制/导入记录](evidence-13/imports.json)、[旧 history 清单](evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec)：

- 250 个 `raw_artifacts` 全部 `acquisition_time=null`、`original_transport_receipt_in_this_package=false`、`historical_first_publication_certified=false`；268 个结果 `certification_state=not_performed`；1858 个标量全部 `definition_version=null`、`acquisition_ids=[]`。这是准备材料的真实字段，不等于读取了生产库并判定那里没有声明。
- HTTP回执15条，按A18精确SHA交集为0；imports13条，其中A18精确SHA交集9条。这九条包括目标期产能、CPI、工业财务、增加值、PMI、PPI、货币/金融合页、OMO和工具流动性页；复制发生在2026-09-06T16:16:32.045373Z—16:16:32.136766Z。它们证明复制的具体字节，不能改名为原始HTTP接收/校验完成。
- 旧history清单保存270份记录的原件/期次/家族/发布标签及整体代码身份、声称284次网络请求、browser_capture_records=0；没有逐记录started/received/validated字段。当前 `source_history._FetchedRecord` 也只有记录、内容、MIME、最终URL和状态，[源码 L33—39](../../src/pring_cycle/source_history.py#L33)；生成的记录仍只写原件、期次、release/public/URL，[L198—207](../../src/pring_cycle/source_history.py#L198)。因此不能从这个清单重新算出每次原始接收时间。此结论限定于已读材料，不声称其他未检查存储永远不可能找到原始记录。

**已有页头材料不是“时间全未知”。** 例如2026-07工业增加值原页标15:00；2026-02货币原页标17:00:01而createDate为18:51:11；2024-01贷款原页标2024-02-09 15:00:30而createDate是2025-12-10。OMO131个createDate中86晚于、43早于、2等于页头。各审计已给原文行及哈希。这证明不同字段不可互换，但单靠差异不能认定官方修订发生，也不能把迁站生成时钟当首发。

新包应把以下内容分别登记为**研究证据字段**，而非直接当数据库PUBLIC资格：页面字面和定位、分钟/秒/日期精度、元数据冲突、项目时区解释、对应内容哈希、原件取得状态、所需版本关联是否已审。已有官方页头可作为可靠公开时间判断的证据输入；若是后页回溯、已知修订却只有旧页头，或不能证明该时间对应当前数值版本，则该版本的PUBLIC资格保持未证。没有可靠日期时为空，只有可靠日期按下一本地日；[publication_times](../../src/pring_cycle/evidence.py#L31) 明确只转换可靠输入，**不认证证据本身**。

既有导入处理会比较同provider/身份与同源原件的前值：无更晚可靠时间的变值、或此前未知PUBLIC版本，会将新声明release/public置空并形成unresolved-publication事件；见 [official_context.py L297—345](../../src/pring_cycle/official_context.py#L297)。它只能发现仓库里已经有的历史，不能证明干净库第一次导入的旧页是首发版本。其release_event_id包含raw hash（L220），给出字节身份，但哈希本身不是公开时间证明。

## 下一可执行公开入口及其输入

**本阶段下一入口是现有纯函数 `parse_official_context_document`，不是 `model-source-certify`。** [公开签名和实现 L180—225](../../src/pring_cycle/official_context.py#L180) 接受 `content: bytes`、`family`、`source_url`、`expected_period`、有时区的 `fetched_at`。它校验官方来源、长度、统计期、源字段，返回标量及解析的时间标签；不创建收据/声明/认证或模型。可在规定 Ubuntu-22.04 / tywin / `env -u PYTHONPATH` / 非 editable 安装 Python 中对现有250原件再次调用，但本研究未执行。

需要的输入已经可从现有材料取得：

1. 精确旧准备SHA、250个原件SHA/字节/URL/期次、268个家族绑定及1858标量身份；先验证字节再解析，不用URL重新取得的不同页面替代旧内容。
2. 最终工作树与安装包匹配的代码/依赖身份、parser v0004、调用起止时钟、明确独立期望与审计文档哈希。父代理已完成本批全套741通过、0失败、977.15秒，57项关联及16项新增通过；完成后81个安装Python文件再次匹配，见前述实施记录。最终新准备包应绑定已提交6341dd2及其完成后确认的执行身份；本研究只读取完成记录，没有再次运行全套或安装指纹验收。
3. 新输出路径及不可变继承关系。现有 [prepare.py](evidence-13-preparation/prepare.py#L29) 的OUTPUT固定指向旧 `preparation.json`，`--write-report` 明确会写旧包；不能对旧文件使用这个选项来更新。默认重跑也以旧值/旧代码作比较，预期会报告版本或M2差异，不能为“过旧验收”还原修复。
4. M2保留旧表示与新精确期望/输出的差异，Q1保留同区间复用状态；其他标量按身份链接现有原文期望。新包可以拥有新的解析验证结果，同时仍标记source-certification/candidate-adoption未执行。

`fetched_at` 在纯函数这里只用于“不早于解析发布时间”的验证，[L190、206—213](../../src/pring_cycle/official_context.py#L190)；传本次真实验证时刻，应明确命名为parser调用参数。它不是原件当时下载时刻，不可以搬进旧 `acquisition_time`、历史SYSTEM或PUBLIC。为新包逐次保存本次执行时间可以且必要，但不会增加一个来源观测或发布事件。

后续若实施隔离环境的公开入库验证，已有 [ingest_official_context_document L239—276](../../src/pring_cycle/official_context.py#L239) 可导入精确字节：`document_import` 经 [AcquisitionRepository.capture L124—190](../../src/pring_cycle/acquisition.py#L124) 取得当前真实started/received，再完成标准化校验；[complete_validation L209—244](../../src/pring_cycle/acquisition.py#L209) 保存validated。声明使用receipt.received/validated，[official_context L346—369](../../src/pring_cycle/official_context.py#L346)，仓库还在最终append时推进实际availability，[evidence L273—281](../../src/pring_cycle/evidence.py#L273)。**这能创建现在才可见的新SYSTEM版本，不会恢复过去SYSTEM。** 对历史PUBLIC还须先完成上述页头/内容版本判断；当前该入口没有一个经审定的“将可解析旧页头强制标unknown”的导入参数，不应仅靠干净库首次导入成功就宣称通过时间认证。

同时必须显式选择已有、适用且保持待认证的定义；来源状态来自目录定义（official_context L364—366），函数名和返回 `stored_candidate` 不是独立认证门。当前 [metric_definition L396—412](../../src/pring_cycle/catalog.py#L396) 只登记v1、v2、v3和融资独立v2，不能传一个尚不存在的A18新版本字符串。新正式定义的注册/绑定属于后续票19承接；本研究不调用旧v3非市场入库来冒充新认证。已有 [真实M2原件公开入库回归](../../tests/adapters/test_official_money_units.py#L69) 展示原件、receipt v4、待认证及SYSTEM血缘可被验证，这只是隔离fixture证据，不是已执行A18真实候选矩阵。

## 旧认证入口为什么确定不可用于本批

这是直接静态调用链结论，无需访问生产或试发命令：

1. [CLI L382—389](../../src/pring_cycle/cli.py#L382) 的 `model-source-certify` 调用 `create_source_certified_candidate`。
2. [source_certification L105—114](../../src/pring_cycle/source_certification.py#L105) 先检查个人非商业确认参数，随后**无条件**调用 `require_source_contract("metric-catalog-v0003")`。
3. [source_contract_review L91—95](../../src/pring_cycle/source_contract_review.py#L91) 对v3且未指定metric_id的调用必抛 `source_certification_contract_unresolved:metric-catalog-v0003`。因此即使确认参数为真且新准备包完整，也在读取smoke之前拒绝；若确认参数为假则先报授权参数缺失，不能借此说v3门不存在。
4. [refresh_source_certified_candidate L249—257](../../src/pring_cycle/source_certification.py#L249) 也只接受candidate且catalog=v3，随后调用同一guard。不能通过旧 `model-source-refresh` 绕过。

这些函数原先是完整旧认证/候选路径，并非可独立写A18材料的API：`_package` 只对metric列表、smoke哈希、review_evidence、terms等描述做确定性哈希（[L349—375](../../src/pring_cycle/source_certification.py#L349)）；原流程使用冻结集合和旧review文档哈希，最终构造v0011模型并写candidate（L223—224）。新包不能只沿用它的 `source-certification-package-v0001` 名称或填certified字符串获得证据资格。旧 [verify_source_smoke_artifacts L323—357](../../src/pring_cycle/rehearsals.py#L323) 还要求真实network计数、匹配执行指纹、登记来源、scope与全套所需kind；新纯解析准备包不是这种smoke产物，不应伪造network_requests以便塞进去。

同样，[refresh_source_history L210—271](../../src/pring_cycle/source_history.py#L210) 虽会验原件hash再导入，但会写收据/声明并以当前导入时刻采集；它不是“只读刷新准备包”。`smoke_source_history` 会发现/抓取网页、存制品，且拒绝unknown-publication（L194—197）；覆盖检查只是固定首末期/数量和OMO日期间隔（[L538—575](../../src/pring_cycle/source_history.py#L538)），不能证明全部事件台账或每个PUBLIC cutoff。因此本阶段不执行这两个入口。

## 本次交付能支持的行动与停止点

可以继续新路径的当前纯解析复算及家族材料整理，保留原字节、页头/元数据、旧审计哈希、当前输出/代码身份和三种分开状态：1856旧字面相符、M2新修复结果、Q1映射待定义。这是已接受规格内下一可审阅交付，不需要重新做规格规划。

以下情形必须保留相应阻断而非中断所有准备工作：原件hash不符则停该件；最终代码/安装指纹未定则不宣告最终复算完成；未知或已知修订无新可靠时间则不授该版本历史PUBLIC；Q1源列别名未绑定则不叫独立累计原字段；缺失OMO完整性证据则不以无行推0；新定义/渠道包和票19前置未满足则不创建完整正式候选。历史120日、当前目标日演练、报告解释、激活和切换仍分别验收；A18本次没有任何一项生产或认证状态变化。

## 输入身份与复核范围

下面33项指纹已在提交6341dd2完成后重新读取并逐项复核；所列应用源码与当前HEAD无差异。初稿读取后，根代理在本批finalize时将三个根复核JSON回执由UTF-16规范化为UTF-8无BOM/LF，并更新票13完成进展；本轮直接复核发现初稿末尾指纹表的取样已晚于这些输入变化，33项均与当前字节匹配，因此保留其精确摘要；正文中过期的运行/提交状态及编码描述已纠正，不以临时编码版本替代当前复核。本文没有转换或修改任何输入文件、原件或旧准备包。本文所有本地链接在交付时检查存在；链接的行号是本次静态读取位置，后续合法修改不回改这份历史研究。

| 输入 | 字节 | SHA256 |
|---|---:|---|
| `spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `issues/13-remaining-p1-evidence.md` | 8104 | `c87d9e0e7526b91d9ee788b5d15d33d7c6475aaf92cc8a4b5c7ce45cb7e74fbf` |
| `issues/19-immutable-candidate-catalog.md` | 3443 | `5a873d6493b2b7d716944ca641cc2eb75f9093f249ef1db1f9b996c5a1cb4b57` |
| `p1-official-preparation.md` | 11901 | `1a1c6984c96df6da41c76a008c4f37419ef9b23621f6391e84e78e68c3444b5f` |
| `p1-certification-readiness.md` | 34721 | `0f3cb130613ee6cddbd535fff58ea11929dca2d0526ba1d2c484dbc25591f368` |
| `evidence-13-preparation/preparation.json` | 2767926 | `a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a` |
| `evidence-13-preparation/anchor-expectations.json` | 4152 | `e4ba9fe88c93701d7fa6ba7f2cca1e37387b95ba2f91771b320fa7be7035eafe` |
| `evidence-13-preparation/prepare.py` | 18456 | `e9295dcd722d9ff1f67e9fb0e57db6154c297510f80df344258b69971f638b27` |
| `evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec` | 94304 | `69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec` |
| `evidence-13/receipts.json` | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| `evidence-13/imports.json` | 5145 | `07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875` |
| `verification-official-parsing/research-verification.json` | 511 | `ef53422e447540668be2f727046c47b97ffe5f58da4ddaaea66c26138c8b7864` |
| `verification-official-parsing/social-financing-verification.json` | 557 | `7455dc5d85203bb5dfbeae2af24464ecd26b74e0b80823623df873c631c69bea` |
| `verification-official-parsing/omo-verification.json` | 194 | `111e6bc7d4eec4ddb5d15c43fbd6b63e14ba69796ffa82de48efeb863222797e` |
| `../../src/pring_cycle/source_certification.py` | 15659 | `e585ce624de989ec6f9def5ff4f44130ebad22c449d6c8a1a2f0c9d64e44a963` |
| `../../src/pring_cycle/source_history.py` | 26596 | `393420b63609d8dc12e63da21c3373fdd430c2d07304d4dfd34787d559577f2e` |
| `../../src/pring_cycle/source_contract_review.py` | 4706 | `ad377fafc71cbd26d8a3d06eaf71131c9111aecc436f84618032f11d70786e64` |
| `../../src/pring_cycle/official_context.py` | 80084 | `b1cb854a431e0b5f488d2b1330177785713e28806a99f6a0e880c798a1203aaa` |
| `../../src/pring_cycle/catalog.py` | 25699 | `59fcac0c8279c4b1acfe7bac4eab1688088571745ef539fc41728c3acd0eb83a` |
| `../../src/pring_cycle/evidence.py` | 52119 | `21c287dd453c56ddde09fd630b7736f85c58c3830fc82f5864faae3ffa463436` |
| `../../src/pring_cycle/acquisition.py` | 14086 | `eee45f82bf5a6d058dfc781ad0f5908914d09bf3992161319c8dcb98b24f7b58` |
| `../../src/pring_cycle/rehearsals.py` | 34880 | `a92eebf4ab938b18ec5a8c3ce9b1cae12046d0c2e93b3a3b65c7ac1877914e06` |
| `p1-capacity-utilization-full-value-audit.md` | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| `p1-cpi-full-value-audit.md` | 19071 | `1f57b4ee4670e928364225944f685823ef30817a7968a42194892489d1c8c751` |
| `p1-industrial-finance-full-value-audit.md` | 24950 | `f14f4f98f8050386a7f9f9f0f3e4d84c75b56c6dffa743d8b47c6e2ed1d3ab7d` |
| `p1-industrial-va-full-value-audit.md` | 16362 | `ef2e599944f049fab8a7bcce34aede93ac29dd2c33c5cd0a2541faf4d0984406` |
| `p1-loan-structure-full-value-audit.md` | 66620 | `2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae` |
| `p1-money-full-value-audit.md` | 16643 | `44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda` |
| `p1-omo-full-value-audit.md` | 81481 | `d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e` |
| `p1-pmi-full-value-audit.md` | 21325 | `02901b12706b0101be06a4c5b74873cd46322fbefb9b6507dbbe7c8bfe3de7ef` |
| `p1-ppi-full-value-audit.md` | 21333 | `b8228fb7eee93ca00363419b909bc3c23b0346117e22a3699cdaf374a88be8d1` |
| `p1-social-financing-full-value-audit.md` | 147300 | `a649d2b86df819fa2682c46997a0cec0fd4021c8d702225ddc6ff3a920cb7437` |
| `p1-tool-liquidity-full-value-audit.md` | 25421 | `13a84f6fcd6ee23827c9d4700d3b4af999a5a2ec40455729bdbf432c44b08fbb` |

本报告最终33项输入指纹复核时刻：`2026-09-07T18:28:57.076472+00:00`。本轮仅标准库只读检验、应用调用0、网络0、数据库读写0；没有再次执行根代理逐格核验程序。报告自身SHA/字节和链接统计在交付消息给出，避免自指摘要。
