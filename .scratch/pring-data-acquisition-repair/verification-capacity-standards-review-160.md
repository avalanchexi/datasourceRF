# Q1 共同依赖测试：Standards 审查 160

仅审 `test_capacity_q1_mapping_still_requires_common_and_legacy_dependencies` 七参数增量（`test_candidate_admission.py:6405`）。HEAD 仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；两份相关生产文件现场哈希与 158 一致。标准及 12 项 smell 启发式沿用此前审查，跳过工具强制检查项。

**新硬性违反：0；新 smell：0。**

- `:6451/6452` 保存完整请求后使用公开准入；`:6456` 实际入库，再于 `:6487/6489` 通过真实检索与投影建立每个参数的合法正例。没有直接写模型表或模拟消费者。
- `:6434` 为 history、fields 创建不同的普通证据，并把 fields 普通证据放在有效映射之后，能够发现“发现映射便提前返回”的检查遗漏。`:6494/6503` 每个参数只损坏一份实际参与证明的 CAS 原件；来源声明值、统计期、时点和目录保持不变。
- `:6505/6510` 检查检索完整性及实际采用 ID；`:6511` 另行保留观测追溯，不以“接口未报错”代替采用断言。符合 `CONTEXT.md:239/259` 的已验证证据及来源认证包边界，未偏离 ADR 0012 第 7 行不可变模型约束。

范围说明：`legacy_mapping/legacy_basis` 保留未类型化的旧样式引用，但仍经过当前准入服务。这两个参数验证旧样式引用的严格依赖，**不单独证明没有新服务标记的历史模型分支**。本测试也不宣称完整回放或所有原件形态覆盖。

既有 1 项 P3 possible Duplicated Code 保留，仍非阻断；本增量没有新增生产维护风险，不要求扩大重构。

| 输入 | SHA256 |
| --- | --- |
| `verification-capacity-inputs-160.json` | `c24224fd1b455418f88c122c2d7ef1a7e9d3270304ecb48f9dcf0f6009548795` |
| `tests/models/test_candidate_admission.py`（378843 bytes） | `f448d697cbe32bc430b23929135c7040d5ef7675f6dabb5386b65d18bc2788e6` |
| `source_contract_review.py`（同 158） | `ea14fa4f7017104d34412538912aae976afe80938e52d39980c6df6db06c4e90` |
| `candidate_admission.py`（同 158） | `d8ba08c83c2b8159dda6a3a7c4210466a7e5937c21aba2ae02207bf6087ff3fe` |

本轴未运行测试、安装、修改源码或环境，不预判 160 或最终关联通过。累计仍为 0 项硬性违反、1 项非阻断 P3。
