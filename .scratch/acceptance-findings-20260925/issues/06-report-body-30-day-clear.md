Status: needs-triage
Type: task

# 06 — 报告正文 30 天清空与 120 交易日统一保留并存

**发现：** 逐票核对旧 `pring-cycle-dashboard` 票 20/21 时（Codex 只读核对，已人工核实代码）。`maintenance.py:159-165` 清理时把 `created_at` 早于 30 天的 `report_snapshot` 正文置为 `{}`、`body_retained=0`；ADR-0022 规定统一 120 交易日保留，未提 30 天。另有事件指标现行基准的窗口外保留例外（`retention.py:150`，ADR-0028）。

**待决定：** 报告正文是否也按 120 交易日保留（删 30 天规则），还是 30 天是有意的额外约束（则应写入 ADR-0022 或新 ADR）。

## Comments
