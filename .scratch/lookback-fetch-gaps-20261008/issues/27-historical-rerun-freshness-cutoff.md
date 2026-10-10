Status: done
Category: enhancement
Type: task

# 27：历史目标日在不同时刻重跑，时效与模型输入随运行截止点变化

## 现象（第三轮验收第五节，2026-10-09）

目标日 09-30。第二轮 14:03 提交、第三轮 22:22 提交，截止点分别冻结在 14:03:47 与 22:30:30。

- 国内日频 20 项由 `awaiting_release`（落后 0 期）变为 `stale`（应有 10-08，落后 1 期），缺口清单 14→34。
- 人民币 16:30 收盘价：投影按目标日选值只能选到 09-28，按截止点判时效落后 2 期，行状态 `current→stale`，选中声明 `341c3afc` 与方向输入 `cf332156` 退出模型输入编号。边界探针：10-09 16:34:59 为 `current`，16:35:00 为 `stale`。

验收记录判断这是既有口径，不是回归，本票由该节"口径要不要调整，可另行分流"一句开出。

## 验收

- [x] 缺口清单每项（或清单整体）带时效判定时点；报告确定性骨架与页面缺口区并列写出"目标日 YYYY-MM-DD；时效截至 YYYY-MM-DD HH:MM（北京）"，三处为同一时点
- [x] 选值、时效状态、缺口类别与模型输入编号都不变（用既有测试与一次投影前后比对证明）
- [x] 历史目标日（截止点晚于目标日之后的交易日）与当日运行两种情形都有用例
- [x] `CONTEXT.md` 或时效契约补一句：历史目标日重跑时时效按运行截止点判定，报告并列标注

## 主要模块

