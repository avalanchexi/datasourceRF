# 模型规则补全与真实验证（2026-10-11）

- [interview.md](interview.md)：访谈决定
- [spec.md](spec.md)：规格
- [codex-facts-20261011.md](codex-facts-20261011.md)：取证

| 票 | 内容 | Blocked by | 状态 |
|---|---|---|---|
| [01](issues/01-window-core-state-every-day.md) | 窗口内每天都有核心状态 | — | done |
| [02](issues/02-last-confirmed-stage-backfill.md) | 回溯找出上一确认阶段 | 01 | done |
| [03](issues/03-scheduled-run-t-plus-1.md) | 盘后调度改为 T+1 | — | done |
| [04](issues/04-audit-commodity-breadth.md) | 体检核对商品篮子分项广度 | — | done |
| [05](issues/05-audit-inventory-quadrant.md) | 体检核对库存象限 | 04 | done |
| [07](issues/07-correct-window-days-summarized-under-old-core-history.md) | 窗口内旧口径日汇总追加更正版本（2026-10-11 用户决定） | 01, 02 | done |
| [08](issues/08-correct-core-only-when-day-context-left-retention.md) | 更正日的上下文明细超出留存时只更正核心（2026-10-12 用户决定，票 06 第一次真实运行发现） | 07 | ready-for-agent |
| [06](issues/06-acceptance.md) | 收尾验收（[中期记录](acceptance-20261012.md)：第一次真实运行已完成；85 个更正日失败，转票 08 后重验） | 01–05、07、08 | claimed |

前沿：06 的第一次真实运行已记录；等 08 合入后做第二次真实运行（记录第八节）。
