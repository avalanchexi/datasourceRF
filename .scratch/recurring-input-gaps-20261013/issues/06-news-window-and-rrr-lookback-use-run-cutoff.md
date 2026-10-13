Status: needs-info
Type: task
Category: bug

# 06：新闻拉取窗口与降准回溯的公开上限改为运行截止

**What to build:** 票 01 之后，目标日的计划已按运行冻结截止要求次晨公开的期次，但新闻拉取窗口与降准回溯仍以目标日结束为上限，次晨发布的新闻、期刊不会被取来补缺。把新闻拉取窗口的终点改为运行截止；降准回溯保留“生效日不晚于目标日”，公开上限改为运行截止。规则走票 01 的 `SummaryCutoff`（`src/pring_cycle/summary_cutoff.py`），补算日不变。

**来源：** 票 01 请示 2，2026-10-13 用户决定另开票。

**Blocked by:** 01（不阻塞 05）

**主要模块：** 新闻规则拉取窗口、降准回溯（见 scratchpad `notes/rig01-cutoff-survey.md` 与票 01 Comments）。

- [x] 新闻拉取窗口终点为运行截止；补算日仍为该日结束
- [x] 降准回溯：生效日不晚于目标日，公开上限为运行截止
- [x] 正反例测试；受影响测试与切片收尾冒烟通过
- [x] 每次运行外部调用增量写明

## Comments

- 2026-10-13 领取：worktree 基于 recurring-input-gaps `e1a0d8a`；接缝沿用现有集成测试（完整运行检索 `FullRunRetrieval.retrieve` 的新闻拉取、`pull_news` 窗口衔接、`backtrack_rrr_chronicle`、完整运行降准回溯 `backtrack_run`）。
- 2026-10-13 新闻切片完成（未提交）：`_pull_news` 终点改为 `SummaryCutoff.target(run, now).public_as_of`（删 `_target_end`）；`news_window` 只从更早目标日的运行衔接（同日重跑、晚做的早日运行不接本日及以后的拉取，因各次拉取止于各自截止）；`_readable` 读到同一截止（采集窗口开放时为当下，而非提交时刻）。新增正反例：次晨 09:39 公开的 CPI 新闻进入（截止 10:00）、10:30 的不取；采集窗口开放时提交后公开的新闻被读。改期望：首拉窗口、次日衔接、长停一周回看三处。
- 2026-10-13 降准回溯切片完成（未提交）：`summary_cutoff.dated_public_by`（只有日期的发布按当日结束公开）；`backtrack_rrr_chronicle`、`discover_event` 新增 `public_as_of`（缺省为 `until` 当日结束），期刊/候选按“当日结束不晚于运行截止”放行，生效日仍不晚于目标日；`_backtrack_events` 传 `SummaryCutoff.target`。新增正反例：周四早截止读到周三期刊、周三早截止不读；周五 09:30 截止采纳周四页面的 8-15 降准、生效日 9-24 的拒收。`test_rrr_backtrack.py` 20 过（208 秒）。下一步：受影响集合、冒烟、重型、审查。
- 2026-10-13 首轮受影响集合 76 过 1 败（新增用例断言精确到秒，运行时钟走动 1 秒即失败，已改为区间断言）；Codex 两轴首轮均阻断：①新闻跨目标日漏用（次日运行只接上次截止，周末/次晨属于下一目标日的新闻无人读）→ 改为从更早目标日拉取的 min(终点, 该目标日结束) 衔接，次日用例恢复原断言；②期刊放行（当日结束）与入库公开时间（次日 00:00）不一致 → 期刊改用 `publication_times`，AI 门槛与入库共用 `day_end`，删 `dated_public_by`；③`_adopt` 仍按提交时刻校验 → 回溯时传运行截止。新增：日末边界、晚发期刊含新降准、跨午夜开放窗口正例（先验证红）。`test_rrr_backtrack.py` 22 过（229 秒）。定向复审进行中。

### 2026-10-13 实施

- **改了什么**：
  - 新闻：`FullRunRetrieval._pull_news` 的请求终点改为 `SummaryCutoff.target(run, now).public_as_of`（运行截止；采集窗口开放时为当下），删 `_target_end`。`tushare_news.news_window` 的起点改为：只看更早目标日的完整拉取，取各自 `min(拉取终点, 其目标日结束)` 的最晚者（一周回看封顶）——每次运行只读自己的拉取、按自己的缺口解析，目标日结束后到截止之间的新闻也属于下一目标日，下一次运行从上一目标日结束接着读；同日重跑仍重读前次窗口。`_readable` 读到同一截止（不再停在提交时刻）。
  - 降准回溯：`_backtrack_events` 取 `SummaryCutoff.target`，`until` 仍为目标日（生效日上限不变），另把运行截止传给 `backtrack_rrr_chronicle(public_as_of=)` 与 `discover_event(public_as_of=)`（缺省为 `until` 当日结束，旧口径）。栏目只列日期的期刊按 `evidence.publication_times`（次日 00:00 公开，与入库口径一致）判断是否在截止前公开；AI 候选按页面日期当日结束（与入库 `public_by_published_day` 共用 `day_end`）判断，`_adopt` 在回溯时用运行截止校验日期与页面精确时间（缺口路径仍用 `run.system_as_of`）。
  - 补算日不变：补算日不拉新闻、不做回溯，其汇总仍按 `SummaryCutoff.at_day_end` 读（票 01 的规则与测试未改）。
