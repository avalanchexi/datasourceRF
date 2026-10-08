# 回看取数缺口（2026-10-08 起）

来源：[宏观语义票 11 验收记录](../macro-semantics-20261006/acceptance-20261008.md) 第五节与第七节。v0015 真实运行（run-4ae95443a6c4a6e63eb3）中，回看计划要求的历史期大量"计划了却没取到"，17 项计数指标中 11 项因此"未确认"。

**分流**（2026-10-08）：Codex 只读调查 + 主会话核验，见 [triage-20261008.md](triage-20261008.md)。用户决定：05 按日期区间扫描、每站每轮 50 页上限、触顶转搜索；08 保留仍被投影引用的来源声明至投影过期。run-findings 10 并入 02。**执行**：主 agent 调度、每票一个子代理，规程见 [goal.md](goal.md)。

| 序 | 票 | 内容 | 状态 |
|---|---|---|---|
| 1 | [06](issues/06-acquisition-row-count-overwritten.md) | 回执行数口径混淆：分记来源记录数、规范化标量数、入库结果 | done |
| 2 | [run-findings 06](../run-findings-20261002/issues/06-tushare-price-delivery-january-ppi.md) | 一月 PPI 累计字段致 CPI/PPI 整批拒收 | done |
| 3 | [07](issues/07-cny-central-parity-member-contract.md) | 人民币中间价成员契约（已入库但选不出） | done |
| 4 | [02](issues/02-sf-components-ingest-all-members.md) | 同一原件全部成员入库（社融分项；并入 run-findings 10 OMO 利率） | done |
| 5 | [01](issues/01-historical-periods-skipped-as-unknown-release.md) | 历史期被"只取最新"门禁判为未知而跳过 | done |
| 6 | [04](issues/04-gdp-official-fallback-members-and-yoy-semantics.md) | GDP 官方回退成员集合为空（TuShare 同比保持拒收） | done |
| 7 | [03](issues/03-sf-stock-yoy-fallback-and-news-rules.md) | 社融存量同比补缺适配器与资讯规则 | done |
| 8 | [05](issues/05-nbs-pboc-historical-listing-paging.md) | 统计局与人民银行历史列表按日期区间扫描 | done |
| 9 | [08](issues/08-pre-window-lookback-claims-untraceable.md) | 保留被投影引用的窗口前声明 | done |
| 10 | [10](issues/10-l01-regression-core-preheat-and-test-time.md) | L01 后回归：同日第三次运行三核心预热未读入；测试变慢 | done |
| 11 | [11](issues/11-runs-get-rereads-all-attempts.md) | `runs.get` 重读全部检索尝试（平方增长） | needs-triage（不阻塞验收） |
| 12 | [09](issues/09-real-run-acceptance.md) | 全套测试与真实运行验收 | done（[验收记录](acceptance-20261009.md)：全套 2107 通过；真实运行模型输入缺失 168→10，17 项完整 6→16） |
| 13 | [12](issues/12-judging-calendar-drops-known-holidays.md) | 截止日超出已存日历时判定日历丢弃已知休市日（既有缺陷，09 发现） | needs-triage |
| 14 | [13](issues/13-capacity-utilization-title-and-path.md) | 产能利用率标题含"规模以上"漏识别；`/zwfwck/sjfb/` 不在白名单 | needs-triage |
| 15 | [14](issues/14-sf-stock-yoy-2025-separate-report.md) | 2025 年社融单独报告未识别；AI 候选只留存量金额 | needs-triage |
| 16 | [15](issues/15-news-rule-city-level-industrial-va.md) | 资讯规则把地方口径工业增加值当全国 | needs-triage |
| 17 | [16](issues/16-derived-coverage-flag-counts-whole-family.md) | 派生指标覆盖标志按整个家族判断（既有问题） | needs-triage |

**下一步**：本批（序 1–12）已完成，验收见 [acceptance-20261009.md](acceptance-20261009.md)。票 11 及 09 新开的票 12–16（序 13–17）待用户分流；其中票 13（产能利用率 2026Q1，17 项中唯一仍缺的主要成员）与票 12（日历误判使日频指标显示陈旧）对读法影响最大。

相关：[run-findings 10](../run-findings-20261002/issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md)（duplicate，并入 02）。DR007 09-30 单日 0 行属上游，不另开票（2026-10-09 验收运行时已回填，取到 1.3665）。

**第二轮**（2026-10-09 规划）：遗留票 11–16 与第 17 张验收，见 [goal-round2.md](goal-round2.md)；以 `/goal` 启动。
