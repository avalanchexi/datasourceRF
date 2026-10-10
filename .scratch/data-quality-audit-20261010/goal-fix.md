# 目标：修复体检发现（票 06、07、09–14，2026-10-10）

分流结论见 [README](README.md) 的“体检发现”和各票的 Agent Brief。用户已逐项决定，不再重复分流。

**终点**：
- 06、07、09、10、11、12、13、14 都已合入 main。
- 收尾票 16 已经完成：全套测试通过；v0015 目标日 10-09 的真实运行加体检，与 [report.md](report.md) 比对，票 06 的错值已改选、各体检误判已更正、其余没有退化。
- 票表、文档、记忆都已更新。

**沿用**：[goal.md](goal.md) 的角色划分与线 B 差异规程；[lookback goal.md](../lookback-fetch-gaps-20261008/goal.md) 的单票执行规程与沿用口径；backlog 批次的 worktree 合入流程。
- 主 agent 只做调度与核验。
- 每张票派一个命名子代理。
- 只读调查和两轴审查都用 `codex exec -s read-only`。
- 重型测试和真实运行一律经 `flock /tmp/pring-heavy.lock`。
- 长任务由子代理在前台守候。

## 任务线

| 线 | 位置 | 顺序 | 主要模块 |
|---|---|---|---|
| A | 主工作区，共享 dev-venv | 06 | `news_rules.py`、`search_evidence.py`、`evidence.py`、选值或冲突相关模块、报告标注 |
| B | worktree，`dev-venv-fixb` | 11 → 14 → 09（重处理已存原件那部分） | `full_retrieval.py`、`targeted_context.py`、`retrieval_ledger.py`、`acquisition.py`、`worker.py`（调度）、`official_context.py` |
| C | worktree，无需 venv | 07 → 09（体检部分）→ 10 → 13 → 12 | `tools/quality/`、`docs/development/data-quality-audit.md`、`CONTEXT.md`（只限票 12 的口径） |
| — | 主工作区 | 16 收尾（阻塞于以上全部） | 全套测试、真实运行、体检、比对 |

- 线 A、B 如果都要改同一个生产文件，后合入的一方先 rebase 再复跑受影响测试。线 B 的改动如果触及 06 的选值路径，先回报主 agent。
- 线 B、线 C 各自收尾时：rebase 到 main，复跑测试，回报分支名，由主 agent 执行 `git merge --ff-only`。
- 线 A、B 的真实运行留到票 16 统一做。各票自己只做受影响测试、冒烟和重型用例；06 与 14 若确实需要真实运行才能验收，并入票 16。

## 何时停下来问用户

- 实施中发现需要新的领域决定，例如 06 中 WebSearch 复核的预算上限、怎样才算“复核定下来”；
- 两轮审查后仍有阻断；
- C 盘余量低于 20G；
- 真实运行失败。

## 进度

| 线 | 票 | 状态 | 提交 |
|---|---|---|---|
| A | 06 | needs-info（①③ 已提交；② 待用户决定 6 项） | d1f4d65 |
| B | 11 → 14 → 09（重处理） | 11 done（83f242a）、14 done（见提交），09 重处理待派 | |
| C | 07 → 09（体检）→ 10 → 13 → 12 | 07、09 体检、10、13 done，12 待派 | |
| — | 16 收尾 | blocked | |