- **测试**：`test_tushare_news.py` 新增次晨 09:39 新闻补 CPI（截止 10:00）／10:30 的不取、采集窗口开放时提交后公开的新闻被读；`pulled_run` 改为按运行截止拉取；改期望：首拉窗口（区间断言，运行时钟会走）、长停一周回看（锚定截止：9-18 15:00）；次日衔接用例保留原断言（周一运行读到周日 LPR）并新增请求两端断言。`test_rrr_backtrack.py` 新增：周四早截止读到周三期刊并采用其中 6-01 降准、周三早／周三日末截止不读；周五 09:30 截止采纳周四页面的 8-15 降准、生效日 9-24 的拒收；23:50 提交、00:10 检索、页面 23:55 的候选被采纳（先验证红）。提取 `column_without_a_cut` helper。
- **验证**（`dev-venv-rig06`）：受影响集合 `test_tushare_news.py`、`test_ai_websearch.py`、`test_full_run_retrieval.py`＋两例冒烟 79 过（595 秒；超 180 秒目标，`test_full_run_retrieval.py` 是新闻拉取与回溯的直接调用方，必须覆盖）；`test_rrr_backtrack.py` 22 过（229 秒）；重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 4 过（349 秒，`flock`）；`ruff check`、`ruff format --check`、`mypy` 改动文件通过。未选：`test_tushare_call_quota.py`、`test_retention.py`（不经 `pull_news`／`_readable`）、`summary_cutoff` 消费者（该模块最终未改）。
- **每次运行外部调用增量**：只有 TuShare `major_news` 变化。窗口终点由目标日结束后移到运行截止，次日运行仍从上一目标日结束读起，因此目标日结束至截止这一段被相邻两次运行各读一次。按真实库 10-09／10-12 两次拉取（约 2 页／天，每页约 8–12 小时）估算：定时 09:30 运行每次约 +1 次分页请求（夜间 9.5 小时约一页），周一跑上周五约 +1～3 次（周末 2.4 天）；日额度 40（可用 36），一周窗口封顶不变。官方期刊、AI WebSearch 请求次数不变（只可能换读另一期期刊或采纳另一候选）。
- **审查**：Codex 两轴首轮均阻断（新闻跨目标日漏用；期刊放行与入库公开时间不一致；`_adopt` 仍按提交时刻），修后定向复审“阻断：无”。非阻断处理：正则拆行、提取 helper、复用 `day_end` 已采纳；`pulled_run` 用生产 `SummaryCutoff` 计算终点不改（它是“按完整运行的方式拉取”的夹具，请求两端另有独立字面断言）；“新闻进入目标日但不进入补算日”“冻结后读取”由票 01 的汇总接缝测试覆盖，不重复写。
- **遗留（建议另开票，既有行为非本票引入）**：官方回溯找到声明即停止、记 `found`，未复核这些声明按其入库公开时间在目标截止时是否可读；若期刊页面正文发布时间晚于栏目日期，可能停在目标日读不到的期刊上（复审确认基线 `e1a0d8a` 已如此；首轮所举夹具的五月时间是 `createDate` 元数据，不被解析，不构成实例）。

### 请示（needs-info）

**显式截止远晚于目标日时，新闻回看锚在哪里？** 现实现：一周回看锚定运行截止（终点＝截止，起点＝截止前一周或上一目标日结束的较晚者）。手动重跑一个较早目标日、截止为今天时，窗口不覆盖目标日附近的新闻，该运行的缺口无法从新闻补（会走后续渠道）；定时与当日手动运行（截止为次晨）不受影响。另一选项：回看锚定目标日结束、终点仍为截止，可读到目标日附近新闻，但截止越晚窗口越长，分页增多，可能耗尽每日 40 次额度（“长停只回看一周”的初衷正是避免这种拉取）。**推荐维持现实现**（历史重跑罕见，回看长度与额度消耗保持原样）。

- 2026-10-13 并入集成分支 `a6beb7d`（只含 tools/quality、文档与票面，未动 src/tests）后重装 `dev-venv-rig06`，复跑受影响集合（`test_tushare_news.py`、`test_rrr_backtrack.py`、`test_ai_websearch.py`、`test_full_run_retrieval.py`＋两例冒烟）101 过（993 秒）。待主 agent 转达请示后合入。
