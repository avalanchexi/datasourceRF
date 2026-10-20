# 阶段 3 积压预审（Codex 只读，2026-10-20，main@2f876b2）

| 票 | 判定 | 证据（简） | 建议 |
|---|---|---|---|
| 模型 01：两套校时冲突 | 已解决 | `7ad3e31`；本次 65 秒检查通过 | 关闭原票，同步过时运维文档 |
| 模型 02：回拨零容忍 | 仍存在 | `_check_time` 倒退 1 微秒即拒收 | `needs-info`，先定时间校验口径 |
| 模型 03：篮子快路径反增请求 | 仍存在 | 缺目标日仍先请求四份日历；测试明确断言该行为 | `ready-for-agent` |
| 模型 04：体检历史误报 | 仍存在 | 本次复现旧清单 `KeyError`、9 项待开票、信用脉冲 13 天原料不齐 | `ready-for-agent`，优先处理 |
| 模型 05：空网址去重偏差 | 仍存在 | 生产仍用 `COALESCE(url, body_hash)`；正式库空串样本 0 | `ready-for-agent`，低优先级 |
| 模型 06：文本比较时间 | 仍存在 | 体检 SQL 和 `_load_announced` 仍按文本比较；原票误标为生产模块 | `ready-for-agent`，先纠正范围 |
| 模型 07：清理结果未留存 | 仍存在 | Worker 丢弃 `prune_to_window()` 返回值 | `ready-for-agent` |
| 模型 08：残留运行及污染报告 | 仍存在 | 正式库仍有四个待处理运行及报告第 1 版 | 建议 `wontfix`，保留历史证据 |
| 缺口 01：人民币收盘价 | 已被取代 | 继任票 08；晚间取数＋次晨补取已实现 | 关联继任票后关闭 |
| 缺口 02：SOX 无来源 | 已被取代 | 继任票 09、12；Nasdaq 来源及体检均已接入 | 关联继任票后关闭 |
| 缺口 03：运行变慢 | 信息不足 | 后续耗时有波动；原异常未稳定复现，根因未证实 | `needs-info`，保留观察 |
| 缺口 04：09:30 准点未验证 | 已解决 | 10 月 20 日计划运行于 09:30:04 受理 | 关闭；勿将提交样本当作完成样本 |
| 缺口 05：体检新截止口径 | 已被取代 | 继任票 10；`ff2bb47` 已实现生效时刻分支 | 关联继任票后关闭 |
| 缺口 06：降准回溯可读性 | 已被取代 | 继任票 11；`083a7c7` 已实现截止复核 | 关联继任票后关闭 |
| 缺口 07：锁竞争与 SSL EOF | 仍存在 | 锁警告在 10 月 16、19 日再次出现；SSL 未见新增 | 锁竞争转 `ready-for-agent` 调查 |

**合计：已解决 2 张、已被取代 4 张、仍存在 8 张、信息不足 1 张。** 优先处理体检误报，以及已经重复出现的心跳锁竞争；不能把继任票的 `done` 一概解释为原问题已根治。

“模型”指 [.scratch/model-rules-residuals-20261013/issues](/mnt/d/cursor/datasourceRF/.scratch/model-rules-residuals-20261013/issues)；“缺口”指 [.scratch/recurring-input-gaps-residuals-20261014/issues](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues)。代码基线为 `main@2f876b2`。正式库通过 Python `sqlite3` 的 `file:…?mode=ro` URI 查询；未修改文件或数据库。下述测试名是代码覆盖证据，未运行 pytest；实际执行了校时、内存探针及两次只读体检。

**模型 01｜已解决**

- 问题：Hyper-V 与 timesyncd 相互校时，造成周期性回拨，原先只有临时处置。
- 证据：`7ad3e31` 记录永久禁用；[原票执行记录](/mnt/d/cursor/datasourceRF/.scratch/model-rules-residuals-20261013/issues/01-clock-two-time-syncs-fight.md:28)及 10 月 15 日重启后验收均确认 disabled／inactive。
- 本次 `python3 -B tools/clock_check.py` 退出码 0，65 秒无超过 0.2 秒跳变；沙箱无法连接 systemd 总线，因此未独立复核当前服务状态。
- 建议：关闭原问题；[local-runtime.md:500](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:500)仍写“持久处置待定”，应另作低优先级文档同步。

