Status: static-production-review-passed
Axis: Spec
Date: 2026-09-10
Scope: 158 typed mapping dependency isolation

固定基点/HEAD 仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。仅审 158 的 candidate_admission/source_contract_review 生产增量及直接相关测试边界；七生产文件匹配冻结 158。

**新增确定实现问题 0。** 155 提出的后发附件污染旧 cutoff，在新服务标记及 typed 引用范围内已有对应修复；运行关闭仍须 GREEN 和关联回归，不能把旧未分类引用改称已获得隔离语义。

- [工程边界 L50、L55](capacity-q1-implementation-boundary.md#L50)要求完整绑定链及原入场模型权限。[candidate_admission.py L72–79](../../src/pring_cycle/candidate_admission.py#L72)在审查成功后写入真实 request_hash 标记，再计算模型身份；[L92–102](../../src/pring_cycle/candidate_admission.py#L92)拒绝输入自声明。[source_contract_review.py L402–429](../../src/pring_cycle/source_contract_review.py#L402)重读请求、核标记及原始 manifest 与剥离服务字段后的清单一致；[L437–447](../../src/pring_cycle/source_contract_review.py#L437)仍取目标目录原 admitting model，没有从后续模型扩权。
- [L54、L57](capacity-q1-implementation-boundary.md#L54)要求准入验证附件、消费时复验。[源码 L393–399、L539–590](../../src/pring_cycle/source_contract_review.py#L393)验证 typed URI/hash、实际映射对象、semantics/fields 类型一致及原有精确语义。只有有效服务标记下明确 typed 的独立映射读取失败可跳过；[L471–501](../../src/pring_cycle/source_contract_review.py#L471)仍遍历六类普通证据，未提前返回绕过共同依赖。包、review、请求及普通引用错误仍阻断。
- [L81](capacity-q1-implementation-boundary.md#L81)要求旧 cutoff 保留。[L510–518](../../src/pring_cycle/source_contract_review.py#L510)保持 legacy basis 全量严格；仅 typed basis 延迟至 [L696–728](../../src/pring_cycle/source_contract_review.py#L696)实际 raw/parser/值完全匹配后校验。没有改选值顺序：最新已选 claim 无可用映射仍失败，不会用旧 raw 映射替代其数值。多个同 raw grant 中只接受完整可验证链，普通共同证据不因另一个 grant 有效而豁免。

本次未运行测试/安装/修改源码，未确认 GREEN。主线随后创建 159，仅作测试类型修正（可空 ID 收窄、哈希变量注解、等值时钟表达），生产未变；本报告不将 159 测试计为冻结 158 同版。共同证据缺失、旧未分类行为及 typed 独立 basis 的运行反例仍应随最终验收核实。真实认证、120 日与切换不在此静态通过范围。

| 158 生产文件 | 已核实 SHA-256 |
|---|---|
| evidence.py | `5172343e432904c449e060b9c093b50ef33e76c85425c0912e95b4e06f740294` |
| official_context.py | `12dc0b7a78c80f407f4e7971ac0f1ac9c100ba224df6f9913c4a37a410948947` |
| search_evidence.py | `beea9d67529a9b9dd368980c99aa5b49e584561ec50075ab92e78ce5dd66fa46` |
| context_projection.py | `8ccfbc5b1fd1f4d1782c4566b97168f8576f0d810c0de63a70a46869d0e6efaa` |
| model_evaluation.py | `2029a89c4e9ac24ac08ca39f3adce890b1e33ae31af1d1d2d54764b77304e113` |
| source_contract_review.py | `ea14fa4f7017104d34412538912aae976afe80938e52d39980c6df6db06c4e90` |
| candidate_admission.py | `d8ba08c83c2b8159dda6a3a7c4210466a7e5937c21aba2ae02207bf6087ff3fe` |

`test_candidate_admission.py` 冻结 158 SHA 为 `23bf8c2ded8b41b47fd476063c92fa6a2dac4a6bc0b4b554e38d70321aacecc2`；交付前实际已变为 `87029e89d790a17d5c9b6f02ec1826579fa1160ed2882b627b13252a6d8b533e`，明确不属于本报告的七生产文件同版核验结论。
