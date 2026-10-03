建议借鉴旧项目的**分层展示和逐项解释**，不要搬用其“置信度”公式。当前项目的“确认度”应定义为：**已确定的正式阶段，其典型经济叙事获得多少宏观与库存证据支持**。它不能表示“阶段正确的概率”，也不能参与阶段选择。

本次仅检索、阅读本地文件；未修改文件、未联网、未执行项目程序或测试。下文“旧”指 `datasource`，“新”指 `datasourceRF`；代码缺陷判断均为静态读码结论。

**1．旧项目三层框架的实际计算**

找到了与问题完全对应的样例：**2026-08-19**，基本面 **46.1/60**、货币宽松度 **41.2/100**、最终阶段Ⅴ、置信度 **71%**。报告和原始结果吻合。[旧报告:103](/mnt/d/cursor/datasource/reports/2026-08-19-背景扫描120.md:103)、[旧结果:37](/mnt/d/cursor/datasource/data/runs/20260819/pring_result.json:37)

`AI报告生成标准流程_V3.3.md` 只提供三层执行流程及样例；其中“五个宏观指标”“含 MLF 的货币层”并不是现存代码的完整评分清单。旧项目自己的优化历史索引也明确要求以实现代码为准。[旧流程文档:238](/mnt/d/cursor/datasource/docs/AI报告生成标准流程_V3.3.md:238)、[旧优化历史:7](/mnt/d/cursor/datasource/docs/archive/pring_optimization_history.md:7)

**Layer 1：基本面分，不是真正的库存量模型。**

公式为 `Σ 指标权重 × 分段乘数`，满分60。下表条件按从左到右判断；所有指标缺失均给该项权重的 **50%**。

| 指标 | 权重 | 阈值 → 乘数 | 样例贡献 |
|---|---:|---|---:|
| PPI同比 | 10 | ≥0.5→1；≥−1→0.7；其余→0.3 | 3.5% →10 |
| CPI同比 | 5 | [0,3]→1；[−0.5,0)或(3,5]→0.6；其余→0.3 | 0.5% →5 |
| PMI综合 | 10 | ≥50.5→1；≥50→0.85；≥48→0.55；其余→0.25 | 49.5 →5.5 |
| PMI新订单 | 10 | 同上 | 48.5 →5.5 |
| PMI生产 | 5 | 同上 | 49.9 →2.75 |
| 工业增加值同比 | 8 | ≥5.5→1；≥4.5→0.8；≥3.5→0.6；其余→0.3 | 4.5% →6.4 |
| 工业营收同比 | 5 | ≥5→1；≥0→0.6；其余→0.3 | 6.5% →5 |
| GDP同比 | 5 | ≥5.5→1；≥5→0.8；≥4→0.6；其余→0.3 | 5% →4 |
| BDI点位 | 2 | ≥2000→1；≥1500→0.7；≥1000→0.5；其余→0.3 | 2815 →2 |

权重见[旧 analyzer.py:659](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:659)，分段函数见[旧 scoring.py:6](/mnt/d/cursor/datasource/src/datasource/calculators/pring/scoring.py:6)。

样例未逐项显示取整前的和为：

`10＋5＋5.5＋5.5＋2.75＋6.4＋5＋4＋2＝46.15`

代码最后 `round(...,1)`，该次结果保存为 **46.1**。逐项显示也各自保留一位，因此不要把报告展示值相加来复算总分。[旧结果:40](/mnt/d/cursor/datasource/data/runs/20260819/pring_result.json:40)、[旧 analyzer.py:674](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:674)

库存阶段完全由总分切档：

| 总分 | 库存标签 | 商品偏向 |
|---|---|---|
| ≥45 | 主动补库存 | 强牛 |
| [35,45) | 被动补库存 | 偏牛 |
| [25,35) | 主动去库存 | 中性 |
| <25 | 被动去库存 | 熊 |

**没有使用产成品存货、原材料库存、库存周转等实际库存指标。** 这更接近“景气水平评分贴上库存标签”。[旧 analyzer.py:688](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:688)

