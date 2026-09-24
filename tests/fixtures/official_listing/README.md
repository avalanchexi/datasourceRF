# 官方发布列表页样本（票 12 诊断）

| 文件 | 原网址 | 取得时间 | SHA256 |
|---|---|---|---|
| nbs_zxfb_index_20260923.html | https://www.stats.gov.cn/sj/zxfb/ | 首次真实运行 2026-09-23（被拒原件） | `81ef2772…` |
| pbc_116219_index_20260923.html | https://www.pbc.gov.cn/diaochatongjisi/116219/index.html | 首次真实运行 2026-09-23（被拒原件） | `f9f6764c…` |
| nbs_zxfb_index.html | https://www.stats.gov.cn/sj/zxfb/ | 2026-09-24 | `dd7b85be…` |
| nbs_zxfb_index_1.html | https://www.stats.gov.cn/sj/zxfb/index_1.html | 2026-09-24 | `e08f719d…` |
| nbs_zxfb_index_2.html | https://www.stats.gov.cn/sj/zxfb/index_2.html | 2026-09-24 | `b06fdc6a…` |

首次运行“链接不唯一”的成因：两次被拒都在请求 2024 年的统计期（GDP 2024-Q2、社融 2024-08），而列表页只列近期稿件，实际是零个匹配却报成“不唯一”；此外国家统计局“最新发布”首页已翻过 7 月中旬，2026 年二季度 GDP 发布稿在第 2 页（`./202607/t20260716_1964142.html`），当期也会零匹配。社融当期（2026-08、2026-07）在人民银行列表页上原本就能唯一选中。
