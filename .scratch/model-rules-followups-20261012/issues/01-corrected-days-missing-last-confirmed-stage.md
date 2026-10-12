Status: needs-triage
Category: bug
Type: task

# 01：08-14～10-08 的 34 个整日更正日“上一确认阶段”为空

## 现象

第一次真实运行（`run-97250978…`）时这 34 天已整日更正，当时前 85 天尚未更正、没有阶段，所以它们的 `last_confirmed_stage` 为空；第二次运行补正了前 85 天（stage_iii 67 天），但这 34 天已是 `core-history-v0002` 口径，`_backfill` 只更正口径不同的日子（`src/pring_cycle/day_summary.py:357-362`，读码推断），之后不会再更正。阶段历史页这 34 天显示“上一确认 尚无”；目标日不受影响。

## 来源

[验收记录](../model-rules-validation-20261011/acceptance-20261012.md) 遗留 8（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
