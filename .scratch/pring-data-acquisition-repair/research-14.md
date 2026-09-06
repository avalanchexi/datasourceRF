# 票14：13项P2来源、取得条件与可用状态补证

研究日期：2026-09-07（Asia/Shanghai）；公开 GET 实际取得区间为 2026-09-06 16:57–17:07 UTC，逐次精确时间见回执。执行边界：research 后台独立子任务，只读现有公开查询、官方页面及源码，只写本报告和 `evidence-14/`。未读取账户密钥、调用账户 API、注册/采购、导入生产证据、授予认证或切换模型。

**结论：13项均已完成来源与取得条件分类，但不能把“分类完整”写成“数据全部可用”。** 公开渠道已经取得 GDP、中间价、EIA、美国财政部、VIX、SOX 的真实样本；COMEX、LBMA、在岸16:30、FXCM仍有实际行情或权利证明缺件。旧库GDP存在可复现的季度/累计口径冲突；P2投影不能区分未授权、未接入、未发布与待认证，且旧美债值按10自然日阈值仍被显示为当前。本报告提供票14实施输入，不自行关闭票14。

## 1. 核查入口与结果边界

输入是[规格](spec.md)、[票14](issues/14-p2-availability.md)、冻结审查 `metric-inventory.json`、既有官方原件和当前源码。旧活动模型读取结果为 `model-v0011-a734bb6e7dcf415f`，查询固定 `metric-catalog-v0003`。新目录/新认证状态应另验，不能把旧目录中的 `certified` 当新候选目录通过。

调用 `EvidenceRepository.metric_series`，同时检查 PUBLIC/SYSTEM 2026-08-28 23:59:59+08:00，以及研究时刻 SYSTEM；当前诊断目标日是2026-09-04。`build_context_projection(..., persist_derived=False)` 未写派生数据。完整读结果在[只读矩阵](evidence-14/p2-read-matrix.json)，可读汇总在[逐项分类](evidence-14/availability-matrix.json)。

| 指标组 | PUBLIC 截至08-28点数 | SYSTEM截至08-28点数 | SYSTEM研究时点点数 | 解释 |
|---|---:|---:|---:|---|
| CN_GDP | 88 | 0 | 88 | 8维度、11个期次；最新2026-06-30，当前8行中6行冲突 |
| UST10Y_NOMINAL_YIELD | 169 | 0 | 170 | 当前最新仍08-28；点数不是请求数/原件数 |
| UST2Y_NOMINAL_YIELD | 169 | 0 | 170 | 与10Y相同查询边界 |
| 其余9项直接指标 | 0 | 0 | 0 | 都显示 `awaiting_source_certification`，原因未细分 |
| UST_2S10S_SPREAD | 0 | 0 | 0 | 查询直接序列为0；本次只读投影现场派生39bp，不应误报“无法计算” |

PUBLIC非零、历史SYSTEM为零意味着旧证据是后来取得，不能倒填系统历史。PUBLIC筛选使用旧证据元数据，**本表本身不重新证明其历史公开时间正确**。

## 2. 13项逐项清单

“未核验账户/许可”与“已证实用户没有许可”不同。本次未读取密钥或合同；以下条件说明来源机制，生产权利仍需显式记录。确已限制且不取得的P2，可交付诚实缺口状态。

