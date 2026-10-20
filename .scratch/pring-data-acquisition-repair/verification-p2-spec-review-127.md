# P2 Spec 复审 127

基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；本轮仅静态窄复审，未运行应用或测试。

**125 遗留已关闭；新增实质发现 0。** [scope:84](../../src/pring_cycle/context_replay_scope.py#L84)已将输出定义变化纳入公式及父项范围。[公开组件:696](../../tests/models/test_candidate_replay.py#L696)保持父项、来源、公式及包不变，仅候选输出待认证；[断言:945](../../tests/models/test_candidate_replay.py#L945)要求比较侧40bp、双方原始父项仍采用、候选仅利差待认证，直接覆盖原遗漏。

符合[实施17](spec.md#L107)“P2 缺口不改变正式阶段”及[票19](issues/19-immutable-candidate-catalog.md#L20)“受限/未认证 P2 保持合规缺口”。GDP/P1依赖硬门、当前值资格/鲜度/血缘校验与前期方向资格保持；未见新增范围扩张。其余三文件指纹与125一致。运行结果由主线记录，本审查不替代全套验证、真实完整候选120日或激活验收。

| 当前文件 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/context_replay_scope.py` | 5373 | `7260e080dc51ab116f59e13d9d21c4ddde39e852e9abef97bae9733df75c8287` |
| `src/pring_cycle/model_evaluation.py` | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| `src/pring_cycle/model_outputs.py` | 34620 | `0010cd10184d61dd91a39282b1fc1801ff575805637d4e40c6a6ba995e4210c0` |
| `tests/models/test_candidate_admission.py` | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| `tests/models/test_candidate_replay.py` | 56603 | `198cb14bbf64ee869bcdd435ea344010c6268fe942187840897664fbd7e91c9e` |
