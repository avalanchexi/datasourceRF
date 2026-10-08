Status: needs-triage
Category: bug
Type: task

# 04：GDP 官方回退成员集合为空，同比期语义被拒

## 现象

GDP 实际季度同比缺 5 季：同比因 `gdp_yoy_period_semantics_unverified` 被拒；Tavily 达上限；官方回退因成员集合为空被取消。

- 位置（读码）：`full_retrieval.py:397`。
- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md)。

## 验收草案

- [ ] 官方回退带上 v0015 声明的 GDP 成员，不因成员集合为空取消。
- [ ] 核实 `gdp_yoy_period_semantics_unverified` 的拒收是否应放行实际季度同比，并补测试。
