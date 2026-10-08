# 回看取数缺口（2026-10-08 起）

来源：[宏观语义票 11 验收记录](../macro-semantics-20261006/acceptance-20261008.md) 第五节与第七节。v0015 真实运行（run-4ae95443a6c4a6e63eb3）中，回看计划要求的历史期大量"计划了却没取到"，17 项计数指标中 11 项因此"未确认"。

**分流**（2026-10-08）：Codex 只读调查 + 主会话核验，见 [triage-20261008.md](triage-20261008.md)。用户决定：05 按日期区间扫描、每站每轮 50 页上限、触顶转搜索；08 保留仍被投影引用的来源声明至投影过期。run-findings 10 并入 02。**执行**：主 agent 调度、每票一个子代理，规程见 [goal.md](goal.md)。

| 序 | 票 | 内容 | 状态 |
|---|---|---|---|
| 1 | [06](issues/06-acquisition-row-count-overwritten.md) | 回执行数口径混淆：分记来源记录数、规范化标量数、入库结果 | done |
| 2 | [run-findings 06](../run-findings-20261002/issues/06-tushare-price-delivery-january-ppi.md) | 一月 PPI 累计字段致 CPI/PPI 整批拒收 | done |
| 3 | [07](issues/07-cny-central-parity-member-contract.md) | 人民币中间价成员契约（已入库但选不出） | done |
| 4 | [02](issues/02-sf-components-ingest-all-members.md) | 同一原件全部成员入库（社融分项；并入 run-findings 10 OMO 利率） | done |
| 5 | [01](issues/01-historical-periods-skipped-as-unknown-release.md) | 历史期被"只取最新"门禁判为未知而跳过 | ready-for-agent |
| 6 | [04](issues/04-gdp-official-fallback-members-and-yoy-semantics.md) | GDP 官方回退成员集合为空（TuShare 同比保持拒收） | ready-for-agent |
| 7 | [03](issues/03-sf-stock-yoy-fallback-and-news-rules.md) | 社融存量同比补缺适配器与资讯规则 | ready-for-agent |
| 8 | [05](issues/05-nbs-pboc-historical-listing-paging.md) | 统计局与人民银行历史列表按日期区间扫描 | ready-for-agent |
| 9 | [08](issues/08-pre-window-lookback-claims-untraceable.md) | 保留被投影引用的窗口前声明 | ready-for-agent |
| 10 | [09](issues/09-real-run-acceptance.md) | 全套测试与真实运行验收 | ready-for-agent（阻塞于以上全部） |

**下一步**：序 5，[01](issues/01-historical-periods-skipped-as-unknown-release.md)（历史期被"只取最新"门禁判为未知而跳过）。

相关：[run-findings 10](../run-findings-20261002/issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md)（duplicate，并入 02）。DR007 09-30 单日 0 行属上游，不另开票。
