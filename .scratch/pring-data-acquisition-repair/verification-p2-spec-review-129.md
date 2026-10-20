# P2 Spec 复审 129

基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`；仅静态窄复审，未运行应用或测试。

**128 所述误引父项硬门已关闭；新增实质发现 0。** [scope:79](../../src/pring_cycle/context_replay_scope.py#L79)先限定双方配置公式并集，再按输入/输出变化触发；双方禁用 credit 时不引入 GDP，任一侧启用仍保留该公式及父项。125 的输出降级修复未撤回。

[公开反例:1028](../../tests/models/test_candidate_replay.py#L1028)仅改变禁用输出定义，调用公开回放及输出校验，要求零缺口、空公式/来源范围、双方 disabled_by_model；没有修改公式算法、认证或激活门。符合[领域规则](../../CONTEXT.md#L56)“固定……派生公式的具体版本”及[实施34](spec.md#L124)“旧值只能以明确旧版本身份重现”。该 legacy 组件不替代完整61/42/8正式候选、真实120日或激活验收。其余三文件指纹与127一致；运行与全套结果由主线记录。

| 当前文件 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/context_replay_scope.py` | 5468 | `0cf789d2c9332a277b530a11fca77486f22139886d68bf76fa00919e3c18d7d0` |
| `src/pring_cycle/model_evaluation.py` | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| `src/pring_cycle/model_outputs.py` | 34620 | `0010cd10184d61dd91a39282b1fc1801ff575805637d4e40c6a6ba995e4210c0` |
| `tests/models/test_candidate_admission.py` | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| `tests/models/test_candidate_replay.py` | 58359 | `7b2407bc3d6ed72a2476df9ac54dc634083c518a42f638aa3d75bf2b84d8dfcc` |
