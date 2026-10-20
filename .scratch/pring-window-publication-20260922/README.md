> **已被取代（2026-09-24）**：本 effort 的开放票已全部标记为 superseded。其路线由 ADR-0021–0025 取代，实质内容并入 `.scratch/pring-fast-refactor-20260923`（票 10–28，已交付）。

# 2026-09-22 固定窗口任务索引

2026-09-22 用户已确认“按此 19 票发布（推荐）”。19 票已逐票发布，均为 `Status: ready-for-agent`。01软件与02准入切片已审并集成；05诊断切片两轴及相关重型通过并集成，完整家族材料正例待完成。03 r2、04 r1、06 r4在独立树并行实施；08/09/11补证已有部分真实原件，仍未完成来源认证。整Goal尚未完成，默认全套及提交待最终软件冻结。实时分派和句柄见 [执行状态](execution-status.md)。

本页记录当前发布状态；[父规格](spec.md)保留规格阶段的原始状态文字，没有因拆票修改父规格。范围及粒度见[已批准拆分记录](ticket-breakdown-proposal.md)。

## 从哪里开始

续接先核[执行状态](execution-status.md)和实际在途。01的软件交付允许03/04/05继续实施；不要重复领取在途票。无票前置的任务还有 **02、06、08、09、11、12、13**；可按实际阻塞择取。它们可以开始核查或实施，不表示真实来源材料已经齐备。

每次读取完整规格、当前票及直接前置的实际交付后实施，保留新旧任务的独立编号。先完成真正前置再解除依赖；同文件修改冲突属于调度问题，重型测试/校准/回放仍须串行。

## 正式任务

| 任务 | 交付类别 | 直接阻塞票 |
|---|---|---|
| [01 — 固定新窗口并从公开预检读回交易日范围](issues/01-fixed-window-calendar.md) | 软件 | 无 |
| [02 — CNY030 专项优先级迁移与可选缺口消费](issues/02-cny030-optional-migration.md) | 软件 | 无 |
| [03 — 三核心计算预热的逐截止点验证](issues/03-core-formula-warmup.md) | 软件 | 01 |
| [04 — 上下文公式的期次、维度与预热父输入验证](issues/04-context-formula-parents.md) | 软件 | 01 |
| [05 — 全目录原件与维度完整性的公开预检](issues/05-catalog-material-preflight.md) | 软件 | 01 |
| [06 — 沪深融资新身份的采集到消费软件闭环](issues/06-margin-two-exchange-delivery.md) | 软件 | 无 |
| [07 — 新目录和新窗口的完整隔离生命周期验收](issues/07-isolated-window-lifecycle.md) | 软件 | 02、03、04、05、06 |
| [08 — 000985 与 000012 的新窗及预热发布证据认证材料](issues/08-csi-core-publication.md) | 真实材料 | 无 |
| [09 — NHII 原件复用、补值及预热发布证据认证材料](issues/09-nhii-publication.md) | 真实材料 | 无 |
| [10 — 沪深融资新 17 日与整窗发布证据认证材料](issues/10-margin-publication.md) | 真实材料 | 06 |
| [11 — 其余确认指数的新窗发布证据认证材料](issues/11-confirmation-index-publication.md) | 真实材料 | 无 |
| [12 — 三指数估值的新窗完整维度与发布证据认证材料](issues/12-valuation-publication.md) | 真实材料 | 无 |
| [13 — 真实月份合约与去生猪篮子的新窗证据交付](issues/13-futures-basket-evidence.md) | 真实材料 | 无 |
| [14 — 其余目录的新窗口差额对账与缺口归属](issues/14-remaining-catalog-reconciliation.md) | 对账/交接 | 02、04 |
| [15 — 绑定真实材料并创建新完整候选](issues/15-real-complete-candidate.md) | 真实验收 | 07、08、09、10、11、12、13、14 |
| [16 — 固定 120 日真实 PUBLIC 回放与差异归因](issues/16-public-replay-120d.md) | 真实验收 | 15 |
| [17 — 新目标与同组真实缺口的配对检索测量](issues/17-paired-retrieval-benchmark.md) | 真实验收 | 15 |
| [18 — 09-22 真实隔离运行、报告和恢复验收](issues/18-target-run-report-recovery.md) | 真实验收 | 16 |
| [19 — 汇总最终真实验收并沿显式操作生效、切换](issues/19-live-acceptance-cutover.md) | 真实验收 | 17、18 |

## 材料与操作条件

- 07 汇总软件行为，不等待 08–14 的真实来源交付；有效软件收据可按既定绑定规则复用。
- 08–13 的材料缺件继续阻塞各自完成，不能以“未找到”的调查报告关闭认证交付。
- 14 交付逐项对账与责任交接；15 还必须核实矩阵内全部必需缺件已补齐，旧任务仍有未闭合材料时不能放行。
- 16 另需相同完整区间的合法比较基线；16 与 17 不互相等待。18 等待 16；19 汇合 17/18，并核对后续新增版本对收据有效性的影响。
- 凭据、预算、机器验收与具体生效/切换授权仍按各票前置条件执行。本次发布只确认任务范围和依赖，没有执行来源认证、回放、生效或切换。

## 实施资料

- [公开入口和测试先例](implementation-context.md)
- [固定日历规划与原件哈希](calendar-plan.json)
- [项目测试与收据复用规则](../../docs/agents/testing.md)
- [旧工作的续接记录](../pring-data-acquisition-repair/continuation-status.md)：历史在途记录必须核实际进程/终态，不据旧句柄自行重启。

发布时仅进行文档结构检查；后续实施、验证与来源取证已按各票Comments和执行状态分别留证。逐票完成条件和执行进度以各票正文及 Comments 为准。
