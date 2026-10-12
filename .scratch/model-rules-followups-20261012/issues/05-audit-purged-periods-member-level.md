Status: needs-triage
Category: enhancement
Type: task

# 05：体检第一层“已入库后被清理”按指标聚合，掩盖成员差别

## 现象

一个指标只要还有任一成员留存，就不再列“整期被清理”（`tools/quality/acquisition.py:1072`、`:1096`），例如工业财务 2026-03 选中的营收同比已清理而利润同比仍在。影响较小。

## 来源

验收记录遗留 4（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
