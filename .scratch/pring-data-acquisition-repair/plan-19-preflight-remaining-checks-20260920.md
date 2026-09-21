Status: assessment-only
Type: read-only-survey
Date: 2026-09-20

# #19 预检剩余五项检查的只读评估

本文件只评估，不改产品代码、不勾选验收。写作期间 #22 同版本默认全套正在执行，故全程不触碰 `src/`、`tests/`、`tools/`。

## 先更正一处过时判断

提效文档（2026-09-18）把 #28 列为「0/4、下一关键路径」。修复提交 `4be17e2` 确已落地，**#28 不是下一张票**；引用提效文档的票况时必须回票面核对。

> **2026-09-21 订正**：本段原先写作「票面已在 2026-09-19 推进覆盖：`Execution: completed`，四项验收全部勾选」——**这句不属实**。`git log --all` 对 #28 票文件只有一次提交 `6c5f5f1`（创建），票面直到 2026-09-21 仍是 `Execution: not-started`、0/4 勾选。`4be17e2` 落地了代码与测试，但没有更新票面。本段自己的结论是「必须回票面核对」，而它当时恰恰没有核对。逐条现状见[#28 事实对齐](finding-28-calendar-facts-20260921.md)。

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

## 2026-09-20 实施发现：维度反例对 margin 家族不可达

尝试为 `CN_MARGIN_BALANCE`（要求 `financing_balance` 与 `financing_buy_amount` 两个 measure）构造缺维度成员反例，两条路都被合法公开守卫在更早位置拦住：

1. 持久化时过滤掉 `financing_buy_amount` 标量 → `registered_margin_acquisition_values_mismatch`：持久化标量必须与原件内容一致。
2. 原件本身去掉 `rzmre` 列 → `tushare_response_required_field_missing`：交付缺必需字段在传输边界即被拒。

**结论：对该家族，「缺维度成员」这一状态无法经合法公开入口到达**——守卫在产生任何声明之前就触发。这与本票历史上日历声明分支的情况同型（当时三场景均在 `append_source_claims` 前置失败）。按既定规矩不绕合同造夹具，该测试已撤除，未留失败用例。

因此维度这一项的下一步应改为：(a) 换一个成员集合合法可变的家族——CPI 的 measure 集合按报告月变化（1 月无 cumulative 列），那是合法变化而非缺口，需要先确认是否存在「应有而未交付」的合法可达状态；(b) 若逐家族核对后确认所有注册家族都不可达，则应把 `dimensions` 从 `pending_checks` 移出并记为「合同上不可达」，而不是留一个永远验不了的待办。这一判定本身需要逐家族核对，属独立切片。

### 维度可达性：区分点不是守卫，是交付粒度

进一步只读核对（2026-09-20，全套运行期间的并行只读工作）：`REQUIRED_DIMENSION_MEMBERS` 共 10 个家族。margin 之所以不可达，不是因为守卫特别严，而是因为**它的全部必需成员来自同一次交付**——同一份原件里缺列会被响应字段校验拦住，事后过滤标量会被原件一致性校验拦住。

`CN_INDEX_VALUATION` 则不同：`TushareContextAdapter.index_valuation` 对 `VALUATION_INDEX_CODES` **逐指数分别 `_call`**（`tushare_context.py:968` 起）。因此「某个指数那一次返回空行」是完全合法的交付形态，会自然产生缺该指数全部 measure 的声明集，**无需绕过任何合同**。

**下一切片的维度反例应建在 `CN_INDEX_VALUATION` 上**：交付 000300 与 000905 而 000852 为空，断言预检精确指出缺失的是 `{"index": "000852.SH", ...}` 三个 measure，而不是只给一个笼统的选择失败。

其余家族按同一标准分类（同次交付 vs 分次交付）仍待逐个核对，但该判据已经明确，不必再逐个撞守卫去试。

> **2026-09-21 订正**：逐家族核对已完成，见[维度可达性分类](finding-19-dimension-reachability-20260921.md)。**上面这条判据只覆盖了一半**：除「分次 `_call` 某次空行」外，还有第二条合法通道——同次交付内 builder 遇空值若 `continue` 而非 `raise`，也会少产成员，且原件一致性校验此时比对的是「短集 vs 短集」，恒相等因而拦不住。所以决定可达性的是 **builder 对缺值的处置方式**，不只是交付粒度；margin 不可达是因为两条通道都被堵（单次 `_call`，且缺值处 `raise tushare_margin_value_missing`，`tushare_context.py:875`）。
>
> 结论：`dimensions` **可达**，应保留在 `pending_checks` 并落反例，不得记为「合同上不可达」。反例仍建在 `CN_INDEX_VALUATION` 上，但上面这句「断言三个 measure」需按目录版本核定期望集；另注意 `CN_FUTURES_WARRANTS` 虽可达却走专用诊断（`symbol_missing:{symbol}`），钉不住 `required_dimension_members`，不可用作反例。
