Status: ready-for-agent
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

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：回退缺陷属实——`scope.members` 为空时传入空 `missing`，`all(空集合)` 成立，已有名义值便取消官方回退（`full_retrieval.py:503`、`:397`）。但 TuShare GDP 同比拒收**有依据，应保持拒收**：2026Q2 TuShare `gdp_yoy=4.7`，官方实际季度同比为 4.3（`tushare_context.py:1840`）。
- 修复：始终传递实际缺失成员，官方只补缺失的同比，保留已持有名义值保护。约 1–3 模块。
- 无需用户决定。排在 01 之后（共用计划代码）。
