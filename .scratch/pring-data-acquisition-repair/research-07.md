# 第 07 票：三指数估值语义、完整性与官方样本

研究日期：2026-09-06。固定目标：2026-03-09 至 2026-08-28 的 120 个中国交易日。依据 [规格](spec.md)、[第 07 票](issues/07-valuation-certification.md)、[ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)及当前代码契约。本次只新增本文件与 `evidence-07/`；未调用账户 API、读取密钥、购买、修改应用、生产库、模型、认证或票状态，04/05/06 研究保持不变。

**结论：已新增确认三指数单张中的滚动 PE、PB 和股息率，其中 CSI1000 有真实官方 PB 样本；但日期为 2026-08-31，不能回填目标日 08-28。三指数完整 PE/PB/换手率认证仍未完成。** 当前官方历史滚动 PE 可覆盖 120 日，不能替换要求的静态 PE；同日不同官方交付也存在数值差异，必须绑定具体计算口径与版本。

本次重新下载 8 份既有公开估值响应，其 SHA256 与 09-05 原件完全相同；另取得两份上交所托管的指标说明。不是只重复链接：重新解析了真实 XLS、JSON、PDF，复核已保存 TuShare 原响应，并只读统计实际缺少的日期维度。全部请求有限超时，无无限重试。[请求回执](evidence-07/receipts.json)记录 URL、HTTP、接收时刻、字节数及响应头；[导入记录](evidence-07/imports.json)区分旧 CAS/06 原件复用；[验证明细](evidence-07/verification-summary.json)保留逐行结果。

## 1. 现有契约与真正应有的成员

当前 `tushare_context.py:45` 指定 `000300.SH`、`000905.SH`、`000852.SH`，估值路径第 784–814 行消费：

| 渠道字段 | 当前 measure | 当前单位 | 本票需要解决的语义 |
|---|---|---|---|
| `pe` | `price_earnings` | `multiple` | 票要求静态 PE；TuShare 文档仅称市盈率，尚未完整证明利润期、聚合股本和更新规则 |
| `pb` | `price_book` | `multiple` | 净资产、股本权重、负净资产处理与财报更新时点 |
| `turnover_rate` | `turnover_rate` | `percent` | 股本还是市值换手率、流通还是自由流通分母、成交范围及真实数值单位 |

`catalog.py:226,244,261` 将 `CN_INDEX_VALUATION` 绑定 `tushare:index_dailybasic`、`multiple/percent`、`index/measure`，属于现行 v3 的 P1。然而 `metric_contracts.py:42–48` 的必需集合只有 300/500 六成员，注释将 1000 当作不支持而排除。**这与第 07 票要求的三指数完整性不一致**；渠道缺行应表现为缺口，不能缩小应有集合。

按当前票的三指数 × PE/PB/换手率，每个交易日应有 9 个成员，120 日合计 1080。只读库查询实际有 **720 个唯一日期维度值组、1440 条底层 claim、120 个日期**，全部为 300/500 × 三字段；缺 CSI1000 的 360 个应有成员，未发现额外成员。不能把重复 claim 数量当作覆盖。存在、完整、已认证、点时可见和已被模型选择分别判断。[精确 SQL、参数、查询时间及全部结果](evidence-07/read-only-claims.json)。

```sql
SELECT period_end,value,unit,dimensions_json,count(*) AS n
FROM source_claim
WHERE metric_id=? AND period_end BETWEEN ? AND ?
GROUP BY period_end,value,unit,dimensions_json
ORDER BY period_end,dimensions_json,value;
```

参数为 `CN_INDEX_VALUATION`、`2026-03-09`、`2026-08-28`，SQLite URI 使用 `mode=ro`。

更早的 [v1 目录第 80 行](../pring-cycle-v1-wayfinding/assets/v1-metric-catalog.md)标题含股息率、列为 P2，并限定实际支持字段；当前代码与第 07 票明确 PE/PB/换手率。这里记录版本差异，**不凭旧标题自动加股息率，也不因取得 TTM 就替换静态 PE**。新增/改名须形成明确决议和新不可变定义。

## 2. PE、PB、股息率和换手率：可支持的规则依据

### 2.1 一般定义足够区分指标，但不证明某渠道实现

