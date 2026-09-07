# 票14增量：Treasury 2Y/10Y 官方日表与时间边界

研究于2026-09-07完成，执行解释器为 `C:\Python313\python.exe -B`。C盘空间耗尽、WSL已停止，本次没有调用WSL、账户API、密钥或数据库，只在指定D盘目录保存研究材料。此文补充[研究14](research-14.md)，不修改旧报告、应用、认证、目录或模型。

**结论：2Y/10Y的官方身份、单位、统计日和公开CSV交付均已取得可核验依据；来源时区明确为美国东部时间，但历史逐日真实公开时间仍未知。** 本次3次官方GET全部200；2026年CSV与既有官方HTML的171日、342个字段逐项一致。这是同一发布者的格式与快照对照，不是两家独立来源认证，也不代表120个中国交易日点时重放通过。

## 1. 真实来源与字段协议

本次直接GET的CSV地址由既有[官方日表原件](evidence-14/54a2b1462c7a2116201b45eaf2dfdfe8fe3654cfd62fe46b6c2c09439c252330)中的下载链接取得；没有猜测账户接口。使用 `type=daily_treasury_yield_curve`，身份为名义固定期限 Treasury par/CMT 曲线，不能接成实际单只债券收益率、实际利率/TIPS、贴现率、零息曲线或长期收益率平均值。[官方日表](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve)

| 项目指标 | CSV字段 | 已有HTML语义绑定 | 规范含义 |
|---|---|---|---|
| `UST2Y_NOMINAL_YIELD` | `2 Yr` | `headers=view-field-bc-2year-table-column` | 2年名义固定期限par收益率，`percent` |
| `UST10Y_NOMINAL_YIELD` | `10 Yr` | `headers=view-field-bc-10year-table-column` | 10年名义固定期限par收益率，`percent` |
| 两项统计日 | `Date`，`MM/DD/YYYY` | `headers=view-field-tdr-date-table-column` | 来源交易日，规范为`business_day`，期始=期末；不是中国报告日或取得日 |

官方FAQ说明CMT是曲线固定期限读值，不必等于某只债券；收益率是半年度付息证券的简单年化 bond-equivalent yield，不含APY复利换算。数值4.37应保存为4.37%，不能当0.0437%或437bp。FAQ另说明实际天数/365或366计日基础。[官方FAQ](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rates-frequently-asked-questions)

CSV有15个字段，按字段名定位；原始行按日期倒序。HTML有26列，混有其他曲线/票据展示用的`N/A`列，不能以第2个收益率列或全表第N个数字抽取2Y。完整表头、全部逐日对照、原件回执和源码快照在[解析检查](evidence-14-treasury-followup/source-inspection.json)。本次未读取XML，不声明XML字段或时间属性已验证。

## 2. 已取得的数据及缺值边界

| 核对项 | 实测结果 |
|---|---|
| 日期覆盖 | 2026-01-02至2026-09-04，共171日，无重复日期 |
| 2026-03-09至09-04 | 127个来源交易日，不等于120个中国交易日 |
| 2Y、10Y值分类 | 各171个正数；各0个零、负数、空值或特殊标记 |
| CSV与旧HTML | 日期集合相同；342/342字段值相同 |
| 2026-08-28 | 2Y=4.34%，10Y=4.73%，差39.00bp |
| 2026-09-04 | 2Y=4.37%，10Y=4.78%，差41.00bp |

数据依据为[2026年官方CSV](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv)；本地保存[原始CSV字节](evidence-14-treasury-followup/a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5)。用十进制计算`(10Y%-2Y%)*100`得到bp，避免展示浮点尾数；只能在相同统计日、相容版本、相同as-of模式的父项之间计算。

官方日表的名义CMT说明明确：允许负收益率对应的报价进入拟合，但**公布的名义CMT曲线以零为下限**。因此0是此来源协议可解释的值，不能被`value>0`过滤；本次2026样本没有零，不声称已经实际取得零值样本。负值若出现在这套名义发布序列应保留原件并触发身份/数据异常核验，不能静默夹成0；也不能把实际收益率的负值规则搬来。`N/A`、空格和缺日期不得变成0或前值填充。[官方名义CMT说明](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve)

## 3. 统计日、来源时区与真实公开时间

方法页标明说明修订日期为2025-02-18，输入是NY Fed取得的指示性买方报价，不是实际成交；每日约15:30是报价采样。官方另明确收益率通常于交易日18:00美国东部时间前可用，但系统等问题可能延迟。18:00属于通常的可用预期，不能充当固定真实发布点。[官方方法](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)

