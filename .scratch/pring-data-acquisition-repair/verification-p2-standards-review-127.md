# Standards 127

基点及 HEAD：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`；提交列表为空。只读五文件增量，未运行应用或测试，125 保留。

**原 output_downgrade 问题已关闭；剩余硬问题 1；气味 0。**

中：`context_replay_scope.py:84–87` 新增输出变更条件遍历全部已知公式，未限两侧实际配置。两侧均禁用 credit_impulse、仅修改 CN_CREDIT_IMPULSE 输出定义时，仍将该公式加入 required_formulas，进而要求 P2 GDP 认证与覆盖，给未运行公式新增硬门。应先限于两侧已配置公式的并集，再按输入／输出变化选取。

依据：规格 `spec.md:107` 不给缺源 P2 增加硬门；`124` 要求绑定冻结公式，ADR0012 要求按固定模型比较。既有公开测试 `test_context_model_certification.py:17–42` 明确禁用公式无需 GDP；本反例仅为静态判断，未运行复现。

UST 新正例保留比较版40bp、候选仅派生待认证及两侧原始父项采用。未弱化来源合同；本复审不代表真实认证、120日或激活验收。

## 输入 SHA256

| 文件 | SHA256 |
|---|---|
| src/pring_cycle/context_replay_scope.py | `7260e080dc51ab116f59e13d9d21c4ddde39e852e9abef97bae9733df75c8287` |
| src/pring_cycle/model_evaluation.py | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| src/pring_cycle/model_outputs.py | `0010cd10184d61dd91a39282b1fc1801ff575805637d4e40c6a6ba995e4210c0` |
| tests/models/test_candidate_admission.py | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| tests/models/test_candidate_replay.py | `198cb14bbf64ee869bcdd435ea344010c6268fe942187840897664fbd7e91c9e` |
