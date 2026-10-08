Status: needs-triage
Category: bug
Type: task

# 07：人民币中间价成员契约缺失

## 现象

AI 检索已取得人民币中间价 6.7351，但因 `dimension_contract_unavailable` 被阻，未入库。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [ ] 为人民币中间价补维度成员契约，或明确其不入库并从计划中移除。
