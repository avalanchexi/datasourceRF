# 16: 残留"正式阶段"文案与报告拒收原因写法

**What to build:** v0016 页面上普通展示文字统一用"价格阶段"，报告退模板时写出的拒收原因与实际校验一致。依据：`../investigations/browser-v0016-first-day.md` 第 4、7 条。

1. ② 债券归因（不计数）抽屉末段："不计入确认度，不由宽松程度推算或改写债券牛熊与正式阶段"作为普通说明呈现时用"价格阶段"（模型数据原文若需保留，在报告详情 JSON 中不改）。
2. 启动壳（Dash 主体加载前的静态占位）曾短暂显示"暂无正式阶段"，改为不含旧术语的占位。
3. 适配器拒收原因：`stage_mutation_rejected` 目前一律显示"输出改写价格阶段被拒"；按审计里的 `rejection.check` 区分：价格阶段改写、宏观判断阶段陈述不符（`macro_stated_stage`）、得分不符（`macro_stated_score`）、把握程度不符（`macro_stated_confidence`）等，写出读者看得懂的原因。旧审计没有 `rejection` 时保持现有写法。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 页面测试：v0016 投影页面（含抽屉）普通文字不出现"正式阶段"；启动壳不含"正式阶段"
- [x] 页面测试：拒收原因按 `rejection.check` 分别写出，旧审计照旧
- [x] 两例冒烟通过

## Comments

- 2026-10-20 ticket-ms16（分支 ms-16）实施：
  - ② 债券归因抽屉：`cockpit.attribution_card` 在有宏观判断块时把"正式阶段"写作"价格阶段"；报告详情"已验证结果"JSON 中 `bond_attribution.boundary` 原文不改；旧投影（无宏观块）照旧。
  - 启动壳：`web._meaningful_dashboard_shell` 在有宏观判断块时显示主结论标题（如"宏观判断：第三阶段（倾向，5 维中 3 维吻合）· 相对上次确认第三阶段 不变"），旧投影仍用 `stage_title`。为不让加载页导入 Dash，标题拼写移入 `wording.macro_title`，`macro_board.title` 改为调用它（行为不变）；`_NO_STAGE` 改为 `wording.MACRO_NO_STAGE`。
  - 拒收原因：`ReportSnapshot.adapter_rejections` 按尝试顺序带出审计里的 `rejection.check`；`cockpit.adapter_failure` 按 check 写：价格阶段改写（current_stage／stated_stage／price_stated_stage，旧报告仍写"正式阶段"）、宏观判断阶段与规则结论不符、阶段得分不符、把握程度不符、未写明把握程度；其余 check 与旧审计（无 `rejection`）沿用结果码原写法。
  - 测试：新增 `tests/reports/test_macro_report.py::test_a_template_says_which_check_refused_the_reading`（5 例，经 ReportService 真实拒收后渲染首页）、`tests/web/test_projection_api.py::test_deferred_dashboard_shell_under_the_judgement_shows_the_judgement`；收紧 `test_the_report_under_the_judgement_names_the_cores_stage_the_price_stage`（只豁免报告 JSON 原文）与 `tests/web/test_macro_signal_board.py::test_a_page_led_by_the_judgement_calls_the_cores_stage_the_price_stage`（不再豁免抽屉）。
  - 运行（venv dev-venv-ms16，basetemp /tmp/pytest-ms16，flock）：合并前 tests/web＋tests/reports 全部文件 353 passed（131 s）；相关 integration 13 个文件＋两例冒烟 449 passed（1580 s，排队与并发负载下）。合并 macro-followups 06b7503 后复跑 tests/web＋tests/reports 全部＋test_macro_stage_history、test_day_summary、test_confirmation_bond_attribution＋两例冒烟 466 passed（261 s，超过 180 s 反馈目标）。ruff check／format、mypy（改动的 5 个源文件）通过。
  - 偏离：启动壳在 v0016 下直接显示宏观判断主结论，不只是去掉旧术语的占位；`noncanonical_stated_stage` 未单列原因（属旧非典型解读，按 spec 保持现状）。
