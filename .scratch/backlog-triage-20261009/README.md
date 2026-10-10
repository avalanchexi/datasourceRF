# 积压票分流（2026-10-09 起）

这一批分流并处理各来源目录里积压的票（8 张）和第三轮验收提出的时效口径一项。回看取数第二、三轮验收（票 17、25）已完成，票 18、19 已 `wontfix`。票本身留在原来的目录里，不搬动；本目录只放规程（[goal.md](goal.md)）、收尾验收票和验收记录。

| 票 | 内容 | 状态 |
|---|---|---|
| [run-findings-20260928/11](../run-findings-20260928/issues/11-tests-reach-network.md) | 测试仍会真实访问外网（实际已实施，待核验关闭） | done（分流核验关闭） |
| [run-findings-20261002/03](../run-findings-20261002/issues/03-czce-warrant-ssl-failures.md) | 郑商所仓单 SSL 失败 | wontfix（10-03 后零复现） |
| [run-findings-20261002/04](../run-findings-20261002/issues/04-czce-acquisition-time-invalid.md) | 郑商所 `acquisition_time_invalid`（时钟回跳；CF 失败连带 TA） | done（(a) dd2058c；(b) 用户决定 wontfix） |
| [run-findings-20261002/05](../run-findings-20261002/issues/05-rejected-candidate-overrides-held-target.md) | 已取得的目标期被旧候选改判为"检索未通过" | done（68b50d2） |
| [run-findings-20261002/11](../run-findings-20261002/issues/11-first-retrieval-plan-before-run-calendar.md) | 首次补缺规划在装入运行日历之前 | done（732cbc7） |
| [run-findings-20261002/12](../run-findings-20261002/issues/12-scheduler-skips-only-weekends.md) | 盘后调度只排除周末 | done（cbac9b7） |
| [lookback/24](../lookback-fetch-gaps-20261008/issues/24-test-feedback-too-slow.md) | 测试反馈过慢（先诊断） | done（诊断：慢在每次运行约 7.1 万次开连接；`check.py` 逐阶段计时 a692827；`storage.py` 连接复用 0e0d7de／65b9e05，同口径 −28%／−50%；框 1、5 由收尾全套勾选） |
| [lookback/26](../lookback-fetch-gaps-20261008/issues/26-ai-websearch-claims-lack-subject-context.md) | AI WebSearch 原话缺标题与主语分句 | done（按网址重取页面；存量 35 条采用 30、排除 1、取不到 4，选值不变） |
| [lookback/27](../lookback-fetch-gaps-20261008/issues/27-historical-rerun-freshness-cutoff.md)（时效口径） | 历史目标日重跑时时效按运行截止点判定 | done（保持口径、并列标注） |
| [01](issues/01-acceptance.md) | 收尾验收：全套＋v0015 真实运行 | done（[acceptance-20261010.md](acceptance-20261010.md)：全套 2259 passed 1:06:05；`run-a1110cb8616e39b00f60` 10.2 分钟 153 回执；缺失 7、17 项完整、资讯选值 20 均不变；缺口 34→35 为 ECB 参考价截止时点口径） |

残余开票（下一批分流）：[lookback/28](../lookback-fetch-gaps-20261008/issues/28-dateline-xiaoxi-read-as-place.md) 电头"北京…消息"误判地方；[lookback/29](../lookback-fetch-gaps-20261008/issues/29-backfill-evidence-preload-and-wal-sync.md) 补算证据预载与 WAL `synchronous` 取舍。2026-10-10 分流：28 wontfix；29 ready-for-agent（`synchronous=NORMAL`，见 ADR-0038），同日实施完成（done，补算快照＋NORMAL；真实运行发现留存删除覆盖国庆的日历回执，致日频指标判为落后 6 期，待开票）。

**下一步**：本批已完成（2026-10-10，[验收记录](acceptance-20261010.md)：全套 2259 passed 1:06:05；v0015 真实运行 10.2 分钟，模型输入缺失 7→7、17 项完整、资讯选值 20 项不变）。残余票 28、29 已于 2026-10-10 分流（28 wontfix；29 当日实施 done，另发现留存删日历回执的既有缺陷待开票）；1002/05、1002/11 在真实运行中尚无可区分修复前后的实例，1002/12 要等 Worker 重装重启后生效（运行库调度已开启）。回到界面重规划主线（[decisions.md](../ui-replan-20261003/decisions.md)：报告式首页原型 → `/to-spec`）。
