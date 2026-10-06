# 宏观语义与确认度（2026-10-06 起）

依据：[旧项目审计](../../docs/research/legacy-pring-model-audit.md)、[普林格指标需求](../../docs/research/pring-indicator-requirements.md)、[界面重新规划决定](../ui-replan-20261003/decisions.md) 第二轮第 9 条。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-bond-930916-read-as-a-price.md) | 930916 债券价格指数被当作收益率解读（N05） | ready-for-agent |

## 访谈结论（2026-10-06）

- 关键指标与读法：[key-indicators.md](key-indicators.md)；六阶段预期表、通用规则、债券归因、供需规则与扩充准入：[expectation-table.md](expectation-table.md)；决定汇总：[ADR-0037](../../docs/adr/0037-confirmation-counts-key-indicators-against-stage-narrative.md)；术语见 `CONTEXT.md`。
- 用户方向：**先集中把普林格模型设计准确**，首页原型与页面改造暂缓。

**下一步**：`/to-spec`——只覆盖模型：宏观语义修正（N01–N14 中除 N05 外）、关键指标与维度汇总（退役四个单一标签）、确认度与预期表、信号成熟度、价格内部一致性（含三项相对动量派生）、债券归因、非典型组合解读的输入；只用现有指标。报告式首页、扩充数据（收益率曲线、AAA 信用利差、社零、EIA 收支子集等）各自另起规格。
