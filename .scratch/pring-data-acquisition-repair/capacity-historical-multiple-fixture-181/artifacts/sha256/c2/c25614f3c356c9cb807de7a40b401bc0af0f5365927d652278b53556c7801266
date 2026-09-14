Status: research-resolved
Type: source-mapping-decision
Date: 2026-09-09

# Q1 产能利用率的同区间源映射

**支持落实这一个映射：将 2026 年一季度全国规模以上工业产能利用率的同一官方源格 73.6%，显式映射为 2026-01-01 至 2026-03-31 的 `ytd_rate`。这是同一报告期的来源别名，不是另一个官方累计发布值，也不是新估算公式。** 不需要新增产品选择；需要把映射身份及适用条件冻结、验证并绑定到新的证据/定义版本。本文完成研究判定，没有解除应用守卫、修改旧包或授予认证。

这个结论有明确的推论边界：官方直接给出 Q1 的统计率和报告期定义；Q1 与“年初至一季度末”的区间恒等由日历及现有目标字段定义推出。本次没有找到国家统计局单独规定“Q1 累计率等于当季率”的专门条文，不能把上述推论写成官方原句。旧审计的 **8 个独立字面格 + 1 个语义复用** 分类保持成立；映射完成后可称“8 个直接源格及 1 个显式映射已核对”，不能改称“9 个独立官方累计/当季原字段通过”。[既有逐格审计](p1-capacity-utilization-full-value-audit.md)

## 直接一手证据与确切位置

主证据为[国家统计局 2026 年一季度页面](https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html)的[已保存原件](evidence-a18-import-20260909/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a)。本次重新读取原始字节，长度 **128195**，SHA-256 **`0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a`**，与文件名一致。以下为原始 HTML 物理行，引用文字仅去除标签及排版空白，未改原件。

| 证据位置 | 原文字面/直接事实 | 对映射的约束 |
|---|---|---|
| L8、L332 | 标题及正文限定 2026 年一季度、全国规模以上工业，率为 73.6% | 只能映射该统计总体、该期、该版本，不是所有工业或分行业合成值 |
| L336–344 | 行业列；一季度表头；产能利用率的百分比列；同期增减的百分点列 | 仅两项数值列，无独立累计列；同比点差不可充当累计率 |
| L347–351 | 工业总行；73.6 位于 L348 开始的单元格，字面在 L349；-0.5 在 L351 | 唯一所用源格是第一数值列；不使用后续重复排版表扩大分母 |
| L477，附注“指标解释” | 实际产出对应“企业报告期内的工业总产值”；生产能力也针对报告期，二者以价值量计量并形成比率 | 这是期间比率，不是期末存量，也不是把几个季度百分比相加的量 |
| L477，附注“调查方法及范围” | “本调查按季进行”；该页说明未经季节调整及全国规模以上工业调查合成范围 | 映射保留同一调查结果、总体及未季调属性，不引入另一种累计调查或权重 |
| L11、L277 | meta 与可见栏均为 `2026/04/16 10:00` | 仅是这个保存版本的页面时间字面；不是证明首发及修订历史的第二证据 |

原审计用 L348 标识源单元格，本次精确到 L349 的数值文本，两者指向同一个格。表头和附注已经足以确定本页的率是 Q1 报告期的统计结果。

## 为什么可落成合同，而不是再等一个产品取舍

