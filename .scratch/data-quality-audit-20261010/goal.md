# 目标：数据质量体检（2026-10-10）

规格见 [spec.md](spec.md)。体检开发与 [lookback/30](../lookback-fetch-gaps-20261008/issues/30-retention-prunes-judging-calendar-receipt.md) 并行推进（用户 Q16 选 A）。

**终点**：票 01–04 已合入 main；lookback/30 状态为 `done`；票 05 已在目标日 10-09 的真实运行上产出 `report.md`，报告里的问题已开票或标注为已知；README 票表、文档和记忆都已更新并提交。

## 角色

沿用 [backlog goal.md](../backlog-triage-20261009/goal.md) 的"角色"一节和 [lookback goal.md](../lookback-fetch-gaps-20261008/goal.md) 的"单票执行规程""沿用口径"。

- 主 agent 只负责调度与核验。
- 每张票派一个命名子代理。
- 只读调查和两轴审查用 `codex exec -s read-only`。

## 任务线

| 线 | 位置 | 顺序 | 主要文件 |
|---|---|---|---|
| A | 主工作区，共享 dev-venv | lookback/30 | `trading_calendar.py`、`worker.py`、`retention.py`（如需要） |
| B | worktree `datasourceRF-dq`（不需要 venv：脚本不导入 `pring_cycle`） | 01 → 02 → 03 → 04 | `tools/quality/`、`docs/development/data-quality-audit.md`、`AGENTS.md` |
| — | 主工作区 | 05（阻塞于 01–04 与 lookback/30） | 真实运行与报告 |

## 线 B 的差异规程

- 不适用 TDD 与 `check.py`：脚本只读、离线，不进 `src/`。验证方式是对运行库实跑，再用已知事实对账。
  - 已知事实以 `run-a8675946cf7fa1b060b4` 和 `run-a1110cb8616e39b00f60` 为对照，见 [inventory](inventory-20261010.md) 与 [lookback/29 Comments](../lookback-fetch-gaps-20261008/issues/29-backfill-evidence-preload-and-wal-sync.md)。
  - 例如：模型输入缺失 7 个"指标期"；期货仓单 07-21 缺 CU、RB、RU、SC、SP；batch_freshness 计数；`a8675946` 中 25 项"落后 6 期"。脚本结果必须与这些对上，对不上就要解释。
- 每张票：
  - 改动的文件通过 `ruff check` 与 `ruff format --check`；
  - 跑 Codex 两轴审查（标准轴、规格轴，规格以 `spec.md` 为准）；
  - 在本目录 issues 下的票面记录对账结果；
  - 提交到 worktree 分支，回报主 agent，由主 agent 执行 `git merge --ff-only`。
- 运行库只读：一律用 `file:...?mode=ro` 打开；**禁止**启动 Worker、提交运行或做任何外部调用（这些归票 05）。
- 脚本保持简练：标准库实现，一个入口加按层的少量模块，不做通用框架。

## 票 05（收尾）规程

1. 等 lookback/30 合入、dev-venv 重装后，在 `flock /tmp/pring-heavy.lock` 下做一次 v0015 真实运行，目标日 2026-10-09。外部调用串行，C 盘保护照旧；子代理在前台守到结束。
2. 运行 `python tools/quality/audit.py --run <新运行>`，把报告写到 `report.md`。
3. 对报告中的可疑值，按约定源头串行核对，最多抽查 5 个，并记录结果。
4. 每个问题：属于已知票的，标注票号；属于新问题的，在 `.scratch/data-quality-audit-20261010/issues/` 新开 `needs-triage` 票。
5. 报告过 Codex 规格轴审查，之后提交。

## 何时停下来问用户

- 规则文档对核心趋势状态的定义有歧义，没法独立实现；
- 体检结果与已知事实对不上，又解释不了；
- C 盘余量 < 20G；
- 真实运行失败。

## 进度

| 票 | 状态 | 提交 |
|---|---|---|
| lookback/30 | done（真实运行 `run-a04dcc783e44323e049c`：宏观输入 2775，25 项回到 behind=1；注意 `full_run_acquisition` 新增 `phase='referenced'` 引用行，统计请求数时须排除） | 见提交 |
| 01 取数完整（日频/低频） | done | 34abdbb、84d6b99 |
| 02 派生数据存在与重算 | done | 63c6c5d |
| 03 模型输入完整＋输出一致性 | done | 875b53c |
| 04 三核心独立重算 | done | 81f1ac7、f476d63、e846a5a |
| 05 真实运行与体检报告 | done（`run-674411db5f492d4b607e`；新开 06–13 待分流） | 见提交 |
