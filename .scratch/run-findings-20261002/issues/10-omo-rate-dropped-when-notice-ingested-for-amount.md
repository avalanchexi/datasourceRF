Status: duplicate（并入 lookback-fetch-gaps 02）
Category: bug
Type: task

# 10 — OMO 公告原件写了利率，入库只存了操作量

## 原始发现

- 验收运行 `run-cfb8d12142289f56af73`（2026-10-03）缺口清单 3 项中有 `CN_OMO_7D_RATE`（持有 9/28、应有 9/29，`one_period_behind_carried`）与随之的 `CN_DR007_POLICY_SPREAD`。
- 9/29 央行公告（回执 `acquisition-d8a46a7e4baf49e287065fe82556a60e`，`official_http_get`，基线运行 `run-b7ccf5dbbe8e21b2a6fc` 取得）原文"7 天 1.40 % 905 亿元"，规范化结果 `scalars` 同时含 `CN_OMO_7D_RATE`=1.4 与 `CN_OMO_7D_AMOUNT`=905；回执 `accepted`，但只有操作量声明与之关联，利率声明 0 条。
- 同样现象：9/21–9/29 各公告在 v0005、v0006 下都只有操作量声明；利率只在 9/24（v0004）、9/28（v0005）有。

## 推测（未核实）

补缺按缺口的指标范围筛选规范化标量入库，公告为操作量缺口取得时利率被丢弃。不是 run-findings 01、02 引起的（回执早于本轮改动）。

## 待决定

- 是否修：一份公告取得后，同族全部成员一并入库。

### 2026-10-08 分流

原推测已实测证实（回执 `acquisition-d8a46a7e4baf49e287065fe82556a60e` 规范化含利率 1.4 与金额 905，只关联金额声明）。与社融分项被丢是同一过滤点（`official_context.py:563–575`），**并入 [lookback-fetch-gaps 02](../../lookback-fetch-gaps-20261008/issues/02-sf-components-ingest-all-members.md) 一并修复**。

### 2026-10-08 修复

已随 lookback 02 修复（e10db1b）。除金额范围丢利率外，还修了第二个原因：范围含利率时，前一日旧利率被算作"已持有"而挡住当天公告利率。状态保持 duplicate（仓库惯例：并入票以主票 done 为准）。
