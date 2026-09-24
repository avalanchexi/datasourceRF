# 02: 交易日历不再列入缺口

**What to build:** 交易日历作为运维证据，不参与时效判定，完整运行的缺口清单里不再出现 P0 交易日历缺失。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 经公开入口断言：完整运行后缺口清单不含交易日历
- [ ] 批次时效记录不再为交易日历判定状态
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
