# Q1 测试矩阵增量：Standards 审查 151

范围仅为 148—151 的 `tests/models/test_candidate_admission.py` 增量。HEAD 与基点仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。现场核验 151 清单中的 8 个相关文件全部匹配；7 个生产文件与已审 147 完全相同。沿用项目 AGENTS、docs/agents 文档、CONTEXT、ADR 0012 及 12 项 smell 启发式，不重复扩大生产审查。

## 新硬性违反：0；新 smell：0

**准备与单条件变化。** `test_candidate_admission.py:5835` 每个参数项均先公开准入合法候选，再在 `:5843` 改一个映射字段；第 16 项只移除 fields 对该映射的审查引用。`:5848` 重算附件、审查及包哈希，不用损坏 JSON 代替合同错误；`:5867` 按 CLI 边界检查退出码 2、精确错误、无 stdout 和模型数量不变。零哈希项验证缺原件/依据的拒绝，不应解释成字段值语义检验。

**独立预期与实际消费。** `:5936` 独立列出 73.6、-0.5 及单位、期次预期，不复用解析器生成断言。`:6020/6028` 建立合法消费正例，再于 `:6040` 只损坏选定的 raw、normalized 或 mapping；`:6043/6055` 检查实际采用 ID，`:6059` 单独保留可追溯展示。这与 `CONTEXT.md:239` 的已验证证据边界一致。

**版本与时点。** `:6162` 先入库原版本；`:6163` 明示同 URL 改值只是合成修订。`:6202/6210` 断言后续模型不能扩展旧目录许可、旧声明继续保留；`:6214` 使用新定义版本和重审映射，符合 ADR 0012 第 7 行不可变版本约束。`:6236` 保留未知 PUBLIC，符合 `CONTEXT.md:173`。`:6251` 修正的历史目标两模式均缺口，由既有 `search_evidence.py:67`、`context_projection.py:595` 的目标 PUBLIC 截止和 `evidence.py:928` 非空过滤支持；`:6224/6257` 仍分别验证直接 SYSTEM 可用与 PUBLIC 不可用，没有修改业务规则来迎合测试。

141/147 的 **1 项 P3 possible Duplicated Code** 仍为非阻断维护建议；本次无生产变化，没有新增风险证据，不要求重构。

## 输入与边界

| 项目 | SHA256 |
| --- | --- |
| `verification-capacity-inputs-151.json` | `ef10378f26368050ef678598186561da9ac09d2219f615f707548f753c99aa24` |
| `tests/models/test_candidate_admission.py`（352258 bytes） | `6538b8479de072f037aa3f6faef37a347add5c075dfb55eb2f4c4c065dd12023` |

其余 7 文件哈希逐项匹配 [147 报告](verification-capacity-standards-review-147.md)与冻结 151；本轴未执行测试、安装、修改源码或环境。上述为静态审查，不预判 GREEN151，不替代剩余矩阵、完整 Q1、默认全套或真实 120 日验收。累计仍为 0 项硬性违反、1 项非阻断 P3。
