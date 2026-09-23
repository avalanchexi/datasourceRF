---
status: accepted
---

# 注册来源按频率推定时效，取代来源认证与逐值发布证据

2026-09-23 用户选择：TuShare 与已注册官方直连来源**不再做来源认证包与逐值发布证据**，只做廉价结构校验（字段、单位、统计期、非空），时效按注册表登记的“频率＋发布滞后＋更新时点＋宽限”推定。公开可用时间 = min(按发布预告或登记滞后推算的发布时点, 系统首次取得时间)。门禁只剩三道：①120 交易日窗口内应有明细是否完整；②时效是否正确；③是否经正确接口并通过结构校验——只有③能拒收数据。三核心缺失时先经 TuShare 与检索补全，仍缺且只落后 1 期则**核心沿用**上一交易日值，落后 ≥2 期或冲突才阻断正式阶段；P1/P2 缺失只形成可见缺口。

取舍：此前的认证链（认证包 → 候选准入 → 120 日点时回放 → 激活 → 系统验收）让一次完整运行始终停在“有来源拿不到历史发布证据”上，数周未能产出结果；而本产品的实际用途是对**最近交易日**给出可追溯判断，不是做无前视历史研究。接受的代价是：官方实际发布晚于推算时点时会有轻微前视；推算时点只是约定，不是证明。细节见[时效契约](../../.scratch/pring-fast-refactor-20260923/issues/04-freshness-contract.md)与[运行流程形状](../../.scratch/pring-fast-refactor-20260923/issues/07-simplified-run-pipeline-shape.md)。

本 ADR 取代 [ADR-0016](0016-certification-gate-escape-valve-is-catalog-membership.md)、[ADR-0017](0017-public-time-stays-empty-without-a-reliable-date.md)、[ADR-0018](0018-tiered-evidence-for-historical-publication-dates.md)、[ADR-0019](0019-formula-warmup-requires-publication-evidence.md)，以及 [ADR-0013](0013-tushare-delivery-with-official-sampling.md) 中的认证、官方抽样与点时重放要求、[ADR-0020](0020-cny030-optional-pending-certification.md) 中的“待认证”状态（CNY030 仍为 P2）。指标目录成员不因此改变。
