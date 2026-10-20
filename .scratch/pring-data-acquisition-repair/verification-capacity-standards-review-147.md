# Q1 消费与准入切片：Standards 审查 147

范围：144 的仓库消费重验、official matcher 显式目录版本及 7 处调用接线；147 的准入映射预检；相应公开准入、检索、模型采用和单日回放测试。基点与 HEAD 均为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，无新增提交；核对该基点至工作区的 8 文件差异，仅审上述增量。标准沿用 141 的 AGENTS、3 份 docs/agents 文档、CONTEXT、ADR 0012 和完整 12 项 smell 启发式；文档优先，跳过工具强制项。

## 硬性违反：0

`evidence.py:406` 在仓库内部重建声明，并于 `:455` 复用入库校验；`official_context.py:358` 按显式目录版本重验 Q1 映射。检索 `search_evidence.py:130`、投影 `context_projection.py:701/886/1023/1341/1440`、回放 `model_evaluation.py:1186` 均传递对应版本，未在各消费点复制 Q1 认证逻辑。这符合 `CONTEXT.md:55` 的固定规则清单与 `:153` 的观测身份边界。

`candidate_admission.py:68` 在候选创建前调用映射语义预检；`source_contract_review.py:513/519/526` 重读有哈希和来源登记的原件并核对实际单元格。未发现违反 `CONTEXT.md:239` 的已验证证据要求或 `docs/adr/0012-atomic-model-versions-and-parallel-replay.md:7` 的不可变版本约束。

`test_candidate_admission.py:5825` 断言错值准入不增加模型；`:5976/5993` 检查实际采用 ID；`:6025` 明示单日组件回放范围。未将原件可追溯展示当作模型采用，也未宣称真实认证或完整回放。

## 启发式：既有 P3 增量证据，仍非阻断

141 的 **possible Duplicated Code** 保留。本轮 `source_contract_review.py:426` 与 `:473` 增加了相同的“遍历审查引用 → 读取 CAS → JSON 判别映射”形状；`:533` 与 `:593` 分别构建同一映射单元格合同。依据 smell baseline，这是将来规则变更可能不同步的维护风险。目前两者分别承担准入和收据消费责任，未发现实际语义分歧；原哈希/CAS 重复也未出现新错误。后续自然修改时可共享局部提取/合同构建函数，保留各边界校验。计为既有 1 项 P3 的扩展实例，不新增独立 finding，不要求扩大本切片重构。

## 冻结输入

8 个现场 SHA256 全部匹配 `verification-capacity-inputs-147.json`；清单 SHA256：`2e7ccaa2c244f6210e485d2ed8935e9d7d24914a7d077a184c8033dcbb19b4a6`。

| 文件 | SHA256 |
| --- | --- |
| `src/pring_cycle/evidence.py` | `5172343e432904c449e060b9c093b50ef33e76c85425c0912e95b4e06f740294` |
| `src/pring_cycle/official_context.py` | `12dc0b7a78c80f407f4e7971ac0f1ac9c100ba224df6f9913c4a37a410948947` |
| `src/pring_cycle/search_evidence.py` | `beea9d67529a9b9dd368980c99aa5b49e584561ec50075ab92e78ce5dd66fa46` |
| `src/pring_cycle/context_projection.py` | `8ccfbc5b1fd1f4d1782c4566b97168f8576f0d810c0de63a70a46869d0e6efaa` |
| `src/pring_cycle/model_evaluation.py` | `2029a89c4e9ac24ac08ca39f3adce890b1e33ae31af1d1d2d54764b77304e113` |
| `src/pring_cycle/source_contract_review.py` | `b71faa479efc39538c82fbe300475aa5b935b96ae2c48caae5804f90fce55fce` |
| `src/pring_cycle/candidate_admission.py` | `f6677cbd75d982faeca31ef37839858532593bb6f0a4828aed4ea084efc27a49` |
| `tests/models/test_candidate_admission.py` | `d519ea6e09852cb5a529773d2e87f0d84282fde3057bd7eddb5725915f1a32a9` |

本轴未运行测试、安装或修改源码/环境；未认定 GREEN147、完整 Q1 或默认全套通过，剩余反例矩阵仍待补。Standards 累计：0 项硬性违反、1 项非阻断 P3。
