Status: ready-for-agent
Category: bug
Type: task

# 05 — 已取得目标期的指标被旧候选拒绝改判为"检索未通过"

## 原始发现

- `CN_OMO_7D_AMOUNT`：9/30 实际取得（`retrieval_attempt` 为 `succeeded/complete`，值 0.0），缺口清单却列 `retrieval_failed`，附三个被拒候选网址。
- `CN_USDCNY_CENTRAL_PARITY`：v0006 已持有 9/30（6.7351，经 AI 联网搜索取得新浪页面），缺口清单列 `retrieval_failed`，附两个 `period_mismatch` 候选。
- 两者真正的缺口来自票 01 的错误应有期 10/01；但 `freshness.py:857` 只要本轮有被拒候选，就把 `freshness_gap` 改判为 `retrieval_failed`，读起来像"目标期没拿到"。

## 待决定

- 候选失败分类是否只对应仍未解决的那一期（建议）；票 01 修好后这两项会消失，可并入票 01 一起处理。

## 验收

- [ ] 已解决期次的被拒候选不改变该指标其他期次的缺口类别（上述反例保持 `freshness_gap`）
- [ ] 同一期仍缺成员、且有候选被拒时，仍列为 `retrieval_failed` 并附候选
- [ ] 整个指标已 `current`／`awaiting_release` 时不新增缺口

## 主要模块

`src/pring_cycle/freshness.py`（`_failed_candidates` 按指标＋期次＋成员关联，与最终计划或检索账本中仍未解决的期次比对）、`tests/integration/test_gap_list.py` 一带。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`（偏离预设"没有了 → done"，理由如下）。
- 现象三轮都没再出现：第一、二、三轮投影缺口 36／14／34 项中 `retrieval_failed` 均为 0；OMO 操作量、人民币中间价 09-30 三轮最终计划都是 `local_complete`。
- ★ 但根因仍在（主 agent 已核对代码）：`freshness.py:700` 的 `_failed_candidates` 只按指标汇总被拒候选，丢掉期次与成员；`:857` 对任何非 `unconfigured` 缺口一律改判 `retrieval_failed`。反例（读码推断，未执行）：本轮先拒一个 09-30 候选、随后补齐 09-30，若该指标另有"落后一期"的时效缺口，仍会被改判，原因字段却是 `one_period_behind_carried`。现象消失是因为票 01 去掉了错误应有期，不是这里修好了。修复面小，故实施。
