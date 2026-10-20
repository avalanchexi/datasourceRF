# 08 日广度 Standards 复审 410

审查基点为 `fb13723` 及 `breadth-baseline-373.json` 保存的既有工作区。范围仅为 `breadth-review-diff-410.patch` 的七文件增量；已独立核对 `breadth-review-inputs-410.json` 的七文件哈希和补丁哈希，均匹配。尚无本批提交。

依据：`AGENTS.md`、`docs/agents/`、`CONTEXT.md`、ADR 0006/0012/0013、`pyproject.toml` 及本票实施记录；另按 code-review 的十二项 Fowler smell 基线判断。格式、类型及测试终态由根代理验证，本报告不替代这些检查。

## 明确规范违规

未发现。新日统计使用独立来源合同，保留旧目录和历史结果，符合 ADR 0012。原件复核、零参与不可用及退出成员证据的 PUBLIC 约束符合 ADR 0006 和 CONTEXT 的双点时语义；历史股票池输入审查不授予真实来源认证，符合 ADR 0013。

## 判断性 smell

本轮没有需处理的重要 smell。406 的两项建议已闭合：

- `market_breadth.py:269` 的 `DailyBreadthResult` 明确了跨采集、标准化和复核使用的日结果字段，替代该边界上的无结构字典。
- `market_breadth.py:645` 的 `daily_breadth_scalars` 统一六标量转换；采集和 `daily_breadth_scalar_documents` 均复用它，独立测试期望仍保留。

`market_breadth.py:380` 按代码和证券主体分别分组、排序检查区间重叠，保留原身份约束，未发现整理引入行为冲突。模块说明已区分旧输入与带证据时间的日统计，未将输入审查描述为来源认证。

结论：明确规范违规 0，待处理重要 smell 0。除本报告外未修改文件；60 个新场景及相关回归的结果以实际终态为准。
