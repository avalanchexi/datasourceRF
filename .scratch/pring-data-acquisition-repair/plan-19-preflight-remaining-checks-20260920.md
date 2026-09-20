Status: assessment-only
Type: read-only-survey
Date: 2026-09-20

# #19 预检剩余五项检查的只读评估

本文件只评估，不改产品代码、不勾选验收。写作期间 #22 同版本默认全套正在执行，故全程不触碰 `src/`、`tests/`、`tools/`。

## 先更正一处过时判断

提效文档（2026-09-18）把 #28 列为「0/4、下一关键路径」。票面已在 2026-09-19 推进覆盖：`Execution: completed`，四项验收全部勾选，修复提交 `4be17e2`、收尾提交 `c5f0796`（即整合树当前 HEAD）。**#28 不是下一张票**；引用提效文档的票况时必须回票面核对。

## 对应的验收条件

#19 第 50 行：「接收必要家族的软件合同及合法输入，逐项预检**完整目录、维度、原件、点时及派生父项**；材料无法通过时列出具体缺件，不能删 P1、套用旧认证或复制生效记录来制造完整模型。」

这与 `material_preflight.py:312` 硬编码的 `pending_checks = ["calendar", "originals", "dimensions", "point_in_time", "parents"]` 一一对应。该列表是静态常量，从未随实现缩减——所以 `checks_complete` 永远为 false，这是设计上的保守，不是缺陷。要让它为 true，须逐项给出「已覆盖到何种程度」的证据，并把列表改成按实际覆盖计算。

## 逐项现状

当前预检产出的诊断标识（源码实测）：`source_material_missing`、`input_selection_missing`、`input_stale`、`daily_coverage_missing`、`input_warmup_missing`、`core_history_input_missing`、`core_history_original_invalid`、`formula_inputs_unavailable`、`formula_lineage_missing`、`invalid_parent_claims`、`missing_input_periods`、`calendar_material_invalid`、`calendar_normalized_original_mismatch`、`calendar_range_not_covered`。测试 11 项、源码 495 行、测试 709 行。

| 检查项 | 已覆盖 | 仍缺 |
| --- | --- | --- |
| `calendar` | 收据路径的有效/坏 raw/坏 normalized/请求范围超界四场景；raw 与 normalized 双向哈希校验并经公开 `TushareCoreAdapter.trading_days` 重解析比对；`late_capture` 按 `inspected_at` 取得截止 | 日历**声明**分支的原件资格未验（合法注册候选无法经公开入口新增此类标量声明，当时三场景均在 `append_source_claims` 前置失败，不是预检 RED）；PUBLIC/SYSTEM 截止语义未逐项核对 |
| `originals` | 融资、日历、GDP 父项、核心三项的坏原件均有反例；跨调用守卫（首次合法、破坏后二次必须报缺）；未来坏修订不污染旧选值 | 未覆盖全部 59 项目录的原件路径，仅覆盖已写反例的家族；「完整有效材料正例」尚无 |
| `dimensions` | 经 `ModelInputSelector.select` 的真实维度守卫间接覆盖（`missing_members`） | **无专项反例**：缺某维度成员时的诊断未被独立钉住；`required_dimension_members` 为 None 的合同不可用分支未验 |
| `point_in_time` | 已知 PUBLIC / 原件损坏 / 未知 PUBLIC / 未来 PUBLIC 四场景；未来坏修订隔离；逐日 PUBLIC 选值而非只验末日 | 仅「当前材料上的历史 PUBLIC」一种模式；**任意双截止 SYSTEM 回放未验证**，记录中已明确不得宣称 |
| `parents` | 信用脉冲缺社融差分基线、`missing_input_periods` 精确到 `CN_SF_TOTAL:[2026-06]`、历史坏父项定位到 `CN_GDP/2024-Q3/claim_id`、P2 必要/可选分类、公式预热覆盖 | **全公式诊断范围未审**：仅验证了信用脉冲与 UST 利差路径，其余公式是否都能给出父项级诊断未逐一确认 |
| （目录完整性） | 候选目录 59 项计数可读 | 「逐项汇总 61 项目录」是 #19 另一条独立验收（第 21 行），**不属于预检**，不要混记 |

## 规格轴复核新增的两条（2026-09-20，已核实代码属实）

这两条本评估最初漏掉，由独立规格轴指出，优先级高于下面原有的建议顺序：

- **完整目录漏两项 P0**：`material_preflight.py:101-106` 裸 `continue` 跳过 `CN_RELEASE_SCHEDULE` 与 `SOURCE_OBSERVED_AVAILABILITY`（实为 P0 / awaiting_source_certification），材料全缺也不产条目。仿照来源 `full_retrieval.py:213-220` 会输出 `{"status": "operational_evidence"}` 保留可见性。反例应为：这两项材料缺失时，预检结果里必须能看到它们（哪怕标为运维证据），而不是消失。
- **密度检查绕过点时**：`material_preflight.py:152-163` 的 `observed` 只要求 `public_available_at is not None`，从不与 business_date 比较。反例应为：某日频指标 120 天数据全部在窗口结束后才发布，`daily_coverage_missing` 当前为空、修复后应报缺。这条使 `pending_checks` 里的 `point_in_time` 在密度维度实际未生效，属「看似实现而实现有误」，应排在维度专项之前。

## 下一切片的建议驱动顺序

按「先写会失败的反例，再改实现」：

1. **维度专项**（缺口最明确、成本最低）：构造合法候选后删去某多维指标的一个维度成员，预检应精确报出 `metric_id` 与缺失成员，而不是只给 `input_selection_missing`。再补 `required_dimension_members` 返回 None 时的合同不可用分支。
2. **全公式父项诊断范围**：遍历 `rules.formula_versions`，对每个公式各造一次父项缺失，确认都能返回父项级诊断而非只列公式失败。
3. **完整有效材料正例**：在 2026-09-20 首次跑通的整窗基础上（120 天、必需 gaps 0），补一条断言「合法完整材料下必需缺口为空且五项检查均已执行」的正例。这是把 `pending_checks` 从静态常量改为按实际覆盖计算的前提。
4. **日历声明分支**：需要先确认合法公开入口能否为注册候选新增 `CN_TRADE_CALENDAR` 标量声明；若确实不能，应把该分支记为「合同上不可达」并从 pending 中移除，而不是留着一个永远无法验证的待办。
5. 最后才是生命周期接入与 `checks_complete` 的真值化。

## 明确不做的事

不为缩短 pending 列表而降低任一门槛；不把合成隔离材料的通过登记为真实来源认证；不把 #19 第 21/40/42/54 行的真实候选与来源条件与本预检条件混为一谈。整窗预检跑通只证明**那份合成材料**在 120 天窗口上无必需缺口。
