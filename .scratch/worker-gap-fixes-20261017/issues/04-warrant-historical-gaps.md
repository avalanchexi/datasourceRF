# 04: 仓单历史缺期进缺口清单

**What to build:** 仓单 07-21 五品种、09-09 聚丙烯的历史缺期在 ⑦ 找不到（决定 4）。最终补缺计划中的历史缺期并入缺口清单，按指标归组（如"仓单：历史缺期 6 个"），期与品种明细进抽屉；完整度"其他缺失"能对上。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** ready-for-agent

- [ ] 完整运行：最终计划含历史缺期时，缺口清单按指标归组并带期与成员
- [ ] 完整度"其他缺失"数与缺口清单条目一致
- [ ] `dashboard_page` 断言 ⑦ 归组行与抽屉明细
- [ ] 两项必跑冒烟通过