| 元数据 | 本次能证明什么 | 不能据此写入什么 |
|---|---|---|
| `Date=09/04/2026` | 09-04来源交易日收益率 | 09-04任何固定公开时刻 |
| HTML`time datetime=2026-09-04T12:00:00Z` | 日期单元格编码的时间属性 | 12:00Z真实发布 |
| 约15:30采样 | 市场报价输入的采样惯例 | `release_at=15:30` |
| 通常18:00前、可延迟 | 发布预期使用Eastern Time | `public_available_at=18:00`，或无可靠发布日期时倒填次日00:00 |
| 方法/FAQ的2026-08-26 HTTP Last-Modified | 当前文档响应的修改元数据 | 2026每条行情的首次发布时间 |
| 本次CSV接收2026-09-07 06:37:53.830242 UTC | 当前公开响应已由本研究取得的时刻 | 历史逐日首次公开时间、过去生产系统取得时间 |

将官方Eastern Time实施为`America/New_York`是合理的工程映射，须处理夏令时，不能全年硬编码UTC-5；官方没有在本次原文使用IANA标识。**本批年度CSV没有可赋予每一行的可靠原始发布日期或时刻，逐日`release_at`和`public_available_at`保持null。** 已知来源时区不能弥补缺失发布日期。未来若取得明确批次发布日期，可按既定规则记录该批次边界，但仍不能冒充原始历史逐日发布。研究GET只能证明本次取到的快照；正式接入必须记录自己的取得与校验完成时钟。

这与[双点时ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)一致：公开与系统点时分别表达；后来取得/认证不能回填历史SYSTEM。此处不为保证日历、美国假期或延迟容忍阈值冻结新规则。127行只证明来源数据覆盖，历史PUBLIC证据仍须另验。

## 4. 当前实现与旧库证据的准确边界

本次读取的[TuShare上下文适配器](../../src/pring_cycle/tushare_context.py)567–599行仍调用`us_tycr`，请求`date,y2,y10`，分别映射2Y/10Y，单位`percent`。`_daily_scalar`以来源日建立`business_day`，`ContextScalar`公开时间默认null；`_number`接受有限数，0和负数均能通过通用数字检查。这里是已有TuShare解析路径，不能写成“财政部CSV已经接入”。对`src`搜索`BC_2YEAR|daily_treasury_yield_curve|home.treasury.gov`未发现正式Treasury HTML/CSV适配器；这是本次源码快照结果，后续实施可能改变。

[worker](../../src/pring_cycle/worker.py)1438行已有`treasury_yields`任务；[上下文投影](../../src/pring_cycle/context_projection.py)737–769行在认证父项共同日期中取最新一期，使用`multiplier=100.0`与`basis_points`派生利差。当前投影还携带两父项取得状态，不能继续沿用研究14中“尚未展示取得原因”的旧缺陷作为未复核现状。检查文件的字节SHA和相关行已收入[源码快照](evidence-14-treasury-followup/source-inspection.json)，未运行或修改代码。

[旧研究样本对照](evidence-14/sample-comparison.json)在2026-09-06旧仓库读取边界下证明08-28两项2/2相符；旧读取最新08-28、旧历史SYSTEM为0。**本次没有数据库查询**，不能将那次快照描述成现在生产库的最新状态，也不能把旧认证标签当本候选版本认证。

## 5. 可审阅的接入反例与剩余门槛

| 正常/反例 | 应有结果 |
|---|---|
| 名义CSV，09-04两列4.37/4.78 | 按字段名解析两项；待认证候选可保留来源、原件、取得及校验时间；同日可验证41.00bp算术 |
| CSV列顺序改变但字段名唯一完整 | 仍按`Date`,`2 Yr`,`10 Yr`绑定，结果相同 |
| HTML26列中11个其他产品`N/A`字段 | 不令正确2Y/10Y失效，也不压缩单元格后错位 |
| 2Y缺值、10Y有效 | 明确保留字段缺口；不以0、昨天2Y或3Y替代；不派生当天利差 |
| 重复日期冲突、重复目标列、行字段数与表头不一致 | 保存原件并拒绝含歧义输入；不得覆盖、截断后默默入库 |
| `type=daily_treasury_real_yield_curve`、长期均值、票据贴现或单券报价 | 拒绝替代该名义2Y/10Y身份，即便出现相似标题或数字 |
| 名义0、负数、`N/A` | 0按源定义保留；负数触发核验；`N/A`保持缺值；本表只定义后续验收，不声称这些反例已经跑过代码测试 |
| 09-04行附12:00Z/15:30/通常18:00 | 行公开时间保持未知，禁止固定发布点和历史回填 |
| 中国09-04报告，父项仅有09-03美国日 | 显示实际期次；按相同as-of可见证据选择，不把未来美国09-04行倒灌 |
| 新CSV与旧版本同日值变化 | 建立修订/冲突证据，不覆盖原件或旧报告；不能用今天快照证明过去值未修订 |

