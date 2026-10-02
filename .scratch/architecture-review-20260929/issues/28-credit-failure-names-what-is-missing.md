# 28: 信用脉冲失败说清缺了什么

**What to build:** 把笼统的 `missing_inputs` 拆成具体原因（缺社融期数、缺 GDP 期数、差分缺基期、最新期未对齐、值为空、父点不可用等），并由模块的需求结果给出缺口里"缺哪些输入"——只列公式实际消费的成员与期别。

**Blocked by:** 23、27（与票 27 同改缺口合并，排在其后）

**勿并行：** 04、06、07、08、09、15、16、18、19、20、21、24、25、26、30（同改：上下文投影；缺口清单与时效；完整运行规划；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 5 访谈 Q5、差异 4（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 现状

- 数量不足、缺基期、末期落后、缺值、父点冲突或未验证、旧版本不许差分都报 `missing_inputs`；GDP 先查，会遮住社融问题（勘察 6.2–6.4）。
- 缺口按父指标全部未齐成员列出，含公式不读的社融存量、GDP 同比等；GDP 数据版本不可比时列表为空（勘察 2.8，`full_retrieval.py:404`、`:598`，`freshness.py:1052`）。
- 报告 AI 输入只收类别计数与摘要，不含精确原因（勘察 6.8），本票不改报告。

## 验收

- [x] 模块结果带结构化失败原因与所缺成员／期别；社融与 GDP 的问题同时报告，不互相遮蔽。
- [x] 缺口清单信用脉冲条目只列公式消费的成员与期别；数据版本不可比时说明哪几季不可比。
- [x] 按 TDD 覆盖每种原因；缺口测试在 `add_projection_gaps()` 上。
- [x] 受影响测试经 `check.py quick` 通过。
- [x] 代码审查无阻断。

## Comments

**2026-10-02 实施记录**

- **取舍**：`status` 保持原有汇总值（`missing_inputs`、`nonconsecutive_*`、`incomplete_source_artifacts`、`incomparable_gdp_vintages`、`invalid_gdp_denominator`），投影、看板、报告等消费方照旧；具体原因放进新增的结构化 `failures`。报告 AI 输入不改。
- **模块** `credit_impulse.py`：
  - `InputFailure(metric_id, reason, periods, members)`，`CreditImpulseResult.failures`。成员按计划 `missing_members` 的键写，只含该公式版本会读的口径。
  - `_shortfall`：从版本可读口径的最新持有期回推窗口，逐期归因，共 8 种：`missing_periods`、`value_missing`、`parent_unusable`、`invalid_difference`（两期累计值都在、差分被拒）、`latest_not_aligned`（最新累计值无前期可差）、`base_period_missing`（列出所缺基期，基期本身在窗口内且未覆盖时只按其自身原因报）、`differencing_not_allowed`、`measures_do_not_join`（逐期都有、但没有一种口径连贯覆盖）。父指标完全未持有时不带期别。
  - 社融与 GDP 同时报告：读取失败的一边照报缺期，读取成功的一边仍做可采用复核（`not_adoptable`，列出被拒父点的期别与成员）和 GDP 数据版本核对（`incomparable_gdp_vintages`，列出不可比季度）；`status` 按原优先级取第一项。分母非法也附上 GDP 窗口与口径。
- **投影**：信用公式文档带 `failures`。
- **缺口清单** `freshness.add_projection_gaps`：信用脉冲条目的 `missing_inputs` 优先按公式 `failures` 逐期列出（含 `reason`，只列公式所读成员）。不带期别的 failure 从计划未齐缺口里取该指标的期别，只保留与公式所读成员的交集。没有 failures 的公式照旧退回计划缺口。
- **测试**：
  - `test_credit_impulse.py`：各原因精确断言（两边同时缺、缺基期、最新期未对齐、值为空与父点不可用、版本不许差分、差分被拒、口径不连贯、断期两例、分母非法、禁读口径不移动窗口）；
  - `test_worker_reviewed_context.py`：不可比季度为 2025-Q2、Q3（单独重取 Q2 改变 Q2 和由它差出的 Q3），原件损坏时列出整次交付的全部月份；
  - `test_derived_context_freshness.py`：缺口只列公式所读成员；未持有父指标从计划取期别。
- **行为差异（只记录，未改）**：
  - 同时有读取失败与原件问题时，`status` 仍只给第一项，其余见 `failures`。
  - 看板缺口页不渲染 `missing_inputs` 明细（原本就不渲染）。
  - 审查建议的组合用例（"缺期＋另一边原件拒绝""社融缺期＋GDP 版本不可比""社融原件拒绝＋GDP 版本不可比"）未补：原件拒绝与版本核对要真实 TuShare 原件夹具，目前分别在 `test_worker_reviewed_context.py` 的参数化里覆盖；同时报告的机制由"两边同时缺期"一例覆盖。
- **验证**（`PYTHONPATH=src`）：信用脉冲模块、上下文投影、派生时效、Worker 审定上下文、GDP 与社融官方回退、完整运行检索、可采用声明、日汇总、补算、缺口清单、PMI 回退、报告输入，加两例收尾冒烟与完整目录正例，共 222 例全过（17.1 分钟）。ruff、mypy 通过。
- **审查**（Codex 只读，两轮）：首轮 5 项阻断——一边失败遮住另一边的原件和版本问题、未持有父指标丢期别、原因断言不全、差分被拒误报缺基期、禁读口径移动诊断窗口——均已修；次轮无阻断。
