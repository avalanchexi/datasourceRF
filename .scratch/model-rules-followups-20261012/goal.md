# 目标：模型规则批次后续积压的分流与处理（2026-10-12 规划）

**范围**：[本目录 README](README.md) 的 01–08（来源：[模型规则批次验收](../model-rules-validation-20261011/acceptance-20261012.md) 遗留一节与各票实施遗留）。

**终点**：
1. 01–08 每一张都有最终去向：`done`（已合入 main）、`wontfix` 或 `duplicate`（票面写明理由），或 `needs-info` 且问题已一次性交给用户。不留 `needs-triage`、`ready-for-agent`、`claimed`。
2. 若本批有改动生产代码（`src/`）的票合入，收尾验收票（新建 `issues/09-acceptance.md`）已 `done`：全套测试通过；一次 v0015 真实运行加体检，与 `run-b7d59b63bedca39d9d2e` 的差异都有原因。只改了体检脚本或文档时，只需对 `run-b7d59b63…` 实跑体检对账，不做真实运行。
3. 本目录 README 票表、本文件进度表、记忆都已更新并提交。

## 沿用

- [lookback goal.md](../lookback-fetch-gaps-20261008/goal.md) 的“单票执行规程”和“沿用口径”。
- [backlog goal.md](../backlog-triage-20261009/goal.md) 的角色划分、分流做法（`/triage`：事实由 Codex 取证，决定按预设走）与 worktree 合入流程。
- [体检 goal.md](../data-quality-audit-20261010/goal.md) 的“线 B 的差异规程”：体检脚本以实跑对账为准，只用标准库，不导入生产代码，运行库只读，规则只依据文档。
- [模型规则 goal.md](../model-rules-validation-20261011/goal.md) 的“角色”与“何时停下来问用户”，以及该批确立的做法：两轮审查后仍有新阻断时请示用户，批准后做一次定向复审。

## 角色

- **主 agent（`/goal` 会话）只做调度与核验**：分流、派票、核验提交与票面、执行 `git merge --ff-only`、清理 worktree、记进度、把问题转给用户。不亲手写实现代码，不亲手跑重型测试。
- **每张实施票派一个新的命名子代理**（Agent 工具，后台运行）；并行的票用 `isolation: "worktree"`。子代理完成并核验后，立即发出关闭请求。
- **只读调查、分流取证、两轴审查**一律用 `codex exec -s read-only`（见 `docs/agents/codex-delegation.md`），不开 Claude 子代理。
- 子代理的长任务**必须在前台轮询守到结束**。
- **API 连接中断（ECONNRESET）应对**（2026-10-12 实测多次）：子代理每完成一个阶段就在票面 Comments 记一句进展（时间、做到哪、日志路径）。主 agent 发现子代理 idle 而票未完成时发消息续做；显示 running 但文件长时间无变化时 TaskStop 并换新代理，提示词写明断点。

## 启动时先做

1. 用 CronCreate 设每 15 分钟一次的进度汇总（cron `7,22,37,52 * * * *`），提示词见文末；本会话已有同名汇总就不重复创建。
2. 运行 `df -h /mnt/c`，确认余量 ≥ 30G；确认 `/tmp/pring-heavy.lock` 未被占用、没有 Worker 在跑；运行 `git worktree list`（`datasourceRF-window-20260922/ticket-01…06` 是旧 worktree，不要动）。
3. **真实库的盘后计划已开启**（交易日 09:00 提交上一交易日）：本批除收尾验收外不要启动 Worker。
4. 提交本文件。

## 阶段 1：分流

- 按组运行 `codex exec -s read-only` 取证，逐项回答：现象在当前 main 上是否还在（给代码或运行库证据）、根因 `file:line`、受影响面、修复候选（各自改动模块、每次运行外部调用增量、会不会改变选值或口径、是否需要用户决定）。取证写进各票 `## Comments`，标题“2026-10-12 分流”。
- 主 agent 挑最反直觉的一两条结论自己复核。
- 套用下方预设后，把 `Status` 改为 `ready-for-agent`、`wontfix`、`duplicate` 或 `needs-info`；`ready-for-agent` 的票补上“验收”勾选框与“主要模块”。
- 需要用户定的问题攒成一批，一次 AskUserQuestion 问完（每次最多 4 题）；等待期间先推进已就绪的票。

### 分流池与预设决定

