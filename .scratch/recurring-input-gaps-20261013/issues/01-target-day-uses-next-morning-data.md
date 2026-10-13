Status: done
Type: task
Category: bug

# 01：T+1 用上次日早上公开的目标日数据

**What to build:** 目标日汇总可用公开可用时间不晚于运行冻结截止、期次不晚于目标日的明细，两融合计等次日早上公开的目标日数据当天进入模型。自动运行由 09:00 改为 09:30 发起，保证两融（09:05）在请求时已公开。补算日汇总口径不变，已有目标日汇总不追加更正。见 [规格](../spec.md)“Implementation Decisions”前两条与 ADR-0041 2026-10-13 补写。

**Blocked by:** None (can start immediately)

**主要模块：** 完整运行的需求计划、补缺门禁与上下文投影（目前各自计算目标日公开截止，先收拢到一处）；运行调度。

- [x] 目标日公开截止只在一处计算，计划、补缺门禁与投影共用
- [ ] 正例：目标日两融在次日 09:05 公开、早于冻结截止，进入目标日投影的冻结输入（同一规则以 CPI 在汇总接缝验证、两融在计划接缝验证为目标日期次且 released；两融进入冻结输入的端到端用例未写成，见实施记录）
- [x] 反例：同一值不进入补算日汇总；期次晚于目标日的值不进入目标日汇总
- [x] 调度：09:29 不提交、09:30 提交；补交、P0 截止（提交日 21:00）与幂等键用例保持通过
- [x] 受影响测试与切片收尾冒烟通过（docs/agents/testing.md）
- [x] 若有与 CONTEXT.md、ADR-0041 补写不一致之处，在 Comments 写明并请示

## Comments

- 2026-10-13 领取：worktree 基于 recurring-input-gaps `fd5a91b`；接缝按规格 Testing Decisions（Worker 完整运行集成测试、调度编排测试），开始调查目标日公开截止的计算点。
- 2026-10-13 调度切片完成（未提交）：`SCHEDULE_START_TIME` 改 09:30，新增迁移 `0038_scheduled_run_at_0930`（最新版本非 09:30 时追加 09:30 新版本、开关不变），调度用例时刻平移到 09:30 边界；`test_run_orchestration.py`、`test_database_lifetime.py`、`test_worker_execution.py -k schedul` 通过。
- 2026-10-13 投影切片完成（未提交）：新模块 `summary_cutoff.py`（`SummaryCutoff`：公开不晚于截止，且越过该日结束的只认期次不晚于该日的；补算日截止即该日结束，规则退化为旧口径），投影 `TargetBoundEvidenceRepository` 与 `DaySummaries.summarize_target` 接入；`test_day_summary.py` 新增目标日正反例、补算日反例，`test_day_summary.py`、`test_context_projection.py` 通过。调查笔记：scratchpad `notes/rig01-cutoff-survey.md`。下一步：计划锚点、补缺门禁、选值器、lookback/信贷脉冲覆盖共用该规则。
- 2026-10-13 计划/门禁切片完成（未提交）：`freshness.latest_released_period`、`worker._retrieval_release_status`/`_registered_release_state`、`full_retrieval` 的门禁/计划/应有期/最新已发布期、`ModelInputSelector.cutoff`、`full_run_requirements.public_cutoff`、`lookback.resolve`/`credit_impulse` 覆盖、Worker 解释性完整度警告均改用 `SummaryCutoff`；`test_full_run_retrieval.py` 计划用例改为冻结在次晨 9:40，两融/VIX/SOX 计划目标日、无晚于目标日的会话。正在跑受影响集合（73 个文件）。
- 2026-10-13 受影响集合首轮：1500 过、3 败（57 分钟）；Codex 两轴首轮均“阻断：有”。已修：①`_due` 越过目标日即返回空（历史重跑漏应有期）→ 新增 `freshness.latest_due_period` 向前找所知的最新应有期；②同来源修订折叠后再过滤会丢目标日已知旧值 → `TargetBoundEvidenceRepository._known` 对期末晚于该日的点按该日结束读取（新用例 `test_a_period_running_past_the_target_is_read_as_it_stood_by_the_targets_end`）；③定向刷新的选值器误用运行截止 → 只对完整运行用运行截止；另 `_target_trading_days` 共用截止、删 `lookback._day_end` 死代码。3 个失败用例与新用例复跑通过。两融专项汇总用例因 v0015 观察接口夹具（同日公开的两融也显示 missing，与截止无关）放弃，改由计划用例与 CPI 汇总用例覆盖。

### 2026-10-13 实施

