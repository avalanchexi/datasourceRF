Status: done
Type: grilling

# 04 — USDCNY 16:30、VIX、SOX 需要结构化来源

**现象：** 本轮这三个 P2 缺口的检索候选全为 `period_mismatch`（run-f26f88cbd9e0681f397a）。候选本身就是错的页面：新浪 3–4 月旧文（USDCNY）、Yahoo OVX 历史页与 CFE 合约公告（VIX）、Investing/东财首页与行业新闻（SOX）。拒收是正确的，代码无缺陷。

**真正的问题：** 这三个日频行情指标没有登记的结构化来源，只能靠网页搜索碰运气，而搜索不擅长给出“某日收盘值”。需要决定每个指标的来源（例如交易所/发布方官方日数据文件、TuShare 可用接口、或接受长期缺口），这是取舍而非实现。

**建议：** 并入 18 个缺口的统一取舍，用 `/grill-with-docs` 逐项决定后再立实施票。

## Comments
- 2026-09-25 已按 ADR-0029 实施：VIX、USDCNY 16:30 走官方文件（gap-sources 票 06/07），SOX 列授权缺失（票 04）。
