Status: ready-for-agent
Category: bug
Type: task

# 08（02b）— 相同定义：已持有日与入库查重

**What to build:** 按版本判断"已持有"的取数决策改为认相同定义版本组，换目录后不再把相同定义的已持有日当成缺日重取。

**Blocked by:** 07

**勿并行：** 07、09

## 验收

- [ ] 广度已持有日、商品篮子已持有水平、郑商所仓单 `_held_totals`、核心补缺与目标交易日、信用脉冲输入（含 GDP 同次交付 `delivered_values`）、发布日历、来源入库前查重（`latest_source_claim`、`source_claim_vintages`、`claims_for_release_source`、`release_events_for_definition`）认相同定义版本组。
- [ ] 回归：激活只改了信用脉冲的新目录后，已持有的广度、篮子、仓单日期不再重取；来源代码变化的指标（v0012→v0013 广度）仍重取。
- [ ] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments
