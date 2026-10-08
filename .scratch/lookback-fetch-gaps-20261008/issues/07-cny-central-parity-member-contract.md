Status: ready-for-agent
Category: bug
Type: task

# 07：人民币中间价成员契约缺失

## 现象

AI 检索已取得人民币中间价 6.7351，但因 `dimension_contract_unavailable` 被阻，未入库。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [ ] 为人民币中间价补维度成员契约，或明确其不入库并从计划中移除。

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：中间价**已入库**（AI 回执关联 1 条 6.7351、2026-09-30、validated，主会话已复核），问题在选值：缺必需成员契约被判 `dimension_contract_unavailable`（`search_evidence.py:236`、`ai_websearch.py:272`）。
- 修复：补 `USD/CNY`、`CNY per USD` 成员契约并验证选择结果，复用现有资讯规则（`news_rules.py:477`）。约 1–2 模块。
- 无需用户决定。独立实施。
