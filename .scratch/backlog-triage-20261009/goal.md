# 目标：分流并处理积压票（2026-10-09 规划，第三轮验收后更新）

**前提**：回看取数第二、三轮均已验收（票 17、25 `done`，见 [acceptance-20261009-round2.md](../lookback-fetch-gaps-20261008/acceptance-20261009-round2.md)、[acceptance-20261009-round3.md](../lookback-fetch-gaps-20261008/acceptance-20261009-round3.md)）；票 18、19 已在第三轮分流为 `wontfix`。原"阶段 1：收口票 17"已无事可做，删去。基线为第三轮验收：全套 2208 通过 1:16:56；模型输入缺失 7；17 项计数指标完整；最终计划 7 个缺口。

**终点**：
1. 分流池（见下方）里的每一项都有最终去向：`done`（已合入 main）、`wontfix` 或 `duplicate`（票面写明理由），或者 `needs-info` 且问题已一次性交给用户；后两种以外不留 `needs-triage`、`ready-for-agent` 或 `claimed`。
2. 若本批有实施票合入，本目录的收尾验收票（`issues/01-acceptance.md`）已 `done`：全套测试通过；若改动触及检索规划、缺口分类或时效判定（池中 1002/05、1002/11、时效口径），再做一次真实运行并与第三轮验收对比。
3. 各来源目录的 README 票表、本文件进度表都已更新，并已提交。

**沿用**：[lookback goal.md](../lookback-fetch-gaps-20261008/goal.md) 的"单票执行规程""沿用口径""并行规则""约束"，以及 [goal-round2.md](../lookback-fetch-gaps-20261008/goal-round2.md) 的"角色"和 worktree 合入流程、[goal-round3.md](../lookback-fetch-gaps-20261008/goal-round3.md) 的会话中断接手规则，全部照用。本文件只写本批的差异。

## 角色（同第二、三轮）

- **主 agent（`/goal` 会话）只调度**：分流、派票、核验提交与票面、合入、记进度、把问题转给用户。不亲自写实现代码，不亲自跑重型测试。
- **每张实施票派一个命名子代理**（Agent 工具，后台运行）；并行的票用 `isolation: "worktree"`。子代理核验完立即发关闭请求；合入后删除它的 worktree、分支和专用 venv。
- **只读调查和分流取证**都交给 `codex exec -s read-only`（见 `docs/agents/codex-delegation.md`），不开 Claude 子代理。

## 启动时先做

1. 用 CronCreate 设每 20 分钟一次的进度汇总（cron `7,27,47 * * * *`），内容包括：整体进度、每条任务线、刚完成的事、接下来要做的事、资源（C 盘余量、活跃子代理数、`/tmp/pring-heavy.lock` 是否占用）。只做定时汇总，不逐事件通知。
2. 运行 `df -h /mnt/c`，确认余量 ≥ 30G；确认 `/tmp/pring-heavy.lock` 没被占用（`ps` 里没有 `check.py`、pytest 或 worker）；运行 `git worktree list`。`datasourceRF-window-20260922/ticket-01…06` 是 9/22 的旧 worktree，与本批无关，**不要动**。
3. 提交本目录（`goal.md`、`README.md`）。

## 阶段 1：分流

按 `/triage` 的做法分流，但**事实由 Codex 取证，决定按下面的预设走**。

- 按组跑 `codex exec -s read-only`，取证内容为：现象在当前 main 上是否还在、根因在哪个 `file:line`、受影响面有多大、修复需要动哪些模块。取证结果写进各票 `## Comments`，以"2026-10-09 分流"开头。
- 套用预设决定后，按结果把 `Status` 改成 `ready-for-agent`、`wontfix`、`duplicate` 或 `needs-info`。设为 `ready-for-agent` 的票，票面要补上"验收"勾选框和"主要模块"。
- 不在预设范围内的领域决定，**攒成一批，一次性问用户**（AskUserQuestion，一次最多 4 题）。等用户回答的同时，先推进其他已就绪的票。

### 分流池与预设决定（8 张票＋时效口径一项）

