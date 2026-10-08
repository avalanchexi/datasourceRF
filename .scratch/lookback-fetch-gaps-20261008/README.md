# 回看取数缺口（2026-10-08 起）

来源：[宏观语义票 11 验收记录](../macro-semantics-20261006/acceptance-20261008.md) 第五节与第七节。v0015 真实运行（run-4ae95443a6c4a6e63eb3）中，回看计划要求的历史期大量"计划了却没取到"，17 项计数指标中 11 项因此"未确认"。用户 2026-10-08 决定：先开 needs-triage 票，暂不实施。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-historical-periods-skipped-as-unknown-release.md) | 历史期因"发布配置未知"被静默跳过（工增、产能利用率、贷款、工具流动性、社融分项） | needs-triage |
| [02](issues/02-sf-components-ingest-all-members.md) | 社融分项未按原件全部入库 | needs-triage |
| [03](issues/03-sf-stock-yoy-fallback-and-news-rules.md) | 社融存量同比的补缺路径与资讯规则 | needs-triage |
| [04](issues/04-gdp-official-fallback-members-and-yoy-semantics.md) | GDP 官方回退成员集合为空，同比期语义被拒 | needs-triage |
| [05](issues/05-nbs-pboc-historical-listing-paging.md) | 统计局与人民银行历史列表只读首页或翻页有上限（含 OMO 100 个交易日） | needs-triage |
| [06](issues/06-acquisition-row-count-overwritten.md) | 取数回执行数被归一化行数覆盖 | needs-triage |
| [07](issues/07-cny-central-parity-member-contract.md) | 人民币中间价成员契约缺失 | needs-triage |
| [08](issues/08-pre-window-lookback-claims-untraceable.md) | 窗口前回看数据清理后无法追溯原声明 | needs-triage |

相关既有票：[真实运行发现 06](../run-findings-20261002/issues/06-tushare-price-delivery-january-ppi.md)（CPI/PPI 一月字段致整批拒收）、[真实运行发现 10](../run-findings-20261002/issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md)。DR007 09-30 单日 0 行属上游，不另开票。
