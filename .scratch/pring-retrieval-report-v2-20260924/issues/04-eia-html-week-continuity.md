# 04: EIA HTML 周连续性：先诊断、再修复

**What to build:** 未配置 EIA key 时，EIA HTML 历史表不再因节假日等正常缺周被整表拒收；真实断档如实记为缺口。先保存真实历史表作为样本复现拒收，再改。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 保存真实历史表样本，并记录首次运行拒收的成因
- [ ] 以样本断言：节假日缺周照常取得 Brent/WTI，真实断档记为缺口
- [ ] 经公开入口断言：未配置 EIA key 的完整运行中 EIA 不再列为拒收（样本无断档时）
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
