# 02: 社融发布门禁按成员判断

**What to build:** 9 月社融 10-14 已发布，⑦ 却写"未请求 2026-09（等待发布）"（决定 2）。同一发布事件已取得可靠已发布证据时，估算门禁不再拦其他成员；门禁按成员评估；估算门禁未到时每次运行允许查一次官方目录发现提前发布；⑦ 写出已取得与仍缺的成员（原因文案进票 A13 建的中文对照表）。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** ready-for-agent

- [ ] 完整运行：社融总量当期已持有时，存量同比等成员被请求，不再整期 period_not_requested
- [ ] 估算门禁未到期时，运行内对官方目录探查一次
- [ ] `awaiting_release` 仍只用于发布判定，不进证据时效
- [ ] `dashboard_page` 断言 ⑦ 写出社融已取得与仍缺成员
- [ ] 两项必跑冒烟通过