- **改了什么**：新模块 `src/pring_cycle/summary_cutoff.py`（`SummaryCutoff`）：一条规则——声明公开不晚于截止；公开晚于该日结束的，只认期次结束不晚于该日的。目标日截止取运行冻结截止（采集窗口开放时取决策时刻），补算日截止即该日结束，规则退化为旧口径。计划（`full_run_requirements.public_cutoff`、`full_retrieval` 的期次锚点、应有期 `freshness.latest_due_period`、最新已发布期 `freshness.latest_released_period`）、补缺门禁（`worker._retrieval_release_status`/`_registered_release_state`）、完整运行选值器（`ModelInputSelector.cutoff`）、lookback 与信贷脉冲覆盖（`cutoff.on(day)`）、投影（`TargetBoundEvidenceRepository`，`DaySummaries.summarize_target` 传冻结截止）、Worker 解释性完整度警告共用它。期末晚于目标日的点按目标日结束读取（避免同来源次晨修订折叠掉目标日已知值）。定向刷新保持该日结束。调度 `SCHEDULE_START_TIME` 改 09:30，迁移 `0038_scheduled_run_at_0930` 对最新版本非 09:30 的计划追加 09:30 新版本（开关、时区保留；幂等键中的计划版本随之变化）。文档：`GLOSSARY.md` 自动运行默认时刻、`docs/development/local-runtime.md` 调度段。
- **测试**：新增 `test_day_summary.py` 目标日正反例（次晨公开、期次不晚于目标日的进入投影与冻结输入；期次晚于目标日的不进入）与补算日反例；`test_context_projection.py` 进行中期次的次晨修订不覆盖目标日已知值；`test_full_run_retrieval.py` 计划用例冻结在次晨 9:40，两融/VIX/SOX 计划目标日、门禁 released、无晚于目标日的会话；调度边界 09:29:59 不提交、09:30 提交，迁移用例。改期望的旧用例：`test_full_run_retrieval.py` 三处（计划用例改冻结时刻并删“VIX 无 scope”——夹具 Cboe 文件止于 9/22，目标日 VIX 缺值按原注释进入计划，执行层仍不检索；`treasury_partial` 改 `source_empty`——补取的是目标日本身，夹具缺两年期；核心 as-of 模式用例改为公开时间晚于截止以保留 PUBLIC/SYSTEM 区分），`test_worker_execution.py` 调度时刻平移到 09:30，`test_run_orchestration.py` 默认计划 09:30、0036 用例停在 0036。两融专项汇总用例因 v0015 观察接口夹具（同日公开也显示 missing，与截止无关）未写成，由计划用例与 CPI 汇总用例覆盖。
- **验证（并入集成分支 `4e4b934` 后、重装 `dev-venv-rig01`）**：受影响集合 74 个文件 1517 过（55.5 分钟，超 180 秒反馈目标，因共享选值逻辑扩大范围）；冒烟两例 2 过（32 秒）；重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 4 过（305 秒，`flock`）；`ruff check`、`ruff format --check`、`mypy` 改动文件通过。
- **审查**：Codex 两轴首轮均阻断（`_due` 越界返回空、修订折叠丢值、定向刷新误用运行截止等），修复后定向复审“阻断：无”。非阻断未采纳：新闻拉取窗口、降准回溯、LPR 发布日历仍以目标日结束为上限（见下方请示）；体检 `tools/quality` 的公开截止口径属票 03。

### 请示（needs-info）

1. **进行中期次**：“期次不晚于目标日”按期次结束日理解时，当月 LPR 定盘（期次 8-01..8-31）在 8-28 也会被排除。现实现保留旧行为：期末晚于目标日的声明只在目标日结束前公开才进入目标日汇总（次晨公开的不进）。推荐：维持此实现，并在 GLOSSARY“单日汇总”补一句。
2. **新闻拉取窗口与降准回溯**：仍以目标日结束为上限，次晨发布的新闻、期刊不会被取来补缺（计划已按新口径要求这些期次）。推荐：另开票，让新闻窗口终点改为运行截止，降准回溯保留“生效日不晚于目标日”、公开上限改为运行截止；本票不改。

### 2026-10-13 用户决定（主 agent 转达）

1. 进行中期次：维持现实现（期末晚于目标日的声明只在目标日结束前公开才进入目标日汇总）；GLOSSARY“单日汇总”已补一句。
2. 新闻拉取窗口与降准回溯：另开票 → [06](06-news-window-and-rrr-lookback-use-run-cutoff.md)，本票不改。

未勾的正例框（两融进入目标日冻结输入的端到端用例）由票 05 真实运行核验。主 agent 核验后合入集成分支（`bf7f953`）。
