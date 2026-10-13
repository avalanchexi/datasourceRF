Status: claimed
Type: task
Category: bug

# 01：T+1 用上次日早上公开的目标日数据

**What to build:** 目标日汇总可用公开可用时间不晚于运行冻结截止、期次不晚于目标日的明细，两融合计等次日早上公开的目标日数据当天进入模型。自动运行由 09:00 改为 09:30 发起，保证两融（09:05）在请求时已公开。补算日汇总口径不变，已有目标日汇总不追加更正。见 [规格](../spec.md)“Implementation Decisions”前两条与 ADR-0041 2026-10-13 补写。

**Blocked by:** None (can start immediately)

**主要模块：** 完整运行的需求计划、补缺门禁与上下文投影（目前各自计算目标日公开截止，先收拢到一处）；运行调度。

- [ ] 目标日公开截止只在一处计算，计划、补缺门禁与投影共用
- [ ] 正例：目标日两融在次日 09:05 公开、早于冻结截止，进入目标日投影的冻结输入
- [ ] 反例：同一值不进入补算日汇总；期次晚于目标日的值不进入目标日汇总
- [ ] 调度：09:29 不提交、09:30 提交；补交、P0 截止（提交日 21:00）与幂等键用例保持通过
- [ ] 受影响测试与切片收尾冒烟通过（docs/agents/testing.md）
- [ ] 若有与 CONTEXT.md、ADR-0041 补写不一致之处，在 Comments 写明并请示

## Comments

- 2026-10-13 领取：worktree 基于 recurring-input-gaps `fd5a91b`；接缝按规格 Testing Decisions（Worker 完整运行集成测试、调度编排测试），开始调查目标日公开截止的计算点。
- 2026-10-13 调度切片完成（未提交）：`SCHEDULE_START_TIME` 改 09:30，新增迁移 `0038_scheduled_run_at_0930`（最新版本非 09:30 时追加 09:30 新版本、开关不变），调度用例时刻平移到 09:30 边界；`test_run_orchestration.py`、`test_database_lifetime.py`、`test_worker_execution.py -k schedul` 通过。
- 2026-10-13 投影切片完成（未提交）：新模块 `summary_cutoff.py`（`SummaryCutoff`：公开不晚于截止，且越过该日结束的只认期次不晚于该日的；补算日截止即该日结束，规则退化为旧口径），投影 `TargetBoundEvidenceRepository` 与 `DaySummaries.summarize_target` 接入；`test_day_summary.py` 新增目标日正反例、补算日反例，`test_day_summary.py`、`test_context_projection.py` 通过。调查笔记：scratchpad `notes/rig01-cutoff-survey.md`。下一步：计划锚点、补缺门禁、选值器、lookback/信贷脉冲覆盖共用该规则。
- 2026-10-13 计划/门禁切片完成（未提交）：`freshness.latest_released_period`、`worker._retrieval_release_status`/`_registered_release_state`、`full_retrieval` 的门禁/计划/应有期/最新已发布期、`ModelInputSelector.cutoff`、`full_run_requirements.public_cutoff`、`lookback.resolve`/`credit_impulse` 覆盖、Worker 解释性完整度警告均改用 `SummaryCutoff`；`test_full_run_retrieval.py` 计划用例改为冻结在次晨 9:40，两融/VIX/SOX 计划目标日、无晚于目标日的会话。正在跑受影响集合（73 个文件）。
- 2026-10-13 受影响集合首轮：1500 过、3 败（57 分钟）；Codex 两轴首轮均“阻断：有”。已修：①`_due` 越过目标日即返回空（历史重跑漏应有期）→ 新增 `freshness.latest_due_period` 向前找所知的最新应有期；②同来源修订折叠后再过滤会丢目标日已知旧值 → `TargetBoundEvidenceRepository._known` 对期末晚于该日的点按该日结束读取（新用例 `test_a_period_running_past_the_target_is_read_as_it_stood_by_the_targets_end`）；③定向刷新的选值器误用运行截止 → 只对完整运行用运行截止；另 `_target_trading_days` 共用截止、删 `lookback._day_end` 死代码。3 个失败用例与新用例复跑通过。两融专项汇总用例因 v0015 观察接口夹具（同日公开的两融也显示 missing，与截止无关）放弃，改由计划用例与 CPI 汇总用例覆盖。
