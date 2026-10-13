# 目标：反复出现的输入缺口（2026-10-13 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–05。
**集成分支**：`recurring-input-gaps`（基于 main `7e321b7`，主工作区所在）。全部票合入并验收后再由用户决定并入 main。
**终点**：01–05 全部 `done` 并合入集成分支；集成分支经代码审查、问题修复；README、本文件进度表、记忆已更新。

## 任务图

01、02 并行 → 03（需 01）→ 04（需 03）→ 05（需 01–04 与[残余票 01](../model-rules-residuals-20261013/issues/01-clock-two-time-syncs-fight.md) 的时钟处置）。
04 的交易所核实（只读、外部访问串行）不依赖 03，先行做，结论落在 `notes/`（见下），04 实施时直接使用。

## 沿用

- 单票执行规程与沿用口径：[lookback goal.md](../lookback-fetch-gaps-20261008/goal.md)“单票执行规程”“沿用口径”（第 3 步按 `tdd` 技能做；提交尾行改为 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`，不加 Claude-Session 行）。
- worktree 与合入：[goal-round2.md](../lookback-fetch-gaps-20261008/goal-round2.md) 第 40–42 行；本批差异是基线为**集成分支** `recurring-input-gaps` 而不是 main。
- 体检线规程：[体检 goal.md](../data-quality-audit-20261010/goal.md)“线 B 的差异规程”——只用标准库、不导入生产代码、运行库只读、规则只依据文档、以实跑对账为准。
- 审查：两轴各一次 `codex exec -s read-only`；两轮仍阻断即停并上报；只剩对上一轮修复的确认时做一次定向复审。

## 并行规则

- 每个 worktree 用自己的 venv：`~/.local/share/pring-cycle/dev-venv-rig<票号>`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-rig<票号>`。
- 重型测试（`HEAVY_FILES`、`test_worker_registered_catalog.py`、`test_core_carry_forward.py`）一律 `flock /tmp/pring-heavy.lock`。
- 开工前确认 worktree 基于集成分支：`git merge-base --is-ancestor recurring-input-gaps HEAD`，否则 `git reset --hard recurring-input-gaps`。
- 收尾：`git merge recurring-input-gaps`（把集成分支最新提交并入本分支）→ 重装 venv → 复跑受影响测试 → 回报分支名与提交号；主 agent `git merge --ff-only` 合入集成分支。
- 本批除收尾验收外**不启动 Worker、不做真实运行**。票 03 验收中“对 01 合入后的一次运行实跑”移到票 05 完成。
- 只读调查量大时用 `codex exec -s read-only ... < /dev/null`（main 56d9daa 起标准命令须带）；可复用的调查笔记写入共享目录 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/3c98b852-8a48-470d-b56a-0661f8b7cfa4/scratchpad/notes/`。

## 何时停下来问用户

规格、GLOSSARY.md、ADR-0041 补写都未覆盖的领域选择（票面 `needs-info`，先按推荐实现、不合入，回报主 agent）；两轮审查仍阻断；与本批无关又无法判断来源的测试失败；C 盘余量低于 20G。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 01 目标日截止与 09:30 | done（用户决定：进行中期次维持旧行为、GLOSSARY 补句；新闻窗口与降准回溯另开票 06） | e264a98、bf7f953 |
| 02 时效按词表 | done（审查无阻断；遗留：词表“应有期”不含宽限 vs 代码 due_period 含宽限，收尾交用户；LPR 行仍显示“等待发布”） | f6d238c、f434114 |
| 04 前置：交易所核实 | done：六格均“来源缺失”（SHFE 07-21 官方原件，主 agent 抽查属实；DCE PP 09-09 仅转载二手证据）；另见 CU/SP/RU 09-09 单日请求 failed（acquisition_time_invalid，疑时钟）待 04 一并核对；报告 notes/warrant-gaps-verification.md | |
| 03 体检新分类 | done（对账：EIA 两项归新分类，真正缺失 9→7，余仓单 6 格＋SOX；第 3 框移票 05；遗留：派生层其他日按该日结束读，建议内置新口径生效时刻） | aa33704、fa344b1、dc87a52 |
| 06 新闻窗口与降准回溯 | done（用户决定回看锚定运行截止；合入审查修复后复跑 101 过、重型 4 过；遗留：官方降准回溯找到即停未复核截止可读性，建议另开票） | 09a97e0、3680205、07294c9、d6b3126 |
| 04 仓单单列 | done（对账：仓单 6 格单列已知历史缺口，真正缺失 1（仅 SOX，目录全部口径）、仅模型用到 0，主 agent 复跑确认；PP 二手证据） | 777e4ce、3fa8b50、1802131 |
| 05 收尾验收 | 第一段进行中（ticket-05：全套→备份→init 0038→21:00 后常驻 Worker）；第二段 10-14 09:30 计划运行后体检与验收记录 | |
| 代码审查与修复 | done：规格轴阻断属实（触发形状：修订在目标日后、截止前入库而公开时间晚于截止），`system_known_by` 修复并有复现用例；两条坏味道已改（`decision_as_of`、`StoredClaim`，体检对账逐字相同）；两轴复审无阻断；记录 review-fixes.md | 6bcb219、f653bc9、d6e3cb1、4f80857、327bf85 |

## 2026-10-13 15:50 并入 main 56d9daa

CONTEXT.md 已改名 GLOSSARY.md（.scratch 内历史引用不改）；新增 `tools/clock_check.py`（全套与真实运行前跑，退出码 0 才开跑）、`tools/disk_guard.sh`、`tools/progress.py`；codex 标准命令末尾须带 `< /dev/null`。
