# 2026-09-28 真实运行遗留分流

来源：run-findings-20260926 的验收运行。先跑全套（`check.py full`，代码 `18899cf`：1214 过、3 败，84 分钟），再跑真实完整运行 `run-dc0bb2d9db7068bf552d`（目标日 2026-09-24，`completed`，57 分钟，1171 张回执）。

缺口清单从上一轮（`run-64209ab01ac75439cc8c`，同一目标日）的 4 项变为 12 项：

| 上一轮 | 本轮 |
|---|---|
| 工具流动性 `retrieval_failed` | 已持有（20260926 票 03 通过） |
| OMO 操作量 结构不符拒收 | 已消失（20260926 票 04 通过） |
| 仓单 `tushare_warrant_quantity_negative` | 仓单 `fut_wsr:acquisition_time_invalid`（票 01） |
| SOX `license_missing` | 同左，按预期保留 |
| — | 篮子、袖套 `fut_basic:acquisition_time_invalid`（票 01） |
| — | EIA Brent、WTI `eia_history_html:acquisition_time_invalid`（票 01） |
| — | DR007、DR007 政策利差、OMO 量与利率、SHIBOR、USDCNY 中间价：按 9/25 计落后一期（票 03） |

另外，提交运行时不指定 `--target-date` 会失败（`acquisition_time_invalid`，票 01）。前两次提交的目标日写错（9/26 周六、9/25 中秋），都已取消；它们只消耗了 Tavily 15 次、AI 联网搜索 4 次。

| 票 | 问题 | 建议 | 状态 |
|---|---|---|---|
| [01](issues/01-wsl-clock-acquisition-time.md) | Windows 时钟快约 9.6 秒，WSL 被两边来回拉扯而跳变，回执时间不单调，报 `acquisition_time_invalid` | 根因是 Windows 时钟未对时、快约 9.6 秒；已同步。代码是否防护待复验后定 | done |
| [02](issues/02-fut-wsr-request-volume.md) | 按品种逐日取 `fut_wsr` 约 720 次，42 次没收到应答；CU 缺 10 天，其余各缺 1 天 | 查限频；考虑按日取整族再按品种拆分隔离 | needs-triage |
| [03](issues/03-mid-autumn-due-period.md) | 中秋休市的 9/25 被当成应到期：银行间日频指标和中间价按落后一期计 | 查时效到期日所用的日历 | wontfix |
| [04](issues/04-vix-scope-test-order.md) | 全套里 `test_full_run_plans_the_latest_released_period_of_a_metric_not_held` 失败，单独跑能过 | 查测试之间的串扰；真实运行里 VIX 没有进入检索范围 | needs-triage |
| [05](issues/05-heartbeat-overlap-test.md) | `test_a_heartbeat_blocked_by_a_long_write_keeps_the_lease` 稳定失败，在 `9d230f9` 上也失败 | 查锁为何提前释放；可能与票 01 的时钟有关 | done |
| [06](issues/06-context-trade-cal-empty.md) | 今天两次 context 口径的 `trade_cal`（`is_open=1`）都返回 0 行，上次返回 1560 行 | 先确认是否影响任何指标 | needs-info |
| [07](issues/07-bytecode-in-src.md) | 全套里字节码用例失败：`src/pring_cycle/__pycache__` 是 9/26 用系统 Python 3.10 留下的 | 已清除，单独复跑通过；只记录 | wontfix |
| [08](issues/08-czce-cf-first-request-failures.md) | 郑商所 CF 有 6 天首次请求 `ValueError`、没有原因码，同一运行内重取成功 | 补上原因码；可能与票 01 有关 | needs-triage |

用户确认数据时效只需 T+1（2026-09-28）：01、05 已关闭，03 不修。处理顺序：02 → 04 → 08，06 继续观察。
