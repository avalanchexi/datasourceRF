# Official release fixtures

Exact response bytes fetched on 2026-09-17 for the bounded article follow-up. Tests use these as archived transport responses, not as source-certification packages. The local research receipts are in `.scratch/pring-data-acquisition-repair/evidence-25-articles-20260917/receipts.json` in the main workspace.

| File | Original URL | SHA256 |
|---|---|---|
| nbs_core_cpi.html | https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965263.html | `a04f01c303c85edff794081d3651efe89bb679b1e5bad08aaa07a115dde74fbe` |
| nbs_ppi.html | https://www.stats.gov.cn/sj/zxfb/202609/t20260909_1965262.html | `46fda2cc27a2052cb357b288e44d60f8c36daccdfd8bd5d61e755ea881981b57` |
| nbs_pmi.html | https://www.stats.gov.cn/sj/zxfb/202608/t20260831_1965154.html | `a561911c92b4ea4ea58ed808d5fe4ef61a1dfb79a31f593ba46ad4692aa5af46` |
| pbc_money.html | https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html | `933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef` |
| nbs_gdp.html | https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html | `60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915` |
| nbs_gdp_q1.html | https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html | `61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18` |
| nbs_gdp_q3.html | https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html | `0f7c85e52242f3e1905d3313aa744028f51d48f60bcff899b712da400f135a5c` |
| nbs_gdp_q4.html | https://www.stats.gov.cn/sj/zxfb/202601/t20260120_1962349.html | `9d9bc9ece5d52a9ba07d6d9ed01e0d865b4d72b385c1b2a9873501e2d5532765` |
| nbs_capacity_utilization_zwfwck_q1.html | https://www.stats.gov.cn/zwfwck/sjfb/202604/t20260416_1963322.html | `d038b999e708a80099d1bce73adb7a773bd75bfc8ccb42dc732e8a75baee750b` |
| pbc_social_financing_stock_202507.html | https://www.pbc.gov.cn/diaochatongjisi/116219/116225/4405816f165642d8b7d9ece44ea6f88a/index.html | `b137eea74d9a9ebd2607953359693a83fc1f36b9bcb649cad56f49012e3fece6` |

The GDP fixtures reuse the earlier `evidence-13` and `evidence-macro-normalized` originals; they were not downloaded in the article follow-up batch.

`nbs_capacity_utilization_zwfwck_q1.html` was fetched once (curl, HTTP 200, no redirect) on 2026-10-09 00:03 UTC for lookback 13: the 2026 Q1 capacity utilization release as the NBS serves it under `/zwfwck/sjfb/`, the address Tavily and the AI search found in run-8a3779cff80f6bd586a0.

`pbc_social_financing_stock_202507.html` was fetched once (curl, HTTP 200, no redirect) on 2026-10-09 01:13 UTC for lookback 14: the "2025年7月社会融资规模存量统计数据报告" listed on the column's second page (`official_listing/pbc_116225_11871-2_20261009.html`). Until August 2025 the PBC released the social financing stock in this report of its own; the run never requested it, so the local runtime held no copy.
