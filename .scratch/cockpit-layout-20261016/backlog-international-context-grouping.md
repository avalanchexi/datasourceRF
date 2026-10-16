# 积压：Worker 把全部 P2 指标装进 international_context

**Status:** needs-triage

Worker 生成上下文投影时，`international_context` 收录所有 `priority == "P2"` 的指标，不看是否海外或汇率，所以 GDP（8 个产业 × 口径行）与中债 030 也在其中；页面标题却是"海外与汇率"。布局精简批次在页面端用明确名单筛选（票 01），未改 Worker。待分流：是否在 Worker 侧按领域分组（需投影结构变化与新模型版本评估）。证据见会话 scratchpad `grill/names-facts.md` 第 3 节。
