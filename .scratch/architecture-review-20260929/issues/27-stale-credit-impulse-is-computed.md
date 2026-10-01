# 27: 输入陈旧的信用脉冲不列为派生失败

**What to build:** 公式状态 `stale_inputs` 视为"已算出"，缺口清单不再为它单独生成 `derived_failed`；陈旧由时效条目表达，公式状态作附注保留。

**Blocked by:** 23

**勿并行：** 04、09、16、18、19、20、21、24、25、26（同改：缺口清单与时效；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 5 差异 3（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 现状

- 投影算出但输入陈旧时，行状态 `stale`、公式状态 `stale_inputs`（`context_projection.py:2385`、`:2404`）。
- `_USABLE_DERIVED_STATUSES`（`freshness.py:975`）含 `stale` 不含 `stale_inputs`，且公式状态优先（`:1045`），故无已有条目时新增 `derived_failed`（已核实）。

## 验收

- [x] 按 TDD 直接调 `add_projection_gaps()`：`stale_inputs` 不生成 `derived_failed`；已有时效条目时附注 `formula_status=stale_inputs`。
- [x] 受影响测试经 `check.py quick` 通过。
- [x] 代码审查无阻断。

## Comments

**2026-10-02 实施记录**

- `freshness.add_projection_gaps`：公式状态为 `stale_inputs` 时不再进入派生失败分支。若缺口清单已有该指标的时效条目，只附注 `formula_status=stale_inputs`，类别、原因与时效字段不变；没有条目就不新增。来源失败与冲突的后续处理照旧。
- `credit_impulse` 模块文档删去"陈旧算作派生失败"的留账说明。
- **测试**（先红后绿）：`test_derived_context_freshness.py::test_stale_inputs_computed_the_formula_and_only_annotate_its_timeliness` 直接调用 `add_projection_gaps()`，覆盖"无条目返回空"和"已有条目只加附注"两种情形。
- **验证**（`PYTHONPATH=src`）：派生时效、信用脉冲、PMI 官方回退、缺口清单、日汇总、补算及两例收尾冒烟，共 92 例全过（3.5 分钟）。ruff、mypy 通过。
- **审查**（Codex 只读）：无阻断。目前只有信用脉冲会给出 `stale_inputs`，其他派生公式不受影响。
- **行为差异（只记录，未改）**：缺口页 `dashboard._gap_list()` 不展示 `formula_status` 附注；信用响应卡另有"输入数据已陈旧"的展示。两处不一致，票面只要求保留字段。
