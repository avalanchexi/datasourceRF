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

## 修复记录

2026-10-16，分支 `cb-rf`（worktree `/home/tywin/worktrees/datasourceRF-cb-rf`），基于 conclusion-board `faf76ad`。每个行为修复先写失败测试再改。

- **Spec 1（上次确认）**：有投影但既无上一确认阶段、又无回溯记录时写"上次确认 未提供"，不再写"无"；空库（无投影）仍写"无"。测试：`test_last_confirmed_keeps_its_lookback_note_and_carry_forward_names_the_held_core` 断言改为"未提供"（先红后绿）。
- **Spec 2 / Standards 3（候选持续天数）**：新增 `cockpit.asset_candidate`，三核心表候选列与转折观察行共用；持续天数或门槛缺失均写"未提供"，不再补 0，也不再出现"未提供 日"。测试：新增 `test_a_candidate_without_its_duration_reads_not_provided_in_the_watch_and_the_table`。
- **Spec 3（报告生成中）**：按规格原句，报告任务排队或运行中板底一律写"报告生成中"，已有同投影旧报告也不例外；⑦ 段仍保留旧报告与"完成后自动显示新版本"提示。票 06 Comments 中相反的选择已划掉并标注"已按审查推翻"。测试：新增 `test_regenerating_a_report_says_it_is_being_generated_over_the_one_already_read`。
- **Standards 1（样式断言）**：删除 `test_the_table_scrolls_inside_its_own_container_so_the_page_does_not_overflow`（test_core_table.py）与 `test_the_board_stacks_its_columns_on_narrow_windows_without_widening_the_page`（test_conclusion_board.py）。两者的业务意图都是"窄屏不溢出"，无法改写成可见文本与顺序断言，交给票 07 浏览器截图验证。
- **Standards 2（投影构造）**：成本低（单例约 1.5 秒），已改。`test_the_right_column_reads_the_confirmation_the_day_summary_publishes` 改用 `tests.integration.test_confirmation_publish.confirmed`（集成运行时 + 带确认规则的模型 + 单日汇总 `summarize_target`）生成投影，断言确认度标题、过热格计数、库存象限、债券归因、数据边界及四行顺序。原测试中经 `build_context_projection` 的非典型分支不再走运行时（`seed_cores` 只产出典型组合，造非典型需另写核心序列）；非典型"不适用"由手写投影用例 `test_a_noncanonical_combination_marks_the_confirmation_and_each_cell_not_applicable`覆盖。

验证：
- `tests/web/` 全部 8 个文件 + `tests/reports/test_noncanonical_reading.py`：109 passed，16.7 秒。
- 两项必跑冒烟（flock）：2 passed，43.6 秒。
- 改动文件 `ruff check`、`ruff format --check` 通过；`mypy src/pring_cycle/cockpit.py` 通过；4 个改动测试文件自身无 mypy 报错（报错均在其导入的其他测试模块，基线相同）。
