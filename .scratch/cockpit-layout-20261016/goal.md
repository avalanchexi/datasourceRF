# 目标：驾驶舱布局精简（2026-10-16 实施）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–10；决定见 [decisions.md](decisions.md)。
**集成分支**：`cockpit-layout`（基于 `conclusion-board` 638d125），集成 worktree `/home/tywin/worktrees/datasourceRF-cl`。主工作区 `/mnt/d/cursor/datasourceRF` 不动；验收后由用户决定与 conclusion-board 一起并入 main。
**状态（2026-10-17 01:40）**：01–09 与审查修复 done，10 ready-for-human；预览 8067（10-14）、8068（10-15）由 dev-venv-cl10 起站。
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
| 03 ① 非典型读法 | done（只差一项读 noncanonical_basis；非典型右栏一行；转折观察只列反向；缺口抽屉 conclusion-gaps。遗留：tests/integration/test_confirmation_publish.py 两例自结论板批次起即失败，待审查修复时改写） | 7ab64a4、d9fb04d |
| 04 ② 三列资产卡 | done（① 去三核心表加"三核心详见 ②"；② 三卡＋160px 小图＋同类观察限高 320＋行抽屉；价格一致性窄卡；单位家/倍/比值；② 段 ~5005→1321px。遗留：家数两位小数"978.00 家"） | 3d14527、da572cb；合并 5911e74（report.css 冲突两边保留，合并后 tests/web 133 passed） |
| 05 ④ 两列维度卡 | done（confirmation_cards 五卡两列；非典型行写读法＋不计数；指标抽屉含 GDP 分产业 4×2；④ 段 ~1459→746px。遗留：tests/integration 确认相关 4 例旧首页文案断言待票 10 改写；有正式阶段的真实投影未在浏览器核对） | 50e888a、c4cb883；合并 830e3b6 |
| 06 ⑤ 库存精简 | done（inventory_section：象限卡＋三线小卡＋仓单一行，抽屉含分品种/原始输入/实际库存近似；⑤ 段 3671→454px。遗留：仓单吨数旧格式 2175351.0） | 89d1c3e |
| 07 ⑥ 区间列表 | done（同状态连续日合并区间、区间抽屉逐日与更正；等价表格抽屉顶部含回溯小节 lookback_note；⑥ 段 ~8000→611px） | 86d5094、d5e04b1、aa2aca7 |
| 08 ⑦ 精简 | done（gap_preview 前 5 条＋查看全部抽屉；report_summary 四态；报告详情与发布日历抽屉；⑦ 段 1838→689px） | 63cd500 |
| 09 桑基图 | done（FLOW_RESULTS 一处映射四色；flow_sankey 中文名·数、其他（N）、悬停占比；主题变量 restyle；请求表限高 480 吸顶） | 26f8313、9383800 |
| 审查与修复 | done（S1–S4、P2、P4、P5 修；P1 不改、P3 接受；集成 3 例旧文案断言改写；家数整数、仓单千分位） | 3a86b37、1eb0d17、1828c2d |
| 10 集成验收 | ready-for-human（首页 1440 总高 22,467→5,396；82 个抽屉全可开关；全套 2676 过 / 1 败，该例为删观察接口列表后的过时断言，已改写复跑通过；8067/8068 已换新代码；待用户逐段确认） | 9970350 |

---

# 第二轮：验收后调整（2026-10-17 实施）

**范围**：[spec-adjust-20261017.md](spec-adjust-20261017.md) 与票 11–15；决定见 decisions.md 第五轮（25–30）；⑦ 根因见 `../worker-gap-fixes-20261017/investigation.md`。
**集成分支**仍为 `cockpit-layout`；票 worktree `/home/tywin/worktrees/datasourceRF-cl-<票号>`（11–14 已建并对齐 340d2e2）。
**任务图**：11、12、13、14 并行 → 15 集成验收。13 合入后 B 批次 02–04 解锁（B 合入 `cockpit-layout` 最新）。
**规程**：沿用上文"单票执行规程"1–10 与"约束"，差异如下：
- 第 2 步"读"改为：票文件、`spec-adjust-20261017.md`、decisions.md 第五轮、共享材料 `notes/cockpit-layout/`（drawer-usage.md、names-facts.md、serve_example.py）、`docs/agents/testing.md`、`GLOSSARY.md`（"正式阶段"已改称"价格阶段"，代码标识符 `formal_stage` 不改）。
- 第 6 步浏览器自检可交 Codex（`docs/agents/codex-delegation.md` 第五节：`-s workspace-write`、`-C` 指向 scratchpad 下本票独立空目录）；起站、停站由子代理自己按 PID 做。端口 `81<票号>`。
- 第 8 步 Comments 小标题写"### 2026-10-17 实施"。
- 11、12 有上一位实施者未提交的半成品（已保留在 worktree），先 `git diff` 读懂再续做，不对可重做。
- 同改 `cockpit.py`、`report.css`、`wording.py` 时只动本段相关规则、不改共用选择器；合并冲突由主 agent 处理。

## 第二轮进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 11 ② 三卡等高 | 实施中 | cl-11 |
| 12 ⑥ 左右布局 | 实施中 | cl-12 |
| 13 ⑦ 原因码中文与说明 | 实施中 | cl-13 |
| 14 遗留 a、c–f | 实施中 | cl-14 |
| 15 集成验收 | 等 11–14 | — |
