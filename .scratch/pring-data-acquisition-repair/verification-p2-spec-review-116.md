# P2 Spec 复审 116

2026-09-10；固定基点 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，审指定五文件未提交增量。只读；未运行应用、测试、WSL、SQL 或网络，旧 110 保留。

**原发现 1 已关闭；原发现 2 部分关闭。当前仍有 2 项：1 项原范围残留、1 项新增。** 已认证原始行的身份/值/维度/期次及采用关联、adopted 点质量/认证/reported_value 已补检查；以下为静态结论，未由本代理运行反例。

1. **原发现 2 残留：待认证 P2 未进入行守卫。** [model_outputs.py:558](../../src/pring_cycle/model_outputs.py#L558)以 `scope.source_metrics` 推导应有行，但 [scope:113](../../src/pring_cycle/context_replay_scope.py#L113)排除 awaiting P2。这些原始缺口行既可删除，也可改成孤立 current/available，因为 [577 行](../../src/pring_cycle/model_outputs.py#L577)直接跳过。现 missing_row 用例仅覆盖 certified UST。应从本轮受影响的 P2 定义/公式输入确定展示范围，与合格来源集合分开。依据[票 14](issues/14-p2-availability.md#L19)“未发布、未授权、未认证、源失败和陈旧分别体现在运行状态与只读投影”，以及[实施 17](spec.md#L107)“缺许可或无可靠来源者保留明确缺口”。

2. **派生结果与父项尚未一致性校验。** [585–610 行入口](../../src/pring_cycle/model_outputs.py#L585)核父项、公式版本和采用 ID 后直接结束。合法 40 bp 输出两侧同改为 400 或 None/current，保持父项与公式版本，差异数不变，仍缺拒绝路径；跨期父项、错单位同样未绑定。原始行 [611 行](../../src/pring_cycle/model_outputs.py#L611)也未核 row.unit。应按配置的 2S10S 公式核同日期父项、数值/单位及行身份，不把“有血缘”当“结果正确”。依据[实施 34](spec.md#L124)“绑定全部定义、来源认证、选择与时间规则、公式及执行指纹”；[Testing 6](spec.md#L137)要求“错标识、错单位、错统计期…必须有负例”。

未发现额外范围扩张。GDP 仍在 P1 信用脉冲依赖闭包；两项新目录公开准入例保留 61/42P1/8。legacy v3 的两日 PUBLIC 与合成 40 bp 组件例未被当成完整新目录 120 日或激活验收。

读取快照（后续修复不回写）：

| 文件 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/context_replay_scope.py` | 4846 | `e5bd3b7325d4e01ee7a8a917b50621e89b59f7a50eaf8ca8f0aa881cc6f319b9` |
| `src/pring_cycle/model_evaluation.py` | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| `src/pring_cycle/model_outputs.py` | 30940 | `cd4af58b6b496a211d05e396e6932f485eddcf7eb9ea0347dba9aae76889eb21` |
| `tests/models/test_candidate_admission.py` | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| `tests/models/test_candidate_replay.py` | 48612 | `de80f7ee8994e58cb7e00e8ed813214363c0a73bfff3f86f6ffcea3d11b7d4b7` |
