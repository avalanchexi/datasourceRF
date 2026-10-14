# 目标：目录全部口径的真正缺失归零（2026-10-14 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 08–13（01–07 是来源票，由 08–13 落实，不单独实施）。
**集成分支**：`input-gap-residuals`（基于 `recurring-input-gaps` `006e7d0`），worktree `/home/tywin/worktrees/datasourceRF-igr`（主 agent 在此合入；主工作区 `/mnt/d/cursor/datasourceRF` 不动）。全部票合入并验收后再由用户决定并入去向。
**终点**：08–13 全部 `done` 并合入集成分支；集成分支经代码审查、问题修复；README、本文件进度表、记忆已更新。

## 任务图

08、09、10、11 并行 → 12（需 09）→ 13（需 08–12，及用户调好电源设置）。
09 选定来源后**停下回报**，用户确认后再实施（票面 `needs-info`，不合入）。

## 沿用

- 单票执行规程与沿用口径：[lookback goal.md](../lookback-fetch-gaps-20261008/goal.md)“单票执行规程”“沿用口径”（第 3 步按 `tdd` 技能做；提交尾行只用 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`，不加 Claude-Session 行）。
- worktree 与合入：[上一批 goal.md](../recurring-input-gaps-20261013/goal.md)“并行规则”，基线改为本批集成分支 `input-gap-residuals`。
- 体检线规程（10、12）：[体检 goal.md](../data-quality-audit-20261010/goal.md)“线 B 的差异规程”——只用标准库、不导入生产代码、运行库只读、规则只依据文档、以实跑对账为准。
- 测试执行：`docs/agents/testing.md`（ADR-0025）。
- 审查：两轴各一次 `codex exec -s read-only … < /dev/null`；两轮仍阻断即停并上报。

## 并行规则

- 每个 worktree 用自己的 venv：`~/.local/share/pring-cycle/dev-venv-rig<票号>`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-rig<票号>`；从 `src/` 导入调试加 `PYTHONDONTWRITEBYTECODE=1`。
- 重型测试（`HEAVY_FILES`、`test_worker_registered_catalog.py`、`test_core_carry_forward.py`）一律 `flock /tmp/pring-heavy.lock`。
- **外部调用一律 `flock /tmp/pring-external.lock`**（08、09 的调查与探测），一次一个请求、取到即停；有真实运行在跑时不调。
- 开工前确认 worktree 基于集成分支：`git merge-base --is-ancestor input-gap-residuals HEAD`，否则 `git reset --hard input-gap-residuals`。
- 收尾：`git merge input-gap-residuals` → 重装本 worktree venv → 复跑受影响测试 → 回报分支名与提交号；主 agent 在集成 worktree `git merge --ff-only`。
- 票面状态与 Comments 只在**本票分支**上改（随合入进入集成分支）；不改主工作区。
- 除 13 外**不启动 Worker、不做真实运行**；体检实跑只读运行库。
- 耗 token 的只读调查用 `codex exec -s read-only -C <worktree> --skip-git-repo-check "…" < /dev/null`（Codex 沙箱无外网，外部探测自己做）。

## 何时停下来问用户

规格、GLOSSARY.md、ADR 都未覆盖的领域选择（票面 `needs-info`，先按推荐实现、不合入，回报主 agent）；09 的来源选择；两轮审查仍阻断；与本批无关又无法判断来源的测试失败；C 盘余量低于 20G。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 08 16:30 收盘价上一交易日 | done（货币网无按日期历史接口，走退路：Worker 开市日 16:35–21:00 单取一次；两轴审查 4 条阻断已修、复审无阻断；用户 10-14 决定加次晨补取：当晚未持有则次晨 0:00–09:30 前取前一交易日，定向复审 2 条阻断已修；遗留：当晚与次晨都不在线则补不回、周末未入日历时周一多一次请求） | bd6dbe4、4db013d |
| 09 SOX 取数路径 | 实施中（TuShare 无 SOX；用户 10-14 选 Nasdaq 指数官网，接受无文档接口与禁止抓取条款的风险） | 2bb9b25（调查） |
| 10 体检新口径生效时刻 | done（两运行对账：25ac18e4 逐字一致；0a8dabc2 差异全来自留存清理；新分支以临时副本插桩验证，实证待 13） | ff2bb47、92b74da |
| 11 降准回溯截止可读性 | done（读不到的期刊跳过并不计 covered_through；两轴无阻断；遗留：无声明期刊仍只按栏目日期） | 727b509、15e021c |
| 12 体检 SOX 口径 | 待 09 | |
| 13 收尾验收 | 待 08–12、电源设置 | |
