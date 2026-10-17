# 13: ⑦ 展示修正（原因码中文与说明）

**What to build:** 决定 27（第五轮）。⑦"数据说明与解读"在 10-15 投影上仍写原因码与误导说法（截图 `screenshots/1015-home-reading-light-1440.jpg`；根因调查 scratchpad `accept-1017/q3-out.md` 第 1、3、6 条）。只改前端：

1. 原因码中文：缺口与检索未通过条目里的原因码（如 `period_not_requested`、`one_period_behind_carried`、`rule_not_matched`、`period_mismatch`、`negative_cache_active`、`listing_not_covered` 等，以投影中实际出现的全集为准）经一张中文对照表显示，例："未请求（等待发布）""落后一期，沿用上一期"；指标写中文名为主、代号为辅（`wording.display_name`）；未映射原因码显示原值。对照表一处维护（与 `wording` 同处）。
2. "无网页补缺渠道"改为"未配置额外网页检索补缺"。
3. 旧投影无完整度口径时写"该投影生成时尚未提供此统计"。
4. "目标日 … ；时效截至 …"旁加一句："目标日决定分析日期，时效按运行冻结时点判断"。
5. 非典型组合时，⑦ 与阶段事件里"阶段变化记为缺口"类表述改写为"非典型组合，暂无正式阶段"（AI 报告正文本身不改，那是 Worker 批次）。

**Blocked by:** None（基于 `cockpit-layout` 最新）

**Status:** ready-for-agent

- [ ] 10-14、10-15 两份投影的 ⑦ 不再出现英文原因码（未映射值除外）；指标名中文为主
- [ ] 2–5 条文字按上述出现
- [ ] `dashboard_page` 测试断言中文原因、说明句与旧投影提示；受影响 Web 用例、两项必跑冒烟通过
