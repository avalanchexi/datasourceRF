Status: superseded (was ready-for-agent)
Execution: not-started
Type: task
Delivery: material-reconciliation
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 14: 其余目录的新窗口差额对账与缺口归属

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 对 08–13 未承接的指标逐项给出新窗及实际公式需求的材料矩阵，列出可复用收据、增量期次、必需缺件和可选缺口，并逐项链接现有责任票。

**Blocked by:** [02 — CNY030 专项优先级迁移与可选缺口消费](02-cny030-optional-migration.md)；[04 — 上下文公式的期次、维度与预热父输入验证](04-context-formula-parents.md)

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

覆盖广度/成交金额、其余宏观及政策 P1、运维证据和 P2；按当前目录枚举，不硬编码 61/42/27 等旧数量。已有有效材料直接对账；DR007 历史发布、仓单单位和 RRR 事件等未闭合事项继续由对应旧任务承接，明确本次增量范围。CNY030 的 P2 待认证和其他受限 P2 可作为诚实缺口交付，不要求取得全部 P2。

此票只完成逐项对账和明确的材料交接，不包办所有来源研发/认证，也不以矩阵完成表示必需缺件归零。15 仍单独要求矩阵中的每项必需证据合格；若发现缺口没有责任任务，先形成具体拆票修订，不把未知工作塞进本票。

**规格覆盖：** User Stories 4、6、13、14、15、21、27、34、35；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 从批准的新目录枚举 08–13 未承接的全部成员，并用 04 的实际公式需求形成新窗差额矩阵，覆盖广度/成交金额、宏观政策、运维证据及 P2。
- [ ] 每项列明所需期次/维度、真实取得/校验/认证/PUBLIC/SYSTEM/采用状态、可复用收据及其绑定；不硬编码旧 61/42/27 数量。
- [ ] 每个必需缺件列明确切补件范围和现有责任任务，含 DR007 历史发布、仓单单位及 RRR 事件等未闭合项；旧票已完成记录保留。
- [ ] CNY030 及其余可选/受限 P2 诚实呈现待认证或授权缺口，不要求全 P2 取得；缺件不填零、不造事件或每日复制低频事实。
- [ ] 交付可逐项复核的矩阵与交接即可完成本票，但不得宣称必需缺件归零；15 的每项材料门单独核查。发现没有责任任务的缺口时先给具体拆票修订，不静默扩大本票。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #09](../../pring-data-acquisition-repair/issues/09-breadth-window-metrics.md)；[旧 #10](../../pring-data-acquisition-repair/issues/10-breadth-amount-share.md)；[旧 #13](../../pring-data-acquisition-repair/issues/13-remaining-p1-evidence.md)；[旧 #14](../../pring-data-acquisition-repair/issues/14-p2-availability.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **窗口：** [日历规划及来源哈希](../calendar-plan.json)。该清单不替代应用日历认证。
- **目录决定：** [ADR-0020 CNY030](../../../docs/adr/0020-cny030-optional-pending-certification.md)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
