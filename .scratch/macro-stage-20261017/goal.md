# 目标：宏观判断阶段为主结论（2026-10-17 起）

**范围**：[spec.md](spec.md) 与 [issues/](issues/) 01–08；决定见 [decisions.md](decisions.md)（两轮 14 条）；调查见 [investigation.md](investigation.md)；ADR-0043。
**当前只做 01 原型回测**。02 起等 01 经用户定稿（特征表与门槛记入 decisions.md）且 A 批次（`cockpit-layout`）验收并入 main 后，集成分支 `macro-stage` 从 main 建，届时补写本文件的单票规程。

## 01 原型回测规程

1. **worktree**：`git -C /home/tywin/worktrees/datasourceRF-cl worktree add -b prototype/macro-stage /home/tywin/worktrees/datasourceRF-ms-proto cockpit-layout`。脚本与输出放 `prototype/macro-stage/`（仓库根下目录），用完即弃写法，不写测试、不改 `src/`。
2. **读**：票 01、spec、decisions（重点决定 4、7、8、9、13）、investigation、ADR-0043、GLOSSARY（宏观判断阶段、宏观周期特征表、维度方向、价格验证、价格阶段）。只读调查用 `codex exec -s read-only`。
3. **数据**：只读隔离副本。先把 `/tmp/pring-cb-real-20261016` 复制为 `/tmp/pring-ms-proto`（不在原副本上做任何写操作），脚本只读这份拷贝；不访问外网、不调 TuShare、不启动 Worker。
4. **运行**：用 `~/.local/share/pring-cycle/dev-venv-cl10` 的解释器加 `PYTHONPATH=src` 与 `PYTHONDONTWRITEBYTECODE=1` 导入当前代码（不重装、不改该 venv）；重计算放 `flock /tmp/pring-heavy.lock` 下。
5. **时点纪律**：逐月取时点，每个时点只用 `available_at` 不晚于该时点的观测；关键指标读法复用现有代码，不重写；五维方向按决定 7、特征表按决定 8、选取按决定 9。
6. **产出**：每月表格（五维方向与主要指标、六阶段得分、宏观判断/介于/证据不足、当时价格阶段或非典型）＋小结（覆盖月数与数据缺口、判断跳变次数、并列与证据不足月数、与价格阶段一致/偏离分布、I 与 VI 混淆、3 分门槛是否合适、是否需要滞回）；10-15 时点与手算（第五阶段 4/5）对照。小结写进 `prototype/macro-stage/README.md`，并摘要写回 spec "Further Notes"（只在本分支）。
7. **提交**：在 `prototype/macro-stage` 分支提交，英文提交信息带两行署名（同 A、B 批次）。票面 Comments 记"### 2026-10-17 回测"，`Status: needs-info`（等用户定稿），不勾"用户已看过"一框。
8. **回报**（中文）：分支与提交号、小结要点、建议的特征表或门槛调整（如有）。

## 进度

| 票 | 状态 | 分支／提交 |
|---|---|---|
| 01 原型回测 | 实施中 | prototype/macro-stage |
| 02–08 | 等 01 定稿与 A15 | — |
