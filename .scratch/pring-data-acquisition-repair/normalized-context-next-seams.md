# 三类上下文 normalized 消费的下一组公开反例

2026-09-09；读取基点 `3e1b7d3f4f2421fa72ee2e30ffbaefb11da03f8d` 及当前冻结工作树。范围仅 LPR、常规官方宏观、DR007/Shibor；只读源码、既存原件及研究回执，未运行应用、测试、WSL、网络或数据库。下文是静态下一切片设计，所有新增正反例均未执行。沿用[票02原件要求](issues/02-core-acquisition-receipts.md#L17)与[规格验收38](spec.md#L128)，不更改认证、旧 v3 隔离或模型激活门。

## 已实现与共用缺口

当前 [source_claim_acquisitions_many](../../src/pring_cycle/evidence.py#L301)已经按精确声明关联批读 raw/normalized、校验可读性与哈希；同一批每个 acquisition 只读一次，任一关联读取失败则该 claim 返回空。此前只读 raw 的基础能力已变化，不能照抄旧研究结论。但本次三类仍走[通用检索选值](../../src/pring_cycle/search_evidence.py#L180)、[上下文状态](../../src/pring_cycle/context_projection.py#L1520)、[回放状态检查](../../src/pring_cycle/model_evaluation.py#L1187)，这些路径没有调用该制品校验。现有检查包括目录/成员、选中值、认证、质量、期次、鲜度及点时边界；它们不证明制品仍在，也不证明 normalized 对应 raw。

[source_claim_publication](../../src/pring_cycle/evidence.py#L351)有 raw 重解析与完整 normalized 对照的实现可参考，但只接受 `official-context-parser-v0004`，当前消费方为 RRR。它跳过失败关联，不等于“所有关联都合格”，也不能原样用于不同结构的 LPR 或 TuShare。

应分别验证两层：**raw → 采集时 normalized 的来源事实**，以及 **采集结果 → 当前选中声明的经济身份与合法时间降级**。不能把 `SourceClaimInput` 整对象与 normalized 逐字相等，也不能先删除所有可变字段后把错目录/错时间一并放行。

## LPR

现有公开路径是 [ingest_lpr_document](../../src/pring_cycle/official_lpr.py#L211)／[refresh_lpr_release](../../src/pring_cycle/official_lpr.py#L297) → 官方共用入库 → 通用消费者。采集身份为 provider `中国货币网`，API `document_import` 或 `official_http_get`，parser `chinamoney-lpr-parser-v0002`，fields `1y,5y_plus`。

normalized 是 [ParsedLprRelease](../../src/pring_cycle/official_lpr.py#L38)：`release_event_id, period, release_at, public_available_at, source_url, observations[{tenor,value}]`。它**没有** `family/provider/scalars/definition_version/acquisition_ids`。[_ingest_lpr_acquisition](../../src/pring_cycle/official_lpr.py#L248)之后才包装 `chinamoney_lpr`、`month` 月首至月末、`percent`、`tenor=1y/5y_plus` 的 ContextScalar，目录版本另传给入库。

可复用真实 [2026-08 raw](evidence-lpr-import-20260908/5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5)及 [normalized](evidence-lpr-import-20260908/9d6ef8142a525532f533d7b78152d9dc1030662916f36eb0c1d2314d1e73a88a)：原值 `1y=3.0, 5y_plus=3.5`，页头 `2026-08-20 09:00+08`，分别 11,000／379 bytes；文件名均已重核为 SHA256。[归档回执](evidence-lpr-import-20260908/receipts.json)是 document_import 准备，`source_claims_created=0`；多了 `imported_from` 元数据，不可假称生产声明，也不宜因这个附加来源字段认定内容错误。

最小公开 seam：[新目录 LPR 入库→双点时→检索→上下文](../../tests/models/test_candidate_admission.py#L3494)。先复用 3.0/3.5 正例，再只改 normalized 的一个 value、tenor、period、URL、event hash 或删除第二期限；即使新收据哈希自洽也应不再采用。raw/normalized 相符但声明期次、单位或值不符也须拒绝。

必须保留[同页无新时间的 3.0→3.1 修订](../../tests/adapters/test_chinamoney_lpr.py#L203)：SYSTEM 新值仍可核，PUBLIC 仍选旧值。入库会清两时间并改为 `unresolved-publication:<acquisition_id>`，采集 normalized 保留原页时间与原事件 ID。重解析校验不可把它恢复成 PUBLIC，也不可因两对象不同误拒 SYSTEM。另保留[仅日期／无日期](../../tests/integration/test_context_acquisition_receipts.py#L582)、[明确新时间修订](../../tests/integration/test_context_acquisition_receipts.py#L604)及[相同时刻不同时区表示](../../tests/integration/test_context_acquisition_receipts.py#L711)；字符串 `空格` 与 `T` 不是经济或时刻冲突。

## 常规官方宏观

[parse_official_context_document](../../src/pring_cycle/official_context.py#L180)返回 `family, provider, release_event_id, period, release_at, public_available_at, source_url, scalars[]`；[capture](../../src/pring_cycle/official_context.py#L263)用 `asdict` 保存整个对象，parser v0004。每格包含指标、api/source_field、period_kind/start/end、dimensions、value、unit，以及 [ContextScalar 默认值](../../src/pring_cycle/tushare_context.py#L77)：`definition_version=null, acquisition_ids=[]`。采集文件不应被改写为后来目录版本。

真实 [7月 CPI raw](evidence-cpi-import-20260908/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49)／[normalized](evidence-cpi-import-20260908/f8e6e879bc91a4f6b825bf14f59efe3c9271b0e8678ea0ec65a00462501e58d0)为 233,412／2,771 bytes，SHA 均等于文件名：headline 的 mom/yoy/cumulative 为 `-0.1/0.5/0.9`，core 为 `0.3/0.9/1.1`，六格 `percent`，顶层 `2026-08-09 09:30+08`。归档[回执](evidence-cpi-import-20260908/receipts.json)也是未创建声明的准备；它的 parameters 没有 family，family 在 normalized 中。正式公共入口会记 family；兼容归档时必须以受支持指标—family 映射、provider/URL 和 raw 重解析核身份，不能只信 normalized 自报 family，也不能冒称这批归档已被现有 publication API 消费。

**仅日期的关键差别：** 顶层 `release_at=null`、`public_available_at=次日本地00:00`；[_parse_core_cpi](../../src/pring_cycle/official_context.py#L607)／[_official_scalar](../../src/pring_cycle/official_context.py#L2151)的格内两时间却由 release_at 构造，均为 null。声明取[顶层时间与整公告修订结果](../../src/pring_cycle/official_context.py#L320)，不是格内时间。[现有精度用例](../../tests/integration/test_context_acquisition_receipts.py#L100)已写这个行为；下一消费正例须保留，不能强要求“声明 PUBLIC = scalar PUBLIC”。

最小 seam 复用[真实家族参数化入库→选值→上下文](../../tests/models/test_candidate_admission.py#L2401)，先选一个多指标公告，如 [7月 PMI 原表](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L541)中的 manufacturing `49.2`、production `49.9`、new_orders `48.5`、raw_materials `48.3`，既有[独立期望](../../tests/models/test_candidate_admission.py#L2225)可复用。删格／换同日另一指标或 source_field／改单位／格内默认目录改错值，normalized 哈希自洽仍不能通过；完整 raw 对照后，再按 selected metric/period/member 匹配，不要求一次小 scope 包含所有同公告指标。

保留[同时间修订及重复取得不恢复 PUBLIC](../../tests/integration/test_context_acquisition_receipts.py#L135)。使用已有[1月缺累计列及季度形状](../../tests/models/test_candidate_admission.py#L2462)正例，合法缺列不能新增默认 0 或固定成员要求；1—2月合并、YTD、负环比、真实 0 等继续由家族原解析器负责，不扩展本次业务规则。

## DR007／Shibor

[transmission](../../src/pring_cycle/tushare_context.py#L603)调用 `repo_daily(ts_code=DR007.IB,start_date,end_date)` 的 `ts_code,trade_date,repo_maturity,weight`，只取同时匹配 `DR007.IB/DR007` 的行；`shibor(start_date,end_date)` 的 `date,on,1w,3m` 对应 `overnight/1w/3m`。[_daily_scalar](../../src/pring_cycle/tushare_context.py#L1639)产生 `business_day`、start=end、percent，时间/目录默认 null。[_call](../../src/pring_cycle/tushare_context.py#L1110)已核 code、字段与[日期范围](../../src/pring_cycle/tushare_context.py#L1892)，不能另报“尚未检查返回日期”。

raw 是 TuShare `code/data.fields/data.items` 响应；最终 normalized **不是 rows**，而是 [acquire_scalars](../../src/pring_cycle/tushare_context.py#L171)关联 acquisition_ids 后，[complete_validation](../../src/pring_cycle/tushare_context.py#L197)保存的标量列表。普通 transmission 没有 rejected_fields；其他接口的拒绝字段封装不应无条件套到这两个 API。调用方可在公开 retrieve 回调里显式补合法时间／当前 definition；不能把这种 normalized 与原始默认 null 全对象硬等。应先独立验证附加时间有时区、definition 为 null 或当前版本、关联收据完整，再比较 raw 决定的经济字段。显式错误目录和错关联不能被“恢复默认值”掩盖。

**同 API 多收据必须有正例：** 当前按 api_name 将每格关联本批所有同 API 收据，每张 receipt 的 normalized 保存所有相关格。因此公开 retrieve 连续取两日时，单张 raw 可以只有一天、该张 normalized 却有同 API 两天结果。不能用单张 raw 的全表与整个 normalized 列表硬等。最窄复算单位是声明所关联的完整同 API 批次：核每份 raw/normalized 与 receipt 关系，合并该组实际响应生成期次/成员期望，并保持每格至少有确切原行；不将 repo_daily 与 shibor 合并、不强行缩为单请求、不只验证当前目标格后忽略伪造附加格。若下一实现暂未支持这种现有形状，应显式报未支持，不能宣称所有公开入口已接通。

[CFETS DR 原件](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d)的唯一 DR007 `wghtdAvgRepoRate=1.3859`；[Shibor 原件](evidence-13/365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62)的 `showDateCN=2026-08-28, ON=1.3390,1W=1.3870,3M=1.4300`。分别 1,425／2,112 bytes，SHA 等于文件名。它们提供独立数值期望，**不是 TuShare 交付原件，也不证明历史首发时间**。复用[已明确为合成传输的公开用例](../../tests/models/test_candidate_admission.py#L1772)，不伪装渠道。

下一反例：normalized 改 weight 为 close 值 `1.3806`、以 R007 冒充 DR007、Shibor 缺 3m／换期限、wrong API/field、wrong day、错目录、空／错误 acquisition_ids；均保留真实目标身份。先用合成且明确 PUBLIC 的正例观察选择，再故障注入，避免 PUBLIC 原本未知导致假绿。另加默认 null、显式正确 definition、同 API 两日联合三种正例，以及值修订后 normalized 仍有时间而[入库降两时间为 null](../../src/pring_cycle/tushare_context.py#L1295)的 SYSTEM 正例；不能因此恢复历史 PUBLIC。

## 必须一起接的公开消费边界

1. [select_retrieval_input](../../src/pring_cycle/search_evidence.py#L41)应报告不完整、移除不可核 selected_claim_ids；不能只验证 capture/ingest，因为故障发生在成功入库之后。
2. [build_context_projection](../../src/pring_cycle/context_projection.py#L227)不能只让 `_metric_rows` 显示 source_failed：[DR007 派生](../../src/pring_cycle/context_projection.py#L814)重新经 [_latest_certified_point](../../src/pring_cycle/context_projection.py#L1276)读 series，其他派生也用 [_certified_point](../../src/pring_cycle/context_projection.py#L2098)。所有同次计算须消费同一已核资格集合；失效值不能留在派生值、父项 trace 或 observation_version_ids 中。
3. [evaluate_context_replay](../../src/pring_cycle/model_evaluation.py#L660)及其[选值门](../../src/pring_cycle/model_evaluation.py#L1086)须复用该校验，关联到 calibration/replay 的公开结果；不能只改展示路径或直接测私有 validator。

一条最小派生反例：用独立 DR007 `1.3859` 与 [PBC 08-28 七天逆回购原表](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a#L350)利率 `1.4`，正例利差 `(1.3859−1.4)×100=-1.41bp`；只坏 DR normalized 后，原始行、利差、检索和回放同时不再采纳该声明。这是待执行的合成软件实验，未声明真实模型可用。

共用故障组为 normalized 缺失、文件字节哈希失配、哈希正确但结构/来源事实错配、关联一好一坏；另保持另一合格 vintage，验证校验针对每个 cutoff 真正选中的声明，不因未来未选原件损坏污染早期结果，也不以坏的新合格声明静默退回旧值。SYSTEM 新修订可核而 PUBLIC 旧版可用是另一种合法情况；[目标日中国 PUBLIC 上界](../../src/pring_cycle/search_evidence.py#L60)仍约束普通 SYSTEM 定向查询，不能用无 target 的 SYSTEM 诊断结果要求历史 selector 接受新修订。

建议延用现有批量双制品读取，并把按家族的纯重解析／经济身份／时间兼容结果缓存于**单次消费**；跨日回放缓存物理解析、逐日重选版本。不得长期缓存“文件仍存在”，不得把读取校验改写为认证通过，也不为本批另建数据库 schema、改旧原件或重写历史声明。

输入工作树指纹（标准库只读，不执行这些模块）：

| 文件 | bytes | SHA256 |
|---|---:|---|
| official_lpr.py | 15707 | `2173c4ea5d3c16acd26fb58c9a9a04ae79e5519403be93bf8b46a94f22f290d1` |
| official_context.py | 80147 | `0e6f57ea5770e3d35b2dbbd3255a8df9e1237296f2c6b97c1d6e2d54dbc20252` |
| tushare_context.py | 76846 | `5a642d4a7275c8991d76f6e5ec24f271ff1fc8693e213fc7abeca26d0602c443` |
| evidence.py | 60640 | `9a969d05fbce05fcd79c4085ba9e191c32c8cddf2e6607ed4ff22976a6753584` |
| context_projection.py | 82202 | `f3e986b42ff235159dba263357b740ba06b42619ed4e233e391712de2115f2af` |
| search_evidence.py | 16641 | `be9c08917c9ec3220654e155e14213eaf5a3d2d7602e19e1f282ecced34a30cb` |
| model_evaluation.py | 48138 | `4fcbd2a8531839fff04b6c542aab14c11428835d66d4bcebae8163aafe4243ce` |
| tests/models/test_candidate_admission.py | 178237 | `4b466ca451a4114c09f7f3c153ef8cb9ef870469d0c8a7b16055df419a2f86a1` |

前七项位于 `src/pring_cycle/`。唯一交付为本文件；53 个本地链接指向 22 个唯一文件，路径存在及行号范围均已只读核对；这不代表链接目标中的测试本轮已执行。最终 SHA/bytes 随交付消息提供。所有样本及旧报告保持原字节。
