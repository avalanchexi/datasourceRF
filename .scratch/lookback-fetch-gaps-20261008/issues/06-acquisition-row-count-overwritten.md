Status: ready-for-agent
Category: bug
Type: task

# 06：取数回执的行数被归一化行数覆盖

## 现象

`acquisition_request.row_count` 记录的是归一化后的行数，覆盖了来源实际返回的行数，复核"来源返回了多少、入库了多少"时对不上。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [ ] 回执分别保留来源返回行数与归一化入库行数。

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：不是"先存原始行数再被覆盖"，而是口径混淆——接收阶段只存字节和哈希，校验阶段才从归一化对象算 `row_count`（`acquisition.py:433`、`:361`），计数器也不识别 `accepted_scalars`/`scalars`（`batches.py:75`）。实测 CPI 原始 20 行记为 60、PPI 20 行记为 180，GDP 原始 7 行、28 个接受标量却记为 1。
- 修复：分别记录来源记录数、规范化标量数、实际入库结果；HTML 原件不冒充一行。约 3–5 模块加数据库迁移。
- 无需用户决定。建议最先实施，便于后续验收读懂三个数量。