**模型 02｜仍存在**

- 问题：取数回执以墙钟严格判断先后，回拨会导致拒收。
- 证据：[acquisition.py:696](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:696)仍直接判断 `value < previous`；本次提取原函数做内存探针，倒退 1 微秒即报 `acquisition_time_invalid`。
- “整批拒收”不能泛化：`test_a_clock_stepping_back_fails_only_that_symbol_day` 已覆盖 CZCE 的品种日隔离；其他批量路径仍需分别确认。
- 影响／分流：中等、条件性风险；回拨复发会影响取数完整性和当日结果，目前触发环境已缓解。建议 `needs-info`。
- 拍板：是否改变时间顺序判据？推荐保留 UTC 审计时间，评估同进程单调时钟判序，并先明确跨进程／恢复边界，不直接放宽任意秒数容差。

**模型 03｜仍存在**

- 问题：篮子快路径只利于窗口全持有的重跑，日常新增目标日反而多请求日历。
- 证据：[basket.py:162](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:162)无目标日持有预判，直接进入四日历检查；[basket.py:321](/mnt/d/cursor/datasourceRF/src/pring_cycle/basket.py:321)最后才检查窗口全持有。
- `test_a_window_with_a_day_not_held_selects_as_the_full_flow_does` 明确断言“四份日历＋完整流程”；失败回退测试也明确保留额外请求。
- 影响／分流：低；增加每日耗时与额度消耗，未见改变计算结论。建议 `ready-for-agent`。
- 拍板：保留、撤销还是提前短路？推荐目标日未持有时跳过快路径预检，保留同目标日重跑收益；其余日历与回执遗留分开验收。

**模型 04｜仍存在**

- 问题：体检混淆历史清理、更正版本与实际缺数，并且不兼容缺少确认规则的旧模型。
- 实跑：`run-dc0bb2d9…` 退出码 1，在 [common.py:277](/mnt/d/cursor/datasourceRF/tools/quality/common.py:277)报 `KeyError: confirmation_rules`。
- 实跑：`run-0a8dabc2…` 退出码 0，但清理后的窗口首段仍报缺数／缺投影、派生 9 项待开票、信用脉冲 13 天重算原料不齐；435 条断链仍统称“窗口前预热”。
- 代码：[derived.py:1261](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:1261)仍取更正投影截止；[derived.py:1181](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:1181)只读 `corrects.scope`，未追 `carries`。
- 影响／分流：中；不改每日模型结果，但会误导质量判断、阻断旧运行体检。建议 `ready-for-agent`，拆成四个可验收修复点。
- 拍板：旧模型规则缺失如何处理？推荐明确报告“该项不适用／无法核对”，不能套用当前模型规则；其余修复无需新增口径决定。

**模型 05｜仍存在**

- 问题：空串网址被生产逻辑视为同一页面，与按正文哈希区分页面的书面规则冲突。
- 证据：[news_rules.py:1270](/mnt/d/cursor/datasourceRF/src/pring_cycle/news_rules.py:1270)、`:1382`仍用 `COALESCE`；[体检规则:386](/mnt/d/cursor/datasourceRF/docs/development/data-quality-audit.md:386)明确要求空串也回退到哈希。
- 内存 SQL 复现不同正文得到相同空串页面键；正式库 `claim_matched_quote WHERE url=''` 为 0。相关测试为 `test_a_kept_news_claim_whose_page_names_a_place_elsewhere_waits_for_its_subject`，未见空串专项覆盖。
- 影响／分流：低、潜在；触发时可能误排合法宏观声明，当前无受影响样本。建议 `ready-for-agent`。
- 拍板：无需新增决定，推荐按现有书面规则修复生产实现。

**模型 06｜仍存在，但票面范围有误**

