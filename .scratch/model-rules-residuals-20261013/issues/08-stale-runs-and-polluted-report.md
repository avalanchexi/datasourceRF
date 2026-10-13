Status: needs-triage
Category: task
Type: task

# 08：旧残留运行与被时钟污染的报告

## 现象

1. 4 个 2026-09-24／25 的 targeted_refresh 仍处于 `action_required`（`run-051b108c…`、`run-6e2b8c63…`、`run-297db123…`、`run-d3aa44aa…`），不会被 Worker 领取。
2. `run-742bf2b787a6feca48a7` 的 10-12 报告（第 1 版）是用被时钟污染的数据生成的，仍在库中；当前投影已是 `run-0a8dabc2…`，第 2 版报告取代了它的展示。

## 待分流

是否需要处置（关闭、标注或保留原样作为证据），属于数据处理决定。

## 来源

[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 8、9。
