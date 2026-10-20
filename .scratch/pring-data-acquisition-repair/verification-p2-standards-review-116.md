# Standards — P2 最终候选增量复审 116

基点及 HEAD：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`；其后提交列表为空。只审指定五文件的 P2 增量，未执行应用、测试、WSL、SQL 或网络；110 报告未修改。

## 原问题：已关闭

`model_outputs.py:707–716` 已独立检查实际采用点的定义认证、声明认证、质量和 reported_value；`550–622` 已核可选当前行、父项、采用 ID 及缺行。必需集合保留信用脉冲的 GDP 依赖，合法 P2 缺口可以留存。公开测试包含真实计算 40bp 正例及资格、孤立引用、缺点、缺血缘和缺行反例；未绕过来源契约。

## 剩余明文标准问题：1

**高：可选 current/available 输出的标量身份仍未完整校验。** `model_outputs.py:585–610` 的派生分支核验父项后直接 continue；以合法 40bp 输出为起点，保留完整公式、父项和采用 ID，只把两侧派生行 value 改为 null，或 unit 改为 percent，静态路径仍可通过。原始行 `611–620` 也未比对 row.unit 与对应声明单位，4.0 percent 可被展示成 4.0 basis_points。两侧同步修改不会改变差异计数。建议对实际可用行核有限实值、值状态及单位／期次契约；原始行逐项对应声明，派生行对应冻结公式。非 current 的 null 缺口应继续允许。以上为静态反例，未由本审查运行复现。

依据：`CONTEXT.md:158` 将派生观测定义为由冻结公式和明确输入计算的“不可变标量事实”；`spec.md:111` 要求核对单位、数值和统计期，Testing 11（142 行）要求回放完整性；ADR0012 第 7 行要求可审计的质量与回归验收。完整血缘不能替代输出本身有效。

## 启发式建议：0

未发现新增实质气味。窄复审不代表新目录 120 日、真实认证或激活验收。

## 审查输入 SHA256

| 文件 | SHA256 |
|---|---|
| src/pring_cycle/context_replay_scope.py | `e5bd3b7325d4e01ee7a8a917b50621e89b59f7a50eaf8ca8f0aa881cc6f319b9` |
| src/pring_cycle/model_evaluation.py | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| src/pring_cycle/model_outputs.py | `cd4af58b6b496a211d05e396e6932f485eddcf7eb9ea0347dba9aae76889eb21` |
| tests/models/test_candidate_admission.py | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| tests/models/test_candidate_replay.py | `de80f7ee8994e58cb7e00e8ed813214363c0a73bfff3f86f6ffcea3d11b7d4b7` |