**Layer 2：货币宽松度。**

同样是分段加分，满分100；缺失仍给50%权重。变化量以下用百分点表示。

| 指标 | 权重 | 阈值 → 乘数 | 样例贡献 |
|---|---:|---|---:|
| RRR变化 | 20 | ≤−0.5→1；≤−0.25→0.8；<0→0.6；=0→0.4；>0→0.2 | 0 →8 |
| 7天逆回购利率变化 | 15 | ≤−0.15→1；≤−0.05→0.75；<0.02→0.45；其余→0.25 | 0 →6.75 |
| DR007变化 | 15 | ≤−0.2→1；≤−0.1→0.8；≤0.05→0.5；≤0.15→0.35；其余→0.15 | +0.2 →2.25 |
| TSF增速 | 20 | ≥10→1；≥8→0.8；≥6→0.5；其余→0.2 | 7.42% →10 |
| M2增速 | 15 | ≥10→1；≥8→0.8；≥6→0.55；其余→0.3 | 7.7% →8.25 |
| M1增速 | 10 | ≥8→1；≥5→0.75；≥3→0.5；其余→0.25 | 4% →5 |
| M1−M2增速差 | 5 | ≥1→1；≥0→0.7；≥−1→0.45；其余→0.2 | −3.7 →1 |

因此：

`8＋6.75＋2.25＋10＋8.25＋5＋1＝41.25 → 保存41.2`

分档为 **≥60宽松、[30,60)中性、<30收紧**。MLF虽被读取、出现在方法说明中，**不在实际七项计分表中**。[旧 analyzer.py:475](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:475)、[旧 scoring.py:79](/mnt/d/cursor/datasource/src/datasource/calculators/pring/scoring.py:79)、[旧结果:59](/mnt/d/cursor/datasource/data/runs/20260819/pring_result.json:59)

利率变化优先取 `change_from_120d`；RRR也优先取该字段，而评分说明却写“年内累计降准”，存在窗口叙述不一致。[旧 analyzer.py:342](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:342)、[旧 analyzer.py:583](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:583)

**Layer 3：有五段处理，并非只做一次资产映射。**

| 顺序 | 实际规则 | 置信度处理 |
|---|---|---|
| ① 三资产映射 | 六种典型组合映射Ⅰ—Ⅵ | 精确匹配固定90%；近似匹配为`0.9×匹配分/3`，中性计0.5 |
| ② 一致性约束 | Ⅲ非主动补库降Ⅱ；Ⅳ遇收紧或非主动补库降级；与宏观阶段差≥2再改阶段 | 分支扣5或10个百分点，可叠加 |
| ③ 阶段加权融合 | 库存阶段序号×0.35＋货币阶段序号×0.35＋资产阶段序号×0.30，四舍五入 | 若改阶段，扣5个百分点 |
| ④ 领先指标平移 | 宽松向前一档、收紧向后一档，边界截断、不循环 | 实际平移扣2.5或4个百分点 |
| ⑤ 货币修正 | 现存函数保持阶段，只改分 | 按规则加减，最后截到[0,1] |

代码调用顺序见[旧 analyzer.py:1604](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1604)。

其中：

- 宏观阶段由先行、同步、滞后三组方向映射；精确匹配90%，否则选平方距离最近者，`max(0.3,0.9−0.2×距离)`。方向来自**指标水平阈值**及DR007变化，不全是时间趋势。[旧 analyzer.py:1331](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1331)
- 库存映射为：主动补→Ⅲ，被动补→Ⅱ，被动去→Ⅴ，主动去→Ⅵ；货币映射为宽松→Ⅱ、中性→Ⅲ、收紧→Ⅴ。[旧 analyzer.py:1414](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1414)
- 最后的货币加减分：宽松对Ⅱ/Ⅲ/Ⅳ加10点；对Ⅴ，补库加5点、去库扣10点。收紧对Ⅱ/Ⅲ/Ⅳ扣15点；对Ⅰ加10点；对Ⅴ且主动补库加5点。中性不调。[旧 analyzer.py:1163](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1163)

