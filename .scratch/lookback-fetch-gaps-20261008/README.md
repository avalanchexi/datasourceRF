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
| 11 | [11](issues/11-runs-get-rereads-all-attempts.md) | `runs.get` 重读全部检索尝试（平方增长） | done（第二轮；方案 B，657fffd） |
| 12 | [09](issues/09-real-run-acceptance.md) | 全套测试与真实运行验收 | done（[验收记录](acceptance-20261009.md)：全套 2107 通过；真实运行模型输入缺失 168→10，17 项完整 6→16） |
| 13 | [12](issues/12-judging-calendar-drops-known-holidays.md) | 截止日超出已存日历时判定日历丢弃已知休市日（既有缺陷，09 发现） | done（第二轮，2a3935f） |
| 14 | [13](issues/13-capacity-utilization-title-and-path.md) | 产能利用率标题含"规模以上"漏识别；`/zwfwck/sjfb/` 不在白名单 | done（第二轮，78ba0ea） |
| 15 | [14](issues/14-sf-stock-yoy-2025-separate-report.md) | 2025 年社融单独报告未识别；AI 候选只留存量金额 | done（第二轮，58dddd7） |
| 16 | [15](issues/15-news-rule-city-level-industrial-va.md) | 资讯规则把地方口径工业增加值当全国 | done（第二轮，0effd27） |
| 17 | [16](issues/16-derived-coverage-flag-counts-whole-family.md) | 派生指标覆盖标志按整个家族判断（既有问题） | done（第二轮，f322e25；OMO 按用户决定补齐） |
| 18 | [17](issues/17-round2-acceptance.md) | 第二轮全套测试与真实运行验收 | done（[验收记录](acceptance-20261009-round2.md)：全套 2158 通过；真实运行模型输入缺失 10→7，17 项完整 16→17） |
| 19 | [18](issues/18-loan-stock-v0001-coverage-flag.md) | 贷款存量 v0001 覆盖标志恒为 false（既有，16 发现） | wontfix（2026-10-09 分流：只影响内置目录审计标志） |
| 20 | [19](issues/19-runs-get-rereads-ledger.md) | 读运行时每次全读检索账本（11 发现） | wontfix（2026-10-09 分流：剩 0.33 秒／50 秒，改动会移动快照时点） |
| 21 | [20](issues/20-pre-fix-local-news-claims-still-candidates.md) | 资讯从严主语规则＋候选列表与选值动态复核（只要全国口径） | done（第三轮线 A；5753 篇正文前后比对零增减；3 条旧地方声明退出候选，`c8dcb77e` 交票 23） |
| 22 | [22](issues/22-news-claim-subject-context.md) | 资讯声明入库保存主语上下文与页面标题（迁移加字段，复核使用） | done（第三轮线 A；迁移 0033 加 `subject`，标题列 0030 已有；用户决定方案 A，新旧行一律按已存标题复核，c8dcb77e 退出候选，选值不变；遗留：AI WebSearch 无标题与段落） |
| 23 | [23](issues/23-suspect-legacy-news-claim-refetch.md) | 嫌疑旧资讯声明（`c8dcb77e…` 广东 6.9）定点重取并判定 | ready-for-agent（第三轮线 A，阻塞于 20、22） |
| 24 | [21](issues/21-capacity-search-fallback-chain-unverified.md) | 产能利用率检索补救经 `/zwfwck/sjfb/` 的离线端到端用例（只补测试） | done（`test_capacity_search_rescue.py` 两例：列表缺稿时 Tavily 候选补齐 2026-Q1 73.6／-0.5，同一原件给其他季度按期次拒收；未改生产代码） |
| 25 | [24](issues/24-test-feedback-too-slow.md) | 测试反馈过慢（受影响测试 15–70 分钟） | needs-triage（不进第三轮） |
| 26 | [25](issues/25-round3-acceptance.md) | 第三轮全套测试与真实运行验收 | ready-for-agent（阻塞于 20–23） |

**下一步**：第一轮（序 1–12）与第二轮（序 13–18，票 11–17）均已完成，验收见 [acceptance-20261009.md](acceptance-20261009.md) 与 [acceptance-20261009-round2.md](acceptance-20261009-round2.md)：17 项计数指标按主要成员缺期计已全部完整，最终计划只剩 7 个上游、时效或凭据类缺口。遗留票 18、19 与 17 新开的票 20、21（序 19–22）均 needs-triage，待用户分流；其中只有票 20 可能影响选值（某期没有全国值时，旧地方口径声明仍可能被选中），其余三张只涉及审计标志、读取耗时或测试覆盖。

相关：[run-findings 10](../run-findings-20261002/issues/10-omo-rate-dropped-when-notice-ingested-for-amount.md)（duplicate，并入 02）。DR007 09-30 单日 0 行属上游，不另开票（2026-10-09 验收运行时已回填，取到 1.3665）。

**第二轮**（2026-10-09 规划）：遗留票 11–16 与第 17 张验收，见 [goal-round2.md](goal-round2.md)；以 `/goal` 启动。

**第三轮**（2026-10-09 grilling 分流）：票 20、22、23、21 实施，18、19 `wontfix`，24 待分流，25 验收，见 [goal-round3.md](goal-round3.md)。
