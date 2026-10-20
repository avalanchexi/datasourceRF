Status: superseded (was ready-for-agent)
Execution: not-started
Type: task
Delivery: real-acceptance
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 15: 绑定真实材料并创建新完整候选

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 经公开认证请求和准入入口形成真实新目录/模型、完整材料预检、来源包绑定与可查询的候选验收记录。

**Blocked by:** [07 — 新目录和新窗口的完整隔离生命周期验收](07-isolated-window-lifecycle.md)；[08 — 000985 与 000012 的新窗及预热发布证据认证材料](08-csi-core-publication.md)；[09 — NHII 原件复用、补值及预热发布证据认证材料](09-nhii-publication.md)；[10 — 沪深融资新 17 日与整窗发布证据认证材料](10-margin-publication.md)；[11 — 其余确认指数的新窗发布证据认证材料](11-confirmation-index-publication.md)；[12 — 三指数估值的新窗完整维度与发布证据认证材料](12-valuation-publication.md)；[13 — 真实月份合约与去生猪篮子的新窗证据交付](13-futures-basket-evidence.md)；[14 — 其余目录的新窗口差额对账与缺口归属](14-remaining-catalog-reconciliation.md)

**材料前置:** 14 矩阵中的全部必需缺口已由各责任任务补齐，既有离线校准及候选准入的必需历史材料满足原门槛；不能仅凭这些票的文档状态放行。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

继承旧 #19 的真实门；检查目录、公式、日历、代码/安装和材料身份一致，任何未完成检查、旧审核包或必需来源缺件拒收。CNY030 待认证仍可选；不激活生产模型。软件收据复用按实际绑定判定。

**规格覆盖：** User Stories 16、17、19、20、21、22、23、24、25、27；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 逐项核验上游真实材料及 14 的全部必需缺口已合格关闭；既有离线校准/准入所需历史满足原门槛，不以票面完成状态代替材料。
- [ ] 经公开认证请求、准入和候选验收入口形成真实新目录/模型，绑定完整来源包、公式、日历、目标窗口及实际材料。
- [ ] 完整材料预检实际完成各必需检查并通过；旧审核包、缺必需来源、未完成检查或不匹配软件/材料身份必须拒收。
- [ ] 三核心和其他 P1 合格，CNY030 为 P2 待认证并保留可选缺口；来源包、目录注册、模型与查询结果可相互对账。
- [ ] 仅复用绑定有效的软件收据，新数据完成对应质量/认证验收；不倒填 SYSTEM、不改历史结果、不激活生产模型。

## Testing decisions

使用本票要求的真实公开流程与查询结果验收，明确真实材料、隔离 fixture 和正式操作各自证明范围。核对源码、实际导入包及材料身份，只复用有效收据；输入变化时补受影响及既有必需门。重型执行、磁盘、终态与软件收据要求见[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #19](../../pring-data-acquisition-repair/issues/19-immutable-candidate-catalog.md)；[旧 #09](../../pring-data-acquisition-repair/issues/09-breadth-window-metrics.md)；[旧 #10](../../pring-data-acquisition-repair/issues/10-breadth-amount-share.md)；[旧 #13](../../pring-data-acquisition-repair/issues/13-remaining-p1-evidence.md)；[旧 #14](../../pring-data-acquisition-repair/issues/14-p2-availability.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **窗口：** [日历规划及来源哈希](../calendar-plan.json)。该清单不替代应用日历认证。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。
- **目录决定：** [ADR-0020 CNY030](../../../docs/adr/0020-cny030-optional-pending-certification.md)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
