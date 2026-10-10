# 数据质量体检（2026-10-10）

- [spec.md](spec.md)：访谈定稿的规格
- [goal.md](goal.md)：执行规程与进度
- [inventory-20261010.md](inventory-20261010.md)：现状盘点（Codex）

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-acquisition-completeness.md) | 脚本骨架；日频逐交易日、低频最新期与发布延迟 | done（worktree 分支，待 ff 合入） |
| [02](issues/02-derived-presence-and-recompute.md) | 派生数据存在性与独立重算 | done（worktree 分支，待 ff 合入） |
| [03](issues/03-model-input-and-output-consistency.md) | 模型输入完整，以及输出内部一致性 | done（worktree 分支，待 ff 合入） |
| [04](issues/04-core-independent-recompute.md) | 三核心独立重算到正式阶段 | done（A2／A3／A8 已裁决并收敛；A4／A5／A6 留待票 05 分流） |
| [05](issues/05-real-run-and-report.md) | 目标日 10-09 真实运行与体检报告 | blocked（01–04、lookback/30） |

**下一步**：线 A 实施 lookback/30，线 B 依次实施 01→02→03→04，两线并行；全部合入后执行 05。
