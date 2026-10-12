# 模型规则补全批次的后续积压（2026-10-12）

来源：[模型规则补全批次](../model-rules-validation-20261011/README.md) 收尾验收（[acceptance-20261012.md](../model-rules-validation-20261011/acceptance-20261012.md) 遗留一节）与各票实施记录中的遗留。2026-10-12 已分流（取证见 `triage-codex-*.md`），按 [goal.md](goal.md) 分三线实施。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-corrected-days-missing-last-confirmed-stage.md) | 08-14～10-08 的 34 个整日更正日“上一确认阶段”为空 | needs-triage |
| [02](issues/02-scheduler-skips-missed-0900.md) | T+1 盘后调度只在 Worker 跨过 09:00 时提交，错过不补交；P0 截止改口径未写入 ADR | ready-for-agent |
| [03](issues/03-audit-lookback-and-core-only-days.md) | 体检未覆盖“回溯得出”与“只更正核心”日 | done |
| [04](issues/04-audit-loan-ytd-diff-false-missing.md) | 体检贷款年内差分 189 项“缺失”为误报 | done |
| [05](issues/05-audit-purged-periods-member-level.md) | 体检第一层“已入库后被清理”按指标聚合，掩盖成员差别 | ready-for-agent |
| [06](issues/06-receipt-and-calendar-residuals.md) | 残余 01／02 的未处理部分 | ready-for-agent |
| [07](issues/07-audit-script-residuals.md) | 体检脚本的零散残余（时间比较、原话复核、空串网址） | ready-for-agent（(b) wontfix） |
| [08](issues/08-lookback-cost-and-test-gaps.md) | 上一确认阶段回溯的成本与测试缺口 | ready-for-agent（缓存 wontfix） |

不开票的已知局限：确认度在典型组合下尚无真实数据验证（体检报告已写明，等出现典型组合的真实运行）；体检商品广度、库存象限只核本运行投影（文档已列局限）。
