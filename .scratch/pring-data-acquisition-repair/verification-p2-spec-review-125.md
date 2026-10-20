# P2 Spec 复审 125

基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；只读五文件增量，未运行应用或测试。

**120 遗留已关闭，当前仍有 1 项错误实现。** 当前行已按 cutoff/既有鲜度规则验证，合法前期方向输入保留。

仅候选利差输出降为 awaiting、父项及公式不变时，[scope:84](../../src/pring_cycle/context_replay_scope.py#L84)只按公式输入找变化，遗漏输出变化；公式集合为空。[行校验:561](../../src/pring_cycle/model_outputs.py#L561)遂将比较侧合法 current 利差当原始行，因无父项快照而拒绝。当前[fixture:695](../../tests/models/test_candidate_replay.py#L695)同时改父项来源，未覆盖此分支。应把输出定义变化纳入公式及父项范围。

依据[实施17](spec.md#L107)“P2 缺口不改变正式阶段”，及[票19](issues/19-immutable-candidate-catalog.md#L21)“受限/未认证 P2 保持合规缺口”。限已有 legacy 公开组件；新目录包变化触发全量范围时不受此窄分支影响。静态未复现，无其他扩张；不替代真实完整候选120日或激活验收。

| 当前文件 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/context_replay_scope.py` | 5306 | `5db4555f03d008bbdc89771d75ecce382541718869311719b6d8da517c3b855d` |
| `src/pring_cycle/model_evaluation.py` | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| `src/pring_cycle/model_outputs.py` | 34620 | `0010cd10184d61dd91a39282b1fc1801ff575805637d4e40c6a6ba995e4210c0` |
| `tests/models/test_candidate_admission.py` | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| `tests/models/test_candidate_replay.py` | 55779 | `18bc8198be724678ded8f8cb7dbcbed2d6aad156400480fad255aecbe10aea52` |
