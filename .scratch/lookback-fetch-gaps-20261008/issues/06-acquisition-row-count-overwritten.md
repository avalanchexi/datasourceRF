Status: needs-triage
Category: bug
Type: task

# 06：取数回执的行数被归一化行数覆盖

## 现象

`acquisition_request.row_count` 记录的是归一化后的行数，覆盖了来源实际返回的行数，复核"来源返回了多少、入库了多少"时对不上。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [ ] 回执分别保留来源返回行数与归一化入库行数。
