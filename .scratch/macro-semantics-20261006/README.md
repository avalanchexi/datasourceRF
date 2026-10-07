# 宏观语义与确认度（2026-10-06 起）

依据：[旧项目审计](../../docs/research/legacy-pring-model-audit.md)、[普林格指标需求](../../docs/research/pring-indicator-requirements.md)、[界面重新规划决定](../ui-replan-20261003/decisions.md) 第二轮第 9 条。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-bond-930916-read-as-a-price.md) | 930916 债券价格指数被当作收益率解读（N05） | done |
| [02](issues/02-lookback-declaration-prefactor.md) | 预备重构：按"成员＋读法＋发布期"声明回看 | done |
| [03](issues/03-tracer-new-model-with-pmi.md) | 打通全链路：新模型版本与 PMI 一项确认度 | done |
| [04](issues/04-monthly-official-key-indicators.md) | 月度官方值类关键指标 | done（Q1 工业增加值 2 月取 1—2 月累计同比；Q2 社融辅成员为政府债＋7 个非政府分项：用户确认） |
| [05](issues/05-timing-grace-and-maturity.md) | 指标时序、宽限与信号成熟度 | done（月度检索锚点按发布日历到期期修正，仅新模型） |
| [06](issues/06-policy-dimension.md) | 政策维度：政策动作、DR007 与净投放 | done（Q1 日频 5 个交易日一期、宽限 2 期；Q2 已传导＝下调后 DR007 每期均值下降，政策利率与 LPR 同用；Q3 D1 六阶段适用；Q4 按 SSE 日历：用户确认） |
| [07](issues/07-cumulative-and-quarterly-indicators.md) | 累计口径与季度关键指标 | done（Q1 季度一年尺度取近 4 季、回看上限 t−4；Q2 贷款守 13 个月；Q4 Ⅵ信用脉冲附注；Q5 盈利 2 月对上年 12 月：用户确认；Q3 GDP 名义累计只展示：主会话决定） |
| [08](issues/08-inventory-quadrant-and-warrants.md) | 库存象限新规则与仓单读法 | done（不足→未分类且未确认、不一致→未分类且仅观察；库存卡可用性按成员自身证据，关系随象限；仓单为附注不计数） |
| [09](issues/09-price-consistency-and-observation-interfaces.md) | 价格内部一致性、观察接口与商品供需附注 | done（Q1 广度用站上 90 日均线占比、50% 多数线；Q2 篮子按同向分项个数；Q3 "明显回升"＝收益差转正：用户确认） |
| [10](issues/10-bond-trend-attribution.md) | 债券归因 | ready-for-agent（阻塞于 04、06） |
| [11](issues/11-activate-model-and-acceptance.md) | 启用新模型与真实运行验收 | ready-for-agent（阻塞于 01、05–10） |

## 访谈结论（2026-10-06）

- 关键指标与读法：[key-indicators.md](key-indicators.md)；六阶段预期表、通用规则、债券归因、供需规则与扩充准入：[expectation-table.md](expectation-table.md)；决定汇总：[ADR-0037](../../docs/adr/0037-confirmation-counts-key-indicators-against-stage-narrative.md)；术语见 `CONTEXT.md`。
- 用户方向：**先集中把普林格模型设计准确**，首页原型与页面改造暂缓。

**规格**：[spec.md](spec.md)（2026-10-07）。**下一步**：按阻塞关系逐票 `/implement`，每票之间清空上下文；01—09 已完成（2026-10-07），下一张是 10。