**71%的完整复算：**

该日资产是“债看多、股中性、商品中性”，宏观阶段为Ⅳ。[旧结果:5](/mnt/d/cursor/datasource/data/runs/20260819/pring_result.json:5)

1. 代码先把“是否Bullish”转布尔，两个Neutral变成False，命中Ⅰ：**90%**。
2. 与宏观Ⅳ相差3，执行一致性修正：Ⅰ→Ⅴ，**80%**。
3. 库存Ⅲ、货币Ⅲ、资产Ⅴ融合：`3×.35＋3×.35＋5×.30＝3.6`，取Ⅳ，**75%**。
4. 领先指标收紧，Ⅳ→Ⅴ，扣4点：**71%**。
5. 货币中性，不再调整。

即 **90%−10%−5%−4%=71%**，不是由46.1与41.2加权得到。

报告显示“基础Ⅴ→最终Ⅴ”，因为保存的 `base_stage` 已经过前四段处理；它只展示最后一次货币修正前后。[旧 analyzer.py:1210](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1210)、[旧 analyzer.py:1252](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1252)、[旧 analyzer.py:1760](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1760)

**DR007“阶段可能向后1档”的真实规则：**

- DR007较120日前变化≤−15bp为宽松、≥+15bp为收紧；15—25bp信号强度0.45，达到25bp为0.60。
- M1−M2≥+0.5个百分点为宽松，≤−0.5为收紧；绝对值达到1时强度由0.40升至0.55。
- 两者反向：`conflict/flat`，不平移；同向则取最大强度再加0.15，上限0.75。
- 有方向就执行±1档；实际平移时，DR变化绝对值≥20bp扣4点，否则扣2.5点。
- `lead_days=35`直接写死；DR原始值不可得时还可能采用逆回购字段。
- 注释说“仅在方向冲突时调整”，**代码没有对应冲突条件**。
- “可能向后1档”的文字优先读取 `applied_shift`，所以它实际上可能描述**已经发生的平移**，容易让人误解为下一次预测。

出处：[旧 analyzer.py:141](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:141)、[旧 analyzer.py:164](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:164)、[旧 analyzer.py:269](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:269)、[旧 summaries.py:20](/mnt/d/cursor/datasource/src/datasource/calculators/pring/summaries.py:20)。

**资产信号与配置的来源：**

- **债券**：CN10Y收益率120日变化，缺失退到5日；下降看多、上升看空、持平或缺值中性。[旧 analyzer.py:1035](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1035)
- **股票**：预载沪深300 `trend_score`，≥60看多、<20看空，其余中性。不是旧说明中“A股＋港股70%、美股30%”的组合。[旧 analyzer.py:1060](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1060)
- **商品**：WTI、Brent、铜、黄金、GSG有效技术评分平均，再计算`技术分×35%＋基本面分×65%`；≥70看多、≤30看空，其余中性。技术分满分40，基本面满分60。[旧 analyzer.py:120](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:120)、[旧 analyzer.py:718](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:718)
- **关注资产、配置文字、仓位区间**：按最终阶段查硬编码模板，未见组合优化计算。[旧 stage_allocations.py:6](/mnt/d/cursor/datasource/src/datasource/calculators/pring/stage_allocations.py:6)

| 阶段 | 模板关注资产 | 债／股／商品／现金仓位区间 |
|---|---|---|
| Ⅰ | 长久期国债、政策利率债、货币基金 | 55–65／20–30／5–10／10–15% |
| Ⅱ | 高β股票、宽基、长久期国债 | 40–50／30–40／10–15／5–10% |
| Ⅲ | 权益指数、工业金属ETF、资源股 | 25–35／45–55／15–20／5–10% |
| Ⅳ | 能源资源股、原油及商品ETF | 20–30／35–45／20–30／5–10% |
| Ⅴ | 贵金属、能源商品指数、抗通胀资产 | 10–20／25–35／35–45／10–15% |
| Ⅵ | 短久期国债/政策金融债、现金、黄金 | 35–45／15–25／5–10／15–25% |

