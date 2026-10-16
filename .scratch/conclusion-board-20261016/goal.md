# 目标：结论板对齐 Claude 方案 ①（2026-10-16 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–07。
**集成分支**：`conclusion-board`（基于 main `012f362`），集成 worktree `/home/tywin/worktrees/datasourceRF-cb`。主工作区 `/mnt/d/cursor/datasourceRF` 不动；全部票合入并验收后由用户决定并入 main。
**终点**：01–07 全部 `done`（07 中需用户确认的项除外，标 ready-for-human）；集成分支经 Codex 代码审查、问题修复；本文件进度表与记忆已更新。

## 任务图

01、02 并行 → 03（需 01）、05（需 01）并行 → 04（需 03）→ 06（需 02、04）→ 07（需全部）。

## 单票执行规程（实施子代理照做）

1. **worktree**：`git -C /home/tywin/worktrees/datasourceRF-cb worktree add -b cb-<票号> /home/tywin/worktrees/datasourceRF-cb-<票号> conclusion-board`；已存在则确认 `git merge-base --is-ancestor conclusion-board HEAD`，否则 `git reset --hard conclusion-board`。之后只在该 worktree 内工作。
2. **读**：票文件、`spec.md`、`decisions.md`、前置批次 `../ui-rebuild-20261015/spec.md` 与 `testing-analysis.md`、`docs/agents/testing.md`、`CONTEXT.md`/`GLOSSARY.md` 相关术语、已合入的前置票提交。只读调查量大时用 `codex exec -s read-only -C <worktree> --skip-git-repo-check "…" < /dev/null`，不开 Claude 子代理；可复用的调查笔记写入共享目录 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/notes/`。
3. **领取**：票面 `**Status:** ready-for-agent` 改为 `claimed`。
4. **TDD**：调用 Skill 工具 `tdd`；先写会失败的测试再实现，一次一个红→绿切片。测试缝只有首页渲染函数（规格"测试决定"），断言用户可见文本、链接与顺序。
5. **环境**：venv `~/.local/share/pring-cycle/dev-venv-cb<票号>`，改 `src/` 后重装：
   `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv-cb<票号> uv sync --extra dev --no-editable --reinstall-package pring-cycle`
   测试：`$VENV/bin/python tools/check.py quick <具体文件或 node>`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-cb<票号>`；从 `src/` 直接导入调试加 `PYTHONDONTWRITEBYTECODE=1`。重型测试与两项必跑冒烟一律 `flock /tmp/pring-heavy.lock`。
6. **验证**：受影响 Web 用例 → 两项必跑冒烟（testing.md）→ 改动文件 `ruff check`、`ruff format --check`、`mypy`。失败如实记录，不删必要测试。
7. **收尾**：`git merge conclusion-board`（并入集成分支最新）→ 重装 venv → 复跑受影响测试；勾选有证据的验收框；票面 `## Comments` 追加"### 2026-10-16 实施"（改了什么、测试与耗时、遗留）；`Status: done`。票面只在本票分支上改。
8. **提交**：只 `git add` 本票相关文件；英文提交信息（一句话标题＋简短正文），末尾：

   ```
   Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01TqrJbWW3thDiX894Wez2xp
   ```

9. **回报**（中文，精炼）：分支名与提交号、改动要点、测试结果与耗时、遗留；需用户决定的问题写进票面并 `Status: needs-info`，不合入。

## 约束

- 不启动 Worker、不做真实运行、不调用真实 AI 适配器与外部接口；票 07 只用隔离副本。
- 不改正式安装 `dev-venv`、正式库与调度。
- 规格、词汇表、ADR 未覆盖的领域选择：按推荐实现并在票面 Comments 记录，回报主 agent。
- C 盘余量低于 20G 时停下。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 01 用词统一 | 待派 | |
| 02 顶栏与运行摘要 | 待派 | |
| 03 左栏 | 阻塞（01） | |
| 04 右栏 | 阻塞（03） | |
| 05 三核心表九列 | 阻塞（01） | |
| 06 板底事实行 | 阻塞（02、04） | |
| 07 集成验收 | 阻塞（全部） | |
