# 01: 预重构：统一检索登记处

**What to build:** 把分散的检索登记（官方解析器家族、LPR、中证核心、P2 宽松主机）收到同一登记处，并提供“可检索缺口”判定（指标属于登记解析器家族或登记了宽松主机）。对外行为不变，为后续各票铺路。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 各来源的主机、指标集与解析入口从同一登记处读取，原有调用方改用它
- [ ] 提供“可检索缺口”判定，派生指标与 NHII 判为不可检索
- [ ] 现有测试不改断言即全部通过（行为不变）
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
