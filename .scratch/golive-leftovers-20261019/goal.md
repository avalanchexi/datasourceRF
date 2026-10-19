# 目标：上线遗留 20261019

**来源**：10-19 上线运行 run-153de306 的体检（.scratch/golive-20261019/audit-run-153de306.md）与 Codex 根因调查（[investigation.md](investigation.md)）。用户 2026-10-19 确认按此拆票。分支前缀 `gl`。**01 最急**（不修则每天 09:30 的 AI 报告都会超时退模板）。

## 单票规程

1. **worktree**：从 `main` 最新头建分支 `gl-NN` 与 worktree `/home/tywin/worktrees/datasourceRF-gl-NN`。
2. **读**：本票、本目录 investigation.md（Codex 只读调查，含 file:line 与库中证据）、`docs/agents/testing.md`、AGENTS.md、GLOSSARY.md 相关词条。
3. **环境**：独立 venv `~/.local/share/pring-cycle/dev-venv-glNN`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-glNN`，`PYTHONDONTWRITEBYTECODE=1`；不碰正式 `dev-venv`、正式库与调度；正式环境有常驻 Worker（不要停它、不要另起 Worker）；不调外部接口（离线测试替身）。
4. **实施**：调用 Skill `mattpocock-skills:tdd`；只跑受影响测试（`python tools/check.py quick <文件>`），重型文件在 `flock /tmp/pring-heavy.lock` 下；收尾两例冒烟。
5. **收尾**：合并 main 最新头并复跑受影响测试；票面勾选、Comments 记测试命令与结果；`Status: done`；英文提交信息带 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`；不 push、不合入 main。回报主 agent：分支、提交号、测试、偏离。
6. **合并**：主 agent 核验后合入 main；集成票统一做全套与上线。
## 进度

| 票 | 状态 | 执行者／分支 |
|---|---|---|
| 01 CLI 写入 | done（ddbba45，快进合入 main） | ticket-gl01／gl-01 |
| 03 回看重展 | done（gl-03，待主 agent 核验合入） | ticket-gl03／gl-03 |
| 04 指数范围 | 进行中（23:1x 派出） | ticket-gl04／gl-04 |
| 02 | 待派 | — |
| 06 | needs-triage | — |
| 07 | ready-for-human | — |
