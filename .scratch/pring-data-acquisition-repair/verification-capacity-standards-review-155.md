# Q1 收据、表形状与 PUBLIC 回放：Standards 审查 155

范围仅为 153—155 的测试增量；基点与 HEAD 仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。现场 8 文件哈希均匹配冻结 155，7 个生产文件与已审 147 完全相同。沿用 AGENTS、docs/agents 文档、CONTEXT、ADR 0012 和完整 12 项 smell 启发式，跳过工具强制检查项。

## 新硬性违反：0；新 smell：0

**真实边界与独立预期。** `test_candidate_admission.py:6114` 通过仓库公开合同检查验证正确目录 ID，再仅换成比较目录 ID 并要求拒用。`:6120/6152` 调用实际 PUBLIC 回放；损坏或删除单个附件前先核对两侧采用 ID。`:6143` 明示 raw/normalized 为两目录共享的同一 CAS，故断言两侧受影响；映射损坏仅影响目标目录。该设计遵守 `CONTEXT.md:153` 的观测身份，而非假设不同目录必有不同原件。

**晚修订。** `:6190` 在首个候选准入前明确纳入两个原件映射，不修改既有许可；`:6250/6255` 使用独立数值、日期常量验证合成修订。`:6267` 先断言两个 PUBLIC 截止分别采用旧/新 ID，再于 `:6281` 只损坏晚修订的一份原件。`:6292/6297` 分别要求旧截止仍用旧值、最新截止不得退回旧值；比较侧仍独立验证。符合 `CONTEXT.md:161` 的公开点时含义及 ADR 0012 第 7 行历史保留约束，且 `:6216` 明示只做两日组件验证。

**收据与表形状。** `:6494` 先验证公开 direct append 合法正例；每个 fault 只替换、增添、缺失一个收据或损坏一份原件。`:6520` 使用实际 capture 建立哈希自洽的错误 normalized，`:6537` 确認 CAS 可读，再由入库拒绝其语义不符，符合 `CONTEXT.md:239` 已验证证据要求。`:6616` 每项先准入合法合成表；`:6626` 证明独立累计列可正常解析，再要求其不能套用别名规则，避免以字段缺失伪装语义反例。新增 source/target 字段、schema、rule 四项沿用逐项合法正例和单字段变更的准入结构。

既有 **1 项 P3 possible Duplicated Code** 保留、仍非阻断；没有新生产变化或实际新风险证据，不要求扩大重构。

## 输入与限界

| 项目 | SHA256 |
| --- | --- |
| `verification-capacity-inputs-155.json` | `d52a9c38113308c0caaef32d8fe2de2bd54e354e513ba63bc76751f1abb9d7dd` |
| `tests/models/test_candidate_admission.py`（369582 bytes） | `c5dc2ce2ace6eefbffdb00c3fa877deee4227fe950e7cc5da490e8e5d2b361ed` |

其余 7 文件逐项匹配 [147 报告](verification-capacity-standards-review-147.md)。本轴未运行测试、安装或修改源码/环境；不预判 155、四项新增准入反例或最终关联回归通过，不替代完整 Q1、默认全套和真实 120 日验收。
