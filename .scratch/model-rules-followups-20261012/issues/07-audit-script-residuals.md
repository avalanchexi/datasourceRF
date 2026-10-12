Status: needs-triage
Category: task
Type: task

# 07：体检脚本的零散残余（时间比较、原话复核、空串网址）

## 现象

(a) 残余 03：`core_recompute._raw_rows` 与 `common.Run.reached_source`／`validated_by_cutoff` 仍按文本比较时间（当前库都存 `+00:00`，不影响结果）；整批声明全被清理的旧投影无法恢复编号（`run-dc0bb2d9…` 56 个）。(b) 体检 17：未独立实现“原话按现行规则是否仍给出该值”一类排除（本样本漏判 2 条工业增加值）；空串网址体检按正文哈希区分页面、生产视为同一页面。

## 来源

[残余 03](../residual-triage-20261011/issues/03-core-pre-window-inputs-untraceable.md)、[体检 17](../data-quality-audit-20261010/issues/17-audit-multi-source-note-lists-excluded-claims.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## Comments
