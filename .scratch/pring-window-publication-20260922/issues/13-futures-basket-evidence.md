Status: superseded (was ready-for-agent)
Execution: blocked
Type: task
Delivery: source-material
Date: 2026-09-22
Review state: 用户已确认按 19 票发布，保留批准的粒度与阻塞边。

# 13: 真实月份合约与去生猪篮子的新窗证据交付

**Parent:** [固定窗口、预热证据与目录迁移规格](../spec.md)；[已批准拆分记录](../ticket-breakdown-proposal.md)。

**What to build:** 复用旧 #11/#12 的合同和冻结换月规则，将新窗口及必要预热的真实合约、历史可知映射、价格和发布证据贯穿到篮子派生与血缘查询。

**Blocked by:** None (can start immediately)。无票前置不表示外部材料已经齐备。

## Scope

本轮目标固定 2026-09-22，正式窗口为 2026-04-01 至 2026-09-22，含首尾 120 个中国交易日。执行跨日不移动末端；必要预热按冻结公式另定，来源缺件不导致缩窗。

只做新范围差额及旧缺件复核，不重建既有篮子软件；覆盖换月/到期与父项完整性，不跨合约相除、不把主力连续代理当真实月份合约。必要映射、价格或发布证据缺失继续阻塞。

仅调查到“未找到”不能完成本票。缺件时记录已查范围、失败证据与受影响结果，Execution 保持 blocked；Status 的 ready-for-agent 表示任务描述可执行，不表示来源合格。

**规格覆盖：** User Stories 6、7、11、23；本票同时继承规格中的版本、证据与验收边界。

## Acceptance criteria

- [ ] 复用真实月份合约合同与冻结换月规则，按本轮窗口和必要预热列出真实合约、历史可知映射、价格及发布版本需求。
- [ ] 补新 17 日差额及仍缺父项，经现有公开获取/选择/篮子计算查询读回去生猪篮子及每个实际采用输入的血缘。
- [ ] 在换月、到期及父项边界核对映射当时可知，价格口径正确；不跨合约相除，不用主力连续代理冒充真实月份合约。
- [ ] 每项必要父输入及映射具有合格原件和点时依据，可供本轮真实认证/候选绑定；任何缺件继续阻塞，软件 fixture 不替代真实证据。
- [ ] 保留既有篮子规则、商品核心和历史数据版本；只处理增量范围与旧缺件，不重建已验软件或全量抢救。

## Testing decisions

经现有公开采集/解析/声明/点时查询及审核入口核验真实材料，保留原件、获取时刻、版本、缺件和实际终态。fixture 只证明软件行为，不代替真实来源。软件未变时按[已确认收据复用规则](../../pring-data-acquisition-repair/remaining-work-efficiency-20260918.md)复用有效软件收据，新增数据完成相应质量与认证；必要代码变更重新遵守[项目测试规则](../../../docs/agents/testing.md)。

## Reuse and references

- **原交付：** [旧 #11](../../pring-data-acquisition-repair/issues/11-futures-contract-evidence.md)；[旧 #12](../../pring-data-acquisition-repair/issues/12-commodity-basket.md)。只复用适用的实现与收据，不重置旧票。
- **实施定位：** [公开入口与既有测试先例](../implementation-context.md)。定位仅供核对，不限定具体实现文件。
- **证据规则：** [ADR-0019 计算预热](../../../docs/adr/0019-formula-warmup-requires-publication-evidence.md)、[ADR-0018 发布日期](../../../docs/adr/0018-tiered-evidence-for-historical-publication-dates.md)。

## Execution notes

开始前阅读完整父规格、本票及其直接前置的实际终态，核对[旧工作续接记录](../../pring-data-acquisition-repair/continuation-status.md)中日志/句柄是否仍有效。只实施本票交付，不修改或关闭父规格及旧任务，不覆盖既有原件、失败收据和发布历史。

把新发现和进度追加到本票 Comments，验收逐项依据实际证据勾选；软件、来源认证、回放和切换分别记结论。任何后续依赖只按本票已证明的交付解除，不能仅凭文档状态推断全部产品就绪。

## Comments

- 2026-09-22：用户回复“按此 19 票发布（推荐）”，按已批准拆分正式发布。本票尚未实施，验收项均未勾选。

- 2026-09-23：开始独立只读真实材料差额盘点source13-inventory，范围包括冻结真实合约/换月、历史可知映射、价格/发布原件与新增17日；不联网、不重新构建旧篮子软件，后续由主代理核验再安排最小实际取证。

- 2026-09-23：独立盘点结束，主代理核535原路径14件有效/152缺失。实际新增2次SHFE GET，301合约身份、331行情行，其中66个CU/RB/RU/SP/SC普通月份合约有对应身份及正结算对。仍缺逐版本公开、PP/CF/TA、日历/时段与整条价格链，保持blocked不勾AC。详见../evidence-13-value-review.md，原件/失败不覆盖。
- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