| 票 | 取证要点 | 预设决定 |
|---|---|---|
| [0928/11](../run-findings-20260928/issues/11-tests-reach-network.md) 测试访问外网 | `tests/conftest.py` 已有 `_network_offline`，9/29 离线全套已通过；确认第三轮全套里没有 `network_offline_in_tests` 失败 | 已经实施完、只是状态没改：勾选、补 Comments，改为 `done`。票里列的三个"提速候选"并入票 24 的诊断，不另开票 |
| [1002/03](../run-findings-20261002/issues/03-czce-warrant-ssl-failures.md) 郑商所 SSL | 查运行库：10/03 以来的运行（含三轮验收）是否还有郑商所 SSL 失败的回执，以及 `CN_FUTURES_WARRANTS` 是否进过缺口清单 | 没再出现 → `wontfix`（ADR-0032 规定下一轮补取未持有的日子，这已经覆盖了）；再次出现 → `ready-for-agent`：对传输层可恢复的 SSL 错误做有界重试（每日每品种最多 2 次，退避；外部调用保持串行） |
| [1002/04](../run-findings-20261002/issues/04-czce-acquisition-time-invalid.md) 回执时间倒退 | 测 Windows 和 WSL 的时钟偏差；查 10/03 以来 `acquisition_time_invalid` 的回执；查 CF 失败为什么会连带 TA（`czce_warrants.py:434`） | 拆成两部分处理。(a) CF 失败不再连带 TA：ADR-0032 本来就规定按品种逐日拒收，所以直接 `ready-for-agent`；(b) 时钟回跳的代码层防护会改变证据时间的语义，**问用户**，推荐方案是"回执时间单调递增，靠进程内单调时钟锚定墙钟来保证" |
| [1002/05](../run-findings-20261002/issues/05-rejected-candidate-overrides-held-target.md) 被拒候选改判 | 在第三轮验收的缺口清单里，看是否还有"已持有目标期却列为 `retrieval_failed`"的指标 | 没有了 → `done`（票 01 已修复，写明证据）；还有 → `ready-for-agent`：候选失败的分类只对应仍未解决的那一期（`freshness.py` 一带） |
| [1002/11](../run-findings-20261002/issues/11-first-retrieval-plan-before-run-calendar.md) 首次规划早于运行日历 | 票 12（2a3935f）改了判定日历以后，首次 `_plan` 是否仍然用工作日日历 | 仍然用 → `ready-for-agent`：首次规划前先装入判定日历，口径同票 12。走 `/diagnosing-bugs`：替身是"9/28 判定融资余额、人民币收盘价，最新发布期应为 9/24" |
| [1002/12](../run-findings-20261002/issues/12-scheduler-skips-only-weekends.md) 调度只排除周末 | `worker.py` 的盘后计划 | `ready-for-agent`：按上交所日历判断当天是否开市；日历没覆盖到的日子按工作日推定，与票 12 口径一致。调度默认关闭，优先级低 |
| [lookback/24](../lookback-fetch-gaps-20261008/issues/24-test-feedback-too-slow.md) 测试反馈过慢 | 第三轮全套 `--durations` 与慢文件分布；完整运行级替身的建库、迁移、Worker 编排各占多少 | `ready-for-agent`，但**不走普通实施**：先用 `/diagnosing-bugs` 找到慢在哪里（反馈环是可重复的计时命令）；结论若是测试结构没有好的切入点，再按 `/improve-codebase-architecture` 的做法（codebase-design 词汇）提出加深方案。涉及 ADR-0025 分层调整的属领域决定，问用户 |
| [lookback/26](../lookback-fetch-gaps-20261008/issues/26-ai-websearch-claims-lack-subject-context.md) AI 原话缺主语上下文 | 运行库 35 条 `ai_websearch` 声明中，原话自带"全国／我国／国家统计局"的有几条、被选中的有几条；各方案会丢掉多少现有选值 | 方案选择属领域决定，**问用户**。推荐"只认原话自带全国信号的 AI 值"（离线、零额外请求，符合"宁可误丢全国值，不让地方值混入"） |
| 时效口径（[第三轮验收第五节](../lookback-fetch-gaps-20261008/acceptance-20261009-round3.md)） | 历史目标日晚间重跑时，日频时效按运行截止点判定，20 项由 `awaiting_release` 变 `stale`，人民币 16:30 收盘价落后 2 期而退出模型输入；查该口径出自哪条 ADR／规格，改成"按目标日收盘判定"要动哪些模块 | 口径属领域决定，**问用户**。分流结论落在新开票 lookback/27（`needs-triage` → 按用户决定） |

