# 03: "等待发布"分组

**What to build:** EIA 布伦特、WTI 正常的分批发布滞后被列为缺失（决定 1）。缺口清单新增"等待发布"分组：来源原件写明下次发布日（EIA）或按登记发布滞后未到期的期归入此组，不计入缺失与完整度缺口；⑦ 单列一组（中文文案进对照表）。证据时效仍只有 current/stale。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** ready-for-agent

- [ ] 以 10-15 EIA 原件为夹具，完整运行把 10-15 期归入等待发布并带下次发布日
- [ ] 完整度缺口数不含等待发布
- [ ] `dashboard_page` 断言 ⑦ 有"等待发布"组且不在"缺失"组
- [ ] 两项必跑冒烟通过