这些是旧项目模板，不是本次投资建议。

**2．旧项目有没有逐阶段宏观／库存／货币预期表？**

**有显式宏观六阶段表，但没有找到一张统一、无矛盾的“阶段×库存四象限×货币状态”正式预期表。**

显式宏观表如下，且已进入 `determine_macro_stage`：

| 阶段 | 先行：信用/M2/利率 | 同步：PMI/工增/GDP | 滞后：PPI/CPI | 文档叙事 |
|---|---|---|---|---|
| Ⅰ | ↑ | ↓ | ↓ | 衰退末、政策开始发力 |
| Ⅱ | ↑ | ↑ | ↓ | 复苏、通胀仍低 |
| Ⅲ | ↑ | ↑ | ↑ | 扩张、通胀抬头、政策转中性 |
| Ⅳ | ↓ | ↑ | ↑ | 过热、信用减速、政策收紧 |
| Ⅴ | ↓ | ↓ | ↑ | 增长下滑、通胀仍高 |
| Ⅵ | ↓ | ↓ | ↓ | 增长和通胀共同走弱 |

出处：[旧 stage3pring分析优化.md:44](/mnt/d/cursor/datasource/optimization/archive/stage3pring分析优化.md:44)、[旧 analyzer.py:1394](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1394)。

库存相关规则却存在不同版本：

| 库存标签 | 《系统技术文档》的阶段影响 | 现存融合代码的阶段序号 |
|---|---|---|
| 主动补库 | Ⅲ—Ⅳ | Ⅲ |
| 被动补库 | Ⅲ | Ⅱ |
| 主动去库 | Ⅱ | Ⅵ |
| 被动去库 | Ⅰ—Ⅱ | Ⅴ |

出处：[旧系统技术文档:655](/mnt/d/cursor/datasource/docs/系统技术文档.md:655)、[旧 analyzer.py:1414](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1414)。

因此，**“Ⅴ对应主动补库＋货币中性/收紧”不能当作旧项目已有的正式规则**。它可能是某日报的实际组合，也可能来自Ⅴ阶段的货币加分分支；都不等于逐阶段预期定义。旧文档对主动/被动补库的PPI—库存方向甚至互有颠倒。[旧背景扫描方案:207](/mnt/d/cursor/datasource/docs/archive/legacy/120日背景扫描方案.md:207)、[旧技术指标计算说明:277](/mnt/d/cursor/datasource/docs/archive/original_files/技术指标计算说明.md:277)

**3．迁移到当前项目的合理性与验证证据**

**指标大多已有，但身份、统计口径和计算窗口不能照抄。**

当前应按 `model_v0014_manifest` 的有效清单核对。基础目录原有61组；迁移删除两项黄金得到59组，v0013把两项120日广度换成四项90/250日广度，恢复61组；v0014继承并修改信用脉冲、停用12月参考轨道。[新 catalog.py:716](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:716)、[新 models.py:483](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:483)、[新 models.py:510](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:510)