| 票 | 取证要点 | 预设决定 |
|---|---|---|
| [01](issues/01-corrected-days-missing-last-confirmed-stage.md) 34 个整日更正日上一确认阶段为空 | 实测 `run-b7d59b63…` 中 08-14～10-08 各日最新评估的 `last_confirmed_stage`；确认 `_backfill` 只按口径版本选择（`day_summary.py:357-362`）、以后确实不会再补；页面与报告哪里显示 | 是缺陷 → `ready-for-agent`：对“上一确认阶段”依赖的阶段历史已被后续更正改变的日子，追加一次只更正“上一确认阶段”的版本（不重算核心与上下文，外部调用 0，旧版本保留）。是否借用口径版本号机制或另设标记，按取证选更小的改动；若需改变“已汇总不再重算”的口径以外的领域规则，问用户 |
| [02](issues/02-scheduler-skips-missed-0900.md) 错过 09:00 不补交；P0 截止口径未入 ADR | `worker.py:142`、`:219` 的提交条件；晚启动时会不会与手动运行或幂等键冲突；补交对 P0 截止（提交当天 21:00）的影响 | 补交策略属领域决定，**问用户**，推荐“当日 09:00 后、P0 截止前首次判断时补交一次（同一幂等键）”。P0 截止改为“提交当天 21:00”直接补写进 ADR-0041（不问） |
| [03](issues/03-audit-lookback-and-core-only-days.md) 体检未覆盖回溯与只更正核心日 | 复现 (a) 回溯得出时第三层（一）的误报（可用 `run-97250978…` 复现）；(b) 只更正核心日在派生节被算作缺失的“待开票 8 项” | `ready-for-agent`（体检线）：文档先写回溯与只更正核心的核对规则，再改 `output_consistency.py`、`derived.py` |
| [04](issues/04-audit-loan-ytd-diff-false-missing.md) 贷款年内差分 189 项误报 | 在 `run-b7d59b63…` 上复现；确认生产“只看最新一期、前期不连续不出值” | `ready-for-agent`（体检线）：体检改为只取最新锚定期或按当日可见窗口截取，与生产口径一致 |
| [05](issues/05-audit-purged-periods-member-level.md) 清理统计按指标聚合 | 统计受影响的指标与期次数 | 影响小：若只涉及少数呈现 → `ready-for-agent`（体检线，改为成员级）；若改动牵涉第一层大范围重排 → `wontfix` 并写明理由 |
| [06](issues/06-receipt-and-calendar-residuals.md) 回执与日历残余 | (a) breadth 空交付记为 `nothing_new` 的影响面（是否影响缺口分类、重试）；候选 B（篮子全持有时 12→4 次请求）的节省与风险。(b) 时效截止日补取漏日按工作日回退会多算多少应有期；人工入口无 token 回退工作日的触发条件 | (a) 分类修正 → `ready-for-agent`（只改尝试分类，不动回执）；候选 B 属成本优化，**问用户**做不做（推荐做，外部调用每次少 8 次）。(b) 改不改为阻断属领域决定，**问用户**，推荐“保持回退、在缺口与报告中醒目标注日历依据不足” |
| [07](issues/07-audit-script-residuals.md) 体检零散残余 | (a) 文本比较时间的位置与潜在误判条件；(b) “原话不再成立”类排除能否只用标准库按文档独立实现；空串网址差异 | (a) → `ready-for-agent`（体检线，改为解析时刻后比较）；(b) 能独立实现 → 并入体检线，不能 → `wontfix` 并在体检已知局限写明 |
| [08](issues/08-lookback-cost-and-test-gaps.md) 回溯成本与测试缺口 | 每次运行重新回溯的实际成本（请求数、耗时）与触发频率；日历请求偏差 | 测试缺口 → `ready-for-agent`。回溯结果缓存（同一窗口首日、同一口径版本不重复回溯）→ `ready-for-agent`。规格补写“每年另有 1 次日历请求”（不问） |

## 阶段 2：实施

分流结束后按实际 `ready-for-agent` 的票删减下表：

| 线 | 位置 | 顺序 | 主要模块 |
|---|---|---|---|
| A | 主工作区，共享 `dev-venv` | 01 → 08 | `day_summary.py`、`projections.py`、`p0.py`、`stage_lookback.py`、`dashboard.py` |
| B | worktree，专用 venv `dev-venv-fub` | 02 → 06 | `worker.py`（调度）、`tushare_context.py`、`basket.py`、`freshness.py`、`trading_calendar.py`、ADR-0041 |
| C | worktree，不需要 venv | 03 → 04 → 05 → 07 | `tools/quality/`、`docs/development/data-quality-audit.md` |

- 实施票按 `/implement` 的做法：读票 → TDD（体检票除外）→ 受影响测试与冒烟 → 涉及运行编排时加跑重型两例 → ruff、mypy → Codex 两轴审查 → 提交。bug 票先拿到一条稳定变红的命令（`/diagnosing-bugs`）。
- 重型测试、`check.py full`、真实运行一律加 `flock /tmp/pring-heavy.lock`。
- worktree 分支收尾：先 rebase main，再复跑受影响测试，回报分支名；由主 agent `git merge --ff-only`。主工作区有其他线未提交的同名文件时，主 agent 先存补丁、合入后 `git apply --3way` 放回并通知该线子代理（不要用裸 `git stash`）。
- 线 A 与线 B 都可能碰 `worker.py`：后合入的一方先 rebase 再复跑受影响测试。新增迁移时编号以合入时 main 为准（当前最新 0037）。
- 体检线每票对 `run-b7d59b63bedca39d9d2e` 实跑对账：改动前后各跑一次，除改动节与耗时外逐字相同，差异逐项解释。

## 阶段 3：收尾验收

