# CNY030 与中证三指数估值：官方样本补充复核

复核日期：2026-09-05。范围限于 `CN_BOND_FULL_PRICE_CNY030` 与 `CN_INDEX_VALUATION`。依据 [ADR0013](../adr/0013-tushare-delivery-with-official-sampling.md)，本文件补充官方抽样证据，不签发认证、不修改目录或模型，也不要求每条正式观测有第二来源数值。

前次 [市场来源语义复核](market-source-semantic-review-2026-09-05.md) 保持原样；本次核对时其 SHA-256 为 `e6c027f2749f901526cc3deb10f6a855d993b3843ceae420d4fad40eaf618cc2`。第一阶段仅新增此文档及获授权保存的原始公开响应，没有读取密钥、调用账户接口、连接 FTP、修改代码或数据库。后续第五节只读主执行代理另行授权取回的 TuShare 响应进行同日比较；研究代理本人没有读取密钥或发起账户请求。

## 结论与认证边界

1. **三指数均取得真实官方估值 XLS 样本**，各含 2026-08-10 至 2026-09-04 的 20 个交易日。表头明确区分总股本市盈率 P/E1 与计算用股本市盈率 P/E2；官方技术规范给出两者聚合公式。该 XLS 不含 PB、TTM 或换手率列。
2. **官网 JSON 的 `peg` 有直接中文列绑定**：在“每日指数信息”的指数估值页，它是滚动市盈率；`pe` 是静态市盈率，`pb` 是市净率。该 JSON 当前只有八个指数，覆盖沪深300、中证500，未包含中证1000。不能按字段拼写把 `peg` 当成 TuShare `pe`，也不能把 P/E1、P/E2 当作同一口径。
3. **CNY030 身份已确认，数值样本仍未取得**。官方派生列表确实列出 `000012CNY030` 国债指数(全)。本次日线、单日、收益概览、官方 XLSX 导出均没有有效数值；元数据列出的专属 factsheet 实际返回 HTTP 404。空响应和仅表头文件已保存，可复核“没有取得样本”，不能算官方数值验证通过。
4. **仍不足以认证完整 `index_valuation` family**：中证1000 PB、三个指数的官方换手率，以及 TuShare 社区计算与指定官方估值口径的等价性仍缺证据。现有资料也不能证明历史每条记录的首次公开时间。已取得材料可关闭“没有任何可保存官方估值样本”和“完全不知道 P/E1/P/E2 公式”的缺口。

## 保存方法与时间解释

以下 SHA-256 均针对实际 HTTP 原始响应字节，不是提取文本或整理后的 JSON。存储位置统一为：

`/home/tywin/.local/share/pring-cycle/artifacts/sha256/<hash前2位>/<完整hash>`

通过 Windows 的 WSL UNC 路径写入同一位置；已有同 hash 文件只重新计算 hash 验证，不覆盖。新文件以独占创建模式写入。请求均设 15–20 秒网络超时；失败没有无限重试。XLS 使用 `xlrd`、XLSX 使用 `openpyxl`、PDF 使用 `pypdf` 从已下载字节读取。HTTP 超时或 404 若未保存响应体，表内明确标为无原始 hash。

取回时间统一为 **2026-09-05 UTC**，表中写时分秒；转换北京时间加八小时。`retrieved_at` 是下载完成时本机 UTC 时间，证明当时能公开取得该响应；不证明它在历史交易日何时首次发布。`tradeDate`/XLS“日期”是交易日期。HTTP `Date` 是本次响应时间；`Last-Modified` 是服务器报告的资源修改时间；二者均不自动等于首次公开时间。网页组件虽把变量命名为 `publishDate`，实际赋值来自响应 `tradeDate`，不能据变量名认定发布日期。

## 一、官方端点与字段的证据链