| 旧项目输入 | 当前对应 | 判断 |
|---|---|---|
| PPI、CPI | `CN_PPI`、`CN_CPI_HEADLINE`；另有`CN_CORE_CPI` | 有；区分同比、环比、累计同比 |
| PMI综合/新订单/生产 | `CN_PMI_ACTIVITY`的不同维度 | 有；不是三份独立数据来源 |
| 工业增加值 | `CN_INDUSTRIAL_VA` | 有；当月同比与累计同比分开 |
| 工业营收 | `CN_INDUSTRIAL_FINANCE`的`revenue/official_yoy` | 有；累计口径 |
| GDP同比 | `CN_GDP/real_quarter_yoy` | 有定义；不能拿名义GDP或口径不明的TuShare同比替代 |
| BDI | 无对应指标 | 没有 |
| DR007、逆回购利率 | `CN_DR007`、`CN_OMO_7D_RATE` | 有 |
| RRR | `CN_RRR_EVENT` | 有政策事件；不等同于旧加权平均RRR标量及变化 |
| M1、M2、剪刀差 | `CN_M1_M2`余额/同比；剪刀差可同口径派生 | 有基础输入，无独立剪刀差指标组 |
| 社融增速 | `CN_SF_TOTAL`的`stock_yoy` | 有定义；与增量、存量余额、信用脉冲不同，非每次必有 |
| 单一MLF利率 | 无同名独立指标 | 工具流动性月报不能直接替代 |
| 沪深300 | `CN_EQ_CSI300` | 有辅助指标；正式股票核心是000985 |
| CN10Y收益率代理 | 债券核心000012及辅助债券指标 | 不应替代当前正式债券核心 |
| WTI、Brent | `EIA_WTI_RWTC`、`EIA_BRENT_RBRTE` | 有，但官方现货序列不等于旧期货合约 |
| COMEX铜、GSG/BCOM、黄金 | 无相同有效指标身份；黄金已移除 | 国内商品篮子不能冒充相同序列 |

目录及成员口径：[新 catalog.py:43](/mnt/d/cursor/datasourceRF/src/pring_cycle/catalog.py:43)、[新 metric_contracts.py:144](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:144)、[新 metric_contracts.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:175)。TuShare GDP同比被显式拒绝为“统计期语义未核实”，社融总量`stock_yoy`被排除于必需成员之外。[新 tushare_context.py:1182](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1182)、[新 metric_contracts.py:306](/mnt/d/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:306)

新项目另有旧评分未使用的真实库存、周转、产能、贷款结构、信用脉冲等，**足以构建比旧总分更有解释力的确认层**。但“目录有”不代表某次投影已有有效观测。[新 context_projection.py:55](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:55)

逐项迁移判断：

| 旧做法 | 建议 |
|---|---|
| 分层展示库存、货币、阶段 | 保留展示思路，阶段先算、确认后算 |
| 逐项得分原因与证据 | 保留可解释性，改为支持/反证/未确认 |
| 景气得分推库存阶段 | 不搬；使用当前需求—生产—库存结论 |
| 固定水平阈值及权重 | 不照搬；没有可靠校准证据，且混合水平与趋势 |
| 宏观阶段约束、阶段序号加权 | 禁止；直接违反正式阶段边界 |
| DR007推动阶段±1 | 禁止；最多作为转折观察证据 |
| 90%起分加减 | 不搬；无概率含义 |
| 缺失给50%分 | 不搬；缺失不能产生支持 |
| 静态资产配置权重 | 不纳入确认度；当前研究文档明确产品不输出配置权重 |

最后一项见[新阶段含义研究:5](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:5)；正式边界见[新 CONTEXT.md:7](/mnt/d/cursor/datasourceRF/CONTEXT.md:7)。

**没有找到足以证明旧置信度、阈值和权重有效的统计回测。** 已找到的证据应分开看：

- V4.1“验证通过”验证的是缺数据阻断、完整性阈值和错误输出，**不是阶段准确率或概率校准**；“根据质量调整信心度”仍列待办。[旧V4.1测试报告:9](/mnt/d/cursor/datasource/optimization/archive/V4.1验证测试报告.md:9)、[同文件:196](/mnt/d/cursor/datasource/optimization/archive/V4.1验证测试报告.md:196)、[同文件:262](/mnt/d/cursor/datasource/optimization/archive/V4.1验证测试报告.md:262)
- 优化说明写“依据2025-10至11至少18组样本回测，MR需附对比表”；对应TODO仍未完成真实数据验证、回测权重表。此次未找到该对比表，不能将这句话视为验证已完成。[旧优化说明:420](/mnt/d/cursor/datasource/optimization/archive/stage3pring分析优化.md:420)、[旧Stage3 TODO:44](/mnt/d/cursor/datasource/optimization/archive/stage3_todo.md:44)
- 2026年签名实验室明确写“scale/模板未标定”“仅工程验证”，真实标签评估待办。[旧实验室README:21](/mnt/d/cursor/datasource/optimization/20260705_pring_signature_lab/README.md:21)
- 确有91个月标签验证产物，其中53个月低置信、44个月fallback；这是标签构建诊断，不能证明生产公式71%的校准。[旧标签验证:1](/mnt/d/cursor/datasource/data/pring_stage_labels/2019_2026/validation_report.json:1)、[同文件:59](/mnt/d/cursor/datasource/data/pring_stage_labels/2019_2026/validation_report.json:59)
- Golden测试检查边界乘数和既有结果稳定性，不等于经济有效性验证。[旧测试:20](/mnt/d/cursor/datasource/tests/test_pring_scoring_golden.py:20)