- 问题：截止时间按字符串比较，混用时区或时间格式时可能错误判定先后。
- 证据：[tools/quality/acquisition.py:695](/mnt/d/cursor/datasourceRF/tools/quality/acquisition.py:695)、`:702`及 [common.py:287](/mnt/d/cursor/datasourceRF/tools/quality/common.py:287)仍保留文本比较；当前生产 `src/pring_cycle/acquisition.py` 没有 `_load_announced`。
- 内存反例：`08:00+08:00` 实际早于 `01:00+00:00`，字符串比较却相反。生产已有 `test_point_in_time_comparison_normalizes_equivalent_timezone_offsets`，不能证明体检 SQL 已覆盖。
- 影响／分流：低、潜在；已证实的是体检误判风险，本次未证实生产取数因此受影响。建议 `ready-for-agent`。
- 拍板：无需新增决定；先纠正原票模块路径，再统一体检比较为带时区时刻。

**模型 07｜仍存在**

- 问题：留存清理虽然返回删除统计，Worker 没有把结果写进运行记录。
- 证据：[worker.py:865](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:865)直接丢弃返回值；[retention.py:60](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:60)已有窗口、各表删除量、制品数和回收字节字段。
- `test_details_summaries_and_batches_before_the_window_are_deleted` 验证删除行为，并非运行记录留存；未发现记录该返回值的实现。
- 影响／分流：低；不影响每日计算，影响历史排障和清理归因。建议 `ready-for-agent`。
- 拍板：记录统计还是逐条删除身份？推荐先保存现有 `RetentionResult` 摘要；逐条墓碑另定范围，不能声称统计能还原全部被删对象。

**模型 08｜仍存在**

- 问题：四个旧定向刷新运行停在待处理状态，时钟污染运行的旧报告也仍可查。
- 库证据：`051b108c…／6e2b8c63…／297db123…／d3aa44aa…` 均仍为 `action_required`；`run-742bf2b…` 对应报告第 1 版仍为 `completed`、正文保留。
- [runs.py:466](/mnt/d/cursor/datasourceRF/src/pring_cycle/runs.py:466)只领取 `queued`；10 月 12 日已有第 2 版报告，当前投影属于 `run-153de306…`，并非污染运行。
- 影响／分流：低；不阻塞每日领取、不控制当前结论，但历史浏览可能误读。建议 `wontfix`，保留证据至正常留存到期。
- 拍板：是否必须提前处置历史？推荐保留、不删除；如需防误读，另做明确历史标注。

**缺口 01｜已被取代，继任实现已落地**

- 问题：09:30 请求当天盘中接口时，无法取得上一交易日 16:30 收盘价。
- 继任：[08-usdcny-close-holds-previous-session.md](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/08-usdcny-close-holds-previous-session.md)；提交 `e274ca1`、`3c1dbd2` 实现晚间取数与次晨补取，[worker.py:328](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:328)仍在。
- 测试：`test_a_run_past_0930_holds_the_close_fetched_the_evening_before`、`test_a_close_missed_in_the_evening_is_fetched_the_next_morning_before_0930`；正式库 10 月 15 日验收运行持有 10 月 14 日值。
- 边界仍在：错过两个在线窗口无法历史补取；10 月 16 日目标为 15 日的运行仍只持有 14 日值，不能宣称永久无缺口。建议关闭重复原票，沿用已接受的在线条件。

**缺口 02｜已被取代，取数与体检均已落实**

- 问题：SOX 没有真实指数取数路径，长期形成目录缺失。
- 继任：[09-sox-registered-source.md](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/09-sox-registered-source.md)、[12-audit-sox-has-a-path.md](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/12-audit-sox-has-a-path.md)。
- `b6a2c97` 在 [quote_sources.py:213](/mnt/d/cursor/datasourceRF/src/pring_cycle/quote_sources.py:213)接入 Nasdaq SOX 历史表；`36dd4bb` 在 [体检 acquisition.py:94](/mnt/d/cursor/datasourceRF/tools/quality/acquisition.py:94)按运行自己的来源记录判断路径。
- 测试 `test_each_session_of_the_window_is_held_by_its_trade_date`；正式库 10 月 15、16、19 日计划运行分别持有目标日 SOX，来源均为 `nasdaq:index_history`。建议关闭原票。

**缺口 03｜信息不足，不能判为根治**

