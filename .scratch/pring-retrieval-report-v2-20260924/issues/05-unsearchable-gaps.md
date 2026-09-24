# 05: 不可检索的缺口不搜，列为“无可检索来源”

**What to build:** 完整运行中，不可检索的缺口（派生指标、NHII）经 TuShare 与资讯级后不进入搜索级（Tavily/Exa/AI），缺口清单出现“无可检索来源”分组。

**Blocked by:** 01

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：派生指标缺口不发起 Tavily 请求，列为“无可检索来源”
- [x] 页面与报告缺口清单显示“无可检索来源”中文标签
- [x] 可检索缺口的搜索行为不变
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。`RetrievalRequest.searchable`：完整运行按 `is_searchable_gap` 判定整组缺口，不可检索时降级链照常走本地、TuShare、官方直连，Tavily/Exa/AI WebSearch 记 `not_attempted`/`no_searchable_source`，不发请求。缺口清单新增类别 `no_searchable_source`（页面“无可检索来源”）：原为“缺失”且不属于任何登记检索家族的指标归入此类，原因字段保留（未持有/落后两期以上）。
- 新增 `tests/integration/test_unsearchable_gaps.py`（DR007 各日不调用 Tavily、LPR 照常搜索补齐、缺口与页面显示“无可检索来源”）。既有测试随之调整：`test_gap_list` 中 CSI1000、SHIBOR 改为新类别；预算共享例改用可检索的 OMO 操作量；同一发布共享请求例由 EIA 两项（现不可检索）改为社融总量与分项。受影响 42＋2＋53 例全过（`test_full_run_retrieval.py` 单文件 21 分钟）。
