# normalized 消费源码映射

2026-09-09；HEAD `6662bc2f5d7c8914fdedaab187a15aaea5f042c8` 加当前工作树。只读静态核查，未运行应用或测试；本文的缺口均待公开反例确认。范围是新登记目录，沿用[既有边界](normalized-consumption-boundary.md)、[票02](issues/02-core-acquisition-receipts.md#L17)和[验收38](spec.md#L128)。

共用能力：[read_content](../../src/pring_cycle/acquisition.py#L302)校验指定制品可读及 SHA256，但消费者必须实际调用；[source_claim_originals_many](../../src/pring_cycle/evidence.py#L284)只读 raw。[source_claim_publication](../../src/pring_cycle/evidence.py#L331)读两制品，核身份并将 raw 重解析结果与 normalized JSON 比较；当前仅 RRR 调用。

| 类别 | 实际消费与已经实现的检查 | normalized 边界 |
|---|---|---|
| 核心 | [检索](../../src/pring_cycle/search_evidence.py#L96)、[Worker](../../src/pring_cycle/worker.py#L904)、[回放](../../src/pring_cycle/model_evaluation.py#L387)均用 [CoreInputValidator](../../src/pring_cycle/source_adapters.py#L78)，核 raw 哈希、重解析日值与选中值 | 未读 normalized；其缺失、损坏、语义错配待 RED |
| LPR | 下述通用链核选中状态、认证/质量、期次及成员 | 未调用制品读取或 raw 重解析 |
| 官方宏观／RRR | 常规宏观走通用链；RRR 的 [完整公告选择](../../src/pring_cycle/published_events.py#L17)逐成员调用 publication，接入[检索](../../src/pring_cycle/search_evidence.py#L123)、[上下文](../../src/pring_cycle/context_projection.py#L1312)、[回放](../../src/pring_cycle/model_evaluation.py#L1114) | RRR 已核两制品及对应关系；不能推广到全部官方宏观 |
| 银行间 | DR007/Shibor 走通用链 | 未读两制品或重解析 |
| 仓单 | [检索](../../src/pring_cycle/search_evidence.py#L113)、[上下文](../../src/pring_cycle/context_projection.py#L1326)、[回放](../../src/pring_cycle/model_evaluation.py#L1120)调用 [select_warrant_inputs](../../src/pring_cycle/warrant_inputs.py#L69)，核 raw、逐行值及完整成员 | 未读 normalized；与核心共享 raw 读取能力 |

通用链：[ModelInputSelector](../../src/pring_cycle/search_evidence.py#L180)；[Worker](../../src/pring_cycle/worker.py#L345)→[上下文行](../../src/pring_cycle/context_projection.py#L1298)；[回放质量检查](../../src/pring_cycle/model_evaluation.py#L1183)。认证标签本身不证明制品仍可读；报告的 normalized 输出快照也不等于采集 normalized。

最小公开测试入口可复用现有[核心回放](../../tests/models/test_candidate_admission.py#L4009)、[LPR 入库至上下文](../../tests/models/test_candidate_admission.py#L3339)、[官方宏观](../../tests/models/test_candidate_admission.py#L2246)、[银行间](../../tests/models/test_candidate_admission.py#L1617)、[仓单](../../tests/models/test_candidate_admission.py#L803)。先成功采用，再只破坏 normalized：缺文件、哈希失配、哈希正确但内容与 raw 不符；PUBLIC 正例须原本可见，避免未知公开时间掩盖结果。RRR 已有[截断 normalized 的回放用例](../../tests/models/test_candidate_admission.py#L308)，本轮未执行。

下一切片可复用读取能力，并按家族比较重解析结果；不能仅补 hash 检查便声称对应关系已验。publication 会跳过坏关联，因此多收据一坏一好仍须独立反例。保留旧版本、未知时间和激活门；本轮不判定数值错误、不授认证、不宣告真实回放完成。
