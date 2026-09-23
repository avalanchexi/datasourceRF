---
status: superseded by ADR-0023
---

# 证据检索采用缓存优先的成本受控降级链

> 已被 [ADR-0023](0023-retrieval-verification-by-registered-parsers.md) 取代（2026-09-23）。

指标需要刷新时，系统先复用有效本地证据，再依次尝试TuShare、已认证官方直连、Tavily、Exa和受限AI WebSearch。Tavily与Exa不对同一缺口默认并行，AI WebSearch只处理仍未解决的核心及重要政策、库存、过热和通胀证据，并拥有独立硬预算；报告AI不能自由重复搜索。该结构用持久证据缓存、发布事件合并查询和最小化证据片段降低搜索调用及模型Token，同时保证全链路失败时核心阶段安全留空。
