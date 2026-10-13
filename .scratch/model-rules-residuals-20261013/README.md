# 模型规则后续批次的遗留（2026-10-13）

来源：[模型规则后续批次](../model-rules-followups-20261012/README.md) 收尾验收（[acceptance-20261013.md](../model-rules-followups-20261012/acceptance-20261013.md) 遗留一节）与 [goal.md](../model-rules-followups-20261012/goal.md)“本批新增遗留”。尚未分流。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-clock-two-time-syncs-fight.md) | WSL 墙钟两套校时打架，尚无持久处置 | needs-triage |
| [02](issues/02-check-time-zero-tolerance.md) | `_check_time` 对墙钟回拨零容忍、整批拒收 | needs-triage |
| [03](issues/03-basket-fast-path-never-fires-daily.md) | 篮子快路径日常不触发，反而多 4 次请求；票 06 其余残余 | needs-triage |
| [04](issues/04-audit-false-reports-after-correction-and-purge.md) | 体检在更正版本与已清理数据上的误报；旧运行 `KeyError` | needs-triage |
| [05](issues/05-empty-url-dedup-vs-audit-doc.md) | 空串网址去重：生产与体检文档不一致 | needs-triage |
| [06](issues/06-text-time-comparisons.md) | 体检 SQL 与 `_load_announced` 按文本比较时间 | needs-triage |
| [07](issues/07-retention-result-not-recorded.md) | 留存清理结果没有写入运行记录 | needs-triage |
| [08](issues/08-stale-runs-and-polluted-report.md) | 旧 targeted_refresh 残留；被时钟污染的第 1 版报告 | needs-triage |
