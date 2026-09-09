# 官方宏观 normalized 消费：以 PMI 为首个纵向切片

2026-09-09，读取 HEAD `bda795f566f60205fc443f3854a8e2eb1b13b76c` 加当前 LPR 工作树。只读源码与既存原件，未执行应用、测试、网络、WSL 或数据库操作；本文中的新反例均是静态设计，尚未复现，不是正式来源认证或真实模型重放结论。

**下一切片宜选 `nbs_pmi`：一个真实公告的八格，能同时验证三项原始指标、两个派生值、检索及回放。** CPI 用作仅日期和修订兼容的补充正例。当前三处消费者已接 LPR 专用校验，却未接常规官方宏观；仅增加一个原件读取函数或展示行状态不能完成该切片。

## 1. 当前源码实际已经具备什么

| 层 | 当前行为与可复用位置 | 不能直接据此声称 |
|---|---|---|
| 取得与入库 | [ingest_official_context_document](../../src/pring_cycle/official_context.py#L239)、[refresh_official_context_document](../../src/pring_cycle/official_context.py#L406)以 v0004 解析完整公告、`normalize=asdict` 保存；[声明入库](../../src/pring_cycle/official_context.py#L346)关联收据、目录、原件引用与时间 | 成功入库不证明文件后来仍可读或当前声明仍对应原件 |
| 双制品读取 | [source_claim_acquisitions_many](../../src/pring_cycle/evidence.py#L303)按精确 claim 关联读取 raw/normalized、核哈希，批内每 receipt 读一次；任一坏关联令该 claim 返回空 | 不自动检查 normalized 的语义，也未自动应用于所有 metric_series 消费 |
| 官方公告重建 | [source_claim_publication](../../src/pring_cycle/evidence.py#L353)重解析 raw，再与 normalized JSON 相等比较，核 provider 和 `URL#sha256`；当前 RRR 使用它 | 此接口只返回一个 surviving publication，会跳过失败关联，未逐格匹配选中值/指标，不能直接当所有宏观声明的采用资格 |
| LPR 已接链 | [parse_lpr_acquisition](../../src/pring_cycle/official_lpr.py#L176)核收据身份并重建 canonical normalized hash；[lpr_claims_matching_acquisitions](../../src/pring_cycle/official_lpr.py#L206)对每关联原件核值、维度、单位、月界、URL 和顶层时间 | LPR normalized 是 observations；常规宏观是带 family/provider/scalars 的完整 release，不可复制 LPR 数据形状 |

当前官方宏观仍经过[检索通用条件](../../src/pring_cycle/search_evidence.py#L195)、[上下文状态](../../src/pring_cycle/context_projection.py#L1394)、[回放选值门](../../src/pring_cycle/model_evaluation.py#L1180)，其中新增原件校验分支仅指定 LPR（另有既存核心、仓单、RRR 分支）。故“成功入库后只损坏 PMI normalized，仍被采用”是有明确源码依据的待 RED 假设；本轮未运行它。

## 2. 真实输入与独立字面期待

PMI 使用[已存 2026-07 官方 HTML](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，398,889 bytes，SHA256 等于文件名；原 URL 为 `https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html`。页头与 meta 均为 [2026/07/31 09:30](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L277)。下表此次直接只读原行，未调用解析器生成期望；与既有[逐格审计](p1-pmi-full-value-audit.md#L121)及[公开测试独立期望](../../tests/models/test_candidate_admission.py#L2225)一致。

| metric／series | 原表字面值 | 原 HTML 行 |
|---|---:|---|
| CN_PMI_ACTIVITY／manufacturing | 49.2 | [表1七月行](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L541) |
| 同上／production | 49.9 | [L543](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L543) |
| 同上／new_orders | 48.5 | [L545](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L545) |
| 同上／purchase_volume | 49.4 | [表2七月行 L817](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L817) |
| CN_PMI_INVENTORY／raw_materials | 48.3 | [L547](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L547) |
| 同上／finished_goods | 48.6 | [L823](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L823) |
| CN_PMI_PRICES／purchase_prices | 53.2 | [L819](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L819) |
| 同上／output_prices | 47.8 | [L821](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L821) |

既定单位为 `diffusion_index_points`，每格 `measure=level`、`period_kind=month`、2026-07-01—07-31；字段映射与三指标归属由 [_parse_pmi](../../src/pring_cycle/official_context.py#L626)和[现有成员契约](../../src/pring_cycle/metric_contracts.py#L100)拥有。不能把原文的百分比表示解释成同比涨跌幅。

CPI 补充使用[七月原件](evidence-13/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49)，233,412 bytes，SHA 等于文件名；URL `https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html`，[页头](evidence-13/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49#L277)是 2026/08/09 09:30。独立期待为 headline mom/yoy/cumulative `-0.1/0.5/0.9`、core `0.3/0.9/1.1` percent，原格定位见[已核六格](p1-cpi-full-value-audit.md#L116)。已有[新目录 CPI 公开正例](../../tests/models/test_candidate_admission.py#L2882)可继续使用。修改时间或数值以制造反例时，产生的是合成测试字节，不能改写或称为另一真实公告。

## 3. 当前真实结构与时间语义

[ParsedOfficialContextRelease](../../src/pring_cycle/official_context.py#L93)顶层字段为 `family/provider/release_event_id/period/release_at/public_available_at/source_url/scalars`。格内有 metric_id、api_name、source_field、期次、维度、value/unit，及默认 definition_version=null/acquisition_ids=[]。这是采集时解析对象；[入库](../../src/pring_cycle/official_context.py#L346)再赋目录版本与 receipt 关联，不能把采集文件改成入库声明形状。

当前代码仍明确存在两种合法差异：

- **仅日期：** [publication_times](../../src/pring_cycle/evidence.py#L38)返回 `(release=null, public=次日本地00:00)`；[解析顶层](../../src/pring_cycle/official_context.py#L201)保存这两个值，但[_parse_core_cpi](../../src/pring_cycle/official_context.py#L607)及 PMI 所用 `_official_scalar` 只收到 release_at，因此格内两时间均为 null。声明取顶层而非格内时间。对照必须是“raw 重建完整采集对象”，再比较“声明两时间 vs 顶层两时间”；不能把仅日期的合格声明误拒。
- **无新公开时间的修订：** [整公告判定](../../src/pring_cycle/official_context.py#L297)只要满足任一旧格/同原件条件，就可能清该次全部声明的两时间，并把 event 改为 `unresolved-publication:<receipt>`。normalized 保留页面时间和原 event。SYSTEM 可采用新值、PUBLIC 继续旧可见版本；同原件重取及改布局不能复活原公开时间。LPR 当前允许声明两时间都空的[兼容判定](../../src/pring_cycle/official_lpr.py#L238)可复用；非空时须与顶层完全同一时刻，不能容忍任意篡改一分钟。

未知日期仍 `(null,null)`；只有确证的新发布时间才能恢复修订的 PUBLIC。沿用[仅日期/未知精度](../../tests/integration/test_context_acquisition_receipts.py#L100)、[同时间修订及重复取件](../../tests/integration/test_context_acquisition_receipts.py#L135)、[明确新时间](../../tests/integration/test_context_acquisition_receipts.py#L57)、[未知后新公开版本](../../tests/integration/test_context_acquisition_receipts.py#L543)的现有行为，不运行时钟回拨或重写历史来求绿。

## 4. 最短公开 RED 与验收

首个测试复用 [test_registered_pmi_original_reaches_selection_and_context](../../tests/models/test_candidate_admission.py#L2199)：隔离 runtime 中通过公开候选准备和 `ingest_official_context_document` 导入真实七月 HTML；取三指标 `period=2026-07`，目标 2026-08-28，显式 PUBLIC 与合格 cutoff。先断言八个独立值和检索 complete，再只改该 receipt normalized 文件字节。不要修改 raw、claim 值、质量标签或目录，否则不能定位消费缺口。

故障后的独立期待：检索 incomplete，坏声明不在 selected_claim_ids；上下文原始行 source_failed；`macro.model_input_observation_version_ids` 不采用这些声明；两个派生值不得仍采用坏父项。诊断行、原值、claims 及 `observation_version_ids` 可以保留，且应明确记录来源失败。

按下列小组扩展，不重做全项目审计：

| 组 | 公共操作与独立期待 |
|---|---|
| 原件完整性 | raw/normalized 各缺失、哈希坏；哈希自洽但 normalized 改格值/单位/source_field/family 或漏格；均不可采用。语义坏收据可沿 [LPR 测试的公开 capture + append_source_claim](../../tests/models/test_candidate_admission.py#L3655)构造，避免直接改 SQLite。 |
| 声明匹配 | 两制品相符，但把 claim 指向错误 metric、期次、维度、单位、URL#hash、值或非空 PUBLIC；应拒绝。同 provider、同一个数值或同日不是身份一致。 |
| 多指标/多来源 | 一个 PMI raw 对应八格、三个指标，单指标小 scope 也能取自身完整成员；一好一坏关联不得只取好件通过。另保留[社融两个公告组合才完整](../../tests/models/test_candidate_admission.py#L2753)，不能把“完整 normalized 公告”扩大为“单张公告必须含整个指标家族所有成员”。 |
| 时间正例 | 精确时间、仅日期、全未知；同页修订无新时间、重复取得、另有新公开时间；SOURCE 校验合格不能给未知时间增加 PUBLIC。期次缺列沿用[1月 CPI 契约](../../src/pring_cycle/metric_contracts.py#L222)，不补零或缩范围。 |
| vintage | 后来的新修订 normalized 损坏，只影响选中该修订的 cutoff；早期仍选旧原件时应合格。当前选中坏版本不能靠校验筛选偷偷退回旧值。 |

回放复用[现有 LPR 单日公共组件 seam](../../tests/models/test_candidate_admission.py#L3756)，把 scope 换成 PMI 三原始指标和相关派生：调用 [evaluate_context_replay](../../src/pring_cycle/model_evaluation.py#L661)，正常单日 evaluated_cutoffs=1；坏 candidate 后产生对应 `candidate_context_selection_invalid:<metric>`，comparison 仍正常。单日组件结果不通过完整模型的三核心/120日/认证门，也不修改已存 manifest。后续正式 calibration/replay 仍走原完整验收。

## 5. 原始行、派生及采用列表必须一致

PMI 的[派生入口](../../src/pring_cycle/context_projection.py#L882)重新通过 [_certified_points_by_period](../../src/pring_cycle/context_projection.py#L1248)读取 series，不读取 `_metric_rows` 的 source_failed。因此只照 LPR 增加展示分支，会留下另一条采用路径。独立算术期待是 `CN_PRODUCTION_ORDER_SPREAD=49.9−48.5=+1.4`、`CN_ORDER_INVENTORY_SPREAD=48.5−48.6=−0.1`，单位 diffusion_index_points；坏父项后，两者及其父项引用不应继续成为实际采用项。计算可沿现有浮点比较约定验证独立十进制期待，不把字符串尾差扩大为本批新金额契约。

[model_input_observation_version_ids](../../src/pring_cycle/context_projection.py#L509)从合格原始/派生行及其 input/direction/calendar 引用汇集；[observation_version_ids](../../src/pring_cycle/context_projection.py#L526)还收集所有诊断 claims。当前 [LPR 反例](../../tests/models/test_candidate_admission.py#L3740)已明确保留诊断。Worker 的[快照引用](../../src/pring_cycle/worker.py#L367)包含后者，不能仅因坏 claim 仍在快照中就说模型继续采用，也不能删除全部诊断来掩盖问题。

新校验须同时供给检索、原始行/前期方向值、派生原始父项、回放选值门和每日输出；[回放](../../src/pring_cycle/model_evaluation.py#L815)既调门也构建上下文，两个面都需公共断言。若以后推广到其他常规家族，信用脉冲、贷款、OMO 等重新读 series 的父项同样需要使用已核资格；本次不自动把它们列为已接通或改变公式。

## 6. 最小实现建议与旧目录边界

1. 在 official_context 增加一个纯 `parse_official_acquisition(receipt, raw)`：限定现有 API/provider/parser/parameters，复用 parse_official_context_document，按与 capture 相同的 canonical 序列化核 normalized hash。双文件可读/hash由既有批读负责，不能省掉 normalized 实际读取。它返回原始 ParsedOfficialContextRelease，不产生目录、认证或时间写入。
2. 增加按明确 metric/definition 分组的 `official_claims_matching_acquisitions`，复用批读、逐 receipt 缓存及全部关联判定。**必须携带 metric_id 和期次契约**：[MetricSeriesPoint/ClaimView](../../src/pring_cycle/evidence.py#L93)本身没有 metric_id/period_kind，不能只按“任意 scalar 值和维度相等”匹配。以[家族映射](../../src/pring_cycle/source_families.py#L14)核来源，按对应 scalar 的 metric、期次、维度、unit/value/source_reference 与顶层时间匹配；实际目录身份仍由已注册定义守卫负责，不把格内 null definition 当错版本。
3. 在三公共消费者仿现有 LPR 调用点复用同一资格判定；同次上下文把已核资格传给原始行和所有参与本切片的派生查询。可以给共享取值 helper 接入验证器，保留原始诊断 series；无需新 schema、长期原件通过缓存或全系统 repository 重写。按物理 receipt 缓存解析，按 cutoff 重选 claim，不跨运行缓存“文件仍存在”。

`source_claim_publication` 的重解析逻辑可提取复用，但不要为本切片更改 RRR 公告完整成员规则。CPI 已归档的 preparation 回执不创建真实声明、还可能没有 `parameters.family`，不是当前公共 ingestion 的完整契约；复用其 raw 通过正式公开入口生成新收据即可，不能为兼容未审归档而放宽所有来源。

新强校验仅对本切片已支持的新登记目录生效，沿用[当前 builtin 兼容开关](../../src/pring_cycle/search_evidence.py#L212)与原认证/active 门；旧目录、旧 parser 制品和历史声明不改写。哈希/格式或重解析结果不符应显式不可核，不能静默把旧 normalized 换成当前结果。此设计不授真实 PMI/CPI 来源认证，也不冻结尚缺业务选择。

唯一交付为本文件；源码、测试、旧材料及用户 dashboard/css/.tmp/output 均未修改。最终本地链接检查与 bytes/SHA256 随交付消息提供。