**值得明确记录的旧缺陷：**

1. **商品看多不可达。** 按代码上限，`40×.35＋60×.65＝53<70`，正常计分不可能得到Bullish。[旧 analyzer.py:737](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:737)
2. **Neutral可能被按熊市布尔值直接匹配，仍给90%。** 精确匹配返回发生在中性降分逻辑之前；71%样例正受此影响。[旧 analyzer.py:1265](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1265)
3. **同一信息反复参与。** 库存影响商品信号、阶段约束、阶段融合、货币修正；货币又参与宏观阶段、融合、领先平移。不能理解为独立证据累积。
4. **“支持信号”不是针对当前阶段的支持。** 债看多、股看多被普遍写入支持，即便最终阶段Ⅴ要求债股熊。[旧 analyzer.py:1689](/mnt/d/cursor/datasource/src/datasource/calculators/pring_analyzer.py:1689)
5. **真实复盘确认了价格与建议背离。** 2026-08-04全部股指弱势、均线方向向下，但最终Ⅲ仍建议超配股票，复盘归为模型层面的张力。[旧复盘:60](/mnt/d/cursor/datasource/reports/2026-08-04-复盘与问题.md:60)
6. 根目录 `TODOS.md` 主要记录选择性回滚，明确历史计划/证据不代表当前能力；不能引用旧“已完成”措辞替代现状核验。[旧 TODOS.md:17](/mnt/d/cursor/datasource/TODOS.md:17)

**4．当前宏观／库存字段：取值与实际含义**

所有宏观函数先筛选 `freshness=="current"` 且无来源冲突的证据，但**不会统一排除方向unknown**。[新 macro.py:188](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:188)

| 字段 | 可能取值 | 实际判断 |
|---|---|---|
| `policy_direction` | `easing`、`tightening`、`neutral` | 政策行动与市场传导各自方向唯一，且两组相同 |
| 同上 | `transmission_conflict` | 组内多方向，或两组方向不同 |
| 同上 | `insufficient_data` | 政策行动或传导缺有效证据 |
| `credit_response` | `expanding` | money、social_financing、loan_structure三角色齐全，全部有效方向为上/扩张 |
| 同上 | `contracting` | 三角色齐全，全部为下/收缩 |
| 同上 | `mixed` | 角色齐全，但不满足以上一致方向；含持平、unknown等情况 |
| 同上 | `insufficient_data` | 必需角色不齐 |
| `overheat_state` | `overheated` | 需求、生产、信用角色齐全，至少两个必需角色有`high` |
| 同上 | `heating` | 三个必需角色均有`up` |
| 同上 | `cooling` | 未命中前两项，且存在任一`down` |
| 同上 | `insufficient_data` | 缺必需角色，或其余组合 |
| `price_pressure` | `consumer_diffusion` | 任一消费者价格信号`up`，优先级最高 |
| 同上 | `producer_diffusion` | 无消费者上涨，但有生产者价格`up` |
| 同上 | `upstream_pressure` | 前两项没有，但有上游`up` |
| 同上 | `easing` | 有有效信号，但没有上述任何上涨方向 |
| 同上 | `insufficient_data` | 无有效信号 |

分别见[新 macro.py:49](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:49)、[新 macro.py:73](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:73)、[新 macro.py:95](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:95)、[新 macro.py:120](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:120)。

