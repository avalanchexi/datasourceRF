# P2 Spec 复审 120

2026-09-10；基点仍为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，仅审指定五文件未提交 P2 增量。未运行应用、测试、WSL、SQL 或网络；110/116 保留。

**116 的 2 项发现已关闭；当前另有 1 项范围内残留。** `optional_metrics` 包含受影响的 awaiting P2；原始行单位/身份与来源匹配，UST 公式检查有限数值、reported_value、空维度、同日父项、bp 单位及差值乘 100。adopted 点仍独立检查质量/认证，合法前期方向输入及范围外核心日历 ID 未被一并删除。GDP/P1 必需依赖、完整 61/42P1/8 准入例及 legacy 组件边界保持。

1. **错误实现：重标 current 可绕过陈旧采用检查。** [model_outputs.py:591](../../src/pring_cycle/model_outputs.py#L591)依据行自报 status 登记 `referenced_ids`，没有按截止日复核鲜度；[663 行](../../src/pring_cycle/model_outputs.py#L663)仅比较集合。沿 [adopted_stale 用例](../../tests/models/test_candidate_replay.py#L779)，保持 2025-08-28 两父项的真实值、单位、日期、声明和质量，在 2026-08-28 输出两侧把两个原始 UST 行由 stale 改为 current，再加入这两个采用 ID；差异数不变、来源匹配仍成立，新集合检查便缺少拒绝路径。无需伪造新原件或改变利差。当前测试仅追加 ID，未重标行状态。

   依据[票 14](issues/14-p2-availability.md#L19)原句：“未发布、未授权、未认证、源失败和陈旧分别体现在运行状态与只读投影；已有有效值保留真实期次。” [规格实施 17](spec.md#L107)允许明确缺口，不允许将其改为可采用当前值。最小反例是 `adopted_stale` 加 status 篡改；最小修复应按同一 cutoff 和已有[期次鲜度规则](../../src/pring_cycle/context_projection.py#L1686)核原始/派生 current 状态，不另选新日历阈值，也不能拒绝合法前期方向依赖。这是静态审查，未由本代理运行复现。

没有发现其他范围扩张；本报告不把 19 场景或两日组件替代真实完整新目录 120 日及激活验收。

读取快照：

| 文件 | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/context_replay_scope.py` | 5271 | `9c81258a54b88c856548a196fdf9a80ab19a4fa491a7ba90fd27b71ce6c8a886` |
| `src/pring_cycle/model_evaluation.py` | 50010 | `ef8dc6d4f1b6c5257efafb839255986ab8dcf26f0c1b1423be4bfca0d860f2f1` |
| `src/pring_cycle/model_outputs.py` | 33807 | `ab80bee20cd290919a270bac274cca6b019623119a5a9659cd046e9a5331d5fd` |
| `tests/models/test_candidate_admission.py` | 334953 | `e4533108057fd2b19fdb9b8c327ba183735bb5f123644351e30ee196a3e2b111` |
| `tests/models/test_candidate_replay.py` | 52897 | `4f2403251f944a20c1bafd83f5bffb8b591117a57efe70523580776813bae36c` |
