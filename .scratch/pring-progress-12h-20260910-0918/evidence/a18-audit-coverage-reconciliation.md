Status: research-resolved
Type: read-only-audit-reconciliation
Date: 2026-09-10
Execution: no-application-no-tests-no-WSL-no-network-no-database

# A18 审计覆盖、原件与获取收据对账

**现有 A18 的1858个准备标量已全部进入独立审计并有后续根复核材料；183/1858是历史中间快照。旧v1的严格分类是1856个字面相符、1个M2数值尾差、1个Q1产能同区间源格复用。v2已修正M2，分类为1857个字面相符、1个映射待实施绑定。不能称为1858个独立官方原格全通过。**

本次实际复核 UTC：2026-09-10T00:07:11.819286+00:00。只读取既有本地Markdown、JSON和导出的HTML/CAS，使用Windows C:/Python313/python.exe -B 标准库。唯一新文件为本文；没有执行应用、测试、安装、WSL命令、HTTP、数据库查询或来源/模型操作。冻结129源码与合并回归130不属于本报告的验证对象。

## 1. 三种证据层次

1. **既有作者逐格审计**：11份报告均给出覆盖身份、原文字面、单位/期间及相符/差异结论；这是此前独立工作，不是本次的新覆盖。下面逐家族关联根复核，不能仅凭报告标题认定通过。
2. **既有根复核**：各家族都有对应verification JSON；7家族文件还直接内嵌本次所读审计报告的SHA/bytes。工具流动性、产能、贷款及OMO的根记录没有内嵌报告SHA，需结合各报告内容、[后续根汇总](verification-official-parsing/final.json)及[v2 lineage.audit_files](evidence-13-preparation-v2/preparation.json)对11报告的完整哈希绑定。本文不给无内嵌SHA的旧记录补造字段。
3. **本次独立核对**：重新计算全部250原件SHA/bytes、11报告SHA、v1/v2 1858个完整标量身份及精确数值变化，并核对恢复选择后的268收据导出与268规范化CAS的全部1858标量字段；另从原HTML重新独立审查货币28格、产能9个身份（8个独立原格+1个共享源格映射）。其余1821标量的原文字面审计由前两层承接，本次未声称重新逐个提取其全部原文。

本次找不到“仅有子代理报告、始终没有根复核”的家族；但这不等于全部家族已经来源认证。本次没有执行旧verification脚本重现当时运行；“既有根复核”指读取并核对留存证据的结论。

## 2. 逐家族分母、相符/差异与根复核

原件按家族去重；跨家族有同页共享，11行相加为268个原件×家族关系，跨家族去重才是250份。字面/数差/映射均以标量身份计；相符数不包含映射。新覆盖为相对旧18锚点的集合增量，不是新增通过数。

| 家族 / 既有报告 | 原件 / 调用 / 标量 | 原件字节 | v1 字面 / 数差 / 映射 | v2 字面 / 数差 / 映射 | 旧锚点重叠 / 新覆盖 | 既有根复核依据 |
|---|---:|---:|---:|---:|---:|---|
| [nbs_capacity_utilization](p1-capacity-utilization-full-value-audit.md) | 3 / 3 / 9 | 459,969 | 8 / 0 / 1 | 8 / 0 / 1 | 1 / 8 | [verification-omo-flow/tool-capacity-verification.json](verification-omo-flow/tool-capacity-verification.json)；capacity |
| [nbs_core_cpi](p1-cpi-full-value-audit.md) | 8 / 8 / 46 | 1,850,811 | 46 / 0 / 0 | 46 / 0 / 0 | 2 / 44 | [verification-derived-freshness/cpi-verification.json](verification-derived-freshness/cpi-verification.json) |
| [nbs_industrial_finance](p1-industrial-finance-full-value-audit.md) | 7 / 7 / 70 | 3,401,593 | 70 / 0 / 0 | 70 / 0 / 0 | 3 / 67 | [verification-omo-flow/industrial-finance-verification.json](verification-omo-flow/industrial-finance-verification.json) |
| [nbs_industrial_value_added](p1-industrial-va-full-value-audit.md) | 7 / 7 / 20 | 2,664,666 | 20 / 0 / 0 | 20 / 0 / 0 | 1 / 19 | [verification-omo-flow/industrial-va-verification.json](verification-omo-flow/industrial-va-verification.json) |
| [nbs_pmi](p1-pmi-full-value-audit.md) | 7 / 7 / 56 | 2,894,481 | 56 / 0 / 0 | 56 / 0 / 0 | 3 / 53 | [verification-loan-ytd/pmi-verification.json](verification-loan-ytd/pmi-verification.json) |
| [nbs_ppi](p1-ppi-full-value-audit.md) | 8 / 8 / 69 | 2,028,054 | 69 / 0 / 0 | 69 / 0 / 0 | 1 / 68 | [verification-loan-ytd/ppi-verification.json](verification-loan-ytd/ppi-verification.json) |
| [pbc_loan_structure](p1-loan-structure-full-value-audit.md) | 31 / 31 / 279 | 1,281,208 | 279 / 0 / 0 | 279 / 0 / 0 | 1 / 278 | [verification-official-parsing/research-verification.json](verification-official-parsing/research-verification.json)；loan_structure |
| [pbc_money](p1-money-full-value-audit.md) | 7 / 7 / 28 | 312,999 | 27 / 1 / 0 | 28 / 0 / 0 | 1 / 27 | [verification-omo-flow/money-verification.json](verification-omo-flow/money-verification.json) |
| [pbc_omo_notice](p1-omo-full-value-audit.md) | 131 / 131 / 252 | 4,013,310 | 252 / 0 / 0 | 252 / 0 / 0 | 2 / 250 | [verification-official-parsing/omo-verification.json](verification-official-parsing/omo-verification.json) |
| [pbc_social_financing](p1-social-financing-full-value-audit.md) | 51 / 51 / 837 | 1,609,364 | 837 / 0 / 0 | 837 / 0 / 0 | 2 / 835 | [verification-official-parsing/social-financing-verification.json](verification-official-parsing/social-financing-verification.json) |
| [pbc_tool_liquidity_monthly](p1-tool-liquidity-full-value-audit.md) | 8 / 8 / 192 | 357,909 | 192 / 0 / 0 | 192 / 0 / 0 | 1 / 191 | [verification-omo-flow/tool-capacity-verification.json](verification-omo-flow/tool-capacity-verification.json)；tool_liquidity |
| **并集/总计** | **250 / 268 / 1858** | **20,069,217** | **1856 / 1 / 1** | **1857 / 0 / 1** | **18 / 1840** | **11家族均有根复核；不新增认证结论** |

完整身份按 family + raw SHA + source URL + expected_period + metric_id + api_name + source_field + unit + period_kind + start/end + sorted(dimensions) 比较，v1/v2各1858个、无重复、集合完全相同。18锚点按家族、期次、指标、维度、字段、单位、Decimal数值精确匹配，均唯一落到这1858个身份；不能把相同数字的另一月份算作锚点交集。

| 家族 | 实际期次 / 字段口径 | 既有审计保留的边界 |
|---|---|---|
| 产能 | 2025-Q4、2026-Q1、2026-Q2；3季×3规范成员 | Q1只有当季率和同比点差两个原格；独立字面合计8、映射1 |
| CPI | 2025-12—2026-07；headline23、core23 | 1月两指标各2格，累计同比未公布不补0；不是48格 |
| 工业财务 | 2025-12、2026-02—07；财务42、库存14、周转14 | 7个库存金额万亿元转亿元；累计财务与月末库存/周转语义分开 |
| 工业增加值 | 2025-12、2026-02—07；当月同比6、累计同比7、季调MoM7 | 1—2月合并期没有独立2月实际同比，20而非21 |
| PMI | 2026-01—07；活动28、库存14、价格14 | 8个series×7月；扩散指数标度不是同比涨跌幅 |
| PPI | 2025-12—2026-07；3类各23格 | 1月仅MoM/YoY两列；69而非72 |
| 贷款结构 | 2024-01—2026-07，31月×9格 | 49负数；157个万亿元换算；不以分项合计纠正原报总量 |
| 货币 | 2026-01—07，M1/M2各余额、YoY | 14余额单位换算；唯一v1尾差在v2及规范制品更正 |
| OMO | 2026-02-24—08-28，131公告 | 金额131、利率121；10明确零操作公告未公布利率；252而非262 |
| 社融 | 2024-01—2026-07，51文/31月 | 存量279、同比279、YTD增量279；20×18+20×9+11×27=837 |
| 工具流动性 | 2025-12—2026-07，8月×8工具×3格 | 19负数、28真实0；RRR24个“-”不变成0；净额取原报值 |

这组边界来自对应逐格报告及根复核；本次没有以其“全部一致”替代原件指纹核验。家族范围仅为已有准备包，不是整个官方统计表所有行列或整个P1可用率分母。

## 3. 183/1858是哪个阶段

[continuation-status.md](continuation-status.md)明确保留旧执行快照。原有第155行的183来自已完成CPI/PPI/PMI：18+(46−2)+(69−1)+(56−3)=183，1675待审只描述该时刻。

[OMO修复批根终态](verification-omo-flow/final.json)随后保留493个已字面核对、1个Q1映射、1个货币差异、1363待审，其合计仍是1858，也不是当前缺口。[官方解析修复根终态](verification-official-parsing/final.json)已明确not_yet_individually_audited_preparation_scalars=0，记录1856字面相符+1旧M2差异+1Q1映射。

[v2准备说明](p1-official-preparation-v2.md)与[根交付复核](evidence-13-preparation-v2/delivery-verification.json)将唯一M2数值改正单独记为1项，得到1857字面相符+1映射。旧[v1说明](p1-official-preparation.md)的“1840未逐格审”及旧JSON状态保持原样，本次没有改它们。

## 4. 本次直接从原件重核M1/M2 28格

7份页面的货币余额段均在原始HTML物理行L359，逐份按月份、M1/M2标签、余额/同比、原单位与数字核对。数字先从原文明确录入，再用Decimal比例转换与v1、v2及导入规范制品对照；没有用快照反向生成期望。万亿元×10000=亿元，同比保留百分比标度。

| 月份 / 原件L359 | M1余额原文万亿元 → 亿元 | M1同比% | M2余额原文万亿元 → 亿元 | M2同比% |
|---|---:|---:|---:|---:|
| [2026-01](evidence-a18-import-20260909/e5e5bcd61b540d1c7c4e4d68c2a6350bf090bb37c381fec2a9de359487705ad0) | 117.97 → 1179700.00 | 4.9 | 347.19 → 3471900.00 | 9 |
| [2026-02](evidence-a18-import-20260909/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc) | 115.93 → 1159300.00 | 5.9 | 349.22 → 3492200.00 | 9 |
| [2026-03](evidence-a18-import-20260909/0d50495161d327868abe90f1a3d084249145fd63318ce0f7eaaafd00da830abb) | 119.32 → 1193200.00 | 5.1 | 353.86 → 3538600.00 | 8.5 |
| [2026-04](evidence-a18-import-20260909/4434210d0447e96bcbeab8f02d6ac0436fb76a28e41a66f4f133ff46d8b1182e) | 114.58 → 1145800.00 | 5 | 353.04 → 3530400.00 | 8.6 |
| [2026-05](evidence-a18-import-20260909/8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769) | 114.89 → 1148900.00 | 5.5 | 353.67 → 3536700.00 | 8.6 |
| [2026-06](evidence-a18-import-20260909/9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168) | 118.48 → 1184800.00 | 4 | 356.71 → 3567100.00 | 8 |
| [2026-07](evidence-a18-import-20260909/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef) | 115.46 → 1154600.00 | 4 | 355.51 → 3555100.00 | 7.7 |

关键差异（preparation结果下标82、标量下标2，均0起算）：

- 已存原文：[2026-02原件L359](evidence-a18-import-20260909/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc)：“2月末，广义货币(M2)余额349.22万亿元，同比增长9%”。raw SHA：377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc。
- 身份：pbc_money / CN_M1_M2 / source_field=m2 / aggregate=m2 / measure=balance / unit=hundred_million_cny / month / 2026-02-01—2026-02-28。
- 原字面349.22万亿元，十进制期望3492200.00亿元；v1 JSON真实数值字面3492200.0000000005，差+5E-10亿元。严格不相等，不能容差放行v1。
- v2真实字面3492200.0，已保存[规范化制品](evidence-a18-import-20260909/b3d6d0d6ca1c9428b541eb6426f3211684d532b553ed2d3ced10aaadd3ebad3a)同样为3492200.0，两者与原文字面換算严格相等。1858标量比较只有这一处数值变化。
- [既有实施记录](implementation-official-parsing.md)及[根终态](verification-official-parsing/final.json)记录十进制金额先换算再输出的修复和当时回归；本文未重跑当前应用，也未把既有741测试结果写成本次测试。

本次货币结果：v1为27严格相符+1尾差；v2及规范化制品28严格相符；单位/维度/月份28对应。没有新证据支持将旧M2尾差再登记为当前未修数值缺陷；旧报告“仍待处理”仅对历史阶段有效。

## 5. 本次产能8个独立原格+1个映射

独立读取首张表“工业”总行及表头：2025-Q4为74.9/−1.3/74.4/−0.6（当季率/当季同比点差/全年率/全年同比点差）；2026-Q1为73.6/−0.5；2026-Q2为73.0/−1.0/73.3/−0.7。准备实际取前三规范成员，不取全年/累计同比点差。