- 问题：扣除休眠后仍出现约 2014 秒运行，明显慢于 755 秒对照，原因不明。
- [继任验收票 13](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/13-acceptance.md)已完成复测；[验收记录:177](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/acceptance-20261015.md:177)明确“未复现、无因果证据”，不是修复结论。
- 正式库后续完成运行墙钟约为 972、1398、1180、1634 秒；最后一例报告阶段约 601 秒，不能把总耗时变化全部归因于原取证据问题。
- 影响／分流：目前只证实延迟波动，未证实结果错误或稳定性能回退；建议 `needs-info`，现有功能测试不能代替性能基线。
- 拍板：何时升级调查？推荐以同版本、同类目标、无休眠且分阶段可比的运行持续变慢为触发条件，不直接沿用 755 秒单次样本作硬指标。

**缺口 04｜已解决**

- 问题：原先只验证过唤醒后的补交，缺少 09:30 准点提交样本。
- `5820c0c` 已记录用户接受 T+1 补交；[继任票 13:103](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/13-acceptance.md:103)明确取消本机准点验收要求。
- 本次又取得真实提交样本：`run-3ebbe323…` 为 `scheduled_full`，目标 10 月 19 日，受理于 **10 月 20 日北京时间 09:30:04.412978**；查询时仍在 `refreshing_evidence`。
- 测试 `test_enabled_schedule_submits_on_the_first_check_from_0930_to_its_p0_deadline` 覆盖首次检查提交。建议关闭；本次证据只证明提交，未证明这次运行成功完成。

**缺口 05｜已被取代**

- 问题：体检对其他日的投影仍按日终判断，可能误报采用次晨数据的新口径投影。
- 继任：[10-audit-new-cutoff-effective-time.md](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/10-audit-new-cutoff-effective-time.md)；提交 `ff2bb47` 已落地。
- [derived.py:55](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:55)登记生效时刻，[:1275](/mnt/d/cursor/datasourceRF/tools/quality/derived.py:1275)按生成运行受理时间及目标日身份切换到冻结截止。
- 验证采用体检实跑对账：旧运行保持旧口径，继任验收记录已有生效后 UST 场景实证。建议关闭原票；模型 04 的更正版本问题仍独立存在。

**缺口 06｜已被取代**

- 问题：官方降准回溯找到声明就停止，没有确认它在运行截止时可读。
- 继任：[11-rrr-backtrack-checks-cutoff-readability.md](/mnt/d/cursor/datasourceRF/.scratch/recurring-input-gaps-residuals-20261014/issues/11-rrr-backtrack-checks-cutoff-readability.md)；提交 `083a7c7` 已落地。
- [official_context.py:1484](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:1484)调用 `_claims_known`，不可读则继续更早期刊，并撤销不应计入的覆盖月份。
- 测试 `test_a_cut_not_readable_by_the_run_s_cutoff_gives_way_to_an_older_one` 覆盖截止前后两种选择。真实验收未触发回溯，不能冒称线上分支实证；代码与定向测试足以支持关闭原票。

**缺口 07｜仍存在，锁竞争应升级调查**

- 问题：观察心跳数据库锁竞争及调度日历 SSL EOF 是否重复出现、影响运行。
- [worker.jsonl:189](/home/tywin/.local/state/pring-cycle/logs/worker.jsonl:189)、[:196](/home/tywin/.local/state/pring-cycle/logs/worker.jsonl:196)显示 10 月 16、19 日新增锁警告，分别在运行完成约 23 秒、9 秒后；SSL EOF 仍只有 10 月 14 日那次。
- [worker.py:2571](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:2571)仍会记录并重试锁竞争；测试 `test_a_heartbeat_blocked_by_a_long_write_keeps_the_lease`、`test_a_failed_calendar_fetch_defers_the_schedule_and_retries_it` 覆盖恢复行为。
- 影响／分流：低至中；已见重复告警，未见这些样本导致运行失败或结论变化。锁竞争建议 `ready-for-agent`，SSL 保持观察。
- 拍板：是否按重复条件升级？推荐升级锁竞争调查，优先核对完成后的留存写事务与心跳重叠；这只是调查方向，尚非已证实根因。
