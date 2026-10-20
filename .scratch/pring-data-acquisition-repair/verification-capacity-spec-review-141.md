Status: reviewed-with-finding
Axis: Spec
Date: 2026-09-10
Scope: Q1 first ingress slice; static review only

固定基点与 HEAD 均为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，提交列表为空。实际非空审查命令为 `git diff 99c495a217b66d4bca9d6ceae4688ee69d4382bb -- src/pring_cycle/source_contract_review.py src/pring_cycle/evidence.py src/pring_cycle/official_context.py tests/models/test_candidate_admission.py`；只审新增 Q1 映射帮助函数、写入前接入及公开正例，排除既有其他修复。

## 确定逻辑缺口：1 项，P1

**直接追加可提前 PUBLIC 时间。** [工程边界 L75](capacity-q1-implementation-boundary.md#L75)要求“语义映射不提前任何时钟”，[L56](capacity-q1-implementation-boundary.md#L56)要求统一入库前校验防止公开 `append_source_claims` 绕过。当前 [evidence.py L1310–1328](../../src/pring_cycle/evidence.py#L1310)未把声明 `release_at/public_available_at` 交给新校验；[source_contract_review.py L478–528](../../src/pring_cycle/source_contract_review.py#L478)仅比对收据、原件及值。通用追加的 [L468–475](../../src/pring_cycle/evidence.py#L468)只约束 SYSTEM/fetched 时钟；[L1379–1407](../../src/pring_cycle/evidence.py#L1379)仅拒绝已存在 release_event_id 的时间冲突。

因此合法映射、原件和收据配一个新的 release_event_id，直接追加相同 ytd 值但更早的 PUBLIC 时间，可以穿过当前全部检查并提前被 PUBLIC 查询选中。这是静态控制流已确认的缺口，尚未执行反例；建议从合法直写正例仅改公开时钟（使用独立合法事件身份），先取得 RED，再核对声明已知时间与重建公告时间；允许未知时间继续未知。消费者随后拒绝也不能替代入库时钟约束。

## 已实现与明确后续范围

[L55](capacity-q1-implementation-boundary.md#L55)的原入场模型绑定在 [source_contract_review.py L391–445](../../src/pring_cycle/source_contract_review.py#L391)实现；完整定义、包、review、双 assessment 附件、实际 raw/normalized 重建及源格一致性均有对应校验。parser v0004 输出未修改，符合 [L64](capacity-q1-implementation-boundary.md#L64)。未发现额外范围扩张。

admission 附件语义预检、消费者复验及四路反例矩阵按本切片声明仍待实施，不作为隐瞒完成的发现。新正例明确使用 synthetic 审查，不能证明真实来源认证、历史首发、完整候选或 120 日验收。本审查未执行测试或修改源码/环境。

## 已读输入 SHA-256

四个审查文件当前字节均匹配 `verification-capacity-inputs-141.json`：

| 文件 | SHA-256 |
|---|---|
| source_contract_review.py | `764d70c35fa9322a3433c657ec793e1f6d6c9d4887a3b592acea18a60339e459` |
| evidence.py | `ea4e18a38828aeaf0f7625bb69987968e0ccfda074899b0283cb33d201dc3492` |
| official_context.py | `5766d93e3245c9061ac5c65c6bab83c8f38a7aa5e7f558bc7ca0611e69850fd9` |
| test_candidate_admission.py | `62cfdde5e6d2da116ff97c1d04dae752565d6546a03c3dceb54d853ab0ed4173` |
| capacity-q1-implementation-boundary.md | `056a04208ce0cf898f369a65c4a905849f9465b286cf8b76b3a019924de966ed` |
| capacity-q1-source-mapping-decision.md | `c25614f3c356c9cb807de7a40b401bc0af0f5365927d652278b53556c7801266` |
| issues/19-immutable-candidate-catalog.md | `a95f4c278aac1c02ceeb38fc1b87dcd303604724232a6d5fcf3aec1d252059e1` |
| spec.md | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