新取得 [《证券期货业统计指标标准指引（2025 年修订）》](https://big5.sse.com.cn/lawandrules/regulations/csrcannoun/c/10787043/files/6e68fb5e2cf54a3fb3461692ae169297.pdf)（[原 PDF](evidence-07/ef4313bf119ef4688df6f5941c0fed2542cdbbfcc879d5a1cd06be19289702cb.pdf)，279 页）。可定位：PDF 41–43 页为换手率，43–45 页为 PE，46–47 页为 PB，60–62 页为股息率。

它明确：静态 PE 使用最新年报 EPS，滚动 PE 使用连续四季度 EPS；单位倍。利润更新可以集中在财报截止日之后，也可以随公告更新，但须注明；一组股票的算法还要注明是否剔除亏损。PB 使用对应净资产，单位倍，不能从名字推定负净资产处理。换手率单位百分数，分股本/市值，以及流通/自由流通口径；股息率还区分实际、预案和历史年度现金分红。**这些是定义选择的证据，不是 TuShare 或某 CSI 网页算法已满足的证明。**

另取 [上交所月报指标说明](https://star.sse.com.cn/aboutus/publication/monthly/explain/)（[HTML 原件](evidence-07/d899c2317fb0a941de05816691db635d45a60ece16f04aab114a10e7ccd96bba.html)）：其中一组股票采用成交金额/总市值，单股采用成交数量/发行数量。这与上述指引对流通口径的分类共同表明，“换手率”名字不足以唯一确定分母。该月报是其统计对象的规则，不能直接当作三指数 TuShare 字段公式。

### 2.2 CSI 确实提供两种股本口径的 PE 和股息率

[中证普通文件服务规范 V4.5.4](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260112160427-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6%E6%9C%8D%E5%8A%A1%E8%A7%84%E8%8C%83V4.5.4.pdf)（[已存原件](evidence-06/5eed1d83aef3a3158f86bce9c454a4db2728f89a228f375ea451f6465c5d3f7e.pdf)，PDF 第 52 页、3.8.2）定义：

```text
P/E1 = sum(总股本 × 价格) / sum(总股本 × EPS)
P/E2 = sum(调整股本 × 权重因子 × 价格)
       / sum(调整股本 × 权重因子 × EPS)
```

D/P1、D/P2 用相应股本权重的年度每股现金股息与价格比，显式乘 100%。因此 PE 是倍、D/P 是百分数，PE1/PE2 不是两个可随意择近的同义字段，也不是个股 PE 的简单平均。该节没有完整给出 EPS 财报期、亏损/零利润处理和更新日，不足以单独认证三指数完整静态算法。

三份实际 XLS 的表头分别是“市盈率1（总股本）P/E1”“市盈率2（计算用股本）P/E2”“股息率1（总股本）D/P1”“股息率2（计算用股本）D/P2”。它们没有 PB、TTM 或换手率列。[300 官方 XLS](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000300indicator.xls)（[原件](evidence-07/677773b60a9aa22e51e162e3b8f6549c16c6913eff02d31c6103a840909e6123.xls)）、[500](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000905indicator.xls)（[原件](evidence-07/7a7d915fb5ee56c1fe076fd01dcd0b548ab0a65978059dd9780493ee268dad4e.xls)）、[1000](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000852indicator.xls)（[原件](evidence-07/a15cea8ce2a93f1090dab96ea3e2434acd392a855d9e3bb95161989e7c90706e.xls)）。

每份 8192 字节，20 个交易日（08-10 至 09-04），其中 15 日在目标范围；完整行、表头、日期和列值均重新解析留存。不能将 20 日文件写成 120 日静态 PE 能力。

### 2.3 网页 `peg` 确实绑定滚动 PE，单凭名字不得猜测

[官网主 JS](https://www.csindex.com.cn/static/js/app.5663471f.js)（[原件](evidence-07/44bf077194aea6d8f09c6dfa2295d4d74d5fb6ee83ebb05052c7b9befa837da5.js)）的 `data.indexDashboard` 中文资源，以及 [每日指数信息组件](https://www.csindex.com.cn/static/js/chunk-57ef014f.666d6120.js)（[原件](evidence-07/82a2a9831136ab6b52b8425422d959fb085b453da7c01d1bfe39cbb9cfb9cb87.js)）的 `columns2`，直接给出 `PE→pe`、`PETTM→peg`、`PB→pb`、`DP→dp`。因此这里的 `peg` 是滚动 PE，不能按常见金融缩写猜成 PE/增长率，也不能改名为 TuShare `pe`。

主 JS 有亏损剔除、最新财报净资产等页面说明，但仍未完整确定各接口的股本、财报切换和负值处理。另有 [行业指标计算说明 V1.1](https://oss-ch.csindex.com.cn/indexCalculationDescription/%E6%8C%87%E6%A0%87%E8%AE%A1%E7%AE%97%E8%AF%B4%E6%98%8E.pdf)（[原 PDF](evidence-07/e9beda14cdb9f4cff78dbcae3ffe8b6875d2664829086a7bb750cfadc58f7ecd.pdf)），对象明确为行业，虽列具体财报切换及负值筛除，也不能未经适用性证明移植给 CSI300/500/1000。

## 3. 实际官方数值及替代交付的边界

### 3.1 当前 JSON 与历史滚动 PE

[当前 indexValuation](https://www.csindex.com.cn/csindex-home/data-service/indexValuation)（[原 JSON](evidence-07/6828af1f5ee5500656fd790c324a8dc8955f4688656aa5ec880afa85bf65b14e.json)）实际返回 2026-09-04 的八个指数，行内有中英文名称，没有 `indexCode`；目标三者中只有 300/500：

| 指数 / 2026-09-04 | `pe` 静态 | `peg` 滚动 | `pb` | `dp` 股息率 |
|---|---:|---:|---:|---:|
| CSI300 | 14.87 | 13.64 | 1.41 | 2.58 |
| CSI500 | 29.18 | 25.77 | 2.22 | 1.35 |
| CSI1000 | 无该行 | 无该行 | 无该行 | 无该行 |

DP 与该日 XLS 的 D/P1 相符；JSON 没有独立单位元数据，这个比较不能独立证明完整分红算法。该端点没有在实际前端请求中传历史日期，不能擅称历史 API。名称映射须明确且排除重名，不能以任意简称配对。

历史接口为 [300](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000300&startDate=20260309&endDate=20260904)（[原件](evidence-07/3a532a220eb14231072f037321ee4f17d53db39eafebab7041c7acf9101bf4bc.json)）、[500](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000905&startDate=20260309&endDate=20260904)（[原件](evidence-07/80ec76ac9acd629a03bf453f5877c38658b2c12faccce0ef1298fa38f44c3aa3.json)）、[1000](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000852&startDate=20260309&endDate=20260904)（[原件](evidence-07/af2f2c2b264b0eb2f692f24b4a42a9fbaf2e3b0a8c6a872c6c990a86a9539e5c.json)）。各 129 个唯一日期，仅 `tradeDate,indexName,indexNameEn,peg`，无 PE1/PE2、PB、股息率或换手率。

按 [上交所官方日历](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml)（[已存原件](evidence-04/11d8a102d0747eaa8e97d9eda71eb9544ce30adbe83c706f7bdc77be4084686b.html)）复核：每份有 125 个真实交易日，其中目标 120 日完整无重复；另外 04-06、05-04、05-05、06-19 四个休市日期的值均等于前一真实交易日。12 对沿用值全部保留在验证明细。可按已认证日历生成交易日视图，但不能删原件、称 129 交易日，或将休市行算新观测。额外沿用记录本身不否定端点的 120 日能力。

### 3.2 新确认的三指数单张：CSI1000 PB 已有真实样本

第 06 票取得、现重新核验并复制的 2026-08-31 单张第 1 页“基本面”实际含：

| 指数 | 滚动 PE（倍） | PB（倍） | 股息率（%） | 同日历史 JSON `peg` | 单张 PE 减 JSON |
|---|---:|---:|---:|---:|---:|
| 300 | 14.65 | 1.44 | 2.27 | 14.53 | +0.12 |
| 500 | 28.63 | 2.29 | 1.17 | 28.20 | +0.43 |
| 1000 | 33.22 | 2.39 | 0.95 | 32.83 | +0.39 |

来源：[300 单张](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)（[PDF](evidence-07/8653755655ded0148202f0e43a20d36e9beaa1682a09b0c8e6d84f321f13c056.pdf)）、[500](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf)（[PDF](evidence-07/ccabf70fa1383861c8b178d727bbacfbc2634ed8a9a16706a8313f4a19c64c06.pdf)）、[1000](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000852factsheet.pdf)（[PDF](evidence-07/68a6e3e47a6c357537feffaef58d7cc4b994b36149c6589e661e3d1cb1eda671.pdf)）。CSI1000 还通过 [原 PDF 第 1 页渲染图](evidence-07/derived-000852-factsheet-page1.png)视觉核对行列；图片是派生检查图，不能替代 PDF 原件。

三份页脚都明确指标采用个股“计算用股本”。这关闭“没有任何 CSI1000 官方 PB 样本”的旧缺口，**但不关闭目标 08-28 的 PB 或 120 日 PB 缺口**。单张数据日期、指数首次发布日期、文件修改时间分开；不能把页内 2014-10-17 等指数初始发布日当作该估值样本发布时间。

同日单张滚动 PE 与历史 JSON 的差异超过两位展示舍入误差。单张股本口径有证据，历史 JSON 完整口径未证；不能据此猜定差异完全由权重或财报切换造成。即使两者均官方、均写滚动 PE，也不得混成同一序列或择近认证。

## 4. TuShare 000852 空响应的实际含义

[TuShare 官方 index_dailybasic 文档](https://tushare.pro/document/2?doc_id=128)（[本次 HTML 原件](evidence-07/55c112a3e1d830b8eeea82d56ceee0f51099a8d860f2835dce628b77508e92c7.html)）明确数据由社区统计计算，文字提供范围没有中证1000；示例包含 300、500。文档区分 `pe`、`pe_ttm`，后者为最近四季度口径，也区分普通/自由流通股本换手率；没有指数聚合算法、`turnover_rate` 的独立单位字段或日内更新时间证明。

根代理于 09-05 已获授权取得的原响应，本次只读复制并验 hash：

| 请求 / trade_date=20260828 | 原响应 SHA256 | 原接收时间 UTC | 实际结果 |
|---|---|---|---|
| 000300.SH | [9c7cbd8dfe3152de32df132a16e73013abea10295e9123d3f2af8d2752ffd954](evidence-07/9c7cbd8dfe3152de32df132a16e73013abea10295e9123d3f2af8d2752ffd954.json) | 2026-09-05 11:56:35.824122 | 256 bytes，code=0，1 行 |
| 000905.SH | [816fd15e5468bbb98a03605e3140f8056e305a7a67b045cc052eb39b6c0c2be3](evidence-07/816fd15e5468bbb98a03605e3140f8056e305a7a67b045cc052eb39b6c0c2be3.json) | 2026-09-05 11:56:35.907309 | 256 bytes，code=0，1 行 |
| 000852.SH | [edab244c0df5905c02babd5291c27145a182df970699879134eabcbaad4abd3c](evidence-07/edab244c0df5905c02babd5291c27145a182df970699879134eabcbaad4abd3c.json) | 2026-09-05 11:56:35.994393 | 202 bytes，code=0，items=[] |

请求为 `https://api.tushare.pro` POST、`api_name=index_dailybasic`，参数为对应 `ts_code` 和 `trade_date=20260828`，fields 为 `ts_code,trade_date,pe,pe_ttm,pb,turnover_rate`。请求参数/原接收时刻来自根代理先前回执，字节已独立重验；这不是本研究新账户实测。三份 `data.count` 都为 0，但前两份实际有一行，不能只看 count 判空。

**可支持的原因判断**：1000 在该接口文档未获覆盖承诺，具体请求也没有交付行，二者共同支持“渠道覆盖缺口”。原响应没有拒绝原因或权限错误，不能进一步判定账户积分不足、限流、代码永久不支持或某次服务器异常。文档缺名不是永远无法支持的证明；本次不靠多日期账户重试猜原因。CSI 官方有其 PE/股息率、历史滚动 PE 和当期 PB，并不意味着能以相同语义补齐 TuShare 三字段。

### 4.1 同日原响应的数值差异继续保留

| 2026-08-28 | TuShare `pe` | 官方 P/E1 | 官方 P/E2 | TuShare `pe_ttm` | 官方历史 `peg` | TuShare PB / 换手率 |
|---|---:|---:|---:|---:|---:|---|
| 300 | 14.7661 | 14.75 | 17.10 | 13.8377 | 14.42 | 1.4554 / 0.5401 |
| 500 | 38.9664 | 29.23 | 31.46 | 34.1372 | 28.01 | 2.4599 / 1.5455 |
| 1000 | 无行 | 33.30 | 34.49 | 无行 | 32.53 | 无行 |

300/500 的 `pe−P/E1` 分别 +0.0161/+9.7364，`pe−P/E2` 分别 −2.3339/+7.5064；`pe_ttm−peg` 分别 −0.5823/+6.1272。这些仅是诊断差异，不预设算法等价；两位舍入不能消除。没有官方证据把差异归因于特定亏损股、财报期、样本范围或权重，因此不强配 PE1/PE2，也不改原值。

该日官方 XLS 的 D/P1/D/P2 分别为 300：2.52/2.22%，500：1.32/1.18%，1000：1.07/0.97%；它们不是换手率。官方英文 `Turnover` 在日行情导出里表示成交金额（亿元），也不能填 `turnover_rate`。本次没有目标同日 PB/换手率官方同义值，故该两字段是未验证，不应误称已经数值不匹配。

与此处三份真正原响应不同，120 日统计取自标准化 source_claim。数量相符或值相同也不能补造旧声明到逐请求原件的关联。原响应、规范化输出和模型采纳分别保留层级。

## 5. 实际公开时间与历史版本仍有哪些缺件

- 三份 TuShare 原响应只有交易日；根代理 09-05 的取回时刻不证明 08-28 当时可得，也不证明未经修订。
- CSI JSON 没有逐行首次发布/修订时间。组件虽名为 `publishDate`，估值路径实际赋 `t.data.tradeDate`，可在上述 dashboard JS `sendRequest` 的 case 1 定位。不能据变量名认定公开日期。
- 本次 XLS 的 Last-Modified 仍为 2026-09-05 03:30:19Z、03:30:54Z、03:31:00Z；这是当前 20 行文件的资源修改时间，不是其每行历史发布时间。09-05 与本次 hash 相同，只证明两个采样时刻的字节相同，不证明更早历史没有修订。
- 08-31 单张的页内日期是统计截面。HTTP 修改时间与本次取得见导入记录，不自动等于第一公开日，更不能提前到 08-28。
- V4.5.4 PDF 第 22 页的指标文件每日 09:00 更新，以及资讯商总包 23:00 等，是服务安排，不是实际发布日志；不能统一填 15:30、18:00 或次日某时刻。只有取得可信真实发布日期之后，才能按规格的下一本地日规则进入 PUBLIC；单有交易日/当前抓取，历史 PUBLIC 保持未知。

本次没有形成可回填 120 日逐日首次公开时间的新事实。SYSTEM 接收/校验可用时间也必须遵守当前证据与模型认证，不能绕过未认证定义。

## 6. 可执行决策依据与最小后续补证

1. **应有集合不随渠道缩水**：本票以三指数 × 三字段形成 9 成员；同一日期、定义版本分别检查。真实空响应、字段 null、无可靠时间、口径冲突不是同一个失败原因；它们都不能计为完整。
2. **静态与滚动分开决策**：保持当前静态需求，就需要明确总/计算/流通股本、EPS 年度、公告/统一切换规则、负/零利润和成分变动。已有官方 PE1 样本是候选锚点，不能凭数值接近认定与 TuShare pe 等价。若用户决定增设官方 TTM，须独立命名/版本和来源认证，保留静态未证状态；即便增设 TTM，PB/换手率缺口仍在。
3. **PB 和股息率不能用同名简化**：单张已经提供全三指数“计算用股本”PB/股息率语义样本；还需所选交付的完整聚合、负净资产/财报期规则、所需历史原件和实际公开时间。股息率不自动纳入本票三字段，也不能替换换手率。
4. **换手率需要独立锚点**：明确成交股数或金额、总/流通/自由流通分母、跨成分聚合与交易方式范围，取得对应官方目标指数数值。不能用一般行业标准替渠道自选公式，不能拿金额 Turnover 顶替百分比。
5. **官方交付候选分层**：三份公开 indicator.xls 能交付 20 日 PE1/PE2/D/P；历史 indexCsiDsPe 能交付目标 120 日滚动 PE；当前 dashboard 有 300/500 的静态/滚动 PE、PB/DP；08-31 单张有三者 PB/DP。没有一个已验证公开入口能交付完整三指数 120 日静态 PE/PB/换手率。官方文件服务或授权资讯商可以作为待核渠道，但实际历史文件、目标字段、许可和版本/时间必须取得，不能宣称已经拥有该权限或必然有货。

**本研究未代用户冻结新的 PE、TTM 或股息率定义，未申报家族通过。** 新发现已将缺口从“没有任何官方 PB 样本”收窄为“有明确日期和股本口径的样本，但目标历史覆盖、渠道等价和 PUBLIC 未证”；其它未解决项继续阻塞本票正向认证。

## 7. 原件与时间索引

当前 10 笔有限公开请求的完整原始 hash、URL、最终重定向地址、接收时间、响应头和字节数见 [receipts.json](evidence-07/receipts.json)；其中统计指引的 HTTPS 入口重定向到官方 HTTP 文件地址，回执如实保留，不隐藏协议变化。三份账号原响应和其它复用原件见 [imports.json](evidence-07/imports.json)，三份单张保留第 06 票原 URL、原接收时间及响应头。

所有当前响应和复用原件均按内容 SHA256 复核。原件使用 `<完整 SHA256>.<格式>` 命名；本研究 JSON 统计和 PNG 检查图是派生制品，不冒称 HTTP 原件。逐行对账与缺失 360 个成员清单在 [verification-summary.json](evidence-07/verification-summary.json)，可以从每个比较条目追到原始 hash 和日期。
