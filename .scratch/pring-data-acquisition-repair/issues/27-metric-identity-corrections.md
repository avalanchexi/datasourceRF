Status: superseded (was ready-for-agent)
Execution: in-progress
Scope: 来自[规格24](../spec-24-source-identity-20260917.md)第三、四节
Decision: 2026-09-17 用户确认：USD/CNH 改用 TMA 定盘并重命名；删除 COMEX_GC 与 LBMA_GOLD；VIX/SOX/USDCNY_CLOSE_1630 走各自官方通道。
Correction: 2026-09-17 23:42 的[后续决定](../decision-27-ecb-reference-cross-20260917.md)已**用独立 ECB 身份替代原计划 TMA 新项**，本票下方仍写 TMA 的部分作废。
Correction: 2026-09-22 事实对齐——**身份迁移软件已由五个提交落地**（`61de7e0`、`06bccc3`、`dc44076`、`26a0b84`、`fd330c2`），验收一、二已有实现与反例，剩验收三的三条官方通道。**照本票原文从头实施会重做已有工作**，先读[事实对齐](../finding-27-migration-facts-20260922.md)；[身份迁移盘点](../survey-27-identity-migration-20260921.md)是在「尚未动手」假设下写的，其「闸仍待解决」的前提已过时。

# 27: 修正五项 P2 国际行情的口径与身份

**What to build:** P2 国际行情各项的口径与其实际发布方一致；不再有指标 id 把上游代码或经纪商名字当作标准口径。

**Blocked by:** 无。

**Dependency rationale:** 独立于票25、26；三张票可并行。

## 逐项动作

| 指标 | 动作 | 依据 |
|---|---|---|
| `CN_USDCNH_FXCM` | ~~改用 TMA 定盘并重命名~~ → **改为新建独立指标 `CN_USDCNY_ECB_REFERENCE_CROSS`**（P2 / context-only，单位 `cny_per_usd`，公式为同日同一 ECB 发布的 CNY/EUR ÷ USD/EUR）；旧 FXCM 定义与历史继续可追溯，不拼接、不回写旧观测 | [ECB 决定](../decision-27-ecb-reference-cross-20260917.md)：TMA 暂无授权且保留缺口的决定保持。**TMA 侧无适配器**，照原文实施必撞 `registered_source_contract_not_implemented` |
| `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | **删除** | 与 LBMA 金价高度重叠，历史批量需 CME DataMine 付费 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | **删除** | 历史需 ICE Benchmark Administration 授权，只能走 FRED 转发；为一项 P2 背景指标建整套非官方身份语义不划算 |
| `CBOE_VIX_INDEX` | 接 Cboe 官方免费 CSV，正常认证 | TuShare `index_global` 的 20 个指数不含 VIX |
| `NASDAQ_SOX_INDEX` | 接 Nasdaq 官方指数站，正常认证 | 同样不在 `index_global` 内 |
| `CN_USDCNY_CLOSE_1630` | 接 CFETS / 中国货币网，正常认证 | 本项目已有该域通道（`CN_LPR_1Y_5Y` 走同一域且已认证） |

## 待设计的可观察行为

- 指标 id 是身份的一部分：**重命名与删除必须作为迁移设计**，波及目录版本、历史声明与投影。旧 id 的历史证据如何处置须显式表达，不得静默丢弃。
- 新接的三项走既有认证流程，**不引入新的认证身份**——`certification_status` 保持 `certified` / `awaiting_source_certification` 两值不变。

## 验收条件

- [ ] 重命名后旧 id 的历史声明可追溯，且新旧不混算；有反例证明混算会失败。
- [ ] 删除两项黄金指标后，依赖它们的派生与投影路径明确报错或明确不再需要，不留悬空引用。
- [ ] VIX / SOX / USDCNY_CLOSE_1630 各有取得原件与认证材料，走既有认证流程。
- [ ] `certification_status` 取值集合不变。

## 未核实

Cboe CSV、Nasdaq 指数站、TMA 定盘的当前可达性与可程序化取用方式。实现第一步应先核实，取不到则该项保持未认证而非降级冒充。

## 2026-09-22 用户决定：三条 P2 通道只推 VIX

三项均为 P2，按 `candidate_admission.py:207` 可合法保持 `awaiting_source_certification`，
因此这里的取舍不受 [ADR-0016](../../../docs/adr/0016-certification-gate-escape-valve-is-catalog-membership.md) 约束。

| 通道 | 决定 | 理由 |
|---|---|---|
| `CBOE_VIX_INDEX` | **去接** | 唯一一项缺的是工时而非权利：官方免费 CSV 已可取，只需定 CLOSE 口径与时区、做适配器、走既有认证流程。**不得**从日期或常规日程补造历史发布时间。 |
| `NASDAQ_SOX_INDEX` | **接受长期 `awaiting_source_certification`** | 卡点是用途许可，不是工时。为一项 P2 背景指标去谈持续保存与分析的授权，与当初删除两项黄金的账目相同（"为一项 P2 背景指标建整套非官方身份语义不划算"），应得同一结论。六日 XLSX 与方法文件保留为证据，不据此接入。 |
| `CN_USDCNY_CLOSE_1630` | **接受长期 `awaiting_source_certification`** | 不是决心问题：`closeSpotPrice` 快照为 `---`，历史收盘原件不存在；当前成交价、中间价、ECB 交叉值都不得补位。人民币交叉的需求已由 `CN_USDCNY_ECB_REFERENCE_CROSS` 覆盖。 |

**对验收三的影响**：该条改为"VIX 取得原件与认证材料并走既有认证流程；SOX 与 CLOSE_1630 记为
合规缺口，作为受限 P2 保持未认证"。按票19 验收三「受限/未认证 P2 保持合规缺口，不作为强制采购条件」，
这两项的未认证状态是**预期结果**，不是遗留缺件。

**验收四不受影响**：`certification_status` 仍是两值，接受 awaiting 正是在既有取值内表达。

## Comments

- 2026-09-24 标记为被取代：本 effort 的认证→准入→回放→切换路线已由 ADR-0021–0025 取代（见 `docs/adr/`），取数与发布的实质内容已并入 `.scratch/pring-fast-refactor-20260923` 票 10–28 并交付（提交至 fa92b65）。仍未解决的取数缺口见该 effort 票 28 的遗留清单；若本票内容仍需要，按新路线重新立项，不在此继续。
