# 反复出现的输入缺口批次的遗留（2026-10-14）

来源：[反复出现的输入缺口](../recurring-input-gaps-20261013/goal.md) 票 05 收尾验收（[acceptance-20261014.md](../recurring-input-gaps-20261013/acceptance-20261014.md) 遗留一节）。01、02 含用户 2026-10-14 的决定；其余尚未分流。

规格：[spec.md](spec.md)（ready-for-agent），覆盖 01、02、05、06；03、04 并入其收尾验收；07 不在范围。

| 票 | 内容 | 状态 |
|---|---|---|
| [01](issues/01-usdcny-close-previous-day.md) | 人民币 16:30 收盘价取上一交易日值即可 | needs-triage |
| [02](issues/02-sox-source.md) | SOX 接入：先 TuShare，否则可信网站，不用 ETF 代理 | needs-triage |
| [03](issues/03-effective-run-slower.md) | 有效运行耗时 12.6→33.6 分，根因未明 | needs-triage |
| [04](issues/04-verify-0930-on-time.md) | 09:30 准点提交未验证（需调电源设置） | ready-for-human |
| [05](issues/05-audit-new-cutoff-effective-time.md) | 体检内置新口径生效时刻 | needs-triage |
| [06](issues/06-rrr-lookback-cutoff-readability.md) | 官方降准回溯未复核截止时可读性 | needs-triage |
| [07](issues/07-watch-lock-and-ssl-eof.md) | 观察项：`database is locked`、日历 SSL EOF | needs-info |

另有未分流的上一批遗留：[model-rules-residuals-20261013](../model-rules-residuals-20261013/README.md)（8 张）。

## 实施票（落实上表来源票，进度见 [goal.md](goal.md)）

| 票 | 内容 | 被阻塞 | 落实 |
|---|---|---|---|
| [08](issues/08-usdcny-close-holds-previous-session.md) | 16:30 收盘价持有上一交易日 | — | 01 |
| [09](issues/09-sox-registered-source.md) | SOX 接入取数路径（来源经用户确认） | — | 02 |
| [10](issues/10-audit-new-cutoff-effective-time.md) | 体检内置新口径生效时刻 | — | 05 |
| [11](issues/11-rrr-backtrack-checks-cutoff-readability.md) | 降准回溯复核截止时可读性 | — | 06 |
| [12](issues/12-audit-sox-has-a-path.md) | 体检：SOX 有取数路径后的口径 | 09 | 02 |
| [13](issues/13-acceptance.md) | 收尾验收（含 03 复测、04 准点样本） | 08–12、电源设置 | 03、04 |
