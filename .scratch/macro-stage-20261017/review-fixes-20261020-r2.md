# 第二轮审查修复（票 13–15，2026-10-20）

依据：`review-standards-20261020-r2.md`、`review-spec-20261020-r2.md`（范围 74cdb38..06b7503）。两个子代理：ms-rf2a 修 S1–S2（报告校验），ms-rf2b 修 S3–S6（完整度与体检）。

## ms-rf2a：报告宏观陈述校验

1. **S1（阻断）条件作用域过宽、按并集核对**：只对明确描述"某指标变化 → 重判结果"的条件分句启用重判核对，并绑定到被点名的那条信号（如 PMI → 该信号的 `rejudged`），核对它自己的阶段、把握程度与有序转换端点（from→to）；表达性条件（"如果读者需要一句话概括"）、转折后的现实陈述（"但本次……"）、无法绑定到具体信号的条件分句，一律按主结论核对（宁可误拒，不可放过）。补审查给出的四个反例：两段"借条件改写主结论"、"PMI 改投后变为第三阶段倾向／第三阶段向第三阶段转换"、"第五阶段明确但写成第三阶段向第四阶段转换"，均须拒收；两份真实输出仍整份通过。
   - **处理（ms-rf2a，d3f6722）**：`reports.py` 的 `_conditions` 改为逐个条件判定：条件词所在分句（到下一个逗号）恰好点名一条有重判结果的分化信号（名称取自信号行"X 分化："，按最长名匹配，"PMI 价格"不算 PMI）且含变化词（改投、改按、少数方向、转为、走弱……），才是该信号的重判条件；作用域止于下一个条件词、转折或现实陈述词（但、不过、然而、本次、本期、实际、宏观、主结论、当前、目前、现在、当下）。重判作用域内：判出的阶段只能是该信号 `rejudged.stage`，并列只能是它的 `tied`，把握程度须与 (该信号阶段, 该信号把握程度) 一致（无阶段可绑时核对把握程度本身），转换按有序端点 (from, to) 核对该信号的 `transition`。其余条件（表达性条件、点名两条信号、点名无重判的指标、无变化词）一律按主结论读：其作用域里的信号类词（改投、转向、→……）也按主结论核对。条件以外、由信号词引出的"X 向／转向／→ Y"转换，也改按有序端点对全部信号的 (from, to) 核对（原来只核端点并集）。
   - **测试**：`tests/reports/test_real_macro_readings.py` 新增审查四反例（`test_a_conclusion_said_after_a_condition_is_read_as_the_conclusion` 两段；PMI 下"第三阶段、倾向／第三阶段向第三阶段转换"；"第五阶段明确＋第三阶段向第四阶段转换"），另加：PMI 下只改阶段为第三阶段、PMI 下只说倾向、社融的重判说成 PMI 的、PMI 的重判说成社融的、同时点名 PMI 与社融、条件外反向转换（第五转向第三），均拒收；codex 原文两句条件推演（PMI、社融）整句正例通过。原用例"变为第四阶段"的拒收原因由 `macro_stated_confidence` 变为 `macro_stated_stage`（第四阶段只在社融／贷款的并列里，不再被并集放过），仍拒收。两份真实输出 `test_the_first_v0016_readings_are_accepted_whole` 整份通过；`test_macro_report.py` 中 signalled 模板回写仍通过。
