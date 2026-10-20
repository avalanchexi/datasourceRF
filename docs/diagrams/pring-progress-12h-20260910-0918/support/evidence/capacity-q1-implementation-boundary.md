Status: research-resolved
Type: research
Date: 2026-09-10
Implementation: not-executed

# 2026-Q1 产能同区间映射的最小工程边界

**最小落点是补齐“已审映射材料 → 新定义 → 实际收据/原件 → 入库及消费者”的可执行绑定。保留三项成员，复用现有认证包、审查证据引用、定义哈希和获取收据结构；不能只删除 `registered_capacity_q1_mapping_unresolved`。** 本文仅确定实现边界，没有创建来源认证、候选模型或新收据，也没有执行应用、测试、WSL、安装、数据库或网络操作。主线冻结输入 129 及回归 130 不在本文操作范围内。

沿用[已解决的语义决议](capacity-q1-source-mapping-decision.md)：本次只针对已审 2026-Q1 原件，将同一 Jan–Mar 区间的 `quarter_rate` 源格映射为 `ytd_rate`。不再要求寻找另一个 Q1 累计格，也不另设用户审批。正式来源认证、历史 PUBLIC 资格及整体验收仍分别记录，遵守[任务规格](spec.md)、[双点时 ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[不可变版本 ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)和[来源认证 ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)。

## 1. 本次源码已证：守卫在哪里，现有绑定缺什么

| 环节 | 本次确认的实现及限制 | 一手位置 |
|---|---|---|
| 规范成员 | `CN_CAPACITY_UTILIZATION` 固定 `quarter_rate/percent/quarter`、`yoy_change/percentage_points/quarter`、`ytd_rate/percent/year_to_quarter`，维度为 `industry=all_industry`。成员身份没有要求三个独立源格，也没有已审映射字段 | [metric_contracts.py L147](../../src/pring_cycle/metric_contracts.py#L147) |
| 原件解析 | 公开解析器验证官方 URL、字节规模、期次文本及发布时间，调用产能解析。两数值列 Q1 分支把 `quarter_rate` 复用于 `ytd_rate`；四数值列和标准累计列取真实累计格。当前按表头确定行宽，缺累计数据格不再落入当季复用 | [解析入口 L202](../../src/pring_cycle/official_context.py#L202)、[产能分支 L1268](../../src/pring_cycle/official_context.py#L1268)、[行宽及复用 L1310](../../src/pring_cycle/official_context.py#L1310) |
| 收据重建 | `parse_official_acquisition` 目前仅接受 v0004、合法获取类型、空 fields、validated 及 received_at；按收据 family/URL/period 重解析，核 provider 和完整规范 JSON 的 SHA。单独调用此函数不等于 raw CAS 校验；raw/normalized 实际字节校验由仓库读取承担 | [重建 L261](../../src/pring_cycle/official_context.py#L261)、[CAS 读取](../../src/pring_cycle/acquisition.py#L303) |
| 公开入库 | `ingest_official_context_document` 先 capture，继而 `ingest_acquired_official_release` 读取原件，构建 URL+raw SHA 的 source_reference；全批 SourceClaimInput 带同次 acquisition_id。`append_source_claims` 在写入前校验全批声明，所以当前 Q1 ytd 守卫使这一份公告的三声明均不落库；capture 可以已成功 | [入口 L350](../../src/pring_cycle/official_context.py#L350)、[声明 L459](../../src/pring_cycle/official_context.py#L459)、[写入前校验](../../src/pring_cycle/evidence.py#L427) |
| 当前守卫 | `_validate_claim` 仅在声明标记 certified 时调用 `require_registered_source_contract`；后者校验定义、provider、成员及日期后，对任何新注册定义的 Q1 ytd 抛 unresolved。该函数现有参数没有数据库、收据、值或解析版本，故它不能验证“这个映射已审” | [调用 L1294](../../src/pring_cycle/evidence.py#L1294)、[接口 L105](../../src/pring_cycle/source_contract_review.py#L105)、[守卫 L204](../../src/pring_cycle/source_contract_review.py#L204) |
| 候选入场 | 包 v0002 的五个外层字段被严格限定；`definition_bindings` 对完整定义做哈希，包绑定 manifest_hash，review_hash 指向审查。review v0001 的六类 assessment 各需 finding 和 evidence，引用须有注册的 source_reference/artifact_hash，内容须可读且哈希正确。现有代码不解释 Q1 映射证据内容，非空 finding 或 accepted 字符串不能提供该能力 | [admit L22](../../src/pring_cycle/candidate_admission.py#L22)、[包及审查 L196](../../src/pring_cycle/candidate_admission.py#L196) |
| 定义注册 | 注册目录保存 definitions_hash、definitions_json、admitted_by_model_id；读取时核目录哈希及其与所绑定模型清单的一致性。同目录版本不能改定义。MetricDefinition 没有 mapping/parser 专用字段，admission 还拒绝多余定义字段 | [注册表及读取](../../src/pring_cycle/catalog_registry.py#L33)、[定义结构](../../src/pring_cycle/catalog.py#L19)、[字段限制](../../src/pring_cycle/candidate_admission.py#L109) |
| PUBLIC/SYSTEM | `metric_series` 分别使用 public_available_at / available_at，并按传入 definition_version 查询。它是证据选择接口，不负责重读全部官方原件或映射材料；因此查询返回值和模型可采纳是两层事实 | [查询 L854](../../src/pring_cycle/evidence.py#L854)、[精确时点 L1235](../../src/pring_cycle/evidence.py#L1235) |
| 消费完整性 | `official_claims_matching_acquisitions` 经仓库验证每张关联收据的 raw 与 normalized，再核重解析后的来源引用、时间、标量值、维度及起止日。它目前既没有 definition_version 参数，也不核 Q1 映射审查。检索选值、上下文卡片和回放评估都复用此函数 | [收据批量读取](../../src/pring_cycle/evidence.py#L303)、[官方匹配 L295](../../src/pring_cycle/official_context.py#L295)、[检索 L124](../../src/pring_cycle/search_evidence.py#L124)、[卡片 L1423](../../src/pring_cycle/context_projection.py#L1423)、[回放 L1182](../../src/pring_cycle/model_evaluation.py#L1182) |

这条调用链表明，来源资格不能由 `expected_period="2026-Q1"`、新目录名字、`certified`、收据 `validated` 或 normalized 两个值相等中的任一项单独推出。现有[公开反例](../../tests/models/test_candidate_admission.py#L5707)使用真实 Q1 原件及 `prepared_request` 的合成审查包，验证入库仍拒绝；[prepared_request 本身](../../tests/models/test_candidate_admission.py#L60)明确只构造 synthetic review，不是完整真实来源认证。

## 2. 待实施：复用结构的精确绑定

### 映射材料与来源包

建议新增一份内容寻址的**机器可核对映射材料**，由已有 `assessments.semantics.evidence` 和 `assessments.fields.evidence` 的 `artifact_hash/source_reference` 引用。该材料是新的审查附件；不向 ContextScalar、SourceClaimInput、包 v0002 外层或 MetricDefinition 塞研究字段，不新增数据库表。现有结构已允许证据引用任意非空制品，但**识别和校验该附件内容的代码尚待实施**，不能把“允许保存”写作“已支持映射认证”。依据：[现有证据引用验证](../../src/pring_cycle/candidate_admission.py#L227)、[标量的 13 个字段](../../src/pring_cycle/tushare_context.py#L77)。

附件至少冻结下表内容；字段拼写由实现定稿，以下是必须验证的事实，不是创建另一套通用认证系统：

| 必须绑定的身份 | 本次值/规则 |
|---|---|
| 映射规则 | `capacity_q1_same_interval_alias_v0001`；同区间源字段别名，独立源格数不增加 |
| 新定义 | 新 `definition_version`、`CN_CAPACITY_UTILIZATION` 的完整定义哈希；与包 definition_bindings 精确相等。不能复用旧定义身份改变可接受范围 |
| 原件 | 国家统计局、`nbs_capacity_utilization`、`NBS_CAPACITY_UTILIZATION_HTML_V1`；URL `https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html`；raw SHA `0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a`、128195 字节 |
| 原格 | 首张去除相同排版重复后的逻辑表：工业 × 一季度 × 产能利用率（%），原 HTML L348–349；无独立累计列；原字面 73.6，不是邻列 -0.5 |
| 源身份 | `industrial_capacity_utilization_pct`，`industry=all_industry, measure=quarter_rate`，`quarter`，2026-01-01—2026-03-31，percent |
| 目标身份 | `industrial_capacity_utilization_ytd_pct`，`industry=all_industry, measure=ytd_rate`，`year_to_quarter`，同一 2026-01-01—2026-03-31，percent |
| 数值规则 | 目标值逐项等于上述 raw 中唯一真实源格；不容许缩放、累计、平均、换行业或用同比百分点替代。附件所写 73.6 也需对实际原格验证，不能反过来作为原件替代 |
| 解析绑定 | 明确支持的 `parser_version`、family、period、source_url 及完整重建规范哈希约束；实施代码还由新 manifest 的 execution_fingerprint 固定，不能只认版本字符串 |
| 审查性质 | 引用本次语义决议及原字段审计的实际哈希；写明 1 映射对应已计数的源格。映射仅解决 semantics/fields 中该局部事项，不代填 history/time/permissions/usage 的结论 |

一手原件为[本地保存的 HTML](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a#L332)；本次已实际读取并核 SHA 与字节数。区间恒等沿用[语义决议的推论](capacity-q1-source-mapping-decision.md)，不是新增官方原句。

绑定链应为：新定义哈希 → 包的 `definition_bindings` + `manifest_hash` → review 的 `subject_hash` → semantics/fields 中的映射附件哈希 → 附件的精确 raw/字段/期间/parser 身份。包的 review_hash 再把审查材料纳入最终 admitted manifest；整个链只追加新包、新审查及新目录。附件不反向包含其最终包哈希或最终 admitted manifest 哈希，避免循环自引用；其定义哈希、raw 身份和解析规则足够被上层完整绑定。依据：[包、审查及最终清单构造](../../src/pring_cycle/candidate_admission.py#L43)。

### 最小代码接缝

1. **在现有来源契约模块增加一个专用的可复用校验。** 它解析并核对上述映射附件，不接受调用者传入 `mapping_approved=True`、`passed` 或自由字符串作为通行证。`candidate_admission` 在已核包/审查结构及哈希后对被引用的 Q1 映射附件作专门验证；缺映射的旧式包仍不拥有 Q1 别名资格，而不是使无关家族一律无法入场。附件缺定义、错 raw、错 parser、错源格或错误目标身份均拒绝授予该局部资格。[当前通用审查边界](../../src/pring_cycle/candidate_admission.py#L196)
2. **复用目录关联读取已审材料。** 从目标 definition_version 的 registered_metric_catalog.admitted_by_model_id 取得原入场模型的来源包与 review 引用，再核对定义哈希、附件哈希和附件内容。不要从“最新模型”、全局某个 accepted 包或调用方给出的任意文件取映射；不要把相同目录定义加上别处的 review 当作本目录的新资格。若要扩展到新 vintage，应建立新的不可变定义/审查绑定，使旧目录接受集合不变。这个读取能力尚不存在，可放在现有 catalog_registry/source_contract_review 接缝，不需要新注册表。[现有目录关联](../../src/pring_cycle/catalog_registry.py#L77)
3. **入库前必须拿到实际收据并核原格。** `_validate_claim` 已有 database_path 和完整 SourceClaimInput，可将它们提供的定义身份、value、acquisition_id(s) 接到专用校验，再由校验读取 validated 收据及 raw/normalized。保留当前通用字段/日期检查；Q1 分支由“无条件 unresolved”改为“缺少或不匹配已审映射仍 unresolved，匹配且原件重建通过才允许”。不能仅在便捷 ingest 入口检查，否则直接调用公开 `append_source_claims` 可以绕过。实现可复用现有核心原件校验的“批量预校验在事务前”的布局，但不扩成全库重构。[完整声明验证](../../src/pring_cycle/evidence.py#L1294)、[现有核心原件范式](../../src/pring_cycle/evidence.py#L253)
4. **消费者复用同一个校验，不信任写入时曾通过。** 给官方收据匹配路径显式传入目标 definition_version，并核它与模型注册定义一致；ClaimView/MetricSeriesPoint 当前不携带定义版本，不能在帮助函数中猜测。检索、上下文及回放调用方已有目标版本，沿用 Treasury/interbank 的明确参数方式即可。raw、normalized、附件任一后来不可读或损坏，匹配不得产生合格 claim_id；保持现有消费者的 missing/source_failed/invalid 表达。不要悄悄改变通用 `metric_series` 的历史读取含义。[当前匹配接口](../../src/pring_cycle/official_context.py#L295)、[现有消费者版本参数范式](../../src/pring_cycle/search_evidence.py#L133)、[卡片失败状态](../../src/pring_cycle/context_projection.py#L1537)
5. **metric_contracts 保持三个成员及两个 period_kind。** 本次不删 ytd、不合并观测身份、不新增公式，也不把所有 Q1 都改为例外。解析器的独立累计列分支继续读实际累计源格；Q2—Q4 的缺列必须失败。[成员](../../src/pring_cycle/metric_contracts.py#L147)、[实际列选择](../../src/pring_cycle/official_context.py#L1274)

以上是待实施接缝，不是现存 API 或已经完成的代码修改。新 review 附件的验证只认这一份已审 source vintage；相同 URL 的字节变化也不能沿用 raw 许可。其他年份需要自己的明确映射依据和新绑定，不由 `end.month == 3` 自动授予。

### 解析版本与旧收据

**优先保持现有 v0004 的规范输出不变，把新的来源资格判断放在独立映射校验中。** 当前 parser 已输出两个同值标量；批准其来源别名并不必然要求改变这段字节转换。新映射附件明确引用 `official-context-parser-v0004`，新定义/审查绑定实施版本的 [execution_fingerprint](../../src/pring_cycle/runtime_fingerprint.py#L13)，而不是改旧收据或只提高版本号。

若实际实施改变原件解析、列选择或规范输出，则应使用一个新的 parser_version，并在 `parse_official_acquisition` 按版本分派，保留旧 v0004 的重建路径；生成新收据/制品，禁止给旧收据改标签。两个 receipt 允许共享相同 raw SHA，若规范内容相同也允许共享 normalized SHA。新取得或新验证时间仍如实记录，不能因读同一个文件而回填旧 SYSTEM。该条件分支是版本管理推论，依据：[当前严格 parser 版本门](../../src/pring_cycle/official_context.py#L265)、[不可变收据字段](../../src/pring_cycle/acquisition.py#L66)、[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)。

## 3. 待实施验证：公开入库到 PUBLIC/SYSTEM 再到消费者

以下是应补的公开行为验收，不是本次已运行结果。合法正例须在隔离 fixture 中建立**显式标注为 synthetic 的新定义/审查绑定**，映射内容依据真实保存原件独立写出期望；这验证软件接缝。真实来源包仍必须另行完成六类审查，单日 fixture 不代表完整真实候选、120 日、真实 AI 或系统切换通过。

| 场景 | 应验证的结果和边界 | 现有一手接缝 |
|---|---|---|
| 已审精确 Q1 正例 | 从公开 `ingest_official_context_document` 读本次 exact raw；三声明同收据、同原件，quarter/ytd 两个身份各 73.6%，yoy 为 -0.5 percentage_points。trace 可回到新定义、review 附件及 raw 源格，不能只断言记录数 | [入库](../../src/pring_cycle/official_context.py#L350)、[trace](../../src/pring_cycle/evidence.py#L987)、[原件工业行](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a#L347) |
| 同一正例的双点时 | 独立固定 fixture 的可靠公开时点 P、实际 received/validated 时点和最后入库可用时点 S；PUBLIC 在 P 前无、P 起可见，SYSTEM 在 S 前无、S 起可见，且 S 不早于校验完成。语义映射不提前任何时钟；真实原件的页头 2026-04-16 10:00 不能仅因本 fixture 成功就获得历史首发资格 | [PUBLIC/SYSTEM 查询](../../src/pring_cycle/evidence.py#L854)、[入库 available_at 后移](../../src/pring_cycle/evidence.py#L440)、[修订无新公开时点](../../src/pring_cycle/official_context.py#L433) |
| 消费者正例 | 同一新定义、Q1 scope、同一 cutoff 下，`select_retrieval_input` 选择三成员并完整；上下文卡片保持三成员和可追溯 claim_id；独立调用回放资格检查不因该映射报 invalid。选择或卡片的证明不扩张为完整运行成功 | [检索](../../src/pring_cycle/search_evidence.py#L48)、[上下文](../../src/pring_cycle/context_projection.py#L1394)、[回放校验](../../src/pring_cycle/model_evaluation.py#L1182) |
| 未绑定的旧式合成审查 | 保留 `test_registered_capacity_q1_does_not_certify_an_unresolved_reused_cell` 的原意及负例。prepared_request 原有泛化审查即使 accepted、定义 certified，仍无映射资格，三声明不得落入该新注册定义 | [现有反例](../../tests/models/test_candidate_admission.py#L5707) |
| 错期/错目标 | Q2 原件配 `expected_period=2026-Q1`、Q1 raw 配错误年度、起止日或 target measure/unit/source_field 均失败。仅参数改成 Q1 不能使其他表通过；相同月末不是唯一证据 | [期次文本检查](../../src/pring_cycle/official_context.py#L2157)、[契约期次](../../src/pring_cycle/source_contract_review.py#L179) |
| 缺列/错列/重复冲突 | Q1 总行或当季率缺失、拿同比列/分行业列替代、重复总行冲突均拒绝；Q2—Q4 表头有累计而数据行缺累计仍拒绝，不能复制季度率。反例字节明确标注 synthetic mutation | [真实行及行宽](../../src/pring_cycle/official_context.py#L1310)、[原缺列反例记录](capacity-missing-ytd-boundary.md) |
| 坏原件/坏规范制品/坏映射附件 | 入库前任一制品缺失或 SHA 不符均拒绝；合法入库后在隔离 fixture 损坏同一制品，分别验证检索不补齐、上下文 source_failed、回放 invalid。不能把查询仍能读旧声明当作当前消费者合格 | [CAS 校验](../../src/pring_cycle/acquisition.py#L303)、[关联原件失败返回空](../../src/pring_cycle/evidence.py#L329)、[现有消费检查](../../src/pring_cycle/official_context.py#L313) |
| 新 vintage | 同 URL 改字节即新 raw SHA，不能继承这份映射；重新 capture 留新真实时钟及失败/候选事实。若未来经独立审查允许新 vintage，应新建审查/定义绑定和新声明，旧 PUBLIC/SYSTEM cutoff 重现旧版本；无可靠新发布时间时 PUBLIC 保持未知 | [raw 定义发布身份](../../src/pring_cycle/official_context.py#L242)、[修订时间门](../../src/pring_cycle/official_context.py#L433)、[不可变声明身份](../../src/pring_cycle/evidence.py#L1339) |
| 已有独立累计列 | 使用明确含独立累计列且累计值与当季值不同的 fixture，验证 parser 保留实际累计值；同区间别名规则必须不适用，不能以“Q1 两率应相等”覆盖累计格。该页若走真实认证须按独立列/新 vintage 审查；本次 exact-raw 别名包不能接受它。负例是“别名不得套用”，不是“所有含累计列页面都非法” | [标准累计列分支](../../src/pring_cycle/official_context.py#L1274)、[多层实际累计列](../../src/pring_cycle/official_context.py#L1315)、[已有当季/累计分离测试](../../tests/adapters/test_official_context.py#L939) |
| 直接追加绕过 | 公开 `append_source_claims` 中伪造 certified Q1 ytd、漏收据或借另一原件收据仍拒绝；完整匹配材料不能由便捷入库函数外部的布尔标识代替 | [公开写入前统一校验](../../src/pring_cycle/evidence.py#L427) |

零值和负同比属于合法数值，不能作为缺列；Q1 正例的 -0.5 自然覆盖真实负同比。缺可靠 PUBLIC 与获取失败仍是不同状态，不能为了正例可见而赋造发布时间。[publication_times](../../src/pring_cycle/evidence.py#L38)、[A18 时钟边界](a18-document-import-readiness.md)。

## 4. 旧材料的保留及本次实际指纹

本次实际读取 A18 Q1 收据记录为 `acquisition-2b3aff77a1d64332a94574ddbf67c60b`，parser v0004；started/received/validated 分别是 `2026-09-09T07:48:12.813077+00:00`、`07:48:12.830124+00:00`、`07:48:12.930928+00:00`。raw SHA 为 `0c66284a…`，normalized SHA 为 `433f26cf…`。这是已保存 JSON 的事实；本次没有读取数据库、运行重建或证明这些收据已经产生模型可用声明。[原收据记录 L8553](evidence-a18-import-20260909/receipts.json#L8553)、[规范原字节](evidence-a18-import-20260909/433f26cf518cc9862b6d66b335f2dfdde4290da06ff5f12916f597627011df12)。

旧准备包、逐格审计、A18 receipts 中 `source_mapping_pending`、v0004 raw/normalized 和旧认证包都保持原字节及原结论。后续完成映射应另加新结果说明，引用旧 pending 身份与新 review/定义，不能把旧 pending 改写成当时已认证。旧 **8 独立字面格 + 1 复用** 分类保留；新结果最多表述为 **8 个直接源格及 1 个显式映射已核对**，不得称 9 个独立官方字段，更不能把 A18 的 1857+1 改称 1858 独立格。[原逐格审计](p1-capacity-utilization-full-value-audit.md#L5)、[规范对象边界](a18-document-import-readiness.md#L70)。

下表为本次实际读取文件的原始字节 SHA-256；源码只做静态阅读，未执行。路径相对本文件；与旧研究指纹不同的当前源码按此表定位，不能引用旧研究的行号或 SHA 冒充本轮执行输入。

| 输入 | 字节 | SHA-256 |
|---|---:|---|
| [语义决议](capacity-q1-source-mapping-decision.md) | 12902 | `c25614f3c356c9cb807de7a40b401bc0af0f5365927d652278b53556c7801266` |
| [A18 准备边界](a18-document-import-readiness.md) | 20348 | `3a911f5a1cf84f1b092a1badaae59b10597ff9945ac33b0fef8cff533fff7ff4` |
| [逐格审计](p1-capacity-utilization-full-value-audit.md) | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| [缺列记录](capacity-missing-ytd-boundary.md) | 1756 | `b257622abe6acee719e6b014bb2ca5e39ee69c9b1b2b4c8a9efd21870dbbf978` |
| [A18 收据](evidence-a18-import-20260909/receipts.json) | 433467 | `199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c` |
| [Q1 raw](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | 128195 | `0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a` |
| [Q1 normalized](evidence-a18-import-20260909/433f26cf518cc9862b6d66b335f2dfdde4290da06ff5f12916f597627011df12) | 1749 | `433f26cf518cc9862b6d66b335f2dfdde4290da06ff5f12916f597627011df12` |
| [source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 16042 | `58a4590af6fb281edeab6a20c4162652bb1c572dd69fffef212ffeed285eb40c` |
| [official_context.py](../../src/pring_cycle/official_context.py) | 86229 | `32390379d5729d14c0b445ec2a895e3bd799d73ceb691942ed47810bf9cc2bde` |
| [metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 10252 | `db57e40351114456ef31ee1befbaee038f7d90a80e78678dc843248343e549a6` |
| [candidate_admission.py](../../src/pring_cycle/candidate_admission.py) | 13193 | `681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4` |
| [catalog_registry.py](../../src/pring_cycle/catalog_registry.py) | 4349 | `e94a5417a900c111514addb5b3c3b320c3eb0ac723543fca9b116934bcd57ecc` |
| [catalog.py](../../src/pring_cycle/catalog.py) | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| [evidence.py](../../src/pring_cycle/evidence.py) | 60796 | `d27332e14065b179f510c6253e06088f376341349657b598bc692070d9c35ec2` |
| [acquisition.py](../../src/pring_cycle/acquisition.py) | 14584 | `ed81eef2b153417009c0beb356be64bbe8fd164a9f3ea0d6eafe9cdc66ad69f8` |
| [search_evidence.py](../../src/pring_cycle/search_evidence.py) | 19703 | `f87ae76b26f1e7d416a06047f3fd9444058b0cee1b429614d539edc10cf4cca1` |
| [context_projection.py](../../src/pring_cycle/context_projection.py) | 88193 | `44c89b740c4c90c5e488ec6aac2fc39aa917034db7d15aa8bc5b50b11b559528` |
| [model_evaluation.py](../../src/pring_cycle/model_evaluation.py) | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| [tushare_context.py](../../src/pring_cycle/tushare_context.py) | 78830 | `ea66afd3b57969fbd2bcf76889e0bfb7e92037bd1ee12e931b4d14dde2b340a4` |
| [runtime_fingerprint.py](../../src/pring_cycle/runtime_fingerprint.py) | 2775 | `d5976a3fe7530a27262dedbab4f763c259e296faa478cf82e72bb69f689ce46e` |
| [公开入场/消费测试](../../tests/models/test_candidate_admission.py) | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| [解析测试](../../tests/adapters/test_official_context.py) | 39860 | `2ce28bec11a9095996045dfd673ccb187f85e56d62e0542b4fe9b5dbefe0de31` |
| [spec.md](spec.md) | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| [CONTEXT.md](../../CONTEXT.md) | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| [ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md) | 725 | `acb0c307d24518d5e4551f457353535d5398d21c8bd0212c9f9445a82012cf8a` |
| [ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md) | 1277 | `172a1d28d5d67b7075930872032887fd0c4b5748903ed26a5a8760626681ef12` |
| [ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) | 1089 | `8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b` |

本次仅新建本 Markdown；没有修改任一上表输入、旧材料或冻结输入。交付文件本身的字节数与 SHA 在交付消息中记录，不在文件内自引用。