| 指标 | 真实身份、字段/单位 | 公开/受限与当前接入 | 已取得与剩余 |
|---|---|---|---|
| `CN_GDP` | NBS国内生产总值；`nominal_ytd_level`亿元与`real_quarter_yoy`%分开；total/primary/secondary/tertiary | NBS公开原文；TuShare `cn_gdp` 账户/600积分。两种解析及worker已存在 | 官方原件和纯解析可用；旧库4.7等累计同比进入单季字段，见第3节；不能继续按同义字段认证 |
| `CN_USDCNY_CENTRAL_PARITY` | PBC授权CFETS公布的美元人民币中间价，1 USD 对应CNY数 | PBC公开公告；已有 `pbc_usdcny_central_parity` 解析器和可选家族，旧目录没有观测 | 09-04=6.7787，原件和现有纯解析一致。取得-校验-来源认证-候选目录采纳仍待主流程实施 |
| `CN_USDCNH_FXCM` | `USDCNH.FXCM`离岸CNH报价；bid/ask分开，CNH/USD，GMT日线 | TuShare `fx_daily`公开文档、账户至少2000积分；未核验实时权限；代码中未见具体FXCM适配器 | 只取得字段文档及其示例，无当前原始行情；目录`index_points`错误，bid/ask或mid计算、日线边界未冻结 |
| `CN_USDCNY_CLOSE_1630` | CFETS在岸USD/CNY16:30即期收盘价，CNY/USD | 市场数据权利条件需证明；未核验项目授权；未见具体适配器 | 政策文件证实16:30制度仍保留，未取得真实日值；目录`scalar`是占位单位；不能用中间价/FXCM替代 |
| `COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT` | COMEX GC交易所active month结算，USD/金衡盎司，带实际合约月/roll版本 | 官网午夜CT后可公开查看；实时/历史文件有各自账户、许可/费用条件；无具体适配器 | 本地3个公开GET均403，无实际结算价原件；web工具读取官方说明仅补身份。仍缺真实合约价、完整历史映射和对应交付权利 |
| `LBMA_GOLD_PRICE_PM_USD_OZT` | IBA管理的LBMA Gold Price PM，USD/金衡盎司，伦敦未分配金基准 | 官方明确历史表迁移MyLBMA，须相关IBA许可；没有核验现有许可，无具体适配器 | 已取得许可/拍卖时间说明，无PM基准数值原件。保留受限来源缺口，不用AM或XAUUSD替代 |
| `EIA_BRENT_RBRTE` | Europe Brent Spot Price FOB，RBRTE日频，USD/barrel | 官方历史HTML公开可读；项目EIA API适配器/worker存在但需要key，当前key未检查 | 取得9967条数值，最新09-01=96.02；公开HTML接入协议、字段认证和批次公开时间需实施；旧目录0点 |
| `EIA_WTI_RWTC` | Cushing OK WTI Spot Price FOB，RWTC日频，USD/barrel | 同上；不是期货主力/连续合约 | 取得10236条数值，最新09-01=91.48；旧目录0点；公开HTML不是现有API认证的自动替代 |
| `UST10Y_NOMINAL_YIELD` | Treasury nominal par/CMT 10 Yr收益率，% | 官方HTML/CSV/XML公开；已有TuShare `us_tycr.y10`适配器、worker及旧认证 | 08-28=4.73与官方一致；官方09-04=4.78；历史首次公开时间尚未逐期证明 |
| `UST2Y_NOMINAL_YIELD` | Treasury nominal par/CMT 2 Yr收益率，% | 同上，`us_tycr.y2` | 08-28=4.34与官方一致；官方09-04=4.37；不能把报价采样15:30当发布时间 |
| `UST_2S10S_SPREAD` | 同期 `(10Y%-2Y%)*100`，bp | 既有上下文派生，需两父项同模式、日期和有效版本 | 08-28=39.00bp，09-04官方父项可算41.00bp；子项不能比任一父项更早可见 |
| `CBOE_VIX_INDEX` | Cboe VIX指数日收盘点位，CSV `CLOSE`；区别VXO、VIX期货 | 官方CSV公开下载；网站条款限制使用/存储/衍生用途，不能视为生产用途自动获准；未见具体适配器 | 9266行，09-04收盘14.53；无逐日发布时间；完成当前实际用途的权限判断及认证后才可用于正式上下文 |
| `NASDAQ_SOX_INDEX` | Nasdaq PHLX Semiconductor，SOX点位；保留精确指数版本 | 方法/概要公开；完整分类页面提示登录；历史feed/再利用权限未核验；未见具体适配器 | 概要09-04=11735.26；无完整历史原件。方法证实收盘可修订到17:15 ET，不能以16:00为最终值 |

