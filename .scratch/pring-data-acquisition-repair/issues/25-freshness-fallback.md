Status: ready-for-agent
Execution: not-started
Scope: 来自[规格24](../spec-24-source-identity-20260917.md)第一节
Decision: 2026-09-17 用户定"默认 TuShare 是官方通道""TuShare 数据更新不及时时用官方数据"。

# 25: TuShare 未出该期时按指标回退到官方值

**What to build:** 用户能看到某个指标某个期次是由哪条通道交付的；TuShare 尚未发布该期时，该指标该期自动改用官方页的值，其余指标不受影响。

**Blocked by:** 无。

**Dependency rationale:** 两条通道都已存在（`tushare_context.py`、`official_context.py`），本票只加选择规则与留痕，不新增采集能力。

## 实现前核实：这套行为大部分已经存在（2026-09-17）

动手前查了现有取数路径，结论是**本票要的行为基本已在代码里，只是没有任何用例钉住**：

| 票面要求 | 现状 |
|---|---|
| TuShare 优先 | `_refresh_context_sources`（`worker.py:1403`）例行刷新 TuShare 各 family |
| TuShare 没出该期 → 用官方 | 该期缺失即成为缺口，缺口检索的 `official` 适配器（`worker.py:681`）按 `official_family_for_metrics` 取官方页。**官方族恰好就是那 8 项双通道指标** |
| 不中止运行 | 缺口是常态路径，运行照常完成 |
| 按指标按期次 | 缺口本就按指标按期次生成 |
| 留痕交付通道 | `provider` 已区分：TuShare 声明为 `"tushare"`，官方页为 `"国家统计局"`/`"中国人民银行"`（`_validate_source_identity`），且经 `ClaimView` 抵达投影 |

**但 `official_family_for_metrics` 与官方适配器在整个 `tests/` 下零覆盖**——没有任何用例验证过"TuShare 缺该期时官方页真的补上了"。机制存在不等于机制有效。

## 本票因此重定范围

不再是"实现新鲜度回退"，而是**用公开反例把既有行为钉住，并补上它缺的部分**：

1. 公开反例：TuShare 缺某期、官方页有该期 → 运行完成、该指标该期采用官方值、`provider` 显示为官方、其余指标仍为 TuShare 交付。
2. 变异检查：拿掉官方适配器该用例必须变红，证明它真在检验这条路径。
3. 若核实中发现该路径对这 8 项实际上**走不通**（例如 `scope.source_url` 为空导致官方适配器根本不挂载），那才是真正要实现的部分——届时如实记录并实现。

## 核实结果：对 7 项确实走不通

缺口的 `source_url` 来自目录的 `source_candidates`（`full_retrieval.py:545`），而官方适配器只在 `scope.source_url is not None` 时挂载（`worker.py:688`）。逐项查过官方族 21 项：

| | 数量 | 指标 |
|---|---|---|
| 有官方候选 URL，回退路径**活的** | 14 | `CN_CAPACITY_UTILIZATION`、`CN_CORE_CPI`、`CN_FINISHED_GOODS_INVENTORY`、`CN_INDUSTRIAL_FINANCE`、`CN_INDUSTRIAL_VA`、`CN_INVENTORY_TURNOVER`、`CN_LOAN_STRUCTURE`、`CN_OMO_7D_AMOUNT`、`CN_OMO_7D_RATE`、`CN_RRR_EVENT`、`CN_SF_COMPONENTS`、`CN_SF_TOTAL`、`CN_TOOL_LIQUIDITY_MONTHLY`、`CN_USDCNY_CENTRAL_PARITY` |
| 无候选 URL，回退路径**死的** | **7** | `CN_CPI_HEADLINE`、`CN_GDP`、`CN_M1_M2`、`CN_PMI_ACTIVITY`、`CN_PMI_INVENTORY`、`CN_PMI_PRICES`、`CN_PPI` |

**这 7 项恰好就是双通道 8 项去掉 `CN_SF_TOTAL` 的全部。** 原因不难理解：正因为 TuShare 覆盖了它们，当初没人给它们配官方候选 URL。而用户新定的规则要求 TuShare 缺该期时回退到官方页——**回退不了**，缺口里没有 URL，官方适配器根本不挂载。

`source_candidates` 对这 7 项的当前值是指标 id 本身，那是 `_SOURCE_CODES.get(metric_id, (metric_id,))` 的默认回退值，**不是任何人选定的来源**。

## 因此本票要实现的

给这 7 项补上官方候选 URL，使回退路径真正连通；并用公开反例钉住"TuShare 缺该期 → 官方页补上 → 运行完成且 `provider` 显示官方"。

**候选 URL 必须是实际可达、可解析的官方页**，不能凭印象填——票13 的有界抓取已经证明我编造路径会 404。因此本票实现顺序是：先按冻结参数探测这 7 项的官方页（与[票27 的探测](27-metric-identity-corrections.md)同批做），取到再配。取不到的项如实记为"回退路径仍不通"，不伪造。

## 待设计的可观察行为

- 触发条件是**新鲜度**：上游有没有该指标该期次的行。**不是数值比对**——不需要容差，也不需要区分修订差异与真实错误。
- 回退粒度是**按指标、按期次**。**不中止运行**；同一次运行里其他指标照常走 TuShare。
- 每个采用点可查到**交付通道**。采集回执已逐次记录渠道，本票要让它在投影与报告里读得出来。
- 两条通道都是官方级，采用点的**认证身份不因通道而变**；变的只是交付通道。
- 官方页当次也取不到时，按既有规则处理（必需阻断 / 可选降级），**不因回退机制而改变原有失败语义**。

## 验收条件

- [ ] 公开反例：TuShare 缺该期、官方页有，运行完成且该指标采用官方值，其余指标仍为 TuShare 交付。
- [ ] 公开反例：两条通道都缺该期时，失败分类与本票之前一致，不被回退机制吞掉。
- [ ] 投影与报告可按指标按期次查到交付通道；变异检查证明去掉留痕会失败。
- [ ] 回退不改变认证身份：同一指标两条通道交付的点，`certification_status` 相同。

## 解读已确认（2026-09-17）

用户先答"对账不一致：阻断则以官方数据为准"，后答"更新不及时用官方数据"，经逐条摆出三种可能行为后确认取**甲**：**该指标该期改用官方值，运行照常 `completed`，投影正常发布**。"阻断"指阻断 TuShare 那一版的采用，不是让运行停在 `action_required`。

被否决的两种及理由：

- **乙（整个运行停在 `action_required`）**：TuShare 滞后一天是常态而非异常，任一指标滞后都会让当日运行停摆，且停摆不解决问题——数据仍要等，人工介入也只是按下继续。
- **丙（只阻断该指标、该点记缺失）**：主动丢弃一个已经拿得到的官方值，既没用上数据也没提醒人，比甲乙都差。

## 范围边界：只做新鲜度，不做数值不一致

本票**只处理"TuShare 尚未发布该期"**。"TuShare 出了值但与官方对不上"是另一条规则，本票不覆盖。用户 2026-09-17 两次答复指的都是更新不及时，且数值不一致目前**没有任何实例**——为没见过的情况先定规则多半会定错。日后出现实例再单独立票。

采用官方值后 TuShare 补出不同值的情形，由 [ADR-0006](../../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md) 的不可变 vintage 承担：修订另存版本，旧判断不被追改。

## 未核实

TuShare 令牌积分等级、各官方页当前可达性。实现第一步应先核实。
