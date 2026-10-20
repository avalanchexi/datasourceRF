Status: static-test-review-passed
Axis: Spec
Date: 2026-09-10
Scope: 159-160 common dependency test increment

**新增确定问题 0。** 本次只审 [test_capacity_q1_mapping_still_requires_common_and_legacy_dependencies](../../tests/models/test_candidate_admission.py#L6405)，没有重审或修改生产代码。

[工程边界 L50、L55–57](capacity-q1-implementation-boundary.md#L50)要求包/review/定义的完整绑定与消费者复验。本测试先从公开准入、入库和真实查询取得合法三成员，再核对实际采用集合，[L6451–6493](../../tests/models/test_candidate_admission.py#L6451)。随后七参数各破坏一个明确依赖；[L6494–6511](../../tests/models/test_candidate_admission.py#L6494)同时断言检索缺口、ytd 不再被模型采用、历史证据身份仍保留，符合 [L80](capacity-q1-implementation-boundary.md#L80)，不只断言接口无异常。

request/package/review/history/fields 五例明确将映射改成 typed 引用。history 普通附件证明共同依赖不局限于 semantics/fields；fields 普通附件位于合法映射引用之后，能捕获找到映射便提前返回的绕过。这些附件使用独立内容/hash，故负例改变的依赖清楚。

**legacy 两例的准确范围是新服务准入目录内的未分类映射引用及其 basis。** [L6422–6430](../../tests/models/test_candidate_admission.py#L6422)对它们保留原 source_reference，但仍经当前准入服务产生模型；这两例能检查当前选中未分类映射/依据损坏仍阻断，不能冒充“旧无 source_mapping_reference_contract 目录”的兼容性测试。

只读核实 [159 日志](verification-capacity-role-green-159.txt)为 9 通过、136.64 秒，[终态](verification-capacity-terminal-159.json)前验/测试/后验均退出 0。160 的 Ruff、格式及 mypy 日志已成功（mypy 8 文件），但本审查未读取七参数测试的运行终态，不能据此称 160 回归通过。未执行测试、安装或修改源码；本结论不涉及真实认证、完整模型或 120 日验收。

输入核验：七生产文件与冻结 158 完全一致，八文件当前字节均匹配 [冻结 160](verification-capacity-inputs-160.json)。本次测试文件为 378843 字节，SHA-256 `f448d697cbe32bc430b23929135c7040d5ef7675f6dabb5386b65d18bc2788e6`；七生产 SHA 仍为 [158 报告](verification-capacity-spec-review-158.md)逐项列示值。
