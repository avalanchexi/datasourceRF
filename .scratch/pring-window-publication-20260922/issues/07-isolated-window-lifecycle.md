Status: superseded (was ready-for-agent)
Execution: not-started
Type: task
Delivery: software
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 07: 新目录和新窗口的完整隔离生命周期验收

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 合法隔离材料通过新范围的完整预检、候选准入、验收、回放及隔离运行查询，并形成同版本软件收据。

**Blocked by:** [02 — CNY030 专项优先级迁移与可选缺口消费](02-cny030-optional-migration.md)；[03 — 三核心计算预热的逐截止点验证](03-core-formula-warmup.md)；[04 — 上下文公式的期次、维度与预热父输入验证](04-context-formula-parents.md)；[05 — 全目录原件与维度完整性的公开预检](05-catalog-material-preflight.md)；[06 — 沪深融资新身份的采集到消费软件闭环](06-margin-two-exchange-delivery.md)

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

所有必需检查实际完成后才给对应就绪结论；保留一个必需失败反例和 CNY030 可选缺口成功例。结合旧 #19 已有生命周期材料和旧 #17/#18/#22 已完成软件交付，完成受影响重型与同版本必需全套，核对实际导入包与材料。真实认证和正式指针不由此票完成；无真实来源票作为前置。

**规格覆盖：** User Stories 24、25、26、27、33、34；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 使用包含 CNY030 P2、沪深融资及既有其他批准处置的完整合法隔离目录，贯穿新窗口预检、准入、验收、回放及隔离运行查询。
- [ ] 日历、原件、维度、逐 cutoff 点时及完整父输入均实际执行后，才授予相应就绪结论；退出码 0、空 gaps 或已有观测本身不足以通过。
- [ ] 保留完整正例、必要材料失败拒收例及 CNY030 可选待认证仍能完成的例；各结果和来源血缘绑定同一模型、窗口及材料。
- [ ] 复用有效旧生命周期/Worker/报告交付；核对源码、子进程实际导入发行物、依赖与被读材料身份，完成必要相关重型验证及稳定同版本默认全套。
- [ ] 归档真实终态、退出码及前后身份；重型任务串行并遵守磁盘规则，不拼接跨版本通过数。隔离激活只在专属运行库，真实认证/正式指针/切换不由本票完成。

## Testing decisions

沿用已批准的公开任务命令/API → 持久任务 → 单次 Worker → 投影/运行/证据/报告读取边界；必要时使用 PUBLIC/SYSTEM 选值或趋势/阶段的公开领域接口。只替换外部传输、时钟或 CLI，解析、选择、仓库与投影保持真实。先复用有效反例和交付，仅为实际缺口补行为验证；相关重型及同版本全套按[项目测试规则](../../../docs/agents/testing.md)执行，记录实际终态与身份，不为每票重复整套。

## Reuse and references

- **原交付：** [旧 #17](../../pring-data-acquisition-repair/issues/17-full-run-gap-retrieval.md)；[旧 #18](../../pring-data-acquisition-repair/issues/18-report-cli-evidence.md)；[旧 #19](../../pring-data-acquisition-repair/issues/19-immutable-candidate-catalog.md)；[旧 #22](../../pring-data-acquisition-repair/issues/22-live-acceptance-cutover.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **窗口：** [日历规划及来源哈希](../calendar-plan.json)。该清单不替代应用日历认证。
- **目录决定：** [ADR-0020 CNY030](../../../docs/adr/0020-cny030-optional-pending-certification.md)。
- **预检剩余范围：** [剩余检查评估及后续更正](../../pring-data-acquisition-repair/plan-19-preflight-remaining-checks-20260920.md)。历史建议先与已实施状态核对。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