2. **S2（阻断）双重否定**：识别完整否定结构；单层否定才走放行分支；双重否定（"并非不是明确""不能说不是明确的结论"）及无法消歧的嵌套保守拒收。补这两句反例（经 `ReportService.generate` 或现有校验接缝）。
   - **处理（ms-rf2a，d3f6722）**：新增 `_denied`：在把握程度词所在分句（逗号、冒号、括号为界）内数否定字（不、非、未、没、无、否、别、勿、莫）；没有否定为肯定；只有紧邻的单层否定结构（不是、并非、而非、不算、不属于、不能〔被〕解释为、不应、无法……）且它就是分句里唯一的否定时才算否定；其余（双重否定、"不能说不是"、否定不紧邻如"并不明确"）为无法消歧，在主结论、原始判断、信号重判各分支一律拒收（`macro_stated_confidence`），也不算告知把握程度。顺带把"倾向而非明确"认作单层否定。
   - **测试**：`test_a_confidence_denied_is_not_one_told` 新增"把握程度并非不是明确""不能说不是明确的结论"（审查两句，经 `ReportService.generate`）与"并非不是倾向"（逻辑上成立也保守拒收），均 `macro_stated_confidence`；"把握程度为倾向而非明确"正例通过。原有"不能解释为明确结论""不是明确的结论"两句真实正例仍通过。
   - **验证（合并 macro-followups 7001550 后）**：`python tools/check.py quick tests/reports/test_real_macro_readings.py tests/reports/test_macro_report.py tests/reports/test_noncanonical_reading.py tests/reports/test_report_boundary.py tests/reports/test_cli_protocol.py tests/integration/test_confirmation_publish.py tests/maintenance/test_quality_output_consistency.py`（flock）226 passed / 87.6 s，退出码 0；两例冒烟（`test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_completes_a_valid_noncanonical_projection_and_report`）2 passed / 52.7 s，退出码 0；ruff check／format、mypy `src/pring_cycle/reports.py` 通过。

## ms-rf2b：完整度与体检

3. **S3（规格 P2）超出时效行所述范围的计划期**：DR007 场景里应有期 08-27、持有 08-26，计划期 08-28 被算进"其他缺失"，缺口清单却只写"落后一期，沿用上一期（应有期 08-27，持有 08-26）"。晚于应有期的计划期同样"未到应有期"，应归入门禁列；应有期及以前、未持有的期须逐期在缺口清单中可见（或明确归类）。把测试辅助 `_names` 改成对实际可见期次集合严格对账（2099-01-01 这类期不能被当作已解释）。
   - **处理（ms-rf2b，88a9729）**：先改测试再改生产代码。
     - **严格对账**：`tests/integration/test_coverage_matches_gap_list.py` 的 `_names` 只认缺口行"写出名字"的期：时效行的 `due_period`，或 `missing_periods`／`not_requested`／`not_covered`／`members_missing`／`awaiting_release` 逐项列出的期；"持有期之后的期由时效行概括"不再算解释。补断言 `_names(DR007 行, "2099-01-01")` 为假。DR007 场景计划补入应有期 08-27（行写明应有期即解释它），08-28 保留。改测试后变红：`[('CN_DR007', '2026-08-28')]` 未被解释。
     - **归类（不需新取舍，按术语表"应有期"＋10-13 决定）**：`freshness.not_yet_due` 改为按应有期判断——计划期晚于该指标时效记录的应有期（current 且未写应有期时取持有期），且未持有、无门禁、非等待发布、非部分持有，即标 `not_due: {carried_period: 持有期}`，不论 current 还是 stale／missing；完整度计入门禁列，缺口清单不列。DR007 08-28 由此计入门禁（沿用 08-26），其时效行照旧写"落后一期（应有期 08-27，持有 08-26）"。
     - **持有期与应有期之间的期逐期列出**：新增落后两期场景（USDCNY 中间价持有 08-25、应有期 08-27，计划 08-26、08-27 未取得）先变红（08-26 未被解释）。`_historical_periods` 不再把"持有期之后"一概交给时效行：时效行只代表它写明的应有期（及其后未到期的期），早于应有期的未持有期作为 `missing_periods` 记在该行（页面"历史缺期"）；"后面没有已持有期"的跳过条件同时看有没有更晚的应有期。
     - gap_list 既有口径不动：`test_gap_list.py`（CSI300）与 `test_release_preannouncement.py`（CPI）照旧通过。
     - **正式库只读模拟**（`mode=ro`，新 `not_yet_due` 作用于最终计划与 `batch_freshness`）：run-3ebbe323 仍只标 VIX 10-19、run-153de306 仍只标两只债券 10-19，与票 15 结果一致；新增差异只有 run-25ac18e4 的 NASDAQ_SOX_INDEX 10-13（未持有任何期、应有期 10-12，`carried_period` 为空），由其"未持有（应有期 10-12）"时效行说明。近 6 次运行没有"持有期与应有期之间"的未取得期。已发布投影不回填。
