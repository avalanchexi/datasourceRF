# 收尾长任务（2026-10-20 起）

来源：会话 e67d4ad6 末尾的"长任务规划（推荐方案）"，用户 10-20 09:28 设为目标，按阶段 1–5 推进。阶段 6 复盘已于 10-20 在原会话完成（结论见本文末"复盘待定项"，不在本目标内）。

执行方式：主 agent 只调度与核验；每件事派一个命名子代理或交 Codex（只读调查 `codex exec -s read-only`，浏览器核对 Codex `-s workspace-write -C <scratchpad 子目录>` + Playwright）。后台长任务挂 CronCreate `7,22,37,52 * * * *` 每 15 分钟汇报一次。外部调用串行；重型测试走 `flock /tmp/pring-heavy.lock` + `tools/disk_guard.sh`。

进度记录：每个阶段结束时在下方"进度"写一行（时间、结论、产物路径）。

## 完成标准

整个目标完成 = 阶段 1–5 每一项都处于下面两种状态之一：
- **已完成**：满足该阶段的完成标准，并在"进度"记了一行；
- **等用户**：仅剩用户本人才能做的决定或操作（triage 调用、问答、删除清单批准、上线确认），已在对话里把问题完整列给用户，并在"进度"写明在等什么。

### 阶段 1 运行后核对
- 等 v0016 生效后的第一次成功运行（目标日 ≥ 2026-10-20；今天 09:30 若因目标日 10-19 已完成而不跑，则等 10-21 09:30）。
- 核对：① 标题与滞后初值、⑥ 第一格、报告校验通过、提示词约 71KB 全部送达（审计里的 `prompt_bytes_sent`）；用 `tools/quality/audit.py` 体检，重点看 2025-09 贷款、GDP、信用脉冲、债券指数；前端缺陷 03 在新投影上的显示。
- 完成标准：核对结果写入 `.scratch/wrapup-20261020/phase1-run-check.md`；全部通过则把宏观 10、上线遗留 07、前端缺陷 04 改为 done；有不通过的项列出原因并给用户。

### 阶段 2 关旧验收票
- 范围：ui-rebuild-20261015 01–13、conclusion-board-20261016 07、cockpit-layout-20261016 10/15、worker-gap-fixes-20261017 07。
- Codex 按各票验收清单在 8069 正式驾驶舱上逐项核对（已被后续批次改掉的条目按现行规格判定）。
- 完成标准：结果写入 `.scratch/wrapup-20261020/phase2-acceptance.md`，逐票逐项标通过／不通过／已被取代；通过的票改为 done；不通过的项列给用户。

### 阶段 3 积压分流
- 范围：model-rules-residuals-20261013 01–08、recurring-input-gaps-residuals-20261014 01–07（共 15 张）。
- 先由 Codex 只读预审：哪些已被后续工作解决或取代（附提交或代码证据）。
- 已被取代或已解决的，直接标 done 并注明取代者；其余的分流由用户调用 `/mattpocock-skills:triage` 进行（这个技能只能由用户调用）。
- 完成标准：预审写入 `.scratch/wrapup-20261020/phase3-pretriage.md`，可直接关闭的已关闭；剩余票的清单与建议已给用户，等用户调用 triage。

### 阶段 4 后续开发
- 宏观 11（⑥ 宏观区间抽屉）、12（股市广度和商品篮子单日测试）：子代理 tdd 实施 → Codex 两轴审查 → 修复 → 受影响测试与全套通过 → 用户确认后并入 main 并重装正式环境。
- 上线遗留 06：只把要访谈的问题列进票里，不实施（以后用 grill-with-docs）。
- 单票规程：同 `.scratch/golive-leftovers-20261019/goal.md`"单票规程"，替换为分支 `ms-11`／`ms-12`、worktree `/home/tywin/worktrees/datasourceRF-ms-11`／`-ms-12`、venv `dev-venv-ms11`／`dev-venv-ms12`、basetemp `/tmp/pytest-ms11`／`/tmp/pytest-ms12`；票目录 `.scratch/macro-stage-20261017`。
- 10-20 追加：13–16 与审查修复同属本阶段，与 11、12 一起经集成分支 macro-followups 全套、用户确认后上线。
- 完成标准：11–16 状态 done 且已并入 main（或已通过全部测试、只等用户确认上线）；06 的问题清单已写入票。

### 阶段 5 环境清理
- 在阶段 4 并入后进行。删已合并的 worktree 与分支、测试用 venv、/tmp 残留；保留正式环境、正式库、最近 3 份备份、原型分支 `prototype/macro-stage`。
- 删除前把清单写入 `.scratch/wrapup-20261020/phase5-cleanup-list.md` 给用户批准；分支一律 `git branch -d`。
- 完成标准：用户批准的清单已执行完，清理前后磁盘余量记入进度；或清单已给出、等用户批准。

## 当前状态（2026-10-20 16:05，用户 15:48"全部确认"推荐方案后）

| 阶段 | 状态 | 说明 |
|---|---|---|
| 1 运行后核对 | 已完成 | phase1-run-check.md；宏观 10 已于上线后补生成报告通过并关闭 |
| 2 关旧验收票 | 已完成 | 关 ui-rebuild 01–13、conclusion-board 07、cockpit-layout 10/15；worker-gap-fixes 07 清单 1–3 用户接受，清单 6 待 10-21 运行发布后复核（宏观 15 已上线），复核由 10-21 定时任务进行 |
| 3 积压分流 | 等用户 | 已关 6 张；剩 9 张由用户方便时调用 `/mattpocock-skills:triage`（用户确认"这次不动"） |
| 4 后续开发 | 已完成 | macro-followups 并入 main（f3fb425），正式环境重装并逐文件核对，Worker 与 8069 重启（8069 写 PID 文件），10-19 报告补生成 codex_cli 成功；浏览器复核见进度 |
| 5 环境清理 | 已完成 | phase5-cleanup-list.md 执行记录；D 组按推荐保留 |

