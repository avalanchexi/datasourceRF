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
| [02](issues/02-fut-wsr-request-volume.md) | 补缺对每个缺日重取全部 6 个品种（本轮 714 次）；失败回执在 `started` 阶段丢原因码 | 失败都记原因码；补缺只取缺失的品种（缺日根因是时钟，已修） | done（晚间运行已确认）|
| [03](issues/03-mid-autumn-due-period.md) | 中秋休市的 9/25 被当成应到期：银行间日频指标和中间价按落后一期计 | 查时效到期日所用的日历 | wontfix |
| [04](issues/04-vix-scope-test-order.md) | 全套里 `test_full_run_plans_the_latest_released_period_of_a_metric_not_held` 失败，单独跑能过 | 不是串扰：conftest 离线默认漏了 `quote_sources`，用例真实访问 Cboe，失败时 VIX 进入检索范围；已补离线默认并由用例提供 Cboe 夹具 | done |
| [05](issues/05-heartbeat-overlap-test.md) | `test_a_heartbeat_blocked_by_a_long_write_keeps_the_lease` 稳定失败，在 `9d230f9` 上也失败 | 查锁为何提前释放；可能与票 01 的时钟有关 | done |
| [06](issues/06-context-trade-cal-empty.md) | 今天两次 context 口径的 `trade_cal`（`is_open=1`）都返回 0 行，上次返回 1560 行 | 先确认是否影响任何指标 | needs-info |
| [07](issues/07-bytecode-in-src.md) | 全套里字节码用例失败：`src/pring_cycle/__pycache__` 是 9/26 用系统 Python 3.10 留下的 | 已清除，单独复跑通过；只记录 | wontfix |
| [08](issues/08-czce-cf-first-request-failures.md) | 郑商所 CF 有 6 天首次请求 `ValueError`、没有原因码，同一运行内重取成功 | 补上原因码；可能与票 01 有关 | duplicate（并入 02）|
| [09](issues/09-credit-impulse-missing-silently.md) | 信用脉冲自 9/25 起一直 `missing_inputs`，过热卡 `insufficient_data`，但不在缺口清单里 | 现库里从未算出过（不是 9/25 起）。根因：回看起点少了差分基线期（社融 `2024-08`、GDP `2024Q2`），补缺也不走 TuShare。修取数起点；派生失败与冲突进缺口清单（用户定）。已实施；9/29 第四次运行信用脉冲 `available`（−3.93），过热卡 `cooling` | done |
| [10](issues/10-sf-total-conflicted.md) | 社融总量 2026-08 自 9/26 起有一条 `conflicted`，也不在缺口清单里 | TuShare 239109 与央行"23.91 万亿"是精度差，零容差判成冲突。改三档：0.5% 内相容、单位错判冲突、其余冲突（ADR-0033）。是票 09 的第二道阻断。9/29 运行已确认冲突消失 | done |
| [11](issues/11-tests-reach-network.md) | 修掉 Cboe 后仍有测试真实访问外网 | 会话级离线拦截（代理指向关闭端口、只解析本机）；离线全套没有用例因断网失败。另做三处提速，全套 76 → 44 分钟 | done |
| [12](issues/12-gdp-official-backfill-imports-vintage.md) | 补缺为取 GDP 实际同比，把统计局初值也导入了，与 TuShare 修订值冲突，信用脉冲仍缺 | 用户定：补缺跳过已由其他来源交付的成员 | done |
| [13](issues/13-gdp-vintage-check-rejects-tushare.md) | GDP 版本相容性检查只认统计局公告页，TuShare 交付的名义值一律不相容，信用脉冲卡在 `incomparable_gdp_vintages` | 用户定：同一次 TuShare 交付视为同版本（按取值判断）；其余照旧核对 | done |
| [14](issues/14-usdcny-close-document-invalid.md) | 外汇交易中心 16:30 收盘价页面被拒（`chinamoney_close_document_invalid`） | 下次运行仍出现再取原件对照 | needs-info |

用户确认数据时效只需 T+1（2026-09-28）：01、05 已关闭，03 不修。处理顺序：02 → 04 → 08，06 继续观察。

## 验收运行（2026-09-28 晚）

> *本段由 AI 在验收时生成。*