接下来可在现有授权范围内实现官方公开CSV候选采集，绑定序列/字段/单位/日期及原件回执，补正常与拒绝反例，并在环境恢复后执行正式测试。候选仍须来源认证、许可/用途记录的实际适用核查和新不可变目录接续；公开GET本身不授认证，本次也没有发现或论证额外账户许可门槛。

对于已有TuShare路径，可用这批官方样本支撑家族语义复核，但[ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)明确规定的是P1的官方抽样政策，不能据此自动给P2认证。逐条历史双源不在本次范围；仍需处理实际公开时间证据、源日历/鲜度规则、父项同日可见性以及120个中国交易日的实际重放结果。P2缺口继续透明显示且不投正式阶段票，不将全部可选数据完整设成核心/P1硬门。

## 6. 精确交付与复算

本次3次官方GET、3次HTTP200、0次失败、0次截断；共3份新原件173,051字节，其中方法/FAQ各1份、数据CSV1份，不能把文档请求成功率写成模型可用补齐率。另1次web搜索仅用于发现官方方法说明，不混入直接GET分母；旧错误Treasury URL没有重复请求。没有Tavily/Exa调用、新认证、生产导入或模型采纳。

| 原件 | 精确字节数 | SHA256 | 收到时间UTC |
|---|---:|---|---|
| 方法说明 | 77037 | `f0043d5ea80ea54730c5b5ed5a8c8f105341afff6ed5edcc29f45a4ad039b23e` | 2026-09-07T06:37:51.601374+00:00 |
| FAQ | 82053 | `221d19478530d793b08c7b74b3e3f7eafe157c6f0cb67b388fcf2480388a31d1` | 2026-09-07T06:37:52.713434+00:00 |
| 2026 CSV | 13961 | `a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5` | 2026-09-07T06:37:53.830242+00:00 |

URL、起止时间、状态、响应头、精确字节SHA在[逐次回执](evidence-14-treasury-followup/receipts.json)。既有HTML1120481字节在原目录复用且独立SHA核对；新旧4份原件共1,293,532字节。没有改写旧原件、旧正文或任何旧校验文档。

[精确交付文件列表](evidence-14-treasury-followup/delivery-files.txt)与[校验结果](evidence-14-treasury-followup/delivery-verification.json)列出本次新增路径和文件摘要；列表及校验文件按自身引用规则不把自哈希循环写入自身。可在项目根目录用Windows PowerShell复核所有新原件，无须WSL、第三方包或C盘临时文件：

```powershell
$treasuryEvidence = 'D:\cursor\datasourceRF\.scratch\pring-data-acquisition-repair\evidence-14-treasury-followup'
$treasuryReceipts = Get-Content -LiteralPath (Join-Path $treasuryEvidence 'receipts.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($treasuryReceipt in $treasuryReceipts) {
    $treasuryRaw = Join-Path $treasuryEvidence $treasuryReceipt.local_file
    if ((Get-Item -LiteralPath $treasuryRaw).Length -ne $treasuryReceipt.bytes) { throw 'Treasury byte length mismatch' }
    if ((Get-FileHash -LiteralPath $treasuryRaw -Algorithm SHA256).Hash.ToLowerInvariant() -ne $treasuryReceipt.sha256) { throw 'Treasury SHA256 mismatch' }
}
$treasuryManifest = Get-Content -LiteralPath (Join-Path $treasuryEvidence 'delivery-verification.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($treasuryEntry in $treasuryManifest.files) {
    $treasuryFile = Join-Path 'D:\cursor\datasourceRF' $treasuryEntry.path
    if ((Get-Item -LiteralPath $treasuryFile).Length -ne $treasuryEntry.bytes) { throw 'Delivery byte length mismatch' }
    if ((Get-FileHash -LiteralPath $treasuryFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $treasuryEntry.sha256) { throw 'Delivery SHA256 mismatch' }
}
'Treasury raw and delivery hashes verified'
```

CSV复算无需安装库：按`csv.DictReader`读取`Date/2 Yr/10 Yr`，日期按`%m/%d/%Y`转换，对值使用`decimal.Decimal`；与HTML的明确`headers`标识配对后比较。逐日171条输入值、342个比较布尔值和两份日期集合一致检查已完整保存在`source-inspection.json`。[独立校验脚本](evidence-14-treasury-followup/verify_delivery.py)重新解析两份原件并核对派生检查、旧报告SHA、交付文件SHA与本报告本地链接；默认只读，无生产应用导入和网络调用：

```powershell
C:/Python313/python.exe -B D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-14-treasury-followup/verify_delivery.py
```
