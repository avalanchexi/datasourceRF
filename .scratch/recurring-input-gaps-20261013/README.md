# 反复出现的输入缺口（2026-10-13）

规格：[spec.md](spec.md)。取证：[codex-recurrence-20261013.md](codex-recurrence-20261013.md)。相关决定已写入 CONTEXT.md（数据异常、目标日汇总）与 ADR-0041 2026-10-13 补写。

| 票 | 内容 | 前置 | 状态 |
|---|---|---|---|
| [01](issues/01-target-day-uses-next-morning-data.md) | T+1 用上次日早上公开的目标日数据；调度改 09:30 | — | ready-for-agent |
| [02](issues/02-freshness-current-when-due-period-held.md) | 证据时效按词表判定 | — | done |
| [03](issues/03-audit-upstream-unpublished-category.md) | 体检对齐新口径并新增“上游未发布”分类 | 01 | ready-for-agent |
| [04](issues/04-warrant-known-historical-gaps.md) | 仓单历史缺口核实并单列 | 03 | ready-for-agent |
| [05](issues/05-acceptance.md) | 收尾验收 | 01–04、残余票 01 | ready-for-agent |
