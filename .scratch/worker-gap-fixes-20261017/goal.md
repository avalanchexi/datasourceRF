# 目标：⑦ 暴露的 Worker 缺陷修复（2026-10-17 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–07；决定见 [decisions.md](decisions.md)；根因（含 file:line，行号以 ed477be 为准）见 [investigation.md](investigation.md)。
**集成分支**：`worker-gaps`（基于 `cockpit-layout`），集成 worktree `/home/tywin/worktrees/datasourceRF-wg`。主工作区 `/mnt/d/cursor/datasourceRF` 不动。
**终点**：01–06 `done`，07 `ready-for-human`；集成分支经审查并修复；本文件进度表与记忆已更新。

## 任务图

01、05、06 立即并行；02、03、04 等 A 批次票 13（⑦ 原因码中文对照表，在 `wording` 模块）合入 `cockpit-layout` 后，`worker-gaps` 合入 `cockpit-layout` 再开工；全部 → 07。

## 单票执行规程（实施子代理照做）

1. **worktree**：`git -C /home/tywin/worktrees/datasourceRF-wg worktree add -b wg-<票号> /home/tywin/worktrees/datasourceRF-wg-<票号> worker-gaps`；已存在则确认 `git merge-base --is-ancestor worker-gaps HEAD`，否则 `git reset --hard worker-gaps`。之后只在该 worktree 内工作。
2. **读**：票文件、`spec.md`、`decisions.md`、`investigation.md`、`docs/agents/testing.md`、`GLOSSARY.md` 相关术语（等待发布、价格阶段等）、相关 ADR（ADR-0034 单日汇总测试缝、ADR-0003 AI 不参与判定）。只读调查量大时用 `codex exec -s read-only -C <worktree> --skip-git-repo-check "…" < /dev/null`，不开 Claude 子代理。
3. **领取**：票面 `**Status:** ready-for-agent` 改为 `claimed`。
4. **TDD**：调用 Skill 工具 `tdd`；先写会失败的测试再实现，一次一个红→绿切片。测试缝按规格"测试决定"四个：完整运行（Worker 执行集成测试）、单日汇总、报告入口、首页渲染 `dashboard_page`；断言外部行为，不断言内部函数。外部页面用 10-15 隔离副本 `/tmp/pring-cb-real-20261016` 里存下的原件复制成测试夹具（放进 `tests/` 下的夹具目录），测试不访问外网、不读隔离副本路径。
5. **环境**：venv `~/.local/share/pring-cycle/dev-venv-wg<票号>`，改 `src/` 后重装：
   `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv-wg<票号> uv sync --extra dev --no-editable --reinstall-package pring-cycle`
   测试：`$VENV/bin/python tools/check.py quick <具体文件或 node>`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-wg<票号>`；从 `src/` 直接导入调试加 `PYTHONDONTWRITEBYTECODE=1`。完整运行类集成测试、重型测试与两项必跑冒烟一律 `flock /tmp/pring-heavy.lock`。
6. **验证**：受影响用例 → 两项必跑冒烟（testing.md）→ 改动文件 `ruff check`、`ruff format --check`、`mypy`。失败如实记录，不删必要测试。
7. **收尾**：`git merge worker-gaps`（并入集成分支最新）→ 重装 venv → 复跑受影响测试；勾选有证据的验收框；票面 `## Comments` 追加"### 2026-10-17 实施"（改了什么、测试与耗时、遗留）；`Status: done`。票面只在本票分支上改。
8. **提交**：只 `git add` 本票相关文件；英文提交信息（一句话标题＋简短正文），末尾：

   ```
   Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01TqrJbWW3thDiX894Wez2xp
   ```

9. **回报**（中文，精炼）：分支名与提交号、改动要点、测试结果与耗时、遗留；需用户决定的问题写进票面并 `Status: needs-info`，不合入。

## 约束

- 不启动 Worker、不做真实运行、不调用真实 AI 适配器与外部接口；完整运行只在测试里用夹具。
- 不改正式安装 `dev-venv`、正式库与调度；不动 8065–8068 现有预览。
- 不新建模型版本（决定 3）；不改预期表；不改 `freshness` 的 current/stale 二值（等待发布只是缺口清单分组）。
- ⑦ 新增原因文案加在 A13 建的 `wording` 对照表里，一处维护。
- 规格、词汇表、ADR 未覆盖的领域选择：按推荐实现并在票面 Comments 记录，回报主 agent。
- C 盘余量低于 20G 时停下。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 01 中间价取得 | 实施中 | wg-01 |
| 02 社融门禁按成员 | 等 A13 | — |
| 03 等待发布分组 | 等 A13 | — |
| 04 仓单历史缺期 | 等 A13 | — |
| 05 AI 报告中文名 | 实施中 | wg-05 |
| 06 确认度第二阶段报错 | 实施中 | wg-06 |
| 07 集成验收 | 等 01–06 | — |