现有输出合同已要求 `quarter_rate`、`yoy_change`、`ytd_rate` 三个成员，[成员定义](../../src/pring_cycle/metric_contracts.py#L138)没有要求三项必须来自三个独立源格。现有解析器在 Q1 两数值列表下已复用当季率，并将两率的起止日期都落为该年 01-01 至 03-31；[复用位置](../../src/pring_cycle/official_context.py#L1260)、[输出身份](../../src/pring_cycle/official_context.py#L1290)。代码只能证明既有行为，官方期望来自上面的原件，二者不互相代替。

因此可以冻结如下推论：对于同一原件 vintage、同一统计总体和未季调口径，Q1 报告期与年初至 Q1 末是同一时间集合；复用该集合上的同一个已报告比率，不需要再估计分子/分母、确定权重或作数值容差选择。它不推出 Q2 当季等于上半年，也不推出季度率的简单均值等于官方累计率。Q2–Q4 缺累计源列仍必须拒绝，沿用已经修复的[缺列边界](capacity-missing-ytd-boundary.md)。

[业务待决草案](business-decisions-draft.md)涉及估值、广度和商品选月等取舍，没有把该 Q1 源格身份列为产品选项。在用户已经授权继续来源修复的范围内，这个明确且不改变数值/总体/时间的映射可以落实；不需要为它另设审批步骤。

## 可冻结的最小精确映射

以下是本研究中可冻结的映射说明，不要求新增数据结构或给当前规范化 JSON 加研究字段，也不是新的来源认证包。

| 字段 | 固定内容 |
|---|---|
| 规则名称 | `capacity_q1_same_interval_alias_v0001`；含义为同报告期的源字段别名，仅用作本研究规则标识，不要求新增应用字段 |
| 来源 | 国家统计局；`nbs_capacity_utilization`；`NBS_CAPACITY_UTILIZATION_HTML_V1` |
| 本次已审 source vintage | 上述页面 URL、128195 字节、完整 raw SHA；首张逻辑表的 工业 × 一季度 × 产能利用率（%），L348–349 |
| 真实源字段 | `industrial_capacity_utilization_pct`；源成员 `industry=all_industry, measure=quarter_rate`；`quarter` |
| 目标字段 | 保留既有 `industrial_capacity_utilization_ytd_pct` 作为规范字段名；目标成员 `industry=all_industry, measure=ytd_rate`；`year_to_quarter`。明确该名称不是网页额外列名 |
| 统计期间 | 本次源与目标都精确为 `2026-01-01` 至 `2026-03-31`；仅 Q1 可触发，禁止通过改写期次使其他季度进入 |
| 单位与值 | 原字面 `73.6`、`percent`；恒等映射，不缩放、不平均、不外推，不以 `-0.5 percentage_points` 替代 |
| 审查说明 | 同一源格被复用、没有新增独立源格；链接真实源字段/格及本规则版本，不扩展 `ContextScalar` |
| 血缘与时钟 | 与源格绑定同 raw vintage 和实际采集收据；不得新增更早的发布时间或 SYSTEM 可用时间；保留该收据/声明真实时间与修订身份 |
| 版本限制 | 本次仅完成这个已审 2026-Q1 vintage 的映射依据；其他年份或新页面版本须经同样身份/期间/源格检查，不因月份为 3 就自动通过 |

源格缺失、重复冲突、单位/总体/期间不符、raw 或 normalized 损坏、目标值不等于实际源格时，映射失败。若未来官方页同时提供一个独立累计列，应采用且核对实际累计列；与当季冲突时不能由别名规则覆盖它。不要通过删除目标成员、伪造累计列、写一个 `passed:true` 注解，或仅取消错误分支来完成本项。

记录可以放在新的不可变来源映射/审查材料中，以定义版本和完整哈希绑定，并由公开入库及消费边界验证。现有规范输出字段集合与研究注解必须继续分开，旧 normalized 和旧审查字节保留；[A18 的规范对象边界](a18-document-import-readiness.md#L70)仍适用。

## 用现有字段即可追溯，不增加数据结构

现有 [ContextScalar](../../src/pring_cycle/tushare_context.py#L78) 的 `source_field` 是规范字段标识，单靠 `industrial_capacity_utilization_ytd_pct` 不能证明网页有同名累计列。应连同已存在的家族、期次、维度及收据解析契约理解它：

1. 来源声明通过既有 `acquisition_id` 关联收据，`source_reference` 保存官方 URL 加 raw SHA；无需新增一个伪造的来源字段 URL。[现有入库绑定](../../src/pring_cycle/official_context.py#L387)
2. 收据的 `parser_version=official-context-parser-v0004`、`parameters.family=nbs_capacity_utilization`、`parameters.period=2026-Q1`、`parameters.source_url`，以及 raw/normalized 两个 SHA，定位采用的输入及规范结果。单有版本字符串不证明执行字节恒定，执行/审查记录仍须绑定实际源码指纹；本研究已列当前文件 SHA。
3. 公开 [parse_official_acquisition](../../src/pring_cycle/official_context.py#L259) 按收据的 family、period、URL 和真实 received_at 重解析 raw，核对 provider 及完整规范对象 SHA。现有来源消费路径再逐声明匹配；本研究没有代跑这些校验。
4. 对应的 Q1 两数值列表分支精确读取“工业 × 一季度 × 产能利用率（%）”，并在 [L1275–1276](../../src/pring_cycle/official_context.py#L1275) 将同一字面用于当季和累计规范字段。因而 `source_field=industrial_capacity_utilization_ytd_pct` 的真实源格追踪链是：规范标量身份 → 收据/规范哈希 → 固定解析契约及源码 → raw 内上述格。本文件补足该链的语义说明；不用把旁路注解混进旧 normalized。
5. 只补充同值映射依据，不需要给旧收据改 parser 版本或重写旧字节。若后续改变实际解析输出或解析语义，应使用相应新解析版本及新的不可变收据/制品，不能让旧版本标签静默代表另一套规则。新目录采纳该映射的版本变更与整体验证，仍按 ADR0012 处理。

## 真正剩余的缺件

1. **工程落实尚未做。** 当前 [source_contract_review.py:L204–209](../../src/pring_cycle/source_contract_review.py#L204)仍对 Q1 `ytd_rate` 抛 `registered_capacity_q1_mapping_unresolved`。新映射需要绑定到新版本，并以真实这份原件通过公开解析/入库/查询及错源格、错期间、缺列负例验证后，才能将这个特定源映射缺口记为已落实。本研究不运行这些步骤。
2. **时间与来源认证仍独立。** 原件页头时间不证明历史内容在该时刻首发且未被修订；本次读取不补造早期获取事实。现有 A18 document_import 的真实收据即使已验证，也只证明该次导入。不得把语义映射成功升级为历史 PUBLIC、来源认证、120 日候选通过或模型激活。[ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)、[ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)
3. **本项不再以“必须找到另一个 Q1 累计源格”作为缺件。** 若目标就是同一 Jan–Mar 期间率，上述显式别名已经给出可审依据；若今后要求另一个独立官方累计发布系列，那才是不同的需求，本研究并未证明它存在。

## 有界查询记录与未采用证据

仅执行三次 `stats.gov.cn` 限域搜索，没有账户 API、应用、SQL、测试、WSL 命令或原件改写，也未额外下载页面/附件。搜索返回结果由浏览工具提供，未形成新的本地原件或获取收据。

| 次数 | 查询 | 结果及用途 |
|---|---|---|
| 1 | `site:stats.gov.cn 产能利用率 "累计" "一季度"` | 返回[2019 年二季度公告](https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900369.html)等：当季率与上半年累计率分别报告。没有发现 Q1 专门等式条文；历史结果不作 2026 原格依据 |
| 2 | `site:stats.gov.cn "产能利用率" "计算" "季度" "累计"` | 返回[2020 年三季度公告](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202010/t20201019_1794679.html)等，其报告期比率及按季调查说明与本次原件一致。没有发现另一套 Q1 累计调查算法；不能把没有搜到当成不存在的证明 |
| 3 | `site:stats.gov.cn "累计" "年初至" "报告期"` | 返回拆船、社保及 GDP 等其他制度。它们不能决定产能利用率的源映射，未作为支持证据采用；达到预算后停止搜索 |

结论主要依赖已经完整保存并重新验哈希的 2026-Q1 原件及明确的区间恒等推论，未把检索摘要或其他指标方法冒充本指标认证材料。

## 本次只读输入指纹

| 输入 | 字节 | SHA-256 |
|---|---:|---|
| `p1-capacity-utilization-full-value-audit.md` | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| `business-decisions-draft.md` | 5314 | `7d17453b12975869eed360d3047d862c562e1e4f697fbe8a97321af6f0919064` |
| `a18-document-import-readiness.md` | 20348 | `3a911f5a1cf84f1b092a1badaae59b10597ff9945ac33b0fef8cff533fff7ff4` |
| `src/pring_cycle/source_contract_review.py` | 14630 | `c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772` |
| `src/pring_cycle/official_context.py` | 84300 | `fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11` |
| `src/pring_cycle/metric_contracts.py` | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |

仅新建本 Markdown，未改旧审计、准备包、业务草案、源码或原件；最终文件字节与 SHA 在交付消息中给出，避免自引用。