4. **S4（建议）列名**：完整度表总数列"应有期"实际含未到应有期的计划期，改为"计划期数"（或与术语表一致的等价写法），页面测试同步。
   - **处理**：`cockpit.coverage_table` 总数列改名"计划期数"（新旧投影同一表头，计数照发布值显示）；表下说明句随 S3 改为"晚于应有期的计划期未到应有期（如已发布、尚未持有的下一期），沿用已持有的一期，也计在门禁一列，不列为缺口。"（原句"时效仍为当前"对 stale 指标不成立）。`tests/web/test_reading_section.py` 先改断言变红再改源码。
5. **S5（建议）时效摘要成组传递**：`held_periods` 与 `freshness_status` 同键同源，收束为一份有类型的逐指标时效摘要由 Worker 传入、汇总消费；改动小于半天就做，否则在 Comments 说明不做的理由。
   - **处理（做了）**：`freshness.MetricFreshness`（`status`、`held_period`、`due_period`，`from_row` 读 `batch_freshness` 行，`due_by` 给出应有期）。`RunMaterials` 的 `held_periods`、`freshness_status` 合并为 `freshness: Mapping[str, MetricFreshness]`；Worker 仍只读一次 `batch_freshness` 并逐行转换；`summarize_target` 从中取持有期给 `awaiting_stated_release`／`add_projection_gaps`，整份交给 `not_yet_due`。`add_projection_gaps` 的 `held_periods` 参数不变（测试直接调用的接口）。两处旧测试（`test_day_summary.py` 社融、`test_awaiting_release_group.py` 布伦特）改传 `MetricFreshness`，断言不变。
