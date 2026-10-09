# 积压票分流（2026-10-09 起）

这一批分流并处理各来源目录里积压的票（8 张）和第三轮验收提出的时效口径一项。回看取数第二、三轮验收（票 17、25）已完成，票 18、19 已 `wontfix`。票本身留在原来的目录里，不搬动；本目录只放规程（[goal.md](goal.md)）、收尾验收票和验收记录。

| 票 | 内容 | 状态 |
|---|---|---|
| [run-findings-20260928/11](../run-findings-20260928/issues/11-tests-reach-network.md) | 测试仍会真实访问外网（实际已实施，待核验关闭） | 待分流 |
| [run-findings-20261002/03](../run-findings-20261002/issues/03-czce-warrant-ssl-failures.md) | 郑商所仓单 SSL 失败 | 待分流 |
| [run-findings-20261002/04](../run-findings-20261002/issues/04-czce-acquisition-time-invalid.md) | 郑商所 `acquisition_time_invalid`（时钟回跳；CF 失败连带 TA） | 待分流 |
| [run-findings-20261002/05](../run-findings-20261002/issues/05-rejected-candidate-overrides-held-target.md) | 已取得的目标期被旧候选改判为"检索未通过" | 待分流 |
| [run-findings-20261002/11](../run-findings-20261002/issues/11-first-retrieval-plan-before-run-calendar.md) | 首次补缺规划在装入运行日历之前 | 待分流 |
| [run-findings-20261002/12](../run-findings-20261002/issues/12-scheduler-skips-only-weekends.md) | 盘后调度只排除周末 | 待分流 |
| [lookback/24](../lookback-fetch-gaps-20261008/issues/24-test-feedback-too-slow.md) | 测试反馈过慢（先诊断） | 待分流 |
| [lookback/26](../lookback-fetch-gaps-20261008/issues/26-ai-websearch-claims-lack-subject-context.md) | AI WebSearch 原话缺标题与主语分句 | 待分流 |
| 时效口径（[第三轮验收第五节](../lookback-fetch-gaps-20261008/acceptance-20261009-round3.md)） | 历史目标日重跑时时效按运行截止点判定 | 待分流（将开 lookback/27） |
| [01](issues/01-acceptance.md) | 收尾验收（阶段 3 创建） | — |

**下一步**：以 `/goal` 启动 goal.md（2026-10-09 已启动）。本批完成后回到界面重规划主线（[decisions.md](../ui-replan-20261003/decisions.md)）。
