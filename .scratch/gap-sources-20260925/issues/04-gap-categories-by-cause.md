Status: ready-for-agent
Type: task
Blocked by: 03

# 04 — 缺口按真实原因分类；SOX 列为授权缺失

规格“缺口分类”“SOX”两节（用户故事 1–3、24–25）。

- 分类：`fetch_failed`、`ingest_rejected`（附原因码）、`retrieval_failed`、`license_missing`，时效类沿用。
- `no_searchable_source` 不再作分类，改为缺口属性“无网页补缺渠道”（`no_web_fallback`）。
- SOX 在时效登记中标为受限授权，移除宽松检索家族，不发起任何检索。
- 仪表盘、报告展示新分类、原因码与属性；AI 报告输入只收摘要。

## Comments
