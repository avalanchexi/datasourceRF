Status: superseded (was ready-for-agent)
Execution: blocked
Type: task
Delivery: source-material
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 11: 其余确认指数的新窗发布证据认证材料

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 原 #06 中除 CNY030 外的必需确认指数，经原件、声明和点时选择形成新范围的合格审核材料。

**Blocked by:** None (can start immediately)。无票前置不表示外部材料已经齐备。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

从已批准目录确定成员、源代码、日期及实际公式依赖，复用已有采集实现和证据；不因 CNY030 降级放宽其他项。CNY030 留在 02/14 的可选待认证记录，不是本票成功前提；其他必需来源缺件则保持阻塞。

仅调查到“未找到”不能完成本票。缺件时记录已查范围、失败证据与受影响结果，Execution 保持 blocked；Status 的 ready-for-agent 表示任务描述可执行，不表示来源合格。

**规格覆盖：** User Stories 11、15、19；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 从批准目录核定旧确认指数任务中除 CNY030 外的必需成员、源代码、字段及公式需求，明确本票实际范围和逐项覆盖。
- [ ] 复用既有原件/采集能力，补新窗差额及必要预热，贯穿解析、声明、点时选择与来源审核材料，不重新研发已完成家族。
- [ ] 各成员的数值、统计日期和承载版本发布证据均合格；身份资料或发行日不充当逐值发布时间，旧绑定不直接冒用。
- [ ] CNY030 不列强制认证前提，其他指标不因此降级；任何必需成员缺件均列精确原因并保持本票未完成。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #03](../../pring-data-acquisition-repair/issues/03-context-acquisition-receipts.md)；[旧 #06](../../pring-data-acquisition-repair/issues/06-market-index-certification.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。
- **目录决定：** [ADR-0020 CNY030](../../../docs/adr/0020-cny030-optional-pending-certification.md)。
- **真实原件与缺口：** [09-22 有界补查及新 17 日保存结果](../../pring-data-acquisition-repair/research-publication-followup-20260922.md)。失败/空响应不证明永不发布。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。

- 2026-09-22：主代理核既定MARKET_INDEX_IDENTITIES与旧06官方原件，除CNY030外本票必需为000300/000905/000852/930916/NHCI，均是确认指标，不替换三核心。开始复用四CSI旧原件并有界补四次新增17日官方日线请求；只增加研究原件，逐版本公开证据/声明/来源认证仍待核，不能以行数代替认证。

- 2026-09-22 17:58 +0800：实际补四个官方CSI增量请求并独立核hash/代码/唯一日期/close；000300/000905/000852数值原件120/120，930916为119/120、缺09-22。复用现存PDF核49日NHCI，正式覆盖33/120、无新增南华请求。见[数值与阻塞核对](../evidence-11-value-review.md)。逐值PUBLIC版本证据、应用声明/来源认证仍缺，930916目标日与NHCI87个正式日数值仍缺；保持blocked，不勾认证AC。

- 2026-09-23：930916目标日日线185.22取得，研究正式覆盖120/120；PUBLIC、方法/应用合同及NHCI缺件仍阻塞。见../evidence-08-11-bond-target-followup/20260922T235719144642Z/coverage-verified.json；不更改旧原件，不将数值覆盖当认证。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
