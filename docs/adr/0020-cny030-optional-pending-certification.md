---
status: accepted; partially superseded by ADR-0021
---

# CNY030 降为 P2 并保留待认证缺口

> 部分已被 [ADR-0021](0021-registered-sources-freshness-replaces-certification.md) 取代（2026-09-23），冲突之处以 ADR-0021 为准。

2026-09-22 用户选择：在下一版不可变指标目录中，将债券确认指标 `CN_BOND_FULL_PRICE_CNY030` 从 P1 降为 P2，保留待认证状态、缺口说明及后续补证。官方衍生指数列表能证明其身份，但当前有界探测尚未取得目标日合格数值及发布证据；不再让这一非核心指标的来源缺件成为完整候选的强制依赖。

本决定采用 [ADR-0016](0016-certification-gate-escape-valve-is-catalog-membership.md) 的目录成员资格处置，接受首版缺少该项已认证确认数据的代价，不放宽 P1 或 PUBLIC 的证据门槛。债券核心仍为 `CN_BOND_CORE_000012`，三核心的身份与认证要求不变；其他指标不因此自动降级。原目录、历史声明及已发布结果继续保持不可变。

这是后续目录迁移与消费者处理的实施依据，不是已部署的目录变更，也不代表 CNY030 或整体候选已通过认证。领域选择与事实见[接续访谈](../../.scratch/pring-data-acquisition-repair/grilling-resume-20260922.md)。
