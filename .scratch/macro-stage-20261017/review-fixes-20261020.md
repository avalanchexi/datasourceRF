# 审查修复（票 11、12，2026-10-20）

依据：`review-standards-20261020.md`、`review-spec-20261020.md`。一个子代理在分支 ms-rf 上统一修复。

1. **R1（票 11，应改）**：`initial` 不固定写"生效首日"。此前结论无阶段时也产生 `initial`（如生效日"无可取阶段"、次日首次取得阶段），改写"无既往主结论，取当日原始判断"；补该边界的页面断言。
   - **处理（ms-reviewfix，分支 ms-rf，79d5519）**：`cockpit.MACRO_HYSTERESIS["initial"]` 改为"无既往主结论，取当日原始判断"，不再说"生效首日"。
   - **测试**：`tests/web/test_macro_stage_history_board.py::test_a_first_conclusion_after_a_day_with_no_stage_is_not_called_the_rules_first_day`（10-13 生效日"无可取阶段"、10-14 首次取得第五阶段且为 `initial` → 行写新文案，整页无"生效首日"），先红后绿；D2 用例期望同步更新。集成侧 `test_macro_stage_history.py::test_a_day_with_no_stage_to_take_records_so_and_its_relink_records_the_stage_it_takes` 补断言：relink 前后该日展示行均为 `initial`（生效日原为无可取阶段，relink 后首次取得阶段）。
2. **R2（票 11）**：更正说明测试定位到宏观抽屉本身（不能靠价格抽屉的文本通过），断言宏观抽屉的更正说明、旧／新投影链接，以及更正后的滞回状态；relink 路径断言 `macro_hysteresis`。
   - **处理**：测试改写，生产代码未改。`test_a_correction_under_the_macro_judgement_names_the_price_stage` 改为定位宏观区间抽屉中被更正那一行：断言行文本依次为主结论、更正后投影记录的滞回状态（held，当日原始判断第三阶段（倾向））、"更正版本：更正 projection-old-10-14（核心历史口径变更；只更正核心与价格阶段，上下文与确认度未重算…）"，并断言该行两个链接依次指向旧投影与新投影；全页仍无"正式阶段"。relink 路径：`test_macro_signals.py::test_a_relink_while_a_run_is_counted_judges_the_divergence_again` 断言 held 日展示行的 `macro_hysteresis`：relink 前 `agrees`，relink 后为重述后宏观块的 `held`（原始判断第五阶段（倾向）），即更正后而非更正前的状态。
   - **变异核对**：临时去掉 `macro_history_day` 中的 `correction_note`，宏观抽屉用例失败（此前整页文本断言会被价格抽屉蒙混通过）；改回后通过。
3. **R3（票 11）**：补一例集成测试"旧投影有宏观块但缺滞回字段 → 新发布的历史展示行补齐 → 旧投影保持原样"；票面措辞改为"补齐的是新投影中的历史展示行，固定访问旧投影仍显示'滞回状态未记录'"。
   - **处理**：新增 `test_macro_stage_history.py::test_a_set_published_before_its_rows_told_the_hysteresis_keeps_them_the_next_fills_them`：生效日正常发布；次日发布时把 `display_projection.macro_hysteresis_row` 替换为返回 None，模拟票 11 之前的发布（宏观块含 `hysteresis`，展示行缺字段）；再发布目标日 → 新投影三日展示行为 initial／agrees／agrees；按 id 重读旧投影，`datasets` 与发布时完全相同，页面仍含"滞回状态未记录"，新投影页面不含。票 11 Comments 中"下一次发布补上"两处措辞已改为"补齐的是新投影中的历史展示行，固定访问旧投影仍显示'滞回状态未记录'"。
   - **变异核对**：临时让 `P0ProjectionService._macro_judgements` 不读历史各日投影，该用例失败；改回后通过。
