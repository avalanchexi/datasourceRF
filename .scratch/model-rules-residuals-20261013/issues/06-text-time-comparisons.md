Status: needs-triage
Category: bug
Type: task

# 06：体检 SQL 截止比较与 `acquisition.py` `_load_announced` 仍按文本比较时间

## 现象

体检各层 SQL 里的截止比较，以及生产 `acquisition.py` `_load_announced` 的一处，仍按文本比较时间（票 07 已写入体检文档）。目前存量都是 +00:00 写法，暂不误判；混用时区写法时可能出错。

## 来源

[goal 遗留](../../model-rules-followups-20261012/goal.md)（票 07 实施）。
