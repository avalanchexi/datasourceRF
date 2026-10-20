# P2 增量 Spec 审查 110

2026-09-10。固定基点及 HEAD 均为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，提交列表为空；按授权审查指定五文件未提交 diff，仅关注 P2 必需依赖闭包及消费者。未运行应用、测试、WSL、SQL 或网络。

**发现 2 项错误实现，其中第 1 项与 Standards 已报告问题重复；独立新增 1 项。** 以下为源码审查，尚未由本代理运行反例。

1. **实际采用的可选点失去质量检查。** [model_outputs.py:551](../../src/pring_cycle/model_outputs.py#L551)使 optional 的 `required=False`，连同 [668 行](../../src/pring_cycle/model_outputs.py#L668)的 certification、quality、reported_value 检查一起跳过。即使该点列入实际采用 ID，只要值、单位和时间等基础结构相容，错误质量/认证状态仍可通过。应只免除“必须非空”，继续核对实际采用点；不可把全部诊断点改成必需。规格依据：[实施 17](spec.md#L107)“缺许可或无可靠来源者保留明确缺口”；[Testing 6](spec.md#L137)“错标识、错单位、错统计期、少成员、重复输入、矛盾修订、截断和未知时间必须有负例”。

2. **空来源可伪装可用 P2 输出。** [495 行](../../src/pring_cycle/model_outputs.py#L495)只验证国际背景为列表；[518 行](../../src/pring_cycle/model_outputs.py#L518)没有将其 current/available 行与来源快照关联。以新增两日合法输出为起点，保持 UST `source_inputs=[]`，两侧同改 UST 为数值/current 并添加孤立采用 ID，差异数不变；空列表跳过点检查，仍缺拒绝路径。仅修第 1 项不能覆盖此例。应验证可用行及其父项的真实对应，保留 unavailable 诊断；不能要求所有采用 ID 都属于本次 source scope，因为合法核心日历 ID 可在范围外。规格依据：[Testing 3](spec.md#L134)“新增成功例必须能读回真实来源声明、原件、选值与投影关联”。

没有发现额外范围扩张。[依赖闭包](../../src/pring_cycle/context_replay_scope.py#L87)仍纳入 P1 信用脉冲的 GDP；新目录 [preflight](../../tests/models/test_candidate_admission.py#L151)和[缺 GDP/P1 例](../../tests/models/test_candidate_admission.py#L918)保留完整目录及公式。两日 legacy 组件例只覆盖局部 PUBLIC/保存契约，未冒充规格实施 34–35 的真实完整候选、120 日或激活验收。

读取快照：`context_replay_scope.py` 4846 bytes / `e5bd3b7325d4e01ee7a8a917b50621e89b59f7a50eaf8ca8f0aa881cc6f319b9`；`model_evaluation.py` 50026 / `f66cd964bf0687c5ca4d637ff3827a02da0859fd561441a026ba604ccc0d7cb4`；`model_outputs.py` 26890 / `7120de4aed2f92db7faca31aa0178f28685a0af6cf90f8ce691b86e3314ccef9`。后续修复不回写本轮指纹。