入口为 [中证官网每日指数信息](https://www.csindex.com.cn/#/dataService/indexDashboard) 和 [沪深300指数详情](https://www.csindex.com.cn/#/indices/family/detail?indexCode=000300)。官网是 JavaScript 应用，web 工具只能读到启用 JavaScript 的提示；本次进一步下载官网当前实际引用的 JS，沿其请求定义取得公开 JSON、XLS 和 PDF。下载域名均为 `www.csindex.com.cn`、其官方元数据直接给出的 `oss-ch.csindex.com.cn` 或 TuShare 官方文档域名。

|证据|原始 URL|UTC取回时间|字节|SHA-256|
|---|---|---|---:|---|
|官网主 JS：接口路由、中文词条|[app.5663471f.js](https://www.csindex.com.cn/static/js/app.5663471f.js)|10:16:35.405409|955177|`44bf077194aea6d8f09c6dfa2295d4d74d5fb6ee83ebb05052c7b9befa837da5`|
|每日指数信息组件：真实列绑定|[chunk-57ef014f.666d6120.js](https://www.csindex.com.cn/static/js/chunk-57ef014f.666d6120.js)|10:20:49.531768|20551|`82a2a9831136ab6b52b8425422d959fb085b453da7c01d1bfe39cbb9cfb9cb87`|
|指数详情组件：下载元数据参数、派生选择、导出请求|[chunk-1226b234.89f4352e.js](https://www.csindex.com.cn/static/js/chunk-1226b234.89f4352e.js)|10:20:51.439060|160770|`3cd3b83337ae5fcead1f94540c6f0dc0fc121e4dac11733985ae63c0ce3730e2`|
|技术文档组件：公开文件目录参数|[chunk-3ead80c8.21762e87.js](https://www.csindex.com.cn/static/js/chunk-3ead80c8.21762e87.js)|10:25:09.103859|4875|`b5f9fb356bdf6707ee9aed69bb27b1fecb7c4ddfdf1b0184a783a6f24a2ea6b4`|
|TuShare `index_dailybasic` 官方文档 HTML|[doc_id=128](https://tushare.pro/document/2?doc_id=128)|10:25:53.025261|34079|`55c112a3e1d830b8eeea82d56ceee0f51099a8d860f2835dce628b77508e92c7`|

四份中证 JS 的 HTTP `Last-Modified` 均为 `2026-08-26T01:56:34Z`，是站点资源版本证据，不是指数数据发布时间。另两个详情页公共依赖也已保存，未用于推导金融语义：[chunk-626e3dcf.b4dc8b15.js](https://www.csindex.com.cn/static/js/chunk-626e3dcf.b4dc8b15.js)，10:20:50.384899，309442 bytes，`a4bb5be7e80816a36d886f1950a8d739c91625a78e4ee23aa9438245b14b85f3`；[chunk-c75f486c.65771c92.js](https://www.csindex.com.cn/static/js/chunk-c75f486c.65771c92.js)，10:20:50.806708，46185 bytes，`33ddb32940ee27bebe8a234dc03229dfe715c2492abc408abc7eef1a8af35d58`。

字段绑定定位：每日指数信息组件的 `columns2` 使用 `data.indexDashboard.PE → pe`、`PETTM → peg`、`PB → pb`；主 JS 的中文资源分别解释为静态市盈率、滚动市盈率、市净率。组件调用 `data-service/indexValuation`，从 `data.indexValuations` 取行。详情组件的 `getRelativeMaterial` 使用 `fileLang=2&indexCode=...`，不是仅传 `lang=zh_CN`；这解决了前次元数据请求失败的参数问题。[组件原文](https://www.csindex.com.cn/static/js/chunk-57ef014f.666d6120.js)、[详情组件原文](https://www.csindex.com.cn/static/js/chunk-1226b234.89f4352e.js)。

## 二、估值样本、方法及尚不能建立的映射

### 2.1 当前官方 JSON

实际 GET [indexValuation](https://www.csindex.com.cn/csindex-home/data-service/indexValuation)，取回于 10:21:55.403771，1485 bytes，SHA-256 `6828af1f5ee5500656fd790c324a8dc8955f4688656aa5ec880afa85bf65b14e`。返回 `code=200`、`tradeDate=20260904`，行内以中英文名称识别指数，没有 `indexCode` 字段。

|交易日|返回指数名称|`pe` 静态市盈率|`peg` 滚动市盈率|`pb` 市净率|换手率|
|---|---|---:|---:|---:|---|
|2026-09-04|沪深300 / CSI 300|14.87|13.64|1.41|无该字段|
|2026-09-04|中证500 / CSI 500|29.18|25.77|2.22|无该字段|
|2026-09-04|中证1000|该响应无此行|该响应无此行|该响应无此行|无该字段|

PE、PB 为比值（倍），不是百分比；JSON 本身无独立单位字段，语义由真实中文列名建立。该请求没有传历史日期，不能把当前端点视为历史 API；也没有取得每个历史日的发布日期或修订记录。

同日官方 `index-perf` 日线实际含 `peg`：沪深300 13.64、中证500 25.77、中证1000 30.29。其中前两项与上表当日滚动市盈率一致，为跨官方端点的样本佐证。中证1000 的 `peg` 沿相同详情组件用作“历史估值”，但本次未取得它的 PB；不要由这个数值推定全部估值字段已经齐备。

|日线原始 URL|UTC取回时间|字节|SHA-256|同日收盘点位 / `peg`|
|---|---|---:|---|---|
|[000300，20260904](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000300&startDate=20260904&endDate=20260904)|10:24:00.287086|390|`264b236fdca1b619c3ff465c5ef7a0241035a37f6ff3d6343b4cd781452f3337`|4548.05 / 13.64|
|[000905，20260904](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000905&startDate=20260904&endDate=20260904)|10:24:00.290658|407|`d93993035a672cf547c2e1e6f93102acdea2dd834e7dd6d0a9027c6899640cda`|7652.69 / 25.77|
|[000852，20260904](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000852&startDate=20260904&endDate=20260904)|10:24:00.287411|397|`d3b7f3ae00079100a3e925bd2f3ef4cb39cf917b0423ff7c9d54af9601cfce18`|7508.09 / 30.29|

这三条响应的 HTTP `Date` 均为 `2026-09-05T10:23:53Z`，没有 `Last-Modified`，内容无首次发布时间字段。成交金额在官方导出表头叫“成交金额（亿元）Turnover”；**Turnover 是金额而不是换手率**，不能映射 `turnover_rate`。

### 2.2 三指数官方估值 XLS

下列下载链接不是猜文件名得到的：先由各指数详情页的“指数估值”元数据得到，再实际下载并解析。

|元数据原始 URL|UTC取回时间|字节|SHA-256|
|---|---|---:|---|
|[000300 / fileLang=2](https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data?indexCode=000300&fileLang=2)|10:21:55.414935|7087|`7e5a8c76ad8084466de708159aee2906c7f96700f2f50a451dac6e61beea9436`|
|[000905 / fileLang=2](https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data?indexCode=000905&fileLang=2)|10:21:55.416315|3920|`08908c346765993f99dae759eb6f3ea839cec70f4cbf4727397cfd684be8ed45`|
|[000852 / fileLang=2](https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data?indexCode=000852&fileLang=2)|10:21:55.699858|1991|`44a51eac1092715343cc719e9d9462ce58981df0757f6da342426e37b0d9aea4`|

三个 XLS 均为真实 Excel 二进制文件、8192 bytes、一个工作表、21 行（表头加 20 个交易日）、10 列。共同字段为日期、代码、四种中英文名称、P/E1、P/E2、D/P1、D/P2。金融字段的原始中文限定分别为“市盈率1（总股本）”“市盈率2（计算用股本）”“股息率1（总股本）”“股息率2（计算用股本）”。

|原始 XLS URL|UTC取回时间|SHA-256|HTTP Last-Modified（UTC）|20260904 P/E1 / P/E2 / D/P1 / D/P2|
|---|---|---|---|---|
|[000300indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000300indicator.xls)|10:23:06.929777|`677773b60a9aa22e51e162e3b8f6549c16c6913eff02d31c6103a840909e6123`|2026-09-05 03:30:19|14.87 / 17.07 / 2.58 / 2.30|
|[000905indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000905indicator.xls)|10:23:06.974865|`7a7d915fb5ee56c1fe076fd01dcd0b548ab0a65978059dd9780493ee268dad4e`|2026-09-05 03:30:54|29.18 / 31.22 / 1.35 / 1.22|
|[000852indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000852indicator.xls)|10:23:06.721717|`a15cea8ce2a93f1090dab96ea3e2434acd392a855d9e3bb95161989e7c90706e`|2026-09-05 03:31:00|33.56 / 34.65 / 1.09 / 0.99|

P/E 为倍，D/P 为百分数（技术规范公式显式乘 100%）。沪深300、中证500 的该日 P/E1 恰与 JSON `pe` 一致；这只是这两个指数的单日官方内部样本一致，不能替代对 XLS 的 EPS 年度/TTM 选择规则或对 TuShare 聚合口径的验证。三个文件无 PB 和换手率列，不能从文件名称“indicator”补造字段。

### 2.3 真正取得的官方方法文件

技术文档目录来源为 [technicalDocumentation 元数据](https://www.csindex.com.cn/csindex-home/webStatic/selectByPage?language=zh&page=technicalDocumentation)，10:25:51.202063，1825 bytes，SHA-256 `23a53a29f6dbac00ff09fce89ce94d15d1c45fd6cd1c2e354f6b49dccd26bfb1`。

|官方文件|目录显示文件日期|UTC取回时间|字节 / PDF页数|SHA-256 / Last-Modified|
|---|---|---|---|---|
|[中证指数数据文件服务规范 V4.5.4](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260112160427-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6%E6%9C%8D%E5%8A%A1%E8%A7%84%E8%8C%83V4.5.4.pdf)|2026-01-12|10:26:32.326531|490050 / 53|`5eed1d83aef3a3158f86bce9c454a4db2728f89a228f375ea451f6465c5d3f7e`；2026-01-12 08:04:27Z|
|[中证指数行情传输接口规范 2.2](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260803092336-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E8%A1%8C%E6%83%85%E4%BC%A0%E8%BE%93%E6%8E%A5%E5%8F%A3%E8%A7%84%E8%8C%83(2.2).pdf)|2026-08-03|10:26:32.591929|239381 / 8|`de3e59b144da15ff54c95e47945f829e0f942767c9443fdf264a25f869254054`；2026-08-03 01:23:36Z|
|[行业指标数据计算说明 V1.1](https://oss-ch.csindex.com.cn/indexCalculationDescription/%E6%8C%87%E6%A0%87%E8%AE%A1%E7%AE%97%E8%AF%B4%E6%98%8E.pdf)|PDF内2020-12更新；未验证首次公开日期|10:26:06.093830|153609 / 5|`e9beda14cdb9f4cff78dbcae3ffe8b6875d2664829086a7bb750cfadc58f7ecd`；2024-11-30 10:12:00Z|

V4.5.4 的 PDF 第52页、正文第38页、3.8.2 节给出指数指标的正式定义。设价格为 P、每股收益为 EPS、总股本为 S、调整股本数为 A、权重因子为 W：

- P/E1 = Σ(S × P) / Σ(S × EPS)。
- P/E2 = Σ(A × W × P) / Σ(A × W × EPS)。

这是股本权重参与分子、分母的聚合，不能改为个股 PE 的简单平均。该节没有说明 EPS 是哪一期、财报何时切换、亏损或零利润如何处理，也没有 PB 或换手率字段。D/P 使用同类股本权重和年度每股现金股息。该规范的数据对象是 `YYYYMMDDindicator.txt/zip`；公开 XLS 的列名与其中指标一致，但其文件格式、当前窗口与发布时间应分别记录。[V4.5.4，PDF第52页](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260112160427-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6%E6%9C%8D%E5%8A%A1%E8%A7%84%E8%8C%83V4.5.4.pdf#page=52)。

同一规范 PDF 第2页写的是正常情况下 **FTP 数据服务** A股文件18:00前、债券文件20:00前对外发布，迟延时通知用户。这是服务时限和迟延可能性，不是本次官网 XLS/JSON 的首次发布时间，也不能移植为 TuShare 每条历史观测的 `public_available_at`。[V4.5.4，PDF第2页](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260112160427-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E6%95%B0%E6%8D%AE%E6%96%87%E4%BB%B6%E6%9C%8D%E5%8A%A1%E8%A7%84%E8%8C%83V4.5.4.pdf#page=2)。

行业计算说明 V1.1 确实给出静态、滚动 PE 和 PB 的财报切换、亏损筛除等细则；但文档对象是**行业指标**。本次没有取得把它明确适用于上述三个指数及当前网页列的官方说明，故不把其中规则直接纳入指数认证。每日指数信息 JS 还含剔除亏损股票、采用最新财报净资产等说明文字，但它们位于页面说明区域，仍不足以补齐各接口完整算法。

行情传输规范 2.2 的 PDF 第5–7页区分交易日 `JYRQ`、北京时间自然日 `JSRQ`、更新时间 `GXSJ`，并定义收盘值、成交量和成交金额；没有 PE、PB、换手率。它说明官方有精确时间字段的交付形式，但本次没有取得含这些字段的实际当日行情文件，也没有调用该服务。[行情传输规范](https://oss-ch.csindex.com.cn/technical-documentation/cms_add/20260803092336-%E4%B8%AD%E8%AF%81%E6%8C%87%E6%95%B0%E8%A1%8C%E6%83%85%E4%BC%A0%E8%BE%93%E6%8E%A5%E5%8F%A3%E8%A7%84%E8%8C%83(2.2).pdf#page=5)。

### 2.4 对现有交付字段的判断

仓库 `tushare_context.py` 的估值路径请求 `index_dailybasic` 并消费 `pe`、`pb`、`turnover_rate`。截至本次读取，`CN_BOND_FULL_PRICE_CNY030` 映射 `index_daily` / `000012CNY030.CSI`。本文件不改该实现。

|目标子字段|已取得的官方锚点|仍缺的具体事实|
|---|---|---|
|300/500/1000 PE|三份日期明确的 P/E1、P/E2 XLS；正式聚合公式；300/500 静态/滚动 JSON 列绑定|TuShare `pe` 对应哪个官方股本和 EPS 口径，负/零利润、财报切换和样本变动规则是否一致|
|300/500 PB|当前 JSON `pb` 与中文市净率列直接绑定|聚合权重、净资产筛除/切换方法、与 TuShare `pb` 等价性及历史发布时间|
|1000 PB|本次无实际官方 PB 样本|真实字段、日期、值、计算定义|
|三个指数 `turnover_rate`|本次未取得官方换手率字段或数值|交易量/金额分子、总/流通/自由流通股本分母、单位、聚合规则、实际样本；不得使用金额 `Turnover` 顶替|
|历史公开时间|已取得当前公开响应、服务器修改时间；官方文件服务时限|实际观测首次发布日期/时间或可适用于该交付的可靠保守规则；交易日期不可冒充发布日期|

TuShare 文档明确标注数据为社区统计计算，同时把 `pe` 与 `pe_ttm`、`turnover_rate` 与 `turnover_rate_f` 分开。其当前文字覆盖清单和示例未证明中证1000覆盖；接口文档也没有给出三个指数的完整聚合算法。第一阶段没有调用账户 API，也没有做实际交付样本匹配；后续只读比较结果见第五节。[TuShare官方说明](https://tushare.pro/document/2?doc_id=128)。

## 三、CNY030 的有界检索及真实失败证据

|请求 / 来源|UTC取回或尝试开始时间|实际结果|原始 SHA-256|
|---|---|---|---|
|[000012 派生列表](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012)|10:24:00.448868|358 bytes；`000012CNY030` 对应国债指数(全) / Government Bond Index (Full)|`0182843a2d891af5ab5cbb822ec2347a6742bce8493a04b49283004e88e6ffb8`|
|[000012 下载元数据](https://www.csindex.com.cn/csindex-home/indexInfo/index-details-data?indexCode=000012&fileLang=2)|10:21:55.414458|1635 bytes；“指数单张”明确列出 CNY030 专属文件路径|`4e59132fa2f6cb5f04f9367cdffe0124e485e1912c98a8c90bff092c6457b7c9`|
|[CNY030 日线，20260904](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20260904&endDate=20260904)|10:21:55.724859|55 bytes；HTTP成功且业务200，但 `data=[]`|`8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb`|
|[CNY030 日线，20180601–20181231](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20180601&endDate=20181231)|10:25:09.103593|55 bytes；`data=[]`|`8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb`|
|[CNY030 日线，20250101–20251231](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20250101&endDate=20251231)|10:25:09.115835|55 bytes；`data=[]`|`8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb`|
|[CNY030 收益概览](https://www.csindex.com.cn/csindex-home/perf/get-index-yield-item/000012CNY030)|10:21:55.746669|291 bytes；各身份、日期、区间收益字段均为 null|`94480a80df8c0dda6767c7c2cacc1cb926e81e0062e048a185c8153330202ac0`|
|[CNY030 单日行情](https://www.csindex.com.cn/csindex-home/perf/index-perf-oneday?indexCode=000012CNY030)|10:21:55.740395|115 bytes；`intraDayHeader=null`、`intraDayPerfList=[]`|`c59c79fff31d1f79e08e34e81d142f2422a86d590ff26b132d34de7f16b82952`|
|[官方导出端点](https://www.csindex.com.cn/csindex-home/exportExcel/downloadindex-perf?language=CH)，POST，body见下|10:24:00.290434|3761 bytes；真实 XLSX，工作表 `000012CNY030perf` 只有1行表头，无数据行|`37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07`|
|[CNY030 专属 factsheet](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000012CNY030factsheet.pdf)|尝试开始10:23:06.365201|HTTP 404；没有获得 PDF；错误响应体未保存|无|

导出请求是官网详情组件的 `downLoad` → `indexDetailExport` 真实请求形式，执行的是公开数据导出：

```json
[{"indexCode":"000012CNY030","startDate":"20260309","endDate":"20260904"}]
```

导出文件表头包含日期、指数代码、中英文名称、开高低收、涨跌、涨跌幅、成交量、成交金额（亿元）、样本数量；**没有任何 CNY030 交易日、收盘点位或发布日期**。即使该文件有有效 hash，它也只是失败复核材料，不是成功数值样本。

本次还按官方元数据链接分别尝试 [000300factsheet.pdf](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)、[000905factsheet.pdf](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf)、[000852factsheet.pdf](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000852factsheet.pdf)，尝试开始时间分别为10:23:06.731624、10:23:06.795575、10:23:06.989051，均读取超时，未生成原始 hash。没有用搜索摘要、其他指数 factsheet 或第三方转载充当目标 PDF 原文。

因此，当前可以确认代码名称对应全价派生指数，但不能确认任一有效交易日的官方 CNY030 数值、首次公开时间或其与 TuShare `close` 的实际匹配。不能把 `000012` 母指数、净价 `H00012`、利息指数 `N00012`、10年国债 `930916` 或收益率系列替换为 `000012CNY030`。官方数据文件规范提供的是可进一步申请/取得的服务格式，不代表本次已经拿到该指数的日线文件。

## 四、最小后续补证范围

- CNY030：取得至少一个真实、日期明确且身份完全匹配的官方收盘点位原件，并保留方法、发布日期/时间及交付字段映射；在此之前该指标的官方数值抽样保持未通过。无需把全部历史每日值都做双源匹配。
- 估值：先明确现有 `pe`、`pb`、`turnover_rate` 的既定语义，再补对应官方样本与方法。现有 P/E1/P/E2 XLS 可直接作为来源证据；不应为凑齐认证把 `peg` 改名成 `pe`、把金额改名成换手率，或把股本口径差异视为四舍五入误差。
- 时间与许可：只把本次下载时刻记为实际取得证据，保留原始交易日和服务端修改时间；若要回填历史可用时间，须提供适用交付的发布依据。本次公开读取不证明额外商用或再分发许可，仍受 ADR0013 已确认的本地个人、非商业、不可转让边界约束。

本次补充材料可以进入新的待审来源证据包，但不改变冻结审查结论、现行目录、模型、数据库、点时重放结果或激活状态。

## 五、追加：2026-08-28 TuShare 实际交付与官方同日 XLS 比较

追加日期：2026-09-05。本节读取主执行代理已按授权取得并存入同一 CAS 的三个响应；研究代理仅校验字节与 hash、按 `fields` 解码 `items`，没有读取凭据、重发账户请求或修改原始文件。下表请求元数据及取回时间由主执行代理提供，响应内容已从所列 CAS 文件实际读取并验证。补充前本文件 SHA-256 为 `ab362b6f93d5feaa80d2b08309bc2d72391ed63b36cdfc08f9664d7bc825ad26`。

来源为 [TuShare API](https://api.tushare.pro)，POST；三次均使用 `api_name=index_dailybasic`、`params={"ts_code":"对应代码","trade_date":"20260828"}`、`fields=ts_code,trade_date,pe,pe_ttm,pb,turnover_rate`。本节不记录认证信息。

|请求代码|主执行代理取回时间（2026-09-05 UTC）|实际响应字节|已验证 SHA-256|响应检查|
|---|---|---:|---|---|
|000300.SH|11:56:35.824122|256|`9c7cbd8dfe3152de32df132a16e73013abea10295e9123d3f2af8d2752ffd954`|`code=0`；1条 item；代码和交易日符合请求|
|000905.SH|11:56:35.907309|256|`816fd15e5468bbb98a03605e3140f8056e305a7a67b045cc052eb39b6c0c2be3`|`code=0`；1条 item；代码和交易日符合请求|
|000852.SH|11:56:35.994393|202|`edab244c0df5905c02babd5291c27145a182df970699879134eabcbaad4abd3c`|`code=0`，但 `items=[]`；无任何数值观测|

成功状态码不能代替数据覆盖验证。尤其是中证1000，响应头有六个字段名，但没有对应数据行；这不是六个数值均为零，也不能转成成功的空值观测。三份响应的 `data.count` 都为0，前两份实际 `items` 却各有一行；本节以实际列表及其行内代码、日期判断返回内容，不把 `count` 单独作为存在性依据。

### 5.1 实际数值比较

比较锚点为第二节已保存并验 hash 的三份官方 XLS，逐一选择其 `日期Date=20260828` 的行。没有拿2026-09-04的 dashboard 值比较2026-08-28的 TuShare 值，也没有用未保存的历史 JSON 替代原始证据。本节没有新增网络请求。

|指数 / 同一交易日2026-08-28|TuShare `pe`|官方 XLS P/E1（总股本）|差值：TuShare `pe` − P/E1|官方 XLS P/E2（计算用股本）|差值：TuShare `pe` − P/E2|
|---|---:|---:|---:|---:|---:|
|沪深300|14.7661|14.75|+0.0161|17.10|−2.3339|
|中证500|38.9664|29.23|+9.7364|31.46|+7.5064|
|中证1000|无返回行|33.30|不可计算|34.49|不可计算|

单位均为市盈率比值（倍）；上述差值只是数值诊断，**不预设 TuShare `pe` 已与任何一个官方字段语义等价**。即使把前两条 TuShare `pe` 四舍五入到官方显示的两位小数，也分别为14.77、38.97，与官方同日 P/E1、P/E2 均不相同。因而本次样本不能通过“只是两位与四位小数显示精度差异”的解释。未取得计算口径或修订依据，不能反推差异由亏损股剔除、EPS时点、样本范围或权重中的哪一项造成。

官方原始文件引用：沪深300 [000300indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000300indicator.xls)，hash `677773b60a9aa22e51e162e3b8f6549c16c6913eff02d31c6103a840909e6123`；中证500 [000905indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000905indicator.xls)，hash `7a7d915fb5ee56c1fe076fd01dcd0b548ab0a65978059dd9780493ee268dad4e`；中证1000 [000852indicator.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000852indicator.xls)，hash `a15cea8ce2a93f1090dab96ea3e2434acd392a855d9e3bb95161989e7c90706e`。取回时间、服务端修改时间与完整字段限定见2.2节。

|指数 / 同一交易日2026-08-28|TuShare `pe_ttm`|TuShare `pb`|TuShare `turnover_rate`|本节同日官方锚点状态|
|---|---:|---:|---:|---|
|沪深300|13.8377|1.4554|0.5401|已保存 XLS 没有这三个对应字段；不判为通过|
|中证500|34.1372|2.4599|1.5455|已保存 XLS 没有这三个对应字段；不判为通过|
|中证1000|无返回行|无返回行|无返回行|交付本身没有该日观测；不判为通过|

`pe_ttm`、`pb` 的字段定义为比值；`turnover_rate` 在本次原始响应没有单位元数据，官方文档该行也仅写换手率，尚不能依靠响应数值大小决定按百分数或小数比率转换。没有同日、同口径官方值的字段，结论是**未验证**，不是数值已不匹配；中证1000则进一步存在该次请求**无交付观测**的事实。不能把 XLS 的 P/E1/P/E2 与 `pe_ttm` 强行对齐。

### 5.2 发布时间与认证结论

这三份 TuShare 响应只有交易日，没有首次发布日期或时间字段。主执行代理取回时刻证明2026-09-05取得这些返回内容，不能证明数值在2026-08-28几点已可用，也不能证明当前返回的是当时未修订版本。官方 XLS 的服务器修改时间同样不能补成历史交易日的实际发布时间。

本次实际抽样使缺口更具体：沪深300、中证500的交付 `pe` 与同日两种官方 PE 均有未解释差异；中证1000在这个已执行请求中缺行；其余三个子字段缺同日官方验证和完整语义映射。因此不能据这组三次 `code=0` 响应认证完整 `index_valuation` family，也不能宣称中证1000永远不被接口支持。下一步需要能解释并验证既定交付语义的证据与覆盖修复，不能替换原始值、补造空值或把官方近义指标写回成 TuShare 原值。本节不改变任何目录、模型、代码、数据库或激活状态。
