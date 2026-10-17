# 人民币中间价样本（worker-gaps 01）

取自 10-15 隔离副本（运行 `run-2b21b77b4968f3bbcfc3` 等的本机运行库制品，原样复制，未改字节）。

| 文件 | 原网址 | 取得 | SHA256 |
|---|---|---|---|
| cls_2505221_20261015.html | https://www.cls.cn/detail/2505221（财联社 10-15 09:16:03 电："人民币兑美元中间价报6.7253，下调4点"） | 2026-10-16 08:07 UTC，`acquisition-0dda4e0c…`（media_page_get，当时 rule_not_matched） | `7498f5fc…` |
| pbc_125925_index_20261015.html | https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html（人民币汇率中间价公告栏目第 1 页，列有 10-15 公告 `…/2026101509014017867/index.html`） | 2026-10-16 08:07 UTC，`acquisition-991b4b3f…`（当时被当作公告解析，official_context_usdcny_quote_missing） | `d123b27c…` |
| pbc_125925_20260430.html | https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026042916250715970/index.html（2026-04-30 公告，1美元对人民币6.8628元） | 2026-10-02 14:22 UTC，`acquisition-973d18d2…`（搜索 9-30 时命中，period_identity_mismatch） | `0e701c9d…` |

副本中没有 10-15 公告正文原件：该运行从未打开它。需要 10-15 公告的测试在测试内按 4-30 原件的版式自写正文（值取财联社同日报道的 6.7253），并注明非原件。
