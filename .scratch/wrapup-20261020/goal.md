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
- 完成标准：11、12 状态 done 且已并入 main（或已通过全部测试、只等用户确认上线）；06 的问题清单已写入票。

### 阶段 5 环境清理
- 在阶段 4 并入后进行。删已合并的 worktree 与分支、测试用 venv、/tmp 残留；保留正式环境、正式库、最近 3 份备份、原型分支 `prototype/macro-stage`。
- 删除前把清单写入 `.scratch/wrapup-20261020/phase5-cleanup-list.md` 给用户批准；分支一律 `git branch -d`。
- 完成标准：用户批准的清单已执行完，清理前后磁盘余量记入进度；或清单已给出、等用户批准。

## 进度

- 2026-10-20 09:30 写入目标文件，开始。

## 复盘待定项（不在本目标内）

原会话复盘提出 9 条环境改进：小改动（src 字节码检查、全套临时目录自动清理、合并前确认分支头不再变化且用 `-d` 删分支、8069 写 PID 文件）可合成一张票；测试依赖真实时间需单开票；pre-commit 钩子、`docs/agents/subagent-dispatch.md`、文档提交到 main 的约定、`CODING_STANDARDS.md` 等用户过目后再落地。
