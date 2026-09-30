# 09: 缺口清单同时列出冲突与来源失败

**What to build:** 一个成员既来源冲突、选中声明又复核失败时，投影行保留冲突原因，缺口清单同时列出 `source_conflict` 与来源失败。顺带查看时效读取未检查 `selection_status` 的问题。

**Blocked by:** 05、16（05 先改写投影行附近的家族复核；16 与本票同改缺口清单，按缺口链排在其后）

**勿并行：** 02、04、06、07、08、18、19、20、21、23、24、26、27、28、30（同改：上下文投影；缺口清单与时效；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 2 差异 4（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状

- 投影行状态中 `source_failed` 覆盖先算出的 `conflicted`，冲突原因只在最终状态为 `conflicted` 时输出（`context_projection.py:1632`、`:1707`、`:1751`）。缺口清单从投影行收集冲突（`freshness.py:1064`），于是冲突一面从清单消失。
- `freshness.py:594`／`:600` 判断持有哪一期时只看有无选中值，未要求 `selection_status == selected`。**不在本票改成"只认可采用声明"**：时效只记录取到哪一期，可否采用由投影与缺口清单表达（用户决定，2026-09-29）。本票只确认冲突期是否被当作"持有"、是否符合"冲突要进入缺口清单"，再定是否需要改。

## 验收

- [x] 投影行在来源失败时仍带冲突原因；缺口清单两者都列。
- [x] 按 TDD 补用例：冲突且选中声明原件损坏 → 清单同时有 `source_conflict` 与来源失败。
- [x] 时效 `selection_status` 的查看结论写入本票 Comments（改或不改及理由）。
- [x] 受影响测试经 `check.py quick` 通过。
- [x] 代码审查无阻断。

## Comments

- **设计（用户决定，2026-10-01）**：缺口清单新增类别 `source_failed`「来源失败」，与同时冲突的合为一条，条目里附 `conflicts` 明细。只有复核失败的指标也进清单。页面加中文标签。
- **实现**：
  - 投影行只要观测有冲突原因就带 `conflict_reason`，不再只限最终状态为 `conflicted` 的行。
  - 选中声明被家族复核拒收时，行上另加 `source_failure: "not_adoptable"`。拒收原因包括原件、命中原话、成员或注册契约复核不通过。
  - `add_projection_gaps` 只认这个标记，不从 `status == "source_failed"` 推断。所以 LPR 本期取数失败的行、没有家族复核的声明都不进这个类别。
  - 条目附 `source_failures`（期别、维度、原因），并与冲突收集共用 `_by_member` 按成员去重。
  - 指标已在清单里（如时效缺口）时，保留原类别，只附明细；页面在该条目后注明「来源复核失败」或「来源同时冲突」。
  - 报告仍只传类别代码，没有中文标签表，不需要改。
- **时效 `selection_status` 的查看结论（不改）**：
  - 冲突观测仍有选中值，`record_run_freshness` 只看值非空，所以冲突期算"持有"，不进时效缺口。
  - 这符合"时效只记录取到哪一期"的决定。上下文指标的冲突由投影行经 `add_projection_gaps` 进入清单；本票以后，复核同时失败时也不会丢失。
  - 既有遗漏如实记录：股票、债券三核心不是上下文行，缺口合并只读宏观与库存投影。所以核心的当期冲突既不进时效缺口，也不进清单，只由核心就绪检查阻断正式阶段（`day_summary.py` 就绪判断）。
  - 这属于票面外的行为问题，按约定只记录、不修。
  - 融资、估值、CSI 指数目前不作为上下文行读取，同理不会进清单。
- **可观察影响**：
  - 新条目会让报告 `gap_summary.counts` 多出 `source_failed`，P0/P1 摘要也会列出。
  - 可能新进入该类别的有：仓单缺成员、降准公告不完整、LPR/官方宏观/银行间/国债复核失败，以及 NHCI/CNY030/930916 原件损坏。
  - 不影响 P0 阻断、运行状态和阶段判定。宏观信号仍按 `status` 判断。
- **测试**（先红后绿）：
  - `test_official_pmi_fallback.py::test_a_conflict_whose_selected_delivery_fails_its_recheck_keeps_both_in_the_gap_list` 走真实链路：PMI 候选目录中 TuShare 与国家统计局两家认证来源冲突，损坏 TuShare 原件后，行为 `source_failed`，同时带冲突原因与标记；清单为 `source_failed`，同时有两类明细；页面两个提示都在。
  - 先用替换复核结果的版本确认了红灯，按审查意见改成真实链路。
  - `test_derived_context_freshness.py::test_only_a_refused_claim_is_a_source_failure_shown_on_its_listed_gap`：取数失败行不进清单；已有时效缺口的条目附明细，页面显示提示。
  - `test_lpr_gap_uses_a_recorded_source_failure_after_the_release_window` 补断言：取数失败行不带标记。
- **验证**（`PYTHONPATH=src`）：涉及投影、时效、页面及所有完整运行的测试文件，共 799 例全过（45.8 分钟）；复审后补的断言单独跑通过。ruff、mypy 通过。
- **审查**（Codex 只读，两轮）：
  - 第一轮阻断项已修：把所有 `source_failed` 行都当复核失败；已有类别下页面看不到来源失败；缺真实损坏链路。
  - 第二轮指出质量非 validated 的注册声明也会被标为不可采用。经判断，这是注册契约复核拒收，属于来源失败口径，只改正了注释中过强的边界表述。
