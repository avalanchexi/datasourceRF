# 11: ⑥ 宏观判断区间抽屉逐日写宏观信息（D2）

**What to build:** ⑥ 右栏切到"宏观判断"时，区间抽屉的逐日行写该日主结论、把握程度与滞回状态（held／replaced 等），不再重复价格阶段描述；价格信息只留在价格区间抽屉。依据决定 58、acceptance.md 第四节第 9 项与 integration/browser-report-codex.txt 的 D2。

**Blocked by:** 10（激活后做，不阻塞激活）

**Status:** done

- [x] 页面测试：宏观区间抽屉逐日行含主结论、把握程度、滞回状态，不含价格阶段描述；价格区间抽屉不变
- [x] 两例冒烟通过

## Comments

2026-10-20 ticket-ms11（分支 ms-11）实施：

- 做法：阶段史展示行（`stage_history.display.days`）新增 `macro_hysteresis`，发布时取各日自身投影集 `cycle_overview.macro_judgement` 的滞回状态——`held` 附当日原始判断阶段与把握程度，`replaced` 附所需日数，`initial`／`agrees` 只记状态；不记候选与 k/10 计数（决定 33）。读法为 `ProjectionSetRepository.macro_hysteresis`（按投影集 id 的 SQL `json_extract`），当日自身用正在发布的宏观块；`relink` 路径用重述后的宏观块。旧投影集的日子会在下一次发布重建展示时补上，无需迁移。
- 页面：宏观区间抽屉逐日行改为"日期 · 主结论（把握程度）"＋滞回状态（"生效首日，取当日原始判断"／"与当日原始判断一致"／"滞回保持，当日原始判断：第三阶段（倾向）"／"滞回替换：当日原始判断已连续 10 日，取代原主结论"；未记录的写"滞回状态未记录"）、更正说明与投影链接；不再列上一确认、原因、缺口、模型等价格阶段描述。价格区间抽屉不变（更正说明抽成共用的 `correction_note`）。
- 测试缝：页面（`tests/web/test_macro_stage_history_board.py` 新增 `test_a_macro_interval_lists_each_days_conclusion_and_hysteresis_not_its_price_stage`，并在 `test_the_intervals_can_be_listed_by_the_macro_judgement` 补"滞回状态未记录"）；发布（`tests/integration/test_macro_stage_history.py::test_each_day_from_the_rules_on_records_its_main_conclusion_and_none_before` 断言 14 日窗口逐日滞回状态：生效前 2 日无、initial、agrees、held×9、replaced）。两例均先红后绿。
- 受影响测试（venv dev-venv-ms11，`PYTHONDONTWRITEBYTECODE=1`，basetemp /tmp/pytest-ms11，flock /tmp/pring-heavy.lock）：
  - `python tools/check.py quick` web 10 个文件（asset_cards、conclusion_board、dashboard_contract、macro_stage_history_board、projection_api、stage_history_intervals、macro_basis_cards、macro_fallback_board、macro_hysteresis_board、macro_judgement_board）＋ integration test_display_projection、test_macro_hysteresis、test_macro_judgement、test_macro_stage_history：152 passed，260 s，退出码 0
  - integration test_macro_fallback、test_price_verification、test_core_stage_lookback：32 passed，351 s
  - integration test_core_only_correction、test_backfill：7 passed，381 s
  - integration test_macro_signals：21 passed，40 s
  - ruff check／format（改动文件）、mypy（cockpit、p0、projections、display_projection）通过
- 两例冒烟（`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report`）：2 passed，66 s。
- main 头仍为 2f876b2（分支基于它），无需合并。
- 偏离：票面只要求页面测试；滞回状态原先不在阶段史事件与展示行里，故另加发布层断言与一个仓储读法。正式库中 10-14～10-19 已发布投影的展示行没有该字段，上线后下一次运行发布时即补齐；在此之前这些日子抽屉显示"滞回状态未记录"。