`src/pring_cycle/freshness.py`（缺口材料带 `assessed_at`／统一判定时点，`:844` 一带）、`reports.py`（确定性骨架，`:128` 已有截止点）、`dashboard.py`（`:401` 缺口区、`:2042` 截止点展示）；测试 `test_gap_list.py`、`test_report_input.py` 一带。不改运行冻结与选值算法。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g4.out`）：口径属领域决定，交用户。
- 口径出处：`.scratch/pring-fast-refactor-20260923/issues/04-freshness-contract.md:15`"判定时点 = 本次运行取数结束时冻结的时刻"，`:23` P1/P2 落后两期及以上不参与计算；ADR-0021 `:9` 引用该契约，规格 `spec.md:152` 重申；`CONTEXT.md:138` 写明目标交易日不等于运行／报告截止时间。"按目标日限制选值"的实现在 `context_projection.py:1886`（公开时间上限为目标日上海日终），没有单独的 ADR 句子。
- 截止点：默认完整运行取数结束后冻结（`worker.py:395`、`runs.py:679`），不是提交时；显式 `--as-of` 提交即固定，但它同时限制证据可见性，不能拿来只改时效。冻结与批次时效都没有"目标日早于今天"的分支。
- 批次时效（`freshness.py:579`）不受目标日公开时间限制，投影则受限——这是收盘价批次 `awaiting_release`、投影行 `stale` 两层状态不一致的原因。
- 方案：(1) 保持口径，只在报告、页面与缺口清单并列标注"目标日 09-30；时效截至 10-09 22:30（北京）"——改 `freshness.py` 输出、`reports.py`、`dashboard.py`，选值与模型输入不变；(2) 显式"历史模式"，引入独立 `freshness_as_of`（如目标日日终），证据读取仍用真实截止点——改 `runs.py`／`run_cutoffs.py`、`worker.py`、`day_summary.py`、`context_projection.py`、`freshness.py`，并修订时效契约、规格与 `CONTEXT.md`；不宜按"目标日早于今天"自动切换，否则周二上午分析周一这类正常运行也会变；(3) 维持现状，`wontfix`。Codex 推荐 (1)。

**2026-10-09 用户决定**：保持现口径（按目标日限制选值、按运行截止点判定时效），只补标注：报告、页面与缺口清单并列写出目标日与时效判定时点。选值与模型输入不变，符合"时效 T+1 即可"。→ `ready-for-agent`（积压批次线 A，排在 1002/05 之后，因同改 `freshness.py`）。

### 2026-10-10 实施

按用户决定只补标注，选值、时效判定、运行冻结均未改，不做历史模式。

- **缺口清单整体带判定时点**：`p0.py` 在 `cycle_overview` 写 `gap_list_assessed_at`（= 投影 `system_as_of`，即运行冻结截止点，与 `batch_freshness.assessed_at` 同值）。放在数据集里、不进投影身份文档，`projection_set_id` 不变。
- **统一措辞**：`freshness.freshness_statement(target, assessed_at)` 生成"目标日 YYYY-MM-DD；时效截至 YYYY-MM-DD HH:MM（北京）"（转上海时区、截到分钟）。
- **报告**：`reports.py` 确定性骨架新增 `freshness_basis`（目标日、判定时点、上句），由 `report_cutoff`（= 投影 `system_as_of`）生成；`ReportInput` 身份、`bundle_id` 与 AI 输入不变，AI 输出结构校验（ADR-0027）不受影响。
- **页面**：`dashboard.py` 首页缺口区标题下显示同一句；报告阅读页身份区新增"时效判定"。旧投影缺 `gap_list_assessed_at` 时回退其 envelope `system_as_of`（同一时点，ADR-0008 旧投影可读、不改写）。
- **`CONTEXT.md`**"证据时效"补一句：历史目标日重跑时选值以目标日为限、时效按运行冻结时点判定，报告、页面与缺口清单并列标注，三处同一时点。
- **测试**（`tests/integration/test_gap_list.py`）：新增历史目标日夹具（目标 08-27、截止 08-28 21:00，晚于下一交易日收盘），与当日运行（08-28、同截止点）参数化断言 `batch_freshness.assessed_at`、`gap_list_assessed_at`、报告 `freshness_basis` 与首页、报告阅读页文字是同一时点；两种情形缺口类别相同（时效随截止点）；旧投影删字段后回退；措辞单测（UTC 14:30:30 → 北京 22:30）。
- **前后比对**：同一夹具（当日／历史各一）分别在改动前（cbac9b7 安装副本）与改动后跑 Worker 并导出：两种情形 `projection_set_id` 相同，除新增字段外全部数据集（含选值、行状态、宏观与库存模型输入编号、核心模型输入编号）、`batch_freshness`、AI 输入 bundle、报告正文全部相同。

**测试**（共享 dev-venv 已重装）：`test_gap_list.py` 15 passed（约 2.5 分钟）；受影响 `tests/reports/test_report_boundary.py`、`tests/web/test_dashboard_contract.py`、`tests/web/test_projection_api.py`、`test_report_input.py`、`test_p0_gate.py`、`test_day_summary.py`、`test_confirmation_publish.py`、`test_derived_context_freshness.py`、`test_unsearchable_gaps.py` 152 passed（2:45）；两例冒烟 2 passed（92 秒，机器负载高）；重型两例（flock）首轮 3 passed、1 failed（`test_worker_registered_catalog.py::test_a_fetch_from_before_the_window_concludes_what_two_years_did`，28:19，期间系统卡顿、负载到 56、WSL 墙钟跳约 18 分钟），该例前台单独重跑 passed（7:12）；ruff check／format 通过；mypy 改动文件无新错（仅 `test_worker_execution.py` 既有 unused-ignore 17 条）。

**审查**（Codex 两轴）：标准轴无阻断；规格轴无阻断，独立复跑比对脚本确认验收②。非阻断意见：AI 自由文本可能与时点标注矛盾，按沿用口径记残余风险；两组用例都用显式截止点，默认冻结与恢复运行靠读码确认（同一 `run.system_as_of` 贯穿批次时效、目标日汇总与报告），未另写用例——不采纳为新增用例，因本票不改冻结路径。

