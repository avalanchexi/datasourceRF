# 第 04 票：三核心官方语义与历史公开时间补证

审查日：2026-09-06。固定目标：2026-03-09 至 2026-08-28 的 120 个中国交易日。本文是独立研究证据，不是认证通过记录。只新增本文及 `evidence-04/` 原件、请求回执、复核明细；没有调用账户 API、读取密钥、修改生产数据库、应用、候选模型、目录、认证或切换状态，也没有执行应用测试。

**结果：000985、000012 的官方身份、主要计算语义和目标 120 日当前历史数值得到正向支持；各自另取到 139 个基础公式前置日。NHII 的 2025/2026 成分和方法得到补强，取得 15 个目标日可核验收盘样本，但完整 120 日的历史 PUBLIC 认证仍缺必要证据。不能把本文交付计为第 04 票全部验收通过。**

## 1. 判断边界和可复查产物

依据 [规格](spec.md)、[第 04 票](issues/04-core-public-time-certification.md)、[ADR-0002](../../docs/adr/0002-stable-commodity-core-and-certified-fallback.md)、[ADR-0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)、[ADR-0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md)、[ADR-0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)：保持三核心和 2018-06-01 长期校准边界；NHCI 不替换 NHII；后来取得的历史值、发布者当时公开的值、本系统当时取得并通过校验的值分别处理。来源语义认证、数值质量、PUBLIC 可见性是三个独立条件。没有可靠公开日期就保持空值；只有可靠发布日期时，从下一本地日开始，不补造 15:30。

当前证据入口：

- [请求回执](evidence-04/receipts.json)：每个请求的 URL、请求开始/响应接收 UTC 时间、HTTP 状态、内容长度、SHA-256、本地文件、响应头；失败请求保留实际异常。
- [南华固定批次回执](evidence-04/nh-daily-batch-receipts.json)：113 个归档原件请求及结果，每个请求均有有限超时，没有无限重试。错误中的 `Max retries exceeded` 是传输库异常文字，不表示本研究主动做了无限重试。
- [计算和对账明细](evidence-04/verification-summary.json)：官方日历日期集合、完整性检查、逐系列比较结果、NHII 样本和权重解析。
- [只读数据库比较输入及 SQL](evidence-04/read-only-value-comparison-input.json)：`mode=ro` 查询保存于研究目录，未导出秘密内容。

原件文件名是完整 SHA-256；这是 HTTP 响应内容字节的散列，不能当作压缩传输帧散列。已存在同散列文件只验证内容相同。当前接收时间记录本次取得，不是历史首次公开时间；`Date`、`Last-Modified`、PDF 落款、交易日或指数推出日均不自动转换成历史 `public_available_at`。

## 2. 三核心身份、字段与方法

| 核心 | 官方身份及单位 | 当前交付映射 | 正向证据与尚未支持的范围 |
|---|---|---|---|
| `CN_EQUITY_CORE_000985` | 中证全指指数，官方代码 `000985`；CNY 计价基础的指数点位，基日 2004-12-31、基点 1000，推出日 2011-08-02 | `index_daily(000985.CSI).close` → `index_points` | 官方方法及事实表支持价格表现指数；`H00985` 全收益、`N00985` 净收益是独立衍生代码，不能替换。当前方法和回填历史没有证明 2018 年以来每一个当时可知版本 |
| `CN_BOND_CORE_000012` | 上证国债指数，官方代码 `000012`；指数点位，基日 2002-12-31、基点 100，推出日 2003-01-02 | `index_daily(000012.SH).close` → `index_points` | 官方公式包含全价市值、债券利息及再投资收益，并作月末除数维护；不能描述成净价或完全不含利息的价格指数。它也不是国债到期收益率、CNY030 或中国债券总财富指数 |
| `CN_COMMODITY_CORE_NHII` | 南华工业品指数 `NHII`，南华商品一级分类指数；基日 2004-06-01、基点 1000，商品收益率指数加权链式点位 | `fut_index_daily(NHII.NH).close` → `index_points` | 2025/2026 官方工作簿均实际找到 NHII、20 个非零品种、权重和 1、LH 权重为空。不是 NHCI、单一合约结算价或固定成分篮子；旧历史原始发布版本及全窗口 PUBLIC 时间仍未齐备 |

