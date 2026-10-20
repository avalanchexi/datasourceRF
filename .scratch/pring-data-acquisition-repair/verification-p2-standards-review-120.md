# Standards — P2 增量复审 120

基点及 HEAD：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`；提交列表为空。只读指定五文件，未运行应用、测试、WSL、SQL 或网络；110/116 保留。

## 原发现：已关闭

已采用点的资格、空来源、缺行、原始单位、派生有限实值与同日两父项计算均已加守门；合法前期方向父项有公开正例。既有来源合同未放宽。

## 剩余硬规范问题：2

1. **高：未核可选派生输出定义自身资格。** `model_outputs.py:602–630`、`667–690` 验证公式及父项，却不读输出定义 certification_status。保持两父项 certified，仅把 UST_2S10S_SPREAD 定义设 awaiting；恢复占位行为 current、正确 40bp、完整父项及采用 ID，静态路径仍可通过。现有 awaiting_current 同时取消父项资格，未覆盖此例。应按 `context_projection.py:361–364` 已有集合允许 certified／derived_from_certified_inputs，拒绝 awaiting。依据：`CONTEXT.md:268` 要求 P2 认证后才进入正式投影；ADR0012 第7行要求固定模型的认证与质量验收，存档不能违背其实际计算守门。

2. **中：只按候选认证筛 source_metrics，漏掉比较版合法实值。** `context_replay_scope.py:123–127` 仍只遍历 candidate。比较版 P2 certified 且有 PUBLIC 实值、候选版降为 awaiting 时，optional_metrics 要求两侧展示，但 source_metrics 排除该来源；比较版 current 行没有对应快照，新增 validator 将拒绝合法差异。应覆盖任一侧实际可能采用的受影响来源。依据：ADR0012 的“可审计比较”；`spec.md:98/107` 区分可选 P2 缺口与模型资格，不将其变成额外硬门。公开组件可用“仅候选降级、比较版仍有值”复现。

两项均为静态反例，本审查未运行验证。

## 启发式建议：0

未见新增实质气味。不宣称新准入目录120日回放、真实认证或激活完成。

## 输入 SHA256

| 文件 | SHA256 |
|---|---|
| src/pring_cycle/context_replay_scope.py | `9c81258a54b88c856548a196fdf9a80ab19a4fa491a7ba90fd27b71ce6c8a886` |
| src/pring_cycle/model_evaluation.py | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| src/pring_cycle/model_outputs.py | `ab80bee20cd290919a270bac274cca6b019623119a5a9659cd046e9a5331d5fd` |
| tests/models/test_candidate_admission.py | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| tests/models/test_candidate_replay.py | `4f2403251f944a20c1bafd83f5bffb8b591117a57efe70523580776813bae36c` |
