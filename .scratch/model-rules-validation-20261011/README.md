# 模型规则补全与真实验证（2026-10-11）

- [interview.md](interview.md)：访谈决定
- [spec.md](spec.md)：规格
- [codex-facts-20261011.md](codex-facts-20261011.md)：取证

| 票 | 内容 | Blocked by | 状态 |
|---|---|---|---|
| [01](issues/01-window-core-state-every-day.md) | 窗口内每天都有核心状态 | — | ready-for-agent |
| [02](issues/02-last-confirmed-stage-backfill.md) | 回溯找出上一确认阶段 | 01 | ready-for-agent |
| [03](issues/03-scheduled-run-t-plus-1.md) | 盘后调度改为 T+1 | — | done |
| [04](issues/04-audit-commodity-breadth.md) | 体检核对商品篮子分项广度 | — | done |
| [05](issues/05-audit-inventory-quadrant.md) | 体检核对库存象限 | 04 | ready-for-agent |
| [06](issues/06-acceptance.md) | 收尾验收 | 01–05 | blocked |

前沿：01 可以立即开始；03、04 已完成，05 可以开始。
