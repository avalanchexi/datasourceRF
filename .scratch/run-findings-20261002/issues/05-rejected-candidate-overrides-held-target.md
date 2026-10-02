Status: needs-triage
Category: bug
Type: task

# 05 — 已取得目标期的指标被旧候选拒绝改判为"检索未通过"

## 原始发现

- `CN_OMO_7D_AMOUNT`：9/30 实际取得（`retrieval_attempt` 为 `succeeded/complete`，值 0.0），缺口清单却列 `retrieval_failed`，附三个被拒候选网址。
- `CN_USDCNY_CENTRAL_PARITY`：v0006 已持有 9/30（6.7351，经 AI 联网搜索取得新浪页面），缺口清单列 `retrieval_failed`，附两个 `period_mismatch` 候选。
- 两者真正的缺口来自票 01 的错误应有期 10/01；但 `freshness.py:857` 只要本轮有被拒候选，就把 `freshness_gap` 改判为 `retrieval_failed`，读起来像"目标期没拿到"。

## 待决定

- 候选失败分类是否只对应仍未解决的那一期（建议）；票 01 修好后这两项会消失，可并入票 01 一起处理。
