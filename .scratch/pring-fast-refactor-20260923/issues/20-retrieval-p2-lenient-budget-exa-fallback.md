# 20: P2 宽松路径、预算与 Exa 备用

**What to build:** P2 在主机属于白名单时接受 Tavily 或 AI 抽出的值（保存原文及哈希），放开 P2 的 AI WebSearch；USDCNY 16:30、VIX、SOX 登记白名单主机。预算：取消每日硬上限，Tavily/Exa 每次运行上限 16/8，AI WebSearch 每缺口每次运行至多一次；Exa 只在 Tavily 月度限额耗尽后顶替。

**Blocked by:** 19

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：P2 宽松路径被采纳，记录抽取方式与原文哈希
- [x] Tavily 未达月限额时不调用 Exa；达限后由 Exa 顶替
- [x] 每次运行 Tavily ≤16、Exa ≤8；同一缺口 AI WebSearch 每次运行至多一次
- [x] 三项 P2 有登记主机，可经宽松路径取值
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 与 19 同一提交完成（两票在检索验证、台账与 Worker 交织）。
- P2 宽松路径：`search_evidence.LENIENT_HOSTS` 按指标登记“主机＋路径前缀”（USDCNY 16:30 → www.chinamoney.com.cn/chinese/；VIX → www.cboe.com、cdn.cboe.com；SOX → www.nasdaq.com、indexes.nasdaqomx.com）。候选在登记主机上时，从搜索摘要取值：摘要须写出应有期日期（否则统计期不符），其余数中恰有一个小数，或“收盘/closed at”后恰有一个小数（否则解析失败）。随后重抓页面保存原文与哈希（`search_page_get`），检索记录的解析器版本列记抽取方式 `search-summary-extraction-v0001`；公开时间按登记节奏与首次取得取早，晚于截止即拒收。三项 P2 同时登记时效（16:35 当日；VIX、SOX 次日 06:00）。
- 预算：取消每日上限（删 `daily_budget_consumption` 与台账 `daily_consumption`），Tavily/Exa 每次运行 16/8；AI WebSearch 不计次，同一运行内每缺口至多一次；任何渠道同一运行内不重复“完成情况未知”的请求，已完成请求只受负缓存约束。取消 P2 禁用 AI WebSearch。
- Exa 备用：级联中 Exa 仅在本次 Tavily 返回 `quota_exhausted`（402/432/433）或未配置 Tavily 时调用，否则记 `tavily_quota_available`。Tavily 的限额缓存到下月 1 日 00:05（上海），期间台账直接判 `quota_exhausted`，Exa 顶替。
- 未完成：生产代码仍没有 AI WebSearch 适配器（此前也没有），级联中该渠道为 not_configured；“每缺口每次运行至多一次”由台账保证，待接入适配器时生效。Exa 请求未要求返回正文摘要，故 Exa 候选走宽松路径时通常因无摘要日期而拒收。
- 新增 `test_retrieval_p2_lenient.py` 5 例；改写级联/台账相关用例，删除每日上限与深搜每事件额度的 4 例。
