Status: superseded (was ready-for-agent)
Execution: in-progress
Type: task
Delivery: source-material
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 09: NHII 原件复用、补值及预热发布证据认证材料

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 已抢救南华原件经正式解析/声明/点时查询完成对账，再补齐三核心商品项所需的窗口和计算预热证据。

**Blocked by:** None (can start immediately)。无票前置不表示外部材料已经齐备。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

先核 09-02、03、04、08 的值，处理 09-07/22 在当次目录未列出的实际缺件；不重抓已核验原件。复核相关版本、NHII 身份和既有权重/方法边界，不用 PDF 日期匹配冒充数值验收。必要材料仍缺则保持阻塞，不切换商品核心。

仅调查到“未找到”不能完成本票。缺件时记录已查范围、失败证据与受影响结果，Execution 保持 blocked；Status 的 ready-for-agent 表示任务描述可执行，不表示来源合格。

**规格覆盖：** User Stories 12、13、14、15、16；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 核验并复用已保存南华 15 组页面/PDF，按官方身份和版本对账；先解决 09-02、09-03、09-04、09-08 尚未机械核出 NHII 值的材料。
- [ ] 针对当次目录未列 09-07 和 09-22 记录实际补查与原件，不能把旧目录观察或盘中抓取状态视为从未发布或日终结论。
- [ ] 通过正式解析、声明与点时选择读回 NHII 值及真实血缘，复核新窗口及必要计算预热的数值、逐版本发布时间和既有方法/权重边界。
- [ ] 取得合格且范围完整的来源审核材料后才完成；PDF 日期匹配、下载成功或研究对象保存不能代替数值与来源认证。
- [ ] 缺少必要数值或发布证据保持本票阻塞；不重抓已核验对象、不切换商品核心、不回写旧数据版本。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #02](../../pring-data-acquisition-repair/issues/02-core-acquisition-receipts.md)；[旧 #04](../../pring-data-acquisition-repair/issues/04-core-public-time-certification.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **窗口：** [日历规划及来源哈希](../calendar-plan.json)。该清单不替代应用日历认证。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。
- **真实原件与缺口：** [09-22 有界补查及新 17 日保存结果](../../pring-data-acquisition-repair/research-publication-followup-20260922.md)。失败/空响应不证明永不发布。
- **已有材料：** [获取收据](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/receipts.jsonl)、[终态](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/summary.json)、[机械内容检查](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/content-check.json)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。

- 2026-09-22：主代理在三项隔离软件实施同时，核对已保存 PDF 的四个数值解析缺件；尚未取得应用入库或来源认证通过。

- 2026-09-22 16:07 +08：原15组页面/PDF重验通过，四个解析缺口已图像核值；09-07原目录实际存在，但被旧脚本的“日报”标题过滤遗漏，补取附件并核得4122.92。新增17日现有16日原件数值；09-22目录复查仍未列。16份文章均提取自己的发布时间字段，尚未授予来源认证、应用声明或完整窗口/预热合格结论。见[原件复核及纠正](../evidence-09-value-review.md)。

- 2026-09-22 16:34 +08：追加历史盘点与两批补取，研究数值原件覆盖33/120日、公式输入49/259日；批量连接连续无响应后停止，保留失败且不判官方缺数据。正式官方PDF来源合同尚缺，详见原件复核后续段。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
