# Q1 第一入库切片：Standards 审查 141

审查范围：`capacity_q1_alias_value`、四个 mapping helper、入库接线及对应公开正例。基点和 HEAD 均为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，新增提交为空；采用 `git diff 99c495a217b66d4bca9d6ceae4688ee69d4382bb -- src/pring_cycle/source_contract_review.py src/pring_cycle/evidence.py src/pring_cycle/official_context.py tests/models/test_candidate_admission.py` 的工作区差异，仅审查上述新增切片。历史其他 hunk、后续消费矩阵不计入本轴。

标准来源：`AGENTS.md`、`docs/agents/issue-tracker.md`、`docs/agents/domain.md`、`docs/agents/triage-labels.md`、`CONTEXT.md`、ADR 0012，以及 code-review skill 的 12 项 smell 启发式。未运行测试、静态工具或安装依赖；未修改源代码。

## 硬性违反：0

`source_contract_review.py:390` 从目标目录的 `admitted_by_model_id` 读取既有认证包；`official_context.py:1268` 将新增资格判断与冻结解析器分开；测试 `test_candidate_admission.py:5711` 明示合成审查范围，未激活模型。未发现违反 `CONTEXT.md:55` 的不可变模型、`:133` 的观测身份，以及 `docs/adr/0012-atomic-model-versions-and-parallel-replay.md:7` 的新版本与历史保留约束。公开/系统点时被分别断言；这不构成完整消费链路验收。

## 启发式判断：1（P3，非阻断）

**Possible Duplicated Code**：新增 `source_contract_review.py:365` 的 `json.dumps(... sort_keys=True, separators=(",", ":"), allow_nan=False)` 哈希形状和 `:373` 的 SHA 格式、CAS 路径、内容哈希校验，重复既有 `candidate_admission.py:257`、`:272`。它们同时服务认证文档，未来序列化或原件读取规则变更需要同步维护。依据 code-review smell baseline 的“相同逻辑形状可抽取共享形状”；这是维护性判断，并非文档标准违规。后续自然修改该边界时可共享小型纯函数，保留各入口的领域错误；无需为本切片扩大重构。冻结解析器中的表格判定不列为重复问题，因为独立资格检查保留旧解析语义是明确边界。

## 输入核验

以下 4 项现场 SHA256 均与 `verification-capacity-inputs-141.json` 一致；清单 SHA256 为 `f70d6d7b24e9e8a6bb5b06a4e3726df67a87238617cf372da42c8a237e326973`。

| 文件 | SHA256 |
| --- | --- |
| `src/pring_cycle/source_contract_review.py` | `764d70c35fa9322a3433c657ec793e1f6d6c9d4887a3b592acea18a60339e459` |
| `src/pring_cycle/evidence.py` | `ea4e18a38828aeaf0f7625bb69987968e0ccfda074899b0283cb33d201dc3492` |
| `src/pring_cycle/official_context.py` | `5766d93e3245c9061ac5c65c6bab83c8f38a7aa5e7f558bc7ca0611e69850fd9` |
| `tests/models/test_candidate_admission.py` | `62cfdde5e6d2da116ff97c1d04dae752565d6546a03c3dceb54d853ab0ed4173` |

Standards：0 项硬性违反，1 项非阻断维护性启发式；本报告不替代 Spec 审查或运行结果。
