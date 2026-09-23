---
status: superseded by ADR-0021
---

# 公式预热保留 PUBLIC 回放的无前视要求

> 已被 [ADR-0021](0021-registered-sources-freshness-replaces-certification.md) 取代（2026-09-23）。

2026-09-22 用户在 Codex 接续访谈中选择：参与正式 PUBLIC 回放计算的预热输入，同样补齐该值自己的发布证据，并满足既有认证、质量及点时可见性要求。采集发生在今天，不证明该版本在被回放日期已经公开；具体证据沿用 [ADR-0018](0018-tiered-evidence-for-historical-publication-dates.md)，仅有可靠发布日期时沿用下一本地日可见的规则。

此前“预热只检查口径与质量”的建议混淆了计算预热与初始化预热。本决定保留 [ADR-0006](0006-dual-as-of-and-immutable-evidence-vintages.md) 的无前视含义，接受因此增加取证工作的代价；不以放宽公式输入的公开时间门槛换取回放通过。仅用于初始化、且不产生正式回放结果的历史，继续按 `CONTEXT.md` 的初始化预热定义处理。

取证范围按各指标及其公式依赖确定，不能把三核心的 259 个交易日输入范围统一套到全部指标。本决定不宣称任何来源已认证、任何窗口已验收，也不改变已固定的目标窗口末端。
