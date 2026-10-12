Status: needs-triage
Category: enhancement
Type: task

# 02：T+1 盘后调度只在 Worker 跨过 09:00 时提交，错过不补交；P0 截止改口径未写入 ADR

## 现象

票 03 实现：Worker 须在运行中跨过 09:00 才提交上一交易日（`src/pring_cycle/worker.py:142`、`:219`），晚于 09:00 启动的 Worker 不补交当日；票 03、残余 02 的调度至今无真实样本。另：票 03 把 P0 截止从“目标日 21:00”改为“提交当天 21:00”，由 ADR-0041 与票 14 推出，建议写入 ADR。需决定：是否在当日截止前补交、是否补写 ADR。

## 来源

[票 03](../model-rules-validation-20261011/issues/03-scheduled-run-t-plus-1.md) 遗留；验收记录遗留 5（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