4. **R4（票 12，不满足）**：补最小宏观原件集合，让宏观数据也在 v0006 上（可复用 `tests/integration/test_worker_registered_catalog.py` 的假宏观交付构造），至少一例 B 或 K 场景的宏观主结论与价格阶段不同，同时锁定归组基准（相对宏观主结论）与确认基准（价格阶段）。
   - **处理**：`tests/integration/test_macro_signals.py` 新增 `seed_macro_originals`（复用 `test_worker_registered_catalog.macro_rows` 的假 TuShare 宏观交付：cn_pmi、cn_cpi／cn_ppi、cn_m、sf_month、cn_gdp，2024-01～2026-07，经 `TushareContextAdapter.acquire_scalars` 存原件）与 `seed_lpr`（以 `tests/fixtures/chinamoney_lpr_20260820.html` 为模板逐月生成 1～8 月 LPR 公告原件，经 `refresh_lpr_release` 入库，7 月起上调 10bp）。v0006 复核族按原件采用这些宏观数据：政策 tightening、信用 up、物价 up（高位），过热与库存因无统计局原件仍未知。新用例 `test_on_its_macro_originals_a_stage_iv_groups_b2_and_k4_and_k4_confirms_on_stage_iii`：宏观主结论第四阶段（明确，3/3），价格阶段第三阶段；B2 归组 forward 1、K4 归组 back −1（相对宏观主结论；若误用价格阶段会是 forward 2／hold 0），K4 首日 confirmed 入清单、B2 萌芽（确认看价格阶段；若误看宏观阶段 K4 不会确认）。期望值按对照表与特征表事先推出，探查结果与之一致。票 12 偏离 1 撤销（见票 12 Comments）。过热、库存两维未放原件（需统计局 HTML），不影响本项要求。
5. **R5（票 12，建议）**：参数化补对照表的"不落格"负例（普涨、普跌、持平、不一致）与一例 20 日／120 日方向不同的案例，按风险取舍，至少覆盖普涨、普跌。
   - **处理**：新增参数化 `test_a_breadth_or_basket_moving_broadly_or_evenly_is_in_no_cell`（broad_rise：广度 62%＋篮子 6/7 分项上涨；broad_fall：股票熊、广度 38%＋7 分项全跌；even_and_flat：广度 50%＋分项逐日抵消）均断言读法正确且 B／K 不落格；新增 `test_the_basket_is_read_over_its_120_sessions_not_its_last_20`（前 100 日 K4 形态、后 20 日 7 分项全涨 → 120 日读法仍为 few_sleeves_fall，落 K4）。未做：广度"指数持平"（`core_originals` 只能造单边牛／熊核心）与篮子"分项与篮子不一致"（需构造复利与分项求和方向相反的序列），按风险取舍。
   - **变异核对**：临时把 `price_consistency._basket` 的窗口改成末 20 日，120 日用例失败（读成 broad_rise）；改回后通过。

## 收尾验证（ms-reviewfix，2026-10-20）

- 修复提交 79d5519；已合并 macro-followups 最新头 cd25885（合并提交 aa25796，无冲突）。生产代码仅改 `src/pring_cycle/cockpit.py` 一行文案，其余为测试。
- 合并后受影响测试＋两例冒烟（venv `dev-venv-msrf`，`PYTHONDONTWRITEBYTECODE=1`，basetemp `/tmp/pytest-msrf`，flock `/tmp/pring-heavy.lock`）：`python tools/check.py quick tests/web/test_macro_stage_history_board.py tests/web/test_stage_history_intervals.py tests/web/test_macro_signal_board.py tests/web/test_dashboard_contract.py tests/reports/test_macro_report.py tests/integration/test_macro_stage_history.py tests/integration/test_macro_signals.py tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability tests/integration/test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 125 passed，245 s，退出码 0（超出 180 s 反馈目标；两例冒烟 27.4 s＋20.5 s）。
- ruff check／format（改动文件）通过；mypy 新增代码无新错误（`test_macro_signals.py` 仍只剩既有一条）。`find src tools -name __pycache__` 为空。
