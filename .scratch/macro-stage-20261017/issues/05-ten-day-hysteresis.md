# 05: 10 日滞回

**What to build:** 投影同时记原始判断与主结论及滞回状态（候选阶段、已连续日数）：原始判断与主结论不同且连续 10 个交易日相同才替换主结论，中途变化即重新计数；滞回期间信号清单显示"倾向转向第 X 阶段（已 k/10 日）"；v0016 生效首日无既往主结论时直接取当日原始判断；补算日按逐日已发布的判断连续计数。滞回天数作为参数随 v0016 冻结（用户"暂时确认"，可经新模型版本调整）。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 03、04

**Status:** done

- [x] 单日汇总测试：第 10 日替换、第 9 日中断清零、生效首日直接取值、补算日连续计数、把握程度变化但阶段不变时不触发滞回
- [x] 模型版本测试：滞回参数随 v0016 冻结
- [x] `dashboard_page` 断言滞回进度条目在信号清单中可见
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms05，分支 ms-05）

- 参数：`macro_judgement.rules_v0001()` 增 `hysteresis_sessions: 10`，`MacroJudgementRules.hysteresis_sessions` 解析（正整数，否则 `macro_judgement_rules_invalid`），随 v0016 清单冻结。
- 滞回：纯函数 `macro_judgement.hold(block, earlier, sessions_required=)`，在 `DaySummaries._judge_macro` 里 `judge` 之后、`signal_list` 之前（目标日与补算日共用）。发布块 `hysteresis = {sessions_required, basis, candidate, sessions}`，`basis` ∈ `initial`（无既往主结论，直接取原始判断，决定 32）／`agrees`（原始判断与主结论同阶段，主结论随当日把握程度）／`held`（主结论保持原阶段与把握程度，`matched`/`known` 按当日得分）／`replaced`（第 10 个连续交易日替换）。决定 44：原始判断为"弱"而主结论不是"弱"时不计入候选、打断计数；原始判断无阶段（决定 49）时同样保持。
- 前一日状态：`ProjectionSetRepository.macro_judgement_on(day)` 改为 `latest_macro_judgement(before=day)`，返回该日之前最近一个发布了宏观判断的日期与块（各日取最新汇总）。`_earlier_judgement` 据窗口日历判断它是否就是前一交易日：是则接续计数（04 的信号成熟度也只从前一交易日接续，语义不变）；不是（中间缺汇总或缺宏观块）则沿用其主结论、候选从 1 重计，不跨缺失日累计，也不因缺一天让原始判断直接顶上。
- 信号清单：`macro_signals.with_progress` 追加 `id:"H"`、`kind/source:"hysteresis"`、`transition{from: 主结论, to: 候选}`、`sessions`、`sessions_required`，`group`/`steps` 用 `_grouped`；无信号表的模型也追加。页面 `macro_board._reading` 写"倾向转向第 X 阶段（已 k/10 日）"，不另写"符合 X→Y"。
- ① 标题下新增一行 `macro_board.held(block)`："滞回保持，当日原始判断：第 X 阶段（倾向／弱／明确）"（决定 45），在兜底说明行之前。
- 校验：`macro_judgement.validate` 增滞回自洽（非 held 时主结论即原始判断且无候选；held 时主结论不同阶段，候选即原始判断阶段且 1 ≤ k < 所需日数，或无候选且原始判断为弱／无阶段）；`macro_signals.validate` 要求 H 条目与滞回状态一致、无候选时不得出现。
- 更正（03 留言）：`with_reference(block, reference, earlier=)` 在有滞回状态时按新参照重选原始判断后，用 `hold` 从 `earlier` 重新计数；`P0ProjectionService.relink(..., counted_from=)` 由 `DaySummaries._relink` 传入当时读到的较早判断；`regrouped` 同时重建 H 条目。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms05`，`PYTHONPATH=src`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms05`，`PYTHONDONTWRITEBYTECODE=1`，`flock /tmp/pring-heavy.lock`。

- 新增 `tests/integration/test_macro_hysteresis.py`（11 例：v0016 冻结 10 日与不可变／非法拒收；第 10 日替换且两次运行跨已发布日接续；第 9 日中断清零后从 1 重计；生效首日（前几日为无规则模型的汇总）直接取原始判断；把握程度变化不触发滞回；"弱"11 日不顶替"明确"；滞回自相矛盾拒发 5 例）与 `tests/web/test_macro_hysteresis_board.py`（1 例：`dashboard_page` 中滞回保持注与"倾向转向第三阶段（已 2/10 日）"在信号清单"支持后退"组可见）。原始判断的变化靠社融 7 月修订（及不予披露）在指定交易日公开制造。
- 合并前受影响测试：`python tools/check.py quick` 宏观 5 个集成文件＋本票 2 文件＋页面 6 文件＋`test_day_summary.py test_backfill.py test_core_history_correction.py` → 132 passed，578 秒。
- 合并 macro-stage（含 07）后：第一组 `test_macro_hysteresis.py test_macro_judgement.py test_macro_fallback.py test_macro_signals.py test_price_verification.py` 与 `tests/web/test_macro_hysteresis_board.py test_macro_judgement_board.py test_macro_signal_board.py test_price_verification_board.py test_macro_basis_cards.py` → 79 passed，146 秒；第二组 `tests/integration/test_day_summary.py test_backfill.py test_core_history_correction.py tests/web/test_dashboard_contract.py test_conclusion_board.py` → 59 passed，529 秒。
- 两例冒烟：`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 2 passed，49 秒（另排队等锁约 7 分钟）。
- ruff check／format、mypy（改动的源文件）通过。

### 偏离与取舍

- 前一日读取换成 `latest_macro_judgement(before=)`（替代主 agent 指定的 `macro_judgement_on`，后者已无调用者而删去），以处理缺汇总的交易日：沿用最近主结论、计数重来。代码地图"未查实"一项据此定下，未经用户确认。
- 历史更正不向后重算：某日被整日更正或 relink 后，只重算该日（从当时读到的较早判断计数）；其后未被更正的日子保留原计数。
- relink 时的滞回重算已实现，但只经由 03 的既有 relink 用例覆盖（该例前一日从无到有，结果为 agrees），未单写滞回中途 relink 的用例。
- 主结论保持时 `matched`、`known` 取当日五维对保持阶段的得分（如第五阶段明确 5 维中 3 维），把握程度沿用保持前的；页面标题因此可能写"明确，5 维中 3 维吻合"，后注当日原始判断。