仅当本批有生产代码合入时执行。新建 `issues/09-acceptance.md`（被全部实施票阻塞），派一个子代理：

1. 重装 dev-venv，跑一次 `check.py full`，带 `disk_guard.sh <pytest PID> <log> 12`，前台守到结束。
2. 备份运行库（回滚点放在 job 临时目录以外，例如 `~/.local/share/pring-cycle/backups/`），有新迁移就执行 `pring-cycle init`。
3. 真实运行：v0015，目标日取当时的上一交易日。**若票 02 合入且时间允许，优先让 Worker 在交易日 09:00 前常驻，以调度运行作为本次真实运行**（同时作为 T+1 调度的首个真实样本）；否则手动提交。外部调用串行，跑完停掉 Worker。
4. 运行 `python3 tools/quality/audit.py --run <新运行>`，逐项核对各实施票，与 `run-b7d59b63…` 比对差异。
5. 写 `acceptance-<日期>.md`，经 Codex 规格轴审查无阻断后提交；更新 README、本文件进度表和记忆。

只改了体检脚本或文档时跳过本阶段，只在各体检票里完成对账。

## 何时停下来问用户

- 预设决定之外的领域选择：攒成一批再问。
- 某张票两轮审查后，仍有不属于“修复确认”的阻断（请示是否做一次定向复审）。
- 出现与本批无关的测试失败，且无法判断是不是原有问题。
- C 盘余量低于 20G；真实运行失败，修一次后仍然失败；大面积网络故障（成片的 URLError）。

除此之外不要停顿，按依赖关系一直推进到终点。会话中断后重启：先查看 worktree、未提交改动、日志、审查输出和票面 Comments 里已有的进度，再派新代理接手，提示词里写明断点。

## 进度

| 阶段 | 票 | 状态 | 提交 |
|---|---|---|---|
| 1 | 分流 01–08 | done：01–08 全部 ready-for-agent（用户 10-12 决定：02 补交、06 候选 B 做、06(b) 保持回退醒目标注、08 缓存 wontfix；07(b) wontfix 写入体检局限） | a836aa4、本次 |
| 2-A | 01 → 08 | 01 done；08 实施中（fub-08，主工作区） | f7b1129 |
| 2-B | 02 → 06 | 02 实现与审查完成（用户批准第 3 轮定向复审，无阻断），rebase 到含 01 的 main 后复跑中（fub-02） | |
| 2-C | 03 → 04 → 05 → 07 | done（07(b) wontfix 写入体检局限） | 5ee16cb、bcf2e33、8f993b6、abf65e9 |
| 3 | 09 收尾验收（如需） | blocked | |

### 本批新增遗留（收尾时转入下一批积压）

- 生产 `news_rules.py:1262`、`:1374` 空串网址按 `COALESCE(url, body_hash)` 视为同一页面，与体检文档 `:295` 的书面规则不一致（本样本 0 条；票 07 分流）。
- 体检对冻结清单缺 `confirmation_rules` 的旧运行（如 `run-dc0bb2d9…`）报 `KeyError`（票 07 实施）。
- 体检各层 SQL 里的截止比较与 `acquisition.py` `_load_announced` 一处仍按文本比较时间（票 07 实施，已写入文档）。
- 体检 `derived.py` `_core_only()` 只读 `corrects.scope`；只更正核心的日子以后若被票 01 的“上一确认阶段更正”覆盖，原范围在 `corrects.carries` 中，会误报“标记不全”（票 01 实施；本批 34 天均为整日更正，不受影响）。

## 监控提示词（CronCreate 用）

```
【每 15 分钟进度汇总】先判断是否有任务在执行：用 ps 查 pytest、check.py、pring-cycle worker、codex exec、audit.py 等后台进程，并读取 .scratch/model-rules-followups-20261012/goal.md 的进度表，看是否还有子代理在工作、票待派或待用户回答。若既无后台进程、也无在工作的子代理、待派的票或待答问题（全部空闲或已到终点），则不做汇报：用 CronList 找到本任务并 CronDelete 删除，只用一句中文告知“当前无任务执行，已停止定时汇报”。注意：goal 已规划但尚未开始执行时，“待派的票”存在，应汇报“goal 待启动”而不是删除。
否则用中文汇报三部分，进度信息放最前：
一、任务进度：按阶段 1（分流）、线 A（01→08）、B（02→06）、C（03→04→05→07）、阶段 3（09），逐线报当前票与步骤、已完成与提交、最近提交（git log --oneline -3）、未提交改动概况；子代理空闲而票未完成时叫醒，长时间无文件变化时按“API 连接中断应对”处理；worktree 票完成由主 agent 核验、ff-only 合入、清理并派该线下一票。
二、后台执行进度：各进程运行时长与阶段；pytest 给【进度 i/N（p%）】[#####-----] 进度条、当前用例、失败数；真实运行报回执数与失败数；/tmp/pring-heavy.lock 占用者；C 盘余量（df -h /mnt/c）。
三、下一步工作：接下来要做的事项与等待用户决定的问题。
只汇总，不逐事件通知；格式简洁。
```
