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
| [05](issues/05-real-run-and-report.md) | 目标日 10-09 真实运行与体检报告 | done（`run-674411db5f492d4b607e`；报告 [report.md](report.md)） |
| [06](issues/06-loan-structure-wrong-year-media-page.md) | 贷款结构 2026-08 误收 2025 年 8 月报告的数值，住户两成员错值入选模型输入 | needs-triage |
| [07](issues/07-credit-impulse-gdp-quarter-vintage.md) | 信用脉冲 GDP 2025-Q3 当季值与初步核算公告不符（很可能是修订口径） | needs-triage |
| [08](issues/08-dr007-policy-spread-missing-0929.md) | 09-29 日投影缺 DR007 政策利差 | needs-triage |
| [09](issues/09-daily-history-periods-never-requested.md) | 七天逆回购利率、人民币中间价的历史期次从未请求 | needs-triage |
| [10](issues/10-low-frequency-backfill-holes.md) | 低频回填空期：核心 CPI 2026-04、05，工业经济效益三项 2026-03 | needs-triage |
| [11](issues/11-warrant-unpublished-cells-retried-every-run.md) | 仓单上游未发布格每次运行重试，被负缓存拦截计为失败 | needs-triage |
| [12](issues/12-layer3-rules-not-covered.md) | 第三层未覆盖的规则：A4、A5、A6 与按符号比较的成员读法 | needs-triage |
| [13](issues/13-audit-partial-upstream-composite-members.md) | 体检把合计成员的“上游部分未发布”误判为“未取到”（脚本缺陷） | needs-triage |

**下一步**：01–05 与 lookback/30 已完成；体检报告见 [report.md](report.md)。新开 06–13 待分流，其中 06（错年份数值进入模型输入）优先。

## 体检发现（2026-10-10 分流，[取证原文](triage-20261010-codex.md)）

| 票 | 内容 | 状态 |
|---|---|---|
| [06](issues/06-loan-structure-wrong-year-media-page.md) | 贷款结构误收 2025 年报告的值（9 条错期声明，14 个投影） | needs-info（①错期校验与③标注更正已提交；②媒体冲突复核有 6 项领域选择待用户决定，见票面） |
| [07](issues/07-credit-impulse-gdp-quarter-vintage.md) | GDP 当季值的修订口径 | done（体检回读规范化制品确认共同交付，误报消除；08 的旧缺口归为“已修复、历史保留”；生产端 wontfix） |
| [08](issues/08-dr007-policy-spread-missing-0929.md) | 09-29 缺 DR007 政策利差 | wontfix（ADR-0036 已修；体检归因并入 07） |
| [09](issues/09-daily-history-periods-never-requested.md) | 逆回购利率、中间价历史期次 | done（体检部分：事件类按公告覆盖、中间价按需求口径；重处理：`pring-cycle official-reprocess` 从已存原件补回 12 天利率，0 次外调、只补不改变选值的部分；对运行库的执行待票 16；中间价不补历史） |
| [10](issues/10-low-frequency-backfill-holes.md) | 低频空期 | done（体检按最终计划与截止前回执，把核心 CPI 04、05 报“不在需求内”、工业三项 03 报“已入库后被清理”；“到截止仍未入库”归零；留存与需求不变） |
| [11](issues/11-warrant-unpublished-cells-retried-every-run.md) | 仓单未发布格每轮重试 | done（跳过本轮应答已为空的单日补取＋负缓存前移记为暂缓、不写回执；真实核对并入 16） |
| [12](issues/12-layer3-rules-not-covered.md) | 第三层未覆盖规则 | done（体检按裁决补两项：当月增量同比差按正负读方向、与主成员比较，未知或过期为 `not_compared`；分化的关键指标既不算支持也不算反证；两次运行均为非典型组合，按符号比较 10 个成员全部一致，封顶只核到分化识别；口径写入 `CONTEXT.md`；A4–A6 见 15） |
| [13](issues/13-audit-partial-upstream-composite-members.md) | 合计类成员部分未发布误判 | done（按成员所需行键／原件核对：两融交易所、SHIBOR 期限、估值字段、广度、商品篮子；部分缺项记上游未发布并注明缺项，空值、损坏、分页不全记未取到；“本运行回执”识别票 11 的暂缓与本轮应答为空） |
| [14](issues/14-scheduler-weekday-fallback-on-holidays.md) | 调度在节假日误提交 | done（缺覆盖先补一次 `trade_cal`、开市才提交；失败暂缓、每 10 分钟重试至 21:00） |
| [15](issues/15-trend-rules-a4-a6-interview.md) | A4–A6 规则口径访谈 | needs-info（另开访谈） |
