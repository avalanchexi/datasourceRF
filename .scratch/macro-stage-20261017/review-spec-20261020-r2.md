**结论：规格轴部分满足，不能认定全部验收通过。** 13 的真实误拒已修复，但条件推演仍会漏拒错误阶段和转换端点；15 修复了 VIX／债券的已知差额，但“其他缺失逐期可对账”的验收仍不成立。14 的实现正确，缺少把握程度不一致的持久化回归用例。R1–R4 满足；R5 完成最低要求，完整建议部分满足。

审查范围严格为 `74cdb38..06b7503`。全程只读，未修改文件。下文区分本次实测与实施者记录：本次在内存中复核报告校验的全部 20 组输入，直接执行 3 个审计测试和 5 个页面测试函数，均通过；未重跑需要写运行库的集成测试、冒烟或正式库完整体检。

**两项实质缺口**

1. **[P2] 13：条件推演按全部信号并集校验，不能保证对应信号的结论正确。**

   冻结输入中，PMI 重判是 `stage_v / explicit`，转换为 `III→V`。本次调用完整 `_validate_ai_document`，以下错误改写均返回 `succeeded`：

   - PMI 改投后“判断会变为第三阶段，把握程度为倾向……第三阶段向第三阶段转换”。
   - 保留“第五阶段、明确”，但将转换写成“第三阶段向第四阶段转换”。

   原因见 [reports.py:1751](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1751)：阶段及转换端点取所有信号的并集；[reports.py:1835](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1835) 的阶段／把握程度配对也取全部 `rejudged`。现有反例主要使用集合外的第六阶段，未覆盖“借用另一条信号的合法结果”。

   **建议：**将已明确点名的 PMI 条件分句绑定到 `D-pmi`，同时核对该信号的阶段、把握程度和有序转换端点；补上述两个负例。Comments 已披露并集限制，但这不能替代票 13 第三条验收要求。

2. **[P2] 15：对账测试把未列出的期当作已解释，掩盖实际漏列。**

   新测试自身的 DR007 场景把 **08-28** 算入“其他缺失”，而清单实际只显示：

   > 落后一期，沿用上一期（应有期 2026-08-27，持有 2026-08-26）

   没有列出 08-28，也没有说明该期为何不列。见 [test_coverage_matches_gap_list.py:70](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_coverage_matches_gap_list.py:70)、[该文件:134](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_coverage_matches_gap_list.py:134)。

   测试辅助函数 [_names:98](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_coverage_matches_gap_list.py:98) 只要发现 `due_period` 非空、待核日期晚于持有期便返回真；本次实测传入 **2099-01-01** 也返回真。生产代码 [freshness.py:1358](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/freshness.py:1358) 同样把这些期交给时效行概括，页面没有逐期展开。

   **建议：**对实际发布、可见的期次集合做严格对账；对超出时效行所明确说明范围的计划期，逐期列出或明确归类。此行为部分承袭旧实现，但它直接反驳本票新增的广义验收，不能因新测试通过而关闭。

**票 13：逐条验收**

测试证据集中于 [test_real_macro_readings.py](/home/tywin/worktrees/datasourceRF-mf/tests/reports/test_real_macro_readings.py)。

| 验收项 | 判定 | 证据与建议 |
|---|---|---|
| 两份真实完整输出离线固化、通过，`confidence_told=True` | **满足** | `test_the_first_v0016_readings_are_accepted_whole`。本次核对两份原件 SHA-256 与 fixture 内容一致；完整校验均成功，首节均为 `confidence_told=True`。建议保留。 |
| 三类真实句子各有整句正例 | **满足** | `test_the_scores_each_stage_got`、`test_a_confidence_denied_is_not_one_told`、`test_a_recount_under_a_condition_is_read_as_the_recount`；整句均在本次内存复核中通过。建议保留。 |
| 错得分、错主阶段、错把握程度、错条件重判仍拒收 | **部分** | 前三类及集合外重判反例均拒收；“另一信号合法、当前信号错误”的重判和转换仍放行，见缺口 1。建议补绑定及负例。 |
| 不扩大主结论集合、不按整句否定跳过 | **满足** | [reports.py:1741](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/reports.py:1741) 仍只允许主结论阶段；否定仅检查紧邻前缀，且否定不算告知把握程度。测试覆盖“不是倾向”和只否定明确但未告知倾向。建议保持。 |
| 两例冒烟通过 | **满足（据记录）** | 票 13 Comments 第 31 行记录指定两例 `2 passed / 74s`；本次未重跑。建议保留该验证身份与范围。 |

第四处 `restates_confirmation` 修复**可接受**：它是实现“整份真实输出通过”必需的修复，属于同一问题范围；`test_a_relation_denied_of_every_key_indicator` 包含原句正例和两个反例，本次均核验通过。

**票 14：逐条验收**