另外顺手修正 [run-findings-20261002 README](../run-findings-20261002/README.md) 票表里过时的状态：06 已在 lookback 批次完成（693db3f），10 作为 duplicate 并入 lookback 02。

## 阶段 2：实施

模块不重叠的票并行，按任务线组织。分流结束后，主 agent 按实际的 `ready-for-agent` 票删减下表：

| 线 | 位置 | 顺序 | 主要模块 |
|---|---|---|---|
| A | 主工作区、共享 `dev-venv` | 1002/11 → 1002/05 → 1002/12 → 时效口径（lookback/27，用户决定后） | `full_retrieval.py`、`trading_calendar.py`、`freshness.py`、`worker.py`、`context_projection.py` |
| B | worktree（`dev-venv-czce`） | 1002/04(a) → 1002/04(b，用户批准后) → 1002/03 | `czce_warrants.py`、`acquisition.py`、郑商所传输 |
| C | worktree（`dev-venv-news`） | lookback/26（用户决定后） | `news_rules.py`、AI WebSearch 候选入库、`claim_adoption` 复核 |
| D | worktree（`dev-venv-tests`） | lookback/24：先诊断，后按结论实施 | `tests/` 夹具与替身、`check.py`、`docs/agents/testing.md` |

- **每张票一个新的命名子代理**，上下文从零开始（相当于每张之间 `/clear`），按 `/implement` 的做法：读票 → 受影响测试 → 实现 → Codex 两轴审查 → 提交。同一线内逐张串行，前一张合入后再派下一张。
- 线 D 与其他线都可能动 `tests/conftest.py`：D 的改动最后合入，合入前 rebase 并复跑受影响测试；D 若需要改生产代码的测试接缝，先回报主 agent。
- bug 票先拿到一条能稳定变红的命令再修（`/diagnosing-bugs`），其余走 TDD；每票都按单票规程完成"Codex 两轴审查 → 提交"。
- 重型测试、`check.py full`、真实运行一律加 `flock /tmp/pring-heavy.lock`。
- worktree 分支收尾按 goal-round2.md 的流程：rebase main，重装 venv，复跑受影响测试，回报分支名，由主 agent 执行 `git merge --ff-only`。

## 阶段 3：收尾验收

所有实施票合入后，新建 `issues/01-acceptance.md`（被全部实施票阻塞），派一个子代理执行：

1. 重装 dev-venv，跑一次 `check.py full`（带 `disk_guard.sh … 12`），子代理前台守到结束。
2. 如果本批合入了 1002/05、1002/11 或时效口径改动：用 v0015、目标日 2026-09-30，做一次真实完整运行（外部调用串行，带 C 盘保护），并记下这是当日第几次运行。
3. 以第三轮验收（票 25）为基线，逐项对照：各实施票的验收项是否成立，缺口清单、模型输入缺失数、17 项计数指标完整数有没有退化，全套和真实运行的耗时。
4. 把验收记录写进本目录 `acceptance-<日期>.md`，过 Codex 两轴审查，更新票面、各 README 和本文件进度表，提交。
5. 更新记忆：本批结论，以及下一步回到界面重规划主线（`ui-replan-20261003/decisions.md`：报告式首页原型 → `/to-spec`）。

如果本批没有任何票合入（全部 `wontfix`、`done` 或 `needs-info`），跳过阶段 3，只做第 5 步。

## 何时停下来问用户

- 预设决定之外的领域决定，以及 1002/04(b)：攒成一批再问，不要逐条打断。
- 某张票经过两轮审查后，仍有不属于"修复确认"的阻断。
- 出现与本批无关的测试失败，且无法判断是不是原有问题。
- C 盘余量低于 20G；TuShare 额度耗尽，或外部来源大面积不可用；真实运行因代码缺陷失败，修一次后仍然失败。

除此之外不停顿，按依赖关系一直推进到终点。

## 进度

| 阶段 | 票 | 状态 | 提交 |
|---|---|---|---|
| 1 | 分流（8 张＋时效口径） | 未开始 | |
| 2 | 实施 | 未开始 | |
| 3 | 收尾验收 | 未开始 | |
