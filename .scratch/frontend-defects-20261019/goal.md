# 目标：前端缺陷 20261019

**来源**：10-19 上线后浏览器核对与 Codex 调查（[investigation.md](investigation.md)）；用户决定见宏观判断批次 decisions.md 决定 34 与 2026-10-19 会话（Q6：卡内图加高约 240px、横轴每月一刻度；Q36：家数方向与近 5 日矛盾、③ 三卡"—"并入本批）。先修先上，不等 v0016。分支前缀 `fd`。

## 单票规程

1. **worktree**：从 `main` 最新头建分支 `fd-NN` 与 worktree `/home/tywin/worktrees/datasourceRF-fd-NN`。
2. **读**：本票、本目录 investigation.md（Codex 只读调查，含 file:line 与库中证据）、`docs/agents/testing.md`、AGENTS.md、GLOSSARY.md 相关词条。
3. **环境**：独立 venv `~/.local/share/pring-cycle/dev-venv-fdNN`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-fdNN`，`PYTHONDONTWRITEBYTECODE=1`；不碰正式 `dev-venv`、正式库与调度；正式环境有常驻 Worker（不要停它、不要另起 Worker）；不调外部接口（离线测试替身）。
4. **实施**：调用 Skill `mattpocock-skills:tdd`；只跑受影响测试（`python tools/check.py quick <文件>`），重型文件在 `flock /tmp/pring-heavy.lock` 下；收尾两例冒烟。
5. **收尾**：合并 main 最新头并复跑受影响测试；票面勾选、Comments 记测试命令与结果；`Status: done`；英文提交信息带 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`；不 push、不合入 main。回报主 agent：分支、提交号、测试、偏离。
6. **合并**：主 agent 核验后合入 main；集成票统一做全套与上线。

## 进度

| 票 | 状态 | 执行者／分支 |
|---|---|---|
| 01 线图 | done（05fbc03，快进合入 main；首月不打刻度） | ticket-fd01／fd-01 |
| 02 较上期方向 | 进行中（22:2x 派出） | ticket-fd02／fd-02 |
| 03 | 待派 | — |
| 04 | ready-for-human | — |