**这些值不是名称所暗示的完整经济判断：**

- 原始方向中，PMI按**高于/低于50**判断；净投放、释放资金、RRR变化按数值正负；其余一般比较当前值与上一观测。它们不是统一的120日趋势。[新 context_projection.py:1786](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1786)
- 常规 `_raw_direction` 只产生`up/down/flat/unknown`，未产生`high`，所以 **`overheated`虽有领域分支，当前常规投影路径没有触发输入**。
- `heating`只要求各角色出现up，即便同时有down也可能先命中；`cooling`则可能由单项down触发。
- `consumer_diffusion`不要求“上游→生产者→消费者”链条依次成立；只是消费者上涨优先。
- `price_pressure=easing`甚至可能来自只有unknown、没有up的有效信号，不能直接解释为“已证实物价缓解”。
- `support/counterevidence`目前主要按向上/向下分类。对阶段Ⅰ或Ⅵ，向下反而可能支持典型叙事，**不能直接拿这些数组长度计确认度**。

`inventory.directions`含三轴：

| 轴 | 来源 | 常规投影可能取值 |
|---|---|---|
| `demand` | 过热组中demand角色，目前是`CN_PMI_ACTIVITY`各成员 | `up/down/conflict/null` |
| `production` | 工增、产能、工业财务等production角色 | 同上 |
| `inventory` | 优先实际产成品库存，其次周转，再其次PMI库存 | 同上 |

组内先去除unknown和flat；剩一个方向就采用，多个方向为conflict，没有则null。库存优先角色若得conflict，直接返回，不继续降级选择。[新 context_projection.py:63](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:63)、[新 context_projection.py:1914](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1914)

`quadrant`严格对应：

| demand | production | inventory | quadrant |
|---|---|---|---|
| down | down | down | `active_destocking` 主动去库 |
| up | up | down | `passive_destocking` 被动去库 |
| up | up | up | `active_restocking` 主动补库 |
| down | down | up | `passive_restocking` 被动补库 |
| 其他组合 | | | `null` |

因此，**库存四象限为空既可能因缺失，也可能因需求与生产分化，不等于库存数据全无**。[新 macro.py:141](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:141)

另一个易错点：库存特征卡`status="support"`目前表示存在current证据，不表示支持当前Pring阶段；不能直接作为确认票。[新 macro.py:168](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:168)

**5．“确认度”的建议设计**

**输入与计算位置。**

由模型在正式阶段确定后，对同一投影截止点的五个维度评估：

`政策方向、信用响应、过热状态、物价压力、库存状态`

输入还应包含这些结论的证据、统计期、可用时间、新鲜度、缺口、冲突与模型版本。库存`directions`用于解释`quadrant`及未成象限原因，**不再额外算三票**。不要按61个指标逐一投票，也不要把宏观组内重复使用的M1/M2、信用脉冲、PMI当作独立证据。

模型输出确认结果，Worker保存进同一不可变投影集合，首页只读。这符合当前投影边界。[新 CONTEXT.md:45](/mnt/d/cursor/datasourceRF/CONTEXT.md:45)

**预期表的形状应是“六阶段×五维度”，每格不止一个字符串。**

每格至少保存：

`支持状态集合／反证状态集合／未确认状态及原因／是否仅观察／叙事说明`

不要把“不在支持集合里”一律算反证；政策中性、信用mixed、库存分化等可能只是尚未确认。预期规则应随模型版本冻结。

下面是**供拍板的初稿，不是已有实现或已验证规律**：