交付代码定位：[source_adapters.py 第 17 行](../../src/pring_cycle/source_adapters.py#L17)、[第 201–229 行解析](../../src/pring_cycle/source_adapters.py#L201)。上表的官方身份依据分别如下。

### 2.1 000985

中证 [2023 年 12 月 V1.2 方法](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208175438-000985_Index_Methodology_cn.pdf)（[实际 PDF](evidence-04/d6a4d24334f600fe2c80e4f3cbc01cffed931776ec61f7081dffcd72847969d1.pdf)，第 1–2 页）明确代码和基日，样本空间包含沪、深、北交易所符合条件的股票及红筹存托凭证；经上市时间、ST 等规则筛选，按调整市值/除数计算，定期调整及退市等事件有维护规则。不能把“全指”理解为当日所有上市证券无条件等权。

[2026-08-31 事实表](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000985factsheet.pdf)（[实际 PDF](evidence-04/bade84f8672123fd901138eb59563f7af07a179c6b085c3d67b480cdb52d69e3.pdf)，第 1–2 页）列出 5122 个样本、人民币计价、推出日和全收益/净收益衍生代码。推出日是指数身份事实，不是各历史日线的发布时间；事实表日期晚于目标窗口，不能反推此前每一日的当时成分或历史值未曾修订。[官方基本信息](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000985?lang=zh_CN)（[JSON](evidence-04/687e6211137694255502faed2c9d117ed935e0a808de01892d6bef9bf26df495.json)）也未给出逐日发布信息。

### 2.2 000012：需要明确修正旧研究的含息表述

上交所 [000012 编制方案](https://www.sse.com.cn/market/sseindex/indexlist/indexdetails/indexmethods/c1/000012_000012hbook_CN.pdf)（[实际 PDF](evidence-04/209b82e2a207b1ae479d6a6d753fa168899faed3ee65f91857f79d636d5e3ee7.pdf)，第 1–3 页）规定：样本为上交所上市、人民币计价、固定利率、剩余期限超过一年的国债，按发行量加权；取债券实际市场价格，无交易则用最近交易日价格。其指数公式是“样本债券总市值加利息及再投资收益”除以除数再乘 100；总市值使用全价，包含应计利息。样本和发行量变化用除数修正，月末最后交易日另处理当月利息及再投资收益。

这不是本研究新创造的解释：上交所 [2009 市场资料](https://www.sse.com.cn/aboutus/publication/factbook/documents/c/10170573/files/073e042b8b87407b919e3d8e75ee91a5.pdf)（[实际 PDF](evidence-04/c962379b144ace00f189065ce7d1d32ea8f5d7fe47e3e617adc8383a291262c2.pdf)，PDF 第 32 页）已有同类公式并解释当月利息再投资。它支持含息计算并非近期新增，但不能证明整个 2009–2026 期间的全部规则版本、每日首次发布值及发布时间。本文不修改旧冻结文档；后续新认证中的语义标签应准确表述这一公式。

另有元数据冲突：[中证当前基本信息](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000012?lang=zh_CN)（[JSON](evidence-04/4390b7dc8015f4ed85dfeeafde53b7a7b4565ce95064deb5028216343f0fe39b.json)）的通用 `adjFreqCn` 为“每半年”，而上交所具体方案写有新券第二个交易日纳入、月底剔除不合格券及月末利息处理。不要用该通用字段覆盖发行人具体方法。

### 2.3 NHII：权重年度与移仓规则必须按有效期解释

[南华 2025 编制细则](https://www.nanhua.net/cmsbigfile/2025/05/a3eb91a3-d6fc-4d71-b652-d55a60e0b10d/南华商品指数——编制细则(2025).pdf)（[实际 PDF](evidence-04/0f602104fd1b11de0a21995a6ed314591a7b6da7707d23392cc4cc850d73bb00.pdf)，第 3、6–8 页）支持商品主力合约选择、确认后逐步移仓、每年 6 月首个交易日调整权重，以及 NHII 适用的一级分类规则和链式收益率指数公式。概述的 8 日过程与明细的 3 日确认加 5 日分步移仓应一并理解，不能单凭“主力合约”自行拼接未经认证的连续收盘序列。

两份真实工作簿的 NHII 均在 D 列、代码在 D3，B 列为品种代码：

| 工作簿与官方来源 | 本地原件 | 本次实际解析 |
|---|---|---|
| [2025 年权重](https://www.nanhua.net/cmsbigfile/2025/05/5ede4a4d-218d-4fbb-8ffb-e809669b16af/南华商品指数2025年权重调整公告.xlsx) | [acac6c9a… XLSX](evidence-04/acac6c9aaa5906362d54eafff74872a235d96385f6944420e622108b177c4fa6.xlsx) | 工作表 `2025年指数权重图表`，20 个非零品种，合计 1.0000，LH 所在第 35 行 D 列为空。表头名义日期 2025-06-01；按方法的首个交易日规则，实际交易日为 06-03 |
| [2026 年权重](https://www.nanhua.net/cmsbigfile/2026/05/f2db1579-be72-4735-814e-4d4551c5a7bb/南华商品指数2026年权重调整公告.xlsx) | [dad20d28… XLSX](evidence-04/dad20d28d6fd453bced67e60aa65ff77b3cf6fd1f685a5b590939cbaee4054b7.xlsx) | 工作表 `Sheet1`，20 个非零品种，合计 1.0000，LH 所在第 37 行 D 列为空，表头生效日 2026-06-01 |

目标期内有年度换权：2026-06-01 前使用 2025 年方案，此日起适用 2026 年方案；2025 年的 FU、J 在 2026 年非零 NHII 列中不再出现，新增 JM、LC，其他权重也变化。20 个成员与逐项权重已保存于复核 JSON。年度工作簿证明这两次方案，不足以孤立证明不存在临时调整；当前 [公告目录](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=4041&start=0&limit=40)（[27 条原始 JSON](evidence-04/d47699f19517f35a6936f97172219ff0cb78a4dc03f9c6ede2f049a078a7b738.json)）未列出目标期内另一份 NHII 方法变更公告，但不能把“未列出”写成所有渠道均无变更的证明。

[强制移仓规则公告](https://www.nanhua.net/news/2025/05/d8278efd-56d7-475b-881d-acfb9e652405.html)（[HTML 原件](evidence-04/ba31c97fe3816ff248a6e401e15236ab6b1b898c83963e7b442129d25ebc149e.html)）页面明确显示发布时间 2025-05-28 15:20:53，正文规定新强制移仓规则从 **2025-08-15** 起执行。目标 120 日均在此后，但基础公式预热起点 2025-08-06 在此前；不能把一套新移仓规则回推覆盖整个预热段。这不要求重建或替换官方 NHII，而是要求历史方法证据保留有效期边界。

旧 [NHII 历史研究](../../docs/research/nhii-historical-constituents-and-methods.md) 已讨论 2018 年以来方法与成分历史及早期回算局限，本次没有重新下载、逐年认证整条 2018–2024 历史链，也不把旧文中的认证标签提升成新的逐日 PUBLIC 通过结论。

## 3. 交易日、真实数值和精度复核

[上交所 2026 年休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml)（[HTML 原件](evidence-04/11d8a102d0747eaa8e97d9eda71eb9544ce30adbe83c706f7bdc77be4084686b.html)）支持目标期为 120 个交易日：125 个周一至周五日期扣除 04-06、05-01、05-04、05-05、06-19。没有把周末调休作为交易日。补充 [2025 年日历](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml)（[原件](evidence-04/754afc6d12a01013cbadeef55e656aebc4e40aa7ef1cb63792f17dabf9bccdf8.html)）后，2025-08-06 至 2026-08-28 为 259 个交易日。

| 当前官方响应 | 行数 / 日期完整性 | 与现库 TuShare `close` 的比较 |
|---|---|---|
| [000985 目标期](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260309&endDate=20260828&lang=zh_CN) / [原始 JSON](evidence-04/6e849804171177debebc666eabf63388c21066fe695a06f75f6c2cc47043f120.json) | 120 行、120 唯一日期，无缺失、无额外日期 | 120/120 在保留两位小数、十进制 HALF_UP 比较下相同；03-09：6199.43 对 6199.4259；08-28：5935.03 对 5935.0294 |
| [000012 目标期](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012&startDate=20260309&endDate=20260828&lang=zh_CN) / [原始 JSON](evidence-04/a5cc98b01d04c2570ec193eff1fbe89b610e8ec35b3e095b5322636bce17f641.json) | 同上 | 120/120 两位精度相同；03-09：225.87 对 225.8668；08-28：230.11 对 230.1072 |
| [000985 含基础预热](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20250806&endDate=20260828&lang=zh_CN) / [JSON](evidence-04/ffe3b20f7c9a09428bcedd641a358442e7e685c65de55844ac32022fd6b74b2d.json) | 259 行、259 唯一日期，与上述两年官方日历一致 | 259/259 两位精度相同 |
| [000012 含基础预热](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012&startDate=20250806&endDate=20260828&lang=zh_CN) / [JSON](evidence-04/30b9736664d961d6481386433c86ebddb8d7d8171ecd2450ad70da5e8bb49798.json) | 同上 | 259/259 两位精度相同 |

这四次响应包含 `tradeDate,indexCode,indexNameCnAll,open,high,low,close,change,changePct,tradingVol,tradingValue,consNumber,peg`，没有逐观测发布时间或修订版本。两系列比较的最大未舍入绝对差均为 0.005 点；HALF_UP 是本文的公开对账约定，未取得官网自身舍入算法承诺。这证明当前回填值在显示精度内相容，不证明精确四位数相等，不证明历史首次发布版本未变，也不认证无关的 `peg`、成交量/额单位。259 日中的原有各目录版本没有发现同日不同 `close`，但旧版本时间字段不因此恢复可信。

数据库只读 SQL 如下，实际参数、查询时间和返回值在比较输入 JSON：

```sql
SELECT metric_id, period_end, value, count(*) AS n
FROM source_claim
WHERE metric_id IN (?,?,?) AND period_end BETWEEN ? AND ?
GROUP BY metric_id,period_end,value
ORDER BY metric_id,period_end,value;
```

参数是上表三个核心指标 ID、`2025-01-01`、`2026-08-28`。按指标/日期/数值分组，先检查是否存在多种值，没有静默挑一个新版本掩盖冲突；`n` 是历史声明数量，不是独立市场观测数量。

### 3.1 NHII：归档记录、取回成功、内容合格三个分母

[南华日报公开目录](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=404205&start=0&limit=260)（[260 条原始 JSON](evidence-04/fdc2a2c4c696ff176b22d5c85a51e1984f1521dcddc79ba31650a1aaf6c17581.json)）横跨 2025-07-18 至 2026-09-04，完整包围目标期。按标题中的完整日期匹配，只找到目标 120 日中的 **114 个唯一日期**；没有同日重复，也没有标题交易日与 `createTime` 日历日期不一致的记录。明确缺少 **2026-03-26、05-08、05-22、06-09、06-10、07-16** 六日。这里证明的是本次取回的这份官方目录未列出，不是这些日子绝对没有发布过。

114 个记录中，先取回 08-28，再对剩余 113 个固定 URL 请求一次：**16 份 PDF 成功传输、98 个 URL 传输失败**。失败均为 `ProxyError`，代理连接被关闭；不是取得了 HTTP 404，不是解析空表，也不能据此认定许可被拒。对 03-09 PDF 追加一次有界重试仍失败；08-28 独立新闻页两次取回尝试同样失败，全部记录保留。批次回执只保存了截断异常文字，足以识别 `ProxyError` 和目标 URL，不应把截断文字当完整服务端响应。

内容校验又排除一份：目录标题 `南华商品指数日报20260817` 的 `href` 本身实际指向 **20260814 周报**。取回 [官方原件](https://www.nanhua.net/cmsbigfile/2026/08/ecfc24cc-2072-4ceb-9d43-1c6a29d9bbcc/南华商品指数周报20260814：多数上涨，能源领涨.pdf)（[PDF](evidence-04/87d01b4c239555057fbb2af2b38e1fe71d58c955a807ed390d061385b6fe16fb.pdf)、[第 1 页视觉检查](evidence-04/nh-20260817-p1-inspection.png)）共 13 页，首页明确为 2026-08-14 周报。**这不能认证 08-17 日报或 08-17 收盘；不能把标题日期覆盖正文日期。** 08-18 日报的 `Pre.Close` 也不能未经专门前收口径和发布时间处理，就冒充已取得 08-17 日报。

其余 **15 份实际日报**第 1 页 `Index Market Data` 表的 `NHII / Today Close` 与现库相同日期 TuShare 收盘完全相同，单位为点；`Pre.Close`、`Points` 和 `%` 各自保留在明细。这里验证的采纳字段是 `Today Close`，没有把 `Pre.Close` 强制改成数据库前一行收盘，也未将点数变化和收益率强制重算到等式完全一致——原始值存在显示精度差异。逐份 URL、时间、收盘和完整散列见文末表。

### 3.2 收益率字段的可支持程度

[TuShare 指数日线官方文档](https://tushare.pro/document/2?doc_id=95)（[本次 HTML](evidence-04/5f5a4e8a29b483222ee398c896a4221e95b145dc209201f4d596543f00e5c54b.html)）明确 `close/pre_close/change` 为点位，`pct_chg` 为百分数。当前代码对 `index_daily.pct_chg` 除以 100 转比率。

[TuShare 南华日线官方文档](https://tushare.pro/document/2?doc_id=468)（[本次 HTML](evidence-04/d0e5971998ff65e858a24f1307638de4a8ba1434da5bd0851fc009f99d364fc9.html)）列出 `NHII.NH` 与 `close/pre_close` 点位，但 `pct_chg` 仅称涨跌幅，没有明确 `%` 单位，页面示例也未展示该列数值。因此，该页面本身不足以独立证明南华 `pct_chg` 的比率单位。现代码保留原比率、旧账户样本研究曾验证这一差异；本次未作账户请求，也未重新取回目标日 TuShare 原始 `pct_chg` 响应。若这次认证要包含收益率字段，应将已有真实原响应与这 15 份官方 `%` 样本按精度对账，不能只凭函数名或文档标题补造比例认证。

## 4. 实际公开时间：得到什么，缺什么

| 证据 | 可证明 | 不能证明 / 应保留为空 |
|---|---|---|
| CSI 两核心 120 / 259 日 JSON | 当前收到的历史点位及其 `tradeDate` | 每日首次公开时刻、原始历史版本、延迟或后续修訂时刻。`publishDate` 基本信息是推出日，不是 daily 发布时间 |
| NH 日报目录的 `createTime` + 正确日期内容 PDF | 当前官方归档声称文章发布的日期与钟点，15 份日报内容能绑定相同目标日期；可以作为逐件核验的发布日期证据候选 | 未显式给时区/首次发布/修订字段；不能自动证明当前 PDF 字节在 `createTime` 那一秒已存在，也不能据此替全部 114 日补 PUBLIC |
| 当前 HTTP `Date` / 本机 `received_at` | 本次响应和本系统取回的时间记录 | 历史发布时间。`received_at` 还不是应用校验完成后的 `available_at` |
| PDF 的 `Last-Modified` | 当前服务器给出的文件修改元数据 | 历史首次公开时刻，不能代替官方发布事件或修订账本 |
| 方法写实时计算、每秒发布；FTP 有正常发布时限 | 发布频率或服务规范 | 目标日期的实际日终值何时首次可用、当日是否迟发、当前历史值是否修订 |

南华官方 [2026 权重公告页面](https://www.nanhua.net/news/2026/05/f2db1579-be72-4735-814e-4d4551c5a7bb.html)（[HTML](evidence-04/1f3eecdbe960a27ee4130c9dafd5227419f93322a93a17e3f54018852c6c8446.html)）和 [2025 权重公告页面](https://www.nanhua.net/news/2025/05/5ede4a4d-218d-4fbb-8ffb-e809669b16af.html)（[HTML](evidence-04/13c64e98197e1f062525cf2a09f2e46292aecfe4ee1a93ae5d52abb77213aeb6.html)）实际将相应 `createTime` 显示为“发布时间”，分别是 2026-05-25 09:40:31、2025-05-27 19:53:52；强制移仓公告也采用相同显示机制。这比凭交易日臆造发布时刻强，但仍不应把数据库列名机械升级为每份附件的精确首发时间。

具体反例：[08-28 日报](https://www.nanhua.net/cmsbigfile/2026/08/dba8b812-2f80-47ad-b82a-deac81c28417/南华商品指数日报20260828.pdf)（[PDF](evidence-04/f4074c86b04efa7e3cb033e95e8c1aedd0a8ecd91fadcfbdfc503e57b921aaca.pdf)）归档 `createTime=2026-08-28 16:32:33`，而响应 `Last-Modified=2026-08-28 08:33:24 GMT`，按中国本地时区为 16:33:24，晚 51 秒。无论是先创建文章后上传附件还是文件后改，本次都不能判定具体原因；**不得让当前 PDF 在 16:32:33 即被认定可见**。若来源审查接受官方归档日期与正确内容的绑定，仅以可靠发布日期处理，下一本地日 00:00 是符合规格的保守粒度；这仍须新认证明确接受其日期证据和修订不确定性，本文不写入状态，也不声称那 15 日已经 PUBLIC 通过。

已复用并校验旧 CAS 中的中证 [资讯商文件规范 V1.3.22](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260112151836-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6%E6%9C%8D%E5%8A%A1%E8%A7%84%E8%8C%83%EF%BC%88%E8%B5%84%E8%AE%AF%E5%95%86%E4%B8%93%E7%94%A8%EF%BC%89V1.3.22.pdf)（[相同散列 PDF](evidence-04/3c25a8e93c4ca11556148ae64f5460235ee8e99db8dafb04fb9385bb2f9ef59f.pdf)）。第 2 页为正常情况下的分系统服务时限；PDF 第 10–11 页说明 `Vendor/basic`、`YYYYMMDD+系统_perf.txt`、23:00 打包和只保留 3 天的总压缩包。这是可能的官方原始交付路径，不是已取得 120 天历史原始文件的证据；没有读取登录材料或尝试付费/账户服务。**18:00、20:00 或 23:00 均不能伪装成每天实际首次公开时刻。** 本次只是从既存 CAS 校验复制该规范，没有给它编造本次网络接收时间。

## 5. 预热、认证范围及准确缺件

当前 [趋势规则](../../src/pring_cycle/domain/trend.py#L17) 是 `window_days=120,slope_days=20,persistence_days=8`；[公式入口](../../src/pring_cycle/domain/trend.py#L59) 至少需要 140 个点才产生首个 MA/斜率测量。因此，要在 2026-03-09 得到基础测量，需要 139 个前置交易日，从 **2025-08-06** 起；连同目标窗口共 259 日。本次两条 CSI 日线确实取得并核对这一数值范围。

这不是全部状态预热充分性的证明：8 日持续确认还需先前信号；若要求首目标日有机会在初始空状态下完成 8 次测量，至少要从 **2025-07-28** 起提供 147 个截至首目标日的点，而且实际可能因方向不连续仍无稳定状态。稳定状态继承或更长代理指标需遵守模型初始化契约，不得把 139 日当万能的充分前置长度。本次没有下载 07-28 至 08-05 的额外 CSI 原件，也没有执行模型或改变预热规则。

| 系列 / 范围 | 已补正向证据 | 第 04 票仍缺的具体交付 |
|---|---|---|
| 000985 目标 120 日 + 139 基础前置 | 官方方法、事实表、259 个点、目标 120 日独立请求与精度对账 | **全部这些日期**仍缺可绑定数值版本的实际公开日期/时间依据及修订界定。若完整状态预热另需 07-28 起历史，需按实现冻结的最低需求补原件及相应时间依据 |
| 000012 同范围 | 官方含息公式、2009 年同类公式、259 个点与对账 | 同上；新认证语义必须避免旧“纯价格/不含利息”表述。当前方法 PDF 的服务器修改时间不证明所有历史版本生效日 |
| NHII 120 日 | 2025/2026 成分、2025 方法和强制移仓边界；114 条归档记录；15 个正确日报样本 | 六个明确缺目录日期；08-17 错链需真正当天内容；其余 **98 个 URL**当前下载失败（精确列表在批次回执）。这三个不相交集合合计 105 个未取得正确目标日报日，不能给它们填已核验数值/公开日期。仍缺整个最小预热段的正确原件与时间/方法绑定 |
| NHII 15 个已核验日报日 | 官方内容/日期/点位匹配，官方归档提供日期候选 | 精确首发秒、时区声明、当前附件历史修订账本未证；只能在显式接受日粒度证据之后考虑次日本地日 PUBLIC 边界，不能保留旧固定 15:30 |
| 三核心历史与许可 | 当前官方方法可读，现有 ADR 使用边界明确 | 不把公开可下载等同于任意再发布权。南华细则第 8 页限制未授权发布/商业应用；本次未审账户专属合同或全部第三方上游许可，也不推断 TuShare 未列在示例授权渠道中就是未获授权 |

接下来可独立完成的实现是：把这些真实原件与来源解析结果纳入新的不可变证据版本，正确区分未知 PUBLIC 和已取得 SYSTEM；对错误日报、缺日期和未来证据继续拒绝。**实际可公开时间缺件尚在时，应保留第 04 票认证未完成，不能把固定 120 日期平移缩短，也不能用 NHCI、CNY030 或自建新篮子临时补齐。** 本研究不宣称已经通过候选读取入口演示 PUBLIC/SYSTEM 行为；那项是后续应用验收。

## 6. 已取回南华日报逐件清单

下表由实际原件解析结果生成。归档时间保留原字符串；它不是本机取回时间，也未自动认定为附件精确首发时间。所有 15 个有效 `Today Close` 与现库同日期收盘完全一致。完整请求开始/接收时间和 HTTP 元数据在回执，完整文件散列在链接文件名。

| Trade date | Official raw | NHII close (points) | Publisher listing createTime | Received at (UTC) | SHA-256 / local raw |
|---|---|---:|---|---|---|
| 2026-08-07 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/d42b8717-19eb-4cd1-a129-c0b31c0b1041/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260807.pdf) | 3787.53 | 2026-08-07 16:29:53 | 2026-09-06T13:46:02.058540+00:00 | [10ed46fec8b7c7d3d4f84f5672dd97ef65e5d283b398632bb27269df84ca9da6](evidence-04/10ed46fec8b7c7d3d4f84f5672dd97ef65e5d283b398632bb27269df84ca9da6.pdf) |
| 2026-08-10 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/4ed8739d-73fd-4835-b838-e2c0903f5329/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260810.pdf) | 3789.88 | 2026-08-10 16:35:17 | 2026-09-06T13:46:01.193919+00:00 | [633497fb756ddaca2e20538baa854b841b89c6319992a938caee3d623b09d406](evidence-04/633497fb756ddaca2e20538baa854b841b89c6319992a938caee3d623b09d406.pdf) |
| 2026-08-11 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/e5d37f5b-989a-404e-8328-905a36279968/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260811.pdf) | 3862.68 | 2026-08-11 16:42:16 | 2026-09-06T13:46:01.518066+00:00 | [5ae1c614912d626931535047954442ee9839263e22e00c81e0da7069c7d9d89e](evidence-04/5ae1c614912d626931535047954442ee9839263e22e00c81e0da7069c7d9d89e.pdf) |
| 2026-08-12 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/85599134-2e5b-44d2-8242-4b21c3ea439a/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260812.pdf) | 3855.23 | 2026-08-12 16:01:26 | 2026-09-06T13:45:56.367154+00:00 | [d131d1bc3855fa90ae03a4e9890bea76500ccde6f9311bfc4f2aec7982ba15ff](evidence-04/d131d1bc3855fa90ae03a4e9890bea76500ccde6f9311bfc4f2aec7982ba15ff.pdf) |
| 2026-08-13 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/4f305efe-bb9e-4a2a-a24a-813084304cbb/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260813.pdf) | 3847.39 | 2026-08-13 16:19:18 | 2026-09-06T13:45:55.902589+00:00 | [2306c84a648ac8cd21d3d31efe0d5337c633864aab19bf5960314ed6eabefb48](evidence-04/2306c84a648ac8cd21d3d31efe0d5337c633864aab19bf5960314ed6eabefb48.pdf) |
| 2026-08-14 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/b03375e6-980b-47ee-a731-e1e4b910c586/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260814.pdf) | 3861.58 | 2026-08-14 17:03:53 | 2026-09-06T13:45:54.526124+00:00 | [edaef3a9f1112e7ef33c10406ae13ace3bdf8c20de48fbba1d16db6d13b7d61e](evidence-04/edaef3a9f1112e7ef33c10406ae13ace3bdf8c20de48fbba1d16db6d13b7d61e.pdf) |
| 2026-08-17 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/ecfc24cc-2072-4ceb-9d43-1c6a29d9bbcc/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E5%91%A8%E6%8A%A520260814%EF%BC%9A%E5%A4%9A%E6%95%B0%E4%B8%8A%E6%B6%A8%EF%BC%8C%E8%83%BD%E6%BA%90%E9%A2%86%E6%B6%A8.pdf) | REJECT: wrong 2026-08-14 weekly report | 2026-08-17 16:05:23 | 2026-09-06T13:45:55.190116+00:00 | [87d01b4c239555057fbb2af2b38e1fe71d58c955a807ed390d061385b6fe16fb](evidence-04/87d01b4c239555057fbb2af2b38e1fe71d58c955a807ed390d061385b6fe16fb.pdf) |
| 2026-08-18 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/c4a7c6a8-ace5-4664-90f6-6fc431d87f64/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260818.pdf) | 3928.31 | 2026-08-18 16:21:15 | 2026-09-06T13:45:50.376014+00:00 | [132f0b7a0e07532f0f05ec8cecc231b9e6780b633420132870e6b9b850c54904](evidence-04/132f0b7a0e07532f0f05ec8cecc231b9e6780b633420132870e6b9b850c54904.pdf) |
| 2026-08-19 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/e7b8cd58-5db9-432d-9a20-65a35f6371e3/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260819.pdf) | 3913.86 | 2026-08-19 16:32:34 | 2026-09-06T13:45:47.766159+00:00 | [254d8298a153c916fcc898cdb489af62ad1f102d0141000c29bb3c8f78409ab7](evidence-04/254d8298a153c916fcc898cdb489af62ad1f102d0141000c29bb3c8f78409ab7.pdf) |
| 2026-08-20 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/d8abf1d7-f502-4b09-b914-6c29df0a800c/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260820.pdf) | 3923.62 | 2026-08-20 16:54:08 | 2026-09-06T13:45:47.547921+00:00 | [596b080f82a2e7a2e133b79ef9d7faab2a85c805303b2dd89ff179028ec3f256](evidence-04/596b080f82a2e7a2e133b79ef9d7faab2a85c805303b2dd89ff179028ec3f256.pdf) |
| 2026-08-21 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/6f843531-38d9-47f9-adb9-bf4184bc8e5f/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260821.pdf) | 3952.63 | 2026-08-21 16:29:23 | 2026-09-06T13:45:49.237554+00:00 | [a36152be78b9c7e5ebd21e2449d1d50cb7b40bf38d9d02741e1966d947e4c363](evidence-04/a36152be78b9c7e5ebd21e2449d1d50cb7b40bf38d9d02741e1966d947e4c363.pdf) |
| 2026-08-24 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/983370e7-b2e8-4e25-a9e9-c64402742a84/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260824.pdf) | 3961.01 | 2026-08-24 16:06:28 | 2026-09-06T13:45:41.957799+00:00 | [03fe94a71625465fff428430d58bf9078e3f6d8511a408b2bd6dd5e4421ec294](evidence-04/03fe94a71625465fff428430d58bf9078e3f6d8511a408b2bd6dd5e4421ec294.pdf) |
| 2026-08-25 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/fbd50310-7f32-4e14-9d78-6762d3392901/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260825.pdf) | 3942.06 | 2026-08-25 16:19:06 | 2026-09-06T13:45:41.961858+00:00 | [485de594757c5e86577b947c1ceff406f268922deed9b58fe0603fc9674aa147](evidence-04/485de594757c5e86577b947c1ceff406f268922deed9b58fe0603fc9674aa147.pdf) |
| 2026-08-26 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/757bf1f6-9c2b-484e-b0fe-f3a98b1a6ffc/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260826.pdf) | 3890.46 | 2026-08-26 16:04:21 | 2026-09-06T13:45:42.062752+00:00 | [249bfc9a8bec1de69a703baa30aac78bcff06d12649853a786cb2c59c68b9401](evidence-04/249bfc9a8bec1de69a703baa30aac78bcff06d12649853a786cb2c59c68b9401.pdf) |
| 2026-08-27 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/e201b5e9-79b7-46f1-b008-af4d1fa7d806/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260827.pdf) | 3912.04 | 2026-08-27 16:19:01 | 2026-09-06T13:45:42.301974+00:00 | [1775efb81af480034001b0a8ccb4f2e51903c7782ea96cbb7d2eb76a9eea802e](evidence-04/1775efb81af480034001b0a8ccb4f2e51903c7782ea96cbb7d2eb76a9eea802e.pdf) |
| 2026-08-28 | [official PDF](https://www.nanhua.net/cmsbigfile/2026/08/dba8b812-2f80-47ad-b82a-deac81c28417/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260828.pdf) | 3975.49 | 2026-08-28 16:32:33 | 2026-09-06T13:42:59.506288+00:00 | [f4074c86b04efa7e3cb033e95e8c1aedd0a8ecd91fadcfbdfc503e57b921aaca](evidence-04/f4074c86b04efa7e3cb033e95e8c1aedd0a8ecd91fadcfbdfc503e57b921aaca.pdf) |

## 7. 本次网络取回原件索引

下表列成功响应的内容散列、格式和接收时间（UTC）。失败请求在回执原样保留。南华逐日批次见上表及独立批次回执；复用的 CSI 文件规范为既有 CAS 原件，不混入“本次网络取回”计数。

| Receipt name / official URL | HTTP / bytes | Received at (UTC) | SHA-256 / local raw |
|---|---|---|---|
| [csi-000985-120d](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260309&endDate=20260828&lang=zh_CN) | 200 / 43283 | 2026-09-06T13:39:08.879946+00:00 | [6e849804171177debebc666eabf63388c21066fe695a06f75f6c2cc47043f120](evidence-04/6e849804171177debebc666eabf63388c21066fe695a06f75f6c2cc47043f120.json) |
| [csi-000012-120d](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012&startDate=20260309&endDate=20260828&lang=zh_CN) | 200 / 43244 | 2026-09-06T13:39:08.870227+00:00 | [a5cc98b01d04c2570ec193eff1fbe89b610e8ec35b3e095b5322636bce17f641](evidence-04/a5cc98b01d04c2570ec193eff1fbe89b610e8ec35b3e095b5322636bce17f641.json) |
| [csi-000985-method](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208175438-000985_Index_Methodology_cn.pdf) | 200 / 381656 | 2026-09-06T13:39:09.028731+00:00 | [d6a4d24334f600fe2c80e4f3cbc01cffed931776ec61f7081dffcd72847969d1](evidence-04/d6a4d24334f600fe2c80e4f3cbc01cffed931776ec61f7081dffcd72847969d1.pdf) |
| [csi-000985-factsheet](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000985factsheet.pdf) | 200 / 461410 | 2026-09-06T13:39:09.264899+00:00 | [bade84f8672123fd901138eb59563f7af07a179c6b085c3d67b480cdb52d69e3](evidence-04/bade84f8672123fd901138eb59563f7af07a179c6b085c3d67b480cdb52d69e3.pdf) |
| [sse-000012-method](https://www.sse.com.cn/market/sseindex/indexlist/indexdetails/indexmethods/c1/000012_000012hbook_CN.pdf) | 200 / 273067 | 2026-09-06T13:39:09.185246+00:00 | [209b82e2a207b1ae479d6a6d753fa168899faed3ee65f91857f79d636d5e3ee7](evidence-04/209b82e2a207b1ae479d6a6d753fa168899faed3ee65f91857f79d636d5e3ee7.pdf) |
| [nh-2025-weight](https://www.nanhua.net/cmsbigfile/2025/05/5ede4a4d-218d-4fbb-8ffb-e809669b16af/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B02025%E5%B9%B4%E6%9D%83%E9%87%8D%E8%B0%83%E6%95%B4%E5%85%AC%E5%91%8A.xlsx) | 200 / 16581 | 2026-09-06T13:39:11.144480+00:00 | [acac6c9aaa5906362d54eafff74872a235d96385f6944420e622108b177c4fa6](evidence-04/acac6c9aaa5906362d54eafff74872a235d96385f6944420e622108b177c4fa6.xlsx) |
| [nh-2026-weight](https://www.nanhua.net/cmsbigfile/2026/05/f2db1579-be72-4735-814e-4d4551c5a7bb/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B02026%E5%B9%B4%E6%9D%83%E9%87%8D%E8%B0%83%E6%95%B4%E5%85%AC%E5%91%8A.xlsx) | 200 / 17552 | 2026-09-06T13:39:11.351282+00:00 | [dad20d28d6fd453bced67e60aa65ff77b3cf6fd1f685a5b590939cbaee4054b7](evidence-04/dad20d28d6fd453bced67e60aa65ff77b3cf6fd1f685a5b590939cbaee4054b7.xlsx) |
| [nh-2025-method](https://www.nanhua.net/cmsbigfile/2025/05/a3eb91a3-d6fc-4d71-b652-d55a60e0b10d/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E2%80%94%E2%80%94%E7%BC%96%E5%88%B6%E7%BB%86%E5%88%99%282025%29.pdf) | 200 / 384422 | 2026-09-06T13:39:13.720077+00:00 | [0f602104fd1b11de0a21995a6ed314591a7b6da7707d23392cc4cc850d73bb00](evidence-04/0f602104fd1b11de0a21995a6ed314591a7b6da7707d23392cc4cc850d73bb00.pdf) |
| [nh-bulletin](https://www.nanhua.net/subpage/nanhuaIndex/index-bulletin.html) | 200 / 84147 | 2026-09-06T13:39:12.094765+00:00 | [c38fee25d3c593f42a3143a903933ba4ffaff036bb8410361af8e83bd1b3b8e4](evidence-04/c38fee25d3c593f42a3143a903933ba4ffaff036bb8410361af8e83bd1b3b8e4.html) |
| [nh-bulletin-list](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=4041&start=0&limit=40) | 200 / 15836 | 2026-09-06T13:41:21.824628+00:00 | [d47699f19517f35a6936f97172219ff0cb78a4dc03f9c6ede2f049a078a7b738](evidence-04/d47699f19517f35a6936f97172219ff0cb78a4dc03f9c6ede2f049a078a7b738.json) |
| [nh-research-page](https://www.nanhua.net/subpage/researchIndex.html) | 200 / 100149 | 2026-09-06T13:41:22.576513+00:00 | [5633901cec23d8e2e5102de8e220d0985556ceee132131fb4b6d6bd0571298a3](evidence-04/5633901cec23d8e2e5102de8e220d0985556ceee132131fb4b6d6bd0571298a3.html) |
| [nh-force-notice](https://www.nanhua.net/news/2025/05/d8278efd-56d7-475b-881d-acfb9e652405.html) | 200 / 84736 | 2026-09-06T13:41:22.326862+00:00 | [ba31c97fe3816ff248a6e401e15236ab6b1b898c83963e7b442129d25ebc149e](evidence-04/ba31c97fe3816ff248a6e401e15236ab6b1b898c83963e7b442129d25ebc149e.html) |
| [sse-2009-factbook](https://www.sse.com.cn/aboutus/publication/factbook/documents/c/10170573/files/073e042b8b87407b919e3d8e75ee91a5.pdf) | 200 / 2132962 | 2026-09-06T13:41:20.543979+00:00 | [c962379b144ace00f189065ce7d1d32ea8f5d7fe47e3e617adc8383a291262c2](evidence-04/c962379b144ace00f189065ce7d1d32ea8f5d7fe47e3e617adc8383a291262c2.pdf) |
| [csi-000985-basic](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000985?lang=zh_CN) | 200 / 1319 | 2026-09-06T13:41:20.646038+00:00 | [687e6211137694255502faed2c9d117ed935e0a808de01892d6bef9bf26df495](evidence-04/687e6211137694255502faed2c9d117ed935e0a808de01892d6bef9bf26df495.json) |
| [csi-000012-basic](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000012?lang=zh_CN) | 200 / 1055 | 2026-09-06T13:41:20.749165+00:00 | [4390b7dc8015f4ed85dfeeafde53b7a7b4565ce95064deb5028216343f0fe39b](evidence-04/4390b7dc8015f4ed85dfeeafde53b7a7b4565ce95064deb5028216343f0fe39b.json) |
| [nh-daily-20260828](https://www.nanhua.net/cmsbigfile/2026/08/dba8b812-2f80-47ad-b82a-deac81c28417/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260828.pdf) | 200 / 1097835 | 2026-09-06T13:42:59.506288+00:00 | [f4074c86b04efa7e3cb033e95e8c1aedd0a8ecd91fadcfbdfc503e57b921aaca](evidence-04/f4074c86b04efa7e3cb033e95e8c1aedd0a8ecd91fadcfbdfc503e57b921aaca.pdf) |
| [nh-daily-list-page](https://www.nanhua.net/subpage/research/nawaaindex/indexresearch/index-daily.html) | 200 / 84513 | 2026-09-06T13:42:58.098841+00:00 | [0f52acd4089137424c24b4426f8c7e1dc8d355fb1934b3f5365b6e2b4bb15d37](evidence-04/0f52acd4089137424c24b4426f8c7e1dc8d355fb1934b3f5365b6e2b4bb15d37.html) |
| [nh-2026-weight-page](https://www.nanhua.net/news/2026/05/f2db1579-be72-4735-814e-4d4551c5a7bb.html) | 200 / 83337 | 2026-09-06T13:42:56.429041+00:00 | [1f3eecdbe960a27ee4130c9dafd5227419f93322a93a17e3f54018852c6c8446](evidence-04/1f3eecdbe960a27ee4130c9dafd5227419f93322a93a17e3f54018852c6c8446.html) |
| [nh-2025-weight-page](https://www.nanhua.net/news/2025/05/5ede4a4d-218d-4fbb-8ffb-e809669b16af.html) | 200 / 83331 | 2026-09-06T13:42:56.738434+00:00 | [13c64e98197e1f062525cf2a09f2e46292aecfe4ee1a93ae5d52abb77213aeb6](evidence-04/13c64e98197e1f062525cf2a09f2e46292aecfe4ee1a93ae5d52abb77213aeb6.html) |
| [nh-daily-list-260](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=404205&start=0&limit=260) | 200 / 148872 | 2026-09-06T13:43:41.460493+00:00 | [fdc2a2c4c696ff176b22d5c85a51e1984f1521dcddc79ba31650a1aaf6c17581](evidence-04/fdc2a2c4c696ff176b22d5c85a51e1984f1521dcddc79ba31650a1aaf6c17581.json) |
| [sse-calendar-2026](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml) | 200 / 28809 | 2026-09-06T13:46:48.198650+00:00 | [11d8a102d0747eaa8e97d9eda71eb9544ce30adbe83c706f7bdc77be4084686b](evidence-04/11d8a102d0747eaa8e97d9eda71eb9544ce30adbe83c706f7bdc77be4084686b.html) |
| [sse-calendar-2025](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml) | 200 / 28511 | 2026-09-06T13:54:12.669003+00:00 | [754afc6d12a01013cbadeef55e656aebc4e40aa7ef1cb63792f17dabf9bccdf8](evidence-04/754afc6d12a01013cbadeef55e656aebc4e40aa7ef1cb63792f17dabf9bccdf8.html) |
| [csi-000985-259d](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20250806&endDate=20260828&lang=zh_CN) | 200 / 93313 | 2026-09-06T13:55:34.643110+00:00 | [ffe3b20f7c9a09428bcedd641a358442e7e685c65de55844ac32022fd6b74b2d](evidence-04/ffe3b20f7c9a09428bcedd641a358442e7e685c65de55844ac32022fd6b74b2d.json) |
| [csi-000012-259d](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012&startDate=20250806&endDate=20260828&lang=zh_CN) | 200 / 93290 | 2026-09-06T13:55:34.659594+00:00 | [30b9736664d961d6481386433c86ebddb8d7d8171ecd2450ad70da5e8bb49798](evidence-04/30b9736664d961d6481386433c86ebddb8d7d8171ecd2450ad70da5e8bb49798.json) |
| [tushare-public-doc-95](https://tushare.pro/document/2?doc_id=95) | 200 / 36033 | 2026-09-06T13:58:42.382470+00:00 | [5f5a4e8a29b483222ee398c896a4221e95b145dc209201f4d596543f00e5c54b](evidence-04/5f5a4e8a29b483222ee398c896a4221e95b145dc209201f4d596543f00e5c54b.html) |
| [tushare-public-doc-468](https://tushare.pro/document/2?doc_id=468) | 200 / 38165 | 2026-09-06T13:58:44.089105+00:00 | [d0e5971998ff65e858a24f1307638de4a8ba1434da5bd0851fc009f99d364fc9](evidence-04/d0e5971998ff65e858a24f1307638de4a8ba1434da5bd0851fc009f99d364fc9.html) |
