# 集成分支代码审查（2026-10-16）

基线 main 012f362，HEAD 4238bdc；两轴各一次 codex exec -s read-only。

## Standards

发现两类硬违反及一处坏味判断；无阻断项。下称“规格”指 [.scratch/conclusion-board-20261016/spec.md](/home/tywin/worktrees/datasourceRF-cb/.scratch/conclusion-board-20261016/spec.md)。

1. **重要｜硬违反**：`tests/web/test_core_table.py:305`、`tests/web/test_conclusion_board.py:350` 断言组件嵌套、CSS 类名及样式源码；等价布局重构会误报，也不能证明窄屏不溢出。违反规格“测试决定”：只断言可见文本、链接与顺序。

2. **重要｜硬违反**：`tests/web/test_conclusion_board_right.py:319` 通过 `project()` 直接调用 `build_context_projection`，再拼装投影，绕过实际发布结构。违反规格“投影构造”：真实结构验证应经运行时与单日汇总入口。

3. **建议｜判断：Duplicated Code**：`src/pring_cycle/cockpit.py:251、627` 重复格式化候选持续期，已发生分歧：候选存在但天数字段缺失时，表格显示“未提供”，转折行显示“0 日”。依据所给坏味基线，宜共用缺失值处理。

阻断：无

## Spec

发现 3 处规格偏差：

1. **重要**｜[cockpit.py:534](/home/tywin/worktrees/datasourceRF-cb/src/pring_cycle/cockpit.py:534)：旧投影无上一确认阶段且缺回溯记录时显示“无”，把未提供误呈为确定不存在。规格原句：“旧投影缺字段（无回溯记录、无持续门槛、无健康摘要、无覆盖汇总）按‘未提供 / 口径不可用’显示，不补造、不回填。”

2. **重要**｜[cockpit.py:627](/home/tywin/worktrees/datasourceRF-cb/src/pring_cycle/cockpit.py:627)：存在资产候选但缺 `candidate_days` 时，转折观察补成“持续 0 日”，与表格的“未提供”也不一致。规格原句：“不补造、不回填。”

3. **重要**｜[cockpit.py:908](/home/tywin/worktrees/datasourceRF-cb/src/pring_cycle/cockpit.py:908)：只有无旧报告时才显示生成中；同投影重新生成时继续显示旧解读，票 06 Comments 的选择改变了规定行为。规格原句：“报告任务排队或运行中写‘报告生成中’。”

阻断：无

## 调度方核实

- Standards 1、Spec 1、Spec 2（同 Standards 3）、Spec 3 读码属实，交修复。
- Standards 2 属判断：build_context_projection 产出的是 Worker 真实结构，未经单日汇总入口；成本低则改。
- Spec 3 按规格原句改：任务排队或运行中写"报告生成中"，推翻票 06 Comments 的选择。
- 窄屏不溢出改由票 07 浏览器截图验证，不再断言 CSS 源码。