对应官方入口：[GDP原表](https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html)、[TuShare GDP字段](https://tushare.pro/document/2?doc_id=227)、[TuShare FXCM日线](https://tushare.pro/document/2?doc_id=179)、[PBC中间价公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026090409004494582/index.html)、[PBC外汇交易时段文件](https://www.pbc.gov.cn/chubanwu/114566/114579/4533165/4834545/2023033009003384902.pdf)、[CFETS数据服务说明](https://www.chinamoney.com.cn/chinese/dssjfwgl/)。

其余入口：[CME交付FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)、[GC结算修订](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/06/ser-9637r.pdf)、[LBMA基准说明](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices)、[EIA Brent日表](https://www.eia.gov/dnav/pet/hist/RBRTED.htm)、[EIA WTI日表](https://www.eia.gov/dnav/pet/hist/RWTCD.htm)、[EIA使用说明](https://www.eia.gov/about/copyrights_reuse.php)、[Treasury日曲线](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve)、[VIX日表](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv)、[Cboe用途条款](https://www.cboe.com/terms)、[SOX概要](https://indexes.nasdaq.com/Index/Overview/sox)、[SOX方法](https://indexes.nasdaq.com/docs/methodology_SOX.pdf)、[SOX完整分类登录提示](https://indexes.nasdaq.com/Index/Breakdown/SOX)。本段为来源索引；精确取得时间与原件SHA在第7节索引。

## 3. GDP：已确定的样本口径冲突

[独立对照程序](evidence-14/compare_samples.py)直接读NBS原始HTML表的“二季度/上半年”列，再与公开仓库查询到的声明对照，不调用TuShare账户。结果在[可复算样本](evidence-14/sample-comparison.json)。

| 2026Q2实质同比 | 官方单季 | 官方累计 | 旧TuShare声明 | 当前映射 |
|---|---:|---:|---:|---|
| 总量 | 4.3% | 4.7% | 4.7% | real_quarter_yoy |
| 第一产业 | 3.7% | 3.7% | 3.7% | real_quarter_yoy |
| 第二产业 | 3.0% | 3.9% | 3.9% | real_quarter_yoy |
| 第三产业 | 5.1% | 5.2% | 5.2% | real_quarter_yoy |

该样本的四个TuShare同比全部匹配官方累计列；三个与单季列不同。第一产业同值不构成证明“两个字段同义”。`tushare_context.py:gdp`将这些字段统一构造为单季期次，当前投影因此出现三行同比冲突。TuShare自己的doc227却把`gdp_yoy`描述为当季；**当前字段文档、交付样本、NBS列不能同时视为相符**。本次可以确定该版本样本没有通过单季口径验收，不能仅凭一条样本断定TuShare所有年代永远为累计，也不能擅自修改官方指标定义。

另外三个名义累计产业值是精度差异：31521.8/31522、250472.9/250473、413709.2/413709亿元，差-0.2/-0.1/+0.2亿元；四舍五入为整数后相符，但项目按当前严格比较产生冲突。应在来源认证规范明确原始精度、官方展示精度与容差依据，保留两份原值；不能用统一大容差掩盖同比口径错误。名义总量695704亿元一致，可单独验收。

NBS原文和纯解析的实际发布日期为2026-07-16 09:30+08。当前旧TuShare声明另有08-31取得/公开元数据；不得将整批数据回填到Q2期末或按无证据时间重写旧声明。GDP不投正式阶段票，但名义GDP是P1信用脉冲分母；修复不能把“P2可选”误解成可删除信用脉冲所需有效分母。[NBS表及核算说明](https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html)

## 4. 实际原文与时间边界

- **中间价**：官方2026-09-04公告正文6.7787，页面实际09:25:17；URL中的09:00与HTTP Last-Modified 09:25:27均不能代替正文发布时刻。PBC汇编PDF第16页（文件页序）载明CFETS9:15中间价和16:30收盘价制度不变，但不能回填该PBC页面为9:15。现有生产纯解析已经得到正确字段、单位、维度和09:25:17；[纯解析结果](evidence-14/pure-parser-results.json)中的`acquisition_ids=[]`也明确这只是解析，没有取得链路/认证。[公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/2026090409004494582/index.html)
- **Treasury**：官方表是固定期限名义par yield曲线，2 Yr/10 Yr列均以%表示；15:30 ET是报价采样时间，不是逐日网页发布记录。表内`<time datetime=...12:00Z>`是日期格式化元数据，不能当中午发布。当前原件覆盖2026-01-02至09-04共171日，03-09至09-04有127日；08-28两字段2/2对照一致。网站当前页面更新不能证实每个历史日首次公开时间。[Treasury说明](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve)
- **EIA**：本批页标明Release Date=09-02、Next Release Date=09-10，两个序列最新数值均到09-01；不能因为报告目标09-04就把09-02至09-04视为下载失败。可靠发布日期只支持本批快照的日期精度，采用既定保守日期规则前还需固定源时区；不能授予整条历史曲线的原始发布时间。HTML注释09:11:32和HTTP Last-Modified只作生成/修改元数据。历史表中空值、`-`、`NA`、`W`不能变成0或股票交易日填充。EIA官方允许其数据再利用并要求标来源日期，同时保留第三方受保护材料例外；只读研究GET不是已完成项目API认证。[Brent](https://www.eia.gov/dnav/pet/hist/RBRTED.htm)、[WTI](https://www.eia.gov/dnav/pet/hist/RWTCD.htm)、[使用说明](https://www.eia.gov/about/copyrights_reuse.php)
- **VIX**：CSV到09-04，`CLOSE=14.53`，08-28为14.43；9266个不重复日期。CSV的Last-Modified=09-05 19:00:50 GMT只证明当前文件元数据，不能给9266日逐日设定发布时间。03-09至09-04有129行，不代表中国120交易日点时重放已通过。Cboe公共网页给的是日收盘历史，不能混入VXO或VIX期货结算。[历史入口](https://www.cboe.com/tradable_products/vix/vix_historical_data)、[CSV](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv)
- **SOX**：概要仅能取得当次展示的DATA AS OF09-04和11735.26，没有完整历史交付。方法PDF第4页明确17:15 ET之前可修订收盘、发布持续到17:16 ET；应保留来源版本与修订，页面业务日期不是实际发布时间。完整分类页提示注册登录，不能将该限制推演成“一切SOX页面都需付费”。[方法](https://indexes.nasdaq.com/docs/methodology_SOX.pdf)、[概要](https://indexes.nasdaq.com/Index/Overview/sox)
- **黄金两项**：GC的active month结算窗口与具体交付渠道的公开时间分开；2026生效方法包含10月合约，不能沿用旧五个月主链。LBMA PM是15:00伦敦拍卖开始，拍卖结束/正式发布另有时刻。两个指标都需使用IANA时区处理美英夏令时，不能按中国同一自然日填进15:00报告。本次没有两项实际基准/结算数值，不能作认证或120日覆盖证明。[GC方法](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2026/06/ser-9637r.pdf)、[交付FAQ](https://www.cmegroup.com/articles/faqs/access-to-cme-group-settlement-data-faq.html)、[LBMA](https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices)

所有新的SYSTEM可用时间必须来自正式取得且校验完成的真实过程。研究原件取得时间保留在回执，未来主流程不能把本次本地复制/研究解析冒充过去的生产采集完成时间。

## 5. 需要根代理实施的具体缺陷

源码读快照含精确SHA、行号与片段，见[源码证据](evidence-14/code-evidence.json)，避免并行工作改行号后无法复现。

| 触发及证据 | 当前结果 | 应有验收行为 |
|---|---|---|
| `context_projection._gap_row`/`_evidence_status`，9项零观测 | 一律待认证；目录未认证优先于很多其他原因 | 来源接入/授权状态、最近尝试结果、证据认证、发布时间和鲜度分开保存，投影给可解释主状态及原因；不能凭零观测推断“用户未授权” |
| `worker._refresh_context_sources`缺少EIA key分支 | 无key时跳过；未留该条件的显式取得尝试状态 | 若实际运行确认缺key，记录缺少接入条件；来源公开HTML可读与当前API无key并列，不谎报API HTTP失败。本研究没查key，不能先写“缺key”为事实 |
| 同函数EIA失败分支已有source_failed/adapter_failed/validation_failed | 记录尝试，但上下文缺口展示不消费其根因 | 用同一公开运行边界核对“最近失败 + 旧有效值”的期次、原因与可用状态；旧有效值保留，失败不是0 |
| `_release_status`仅处理LPR | P2没有EIA批次、美国/英国市场发布日历 | EIA未到本批发布日期、境外尚未收盘/定盘应与失败分开；仅在可靠日历或样本证明时标未发布，不能用日历虚构实际release_at |
| 美债当前投影08-28，官方已09-04；`_evidence_status`按10自然日 | 研究日仍current；39.00000000000006bp | 显示真实期次、落后于已发布期次的原因；在明确源日历/发布日期后判断陈旧。bp适当格式化为39.00但保留计算精度；不要在未冻结规则下改所有日频阈值 |
| GDP同一季度6/8冲突；第3节 | 错口径和四舍五入冲突混在一起 | 分别修来源字段语义与精度依据；用官方3行不同同比作反例；不可通过放宽容差令4.7等于4.3 |
| `catalog`里FXCM单位index_points、16:30单位scalar | 身份占位，后续可产生错误解释 | 新不可变定义修正确单位/报价方向；FXCM bid/ask/mid选择要明确，未决定保持不可采纳；不原地改旧模型定义 |
| `retrieval.run_retrieval_cascade`按P2不添加ai_websearch；`_international_context`角色为context_only_never_formal_stage | 现有保护成立 | 状态修复后继续保持P2不投阶段票、不进AI WebSearch，不把所有P2完整设为核心/P1硬门；Tavily/Exa未在本研究调用 |

必须通过的正常/缺口例：中间价真实6.7787与发布09:25:17正常呈现；LBMA无已核验许可时显示缺口；CME本次403显示“本次公开请求失败”，不能据403断言收费/无许可；EIA尚未下一批发布保留09-01值；有旧值但最近来源失败保留期次；GDP冲突不输出无证据的季度同比解释。测试在正式任务公共边界使用隔离transport/时钟，不以本研究样本“导入为certified”代替认证流程。

## 6. 120交易日与下一步缺件

公开表的本地日期窗口03-09至09-04：Treasury127日、VIX129日、Brent122日、WTI123日。它们属于各自源日历，不等于中国120交易日。计算程序保留周内空单元格位置，Brent最后96.02是09-01而非把周一空格压缩后误映射08-31。

当前可直接推进：GDP源字段冲突处理；中间价通过既有正式取得接口形成可追溯候选；EIA公开HTML渠道适配与期次/单位/发布批次契约；Treasury家族官方抽样认证及当前期次补齐；P2状态投影与展示反例。VIX、SOX先明确本项目实际使用的许可/来源契约再生产接入；本研究的公开读取不替项目做许可决定。

仍然缺少：FXCM实际交付与报价选择；CFETS16:30真实数值和允许的交付条件；GC实际合约链/结算原件及其交付时间；LBMA许可及PM原件；SOX完整历史及最终收盘修订版本；VIX生产用途证明；跨境发布时区、假期/修订及历史首次公开证据。不能为了清空P2把这些条件转成“认证通过”。公开日期未知保留未知，SYSTEM历史不可回填。受限P2明确暂缺不阻止票14完成“状态透明呈现”，但仍需完成代码与正常/缺口验证。

## 7. 原件、分母、复算与精确交付

[HTTP回执](evidence-14/receipts.json)：21次实际公开GET，17次HTTP200（80.95%），1次404、3次403。404来自本研究Treasury URL拼写错误，已纠正后成功，不能据此判断正确官方端点损坏。三次CME请求得到相同602字节JSON拒绝体，按3次失败保留分母、按1份原件去重；不当PDF或有效行情。17个200中包括文档、条款、页面、CSV，不是“17次模型补齐成功”。本研究新认证数、生产入库数、模型采纳数均为0；Tavily/Exa调用数0，不能提供这两者检索命中率。

NBS既有原件复制1份，独立SHA验证；其原取得时间来自只读仓库声明（2026-08-31 07:34:55.848496+00:00），复制时间只在[imports](evidence-14/imports.json)中记载，不充作GET。[本地失败说明](evidence-14/local-attempts.json)保留一次CAS路径输入失败和最初GDP期次`2026Q2`格式错误；正确期次`2026-Q2`后纯解析成功。它们不是网络失败，也不证明来源失效。

web工具补读CME FAQ、红线PDF和SOX历史界面，另尝试PDF截图，见[独立工具读取说明](evidence-14/web-tool-notes.json)。这些是研究转述，没有原HTTP字节/hash，不混入21次GET统计；本地CME原件仍明确只有拒绝体。截图调用未产生本地可核验图像，未把它列入交付。

复算命令（项目根目录；只写本票证据目录）：

```powershell
C:/Python313/python.exe .scratch/pring-data-acquisition-repair/evidence-14/compare_samples.py
C:/Python313/python.exe .scratch/pring-data-acquisition-repair/evidence-14/verify_delivery.py
```

原始字节以SHA256命名；每个URL、状态、准确字节数、取得时间、文件hash和失败原件映射见[原件索引](evidence-14/raw-index.md)及[校验结果](evidence-14/delivery-verification.json)。[精确交付路径](evidence-14/delivery-files.txt)列出全部纳入文件；`.gitignore`排除`__pycache__/`与`*-run.txt`，临时文件留存，没有删除。报告及脚本是研究产物；原件与派生文本区分，原文SHA不用于证明尚未建立的来源认证。
