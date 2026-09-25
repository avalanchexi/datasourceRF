# 2026-09-26 真实运行遗留分流

来源：[gap-sources 票 09](../gap-sources-20260925/issues/09-endpoint-suite-and-real-run.md) 末尾的遗留（真实完整运行 run-64209ab01ac75439cc8c，目标日 2026-09-24）。核实材料在 [research/](research/)。

| 票 | 问题 | 建议 | 状态 |
|---|---|---|---|
| [01](issues/01-warrant-family-isolation.md) | 一个品种的坏行让仓单八个品种的历史一起被拒（本轮 162 张回执全拒，各品种只持有 9/24） | 最先做，02 依赖它 | done（待真实运行验证）|
| [02](issues/02-pta-warrant-history-source.md) | PTA（及郑棉）TuShare 仓单结构畸形或偏低：郑商所品种改取交易所日报 | 改取郑商所官网日报（ADR-0032），依赖 01 | ready-for-agent |
| [03](issues/03-tool-liquidity-overnight-reverse-repo.md) | 工具流动性从未持有：央行行名改为“隔夜、7天期逆回购”，契约不认 | 同一成员、序列连续 | ready-for-agent |
| [04](issues/04-omo-sibling-notice-rejection.md) | 同日香港央票公告被设计内跳过，却显示为拒收提示 | 回执记为已跳过 | ready-for-agent |
| [05](issues/05-vix-lag-grace.md) | VIX 宽限只观察过两次 | 攒观察 | needs-info |
