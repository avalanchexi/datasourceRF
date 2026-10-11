# 模型规则补全与真实验证（2026-10-11）

- [interview.md](interview.md)：访谈决定
- [spec.md](spec.md)：规格
- [codex-facts-20261011.md](codex-facts-20261011.md)：取证

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-core-lookback-260.md) | 三核心回看约 260 点 | ready-for-agent |
| [02](issues/02-last-confirmed-stage-backfill.md) | 上一确认阶段按需回溯，最长 5 年 | ready-for-agent（阻塞于 01） |
| [03](issues/03-scheduled-run-t-plus-1.md) | 盘后调度 T+1，9:00 识别上一交易日 | ready-for-agent |
| [04](issues/04-audit-breadth-and-inventory.md) | 规则文档化；体检补广度与库存象限 | ready-for-agent |
| [05](issues/05-acceptance.md) | 收尾验收 | blocked |

并行：01→02 同一条线（核心取数）；03（调度）、04（体检脚本与文档）可以与之并行。
