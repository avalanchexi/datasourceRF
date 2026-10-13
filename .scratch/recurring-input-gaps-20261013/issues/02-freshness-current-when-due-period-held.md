Status: ready-for-agent
Type: task
Category: bug

# 02：证据时效按词表判定

**What to build:** 持有期不早于应有期即判 current，下一期已公开但未持有不再把它降为 awaiting_release；未过宽限为 awaiting_release，已过宽限为 stale。T+1 冻结时 DR007、DR007 政策利差、公开市场操作量价、SHIBOR、人民币中间价这类当天已持有的项显示 current，报告、页面与缺口清单一致。见 [规格](../spec.md) 与 CONTEXT.md“证据时效”。

**Blocked by:** None (can start immediately)

**主要模块：** 证据时效判定及其消费者（批次时效、成员读数状态、缺口清单）。

- [ ] 持有期等于应有期、下一期已公开未持有：current
- [ ] 持有期早于应有期、未过宽限：awaiting_release；已过宽限：stale
- [ ] 消费时效标签的报告、页面与缺口清单行为一致，无连带回归
- [ ] 受影响测试与切片收尾冒烟通过

## Comments