| 验收项 | 判定 | 证据与建议 |
|---|---|---|
| v0016 不误报；阶段和把握程度不一致时报错 | **部分：实现满足，回归证明不完整** | [output_consistency.py:879](/home/tywin/worktrees/datasourceRF-mf/tools/quality/output_consistency.py:879) 根据冻结清单启用两个字段的比较。新增测试覆盖一致及阶段不一致；**没有把握程度不一致的测试**。本次内存探针将其改成 `explicit`，正确报 `macro_confidence` 不一致。建议将该探针固化为参数化负例。正式运行 `59/59` 有 Comments 第 20 行记录，本次未重跑。 |
| v0015 体检结果不变 | **满足** | `test_v0015_report_without_a_macro_judgement_stays_consistent` 本次直接执行通过；分支对旧清单不添加字段。Comments 第 21 行记录真实新旧体检除耗时外逐字一致。建议保留。 |
| 体检相关测试通过 | **满足** | [test_quality_output_consistency.py:85](/home/tywin/worktrees/datasourceRF-mf/tests/maintenance/test_quality_output_consistency.py:85) 起三个测试本次均直接执行通过。建议补齐上述负例。 |

保留旧检查名称的偏离**可接受**：不影响实际字段比较，也有保持旧版输出不变的明确理由。

**票 15：逐条验收**

| 验收项 | 判定 | 证据与建议 |
|---|---|---|
| 写明差额根因、选择与理由 | **满足** | Comments 第 16–24 行明确定位 VIX 10-19及旧运行两只债券，并引用基线代码；与 `GLOSSARY.md:281–286` 的证据时效、应有期定义一致。建议保留。 |
| 含沿用场景，其他缺失与清单逐期对上 | **部分** | [freshness.py:1050](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/freshness.py:1050) 和 [day_summary.py:340](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/day_summary.py:340) 正确将 current 指标较新的未持有期标为 `not_due`；对应 VIX／债券用例覆盖有效。但 DR007 对账存在缺口 2。建议修正严格对账断言及清单表达。 |
| 旧投影照旧显示、不前端补算 | **满足** | `test_an_older_projection_shows_its_completeness_as_published` 本次直接执行通过，旧计数仍为原始值；新分类发生在汇总阶段。建议保持。 |
| 两例冒烟通过 | **满足（据记录）** | Comments 第 29–30 行记录合并前及合并后的两例通过，最终为 `2 passed / 55s`；本次未重跑。建议保留。 |

两项声明偏离的判断：

- **Worker 多传 `freshness_status`：可接受。** [worker.py:786](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/worker.py:786) 从同一次 `batch_freshness` 同时取得状态和持有期，是实施 B 方案所需的信息传递，没有扩大业务范围。
- **选 B、计入门禁列并改列名：可接受。** 票面允许“不计其他缺失并说明归类”，也符合“下一期已公开不使 current 降级”的既定决定。列名和说明有页面测试。不过总数列仍叫“应有期”，实际包含“未到应有期”，建议改为“计划期数”，避免与术语表冲突；这不替代缺口 2 的修复。

**R1–R5：逐条核对**

| 项目 | 判定 | 证据与建议 |
|---|---|---|
| R1：`initial` 不固定称生效首日 | **满足** | [cockpit.py:2539](/home/tywin/worktrees/datasourceRF-mf/src/pring_cycle/cockpit.py:2539) 改为“无既往主结论，取当日原始判断”；`test_a_first_conclusion_after_a_day_with_no_stage_is_not_called_the_rules_first_day` 本次执行通过；集成测试补了 relink 前后 `initial` 断言。建议保留。 |
| R2：定位宏观抽屉、更正说明、双链接、更正后滞回；relink 状态 | **满足** | [test_macro_stage_history_board.py:206](/home/tywin/worktrees/datasourceRF-mf/tests/web/test_macro_stage_history_board.py:206) 定位宏观抽屉的更正行并断言文本与两链接，本次执行通过；[test_macro_signals.py:547](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:547) 和第 563 行断言 relink 从 `agrees` 到 `held`。建议保留。 |
| R3：新历史展示行补滞回，旧投影不变 | **满足** | [test_macro_stage_history.py:118](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_stage_history.py:118) 模拟宏观块存在、展示行缺滞回，断言新行补齐、按 ID 重读旧 `datasets` 完全相同及两种页面提示。票面措辞同步澄清。建议保留。 |
| R4：v0006 可采用宏观原件，宏观与价格阶段不同，区分两个基准 | **满足** | [test_macro_signals.py:904](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:904)：原件经适配器入库；宏观 IV／明确、价格 III；B2 前进 1、K4 后退 1，K4 首日确认、B2 萌芽。能区分“归组看宏观”和“确认看价格”。建议保留。 |
| R5：不落格负例与 20／120 日方向不同 | **部分，最低要求已满足** | [test_macro_signals.py:947](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:947) 覆盖普涨、普跌、广度均衡／篮子持平；[第 982 行](/home/tywin/worktrees/datasourceRF-mf/tests/integration/test_macro_signals.py:982) 覆盖最近 20 日全涨、120 日仍落 K4。缺广度“指数持平”和篮子“不一致”。建议保留为明确的测试待办。 |

R4 未提供过热、库存两维原件的偏离**可接受**：要求是最小原件集合及至少一个可区分基准的场景，三维已形成明确宏观 IV，另外两维未知没有削弱目标断言。

R5 未做两类负例的偏离**可接受，但只能按部分完成记录**：原要求明确允许按风险取舍、至少覆盖普涨普跌，最低要求已经达到。夹具构造不便是成本说明，不能据此宣称未覆盖分支已获验证。