6. **S6（票 14）**：补"把握程度不一致 → 报 `macro_confidence` 不一致"的持久化负例（可参数化）。
   - **处理**：`tests/maintenance/test_quality_output_consistency.py` 把阶段不一致负例参数化为 `test_v0016_report_stating_another_macro_stage_or_confidence_is_inconsistent[macro_stage-stage_iv / macro_confidence-explicit]`，各断言"值不同的键：<该键>"与不一致标记。实现早已正确（审查探针已证），此例为回归锁定，未经红灯。
   - **测试（S3–S6，venv `dev-venv-msrf2b`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-msrf2b`，`PYTHONDONTWRITEBYTECODE=1`，均 flock）**：
     - 合并前受影响：`python tools/check.py quick` test_coverage_matches_gap_list、test_gap_list、test_warrant_historical_gaps、test_awaiting_release_group、test_derived_context_freshness、test_official_pmi_fallback、test_display_projection、test_release_preannouncement、web/test_reading_section、web/test_conclusion_board、maintenance/test_quality_output_consistency → 109 passed（460 s）；test_day_summary、test_gap_source_repairs、test_holiday_freshness → 44 passed（152 s）；test_official_social_financing_fallback、test_credit_impulse、test_confirmation_publish、test_decertified_main_chain → 128 passed（380 s）；test_macro_judgement、test_model_version_switch、test_worker_calendar_gate、test_core_carry_forward → 37 passed（263 s）；test_context_projection → 49 passed（14 s）；重型 `python -m pytest tests/integration/test_worker_registered_catalog.py`（Worker 传参改动）→ 2 passed（398 s）。
     - 合并 macro-followups df4b6fd 后：test_coverage_matches_gap_list、test_awaiting_release_group、test_warrant_historical_gaps、web/test_reading_section、web/test_conclusion_board、web/test_board_footer、maintenance/test_quality_output_consistency → 52 passed（134 s）；两例冒烟 2 passed（45 s）。
     - `ruff check`／`ruff format --check`（改动文件）、`mypy`（freshness、day_summary、worker、cockpit）通过；`find src tools -name __pycache__` 为空。

## ms-rf2c：票 16 审查建议（review-16-20261020.md）

7. **S7**：启动壳遇到缺 `conclusion` 的宏观块时显示"宏观判断数据不可用"，不当作合法的"无可取阶段"；补空块测试。
8. **S8**：副标题"五维定宏观阶段"按 GLOSSARY.md 改用规范词（宏观判断阶段），同步 test_macro_signal_board 的断言。
9. **S9**：补三个兼容用例：旧投影抽屉含完整旧术语时保持原样；`current_stage`／`stated_stage` 经仓库读取后的页面文案；未知 check 的回退文案。

### ms-rf2c 处理记录（2026-10-20，分支 ms-rf2c）

- **S7**：`web._meaningful_dashboard_shell` 只在宏观块的 `conclusion` 是字典时调用 `macro_title`（合法"无可取阶段"即 `stage` 为空的结论，照旧）；块缺 `conclusion`、为 `null` 或不是字典时显示"宏观判断数据不可用"，不在页面补算。测试 `tests/web/test_projection_api.py::test_deferred_dashboard_shell_does_not_read_a_judgement_without_its_conclusion`（3 例：`{}`、`conclusion: null`、`conclusion` 为字符串；先红：前两例误显示"无可取阶段"，第三例 AttributeError）。
- **S8**：`cockpit.MACRO_BOARD_SUBTITLE` 改为"五维定宏观判断阶段 · 价格表象作验证 · 库存 · 归因，一板看完"；`test_macro_signal_board.py::test_a_page_led_by_the_judgement_calls_the_cores_stage_the_price_stage` 断言新副标题，并断言首页与阶段史页不出现"宏观阶段"（先红后绿）。
- **S9**：只补测试、不改源码（锁定现有行为，各自做过变异核验：改掉对应分支后测试失败，恢复后通过）。
  - 旧投影抽屉：`tests/web/test_asset_cards.py::test_an_older_set_keeps_the_formal_stage_in_the_bond_attribution_drawer`——无宏观块时归因抽屉末段"……不由宽松程度推算或改写债券牛熊与正式阶段"原样保留、不出现"价格阶段"。
  - 经仓库读取：`tests/web/test_board_footer.py::test_template_reason_for_a_rewritten_stage_read_back_from_the_repository`（2 例：旧投影下 `current_stage`、`stated_stage` 经真实 `ReportService` 拒收、`ReportRepository` 读回后，结论板写"codex_cli 输出改写正式阶段被拒"，并核对审计记下的 check）；`test_template_reason_under_the_judgement_calls_the_rewritten_stage_the_price_stage`（宏观投影下 `current_stage` 写"输出改写价格阶段被拒"）。
  - 未知 check：`test_template_reason_for_an_unknown_check_is_the_outcomes`——审计 check 不在映射表时按结果码写（`conclusion_mutation_rejected` → "输出改写结论被拒"），不显示 check 原名。
- 未碰 `reports.py` 与完整度表；测试辅助未复用 `tests/reports/test_macro_report.py`，避开 ms-rf2a 的改动区。
- 运行（venv `dev-venv-msrf2c`，basetemp `/tmp/pytest-msrf2c`，`PYTHONDONTWRITEBYTECODE=1`，flock）：macro-followups 最新头仍为 7001550，合并为空操作；`python tools/check.py quick` test_projection_api、test_macro_signal_board、test_board_footer、test_asset_cards、test_conclusion_board、test_cockpit_http、tests/reports/test_macro_report＋两例冒烟 **129 passed（98 s；另排队等锁约 6 分钟）**。ruff check／format、mypy（web.py、cockpit.py）通过。

## ms-rf3a：第三轮复审（review-report-check-20261020-r3.md）

收口标准（不再开第四轮对抗探针）：把 r3 报告中的 30 句绕过探针 N1–N30 与 12 句合法改写 L1–L12 全部固化为参数化测试——N 组错误陈述全部拒收（含此前已拒收的 15 句），L 组合法句全部通过；上一轮 6 个反例与两份真实输出保持现状。r3 之后新发现的边角写法记为已知残余风险，另开票。

10. **S10（B1）**：条件作用域结束时同步结束主语继承；无法判定归属的独立结论按主结论核对。
11. **S11（B2）**：点名指标的改投／重判陈述绑定该指标，不依赖条件词白名单；无法绑定的条件推演按主结论核对。
12. **S12（B3）**：识别省略"第"的阶段写法（"五阶段""三阶段向四阶段"），有词法边界，统一转阶段代码。
13. **S13（B4）**：否定作用域不在括号、冒号处清空；跨标点嵌套否定拒收。
14. **S14（误拒）**：识别"不是 A 而是 B"、"没有滞回保持且……"、"没有改变倾向的……"中否定的真实对象；条件结果中的"宏观判断会变为……"不当作现实边界（L2、L3、L4、L6）。
15. **S15（建议）**：若改动自然，把"陈述主语＋信号身份＋作用域"收成一处结果供阶段、把握程度、转换三类核对共用。

### ms-rf3a 处理记录（2026-10-20）

先把 r3 的 N1–N30、L1–L12 原句（各前置"宏观判断为第三阶段，把握程度为倾向。"）固化为 `tests/reports/test_real_macro_readings.py` 的两组参数化测试（`test_a_judgement_told_otherwise_is_refused_however_written[N1–N30]`，期望拒收于 `macro_stated_stage`／`macro_stated_confidence`；`test_a_judgement_told_right_is_accepted_however_written[L1–L12]`，期望通过）。改前红的恰为复审标出的 19 句：N5、N6、N13、N15、N16、N17、N18、N20、N23、N24、N26、N27、N28、N29、N30 与 L2、L3、L4、L6。改动只在 `src/pring_cycle/reports.py` 的宏观陈述校验。

- **S10 处理**：条件作用域结束处插入"恢复主结论"的主语标记（`_read` 中的 `ends`），结束条件即结束主语继承；`_ACTUAL` 增加"判断／结论按现状陈述"一类（`本次判断为`、`报告结论已经是`、`主结论为`、`本日判断为`），不含"会变为"。N5、N6、N23、N24、N26、N27、N30 转红为绿；N1、N7、N22 保持拒收。
- **S11 处理**：点名改投／重判的分句（`_RECOUNTED`：改投、改按、少数方向、改判、重判）不依赖条件词即开启重判作用域，绑定分句点名的那个分化；分句未点名指标时绑定句中最近的"X 分化"；都绑不上的按主结论核对；已在条件作用域内且未另点名的视为该条件的结果。N20 转绿；真实 claude 输出"社融分化（…），按少数方向重判仍是第三阶段（倾向，与第四阶段并列）"现在按社融的重判核对，仍通过。
- **S12 处理**：`_MENTION` 增加省略"第"的中文数字阶段（`五阶段`、`三阶段向四阶段`），前置字排除"上一／同一／单一／每一／前三／共六"等量词与序数用法。N13、N15、N16 转绿。
- **S13 处理**：`_denied` 的否定作用域只在逗号、"而是"、"且"处结束；冒号、括号仅在其前没有悬空否定（`并非`、`不能说`、`不是`）时才断开，否则外层否定计入，嵌套否定按 S2 返回 None 拒收。N17、N18、N28、N29 转绿，N19 与上轮两句双重否定保持拒收。
- **S14 处理**：同上，"不是明确而是倾向"中"而是"后不再受前一否定；"没有滞回保持且……"在"且"处结束否定；"没有改变／没有变化／不变"不计为否定（断言原状成立）；`_ACTUAL` 去掉单独的"宏观""主结论"，条件结果"宏观判断会变为……"仍按重判核对。L2、L3、L4、L6 转绿。
- **S15 处理**：新增 `_Sentence`／`_read`，每句一次算出阶段提及、各提及的主语、主语标记序列（含条件起止）与重判作用域，阶段、把握程度、转换三类核对共用这一结果；`_conditions` 拆出 `_hold`（作用域结束位置）与 `_divergence_before`。
- **测试**：`tests/reports` 全部＋`test_confirmation_policy`、`test_confirmation_projection`、`test_confirmation_publish`、`test_macro_signals`、`test_macro_fallback`、`test_price_verification` 共 451 过（413 s）；其中 `test_real_macro_readings.py` 78 过，含 42 句探针、上一轮 6 个反例与两份冻结真实输出。两例冒烟 2 过（49 s）。ruff、mypy 通过；`find src tools -name __pycache__` 为空。macro-followups 头 8d4ad9a 自本分支起点未变，无需另行合并。
- **残余风险**（未扩展新探针，记此另开票）：省略"第"的识别靠前置字排除表，"分为六阶段"一类会被读作第六阶段；按现状陈述的识别靠"判断／结论＋为／是"，"规则判断为"写在条件结果中会按主结论核对（保守拒收）。
