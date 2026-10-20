# Standards 129

基点及 HEAD：`99c495a217b66d4bca9d6ceae4688ee69d4382bb`；提交列表为空。

**127 发现已关闭；剩余硬规范问题 0；新增实质气味 0。**

`context_replay_scope.py:79–89` 先取两侧已配置公式并集，再判断版本、输入和输出变化：双侧禁用不再引入 GDP/SF 依赖，单侧仍启用的公式继续进入比较范围。未新增全 P2 认证硬门，也未改变已采用证据的资格、鲜度或血缘守门。

新公开测试 `test_candidate_replay.py:1028–1066` 只改候选禁用公式的输出定义，经评价及存档校验核对空公式／来源范围和 disabled_by_model；未调用私有业务替身。符合固定模型比较、最小实际依赖与公开测试边界。

仅静态复审，未运行应用、测试、WSL、SQL 或网络；不表示真实认证、120日或激活完成。旧127报告保留。

## 输入 SHA256

| 文件 | SHA256 |
|---|---|
| src/pring_cycle/context_replay_scope.py | `0cf789d2c9332a277b530a11fca77486f22139886d68bf76fa00919e3c18d7d0` |
| src/pring_cycle/model_evaluation.py | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| src/pring_cycle/model_outputs.py | `0010cd10184d61dd91a39282b1fc1801ff575805637d4e40c6a6ba995e4210c0` |
| tests/models/test_candidate_admission.py | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| tests/models/test_candidate_replay.py | `7b2407bc3d6ed72a2476df9ac54dc634083c518a42f638aa3d75bf2b84d8dfcc` |
