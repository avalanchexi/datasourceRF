Status: needs-triage
Category: bug
Type: task

# 05：生产按 `COALESCE(url, body_hash)` 去重空串网址，与体检文档的书面规则不一致

## 现象

`news_rules.py:1262`、`:1374` 把空串网址按 `COALESCE(url, body_hash)` 视为同一页面，与 `docs/development/data-quality-audit.md:295` 的书面规则不一致。本样本 0 条。需确定以哪边为准。

## 来源

[goal 遗留](../../model-rules-followups-20261012/goal.md)（票 07 分流）。
