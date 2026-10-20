Status: superseded (was ready-for-agent)
Execution: not-started
Type: task
Delivery: source-material
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 10: 沪深融资新 17 日与整窗发布证据认证材料

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 新身份下的沪深融资值经正式采集、入库及历史查询对账，具备本轮所需两所数值与各自可靠发布证据。

**Blocked by:** [06 — 沪深融资新身份的采集到消费软件闭环](06-margin-two-exchange-delivery.md)

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

复用已保存 16 份上交所 XLS；补查当时 09-22 的 404，并覆盖深交所。16 份成功不代表两所齐全，HTTP 修改时间不自动等于首次发布。保持融资 P1、两所身份及旧历史分离；缺件继续阻塞该票。

仅调查到“未找到”不能完成本票。缺件时记录已查范围、失败证据与受影响结果，Execution 保持 blocked；Status 的 ready-for-agent 表示任务描述可执行，不表示来源合格。

**规格覆盖：** User Stories 12、13、14、15、20；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 使用 06 的沪深融资新身份入口复用已保存 16 份上交所 XLS，补查当时 09-22 的 404，并覆盖所需深交所材料。
- [ ] 两所分别完成原件、日期、两个 measure、单位及数值对账，再按批准的两所合同形成声明与历史查询结果。
- [ ] 为新窗及实际必要前置输入逐值绑定可靠发布版本；HTTP 修改时间和 TuShare 交付日程未经证明不能替代首次发布证据。
- [ ] 完整合格的两所材料经正式认证审核可供新候选绑定；一所缺值/缺发布证据不能由另一所或旧三所值替补，必要缺件保持未完成。
- [ ] 保留 P1、两所 scope 与旧历史分离，盘中 404 和失败尝试可追溯，不产生北交所残差或默认空值。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #03](../../pring-data-acquisition-repair/issues/03-context-acquisition-receipts.md)；[旧 #05](../../pring-data-acquisition-repair/issues/05-margin-certification.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。
- **沪深融资现状：** [已完成身份切片及尚缺合同](../../pring-data-acquisition-repair/implementation-05-margin-scope-20260922.md)。
- **真实原件与缺口：** [09-22 有界补查及新 17 日保存结果](../../pring-data-acquisition-repair/research-publication-followup-20260922.md)。失败/空响应不证明永不发布。
- **已有材料：** [获取收据](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/receipts.jsonl)、[终态](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/summary.json)、[机械内容检查](../../pring-data-acquisition-repair/evidence-publication-rescue-20260922/20260922T064537521872Z/content-check.json)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
