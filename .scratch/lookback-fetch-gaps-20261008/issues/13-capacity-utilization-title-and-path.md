Status: needs-triage
Category: bug
Type: task

# 13：产能利用率发布稿标题含"规模以上"，列表识别漏掉；正确地址又不在检索白名单

## 现象（票 09 真实运行发现，2026-10-09）

run-8a3779cff80f6bd586a0 中，产能利用率 2026-Q1（`quarter_rate`、`yoy_change`）仍然缺失。这是 17 项计数指标中唯一仍有缺期的主要成员。

- 本轮读过的统计局列表 `/sj/zxfb/index_6.html` 和 `/sj/zxfbhjd/index_11.html` 都列有 `./202604/t20260416_1963322.html`，标题是"2026年一季度全国**规模以上**工业产能利用率为73.6%"。登记的标题模板是"{year}年{quarter}全国工业产能利用率"（`retrieval_registry.py:74`），`release_url` 用前缀严格匹配（`official_listing.py:131`），所以漏识别。官方渠道最后记为 `official_context_release_link_not_found`。
- 2025-Q2 也是同样原因：正确链接 `t20250715_1960404.html` 已经出现在已读列表里，却没识别出来；扫描继续往下翻，直到统计局本轮 50 页额度用完，记 `listing_not_covered_page_limit`，最后由 Tavily 补齐。2025-Q3、Q4 也由搜索补齐。
- 检索补救也失败了：Tavily 与 AI 都找到了 `https://www.stats.gov.cn/zwfwck/sjfb/202604/t20260416_1963322.html`，但统计局主机只放行 `/sj/` 路径（`retrieval_registry.py:40`、`:185`；正文入口 `official_context.py:2875` 也有同样限制），所以记 `not_whitelisted`，没有下载。另一个 Tavily 候选是 2023 年的页面，被 `official_context_period_identity_mismatch` 正确拒收。
- 归属：L01 已把这一族纳入列表识别，所以这是 L01 范围内的遗漏。`/zwfwck/sjfb/` 白名单属于相邻的新问题。
- 只读调查：Codex（scratchpad `lfg-codex-gaps.out`），主会话已复核列表原件中的标题和模板。

## 建议

标题模板补上"规模以上"的写法，或改为能同时匹配两种写法。检索白名单与正文入口同步登记 `/zwfwck/sjfb/`，同时保留期次和正文校验。

## 验收草案

- [ ] 用真实列表原件（含"规模以上"标题）做替身，能选出 2026-Q1、2025-Q2 的发布稿。
- [ ] `/zwfwck/sjfb/` 下的统计局发布稿能通过白名单，并经期次校验。
