Status: needs-triage
Category: task
Type: task

# 06：残余 01／02 的未处理部分

## 现象

(a) 残余 01：breadth 请求后行情为空时，指标尝试记为 `nothing_new` 而非 `source_empty`（既有分类问题）；候选 B：篮子窗口全持有时先取日历判定，12 次请求可降为 4 次。(b) 残余 02：运行中时效截止日补取遇到漏日应答时按工作日回退（方向保守，可能多算应有期）；人工入口在残缺存量被剔除且无 token 时同样回退工作日。是否改为阻断属领域决定。

## 来源

[残余 01](../residual-triage-20261011/issues/01-recurring-context-observation-failures.md)、[残余 02](../residual-triage-20261011/issues/02-calendar-parser-missing-day-read-as-closed.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