| 阶段 | 政策典型预期 | 信用典型预期 | 需求压力 | 物价 | 库存典型预期 |
|---|---|---|---|---|---|
| Ⅰ | 宽松 | 收缩或传导未恢复 | cooling | easing | 主动去库；被动累库压力仍可能存在 |
| Ⅱ | 宽松 | 转向expanding | 转向heating | easing | 被动去库；订单先改善、生产滞后应保留分化 |
| Ⅲ | 宽松/中性 | expanding | heating | upstream/producer | 主动补库 |
| Ⅳ | 中性/收紧 | 仍可expanding，边际减速另看 | heating；过热需补充分层 | producer/consumer | 主动补库，后段可能转被动累库 |
| Ⅴ | 中性/收紧 | contracting或结构恶化 | cooling | producer/consumer压力仍在 | 被动补库；主动补库只作过渡观察 |
| Ⅵ | 建议先仅观察，可能开始宽松 | contracting | cooling | easing | 主动去库；被动累库向去库过渡 |

该初稿更接近当前项目已写明的“典型但非必要环境”：Ⅰ政策可能转松但信用弱；Ⅳ信用量仍高；Ⅴ主动补库转被动累库；Ⅵ政策可能已开始宽松。[新阶段含义研究:82](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:82)、[同文件:147](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:147)、[同文件:168](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:168)、[同文件:194](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:194)

当前研究也明确指出，中国库存/信用与阶段的对应属于待检验假说，不能冒充Pring定义。[新阶段含义研究:23](/mnt/d/cursor/datasourceRF/docs/research/pring-six-stage-meanings.md:23)

**首页优先显示计数，比例作为补充。**

建议首版：

> **宏观与库存确认：支持3项，反证1项，未确认1项**  
> 可评估4/5；已评估项支持率75%。

设支持S、反证C、未确认U：

- 支持率：`S/(S+C)`；分母为0则不显示。
- 可评估覆盖：`(S+C)/(S+C+U)`。
- “仅观察”的维度另列，不进入分母。
- 具体条目必须可展开，显示实际结论、预期、证据和未确认原因。

这样避免“只有一项可用就显示100%确认”的误导。**不建议首版再划高/中/低档**，否则还需引入未经验证的阈值；若必须分档，应同时约束覆盖度，且说明是规则分档。

还需防止自我确认：当前物价组包含正式商品核心NHII。如果只因NHII上涨得到`upstream_pressure`，不能把它当作独立宏观支持再加一票，应披露证据重用，或要求非核心价格证据补充。[新 context_projection.py:70](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:70)

**非典型组合和边界。**

- `current_stage=null`时，确认度应为 **不适用**，保留五维事实；不能计算六阶段分数后选最高者。
- 核心失效、趋势未稳定，也不能借宏观确认度补出阶段。
- 如展示上一确认阶段的对照，必须明确写“相对上一确认阶段的叙事对照”，不能冒充当前确认度。
- 低确认度只说明典型经济叙事未获支持，**不能降低阶段有效性、阻止发布、改写阶段或阶段史**。
- 新发布的低频数据只从可用时点起参与确认，不倒填历史。

这些边界来自[新 CONTEXT.md:11](/mnt/d/cursor/datasourceRF/CONTEXT.md:11)、[新 CONTEXT.md:31](/mnt/d/cursor/datasourceRF/CONTEXT.md:31)、[新 CONTEXT.md:39](/mnt/d/cursor/datasourceRF/CONTEXT.md:39)。

**需要用户拍板的领域判断清单：**

1. 确认度是否明确限定为“典型叙事支持程度”，排除正确概率、预测概率和投资胜率。
2. 是否采用五个维度等权计数；哪些阶段的政策等维度应“仅观察”。
3. Ⅰ允许哪些库存压力状态；Ⅱ如何容纳订单领先生产；Ⅴ是否以被动补库为主要预期；Ⅵ是否接受政策已宽松。
4. `mixed`、传导冲突、库存分化分别算未确认还是反证，不能统一处理。
5. 物价压力描述要判断“仍处高位”还是“正在上升”：当前字段主要表达后者，不能直接检验前者。
6. 是否先修正/细化现有结论语义，特别是`overheated`不可达、unknown可能进入物价easing、同组多统计口径混合的问题。
7. 是否要求独立于核心资产的确认依据，以及如何披露五维之间的证据重叠。
8. 发布初版时是否只展示计数；若要百分比或分档，其分母、覆盖要求和文案须明确冻结。
