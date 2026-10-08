# 目标：完成回看取数缺口票（2026-10-08 起）

**终点**：README 表中 10 项全部 `done` 并各自提交；票 09 的全套测试与真实运行验收记录写入本目录。

## 用户决定（2026-10-08）

- 机制：**主 agent 调度**（派票、转达决定、核验提交与票面、记进度、每 20 分钟汇报）；**每张票派一个命名子代理**（Agent 团队）执行下列规程。只读调查交 `codex exec`。
- 顺序：严格按 README"序"列串行（共用 dev-venv，重型测试同时只跑一个）。
- 05：按日期区间扫描，一次运行内同栏目只扫一次索引，翻到最早需求日为止；每站每轮上限 50 页，触顶后按现有检索预算转搜索；缺口写"列表未覆盖"。
- 08：保留仍被投影引用的来源声明及原件关联至投影过期，修订 ADR-0035 留存说明。
- 遇到规格、ADR、票面分流记录都没覆盖的领域决定：先按推荐方案实现成可改的规则或配置，状态设 needs-info，不提交，回报主 agent 转用户决定。

## 单票执行规程（子代理照做）

1. **读**：票文件、`spec.md`、票里链接的文档、`docs/agents/testing.md`、`docs/agents/codex-delegation.md`、`CONTEXT.md` 相关术语、相关 ADR（尤其 ADR-0037、ADR-0025、ADR-0034）。只读调查量大时用 `codex exec -s read-only`（见 codex-delegation.md），不要开 Claude 子代理。
2. **领取**：票面 `Status: ready-for-agent` 改为 `Status: claimed`。
3. **TDD 实施**：先写会失败的测试，再实现，一次一个红→绿切片。代码风格贴合周边（命名、注释密度、英文注释与标识符）。
4. **环境**：改 `src/` 后先重装再测：
   `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv uv sync --extra dev --no-editable --reinstall-package pring-cycle`
   测试一律用 `$HOME/.local/share/pring-cycle/dev-venv/bin/python tools/check.py quick <具体文件或 node>`；从 `src/` 直接导入调试须加 `PYTHONDONTWRITEBYTECODE=1`。
5. **验证**（按 testing.md 与票面验收）：受影响测试 → 两例冒烟 → 涉及 Worker 编排、指标目录或来源时加跑 `tests/integration/test_worker_registered_catalog.py` 与 `tests/integration/test_core_carry_forward.py`（重型，用 `python -m pytest` 显式跑）→ `ruff check`、`ruff format --check`、`mypy` 覆盖改动文件。失败如实记录；不删必要测试凑时限。
6. **Codex 两轴审查**：标准轴与规格轴各一次 `codex exec -s read-only ...`（提示词要求中文、结论先行、`file:line`、末行"阻断：有/无"）。有阻断就修，修后复审；两轮仍阻断则停下上报。非阻断意见：采纳或在票面写明不采纳理由。
7. **收尾**：勾选验收框（只勾有证据的）；在 `## Comments` 下追加"### 日期 实施"记录（改了什么、测试与耗时、审查结论）；`Status: done`；更新 `README.md` 票表状态与"下一步"。
8. **提交**：只 `git add` 本票相关文件（工作区有大量与本票无关的未跟踪文件，不要 `git add -A`）；英文提交信息沿用仓库风格（一句话标题＋简短正文），末尾附：

   ```
   Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_013FhCGqT7LMbB6gqUQutg7H
   ```

9. **回报**（中文，精炼）：完成/暂停；提交号；改动要点；测试结果与耗时；审查结论；遗留问题；若暂停，写清需要用户决定的问题与可选方案（同时写进票面 Comments，`Status: needs-info`）。

## 票 03 起沿用的审查口径（主会话决定，2026-10-07）

- 报告正文（AI 自由文本）的确认关系／计数改写校验：结构化结论严格不可改；正文只要求拦住规范写法与常见明确写法（动词式、冒号式、否定式、跨句延续、标题与正文分写），与正式阶段的 `_stated_stages`（ADR-0027）同一标准。审查新找出的自由文本绕过写法记入票面"已知残余风险"，**不算阻断**；审查提示词须写明这一口径。
- 两轮审查后剩下的阻断如果只是对上一轮修复的定向确认，做一次定向复审（只验修复本身，不再找新问题），通过即提交。
## 沿用口径（宏观语义 effort 已确立）

- 审查：两轮仍阻断即停；只剩对上一轮修复的确认时做一次定向复审，通过即提交。报告正文自由文本的新绕过写法记残余风险、不算阻断（同 `_stated_stages`）。
- `ruff format` 只对改动的文件运行；不要对整个目录跑。
- 长任务（全套、真实运行、重型测试）自己守到结束：前台轮询或 Monitor，不要丢在后台就转空闲。
- 票 09 的全套与真实运行带 C 盘保护：`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/0ddce97e-08f2-4fa9-b673-d3e3fb478c4c/scratchpad/disk_guard.sh <pytest或worker PID> <log> 12`（2026-10-08 实测全套 basetemp 峰值 11G、C 盘最低 51G）。

## 并行规则（2026-10-08 用户要求能并行就并行）

- 可并行的判据：改动的模块不重叠。L01、L04、L03、L05 共用 `worker.py`／`full_retrieval.py`／`official_listing.py`，串行；L08（留存与投影依赖）与它们不重叠，可与之并行。09 在全部完成后。
- 并行的子代理在**独立 git worktree** 中工作（Agent `isolation: "worktree"`），并用**自己的 venv**：`UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv-<票名> uv sync --extra dev --no-editable`，测试用该 venv 的 python 跑 `tools/check.py`；pytest 临时目录用 `PYTEST_ADDOPTS=--basetemp=/tmp/pytest-of-$USER-<票名>` 隔开。共享的 `dev-venv` 只留给主工作区的串行票。
- **重型测试全局排队**：`flock /tmp/pring-heavy.lock <命令>`（重型两例、`check.py full`、真实运行都要），同一时刻只跑一个。
- worktree 里的票在自己的分支上提交；收尾前 `git rebase main` 并确认受影响测试仍通过，回报分支名，由主 agent 在主工作区 `git merge --ff-only` 并入 main。

## 约束

- 外部真实调用（TuShare、官网、检索）一律串行，普通回归保持离线。
- 不 push，不改 git 配置，不做破坏性 git 操作；不必更新本文件进度表（主 agent 更新）。
- 交互与文档一律中文；代码标识符、命令、路径保持原样。

## 进度

| 序 | 票 | 状态 | 提交 |
|---|---|---|---|
| 1 | L06 | done（三数分记；0031 改调幂等助手，有 0022/0026 先例） | 39fb148、3744878 |
| 2 | R06 | done（按登记契约只滤一月 PPI 三个累计字段；CPI 不变） | 693db3f |
| 3 | L07 | done（补中间价成员契约；v0001 目录保持无维度） | 054acc2 |
| 4 | L02＋R10 | done（入库扩到目录同族成员；已持有成员按全族求；事件类只认本期最新事件；F3 七分项真实可读留 09） | e10db1b、005abf8 |
