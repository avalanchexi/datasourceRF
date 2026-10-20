# 第二轮审查修复（票 13–15，2026-10-20）

依据：`review-standards-20261020-r2.md`、`review-spec-20261020-r2.md`（范围 74cdb38..06b7503）。两个子代理：ms-rf2a 修 S1–S2（报告校验），ms-rf2b 修 S3–S6（完整度与体检）。

## ms-rf2a：报告宏观陈述校验

1. **S1（阻断）条件作用域过宽、按并集核对**：只对明确描述"某指标变化 → 重判结果"的条件分句启用重判核对，并绑定到被点名的那条信号（如 PMI → 该信号的 `rejudged`），核对它自己的阶段、把握程度与有序转换端点（from→to）；表达性条件（"如果读者需要一句话概括"）、转折后的现实陈述（"但本次……"）、无法绑定到具体信号的条件分句，一律按主结论核对（宁可误拒，不可放过）。补审查给出的四个反例：两段"借条件改写主结论"、"PMI 改投后变为第三阶段倾向／第三阶段向第三阶段转换"、"第五阶段明确但写成第三阶段向第四阶段转换"，均须拒收；两份真实输出仍整份通过。
2. **S2（阻断）双重否定**：识别完整否定结构；单层否定才走放行分支；双重否定（"并非不是明确""不能说不是明确的结论"）及无法消歧的嵌套保守拒收。补这两句反例（经 `ReportService.generate` 或现有校验接缝）。

## ms-rf2b：完整度与体检

3. **S3（规格 P2）超出时效行所述范围的计划期**：DR007 场景里应有期 08-27、持有 08-26，计划期 08-28 被算进"其他缺失"，缺口清单却只写"落后一期，沿用上一期（应有期 08-27，持有 08-26）"。晚于应有期的计划期同样"未到应有期"，应归入门禁列；应有期及以前、未持有的期须逐期在缺口清单中可见（或明确归类）。把测试辅助 `_names` 改成对实际可见期次集合严格对账（2099-01-01 这类期不能被当作已解释）。
4. **S4（建议）列名**：完整度表总数列"应有期"实际含未到应有期的计划期，改为"计划期数"（或与术语表一致的等价写法），页面测试同步。
5. **S5（建议）时效摘要成组传递**：`held_periods` 与 `freshness_status` 同键同源，收束为一份有类型的逐指标时效摘要由 Worker 传入、汇总消费；改动小于半天就做，否则在 Comments 说明不做的理由。
6. **S6（票 14）**：补"把握程度不一致 → 报 `macro_confidence` 不一致"的持久化负例（可参数化）。

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
