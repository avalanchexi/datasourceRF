# 27: 输入陈旧的信用脉冲不列为派生失败

**What to build:** 公式状态 `stale_inputs` 视为"已算出"，缺口清单不再为它单独生成 `derived_failed`；陈旧由时效条目表达，公式状态作附注保留。

**Blocked by:** 23

**勿并行：** 04、09、16、18、19、20、21、24、25、26（同改：缺口清单与时效；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 5 差异 3（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 现状

- 投影算出但输入陈旧时，行状态 `stale`、公式状态 `stale_inputs`（`context_projection.py:2385`、`:2404`）。
- `_USABLE_DERIVED_STATUSES`（`freshness.py:975`）含 `stale` 不含 `stale_inputs`，且公式状态优先（`:1045`），故无已有条目时新增 `derived_failed`（已核实）。

## 验收

- [ ] 按 TDD 直接调 `add_projection_gaps()`：`stale_inputs` 不生成 `derived_failed`；已有时效条目时附注 `formula_status=stale_inputs`。
- [ ] 受影响测试经 `check.py quick` 通过。
- [ ] 代码审查无阻断。