代码 `d351c06`。全套 `check.py full`：1229 例全过，76 分钟，退出码 0（上午那轮 84 分钟、3 例失败）。

真实完整运行 `run-67ad41fc9072b672e3bb`：提交时**不指定** `--target-date`，系统自动定为 2026-09-28，提交成功（票 01 的症状没有再出现）。`completed`，用时 13 分钟（上一轮 57 分钟），261 张回执，检索用量为 Tavily 11 次、AI 联网搜索 3 次、Exa 0 次。

- **缺口清单只有 1 项**：SOX `license_missing`，符合预期。因为目标日是 9/28，中秋造成的落后一期也不再出现。
- 票 01：时间相关错误 0 次。票 02：`fut_wsr` 54 次，失败回执都带原因码，已确认。票 04：全套里通过。
- 票 06：context 口径 `trade_cal` 这次返回 13 行（应约 400 行），仍不可靠。
- 缺口清单之外的发现：信用脉冲一直缺失（票 09）、社融总量有冲突（票 10），两者都早于本轮，缺口清单都看不到。

结论：取数链路（时钟、请求量、原因码、行情文件）已经稳定，按缺口清单验收全部达标。但缺口清单看不到派生指标和冲突，所以"清单里只剩 SOX"不等于所有输出都完整。09、10 需要先分流。

**下一阶段（用户选择，2026-09-28）：** 先修票 09、10（信用脉冲与社融冲突），按 `/triage` 分流后用 `/diagnosing-bugs` 查根因；之后做测试提速（`/improve-codebase-architecture`，票 11 一并纳入），再转入日常运行。

**分流（2026-09-28）：** 09、10 转 `ready-for-agent`，实施顺序 10 → 09（09 的真实运行验收依赖 10）。新增 [ADR-0033](../../docs/adr/0033-cross-source-values-compatible-within-half-percent.md)。

## 验收运行（2026-09-29）

> *本段由 AI 在验收时生成。*

代码 `174d282`。全套：先在离线拦截下跑了一轮，1249 例中 1248 过、1 败（缺口清单同一指标出现两次，已修复），65 分钟；提速后再跑一轮，**1250 例全过，43.7 分钟**（基准 76 分钟）。

真实完整运行 `run-444e4da7f92f0bb34549`：不指定目标日，系统自动定为 2026-09-28，`completed`，用时 10 分钟，完成后已用 SIGTERM 停止 Worker。

- 票 10：社融 2026-08 `ytd_increment` 这次是 `current`，冲突消失。
- 票 09：取数起点已覆盖基线（`202408`、`2024Q2`）；缺口清单现在列出 `CN_CREDIT_IMPULSE derived_failed`，并指出缺的是哪几期，不再只有 SOX。**但信用脉冲仍然算不出来**：补缺带回的统计局 GDP 初值与 TuShare 的普查修订值相差约 2.7%，2024-Q2、2024-Q3 被判为冲突（票 12）。

第二次真实运行 `run-32e17c10a10e4cdad483`（代码 `0b78061`，全套 1251 例全过，49.5 分钟）：`completed`，10 分钟。票 12 已生效，GDP 名义值不再冲突，信用脉冲的输入已齐全，但停在 GDP 版本相容性检查 `incomparable_gdp_vintages`（票 13）；缺口清单另有 USDCNY 16:30 收盘价被拒（票 14）。

第三次真实运行 `run-7e5c2fab7f22529c7250`（代码 `a8455c4`，全套 1252 例全过）：仍是 `incomparable_gdp_vintages`。补缺逐季重取 TuShare，每个季度的声明落在不同回执上；改为按取值判断同一次交付（票 13）。USDCNY 16:30 没有再出现（票 14 按偶发处理）。

**第四次真实运行 `run-c28425a3901b9d5f607c`**（代码 `403cba4`，全套 1254 例全过，56 分钟）：`completed`，11 分钟，Tavily 9 次、AI 联网搜索 1 次。**信用脉冲 `available`，2026-08 值 −3.93；过热卡由 `insufficient_data` 变为 `cooling`；缺口清单只剩 SOX。** 缺口清单现在也会列出派生失败和来源冲突，所以"只剩 SOX"这次代表所有输出都完整。

结论：票 09–13 全部关闭，14 继续观察，06 继续观察。本阶段转入日常运行。
