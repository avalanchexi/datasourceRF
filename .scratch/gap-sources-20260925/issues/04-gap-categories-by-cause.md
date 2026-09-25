Status: done
Type: task
Blocked by: 03

# 04 — 缺口按真实原因分类；SOX 列为授权缺失

规格“缺口分类”“SOX”两节（用户故事 1–3、24–25）。

- 分类：`fetch_failed`、`ingest_rejected`（附原因码）、`retrieval_failed`、`license_missing`，时效类沿用。
- `no_searchable_source` 不再作分类，改为缺口属性“无网页补缺渠道”（`no_web_fallback`）。
- SOX 在时效登记中标为受限授权，移除宽松检索家族，不发起任何检索。
- 仪表盘、报告展示新分类、原因码与属性；AI 报告输入只收摘要。

## Comments

- 2026-09-25 实施：`freshness.gap_list` 读本次运行（`parent_run.accepted_at` 之后、同目标日）每个指标最后一次注册来源取数结果：`source_failed`/`adapter_failed`/`missing_credentials` → `fetch_failed`，`validation_failed` → `ingest_rejected`（原因取票 03 记下的 `reason`）。`FreshnessRule.restricted_license`（SOX）→ `license_missing`/`restricted_license`；`nasdaq_sox` 检索家族删除。每条缺口带 `no_web_fallback`；已列出的指标不再重复出一条 `rejected`。仪表盘新增分类标签与“无网页补缺渠道”，旧快照的 `no_searchable_source` 标签保留以便显示。