## 进度

- 2026-10-20 09:30 写入目标文件，开始。
- 09:50 阶段 3 预审完成（phase3-pretriage.md）：已关闭模型残余 01、缺口残余 01/02/05/06；缺口 04 待今天运行完成后关闭；其余 9 张（模型 02–08、缺口 03、07）等用户调用 triage。
- 09:50 阶段 4：上线遗留 06 的 5 个访谈问题已写入票；ms-11、ms-12 子代理实施中。
- 09:30 今天调度运行 run-3ebbe323（目标日 10-19，model-v0016）即 v0016 生效首个运行，阶段 1 待其完成后核对。
- 10:03 今天运行 run-3ebbe323 完成（v0016 首个投影 projection-59421326）：主结论第三阶段（倾向，3/5 维），提示词 70,650 B 全部送达；但 AI 报告两适配器均被 macro_stated_stage 校验拒绝、退模板 → Codex p1a 查根因，p1b 体检，p1c 浏览器核对。
- 10:15 阶段 2 Codex 核对完成（phase2/ 两份报告，119 项：通过 84、不通过 1、已被取代 24、无法核对 10）：已关 ui-rebuild 01–08、10，cockpit-layout 15。待用户：ui-rebuild 09/11/12（真实生命周期与测试退出码项，建议凭 10-20 全套 2920 过＋真实运行关闭）、ui-rebuild 13／conclusion-board 07／cockpit-layout 10（关口 C 用户签收）、worker-gap-fixes 07（清单 1–3 用户判断；清单 6 债券观察指数缺期未列缺口，待新投影复核）。
- 10:15 阶段 4：ms-12 完成（174e6c9，仅测试；偏离：宏观数据未放 v0006，主结论走弱判断兜底）。
- 10:45 阶段 1 核对完（phase1-run-check.md）：数据四项全部恢复；关上线遗留 07、前端缺陷 04、缺口残余 04。宏观 10 待报告校验修复上线后的下一次运行再关。发现：AI 报告校验误拒 → 宏观 13；体检不认 v0016 字段 → 14；⑦ 完整度对不上缺口清单 → 15；"正式阶段"残留与拒收原因写法 → 16（均在集成分支 macro-followups 开票）。
- 10:45 阶段 4：11、12 已并入 macro-followups（fb824ee、ba845dc），Codex 两轴审查完成（R1–R5 → ms-rf）；子代理 ms-13、ms-14、ms-15、ms-16、ms-rf 并行实施。
- 13:00 阶段 4：macro-followups 已合入 11–16 与第一轮审查修复（头 7001550）；第二轮审查（13–15）两项阻断（条件作用域、双重否定）→ ms-rf2a，完整度严格对账等 → ms-rf2b，票 16 审查小修 → ms-rf2c，修完复审再跑全套。
- 13:55 阶段 4：macro-followups 已合入全部修复（rf2a、rf2b、rf2c、rf3a；头 25b4759）；报告校验第三轮以 42 句探针收口（残余风险两条记在 review-fixes-20261020-r2.md）。全套开跑（full/，dev-venv-mf），rf2b 复审（Codex）同时进行。
- 15:40 阶段 4：全套 3036 passed（13:52–15:37，头 25b4759，full/）；rf2b 复审无阻断，唯一应改由 ms-rf4 修复并合入（90d99ed），受影响页面测试 15 passed。上线步骤写入 golive-plan.md，等用户确认。
- 15:50 各阶段状态：
  - 阶段 1：已完成（宏观 10 待上线后补生成 10-19 报告通过再关，归入阶段 4 上线步骤 6）。
  - 阶段 2：已关 10 张；等用户：ui-rebuild 09/11/12 是否凭全套与真实运行关闭、关口 C 签收（ui-rebuild 13、conclusion-board 07、cockpit-layout 10）、worker-gap-fixes 07 清单 1–3。
  - 阶段 3：已关 6 张；等用户调用 `/mattpocock-skills:triage` 分流剩余 9 张。
  - 阶段 4：全部通过测试，等用户回复"上线"（golive-plan.md）。
  - 阶段 5：清单已给出（phase5-cleanup-list.md），等用户批准；B 组待上线后。
- 15:48–16:05 用户确认推荐方案后执行：停 Worker/8069（按 PID）→ 备份 before-macro-followups-20261020（integrity ok，0039）→ 并入 main f3fb425 → 重装 dev-venv（首次 uv sync 未换副本，加 --reinstall-package 后 153 文件一致）→ init ok → 重启 Worker（pid 907339）与 8069（pid 907336，web-8069.pid）→ 补生成 10-19 报告 report-7e4ac01e v4 codex_cli succeeded（70,650 B 全送达）→ 关宏观 10 → 关阶段 2 旧票 → 清理 A、B 组。

## 复盘待定项（不在本目标内）

原会话复盘提出 9 条环境改进：小改动（src 字节码检查、全套临时目录自动清理、合并前确认分支头不再变化且用 `-d` 删分支、8069 写 PID 文件）可合成一张票；测试依赖真实时间需单开票；pre-commit 钩子、`docs/agents/subagent-dispatch.md`、文档提交到 main 的约定、`CODING_STANDARDS.md` 等用户过目后再落地。
