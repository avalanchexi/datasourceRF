# 目标：驾驶舱布局精简（2026-10-16 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–10；决定见 [decisions.md](decisions.md)。
**集成分支**：`cockpit-layout`（基于 `conclusion-board` 638d125），集成 worktree `/home/tywin/worktrees/datasourceRF-cl`。主工作区 `/mnt/d/cursor/datasourceRF` 不动；验收后由用户决定与 conclusion-board 一起并入 main。
**终点**：01–09 `done`，10 `ready-for-human`；集成分支经 Codex 两轴审查并修复；本文件进度表与记忆已更新。

## 任务图

01 → 02、03、07、08 并行；02 → 04、05、06、09 并行（04、05、06 另需 01）；全部 → 10。

## 共享材料（只读）

目录 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/notes/cockpit-layout/`：
- `names-facts.md`：Codex 调查（各段名称来源与重名、`international_context` 按 P2 收录、`noncanonical_basis` 字段、非典型时成员读法字段、桑基取值全集与标签映射位置），含文件:行号。
- `before/`：改前截图（8067，10-14 投影，1440 宽浅色）。
- `serve_example.py`：只起 Web 的隔离副本起站脚本样例。
可复用的新调查笔记也写入此目录（文件名带票号）。

## 单票执行规程（实施子代理照做）

1. **worktree**：`git -C /home/tywin/worktrees/datasourceRF-cl worktree add -b cl-<票号> /home/tywin/worktrees/datasourceRF-cl-<票号> cockpit-layout`；已存在则确认 `git merge-base --is-ancestor cockpit-layout HEAD`，否则 `git reset --hard cockpit-layout`。之后只在该 worktree 内工作。
2. **读**：票文件、`spec.md`、`decisions.md`、共享材料、前置批次 `../conclusion-board-20261016/spec.md` 与 `../ui-rebuild-20261015/testing-analysis.md`、`docs/agents/testing.md`、`GLOSSARY.md` 相关术语、已合入的前置票提交。只读调查量大时用 `codex exec -s read-only -C <worktree> --skip-git-repo-check "…" < /dev/null`，不开 Claude 子代理。
3. **领取**：票面 `**Status:** ready-for-agent` 改为 `claimed`。
4. **TDD**：调用 Skill 工具 `tdd`；先写会失败的测试再实现，一次一个红→绿切片。测试缝只有首页渲染入口 `dashboard_page` 与数据链路页渲染入口 `data_chain`（规格"测试决定"），断言用户可见文本、链接、顺序与抽屉触发器内容；不断言 CSS。
5. **环境**：venv `~/.local/share/pring-cycle/dev-venv-cl<票号>`，改 `src/` 后重装：
   `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv-cl<票号> uv sync --extra dev --no-editable --reinstall-package pring-cycle`
   测试：`$VENV/bin/python tools/check.py quick <具体文件或 node>`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-cl<票号>`；从 `src/` 直接导入调试加 `PYTHONDONTWRITEBYTECODE=1`。重型测试与两项必跑冒烟一律 `flock /tmp/pring-heavy.lock`。
6. **浏览器自检**（有布局改动的票）：用本票 venv 起只读 Web（参照 `serve_example.py`），端口 `81<票号>`，数据用隔离副本 `/tmp/pring-ui-real-20261015`（10-14 新代码投影）或 `/tmp/pring-cb-real-20261016`（10-15）；不启动 Worker、不发命令。Playwright 可用系统 `python3`（`from playwright.sync_api import sync_playwright`），Dash 页勿用 `networkidle`，用 `domcontentloaded` 加 `wait_for_selector`。截图存本票 scratchpad 子目录，票面写路径与实测值；收尾停掉本票 Web。
7. **验证**：受影响 Web 用例 → 两项必跑冒烟（testing.md）→ 改动文件 `ruff check`、`ruff format --check`、`mypy`。失败如实记录，不删必要测试。
8. **收尾**：`git merge cockpit-layout`（并入集成分支最新）→ 重装 venv → 复跑受影响测试；勾选有证据的验收框；票面 `## Comments` 追加"### 2026-10-16 实施"（改了什么、测试与耗时、遗留）；`Status: done`。票面只在本票分支上改。
9. **提交**：只 `git add` 本票相关文件；英文提交信息（一句话标题＋简短正文），末尾：

   ```
   Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01TqrJbWW3thDiX894Wez2xp
   ```

10. **回报**（中文，精炼）：分支名与提交号、改动要点、测试结果与耗时、遗留；需用户决定的问题写进票面并 `Status: needs-info`，不合入。

## 约束

- 不启动 Worker、不做真实运行、不调用真实 AI 适配器与外部接口；浏览器自检只用隔离副本。
- 不改正式安装 `dev-venv`、正式库与调度；不动 8065–8068 现有预览。
- 只改前端：Worker、投影结构、模型规则、指标目录不动。
- 规格、词汇表、ADR 未覆盖的领域选择：按推荐实现并在票面 Comments 记录，回报主 agent。
- C 盘余量低于 20G 时停下。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 01 抽屉与 ③ 卡片 | done（drawer.py 三函数＋assets/drawer.js 统一开合；③ 名单 OVERSEAS_METRICS 卡片网格；其他背景指标卡；用法见 notes/cockpit-layout/drawer-usage.md） | c3d2158 |
| 02 中文名 | done（wording.display_name 成员项→目录名→指标项→代号；source_name 供 09；row_name/name_cell/name_note；1630 单位元/美元；沪深 300 更正） | d1e04b7、c1837d3 |
| 03 ① 非典型读法 | ready-for-agent | |
| 04 ② 三列资产卡 | ready-for-agent | |
| 05 ④ 两列维度卡 | ready-for-agent | |
| 06 ⑤ 库存精简 | ready-for-agent | |
| 07 ⑥ 区间列表 | ready-for-agent | |
| 08 ⑦ 精简 | done（gap_preview 前 5 条＋查看全部抽屉；report_summary 四态；报告详情与发布日历抽屉；⑦ 段 1838→689px） | 63cd500 |
| 09 桑基图 | ready-for-agent | |
| 10 集成验收 | ready-for-agent | |
