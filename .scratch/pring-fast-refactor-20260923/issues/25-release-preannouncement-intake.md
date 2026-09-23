# 25: 发布预告接入

**What to build:** 推算发布时点优先采用发布预告：TuShare `cn_schedule` → 官方日程页解析器 → WebSearch 取得的白名单官方日程页（须经解析器解析）；都取不到时回落到统计期末后第 N 个交易日推算，不记缺口。

**Blocked by:** 13, 19

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 经公开入口断言：有 `cn_schedule` 预告时按预告日期判定时效
- [ ] `cn_schedule` 缺失时使用官方日程页解析结果
- [ ] 非白名单或未解析的预告被丢弃并回落推算，不产生缺口
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
