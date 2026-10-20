Status: superseded (was ready-for-agent)
Execution: in-progress
Type: task
Delivery: software
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 02: CNY030 专项优先级迁移与可选缺口消费

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 经公开候选准入注册新目录，Worker 和只读结果显示 CNY030 为 P2 待认证；其他必需证据有效时可继续完成运行。

**Blocked by:** None (can start immediately)。无票前置不表示外部材料已经齐备。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

与已有沪深融资、外汇及黄金处置兼容；仅 CNY030 的 P1→P2 变化。拒绝顺带降级其他指标、更改核心/角色/来源身份、复用旧审核包或覆盖旧目录。CNY030 数值不因可选而自动获认证。

**规格覆盖：** User Stories 16、17、18、19、20、21、22；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 通过公开候选审核/准入入口生成新目录和模型，CN_BOND_FULL_PRICE_CNY030 为 P2 且 awaiting_source_certification；从登记目录读回与声明一致。
- [ ] 保持指标 ID、债券确认角色、源代码及其他定义字段；与已批准沪深融资、外汇身份及黄金删除兼容，只有本项 P1 减一/P2 加一。
- [ ] 通过 Worker 及只读消费者验证：其余必需材料合法时运行可完成，CNY030 显式为可选缺口，不进入正式事实、派生输入或报告证据。
- [ ] 无迁移声明直接改优先级、顺带降级其他 P1、改核心/角色/源身份、旧审核包或同版本覆盖均被拒；三核心仍为 000985、000012、NHII。
- [ ] 旧目录、模型、声明和发布结果的身份/哈希保持不变；本票不要求取得 CNY030 合格来源。

## Testing decisions

沿用已批准的公开任务命令/API → 持久任务 → 单次 Worker → 投影/运行/证据/报告读取边界；必要时使用 PUBLIC/SYSTEM 选值或趋势/阶段的公开领域接口。只替换外部传输、时钟或 CLI，解析、选择、仓库与投影保持真实。先复用有效反例和交付，仅为实际缺口补行为验证；相关重型及同版本全套按[项目测试规则](../../../docs/agents/testing.md)执行，记录实际终态与身份，不为每票重复整套。

## Reuse and references

- **原交付：** [旧 #27](../../pring-data-acquisition-repair/issues/27-metric-identity-corrections.md)；[旧 #05](../../pring-data-acquisition-repair/issues/05-margin-certification.md)；[旧 #14](../../pring-data-acquisition-repair/issues/14-p2-availability.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **目录决定：** [ADR-0020 CNY030](../../../docs/adr/0020-cny030-optional-pending-certification.md)。
- **沪深融资现状：** [已完成身份切片及尚缺合同](../../pring-data-acquisition-repair/implementation-05-margin-scope-20260922.md)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。

- 2026-09-22：主代理按已授权 Goal 领取本票，准备独立工作树与虚拟环境；应用验收尚未通过。

- 2026-09-22 16:15 +08：隔离子任务交回公开准入/登记/选值/投影切片；88项选择测试通过，主代理核验安装103文件逐内容一致及测试终态。完整Worker、报告证据排除和发布历史不变仍待验证，整票未完成，暂不勾选验收。已固定WIP差异待两轴审查，见[执行状态](../execution-status.md)。

- 2026-09-22 16:34 +08：两轴审查已完成：Standards无发现，Spec指出核心源代码拒收、报告白名单、完整Worker和历史对象不可变证明缺口；已启动r2先核验并修复准入反例，报告路径保持已批准入口。

- 2026-09-22 17:15 +08：r2新增核心源代码守卫两轴0新增；准入/选值部分已顺序集成根树，与01组合公开入口44项通过，见[组合收据](../execution/integration-01-02-selected/terminal.json)。02整票仍不关闭，完整Worker/报告及历史保护待合法材料验证。公开进程CLI示例已[更正入口](../execution/parent-correction-02-cli-entrypoint.md)。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
