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
4. **S4（建议）列名**：完整度表总数列"应有期"实际含未到应有期的计划期，改为"计划期数"（或与术语表一致的等价写法），页面测试同步。
5. **S5（建议）时效摘要成组传递**：`held_periods` 与 `freshness_status` 同键同源，收束为一份有类型的逐指标时效摘要由 Worker 传入、汇总消费；改动小于半天就做，否则在 Comments 说明不做的理由。
6. **S6（票 14）**：补"把握程度不一致 → 报 `macro_confidence` 不一致"的持久化负例（可参数化）。

## ms-rf2c：票 16 审查建议（review-16-20261020.md）

7. **S7**：启动壳遇到缺 `conclusion` 的宏观块时显示"宏观判断数据不可用"，不当作合法的"无可取阶段"；补空块测试。
8. **S8**：副标题"五维定宏观阶段"按 GLOSSARY.md 改用规范词（宏观判断阶段），同步 test_macro_signal_board 的断言。
9. **S9**：补三个兼容用例：旧投影抽屉含完整旧术语时保持原样；`current_stage`／`stated_stage` 经仓库读取后的页面文案；未知 check 的回退文案。