| 期次 / 原件 | measure / source_field | period_kind；实际区间 | 原文字面与v1/v2/规范值 | 本次类别 |
|---|---|---|---:|---|
| [2025-Q4](evidence-a18-import-20260909/5e067d6d9dbeca559c2ec3ad37abc0a6be6159beb62ccbfe1184fc4b6a7b4da6) | quarter_rate / industrial_capacity_utilization_pct | quarter；2025-10-01—2025-12-31 | 74.9 | 独立字面相符 |
| [2025-Q4](evidence-a18-import-20260909/5e067d6d9dbeca559c2ec3ad37abc0a6be6159beb62ccbfe1184fc4b6a7b4da6) | yoy_change / industrial_capacity_utilization_yoy_change_pp | quarter；2025-10-01—2025-12-31 | -1.3 | 独立字面相符 |
| [2025-Q4](evidence-a18-import-20260909/5e067d6d9dbeca559c2ec3ad37abc0a6be6159beb62ccbfe1184fc4b6a7b4da6) | ytd_rate / industrial_capacity_utilization_ytd_pct | year_to_quarter；2025-01-01—2025-12-31 | 74.4 | 独立字面相符 |
| [2026-Q1](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | quarter_rate / industrial_capacity_utilization_pct | quarter；2026-01-01—2026-03-31 | 73.6 | 独立字面相符 |
| [2026-Q1](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | yoy_change / industrial_capacity_utilization_yoy_change_pp | quarter；2026-01-01—2026-03-31 | -0.5 | 独立字面相符 |
| [2026-Q1](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | ytd_rate / industrial_capacity_utilization_ytd_pct | year_to_quarter；2026-01-01—2026-03-31 | 73.6 | 同区间源格复用；无独立累计格 |
| [2026-Q2](evidence-a18-import-20260909/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8) | quarter_rate / industrial_capacity_utilization_pct | quarter；2026-04-01—2026-06-30 | 73.0 | 独立字面相符 |
| [2026-Q2](evidence-a18-import-20260909/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8) | yoy_change / industrial_capacity_utilization_yoy_change_pp | quarter；2026-04-01—2026-06-30 | -1.0 | 独立字面相符 |
| [2026-Q2](evidence-a18-import-20260909/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8) | ytd_rate / industrial_capacity_utilization_ytd_pct | year_to_quarter；2026-01-01—2026-06-30 | 73.3 | 独立字面相符 |

Q1原件SHA：0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a，128195字节。L336–344仅“一季度”及利用率/同比点差表头；L348为单元格起点、L349为73.6字面，L351为−0.5。quarter_rate与ytd_rate都覆盖2026-01-01—03-31；相等不证明页面有两个原格。

[2026-09-09映射判定](capacity-q1-source-mapping-decision.md)已支持把同区间季度源格作为显式别名；它是日历区间与目标字段定义的推论，没有找到另一条国家统计局“Q1累计等于当季”的专门原句。[2026-09-10工程边界](capacity-q1-implementation-boundary.md)仍标Implementation: not-executed，要求绑定已审原件、映射审查材料、新定义及实际收据，并贯穿入库与消费者。

**下一代码工作是落实这一个精确绑定与拒绝边界，不是继续等待另一个Q1累计原格，也不是再次要求用户作产品选择。** 依据现有工程研究，不能仅删除registered_capacity_q1_mapping_unresolved或写入accepted字符串；还需验证raw/normalized、源与目标成员、同区间、单位/总体/值与定义哈希。本文未读取当前源码或执行其测试；工程细节来自已绑定研究材料，不冒充本轮源码复验。

## 6. 获取收据实际结构与恢复合并

[原receipts.json](evidence-a18-import-20260909/receipts.json)是对象，其receipts数组有268项；每项有顶层status/preparation_result_index，及嵌套receipt的state/raw_hash/normalized_hash。顶层失败不等于底层没有有效收据。

| 层次 | 真实记录 | 解释 |
|---|---|---|
| 原268调用 | 顶层captured266/failed2；嵌套validated267/failed1 | captured_scalars1847只统计266完整结果；加OMO已有有效规范结果为1849，不能混用 |
| 索引22，2024-08贷款 | acquisition_time_invalid；raw已存，normalized_hash=null | 原失败不覆盖；[loan-attempt](evidence-a18-import-recovery-20260909-01/loan-attempt.json)追加1次capture、9标量 |
| 索引223，2026-07-01 OMO | 顶层AssertionError，底层validated且两值已存 | [omo-recheck](evidence-a18-import-recovery-20260909-01/omo-recheck.json)复用旧收据；无新增获取，旧failed保留 |
| 合并 | 268逻辑结果；269实际尝试；268选中有效收据；250raw；268normalized；1858字段匹配 | [combined-verification](evidence-a18-import-recovery-20260909-01/combined-verification.json)所记准备完成与本次CAS/JSON核对一致 |

本次按preparation_result_index选择：22取新loan receipt，其余267取原数组的嵌套receipt（包括223）。验证family、period、source_url、raw SHA、validated状态、started≤received≤validated，以及268个唯一acquisition_id；逐个重哈希normalized CAS。核对1858标量完整规范字段集合：metric_id/api_name/source_field/period_kind/start/end/dimensions/value/unit/release_at/public_available_at/definition_version/acquisition_ids，以及release层provider/period/URL/event/time。仅将日期字符串的空格/T用ISO datetime等值比较，数值没有容差。

这是**本地导出收据与制品一致性复核**。本次禁止数据库查询，未声称实时查库验证receipt行或当前来源/模型表。既有combined记录两个隔离库source_claim/model_version均0，本文只承接其记录时刻，不外推当前数据库实时计数。

新document_import的真实2026-09-09取得/校验时刻已存在，旧v1的acquisition_time=null不能继续解读为“从未补获取收据”。但随后取得已存字节不恢复原发布时的历史SYSTEM，也不证明首次PUBLIC或修订链。旧失败后检查的某个UTC样本未记录，见[失败边界](a18-import-failure-boundary.md)及omo-recheck的old_post_check_utc_sample=not_recorded；不得倒填。

## 7. 当前明确缺陷与缺件

- **待代码落实：Q1映射可执行绑定。** 语义研究已支持实施，工程研究仍未执行；保持8原格+1映射。需证明源格、原件vintage、收据、定义与消费者对应关系，不能直接把字段解析成功升级为certified。
- **旧M2尾差已修复承接。** 本次原文/v2/normalized严格核对确认修正；v1和旧审计保持原样。未发现新的货币数值差异。
- **正式来源认证及模型采用仍缺完整包和执行证据。** v2与恢复记录明确未认证/未采用。全值相符不能代替许可/用途/定义、真实版本/时点、来源认证和模型正式消费验证。
- **历史时点与修订需正式承接。** 页面时间、纯解析研究时钟、新document_import时间各有不同含义；尚未由本次材料证明首次公开字节、历史取得完成或跨发布修订链。社融/贷款YTD差分、OMO到期量与政策有效区间等下游契约也不是1858字面核查的通过结论。
- **完整候选与120交易日等最终验收没有新增。** 本次不修改认证、PUBLIC、SYSTEM、模型或120日计数，不把268调用/1858字段相符转换成模型可用补齐率。

## 8. 可复算输入指纹与本次结果

以下指纹均从本次读取实际字节计算。原件/规范化CAS文件名是完整SHA，附录列出268个逻辑结果raw→normalized本地链接；链接目标实际重哈希相符，不仅检查存在。旧准备包/v2/receipts/recovery的嵌套摘要交叉相符，11审计与v2绑定一致。

| 本次核验 | 结果 |
|---|---:|
| 原件唯一字节身份 | 250/250；20,069,217字节 |
| 审计报告与v2精确指纹 | 11/11 |
| 根verification内嵌报告指纹 | 7家族直接匹配；另4家族由v2完整绑定承接 |
| v1/v2完整标量身份 | 1858/1858；重复0；唯一数值变化1 |
| 旧锚点唯一交集 | 18/18 |
| 恢复选中有效收据 | 268/268；新增获取仅1 |
| 规范化CAS摘要 | 268/268 |
| v2与规范制品完整标量字段 | 1858/1858；Decimal数差0 |
| 本次原文重审 | 货币28；产能9身份=8原格+1映射 |
| 认证/模型/历史PUBLIC/SYSTEM状态写入 | 0 |

1857严格字面是继承原审计加本次修正核验后的结论，不是本次从头重新审了1857段原文。Q1共享源格仍单列。

| 文档/JSON输入 | 字节 | 本次SHA256 |
|---|---:|---|
| [a18-import-failure-boundary.md](a18-import-failure-boundary.md) | 17502 | 98e7938a7698d62f2dee1ae63fdb4d859922455718f3add305b7dbeb52dce2aa |
| [capacity-q1-implementation-boundary.md](capacity-q1-implementation-boundary.md) | 26036 | 056a04208ce0cf898f369a65c4a905849f9465b286cf8b76b3a019924de966ed |
| [capacity-q1-source-mapping-decision.md](capacity-q1-source-mapping-decision.md) | 12902 | c25614f3c356c9cb807de7a40b401bc0af0f5365927d652278b53556c7801266 |
| [continuation-status.md](continuation-status.md) | 56138 | 6cc4d3b9dd68efd96c50f5c1aca5a0d11e09cfa0f63ef076da0e5635133e2397 |
| [evidence-13-preparation-v2/delivery-verification.json](evidence-13-preparation-v2/delivery-verification.json) | 765 | 5edd0be69fe8ba830b21b014ed8a1db912b6ca3c24d65eb104c9d9adad471bc3 |
| [evidence-13-preparation-v2/preparation.json](evidence-13-preparation-v2/preparation.json) | 3189072 | 92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034 |
| [evidence-13-preparation-v2/review.md](evidence-13-preparation-v2/review.md) | 1073 | 0a0ac970ba069140e808f730008c802a176c18a7dcab13236d000a674046b08f |
| [evidence-13-preparation/anchor-expectations.json](evidence-13-preparation/anchor-expectations.json) | 4152 | e4ba9fe88c93701d7fa6ba7f2cca1e37387b95ba2f91771b320fa7be7035eafe |
| [evidence-13-preparation/preparation.json](evidence-13-preparation/preparation.json) | 2767926 | a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a |
| [evidence-a18-import-20260909/delivery-verification.json](evidence-a18-import-20260909/delivery-verification.json) | 1934 | 3d56fbc2e2094249355a63b70ab03dec1d8032d47505fde2cfb945577965fb48 |
| [evidence-a18-import-20260909/receipts.json](evidence-a18-import-20260909/receipts.json) | 433467 | 199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c |
| [evidence-a18-import-recovery-20260909-01/combined-verification.json](evidence-a18-import-recovery-20260909-01/combined-verification.json) | 1085 | cb0768f5e8406e689958cba854122f5e8430775e950e47ad9c184bdfd3a12276 |
| [evidence-a18-import-recovery-20260909-01/loan-attempt.json](evidence-a18-import-recovery-20260909-01/loan-attempt.json) | 1730 | aa5a108819707c68426b240b0051eebae726c6e61790febf4b3fae9b0dd7ee64 |
| [evidence-a18-import-recovery-20260909-01/omo-recheck.json](evidence-a18-import-recovery-20260909-01/omo-recheck.json) | 473 | bc65dcba5725897484630ab0de904c29cc0d33653ee88a581f5125937344fc42 |
| [evidence-a18-import-recovery-20260909-01/recovery.json](evidence-a18-import-recovery-20260909-01/recovery.json) | 3958 | c37aed82e86198f3362cf6c79b63878f1aecd92c649170329f510930c617c4d8 |
| [implementation-official-parsing.md](implementation-official-parsing.md) | 4979 | e07530f9ddcfdd1deb7cb08adbfea24000374c3265963d15375e98022f3c622b |
| [p1-capacity-utilization-full-value-audit.md](p1-capacity-utilization-full-value-audit.md) | 13203 | 5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed |
| [p1-cpi-full-value-audit.md](p1-cpi-full-value-audit.md) | 19071 | 1f57b4ee4670e928364225944f685823ef30817a7968a42194892489d1c8c751 |
| [p1-industrial-finance-full-value-audit.md](p1-industrial-finance-full-value-audit.md) | 24950 | f14f4f98f8050386a7f9f9f0f3e4d84c75b56c6dffa743d8b47c6e2ed1d3ab7d |
| [p1-industrial-va-full-value-audit.md](p1-industrial-va-full-value-audit.md) | 16362 | ef2e599944f049fab8a7bcce34aede93ac29dd2c33c5cd0a2541faf4d0984406 |
| [p1-loan-structure-full-value-audit.md](p1-loan-structure-full-value-audit.md) | 66620 | 2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae |
| [p1-money-full-value-audit.md](p1-money-full-value-audit.md) | 16643 | 44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda |
| [p1-official-preparation-v2.md](p1-official-preparation-v2.md) | 2841 | 6623bd19acee525d3a2a18eec7749e908bf28e17b52e6f6012c92f4a7291b688 |
| [p1-official-preparation.md](p1-official-preparation.md) | 11901 | 1a1c6984c96df6da41c76a008c4f37419ef9b23621f6391e84e78e68c3444b5f |
| [p1-omo-full-value-audit.md](p1-omo-full-value-audit.md) | 81481 | d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e |
| [p1-pmi-full-value-audit.md](p1-pmi-full-value-audit.md) | 21325 | 02901b12706b0101be06a4c5b74873cd46322fbefb9b6507dbbe7c8bfe3de7ef |
| [p1-ppi-full-value-audit.md](p1-ppi-full-value-audit.md) | 21333 | b8228fb7eee93ca00363419b909bc3c23b0346117e22a3699cdaf374a88be8d1 |
| [p1-social-financing-full-value-audit.md](p1-social-financing-full-value-audit.md) | 147300 | a649d2b86df819fa2682c46997a0cec0fd4021c8d702225ddc6ff3a920cb7437 |
| [p1-tool-liquidity-full-value-audit.md](p1-tool-liquidity-full-value-audit.md) | 25421 | 13a84f6fcd6ee23827c9d4700d3b4af999a5a2ec40455729bdbf432c44b08fbb |
| [verification-derived-freshness/cpi-verification.json](verification-derived-freshness/cpi-verification.json) | 384 | 09eacdbbb1c557a36457a6f2bcf7d70209a7dbfa4448b8e7c17b5663bba7c770 |
| [verification-loan-ytd/pmi-verification.json](verification-loan-ytd/pmi-verification.json) | 384 | 1c8c9fe715615a2f0284f34a3029482a67f98db03a98215defc26f265db3ebf6 |
| [verification-loan-ytd/ppi-verification.json](verification-loan-ytd/ppi-verification.json) | 384 | 880369da94733c92a8a18095bec312853da64c90c7f3fc5b9176d6ede5975ab5 |
| [verification-official-parsing/final.json](verification-official-parsing/final.json) | 1179 | a702c1e6c4e050702536ca995d5d3511dea2ddb5a18e20acd073c9539f676d4b |
| [verification-official-parsing/omo-verification.json](verification-official-parsing/omo-verification.json) | 194 | 111e6bc7d4eec4ddb5d15c43fbd6b63e14ba69796ffa82de48efeb863222797e |
| [verification-official-parsing/research-verification.json](verification-official-parsing/research-verification.json) | 511 | ef53422e447540668be2f727046c47b97ffe5f58da4ddaaea66c26138c8b7864 |
| [verification-official-parsing/social-financing-verification.json](verification-official-parsing/social-financing-verification.json) | 557 | 7455dc5d85203bb5dfbeae2af24464ecd26b74e0b80823623df873c631c69bea |
| [verification-omo-flow/final.json](verification-omo-flow/final.json) | 1412 | 3aa65d166d875549cd6f76cb7793c8f0d719809cfe4ac681c707e4df4bb2916d |
| [verification-omo-flow/industrial-finance-verification.json](verification-omo-flow/industrial-finance-verification.json) | 461 | c5dae70da1a0abd63e24b4396530be5340948e0cdf69b4608ec6b5f582d38c74 |
| [verification-omo-flow/industrial-va-verification.json](verification-omo-flow/industrial-va-verification.json) | 424 | 0efa23ddb4a3bad64ac9bf63fc90621ed65754aa3db8905189acf505b142d1e2 |
| [verification-omo-flow/money-verification.json](verification-omo-flow/money-verification.json) | 577 | c0314b6f5e205d543b730fc1fb071aa13144c983d66bafe3ecd0e77eb60c92d0 |
| [verification-omo-flow/tool-capacity-verification.json](verification-omo-flow/tool-capacity-verification.json) | 494 | 62256746f46ba10efec8aed6dbf1238cc4a201add5a2c2e31c2359f6e549610d |

共绑定559个不同路径：41份说明/JSON及518份CAS（250raw+268normalized）。CAS清单摘要：ec7bac4ce7322073f631dcaf57871704e449376ce700c5395a9d6d2a8980e9ba。计算契约：按相对路径字典序，将每个实际CAS输入拼为UTF-8 relative_path<TAB>byte_count<TAB>sha256<LF>，再作SHA256；这不是新原件或收据。

## 附录：268个逻辑结果的原件→规范制品

下标为preparation.data.results的0起算下标。跨行原件重复仅表示同页服务多个家族，唯一raw仍250。第22行规范化使用新恢复目录，第223行使用原validated收据。显示摘要前12位，**链接目标保留完整SHA256文件名**；完整标量保留在这些既有JSON，不复制原件。

| 下标 | 家族 | 期次 | 标量 | 原件CAS | 规范化CAS |
|---:|---|---|---:|---|---|
| 0 | 社融 | 2024-01 | 18 | [42312d6054e2](evidence-a18-import-20260909/42312d6054e2df029dfeeba68c7c60fc4bc45934cb72bdd739c143e1c9f02243) | [2fc9cbcc18ff](evidence-a18-import-20260909/2fc9cbcc18ff2fdffbc09875c99397f977b5d866e1dff2562281298722078afd) |
| 1 | 贷款结构 | 2024-01 | 9 | [1fc855817f7e](evidence-a18-import-20260909/1fc855817f7e1676ab49ab3b3b43cfb42e125ec5542387a87bfdd21b6fe9feb4) | [29f5b71d5e5b](evidence-a18-import-20260909/29f5b71d5e5b9bf08820cb95735ac04f65a8e9897b59c45fb55ceb79c9d04350) |
| 2 | 社融 | 2024-01 | 9 | [d0ae83ced9ad](evidence-a18-import-20260909/d0ae83ced9ad510a057a853f51b185e729ed81c9cd5e958fa988c7b10a676d9d) | [5ebbd2aa0285](evidence-a18-import-20260909/5ebbd2aa0285008ef0a69dd17d28b54a86429fb1cf3107aaa5ab85a9a407822e) |
| 3 | 社融 | 2024-02 | 18 | [0ef100264163](evidence-a18-import-20260909/0ef1002641631790dbbcba5303f793a3cebffb014a28ac3afbc6f6c88dcacc76) | [6b8e8fb1352d](evidence-a18-import-20260909/6b8e8fb1352d8530f66da28d0bcb4edbd3d6798dfa5b3d2b20eeeb164ccf1f79) |
| 4 | 贷款结构 | 2024-02 | 9 | [8c7fa06c5888](evidence-a18-import-20260909/8c7fa06c588887b088a8b82c254e112744f8c3f7058061bc08f5fa156bc3f2e6) | [076878231324](evidence-a18-import-20260909/07687823132474eadd349a4d5f73cd0da4bfebd7682ddcd96f2a7786e0d2b069) |
| 5 | 社融 | 2024-02 | 9 | [4bb290d74da0](evidence-a18-import-20260909/4bb290d74da04a697ae8c58ff2341cdbf4648b744f6c23ac1aa93ef473ce4960) | [01d8f708cc2d](evidence-a18-import-20260909/01d8f708cc2dbc65ce12c2b6f0bea803b985bd8d9ed4f246f287f50b95301d50) |
| 6 | 贷款结构 | 2024-03 | 9 | [de360412abe8](evidence-a18-import-20260909/de360412abe85b7c6ec3b39f0236b713afbb5c91f1d3210e5fb9fe4a8d7814a2) | [6183bb89e38a](evidence-a18-import-20260909/6183bb89e38ae2ab0726569bb38382280f4c4ccb068e9ad590b70a1b4cf4aea6) |
| 7 | 社融 | 2024-03 | 18 | [aeaba667ec8c](evidence-a18-import-20260909/aeaba667ec8c8203d85155fdae3cc1bdee27cbe38f656c71c168ff73af1fa607) | [7969d365c054](evidence-a18-import-20260909/7969d365c054d8460495c656bdf28ca58f586373857f47d42bb411e6c8ba21b4) |
| 8 | 社融 | 2024-03 | 9 | [4042321499dd](evidence-a18-import-20260909/4042321499dd33a9132e2edb2a20579ad2efc9b0ebefcdefe2546fcc9df99d16) | [72ffb220328b](evidence-a18-import-20260909/72ffb220328ba758d0fae15c3766670b10ac1988e73434a8dd4683d61b9ff41b) |
| 9 | 社融 | 2024-04 | 9 | [de7f474188f3](evidence-a18-import-20260909/de7f474188f3052dc35753760f3da2c3261dd65aefa632edb1f998de0a88b16a) | [2be8603331ce](evidence-a18-import-20260909/2be8603331ce31110f5b4724e7edb43357babac2645771c17a0ad2ec7f0a88dc) |
| 10 | 贷款结构 | 2024-04 | 9 | [6bfbeab346d3](evidence-a18-import-20260909/6bfbeab346d36b1823018407f581e675c6b9845afe4dc03a98a273771d93aa43) | [50a2760781ba](evidence-a18-import-20260909/50a2760781ba6e258371e22a15bdb1dc0dfc1d793b857de45b28aabd992f4955) |
| 11 | 社融 | 2024-04 | 18 | [88f2166f81a9](evidence-a18-import-20260909/88f2166f81a9cd04ec6c420234c4c4b0f05cd64bf42d8c082f73adf1d3e3135b) | [a188386189cd](evidence-a18-import-20260909/a188386189cd342f122394ad39f6c5b76b80dd47335c5b31c8170f2fe515a890) |
| 12 | 社融 | 2024-05 | 18 | [71c21dd44be5](evidence-a18-import-20260909/71c21dd44be5b1091ad5646ca58a7483192b612e527e2fc691ca3f8a55345001) | [6fc6293cada2](evidence-a18-import-20260909/6fc6293cada2f09839338ca65fdd5e970cf5d56ef731e18081e5195e301e64a9) |
| 13 | 社融 | 2024-05 | 9 | [775729831c4a](evidence-a18-import-20260909/775729831c4a7e6954558685948bf8232840b8a3abb9222d5a1b608bec048542) | [20e80f0f1e1c](evidence-a18-import-20260909/20e80f0f1e1cf949a3894ee65a2a3db5498fb6c8d0cf0394c74d0de97faa526b) |
| 14 | 贷款结构 | 2024-05 | 9 | [c0a4cda42f7d](evidence-a18-import-20260909/c0a4cda42f7d42b3e0cc0ee9ea0560c9eb02760d313a4e1529c987bb6719e63c) | [d9fbd939d472](evidence-a18-import-20260909/d9fbd939d472277767bd9b023def8310e2fa7385e356f3ae8aa69aede0131567) |
| 15 | 社融 | 2024-06 | 18 | [315bf6badee0](evidence-a18-import-20260909/315bf6badee00f54831dd435cb69d46ad897d83b6c37b8b21c1d5bb3bf93e637) | [dc583374093d](evidence-a18-import-20260909/dc583374093ddc2225ab5423967cdd3a96d1e958cd903bbea65dde089e16584b) |
| 16 | 贷款结构 | 2024-06 | 9 | [1eb7aa1eab31](evidence-a18-import-20260909/1eb7aa1eab315a47fd50b554aaddf00aba969ddca0c4ece042b5bc26ecff2858) | [9798c60e6c0d](evidence-a18-import-20260909/9798c60e6c0d9e0e199ce149cfcb460cda33a045ed5db15b6d8fa29fce5f107b) |
| 17 | 社融 | 2024-06 | 9 | [3bed842ba053](evidence-a18-import-20260909/3bed842ba05386319a069a6212110a5d9d7070f65d9ee30693d7e091a3d9ae29) | [a36da8e17d7e](evidence-a18-import-20260909/a36da8e17d7e399fb3c88043a5e1c187520e4adad112dd00637a506fd68d9779) |
| 18 | 社融 | 2024-07 | 18 | [c71bb0b19724](evidence-a18-import-20260909/c71bb0b19724dbd8e0d13277602cc4c6eb96c363ea1210712378bc5e9eedb3c2) | [b82a94b5c321](evidence-a18-import-20260909/b82a94b5c3219b5795c6f93b1cc2c3357174ee7b39da92ea5acd46d84fce1a50) |
| 19 | 贷款结构 | 2024-07 | 9 | [8658c76f6a27](evidence-a18-import-20260909/8658c76f6a2746ed12f3c570f5250bbabef62ba180ff042f336d3241f94be03b) | [26471b685a67](evidence-a18-import-20260909/26471b685a67d57009e252d734333d83540f336b820e166841418a64b3baa6c9) |
| 20 | 社融 | 2024-07 | 9 | [52d2fe8fc267](evidence-a18-import-20260909/52d2fe8fc26763cb262dabcce6c0256a3524dfccfd6bfa69d80a910c6c3f517b) | [8de2c8bb72f3](evidence-a18-import-20260909/8de2c8bb72f354e8943b7c465f8fd3bca5dcee11c3884e6b7274b5f37f2fca75) |
| 21 | 社融 | 2024-08 | 9 | [7a24c20e6613](evidence-a18-import-20260909/7a24c20e66130c21640827fa9706a58b36eb8988a70b7b2309a1f10285d3d1c2) | [e3e0479208c3](evidence-a18-import-20260909/e3e0479208c32868d941f6bdd9e266cf3a8c41f10b73821aa6d7999881410162) |
| 22 | 贷款结构 | 2024-08 | 9 | [6a73b3145312](evidence-a18-import-20260909/6a73b31453129d53f6aedaa6fc11c78e856904665fa7f275367a9530d0ce30f8) | [a64d0b6d5ddf](evidence-a18-import-recovery-20260909-01/a64d0b6d5ddf6dc80ceeee9654287def4eea5d0002b44ca88561910a362116ff) |
| 23 | 社融 | 2024-08 | 18 | [80331aa5b897](evidence-a18-import-20260909/80331aa5b897259bfb9ed1947321456450a9f787d36eed6c3edff60b5f217ac1) | [f2e23092ce65](evidence-a18-import-20260909/f2e23092ce65f9e06bd817de7d2d4cd3528ca740a3ea26881f536581edd96a5c) |
| 24 | 贷款结构 | 2024-09 | 9 | [56defe8d4373](evidence-a18-import-20260909/56defe8d4373b64d43bb57b54ebce1ef7adc308cb07bd8d9953c3e0b1a7a1bc5) | [681420c51ccd](evidence-a18-import-20260909/681420c51ccda89dbede8683f901caa0c8c812b4308c3c546bd9286c532b0a8a) |
| 25 | 社融 | 2024-09 | 9 | [a0b08ead70f5](evidence-a18-import-20260909/a0b08ead70f5096c3e33b9ff8c566202402a6c5edf65e00b3be2e2b685637a6e) | [ef2acae55c96](evidence-a18-import-20260909/ef2acae55c961d251007f3a9c40f0b8b73a05a891b3fb1ab471ab202182fe067) |
| 26 | 社融 | 2024-09 | 18 | [2574d552d99b](evidence-a18-import-20260909/2574d552d99bf51c0b935c26e7dea68ee6a6717b12d061bd22eb5d31ed74a4b0) | [d85ff66fab76](evidence-a18-import-20260909/d85ff66fab76d5dcdab2bb2f471dcacdc1ad47b274c099ae056694561c80afaa) |
| 27 | 社融 | 2024-10 | 18 | [9f06e5af37c8](evidence-a18-import-20260909/9f06e5af37c8fb1edddc8d0e55b95d5419076a1d2b9316e6b95aaebd9af8beb5) | [873b639e454a](evidence-a18-import-20260909/873b639e454a1be249716c18d5b0abadb49ce10cafd3dbec4b3763bff1361f7a) |
| 28 | 贷款结构 | 2024-10 | 9 | [5beb398f6e37](evidence-a18-import-20260909/5beb398f6e37c20312003b6fb85f914d90c3a390d769e90e8161914d245c465a) | [00c2397b534c](evidence-a18-import-20260909/00c2397b534cc41831e0d5292328a74ada3ee124961d4c57a0f1175ab7a22d6f) |
| 29 | 社融 | 2024-10 | 9 | [6ad6b1f062b5](evidence-a18-import-20260909/6ad6b1f062b5265472fba83df260cf294a5981679814e0861fc406206dffca70) | [ccb09fbe083c](evidence-a18-import-20260909/ccb09fbe083c21deeb415d2b5743b7fae27c5492e572e2b306c71bb2637c9280) |
| 30 | 社融 | 2024-11 | 18 | [540d4dba6217](evidence-a18-import-20260909/540d4dba621723337bf650517d2e28a331542673271145fa9917075a03689b5b) | [537c1f7e6213](evidence-a18-import-20260909/537c1f7e62136b3808172d3fa9419113549bf7a56c361b4ef90c289049d52692) |
| 31 | 贷款结构 | 2024-11 | 9 | [5ef05d405e9a](evidence-a18-import-20260909/5ef05d405e9a4e6af58c98389360912d0087e57d5cf1d1afa0fbfe013070a6ab) | [8ad18b9378a0](evidence-a18-import-20260909/8ad18b9378a05c4b1a9733e786b7fa1ec58aaafc5fb8a474dd6e6bb6361a998a) |
| 32 | 社融 | 2024-11 | 9 | [7e1844487f0a](evidence-a18-import-20260909/7e1844487f0a3983ec2b1419ed365ed2c345f4ad3c3b7b7886228ad24741b1b2) | [3c48be1b9a4c](evidence-a18-import-20260909/3c48be1b9a4cf653fdb8fc1db0942260dd2a5f6067b3fd6db1c2b9219a936988) |
| 33 | 社融 | 2024-12 | 9 | [8081e0f66935](evidence-a18-import-20260909/8081e0f66935a2ce9efcfea3504265858c456bbd5acc903e364c267ce9e964b5) | [e6b0234ee07c](evidence-a18-import-20260909/e6b0234ee07caee4ad28478e5f56559b5460bcb783bb324ee7c280da528e239f) |
| 34 | 贷款结构 | 2024-12 | 9 | [2e77920bd183](evidence-a18-import-20260909/2e77920bd183a9099e0939cb011ac3d9a09924be1fdc06add914a18e258db264) | [47e9c41df7b2](evidence-a18-import-20260909/47e9c41df7b2493e692d361321bbefe52fc598503f1e7dfd3c9d38fa82d0ad7b) |
| 35 | 社融 | 2024-12 | 18 | [b49e75993eab](evidence-a18-import-20260909/b49e75993eab79c6bd8919e12275346b48b54e1baba208c646bda6e55d67ffbf) | [0c21feadc8bf](evidence-a18-import-20260909/0c21feadc8bfdbf4fe6e7f511123d51bb336079ade38be532030b939d61710d8) |
| 36 | 社融 | 2025-01 | 18 | [cc6625821fce](evidence-a18-import-20260909/cc6625821fcecffb2042901fdac0db1b7f97391a6b845e1fb101134bda1a4257) | [6f01942fceef](evidence-a18-import-20260909/6f01942fceef2513fcce44a8b363ecd11aa4235552f3846c3e7129ea277f7728) |
| 37 | 贷款结构 | 2025-01 | 9 | [9f5a0ba19beb](evidence-a18-import-20260909/9f5a0ba19bebd26782dc9b71455b516113e7a28009553ba94aabe29d5b7ff660) | [02cb4cbf199e](evidence-a18-import-20260909/02cb4cbf199e80fcabf2c9049b8fd298c1c8090560b4ebb85aa9e741a9da47c5) |
| 38 | 社融 | 2025-01 | 9 | [6329aac34d9a](evidence-a18-import-20260909/6329aac34d9a1c717acac7e68bb32e0a2344b3e479aa37276a8cf427c65f23ca) | [1f30ef73d724](evidence-a18-import-20260909/1f30ef73d7241ac11c87655e5cddfe978b4dbfdddea7740193e012474bfae5ab) |
| 39 | 社融 | 2025-02 | 9 | [c44f44897b31](evidence-a18-import-20260909/c44f44897b31e643dd88ca7f3751d47bdb83ad0e32e0b28943adc84a163479fd) | [53b37fb20333](evidence-a18-import-20260909/53b37fb203339ddbdbb2665e5ba8e1ddcef04ac28eba696953bdd313b096131e) |
| 40 | 贷款结构 | 2025-02 | 9 | [099bef226266](evidence-a18-import-20260909/099bef22626630ef7b93129bc02d02119f5cf23423d1e5c8352b07d6e3c16e80) | [490945c228be](evidence-a18-import-20260909/490945c228be89c9442fc03df9bbdbb3d96de5f958df4d035a886cfbeb1e272d) |
| 41 | 社融 | 2025-02 | 18 | [2fdb7247c4c2](evidence-a18-import-20260909/2fdb7247c4c27f0ccc497f36e498e42f84748efbe8abb134dcd82a64891287a8) | [6e7581848278](evidence-a18-import-20260909/6e7581848278d1fdf8a466315a5cd0269f2953a1213c95ab6ca3c828762dd884) |
| 42 | 社融 | 2025-03 | 18 | [710b7be402e9](evidence-a18-import-20260909/710b7be402e9f55fa2782a7ac24d3ca788272955f3d4c37ce63c4d9207978230) | [f5f85d5d9fd4](evidence-a18-import-20260909/f5f85d5d9fd442a68c6910c7bc8b1107c10450fd42b4b3b22a8a3ef3bd3284b0) |
| 43 | 社融 | 2025-03 | 9 | [040b29b2bb7f](evidence-a18-import-20260909/040b29b2bb7f97ebf35446c0251849f6317ab9489f675c37b8786a394b632a3b) | [a8595f9efda4](evidence-a18-import-20260909/a8595f9efda49ade9c3b8d254f461678976a5b1c4e684877e224f9d7eafb3fbf) |
| 44 | 贷款结构 | 2025-03 | 9 | [6d3500a14c16](evidence-a18-import-20260909/6d3500a14c1602edcaace8469e0018485714a6c7931bbcbc53ff82c176b69f17) | [5b38904f4620](evidence-a18-import-20260909/5b38904f46204c6acbe7f92d5db4b639306ca7ec23632926687a521e8b783575) |
| 45 | 贷款结构 | 2025-04 | 9 | [54e2d8a768f0](evidence-a18-import-20260909/54e2d8a768f0e9f16abf1e82ef8a5d3acbc3373434fa389a10a432913ab5fd98) | [cbd09837ab43](evidence-a18-import-20260909/cbd09837ab432f7fcda785e97e66d56a6cf43a079b79ebd54012dbe1ccb931a6) |
| 46 | 社融 | 2025-04 | 9 | [f4272816156a](evidence-a18-import-20260909/f4272816156a6e0282a504b2a242fe2c310f6e61739b50306154945a8755a1ae) | [068afed5512b](evidence-a18-import-20260909/068afed5512b8920d7782a719c006d07bc7a95408f7eade0191176b4e0b9b5aa) |
| 47 | 社融 | 2025-04 | 18 | [48110997855d](evidence-a18-import-20260909/48110997855d0f0ff35f2993e9109183eca44e75444bb2d6565d60a507fb86cb) | [1e171ca2d343](evidence-a18-import-20260909/1e171ca2d34390ee3f3f420ee681137a4d852f7a86a8eff68a4c5612b03d4327) |
| 48 | 社融 | 2025-05 | 18 | [1b535e5d00fb](evidence-a18-import-20260909/1b535e5d00fba0d58ab5db7627601c533960a2918d05f0aa0fe65fe5e8e10445) | [01da583783d6](evidence-a18-import-20260909/01da583783d63e66d62408a6be0e374cd2b1b530623f745cfe80672d39a0f81e) |
| 49 | 社融 | 2025-05 | 9 | [3d3053aa2cb4](evidence-a18-import-20260909/3d3053aa2cb4a4b3ad929d39e3d4dcce6947b7f5bfbecc70bf8e840447b24711) | [82faf1f9c18b](evidence-a18-import-20260909/82faf1f9c18b96237dabbfc5a9c3b7241954ce15e8cfc102859685a43456e005) |
| 50 | 贷款结构 | 2025-05 | 9 | [5f4a4e3ac36c](evidence-a18-import-20260909/5f4a4e3ac36cae871ab683de3e067abd98d3640fbeadb24bcce60c74c39d5eed) | [ea729eea6a1c](evidence-a18-import-20260909/ea729eea6a1ccd73490924b010f90bc59ae151f020f4f249fb92eab4e3058e46) |
| 51 | 社融 | 2025-06 | 9 | [813ecda471da](evidence-a18-import-20260909/813ecda471daf222f8d6075543368c0e6414a332a6ef3841b20c9b38518c8181) | [e1442974b577](evidence-a18-import-20260909/e1442974b5772058023f5e5a1e79f9fb67683113e3ab4f2e66916d866b2dd737) |
| 52 | 贷款结构 | 2025-06 | 9 | [cf31e072f283](evidence-a18-import-20260909/cf31e072f283a84717a8e63bdb22ef47a229e82d378e829d7bc13bc55481f96f) | [e8fd57b55fad](evidence-a18-import-20260909/e8fd57b55fad81cbb881d1d0faf245066749b6fc415477797624ecb457f30589) |
| 53 | 社融 | 2025-06 | 18 | [236644a4ab58](evidence-a18-import-20260909/236644a4ab58701bb4cfbf587ef9e28d31db4309b2d7d8e6eb97827cadf454b2) | [fbbd8f2a68ae](evidence-a18-import-20260909/fbbd8f2a68ae79d9ee1368e1fd8329f75beea7211ad513cf7ffed9012dd40b0b) |
| 54 | 贷款结构 | 2025-07 | 9 | [910cd3161aa2](evidence-a18-import-20260909/910cd3161aa2c0af086e00f820366878366269db4bee55a9064cb5fd8099f95b) | [a924c9729b2e](evidence-a18-import-20260909/a924c9729b2e10c0342d16b86e6fbf6dafc1f0142d8b0cfd63b4714a8d9cb602) |
| 55 | 社融 | 2025-07 | 18 | [b137eea74d9a](evidence-a18-import-20260909/b137eea74d9a9ebd2607953359693a83fc1f36b9bcb649cad56f49012e3fece6) | [bca87780c831](evidence-a18-import-20260909/bca87780c831e8fdd800f714245cb34e53271ecea180f8fdd44c25c837777f46) |
| 56 | 社融 | 2025-07 | 9 | [16f76863da7b](evidence-a18-import-20260909/16f76863da7b4ce6fb4c4680fa16b43dce8700260a0b6b872b10890c12f08a83) | [374642238c5f](evidence-a18-import-20260909/374642238c5fa16e8fb552ffcd09df46914853564f8e609ec143cabc4a09cc69) |
| 57 | 社融 | 2025-08 | 18 | [2a15ffe708dc](evidence-a18-import-20260909/2a15ffe708dcb4a2afbbe17ee0086029baf18c6d4a59e8e84a91ec9cec8e88ec) | [2313f91293ae](evidence-a18-import-20260909/2313f91293ae7ed1217f94ea4c7460098b6ab8372ef87f0b11de723b24be4618) |
| 58 | 社融 | 2025-08 | 9 | [3952fda9138d](evidence-a18-import-20260909/3952fda9138d5347905f8c826c73da65823d825b3ae72480624d806dc9d3af42) | [901f50415f7f](evidence-a18-import-20260909/901f50415f7f17523336f97bea5a69d31b1b709da36d25ad3b974ccfdce4786f) |
| 59 | 贷款结构 | 2025-08 | 9 | [a3e044cb1cb5](evidence-a18-import-20260909/a3e044cb1cb5c2d4e548339b355449e7b0871eb8f3e87c150024a30fc3363482) | [00740fa51200](evidence-a18-import-20260909/00740fa5120040f670012eb037d6b9d60e5f521b9b144a6f9700556696371bca) |
| 60 | 贷款结构 | 2025-09 | 9 | [b3c5ecfe4fb6](evidence-a18-import-20260909/b3c5ecfe4fb6599279e3401b3ce0ef25dc5745a8f77cff7e84c9a14e1a4cd157) | [82c6c390f466](evidence-a18-import-20260909/82c6c390f4665ad7a7e50671fba006a7651ea0c655b7df8960ab447abd84f452) |
| 61 | 社融 | 2025-09 | 27 | [b3c5ecfe4fb6](evidence-a18-import-20260909/b3c5ecfe4fb6599279e3401b3ce0ef25dc5745a8f77cff7e84c9a14e1a4cd157) | [3042ed57df2b](evidence-a18-import-20260909/3042ed57df2b9d980d4bf9ef0c1d5304bc1c628fa171ad6f3a9b7f5375f87b02) |
| 62 | 贷款结构 | 2025-10 | 9 | [72d75cc14f8c](evidence-a18-import-20260909/72d75cc14f8c6e7649d2deaec386b6b8252aeb8232a0e3586cdcffc365b3778a) | [ca2c33f1e0fa](evidence-a18-import-20260909/ca2c33f1e0faa34f8a8faaf564ac4a9f7e3159e93818fe7f44dea6e59664d350) |
| 63 | 社融 | 2025-10 | 27 | [72d75cc14f8c](evidence-a18-import-20260909/72d75cc14f8c6e7649d2deaec386b6b8252aeb8232a0e3586cdcffc365b3778a) | [cae5454d4b84](evidence-a18-import-20260909/cae5454d4b844330f547ee57463516cdf0452715a138d11fa5caba6f442b34a2) |
| 64 | 贷款结构 | 2025-11 | 9 | [86dac86009ce](evidence-a18-import-20260909/86dac86009ce1615c6cec1293dbf036603fbd6fdf0f52417e1fb9fcb0902089f) | [b5acdc81e2a6](evidence-a18-import-20260909/b5acdc81e2a61db849ea045d446793abab01107afddd4eb3e3e381a326796f69) |
| 65 | 社融 | 2025-11 | 27 | [86dac86009ce](evidence-a18-import-20260909/86dac86009ce1615c6cec1293dbf036603fbd6fdf0f52417e1fb9fcb0902089f) | [7b118cb9721a](evidence-a18-import-20260909/7b118cb9721ac3f729c6a1e72895732ba5f4f7c621dd4359097e0db0edda0d80) |
| 66 | 贷款结构 | 2025-12 | 9 | [47761677bcf6](evidence-a18-import-20260909/47761677bcf626cfe3ab7ab444940e9c0bdcb4326621edfe7e4e54192ee0bb33) | [77f029153f4a](evidence-a18-import-20260909/77f029153f4ad6e67e90ee2bd7864ec7d612eee745d6961b1ad68798d0f0a662) |
| 67 | 社融 | 2025-12 | 27 | [47761677bcf6](evidence-a18-import-20260909/47761677bcf626cfe3ab7ab444940e9c0bdcb4326621edfe7e4e54192ee0bb33) | [1e544d9c3213](evidence-a18-import-20260909/1e544d9c3213a72bdb166f6633d0d57114ec758dbc14360f549dde45e46bc374) |
| 68 | 工具流动性 | 2025-12 | 24 | [2977f1a0fd7b](evidence-a18-import-20260909/2977f1a0fd7bf182ae2531bc619322f977319dca75cf3d6a8b8c3a1fcbe5b547) | [20d087d41073](evidence-a18-import-20260909/20d087d4107399e64c6a13044fce0fab0147296e6b980996bbdf368028225c71) |
| 69 | PPI | 2025-12 | 9 | [7b8b4c7ec427](evidence-a18-import-20260909/7b8b4c7ec427e17ecb28e0218a745f04a26ab033a6a28a9b2f6672abbad548d4) | [c62cbe392e25](evidence-a18-import-20260909/c62cbe392e2504d0204804d42ff8fee230bd31c0fa4254cee9334a70489295a8) |
| 70 | CPI | 2025-12 | 6 | [029d16d76ba6](evidence-a18-import-20260909/029d16d76ba6c207b46be0cf4a13ca2c88ae431540aec335778644e97830da7f) | [93bdfec1eb07](evidence-a18-import-20260909/93bdfec1eb076175e2341cccc9dd3ed871ea538505fffd1525834885feb340a7) |
| 71 | 工业增加值 | 2025-12 | 3 | [26b1c5458d48](evidence-a18-import-20260909/26b1c5458d483c9be7ef53b7dacd1a97a3c26c0d73448312cb9ad6b24eb8d41f) | [3414a369cf0b](evidence-a18-import-20260909/3414a369cf0b6e972b467cb7aa1abe7d65974b75db59f6651d4be08ba0ce1b53) |
| 72 | 工业财务 | 2025-12 | 10 | [07f5d7434c11](evidence-a18-import-20260909/07f5d7434c11154d88052119b65120f2c7c816205c7fdd003f5edde6e47d5d47) | [25dbbc9b6afd](evidence-a18-import-20260909/25dbbc9b6afdabfd857bb409cca619037017a6ffa673cbc62b4b4020c1ca07c4) |
| 73 | 产能 | 2025-Q4 | 3 | [5e067d6d9dbe](evidence-a18-import-20260909/5e067d6d9dbeca559c2ec3ad37abc0a6be6159beb62ccbfe1184fc4b6a7b4da6) | [2248c715576a](evidence-a18-import-20260909/2248c715576aac6c78c0119c6f87bb8e7c40f0e4b0e7a80b7d99c3a912e9fb3b) |
| 74 | 贷款结构 | 2026-01 | 9 | [e5e5bcd61b54](evidence-a18-import-20260909/e5e5bcd61b540d1c7c4e4d68c2a6350bf090bb37c381fec2a9de359487705ad0) | [ffa2470a6a49](evidence-a18-import-20260909/ffa2470a6a49825b7ffac5599c6f2e8b116da61d105e0df62f331079f4994613) |
| 75 | 货币 | 2026-01 | 4 | [e5e5bcd61b54](evidence-a18-import-20260909/e5e5bcd61b540d1c7c4e4d68c2a6350bf090bb37c381fec2a9de359487705ad0) | [5208d32f124f](evidence-a18-import-20260909/5208d32f124fdfd388ca15e91bb680de5f00306b174d79f8eddd77c4badfd787) |
| 76 | 社融 | 2026-01 | 27 | [e5e5bcd61b54](evidence-a18-import-20260909/e5e5bcd61b540d1c7c4e4d68c2a6350bf090bb37c381fec2a9de359487705ad0) | [ee803caa5a56](evidence-a18-import-20260909/ee803caa5a56bd4f030226a3d7af6068c3acd9c250bddc5f19992f4099c011d1) |
| 77 | 工具流动性 | 2026-01 | 24 | [76d3acb5860e](evidence-a18-import-20260909/76d3acb5860e59ad73afef6113fad6c894d350616fbeb8a00909b5e18b8066d9) | [c6373371be65](evidence-a18-import-20260909/c6373371be65bdd443ca348db5af42307068997578213bfe796bcbb4a64d689f) |
| 78 | PMI | 2026-01 | 8 | [6ef53006136e](evidence-a18-import-20260909/6ef53006136e5a396533fe406f620e1799e7b0bc4246b380fb18e6294edab423) | [e839e9a11114](evidence-a18-import-20260909/e839e9a1111462f66b93e9212c86f84687a63ad20f658733f6ead9903cafee22) |
| 79 | PPI | 2026-01 | 6 | [e7e65eb8ae06](evidence-a18-import-20260909/e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943) | [4c24f81a8fda](evidence-a18-import-20260909/4c24f81a8fdaf375b10ec60312f511bac0e8a9619a57ff33f5ee5d2c3dcf4efc) |
| 80 | CPI | 2026-01 | 4 | [f65b52d3c241](evidence-a18-import-20260909/f65b52d3c2418f40a43e0991d041e0295e56941ca7d9bc9bad76e0d5d0cab964) | [ed3981aa236a](evidence-a18-import-20260909/ed3981aa236a90f1d7ec84427f6779cef73f784242c1c7d28bc9e65a2a703090) |
| 81 | 贷款结构 | 2026-02 | 9 | [377f455aa922](evidence-a18-import-20260909/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc) | [127295386498](evidence-a18-import-20260909/12729538649832dc61ca44858813e98a45f585b5d8763617bf2e6da7d33388f5) |
| 82 | 货币 | 2026-02 | 4 | [377f455aa922](evidence-a18-import-20260909/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc) | [b3d6d0d6ca1c](evidence-a18-import-20260909/b3d6d0d6ca1c9428b541eb6426f3211684d532b553ed2d3ced10aaadd3ebad3a) |
| 83 | 社融 | 2026-02 | 27 | [377f455aa922](evidence-a18-import-20260909/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc) | [b5098c3f76a7](evidence-a18-import-20260909/b5098c3f76a74dda5e9e2c8d11db78a3c4bd51cac13b17494908eb85aa871d0c) |
| 84 | 工具流动性 | 2026-02 | 24 | [579e6e4fcca2](evidence-a18-import-20260909/579e6e4fcca2bf2b596fed965e652b9f1b6c2551f3da80ac6c720faac7370570) | [9c337e0f938a](evidence-a18-import-20260909/9c337e0f938ac2c9e18e21cf3bc41e72a8bb703324db19f4283eb1472f2b59c7) |
| 85 | PMI | 2026-02 | 8 | [2d5629a61b4e](evidence-a18-import-20260909/2d5629a61b4ed28718746b3b2559505ba4162612891f5352604a7c1f2a9075ba) | [bc8d020ad28a](evidence-a18-import-20260909/bc8d020ad28a134041d9af5f198a1b7a6c1127eb5e3b845c6e0dff80670195f0) |
| 86 | PPI | 2026-02 | 9 | [32fd2ce9c325](evidence-a18-import-20260909/32fd2ce9c32548f12331070c9d15ce2c7d726aa390215f58b2076d46a725e6ca) | [514e5440bfa9](evidence-a18-import-20260909/514e5440bfa95fe5b83cb57a12375214c242406524d67a1f287fb293ef4a1a1c) |
| 87 | CPI | 2026-02 | 6 | [321b7693d1e1](evidence-a18-import-20260909/321b7693d1e112a92c83fc16293cc115429b0dee88e4201f115668850cf97043) | [81950481837d](evidence-a18-import-20260909/81950481837d1a593997f83b937e46b179277dbe151639e0f5e972d266e89679) |
| 88 | 工业增加值 | 2026-02 | 2 | [2115d7cc67a2](evidence-a18-import-20260909/2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e) | [1b95b04b3d27](evidence-a18-import-20260909/1b95b04b3d27ad73ac2af57206b1fbed2c4bacda069dfb0de9b435442aedbd44) |
| 89 | 工业财务 | 2026-02 | 10 | [9ba7e4b6ff66](evidence-a18-import-20260909/9ba7e4b6ff669fcb86324dd840b870ffbd4f97f8dad585fb1d50df7f062eac33) | [60655f8fd68e](evidence-a18-import-20260909/60655f8fd68ec37478c3ae515252cc475bcd0bb28691035bb46445f28fdb6475) |
| 90 | OMO | 2026-02-24 | 2 | [25d1e48ed588](evidence-a18-import-20260909/25d1e48ed588dcb523b64d45dfea76d36521c676fd2ce408441b449c2b258f83) | [4663c86dc4ef](evidence-a18-import-20260909/4663c86dc4efbfd21530583110af041400496b3e950b9b1594651f6f3f66d367) |
| 91 | OMO | 2026-02-25 | 2 | [4dcb60f89fe7](evidence-a18-import-20260909/4dcb60f89fe7f88aaabada9b80962ad3b0dc14585e6ca77e9abcfb08afa041b1) | [6faf4ae207ea](evidence-a18-import-20260909/6faf4ae207ead5956e43683bcb1977ecb3b405220bdaed2498dc6941f2b2b70d) |
| 92 | OMO | 2026-02-26 | 2 | [153dab13ba7c](evidence-a18-import-20260909/153dab13ba7cd727c6d4779abb63680fc925413ee0ca80025e90198fede23124) | [e1142c3d7e40](evidence-a18-import-20260909/e1142c3d7e40eb22e3eba1e0c32805ff0a6eb35d7a9315018390c7464a4ca301) |
| 93 | OMO | 2026-02-27 | 2 | [a5ee35759d2f](evidence-a18-import-20260909/a5ee35759d2f6b4bccaee8977e50ac343018de7abd6eb0ab1062d8d187c2a13b) | [1fceb4e82deb](evidence-a18-import-20260909/1fceb4e82debdd1e56bbaaa58eb79b5073bfb2595afd812b76b463ecdb4f6951) |
| 94 | OMO | 2026-02-28 | 2 | [128db89ba2ef](evidence-a18-import-20260909/128db89ba2ef08d516887765f2b980c6f6737034ff81b8d244a68afd815bd1f1) | [c14199e05958](evidence-a18-import-20260909/c14199e05958e6489c8235cc71d73242ec6ef0edc63faed0764e66c78a9a41e3) |
| 95 | 贷款结构 | 2026-03 | 9 | [0d50495161d3](evidence-a18-import-20260909/0d50495161d327868abe90f1a3d084249145fd63318ce0f7eaaafd00da830abb) | [ac2f3f32fd11](evidence-a18-import-20260909/ac2f3f32fd111e649a33f2988778752dfe8ba586cf071636f0c2c2e6dd58024e) |
| 96 | 货币 | 2026-03 | 4 | [0d50495161d3](evidence-a18-import-20260909/0d50495161d327868abe90f1a3d084249145fd63318ce0f7eaaafd00da830abb) | [6edbb08b86c4](evidence-a18-import-20260909/6edbb08b86c4b96329e0aed5caefdaae9f0bbb384520ba880ab2b25c76ddf44e) |
| 97 | 社融 | 2026-03 | 27 | [0d50495161d3](evidence-a18-import-20260909/0d50495161d327868abe90f1a3d084249145fd63318ce0f7eaaafd00da830abb) | [49be0ece45da](evidence-a18-import-20260909/49be0ece45daba5945c698bc7bb9e216bf173c7ab90de0894b745797eff3cf07) |
| 98 | 工具流动性 | 2026-03 | 24 | [7957370a5eeb](evidence-a18-import-20260909/7957370a5eeba6655647dfddde1955a44b3f21ef51f5c15fad29a31927a27b43) | [ecab12ad6875](evidence-a18-import-20260909/ecab12ad6875a7e3899a6c01c22d791271b40a2bbf107c8fa42a6a9f86f55d84) |
| 99 | PMI | 2026-03 | 8 | [31fc72c16f31](evidence-a18-import-20260909/31fc72c16f315e6da565e3cc2fac132d8b3a883878e84e302bbe68b2aad1acfa) | [3484a302dc51](evidence-a18-import-20260909/3484a302dc510aa3f386d7d90f434e876aca6b0fe92516a6bebcb4f7aac926f4) |
| 100 | PPI | 2026-03 | 9 | [bba5cd965fcf](evidence-a18-import-20260909/bba5cd965fcfcc208f0d0de5878a9856c09ce64e2233829328b142d7c9723583) | [51fb8e6d97a6](evidence-a18-import-20260909/51fb8e6d97a6050ade4f1f13ae77ada239b0b974a35446a156cf31ebddb7fbde) |
| 101 | CPI | 2026-03 | 6 | [acaf1bd86124](evidence-a18-import-20260909/acaf1bd86124b1aca4c7ed1cee26560d0fe24c665d614ca4ca2b10c2601a811a) | [d7d12722c18a](evidence-a18-import-20260909/d7d12722c18a5d4cac1bb376f341a0570803bbe3b8963738cdc33bd8e751831b) |
| 102 | 工业增加值 | 2026-03 | 3 | [481bb421c08f](evidence-a18-import-20260909/481bb421c08fde4958091570e3e4fc1a6dffab863779b984469cef239bcb3176) | [1d9c3060cb2b](evidence-a18-import-20260909/1d9c3060cb2be3fc84a125c2afe5327799c53221be6c7de0690288286ea0ad4d) |
| 103 | 工业财务 | 2026-03 | 10 | [bc74852adcca](evidence-a18-import-20260909/bc74852adcca3e9b8974ee21393a4917e0c3feb01a8d7d8f6d8e8bab91a9928b) | [ad6412f2a7f0](evidence-a18-import-20260909/ad6412f2a7f02698086415263e77fa4cead9b2e1704ade23c05099d15c5d3567) |
| 104 | OMO | 2026-03-02 | 2 | [f94561cb8d50](evidence-a18-import-20260909/f94561cb8d50922adc95dc6017bb5b42d3a671d3dc3756d5ba795d2fe1e03c2d) | [f6947d8e973c](evidence-a18-import-20260909/f6947d8e973c572df14d4dd3b6f4709e4d90462a4ceec5887daa1f5c39f4e207) |
| 105 | OMO | 2026-03-03 | 2 | [e83a13cbac4e](evidence-a18-import-20260909/e83a13cbac4e89fda5f60dfe0bfc85af966a672d0381fae1235026f038626b8d) | [0775d636da67](evidence-a18-import-20260909/0775d636da673fdec8c6399be1092ea4bb68fd250ad9119a65539d8a88f69a33) |
| 106 | OMO | 2026-03-04 | 2 | [8721a09a6b29](evidence-a18-import-20260909/8721a09a6b2949c705a8dd1ff46dba1552c83535ad54a0c4634f245d53b1f7b4) | [5c68aaded0a6](evidence-a18-import-20260909/5c68aaded0a6346755055aab700b0bddbbe10627be933024d8bf55dbd85b521f) |
| 107 | OMO | 2026-03-05 | 2 | [9e00103d01a4](evidence-a18-import-20260909/9e00103d01a468fece4c275c521a86374ecbd8179bdd056f250787e2e6be0c73) | [297bb3de33bd](evidence-a18-import-20260909/297bb3de33bde5b27553c4ec4b086c830a1a06e7e31439381b2ee0c01f987092) |
| 108 | OMO | 2026-03-06 | 2 | [344326d3975d](evidence-a18-import-20260909/344326d3975d3fb7d21014cedf1b6809d7c78f5a7e63e550883cf881975c7364) | [b4c5e68ed4f4](evidence-a18-import-20260909/b4c5e68ed4f499b9837c0a99b078cba63c72b13d13ebee81690253aaaca2439c) |
| 109 | OMO | 2026-03-09 | 2 | [5263ed19e932](evidence-a18-import-20260909/5263ed19e9325fb04509ba2f7bd3535b8258fa6836264e347971ded9c4981742) | [cb588b7bc2b0](evidence-a18-import-20260909/cb588b7bc2b02154e15b9efbb93b9db8ff24fa4bfc3564aa03d656c42baaca4e) |
| 110 | OMO | 2026-03-10 | 2 | [e9eaf5b0f0a9](evidence-a18-import-20260909/e9eaf5b0f0a975bc65eec1e42b7fdba7754816eb70ecc2378cd1e97c75c30436) | [97f847c4e520](evidence-a18-import-20260909/97f847c4e520666cdadeab7eb9f6f18419e2e745b6eb8374509f991747489a7e) |
| 111 | OMO | 2026-03-11 | 2 | [82fc3197e6a7](evidence-a18-import-20260909/82fc3197e6a7943a6d2297b870411d0b18cfc568992a0d4de343ff7784fc641f) | [2766e9cbb688](evidence-a18-import-20260909/2766e9cbb688231d03ba39bf7717bc63e1a607788d69e35726fdfb3cab796cc7) |
| 112 | OMO | 2026-03-12 | 2 | [1ab7333145ff](evidence-a18-import-20260909/1ab7333145fffe3f9fca7c1cd2a01b1b0b01a4645846b60656cbd54d35ae3ae5) | [2d9daf0cb0c5](evidence-a18-import-20260909/2d9daf0cb0c542b8468ba5400495e0503e0fb53ff19286cb9b0f3b88cfa008be) |
| 113 | OMO | 2026-03-13 | 2 | [711da5525535](evidence-a18-import-20260909/711da5525535cceed443aaf4a0d9b352f7bae748d153a76ecf3bbb1a90511977) | [2beb60d3e8df](evidence-a18-import-20260909/2beb60d3e8df0e3ad6fc7ebeb8079a47ee439cb5940c72874a6782ea6536afc3) |
| 114 | OMO | 2026-03-16 | 2 | [960612ebb6ff](evidence-a18-import-20260909/960612ebb6ff15759d81714fd8f184554ef1126686b881c41f0a3c385dc2a38e) | [2053dcdc7fe5](evidence-a18-import-20260909/2053dcdc7fe5381e765db57adcdb3d397e1790330b9dceecab53569daed3d333) |
| 115 | OMO | 2026-03-17 | 2 | [da3822a1eabf](evidence-a18-import-20260909/da3822a1eabf9d2311de7249290a597b768e11392d57fada64d07cde0afe6aa7) | [78805f24a9d5](evidence-a18-import-20260909/78805f24a9d56cec676d826a624cb7a1aae8651e1b1223561c7e6d5bce1b6ab1) |
| 116 | OMO | 2026-03-18 | 2 | [97d53d24e57e](evidence-a18-import-20260909/97d53d24e57ee4673da41843198eeb24fe91b1730aeb6ccce90741386b825850) | [0df477ac1add](evidence-a18-import-20260909/0df477ac1add02743472c4b167e496824e3d7d643432dc0eb851ca63a253e9bf) |
| 117 | OMO | 2026-03-19 | 2 | [79536efdd16c](evidence-a18-import-20260909/79536efdd16c3d27a921173491a158abc5b7ffae4c4aa22f6b19003758a7b3c8) | [b4ef4f6fffb8](evidence-a18-import-20260909/b4ef4f6fffb8b0095e831670b83717999c3176fbfd02ab2d0ac71aa475b6771a) |
| 118 | OMO | 2026-03-20 | 2 | [b58c150e05ff](evidence-a18-import-20260909/b58c150e05ff12134979075d5ecc7bd06d4dbf6064f76405d2789451d78d922d) | [8f25b8c279ca](evidence-a18-import-20260909/8f25b8c279caf739e44c1f4e6a064dfdf802f51058408a4ea138dd43dc9a2f73) |
| 119 | OMO | 2026-03-23 | 2 | [ff7d3e7c95f9](evidence-a18-import-20260909/ff7d3e7c95f96db607dc88d2b1cedca0d7866ce674d4fe72f3afb07a6b1e9bde) | [c76e825a3706](evidence-a18-import-20260909/c76e825a37060301ad4f1b8ade41f06af8a52e6681f0f7359ea37c9254e023bf) |
| 120 | OMO | 2026-03-24 | 2 | [bcb9c37224bd](evidence-a18-import-20260909/bcb9c37224bd49b1ca2e9fdf921643e6c2bff6945ef9c72537e6e3c0025a3317) | [179cf77aa45f](evidence-a18-import-20260909/179cf77aa45f30aef3fc58e53031876cb057db6d60363690981c3ac37d6ff5bd) |
| 121 | OMO | 2026-03-25 | 2 | [a269749b41d3](evidence-a18-import-20260909/a269749b41d3a28d298abc1dc2c5ebcb6b7145b9f1aec906ade13551fb2ab5a6) | [70d5315279cf](evidence-a18-import-20260909/70d5315279cf231cd035def084c7f9134fef1ec1350e5095b9dc43af1c1b9f37) |
| 122 | OMO | 2026-03-26 | 2 | [266127101c21](evidence-a18-import-20260909/266127101c21867a807fef16bb24d8d63224200c55e9195a14120a15ee8694dc) | [662d98d3777f](evidence-a18-import-20260909/662d98d3777f1e6b290f1d03ff00b4b4e5e1518ffc499a499785db98d2b90303) |
| 123 | OMO | 2026-03-27 | 2 | [eca8e7e9901e](evidence-a18-import-20260909/eca8e7e9901e78be6437b1fb8e925432f530c898ec56f4d86af430bf937be8ff) | [b13ea85bc2da](evidence-a18-import-20260909/b13ea85bc2da1067ed63ed150ae6af3d0840103d618dcb5419ce199361e833f2) |
| 124 | OMO | 2026-03-30 | 2 | [50e5a389f81b](evidence-a18-import-20260909/50e5a389f81b4627fb8ccbb6df1cea6e0e4c7a49b6e5bc0f3db6397379fac74e) | [cb437ba75853](evidence-a18-import-20260909/cb437ba7585356fd493e3fdc54b1569267c81a675f6ede88de1c2da2e1783386) |
| 125 | OMO | 2026-03-31 | 2 | [d11695ca8f78](evidence-a18-import-20260909/d11695ca8f78cc3224084b9210ccfca588dd47e9f16711cdf96639b43f411a36) | [7a12c0d27b0c](evidence-a18-import-20260909/7a12c0d27b0c8d856a0692f8f53d5b14d85744e1d848e52b0b7887a30efd7f1c) |
| 126 | 贷款结构 | 2026-04 | 9 | [4434210d0447](evidence-a18-import-20260909/4434210d0447e96bcbeab8f02d6ac0436fb76a28e41a66f4f133ff46d8b1182e) | [456702ec0214](evidence-a18-import-20260909/456702ec021492dc3546a2980916f6e76c3a280091271670ac5c30403652246d) |
| 127 | 货币 | 2026-04 | 4 | [4434210d0447](evidence-a18-import-20260909/4434210d0447e96bcbeab8f02d6ac0436fb76a28e41a66f4f133ff46d8b1182e) | [1db0431da601](evidence-a18-import-20260909/1db0431da601b9e510861ef1161b3332d677e8962c6084b00c56693f6a5d2d6e) |
| 128 | 社融 | 2026-04 | 27 | [4434210d0447](evidence-a18-import-20260909/4434210d0447e96bcbeab8f02d6ac0436fb76a28e41a66f4f133ff46d8b1182e) | [31faf4d61b20](evidence-a18-import-20260909/31faf4d61b2061b6cb431dc2b97755df2bb58224be9eb93cf2b5a5d1c07e61e2) |
| 129 | 工具流动性 | 2026-04 | 24 | [500fc11ff59f](evidence-a18-import-20260909/500fc11ff59f46b9c9c62c27999acf18a2dbc4ced814b3b496cbb3754a337986) | [85bf01183423](evidence-a18-import-20260909/85bf01183423c9401db4c55e4102b59d78f7c10b95321ec5da224a762cb5a68e) |
| 130 | PMI | 2026-04 | 8 | [83ee41d92e01](evidence-a18-import-20260909/83ee41d92e01359a9397413cc26b6db9088d1d61e05db19a7eae147b946b4aa0) | [56be8dcca208](evidence-a18-import-20260909/56be8dcca208015251d8d76da7d3809c6c81a74457283cff63d840e81a0ef3a5) |
| 131 | PPI | 2026-04 | 9 | [7ad4e2f7d744](evidence-a18-import-20260909/7ad4e2f7d74453b265b54c21488980fd3cd7eabe9c1ab40ec95ea9523c8fb2e1) | [b314a3edba4e](evidence-a18-import-20260909/b314a3edba4e0f932ad7a054d5904ff922694a325068ac4e3b069087505eae65) |
| 132 | CPI | 2026-04 | 6 | [5b35264f5e63](evidence-a18-import-20260909/5b35264f5e63c0776701fb2586ffd8511f28fdc4360547a791de51e2cc7750c4) | [d815c31b5139](evidence-a18-import-20260909/d815c31b513926e794550740dc46c49948b76faa54c2c301ac8c973335132d1d) |
| 133 | 工业增加值 | 2026-04 | 3 | [2e43dd7ae771](evidence-a18-import-20260909/2e43dd7ae7710d1183f4b78091319d638b0cdfa2d3ad39ecb6760227b317126f) | [27e102171272](evidence-a18-import-20260909/27e102171272615af082c66be08a5856b90f0ac52e18d0bbd0b14c257abfddf5) |
| 134 | 工业财务 | 2026-04 | 10 | [4625e1bc4e83](evidence-a18-import-20260909/4625e1bc4e83e8f6b28134d9555d49839f33efbcb2761c5be81cb5736fa224ac) | [4e64d5592479](evidence-a18-import-20260909/4e64d55924798a9ff88accedff5cac3b0da925dbe0d89717f6f0898b6585d4ee) |
| 135 | OMO | 2026-04-01 | 2 | [bf3f65116f85](evidence-a18-import-20260909/bf3f65116f85cc2013f95cd6bf358b8d347e8ca088f849b761f278190d2e80a3) | [64bd3227cca1](evidence-a18-import-20260909/64bd3227cca18fb337f6bc26c22556c5109ce784e990e00b74d1bfd6732ad22a) |
| 136 | OMO | 2026-04-02 | 2 | [1fb46d2242c3](evidence-a18-import-20260909/1fb46d2242c31e6a5e15eb5c8ae13899259779eb30e74b8b581334b213ea28af) | [cd50948f3373](evidence-a18-import-20260909/cd50948f33735764c5ca3a4935f268eb3f0eb66ae37b952788d0175fbb72ed43) |
| 137 | OMO | 2026-04-03 | 2 | [8cf860820b3f](evidence-a18-import-20260909/8cf860820b3f5223a1c629d783c651fda0ce5fa5a1111f1cc45de80f8f9fced4) | [79a4f448e13f](evidence-a18-import-20260909/79a4f448e13ff66d7af5db28f3e855ffb5c303de35d2f266bd9fb0b888ad7009) |
| 138 | OMO | 2026-04-07 | 2 | [faabbb40c616](evidence-a18-import-20260909/faabbb40c616f3144e3426ddcc247d3daf5918872635c97b18af6d8a82e0a0ca) | [118ce08fba5a](evidence-a18-import-20260909/118ce08fba5aa49ea0fb8de4107047af750e1012aa7455dc3b1a491dbf1c42e9) |
| 139 | OMO | 2026-04-08 | 2 | [4b9bcbe39ffd](evidence-a18-import-20260909/4b9bcbe39ffd5147cb0deb4ecb01ed20b5c803f618d2f0afcaa4b7c613635fdf) | [7ae08720cd53](evidence-a18-import-20260909/7ae08720cd538b8bf39858aefbc6e569c6c5e0f71592a67b65073e3575d387e5) |
| 140 | OMO | 2026-04-09 | 2 | [7fa60fabb359](evidence-a18-import-20260909/7fa60fabb3593e2108c7080ef1de81d5b442a5e279a8f87b1a2f4913cfdcc3e9) | [d7aa654ddbc6](evidence-a18-import-20260909/d7aa654ddbc60a648e200145a3616f4ab1624cd8b119a62d97b92a940e37b97e) |
| 141 | OMO | 2026-04-10 | 2 | [7037dfe4ecbc](evidence-a18-import-20260909/7037dfe4ecbcb76fb7b77c849ede7c29c43aa26adc5bd31e07810c6dfb1c9326) | [73d7638e4401](evidence-a18-import-20260909/73d7638e44019dc71cc5182db7852ec2332d5a3fac6a3ac11a3a91d73f0312c5) |
| 142 | OMO | 2026-04-13 | 2 | [4a7fdd7ff656](evidence-a18-import-20260909/4a7fdd7ff6560490c4ac24b973f078f4ef91e0a19bf871a23d0299b2d107df89) | [02c216892f7c](evidence-a18-import-20260909/02c216892f7cf3ba8226b3e5f9b2053019571adc986335a788b255d74e978ce9) |
| 143 | OMO | 2026-04-14 | 2 | [6b230b8ffb39](evidence-a18-import-20260909/6b230b8ffb39a5a21c9551b039b0433ffe97d5a9c77d17f82ef4377e6700de05) | [969d7299c148](evidence-a18-import-20260909/969d7299c148b020ecd6d52c078c6be0ecc072d10580f3d0b976a0acce1e18aa) |
| 144 | OMO | 2026-04-15 | 2 | [dbb9da06c9ab](evidence-a18-import-20260909/dbb9da06c9ab272f79fd0ec114df1a5f62a269e9d528bd1419dc56a718c77596) | [08ef1c5a1261](evidence-a18-import-20260909/08ef1c5a1261286f2e6a9c8392a0cfcec215e378d266431c34882f5b8297375f) |
| 145 | OMO | 2026-04-16 | 2 | [11f2ceee53f5](evidence-a18-import-20260909/11f2ceee53f54dd2320b206188e75427dd428c9a3b4ec328f9e9b26e15ef8820) | [9ea48cb727b0](evidence-a18-import-20260909/9ea48cb727b0c225d096dcb6ff445b5f7f12e2f6f2d5cbc55d02435ce754bc80) |
| 146 | OMO | 2026-04-17 | 2 | [698d2608bdbc](evidence-a18-import-20260909/698d2608bdbc10f0128a0534b1a96267117e05adb15c9d33ed8d846775d1efd8) | [694e5891d96e](evidence-a18-import-20260909/694e5891d96eaebfa0022c90c634564940a3db88b26774e60afde3a1f0e1765a) |
| 147 | OMO | 2026-04-20 | 2 | [516b076140d9](evidence-a18-import-20260909/516b076140d93cf028c2948fbbb13a54d9eb91c175fba5bf619231f01bcdf26c) | [c4e197cfdcb0](evidence-a18-import-20260909/c4e197cfdcb0a8215d98ed57c7cb454e769a97fc38d0907505a0a5882e01ae1b) |
| 148 | OMO | 2026-04-21 | 2 | [a93324436e41](evidence-a18-import-20260909/a93324436e4145967e477781a5d6f0238c3bad469c42d54adacf5839f44643be) | [d53b769079cc](evidence-a18-import-20260909/d53b769079cccb322922267c0fed5b7df481b1441779724656d5729171f6a2c6) |
| 149 | OMO | 2026-04-22 | 2 | [49fd37843687](evidence-a18-import-20260909/49fd37843687af96a7e854b01776dd71c1e459eb80cf9b66f778912a2b82d9d4) | [aacfc03517e2](evidence-a18-import-20260909/aacfc03517e23d202a71181a1e3772e92d184e30f45d2c47927d0f2fd480ed9a) |
| 150 | OMO | 2026-04-23 | 2 | [71147a74a5c4](evidence-a18-import-20260909/71147a74a5c44a140ca864ece548a6508ca18e11be467fc853bbbb56ac1f6ce2) | [523f8d66c10c](evidence-a18-import-20260909/523f8d66c10c97e8875aee51dd448db8fb3eb654549bf47dc3666bd830ffed51) |
| 151 | OMO | 2026-04-24 | 2 | [6f80fda7cced](evidence-a18-import-20260909/6f80fda7cceddf10fca504c0967dde158479824394337afbe884984332ed251c) | [0895d4bba599](evidence-a18-import-20260909/0895d4bba599faec44f1ce04cc987b9f76644595e383cc98d43182791bdace2f) |
| 152 | OMO | 2026-04-27 | 2 | [73d484788122](evidence-a18-import-20260909/73d484788122c4a714ad028a4050c5340af1bbf72490a436b3d84d547f4a7df8) | [3f1b51796f51](evidence-a18-import-20260909/3f1b51796f51fb8400f2871c241c38276a7f7aa65c179412ce25867eb025aa9f) |
| 153 | OMO | 2026-04-28 | 2 | [d4aa9398ea71](evidence-a18-import-20260909/d4aa9398ea71ed1e2a313c7b1f71a7cbcfb288d5cd5afe19a2e7d59f1d5d633e) | [73b92cfad894](evidence-a18-import-20260909/73b92cfad894ea514039c8cfcabf27330e137fbc745af5dc063d20db02a10f28) |
| 154 | OMO | 2026-04-29 | 2 | [412ff8aed403](evidence-a18-import-20260909/412ff8aed403386bfd7960b0a4e1ac96e41a5fe191b901bef3eed3b95f0cf6d3) | [fa54a5f111f3](evidence-a18-import-20260909/fa54a5f111f3d27d9f5ef3c5c9c4c5d993ca25a2f277635011e25ba9fabfc34d) |
| 155 | OMO | 2026-04-30 | 2 | [0a07f7a87fa9](evidence-a18-import-20260909/0a07f7a87fa950472192a9ebeccbee8c490b4780b9a53bac70e11dab2c24a081) | [d8ee584444e0](evidence-a18-import-20260909/d8ee584444e0ea59ae1bc5248564bdd5bfc762b7fed1d79f55329eb33dea4fde) |
| 156 | 贷款结构 | 2026-05 | 9 | [8f71dd1e651d](evidence-a18-import-20260909/8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769) | [b98832a9f822](evidence-a18-import-20260909/b98832a9f822e5298a256edaf44525b928320ad5ba4179d2c49c94525c49e7ac) |
| 157 | 货币 | 2026-05 | 4 | [8f71dd1e651d](evidence-a18-import-20260909/8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769) | [145375bfacd9](evidence-a18-import-20260909/145375bfacd9975258227b7eef88e9be96aab471b50b5906e8384e75dc8a05c1) |
| 158 | 社融 | 2026-05 | 27 | [8f71dd1e651d](evidence-a18-import-20260909/8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769) | [df8b1d7522b6](evidence-a18-import-20260909/df8b1d7522b648d91a7cae790d8f6efc703e52343e3848a78eb0c298a14d788c) |
| 159 | 工具流动性 | 2026-05 | 24 | [3a773a0da916](evidence-a18-import-20260909/3a773a0da916ab5406c1065861aea02ae2f505f16a23639be020ec2048b3a7a8) | [445ced5c275f](evidence-a18-import-20260909/445ced5c275f5b3e070f53d3d0ccd1bed52a83eb44e5ae2aa6b96b9297f6f523) |
| 160 | PMI | 2026-05 | 8 | [1b0658de10a5](evidence-a18-import-20260909/1b0658de10a52ac891f491ef1e6f7120da9b16a25e7d73ca1005dcb8148bcbf3) | [65906421cc38](evidence-a18-import-20260909/65906421cc38a7a0deb9712def1ad8323952ff77556b7541b97cb30c74ab7e47) |
| 161 | PPI | 2026-05 | 9 | [b3226c07e013](evidence-a18-import-20260909/b3226c07e013db99f170b53454e827c3796731276d101bc8f39e076033ee6b42) | [313b84842063](evidence-a18-import-20260909/313b848420630148ca6510b12686a9323a1aef3fae6a0e035edd198e7c0fc17f) |
| 162 | CPI | 2026-05 | 6 | [f021e838ebf2](evidence-a18-import-20260909/f021e838ebf280e92cde9f4d965cf6b40d4efba391ff4225970731662493559f) | [f41760e995f0](evidence-a18-import-20260909/f41760e995f0cc945feb397bf52f335da004abb4bda462eabf0aec6c6e8e585c) |
| 163 | 工业增加值 | 2026-05 | 3 | [1390e559c07b](evidence-a18-import-20260909/1390e559c07b647b5097ebea3e9fb23ff93e153d536e2a4d7f499f251dccf623) | [d9538ec85a05](evidence-a18-import-20260909/d9538ec85a05fb92dde6680bc915ad906fe158e15eb62f57f8c73b0324c88488) |
| 164 | 工业财务 | 2026-05 | 10 | [e57a62c0d664](evidence-a18-import-20260909/e57a62c0d664ba48d748b612bb9eb97d410ad4727b83a4e5f3bf1bd7be8efe25) | [7ef49673ba47](evidence-a18-import-20260909/7ef49673ba47c583a90fa880c4230e47e2596a1b52902b9dd0838b5d3b06c368) |
| 165 | OMO | 2026-05-06 | 2 | [e77572abd6d7](evidence-a18-import-20260909/e77572abd6d7e5c2e280a5c8f987ab430f94799dc2526a27165f4a1ca7e3dd6b) | [7dd792e99fa2](evidence-a18-import-20260909/7dd792e99fa268c955abf5340e1670c4aba3b6a274ef2a2fe807ac311db19c76) |
| 166 | OMO | 2026-05-07 | 2 | [2a647433142c](evidence-a18-import-20260909/2a647433142cfd5b94a9f48c894f4199057638ae0e39cc181a3cb64814b02065) | [0245f285e99f](evidence-a18-import-20260909/0245f285e99f464cf554e70d47c937b054f8c28ca384ad7c921e4d761923035b) |
| 167 | OMO | 2026-05-08 | 2 | [33bd1f8beeb7](evidence-a18-import-20260909/33bd1f8beeb7676ed8980b865e19d2b4de20f9ea437329d7771d53a1162b05fe) | [a56eabfe0a07](evidence-a18-import-20260909/a56eabfe0a07ad60619998ab0432d9f05685018c90414f703d3a1c2d19b04ab8) |
| 168 | OMO | 2026-05-09 | 2 | [dccaff23cbd9](evidence-a18-import-20260909/dccaff23cbd990c761118a3973693f24d5cdce536d31e0ba2e8b553ec73f8f46) | [2559bdbd0aee](evidence-a18-import-20260909/2559bdbd0aee36514499bbe03586b7f8b823fe3c4a8842a7bab55f6bdadeff43) |
| 169 | OMO | 2026-05-11 | 2 | [21e6102c57f1](evidence-a18-import-20260909/21e6102c57f13d6ddb42b19e57a5293109312691c0ad429eb716ba61e6ab9c6e) | [e0e3bcc224c1](evidence-a18-import-20260909/e0e3bcc224c1202bb6dab5e1c60339eb8d0ff569a9a9f169734f4251c2e1de75) |
| 170 | OMO | 2026-05-12 | 2 | [c1c3a52f892c](evidence-a18-import-20260909/c1c3a52f892c3c3b2020c2db933a560b91b1c9d83b8a7b206f4cb7470d013037) | [b19a5f489eec](evidence-a18-import-20260909/b19a5f489eec3d5a9c049adf02c618c1a965f20d107275c5ba95ff7276b466e4) |
| 171 | OMO | 2026-05-13 | 2 | [40533a0ef913](evidence-a18-import-20260909/40533a0ef9130e032861d7d3944772ad74e099dadaa4b2345295acb3fda09f0f) | [262d2dc6f66d](evidence-a18-import-20260909/262d2dc6f66d02ded5265c2c12c497a3d111169e30d26cc6e9ce9901a9044c12) |
| 172 | OMO | 2026-05-14 | 2 | [1c5492deb309](evidence-a18-import-20260909/1c5492deb309cbff97600a064b706022f2294f424938e6c2aa4c981677bd7873) | [a596e0ac780f](evidence-a18-import-20260909/a596e0ac780f72ac3a89ae585f80082820cd6d9dd215ce6c8acd1546e515df86) |
| 173 | OMO | 2026-05-15 | 2 | [9a3cf85c7dd3](evidence-a18-import-20260909/9a3cf85c7dd3d5b5eb326c0ea047d5f8f1f5ae6796be0ce032ea850bc6f48397) | [79647ad1c090](evidence-a18-import-20260909/79647ad1c09043eb3f49362cd119f4087e6125b216fc8d0cdb53df9cafe0f19f) |
| 174 | OMO | 2026-05-18 | 2 | [d8694afe1a6c](evidence-a18-import-20260909/d8694afe1a6cd8c7d2a22b6d0cb074287885a2daa3c6bf2aa01850a7f65ac304) | [2e1edc0639f1](evidence-a18-import-20260909/2e1edc0639f1539658fe47d4b50029d39cd607da8561ffab7edccf891d42bb5f) |
| 175 | OMO | 2026-05-19 | 2 | [c3cfac7d4073](evidence-a18-import-20260909/c3cfac7d4073799ac30e31854f7d71f421dc2c2136096968c4ec4bb4e083310d) | [355dee810769](evidence-a18-import-20260909/355dee81076935a2f50ee91ddb7ced5117ab653c71bc4e7bff702a65e0e8e3fb) |
| 176 | OMO | 2026-05-20 | 2 | [e84b15579c86](evidence-a18-import-20260909/e84b15579c866cf08d538b0f4828b29dea632dacf4a0c739574c237a3337c4ce) | [eff22422f0f6](evidence-a18-import-20260909/eff22422f0f6ff23a961cd9385c7d2a0d036659d626256a068e9ac779769c250) |
| 177 | OMO | 2026-05-21 | 2 | [1d7106395d0a](evidence-a18-import-20260909/1d7106395d0a4a6cf81f2d7c1a6e38588ca49395f0e5e9b8a6c249fc24c42c10) | [22574392d556](evidence-a18-import-20260909/22574392d5562207f882eb45f638cd43b2428439cda50402c1930216d73709f9) |
| 178 | OMO | 2026-05-22 | 2 | [0b9f3358b2e0](evidence-a18-import-20260909/0b9f3358b2e0262aa06606344cd60ab10d298d3d57801db57a219e8ca9e9dbf6) | [8fbab76c5a1a](evidence-a18-import-20260909/8fbab76c5a1a8b32b80047ee33388a1d121cf86b04ea0f3f24a280e96c7b1602) |
| 179 | OMO | 2026-05-25 | 2 | [c590dd498189](evidence-a18-import-20260909/c590dd49818988f6ad6949d5dc6680225999605caca760c3baa909ddcfd7f247) | [4f588a800dfe](evidence-a18-import-20260909/4f588a800dfef43811178d9b26ea9f097b037dea3a80dde8e502aa082a6dba12) |
| 180 | OMO | 2026-05-26 | 2 | [54cee589a63d](evidence-a18-import-20260909/54cee589a63d02287a831c995257e4b6dfdc7b8a85112608e5a70aebd4a89dbb) | [51ca3a95aabe](evidence-a18-import-20260909/51ca3a95aabeb0fb924e6d99fcef3f85b6f38a69a6465db14f25faa8c254933c) |
| 181 | OMO | 2026-05-27 | 2 | [215c5c2b6564](evidence-a18-import-20260909/215c5c2b6564415b7c52b0309e200a4e8c37c00962121793acd326ffc3d7e91a) | [a4f97aa6c046](evidence-a18-import-20260909/a4f97aa6c046bb55431e0c4dab68e8a88d95cf68c0f1bed09055079d741d5da1) |
| 182 | OMO | 2026-05-28 | 2 | [4facc4f518d4](evidence-a18-import-20260909/4facc4f518d4f895efdd9d3047c241b6a7258e149f5a3032de39fc9e421b873d) | [998388178645](evidence-a18-import-20260909/9983881786459f6bb093a4153d2fa16daef52f9de52a49817c74c8eac000c80e) |
| 183 | OMO | 2026-05-29 | 2 | [112a1cceb0e4](evidence-a18-import-20260909/112a1cceb0e4b870e11d20195c249d464238bb0c9a8b6102e2b93bcda1d559cb) | [c27034fa2c29](evidence-a18-import-20260909/c27034fa2c2995fee260986854d4b13ce7d6d7ffd7c3994d3071265aabccf4d4) |
| 184 | 贷款结构 | 2026-06 | 9 | [9ebce7e21c93](evidence-a18-import-20260909/9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168) | [630c0e8abea6](evidence-a18-import-20260909/630c0e8abea615d933e6ba64ba726c2d969eb2b50bfb2aa6cf5f4c2d1ceba096) |
| 185 | 货币 | 2026-06 | 4 | [9ebce7e21c93](evidence-a18-import-20260909/9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168) | [1488ffdbef16](evidence-a18-import-20260909/1488ffdbef16c855b3f43d35b75023d4235d2003a116407e5148ca8af3dd19f2) |
| 186 | 社融 | 2026-06 | 27 | [9ebce7e21c93](evidence-a18-import-20260909/9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168) | [04f487949443](evidence-a18-import-20260909/04f487949443a06402da04d04a31d394ee159b17d2e3f70b75febebccd79bb92) |
| 187 | 工具流动性 | 2026-06 | 24 | [a7d4e3048aed](evidence-a18-import-20260909/a7d4e3048aed1c652a8dcaddeaf9cf1c1e2d95d1e58638d1bdd616bb5e7c71e2) | [8a9758f9a2b5](evidence-a18-import-20260909/8a9758f9a2b5cf68faf49731de586c391d06381cf8a7a247b4540261bbacd1df) |
| 188 | PMI | 2026-06 | 8 | [f0cc6558252e](evidence-a18-import-20260909/f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c) | [b4ee6b2cf5ac](evidence-a18-import-20260909/b4ee6b2cf5ac8cf0dc590e90842e41c219873255f3b00e0a8b50dfeb79b6222b) |
| 189 | PPI | 2026-06 | 9 | [abc018326fbd](evidence-a18-import-20260909/abc018326fbd23f3194c6ba3c6e82d6d14b5689ea1ccd3770009968fea583c98) | [40b463313d5d](evidence-a18-import-20260909/40b463313d5d19d05e1b846758d93a7ee5027e856fd4ea94eab537ab9b30f211) |
| 190 | CPI | 2026-06 | 6 | [57665164e369](evidence-a18-import-20260909/57665164e369235239d22d66d37d19f86172b2ac20a5e755c72199ad7a953d84) | [e5851c555578](evidence-a18-import-20260909/e5851c555578a9b654946caf202818fae31b6054c045ff0922969c1bfea4db09) |
| 191 | 工业增加值 | 2026-06 | 3 | [e81c7eb1fbba](evidence-a18-import-20260909/e81c7eb1fbbac305dd51797d8aead0825ec28cbf19826386856ec9b90e789ddb) | [df2e3de799f8](evidence-a18-import-20260909/df2e3de799f89986ed1eaf1cd677194e30963add5e0746a107e60f25657146d5) |
| 192 | 工业财务 | 2026-06 | 10 | [15c5f2247073](evidence-a18-import-20260909/15c5f2247073e3e0b6c2c35ca4281885aa929b3b9ceb0bd7b8fd8275cbba5047) | [cd7c85aaab9e](evidence-a18-import-20260909/cd7c85aaab9ef827ff329b2ca10fe955fc8ccbff89673548a907c7d15281fd16) |
| 193 | OMO | 2026-06-01 | 2 | [307975324baa](evidence-a18-import-20260909/307975324baa811c0263fa8b526f9eee14899722b54113a288ed225f71663163) | [e43fe2a6d30b](evidence-a18-import-20260909/e43fe2a6d30b96ab7ec5869366b004d60be708811a487ed38627cc61ae93b62a) |
| 194 | OMO | 2026-06-02 | 2 | [16149e8721bb](evidence-a18-import-20260909/16149e8721bb9fabd2327ff7bbe57c55cd429fd1035d391fe2afe7f1a874af0d) | [8af50fdce14d](evidence-a18-import-20260909/8af50fdce14d5e0214b500dde2adcd101460ed777292af6645b7adce7e4d5aef) |
| 195 | OMO | 2026-06-03 | 1 | [632b1709e4c2](evidence-a18-import-20260909/632b1709e4c27aac9b2fd9135394f11efb530321c8a1960577f8a0a562ec65b0) | [2fef2100c9c4](evidence-a18-import-20260909/2fef2100c9c4c0eeeb5907ca18bb7bf0c19b8748e6b1153d7e1cc7cf7b07c6d4) |
| 196 | OMO | 2026-06-04 | 1 | [35d574c797ea](evidence-a18-import-20260909/35d574c797eabf6182032a43f11c5e8330d9fe2e9ed2c2a23d880d21477f24b0) | [66efc665beda](evidence-a18-import-20260909/66efc665beda8638d0cac834ec7aaa80df34ead272cb33569b5df163dc1511e1) |
| 197 | OMO | 2026-06-05 | 2 | [a8561f351f5b](evidence-a18-import-20260909/a8561f351f5b0aac780d2330119ffbe2021c08cf379148c3ed5feb9b9bdaf502) | [f6b65a72d9de](evidence-a18-import-20260909/f6b65a72d9de595556113e9caac069efdc3d49698ef5cda7fad1f15101f7528c) |
| 198 | OMO | 2026-06-08 | 2 | [abffe07adf53](evidence-a18-import-20260909/abffe07adf53163240df4482d678758b4ebb3a9b90eae727c5ad299b1fb429ca) | [eb22e44514e0](evidence-a18-import-20260909/eb22e44514e03b2fab0b4c9f924418cb5f5c00a8746c691a446e70ec13d93419) |
| 199 | OMO | 2026-06-09 | 2 | [11d5bedab262](evidence-a18-import-20260909/11d5bedab2624b0d2c909a9e12c8f34be9f47ff7d91b0e910ee0c5b0f312cd11) | [bb5667fee77e](evidence-a18-import-20260909/bb5667fee77e4038c74165612ccec03954968ec6a4325b299bc0e340c1d5f513) |
| 200 | OMO | 2026-06-10 | 2 | [e2fcd5763e9f](evidence-a18-import-20260909/e2fcd5763e9f28f59265191f0603e87c02dde925bf3658904f753e7e053ba3ac) | [05fb6b6a0a5b](evidence-a18-import-20260909/05fb6b6a0a5b81d759f2e3a8e09bc95b0826d578bffad6db83f7a99fc5a020de) |
| 201 | OMO | 2026-06-11 | 2 | [e04cacc174ca](evidence-a18-import-20260909/e04cacc174ca0cd9ae483ad9fa29ce3d6dd28abad266022705d146d68c94a04b) | [720a2308ddc1](evidence-a18-import-20260909/720a2308ddc140d389a546591479bdbdd04af4b666fc92ac011cca9274ee3dd6) |
| 202 | OMO | 2026-06-12 | 2 | [0bf41664c34c](evidence-a18-import-20260909/0bf41664c34c0eab6bb36ab57f285924db9686dd8b0b0d7a64b8c12410da70c6) | [0ef82e4684c3](evidence-a18-import-20260909/0ef82e4684c305d015356b3858b0a4e5f1abacaf0f34efa174190e92a10053d1) |
| 203 | OMO | 2026-06-15 | 2 | [570cf4a1d23f](evidence-a18-import-20260909/570cf4a1d23f2ee11fa87673158bdfcd5dff0e7d3f140d0c783fae4fb3740a1f) | [a5844a4e2520](evidence-a18-import-20260909/a5844a4e2520e011d17721bcf2b8ec06b79496c36291431ca42a34466eb5fc4e) |
| 204 | OMO | 2026-06-16 | 2 | [c1c95f8b3ac9](evidence-a18-import-20260909/c1c95f8b3ac939273b4cf7c51cfbfd5b8378064ed92d66d4882ecc289ebee433) | [22fe27c07672](evidence-a18-import-20260909/22fe27c0767264f6d0f5d8e29e9af6a2e9f45887ead935e1c0813f43c8ce91b6) |
| 205 | OMO | 2026-06-17 | 2 | [27c42281d162](evidence-a18-import-20260909/27c42281d162b266ab2e5bc380cd2d649bf56a5c494dcb068b7fc45cd5a2ce2a) | [1dbc6c41f509](evidence-a18-import-20260909/1dbc6c41f50979320100ad238c29d5ad52e7f4cfd65e6e9b069d53fa6fb895ec) |
| 206 | OMO | 2026-06-18 | 2 | [0273f3cd1817](evidence-a18-import-20260909/0273f3cd18178ee9cfe4f6e8e4997bd689470d2275490fb397ae8e77fd4a4a49) | [e1e9e0edbc9c](evidence-a18-import-20260909/e1e9e0edbc9ca3fff3b316dac6de3c65fa3af475eab03bd0310888011cf0ae44) |
| 207 | OMO | 2026-06-22 | 2 | [fb426e5f756f](evidence-a18-import-20260909/fb426e5f756f335c8564d67b68f77e5b1f7e07b1b07eb6470d974b3292379e46) | [2ad5c6cf6d08](evidence-a18-import-20260909/2ad5c6cf6d08b466ae526644f2c1fcc1e0ef60f06d01edc631cd5d17343a26b1) |
| 208 | OMO | 2026-06-23 | 2 | [fe58e4443bcc](evidence-a18-import-20260909/fe58e4443bcc1dcfd378392bfc9ec13d9f05a0da2e7163236d4998d9a41b2ae2) | [0b2cdc521def](evidence-a18-import-20260909/0b2cdc521def51a58c36e429a71ae25c653a8349449796f68e466a33ef043d87) |
| 209 | OMO | 2026-06-24 | 2 | [79a1aacdcd41](evidence-a18-import-20260909/79a1aacdcd41da657fa278052788e4a4f0bb2249773a5b39ab3556f905b22eef) | [f21258f60e3a](evidence-a18-import-20260909/f21258f60e3a00fe2f4b03ade638e424c02379df7fd9d08323bdf621202afdd4) |
| 210 | OMO | 2026-06-25 | 2 | [4d9a2047c9bd](evidence-a18-import-20260909/4d9a2047c9bddae7fdedbbc73766723fd771440abdf280ca3ca765fb76518647) | [606943603917](evidence-a18-import-20260909/606943603917761b8c817f44d9bd60e321be044d90e07194414130271b26565b) |
| 211 | OMO | 2026-06-26 | 2 | [be680b9d0e2f](evidence-a18-import-20260909/be680b9d0e2f356f9ff3c4c7fd853e8f94e312514ea75a9ac8a8e9f36490aeea) | [15b5ecef0625](evidence-a18-import-20260909/15b5ecef0625c4176ff4d046722c53bd6a23144bdd4cbe885f4543f7595309c8) |
| 212 | OMO | 2026-06-29 | 2 | [fd2e4138e7c7](evidence-a18-import-20260909/fd2e4138e7c762196b089b3e707b25284fe5b59871153e4a56f9bf76538d80d7) | [3b0a5fd35d65](evidence-a18-import-20260909/3b0a5fd35d65762ba049fe09f64609df1864695ecc79c86f790765e362434139) |
| 213 | OMO | 2026-06-30 | 2 | [3564358207f5](evidence-a18-import-20260909/3564358207f5237c0568030b72ea3c6971690626efcbea32c8afb25b2e9cc9ae) | [3a2b1585e257](evidence-a18-import-20260909/3a2b1585e257f016b80d2bd2173b4aeaaf6db54413c46b328706d941af78b779) |
| 214 | 贷款结构 | 2026-07 | 9 | [933f3546fc3f](evidence-a18-import-20260909/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef) | [9ba3e301a975](evidence-a18-import-20260909/9ba3e301a97522dd067e3d60247be1ba402c25df50412aa282751efbfed1f25d) |
| 215 | 货币 | 2026-07 | 4 | [933f3546fc3f](evidence-a18-import-20260909/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef) | [44a75676a81b](evidence-a18-import-20260909/44a75676a81bf7f45d38c5c998fa67205e6449f44b19b266ee7d5f80c8eb6b39) |
| 216 | 社融 | 2026-07 | 27 | [933f3546fc3f](evidence-a18-import-20260909/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef) | [88b6521f44b7](evidence-a18-import-20260909/88b6521f44b724c971d11c0d138c77dd862aa957f3caaedc86a19a8f8c0dfa7d) |
| 217 | 工具流动性 | 2026-07 | 24 | [10ed3fb5822b](evidence-a18-import-20260909/10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0) | [4d826c2f60ba](evidence-a18-import-20260909/4d826c2f60ba0ac2652db7577aaf42f6068ae5c69f5dc372141335455b562333) |
| 218 | PMI | 2026-07 | 8 | [fff072e83f89](evidence-a18-import-20260909/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6) | [323d7abe5f4b](evidence-a18-import-20260909/323d7abe5f4bd5623b52ba9c70c17938a86dd753bf470cb453df1ba5d9ddbfe6) |
| 219 | PPI | 2026-07 | 9 | [b323261248c0](evidence-a18-import-20260909/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09) | [e12a9d1bfc73](evidence-a18-import-20260909/e12a9d1bfc731a604f8cdb38f60e107d32070d71f06266271ad6de5608b2894b) |
| 220 | CPI | 2026-07 | 6 | [a4b8c84fa4b0](evidence-a18-import-20260909/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49) | [f8e6e879bc91](evidence-a18-import-20260909/f8e6e879bc91a4f6b825bf14f59efe3c9271b0e8678ea0ec65a00462501e58d0) |
| 221 | 工业增加值 | 2026-07 | 3 | [d8a9cc4305ea](evidence-a18-import-20260909/d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609) | [0bd993c220e3](evidence-a18-import-20260909/0bd993c220e3ba9c401227f05c19e2e79656d15ce624ad932be6b78d7676a9d1) |
| 222 | 工业财务 | 2026-07 | 10 | [28388ca9b78a](evidence-a18-import-20260909/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986) | [aa35da9e81cd](evidence-a18-import-20260909/aa35da9e81cd191adb942ae16bd1fc98f2a9732c3e6aab16a6ccaf08f2a543d2) |
| 223 | OMO | 2026-07-01 | 2 | [4a210c639102](evidence-a18-import-20260909/4a210c639102924ca1540b542cf7b042bb4429b23bb046c196971d827c0c6910) | [38f7b59e290f](evidence-a18-import-20260909/38f7b59e290f92d04e44931fd513e3cbc88f47f2203589d76d2c868f9e58219d) |
| 224 | OMO | 2026-07-02 | 2 | [51179e7471b9](evidence-a18-import-20260909/51179e7471b99a4411db05bfb71a8d060b4e08987a2f2fca824009eaae7cad85) | [b2e4652cb418](evidence-a18-import-20260909/b2e4652cb418413fcc03c61b74c05b98718284eedce862b9cab67c19f90fd067) |
| 225 | OMO | 2026-07-03 | 2 | [0ec2dfbbabf5](evidence-a18-import-20260909/0ec2dfbbabf535513a5eb848d37d6704c87bf6ee2f95162f21cf470fad62f9e4) | [b2672e60ef46](evidence-a18-import-20260909/b2672e60ef46b11a27bcab009b7aa6d49aff8a360fb733f50595e74ad8a59b9a) |
| 226 | OMO | 2026-07-06 | 2 | [5934bff7acf7](evidence-a18-import-20260909/5934bff7acf7a2b758c9fa55a6d186cfd0e16fc4e617f09d8033dd1bd505e216) | [1ef8a286171a](evidence-a18-import-20260909/1ef8a286171a1d3a204a5515b4231892f6b7e255cc761809e4957c5d5b343483) |
| 227 | OMO | 2026-07-07 | 2 | [ad2aaeda4713](evidence-a18-import-20260909/ad2aaeda47130dc45735c018d052a83f48c59c40d5271eebb516289da5971ff5) | [d618e307b1ee](evidence-a18-import-20260909/d618e307b1eed5b9d810b943a2e7cf1d1a67d6b2f8c4e08712b4948dcd251396) |
| 228 | OMO | 2026-07-08 | 2 | [fb1a1a641d4b](evidence-a18-import-20260909/fb1a1a641d4ba2cd729f3d2cde2ed7ea1c282a60b1c5d496d9a16f6161976b08) | [30918ab60a8b](evidence-a18-import-20260909/30918ab60a8b0efe2833aa68daa700ec08f026dbc5b62a632e75188489760196) |
| 229 | OMO | 2026-07-09 | 2 | [fe35620384da](evidence-a18-import-20260909/fe35620384da2db7c923675545f4ae04ba94327eba63d280f3c32f04c4c75d27) | [a702cad1104d](evidence-a18-import-20260909/a702cad1104dd55ca8b161a242980d513905c3c43090d866158e76a734b38c01) |
| 230 | OMO | 2026-07-10 | 2 | [cdcf0dca27ad](evidence-a18-import-20260909/cdcf0dca27adcdf325cabe65586861283ae44ce32fd9b695d78ac60198d82511) | [edb52d306b14](evidence-a18-import-20260909/edb52d306b14c4ca7a2845bde36952151c3631551c307c2e5bda58ca8f3bd529) |
| 231 | OMO | 2026-07-13 | 2 | [6edcc856753e](evidence-a18-import-20260909/6edcc856753e2df1daa49a8fc459a691ba9def46a0cd9d94bb13e8070a92a981) | [b71de7024f22](evidence-a18-import-20260909/b71de7024f2238f8d7fe75cb6d4dd8f89cfad2fe54868818407893d8bd7f2bfa) |
| 232 | OMO | 2026-07-14 | 2 | [f4878c418cbb](evidence-a18-import-20260909/f4878c418cbb905be726da013ff8080edc1c6a69784f29d71c19eac1522a233b) | [e244fc32be18](evidence-a18-import-20260909/e244fc32be1891bb4e020560714662ffe5f102ceee0ab5f547d9a903a4df03cc) |
| 233 | OMO | 2026-07-15 | 2 | [8837eba394ab](evidence-a18-import-20260909/8837eba394abea2c289d329e4bb72b2b53fa2a41b76107b1fc13b46d1bdf597c) | [774f5a12c965](evidence-a18-import-20260909/774f5a12c965d233e8731a142030e145ab5ab1ac9547f4d658a7e98eabea5533) |
| 234 | OMO | 2026-07-16 | 2 | [521ef3739cf1](evidence-a18-import-20260909/521ef3739cf15d0f54fb6537308803e7be32a0a71e3a4d7fa22cb0d6dc45fc56) | [19855d8ab891](evidence-a18-import-20260909/19855d8ab89121d71840dbcdd1d9721742adc292754a7d272854f7406662df17) |
| 235 | OMO | 2026-07-17 | 2 | [7a5dbdb7dc4a](evidence-a18-import-20260909/7a5dbdb7dc4a54373d32f7b4c7735109fa2401f7e3e8199bd0c0b6449812ea06) | [7e5385437ac3](evidence-a18-import-20260909/7e5385437ac3bc1b2035fd126320b96a61846d9b557bebeb86e130a6415d9ab2) |
| 236 | OMO | 2026-07-20 | 2 | [3e52f9cdc80d](evidence-a18-import-20260909/3e52f9cdc80d5104f0b9481ad95f16053d5702b0e34c0d541e4f4d6496560c6b) | [1769bcc68531](evidence-a18-import-20260909/1769bcc685316b2a6604735468eb66def9df3ed77e144be7c9fb5956fe4417cc) |
| 237 | OMO | 2026-07-21 | 2 | [56f13a2d8d7b](evidence-a18-import-20260909/56f13a2d8d7bf0ee7dfcc74da7fae3b3cde79084de15234ecd80c426252aa44f) | [cda1e074bc1d](evidence-a18-import-20260909/cda1e074bc1d56d9957fac4b7692a8957d2cf3e6f308b3a7819f09086afd4d32) |
| 238 | OMO | 2026-07-22 | 2 | [926bd207cc8f](evidence-a18-import-20260909/926bd207cc8ffb3cc3c9851c52326a557f0329b3b9998ce868ec35ad11a81a63) | [60122d277bdb](evidence-a18-import-20260909/60122d277bdb54988c3621e4dea6b50b81fcb265cf6fa3b835e1b3722c1562ee) |
| 239 | OMO | 2026-07-23 | 2 | [165c4263e00f](evidence-a18-import-20260909/165c4263e00f7e39a6701806bfaac87cd900a8362757f8ba8242a6bc73cf8514) | [65d4bdb35c23](evidence-a18-import-20260909/65d4bdb35c23e443601627f202504f08742222ba3cf92abfbe6796c8279ba50c) |
| 240 | OMO | 2026-07-24 | 2 | [de2f71b177d8](evidence-a18-import-20260909/de2f71b177d806fe10b44ad1abd194ef571729e55f92f06218924f5cf0955a61) | [eae33fcb48e7](evidence-a18-import-20260909/eae33fcb48e75936989541d7bd2f13001373232c58cdfbf5612e05747935fb0a) |
| 241 | OMO | 2026-07-27 | 2 | [fbe690744661](evidence-a18-import-20260909/fbe6907446615620debe0fe7e1d13dd528460942f3bf76252c4cefdae81fece8) | [0e1a8f2423c0](evidence-a18-import-20260909/0e1a8f2423c0c7247362dff723877cfe00ee06bcfbdb487c79fd9b9150776d2d) |
| 242 | OMO | 2026-07-28 | 2 | [ffbb03b7217b](evidence-a18-import-20260909/ffbb03b7217b34d31aafadb34f088d21b4d9c81d7aa4e6871cd379eb2bca8c99) | [942f5f05bdcd](evidence-a18-import-20260909/942f5f05bdcdbb7c2bb2f942f5a07ad324f5af3d884d8fd50eeebd7591b8f076) |
| 243 | OMO | 2026-07-29 | 2 | [324c8e62afd9](evidence-a18-import-20260909/324c8e62afd9eeae5c51af543730ca88fb59d7b2028c1fed3c0e41fe4e06afe2) | [188c2bdd0dc5](evidence-a18-import-20260909/188c2bdd0dc5a6675cb4bd44572fe875021f5cbfdd83c986aca2aec2cf6f025c) |
| 244 | OMO | 2026-07-30 | 2 | [dae7629276d5](evidence-a18-import-20260909/dae7629276d56fbe5a62819338459eb8e437bc9b6182d595a38aef138344e1a7) | [57e3d52e8a00](evidence-a18-import-20260909/57e3d52e8a00344339c565c32bacceee8fc0d6141c5a8403046734c6f7b878aa) |
| 245 | OMO | 2026-07-31 | 2 | [d0520b41c081](evidence-a18-import-20260909/d0520b41c08123e1c1cf995d5bf6bddb692aa2114a1af0107ea5471379e8565c) | [5794b140c09b](evidence-a18-import-20260909/5794b140c09bba1c5fc2ba5086bb067570f90efb99e0373d4f37e8109f35efdf) |
| 246 | OMO | 2026-08-03 | 2 | [ac547ddd5e88](evidence-a18-import-20260909/ac547ddd5e887f9b1fd4b65cbb8247bcd07e5470b71bd9fac26e5c2d521ad87a) | [7edf1e4fe15d](evidence-a18-import-20260909/7edf1e4fe15deabcc985d8d3ca32f90840460d7dff26bbddfb0b44786fbf60e5) |
| 247 | OMO | 2026-08-04 | 2 | [746632dcb5d3](evidence-a18-import-20260909/746632dcb5d3359ab540b97e4b364e34398a6940466ead1263eea6f24394f407) | [f274671cbdeb](evidence-a18-import-20260909/f274671cbdebffe4c5ffcc73702005a45078bec7144139722b2c8aa7cc033e5c) |
| 248 | OMO | 2026-08-05 | 2 | [f9418798d85c](evidence-a18-import-20260909/f9418798d85c65336c071fa69d84b704a2407f60a09fd553ed276dc2c3b0bb55) | [c5d8dfa7e99d](evidence-a18-import-20260909/c5d8dfa7e99d5da39fb073c4bf1d0ce6c838f6f19a5331c72d0b0a216653410d) |
| 249 | OMO | 2026-08-06 | 2 | [4b9c1baef1fe](evidence-a18-import-20260909/4b9c1baef1fe25af9add371765235aecdda44f2362913c05f1d91c40a924ea81) | [5e8fba9a04eb](evidence-a18-import-20260909/5e8fba9a04ebd07d557457aba4cd676960c044a8bb3bef97b4633dd3fea4525f) |
| 250 | OMO | 2026-08-07 | 2 | [5e1143e701f9](evidence-a18-import-20260909/5e1143e701f9d3b15568ea07503ee90753d1fdc31586bd727d095f4d0ccc161e) | [99ec5bdab8aa](evidence-a18-import-20260909/99ec5bdab8aab98747cd0c62e6f4bdf774d49187adf82d655d1f41cca94987dc) |
| 251 | OMO | 2026-08-10 | 2 | [80c4177bbf1d](evidence-a18-import-20260909/80c4177bbf1d69c71e5fe3dc91b1fffbbdd41a30ebbe99947c3e58e53241861b) | [5fc79f53de43](evidence-a18-import-20260909/5fc79f53de432b12fd1c4d1a2e9a6afd1101228c2f1f8f78ba110f1ab4d23b7a) |
| 252 | OMO | 2026-08-11 | 1 | [3a06a019cbde](evidence-a18-import-20260909/3a06a019cbde41e74f2a90ff532d688d49b01242c69a80f8bb5afb9480a87c2a) | [af285c1b1761](evidence-a18-import-20260909/af285c1b1761c1aeed80603218e3fd202a3a833fd3a3f77d4caa3aa9af937897) |
| 253 | OMO | 2026-08-12 | 1 | [68fb60b62633](evidence-a18-import-20260909/68fb60b626334012b2c50d9bb3b55f4b0fda57c1d03811e886720592fe8b127c) | [cc3125b9d881](evidence-a18-import-20260909/cc3125b9d881071d2b04aafa7d1cc58c0cce1ea57c1b082a5c5415de913c63ad) |
| 254 | OMO | 2026-08-13 | 1 | [e41b2b8d47f2](evidence-a18-import-20260909/e41b2b8d47f22587c29d081f0a73e9b8f4dc3562efba959b3d7b7ebbea46e796) | [35356236fb57](evidence-a18-import-20260909/35356236fb5798002ed3336a7177e1531bb501cef34335854e343e39f0a78241) |
| 255 | OMO | 2026-08-14 | 1 | [1366cecb1866](evidence-a18-import-20260909/1366cecb1866585ca167908a27d375c74b6835cb53ff3ac5ab01979f3de68baa) | [9d3608581081](evidence-a18-import-20260909/9d3608581081ecd4955b483c58f9a7586669456599882f596b85b7a5b04ca8c8) |
| 256 | OMO | 2026-08-17 | 1 | [4d78f34faceb](evidence-a18-import-20260909/4d78f34faceb34c7b5971d16dd9399f4b0b422de44769554059d8e33c78f610e) | [a46ad6a62b80](evidence-a18-import-20260909/a46ad6a62b80ee525c53495f1b43c68f39d67fd11d5a6916301f39df3ee8aae0) |
| 257 | OMO | 2026-08-18 | 1 | [deae3fae857f](evidence-a18-import-20260909/deae3fae857f4dc388b22a28046c74d84914bfaa336b3885e860a6a6ae0df0ea) | [2f45cc02cb3f](evidence-a18-import-20260909/2f45cc02cb3fa61bb46195f38f2b45d8cd5f125a86e3ecad15e383360deefa70) |
| 258 | OMO | 2026-08-19 | 1 | [5f115cef9aa4](evidence-a18-import-20260909/5f115cef9aa4315719105d8c479891791cc6f13e3746d65cd504568a2beb1f6f) | [253767023eea](evidence-a18-import-20260909/253767023eeae547a8a052d96f58ee10b80531d021002e7370be28a472ecadcd) |
| 259 | OMO | 2026-08-20 | 1 | [4f8e70427c93](evidence-a18-import-20260909/4f8e70427c93229fac26cf614f4b8915f15120f7d44cb27f48d03c1c465c0b15) | [289e2b986efc](evidence-a18-import-20260909/289e2b986efcdca2a75aa215f066bedc64032c0ea181fb061be556fc663678a7) |
| 260 | OMO | 2026-08-21 | 2 | [d5673e8e4351](evidence-a18-import-20260909/d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834) | [024486f654a2](evidence-a18-import-20260909/024486f654a294b8eaba1a2d81dbc983d6a5464db17711952e0ecf9b79ff59fe) |
| 261 | OMO | 2026-08-24 | 2 | [76e61b19e28a](evidence-a18-import-20260909/76e61b19e28a99a71f38e3fc5ce5948e5cf159627db43ad9a266c8ed827b297d) | [6b1ea2769d8a](evidence-a18-import-20260909/6b1ea2769d8a7b6fad31ae1848336cc193982e02ca1a45593ff7feb7f90e4b9c) |
| 262 | OMO | 2026-08-25 | 2 | [1f418c4c2447](evidence-a18-import-20260909/1f418c4c24472c3738f8eb3204e4e437e378562a1984bc89bfc9ab67b51a33ef) | [3cccbd1701f9](evidence-a18-import-20260909/3cccbd1701f99a156054137efcbe8f805dc19d4bf6c2d40e5d8e45bc0e3eb5e3) |
| 263 | OMO | 2026-08-26 | 2 | [7fd11fdeff88](evidence-a18-import-20260909/7fd11fdeff88f58a25742bedcda37fe9fc179b54dac7f2ad68fda55a2967642f) | [2b010747e207](evidence-a18-import-20260909/2b010747e20780a73f342b298e1098df29ac493c781c74fdbee3ff1ace6b1337) |
| 264 | OMO | 2026-08-27 | 2 | [9680947ce839](evidence-a18-import-20260909/9680947ce8393d8fc8e83c93d2d8b7c2b83cf0042a7aac6a0f8552b8189349d8) | [873cc73838b4](evidence-a18-import-20260909/873cc73838b406da11e44087ef9e5d4c1050375a115727fb16ac40d1467b02b1) |
| 265 | OMO | 2026-08-28 | 2 | [ee19f9d0ca92](evidence-a18-import-20260909/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a) | [7d7166582ac1](evidence-a18-import-20260909/7d7166582ac16c0e88fd8655a15cf37aecd23e18bed699ee3f4238ae2c1e15f0) |
| 266 | 产能 | 2026-Q1 | 3 | [0c66284a8d04](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | [433f26cf518c](evidence-a18-import-20260909/433f26cf518cc9862b6d66b335f2dfdde4290da06ff5f12916f597627011df12) |
| 267 | 产能 | 2026-Q2 | 3 | [8d1eadceb125](evidence-a18-import-20260909/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8) | [f9d1296dbf19](evidence-a18-import-20260909/f9d1296dbf192e68ad1059868ea777cc0fa8c717e92cb77bb4f5eba6203c424e) |

本文只对既有A18材料作覆盖与交付一致性对账；未将冻结代码129、回归130、来源认证或120日回放纳入已通过范围。
