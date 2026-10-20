Status: superseded (was ready-for-agent)
Execution: blocked
Type: task
Delivery: source-material
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 12: 三指数估值的新窗完整维度与发布证据认证材料

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 000300、000905、000852 的既定估值指标，从各指数交付到声明与历史选择可对账，形成可用于新候选的完整材料。

**Blocked by:** None (can start immediately)。无票前置不表示外部材料已经齐备。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

沿用旧 #07 已收口的 PE/PB/换手等定义与公式依赖；逐指数、measure、日期检查，不用某一指数成功或总行数代替全维度。数值与发布版本各自有据；缺一项必需成员或发布证据仍阻塞。

仅调查到“未找到”不能完成本票。缺件时记录已查范围、失败证据与受影响结果，Execution 保持 blocked；Status 的 ready-for-agent 表示任务描述可执行，不表示来源合格。

**规格覆盖：** User Stories 11、15、23；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 按既定定义核定 000300、000905、000852 所需 PE/PB/换手等 measure、新窗口和实际公式依赖，保留原定义/单位。
- [ ] 从每个指数交付经原件、解析、声明及历史点时查询完成逐日期/维度对账，形成可供候选绑定的合格审核材料。
- [ ] 每项采用的数值版本绑定可靠发布证据；某指数成功或总行数足够不能替代其余指数/measure 的完整性。
- [ ] 缺一个必需成员、错身份/单位、未证实修订或发布时间均明确阻断；复用已有维度拒收与软件证据，不改变估值公式凑值。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #03](../../pring-data-acquisition-repair/issues/03-context-acquisition-receipts.md)；[旧 #07](../../pring-data-acquisition-repair/issues/07-valuation-certification.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。

- 2026-09-22 18:10 +0800：真实3次TuShare整窗请求，经现有公开解析和主代理独立原始正文逐日期/维度核对，三指数各120日×3成员、1080值，无缺日/重复/额外日期；旧两指数08-28六值一致，000852旧空响应与本次非空各自保留。见[原件及认证缺件](../evidence-12-value-review.md)。PUBLIC全部未知，方法/发布版本/正式声明与来源认证未完成，保持blocked，不勾认证验收。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
