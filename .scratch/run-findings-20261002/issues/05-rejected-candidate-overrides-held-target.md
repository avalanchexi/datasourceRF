Status: done
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

- [x] 已解决期次的被拒候选不改变该指标其他期次的缺口类别（上述反例保持 `freshness_gap`）
- [x] 同一期仍缺成员、且有候选被拒时，仍列为 `retrieval_failed` 并附候选
- [x] 整个指标已 `current`／`awaiting_release` 时不新增缺口

## 主要模块

`src/pring_cycle/freshness.py`（`_failed_candidates` 按指标＋期次＋成员关联，与最终计划或检索账本中仍未解决的期次比对）、`tests/integration/test_gap_list.py` 一带。

## Comments

**2026-10-09 分流**（Codex 只读取证，输出存会话 scratchpad `triage/g1–g4.out`；主 agent 核验了标 ★ 的条目）：`ready-for-agent`（偏离预设"没有了 → done"，理由如下）。
- 现象三轮都没再出现：第一、二、三轮投影缺口 36／14／34 项中 `retrieval_failed` 均为 0；OMO 操作量、人民币中间价 09-30 三轮最终计划都是 `local_complete`。
- ★ 但根因仍在（主 agent 已核对代码）：`freshness.py:700` 的 `_failed_candidates` 只按指标汇总被拒候选，丢掉期次与成员；`:857` 对任何非 `unconfigured` 缺口一律改判 `retrieval_failed`。反例（读码推断，未执行）：本轮先拒一个 09-30 候选、随后补齐 09-30，若该指标另有"落后一期"的时效缺口，仍会被改判，原因字段却是 `one_period_behind_carried`。现象消失是因为票 01 去掉了错误应有期，不是这里修好了。修复面小，故实施。

### 2026-10-10 实施

- **改动**（`src/pring_cycle/freshness.py`）：`_failed_candidates` 改为按 `retrieval_gap.identity_json` 的指标＋期次关联被拒候选，只保留仍未解决期次的候选。判定：最终计划（`full_run_gap_plan` phase=`final` 的 `gaps`）列出的期次按其 `complete`（成员级，缺任一成员即未解决）；最终计划未列的期次（如只"查看新发布"、非必需的期次，或窗口外旧期），按该指标 `batch_freshness.held_period` 是否已达该期（`_held_through`，日／月／季）。`gap_list` 的改判逻辑不变：仍只在有未解决期次的被拒候选时把非 `unconfigured` 缺口改为 `retrieval_failed`，候选列表格式不变。成员粒度说明：检索缺口身份的维度为 `*`，候选无法对应到单个成员，故按"该期是否仍缺成员"判定，满足验收第 2 条。
- **测试**（`tests/integration/test_gap_list.py`，复制模块夹具的运行库后写入被拒候选）：反例——拒 08-26 候选（最终计划已完成）及窗口外 2026-01-05 候选（回退分支，已持有），CSI500 保持 `freshness_gap`／`one_period_behind_carried` 且不附候选（修前变红）；仍缺的 08-27 被拒 → `retrieval_failed`，只附 08-27 候选（修前因附上 08-26 候选变红）；最终计划标 08-26 缺成员、即便持有已达该期也仍为 `retrieval_failed`（规格审查建议补，验证计划优先于回退）；CSI300（awaiting_release）有被拒候选也不新增缺口。
- **验证**：受影响 8 个文件（test_gap_list、test_retrieval_strict_path、test_rrr_backtrack、test_acquisition_outcome、test_official_listing_pages、test_warrant_symbol_isolation、test_derived_context_freshness、test_official_pmi_fallback）128 passed，10 分 42 秒（超 3 分钟目标，均为整次 Worker 运行夹具）；补测后 test_gap_list 10 passed，88 秒；两例冒烟 2 passed，149 秒；重型 test_worker_registered_catalog 2 passed，9 分 41 秒（flock 排队）；`ruff check`、`ruff format --check` 通过；`mypy` 对两文件仅有 tests/integration/test_worker_execution.py 的 17 条既有报错（改动前同数）。
- **审查**（Codex 两轴）：标准轴无问题，阻断：无；规格轴三条验收满足、期次格式一致、日／月／季比较正确，阻断：无；非阻断建议"补测最终计划优先于回退"已采纳（上述第三测）。
