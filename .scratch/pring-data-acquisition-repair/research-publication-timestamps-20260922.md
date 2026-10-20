Status: assessment-only
Type: read-only-probe
Date: 2026-09-22

# 发布时间戳可得性探查：五个发布者、一个交易日

探查窗口：2026-09-22 05:48–06:02 UTC（北京时间 13:48–14:02）。目标交易日固定为 **2026-09-21（周一）**：探查时 A 股尚未收市，2026-09-22 的日终值尚不存在，故最近一个完整交易日是 09-21。本文只做只读网络探查，不签发认证，不写库，不改 `src/`、`tests/`、`tools/` 或任何票，未运行应用测试。

本文回答两个问题：**Q-A** 发布者是否对某个"日频值"提供带**发布时间戳**的公开制品（`trade_date` / 统计日不算）；**Q-B** 若有，能回溯多久。

**结果：五个发布者里只有两个（南华期货、中债）提供真正意义上的逐件首发时间戳，上交所融资提供一个可用但正在被侵蚀的时间戳，中证指数的日收盘和深交所融资则完全没有，CNY030 连制品本身都不存在。更重要的是本次量到了各来源时间戳的"保质期"，从 6 年到 1 个交易日不等，且已经观察到两次发布者批量抹除历史时间戳的事实。证据确实会过期，而且过期速度差三个数量级。**

## 0. 判断口径

算作发布时间戳的：制品自身的 HTTP `Last-Modified`（且该制品是按日固化、不被覆盖的）、发布者自有列表/CMS 给出的 `createTime` / `DOCFIRSTPUBTIME`、页面上可见的"发布时间：…"、按日命名的 URL 从 404 变 200 的可观测跃迁。

不算作发布时间戳的：`tradeDate` / `opDate` / `txtDate` / 标题里的统计日；本次响应的 HTTP `Date`；本机接收时间；按需生成文件内部的 `dcterms:created`（那是生成时刻，不是发布时刻）；指数 `publishDate` 基本信息（那是指数推出日）。

全程用普通浏览器 UA 与必要 `Referer`，未尝试绕过访问控制、未读取任何凭据、未调用账户 API、未访问会员服务。按团队指示未在北交所上花费精力。

## 1. 中证指数公司 — 000985 中证全指日收盘

| 制品 / 官方 URL | 本次实际结果 | 是否带发布时间戳 |
|---|---|---|
| [日线区间接口](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260915&endDate=20260922&lang=zh_CN) | HTTP 200，5 行，末行 `tradeDate=20260921`、`close=5921.92`；**20260922 未出现**。响应头只有 `Date`、CORS、`P3P`，**无 `Last-Modified`、无 `ETag`** | 否。逐行字段为 `tradeDate…peg`，没有任何发布时刻或版本字段 |
| [当日分时接口](https://www.csindex.com.cn/csindex-home/perf/index-perf-oneday?indexCode=000985&lang=zh_CN) | HTTP 200，682 个 tick，`tradeTime` 09:30:11 → 13:50:27，秒级；`intraDayHeader.closePre=5921.92` 与 09-21 收盘一致 | **只对"今天"有效**。显式传 `tradeDate=20260921` 被忽略，仍返回 2026-09-22。会话中每个 tick 的 `close` 均为 `0.0` |
| [自动文件 perf/000985perf.xls](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/perf/000985perf.xls) | HTTP 200，17920 字节，`Last-Modified: Sat, 30 Nov 2024 12:31:06 GMT`。解析后只有 24 行，日期区间 **2021-07-27 至 2021-08-27** | 该制品已废弃五年，其 `Last-Modified` 与任何当前日收盘无关 |
| [事实表 PDF](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000985factsheet.pdf) | HTTP 200，`Last-Modified: Wed, 02 Sep 2026 13:10:59 GMT` | 月频制品。可给月末材料定日期，不能给逐日收盘定发布时刻 |
| [基本信息](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000985?lang=zh_CN) | `publishDate: "2011-08-02"` | 这是指数推出日，与 research-04 第 4 节结论一致，不是日频发布时间 |

**分时接口是本次唯一的正向线索，但它恰好证明了反面。** 它确实给出了官方自己的秒级钟点，可是只覆盖当天；09-21 的 tick 序列今天已经取不到了。也就是说：若要用它给某日收盘定发布时刻，必须在当天收市后、次日开盘前抓取，且本次因探查发生在 13:50（未收市）而**无法核实收市后该接口是否会出现一个带非零 `close` 的终值 tick**——这一点列入"未核实"。

尝试过的 [公告列表接口](https://www.csindex.com.cn/csindex-home/announcement/selectNoticeRe)（GET 与 JSON POST 两种）均返回 `{"code":"500","msg":"服务器异常,请联系管理员"}`，未取得带发布日期的公告清单，记为无法判定。

## 2. 上交所 / 深交所 — 融资余额、融资买入额

两所在这一点上差别极大，必须分开结论。

### 2.1 上交所：有按日固化的制品，且带真实 `Last-Modified`

[上交所按日融资融券文件](https://www.sse.com.cn/market/dealingdata/overview/margin/a/rzrqjygk20260921.xls) 是本次全部探查里结构最理想的制品：**URL 里带日期，因此按日固化、互不覆盖**。

| 项 | 本次实际结果 |
|---|---|
| HTTP / 字节 | 200 / 480768，SHA-256 `c86f9c55529b820e2a2a93e348f76fb348631b33ce0b935bb0930f8be74707c7` |
| `Last-Modified` | `Mon, 21 Sep 2026 23:40:02 GMT` = **北京时间 2026-09-22 07:40:02** |
| 工作表 | `汇总信息`、`明细信息`（2003 行） |
| 汇总值（元） | 本日融资余额 `1339890337610`、本日融资买入额 `94642003793` |
| 与 [汇总接口](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260921&endDate=20260921&isPagination=false) 比较 | `rzye`、`rzmre` 元级完全相同；但该接口响应**无 `Last-Modified`** |
| [次日文件](https://www.sse.com.cn/market/dealingdata/overview/margin/a/rzrqjygk20260922.xls) | **HTTP 404** |

07:40 与北交所业务指南 7.1 "每交易日开市前公布前一交易日市场总量"的制度窗口相容（见 research-05 第 4.2 节），但这里是上交所实测文件时间，不是把制度条文当成发生事实。09-22 文件当前 404，说明 404→200 的跃迁本身是一个可观测的发布事件。

**保留一项已知弱点：该 xls 内部没有日期单元格。** `汇总信息` 表只有表头行、数值行和第 17 行的切换提示，日期身份完全依赖 URL 文件名——与 research-05 第 3 节对深交所 Excel 的判断是同一类问题，不因为有了时间戳而消失。

**Q-B 的答案是本文最关键的量化结果。** 文件本身回溯极深，但时间戳不然：

| 统计日 | HTTP | `Last-Modified` | 判读 |
|---|---|---|---|
| 2026-09-21 | 200 | Mon, 21 Sep 2026 23:40:02 GMT | 真实，次日 07:40 北京 |
| 2026-09-11 | 200 | Sun, 13 Sep 2026 23:40:02 GMT | 真实，下一交易日 07:40 |
| 2026-08-28 | 200 | Sun, 30 Aug 2026 23:40:02 GMT | 真实 |
| 2026-03-09 | 200 | Mon, 09 Mar 2026 23:40:00 GMT | 真实 |
| 2025-12-15 | 200 | Mon, 15 Dec 2025 23:40:10 GMT | 真实 |
| 2025-09-02 | 200 | Tue, 02 Sep 2025 23:40:08 GMT | 真实 |
| 2025-07-15 | 200 | Tue, 15 Jul 2025 23:40:10 GMT | 真实 |
| 2025-06-30 | 200 | Mon, 30 Jun 2025 23:40:10 GMT | 真实 |
| **2025-06-27** | 200 | Sun, 29 Jun 2025 23:40:10 GMT | **真实，最早的一个** |
| 2025-06-20 | 200 | Fri, 27 Jun 2025 06:08:13 GMT | **已被抹除** |
| 2025-05-06 | 200 | Fri, 27 Jun 2025 06:08:20 GMT | 已被抹除 |
| 2025-01-02 | 200 | Fri, 27 Jun 2025 06:08:00 GMT | 已被抹除 |
| 2024-09-02 | 200 | Fri, 27 Jun 2025 06:09:02 GMT | 已被抹除 |
| 2022-09-02 / 2020-09-02 / 2018-09-03 / 2015-09-02 / 2012-09-03 / 2010-09-02 | 200 | 均为 Fri, 27 Jun 2025 06:0x GMT | 已被抹除 |

（2025-06-02 返回空，该日为端午休市，与只有交易日才有文件相符。）

界线干净利落：**2025-06-27 及以后逐日真实；2025-06-26 及以前，全部被 2025-06-27 当天一次站点迁移统一覆盖成 `2025-06-27 06:0x GMT`。** 数值文件回溯到至少 2010-09-02 依然可下载，但那些日子的发布时刻已经**永久丢失**。按今天算，可用时间戳的深度约 **15 个月**。

### 2.2 深交所：数值回溯到 2010 年，发布时间戳一个都没有

| 制品 / 官方 URL | 本次实际结果 | 是否带发布时间戳 |
|---|---|---|
| [JSON 报表](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-09-21&tab1PAGENO=1) | HTTP 200，8384 字节，`metadata.subname=2026-09-21`；响应头**无 `Last-Modified`、无 `ETag`** | 否 |
| [XLSX 导出](https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1837_xxpl&txtDate=2026-09-21&TABKEY=tab1) | HTTP 200，3707 字节；融资买入额 `91,253,970,396` 元、融资余额 `1,274,557,604,699` 元 | 否。`docProps/core.xml` 的 `dcterms:created` 为 **2026-09-22T05:52:36Z**，即本次抓取时刻；ZIP 成员时间同为本次。与 research-05 第 3.1 节判断一致：按需生成，非发布事件 |
| [披露页](https://www.szse.cn/disclosure/margin/margin/index.html) | HTTP 200，`Last-Modified: Sat, 29 Aug 2026 03:10:40 GMT` | 否。这是栏目模板页的时间，与任何一天的数值无关 |

数值深度已实测：`txtDate` 取 2026-09-21、2026-03-09、2025-06-26、2024-01-04、2020-01-02、2015-01-05、2011-01-04、2010-04-01 均返回 1 行有效数据（2010-04-01 为融资融券开闸初期的 `jrrzye=0.06` 亿元）。**即数值回溯到 2010-04-01，而发布时间戳深度为 0。**

尝试过的 [深交所检索接口](https://www.szse.cn/api/search/content?SEARCH_TYPE=1&keyword=%E8%9E%8D%E8%B5%84%E8%9E%8D%E5%88%B8&PAGENO=1) 返回 50x 维护页，未取得带发布时间的公告清单，记为无法判定。

**合计口径的后果：** 三所合计的 PUBLIC 边界不早于其中最晚的一个输入。深交所既然没有任何发布时刻，`financing_balance` / `financing_buy_amount` 的合计标量在目前证据下仍然不可定时——上交所那份质量很高的时间戳救不了合计。这与 research-05 第 6 节的结论方向一致，本次只是把"深交所到底有没有"这一条从未查证变成了已查证为无。

## 3. 中证指数公司 — 000300 / 000905 / 000852 日频估值

本项须先说明一处口径落差：本仓库 [`tushare_context.py:59-64`](../../src/pring_cycle/tushare_context.py#L59) 要求的字段是 **`pe`、`pb`、`turnover_rate`** 三项。本次在中证官方侧找到的东西并不覆盖这三项。

| 官方制品 | 覆盖指数 | 实际字段 | 历史深度 | 发布时间戳 |
|---|---|---|---|---|
| [自动文件 `indicator/<code>indicator.xls`](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000300indicator.xls) | 000300 / 000905 / 000852 / 000985 均有（000012 为 404） | `市盈率1(总股本)`、`市盈率2(计算用股本)`、`股息率1`、`股息率2` —— **无 PB、无换手率** | **固定 URL，滚动 20 个交易日**：本次为 20260825 → 20260921 | HTTP `Last-Modified`，见下 |
| [最新估值快照](https://www.csindex.com.cn/csindex-home/data-service/indexValuation?indexCode=000300&lang=zh_CN) | 仅 8 条，含沪深300、中证500；**不含中证1000** | `pe`、`peg`、`pb`、`dp` —— 有 PB，**无换手率** | **只有最新一个交易日**（`tradeDate=20260921`） | 无 `Last-Modified`，无 `ETag`，无任何时刻字段 |
| [PEG 历史](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000300&lang=zh_CN) | 000300 | 仅 `peg`（滚动市盈率） | 回溯至 **20110628** | 无 |

本次解析出的实值（供交叉核对）：000300 于 20260921 的 `市盈率1=14.73`，与快照接口的 `pe=14.73` 一致；000905 `29.94`；000852 `34.76`；000985 `19.74`。四个 xls 的 SHA-256 分别为 `760197…`、`822b00…`、`15b28c…` 及 000985 一份。

**关于 `indicator` 文件的 `Last-Modified`，必须如实报告两种读法。** 实测值：000300 `Tue, 22 Sep 2026 03:30:25 GMT`、000905 `03:31:11`、000852 `03:31:18`、000985 `03:31:15`，即北京时间 2026-09-22 11:30–11:31 的一次批处理；而四份文件的最新行都是 **09-21**。

- 读法甲：该批处理每日运行一次、写入前一交易日的行，则 11:30 就近似是 09-21 估值在此渠道的公开时刻。
- 读法乙：该文件每日被原地重写，11:30 只是最近一次重写时刻，09-21 的值可能在 09-21 傍晚就已在文件中，那个更早的 `Last-Modified` 已被覆盖。

**本次无法在甲乙之间裁决**，因为只有单点观测。05:48Z 与 06:01Z 两次取回的 `ETag`、`Last-Modified` 与字节完全相同，与"每日一次"相容但不构成证明。

然而**两种读法导出同一个致命结论**：文件位于固定 URL，只保留约 20 个交易日，且每次重写都销毁上一个 `Last-Modified`。**任何一天的估值发布时刻，最多只能在其后约 1 个交易日内被观测到。** 这是本次五个来源中保质期最短的一个。

综上：PE 有一个寿命约一个交易日的时间戳；PB 只有当日快照且中证1000 缺失，谈不上历史时间戳；**换手率在本次探查到的所有中证官方接口与自动文件中均未出现**。

## 4. 南华期货 — 南华商品指数日报 / NHII

这是五个来源里证据质量最高的一个，而且**两个互相独立的发布者侧时间戳可以互证**。

| 证据 | 官方 URL | 本次实际结果 |
|---|---|---|
| 日报列表 JSON | [type=404205, limit=2000](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=404205&start=0&limit=2000) | HTTP 200，803688 字节，`totalCounts=1458`、`totalPages=1`，一次返回全部 1458 条 |
| 目标条目 | `newsId=943264f1-6a3f-40a8-ae1b-f2df5de0d064` | `subject=南华商品指数日报20260921`、`author=指数组`、`typeName=指数日报`、**`createTime=2026-09-21 16:13:07`** |
| 文章页 | [/news/2026/09/943264f1….html](https://www.nanhua.net/news/2026/09/943264f1-6a3f-40a8-ae1b-f2df5de0d064.html) | 页面正文可见 **"发布时间：2026-09-21 16:13:07"** |
| 日报 PDF | [南华商品指数日报20260921.pdf](https://www.nanhua.net/cmsbigfile/2026/09/943264f1-6a3f-40a8-ae1b-f2df5de0d064/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260921.pdf) | HTTP 200，1165307 字节，9 页，SHA-256 `5463a4f81b43ed54162fd325c30962cead69718a312cf0c86bc12c7df27bfa5d`，**`Last-Modified: Mon, 21 Sep 2026 08:14:01 GMT` = 北京时间 16:14:01** |
| 内容绑定 | PDF 第 1 页 `Index Market Data` | 正文自带日期 `(2026 9 21)`；**`NHII / Today Close = 4132.16`**，`Pre.Close = 4113.38` |

列表 `createTime` 16:13:07 与 PDF `Last-Modified` 16:14:01 相差 54 秒——与 research-04 第 4 节在 2026-08-28 观察到的 51 秒同型（先建文章、后传附件）。**这不是缺陷，而是两个独立时间源互相佐证；保守取值应取两者之晚者。**

**Q-B：PDF 的 `Last-Modified` 完整保存到 2020 年，未被迁移抹除。** 逐年实测：

| 列表 `createTime` | PDF `Last-Modified`（GMT） | 换算北京时间 | 差 |
|---|---|---|---|
| 2026-09-21 16:13:07 | Mon, 21 Sep 2026 08:14:01 | 16:14:01 | +54s |
| 2026-06-01 16:51:36 | Mon, 01 Jun 2026 08:52:15 | 16:52:15 | +39s |
| 2025-09-22 17:00:24 | Mon, 22 Sep 2025 09:00:59 | 17:00:59 | +35s |
| 2024-09-23 16:59:58 | Mon, 23 Sep 2024 09:13:15 | 17:13:15 | +13m17s |
| 2023-09-22 16:13:24 | Fri, 22 Sep 2023 08:14:32 | 16:14:32 | +68s |
| 2022-09-22 16:33:15 | Thu, 22 Sep 2022 08:35:08 | 16:35:08 | +113s |
| 2021-09-22 17:01:29 | Wed, 22 Sep 2021 09:02:57 | 17:02:57 | +88s |
| 2020-07-02 17:04:28 | Thu, 02 Jul 2020 09:06:00 | 17:06:00 | +92s |

八个年度抽样全部命中、全部当日、全部次序正确。列表最早一条为 **2020-07-02**，最晚 **2026-09-21**，跨度 **6 年 2 个多月**。

两点如实保留。其一，**列表并不逐日齐全**：逐年条数为 2020=124、2021=240、2022=235、2023=238、2024=230、2025=223、2026(至 09-21)=168，低于同期交易日数，与 research-04 在 120 个目标日中实测缺 6 日同型。其二，1458 条记录中 `updateTime != createTime` 的**有 0 条**，即列表未暴露任何修订信号——这既不能证明从未修订，也不能当作修订账本。

## 5. CNY030 全价 —— 先更正发布者归属

**任务把 CNY030 归给"中债估值中心 / 上清所"，但本仓库自己的映射不是这样。** [`tushare_context.py:55`](../../src/pring_cycle/tushare_context.py#L55) 将 `CN_BOND_FULL_PRICE_CNY030` 映射为 `("index_daily", "000012CNY030.CSI")`，[`catalog.py:228`](../../src/pring_cycle/catalog.py#L228) 同。research-06 第 3 节已考据其官方身份为中证[衍生指数列表](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012)中的 `000012CNY030`／国债指数（全）／Government Bond Index (Full)，属**中证指数—上交所**体系，与中债估值中心或上清所无关。下面两部分分别作答。

### 5.1 精确代码 000012CNY030：没有制品，因此 Q-A 不成立

| 官方 URL | 本次实际结果 |
|---|---|
| [日线区间](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20260901&endDate=20260922&lang=zh_CN) | HTTP 200，`{"code":"200","msg":"Success","data":[],"success":true}` —— **空数组** |
| [基本信息](https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info/000012CNY030?lang=zh_CN) | HTTP 200，`data` 对象 **29 个字段全部为 null** |

与 research-06 第 3 节、[cny030-official-followup-20260909.md](cny030-official-followup-20260909.md) 的结论一致，本次未出现任何变化。**没有任何承载该日数值的公开制品，就谈不上该制品上的发布时间戳。** Q-A 对 CNY030 的答案不是"有时间戳"或"没时间戳"，而是**连被打时间戳的对象都不存在**。

### 5.2 中债估值中心：自身有很好的首发时间戳，但与 CNY030 无关

虽然归属有误，仍按要求实查了中债，且结果本身对本项目有价值。

| 证据 | 官方 URL | 本次实际结果 |
|---|---|---|
| 日评文章页 | [t20260921_855419657.html](https://www.chinabond.com.cn/xxwsy/sy_zdgz_ath/202609/t20260921_855419657.html) | 页面可见 **"发布时间：2026年09月21日"** —— **只有日期，没有钟点** |
| 日评附件 | [P020260921667793987177.docx](https://www.chinabond.com.cn/xxwsy/sy_zdgz_ath/202609/P020260921667793987177.docx) | HTTP 200，1048807 字节，SHA-256 `8793d2d0…`，**`Last-Modified: Mon, 21 Sep 2026 10:33:22 GMT` = 北京 18:33:22** |
| CMS 列表接口 | `POST https://www.chinabond.com.cn/cbiw/trs/content/page`（`channelId=207`） | HTTP 200，`total=10858`、`pages=543`。每条记录带 **`DOCFIRSTPUBTIME`、`DOCPUBTIME`、`CRTIME`、`OPERTIME`、`DOCRELTIME`、`ShengXiaoShiJian`**，均为秒级 |
| 目标条目 | 《中债收益率曲线和指数日评2026年09月21日》 | **`DOCFIRSTPUBTIME = 2026-09-21T18:33:23`**，与附件 `Last-Modified` 仅差 1 秒 |

有一个显式的"**首次发布时间**"字段与"发布时间"字段分开，这在五个来源里是独一份，理论上具备修订识别能力。

**但 Q-B 同样暴露了批量抹除，而且抹了两次：**

| 抽样（标题日期 → `DOCFIRSTPUBTIME`） | 判读 |
|---|---|
| 2026年09月21日 → 2026-09-21T18:33:23 | 真实 |
| 2025年01月20日 → 2025-01-20T20:16:26 | 真实 |
| 2023年10月31日 → 2023-10-31T18:56:38 | 真实 |
| 2023年09月06日 → 2023-09-06T18:19:31 | 真实 |
| 2023年08月04日 → 2023-08-04T18:00:08 | 真实 |
| 2023年07月21日 → 2023-07-28T23:19:44 | 迁移后补录，已偏 7 天 |
| 2023年04月27日 → **2023-07-18T20:58:50** | **已被抹除** |
| 2021年9月30日 → **2023-07-18T21:05:01** | 已被抹除 |
| 2020年7月22日 → **2023-07-18T21:10:54** | 已被抹除 |
| 2009年01月12日 → **2023-07-17T11:27:43** | 已被抹除（列表最末页） |

第一次抹除：**2023-07-17/18** 的一次 CMS 迁移，把此前全部记录的 `DOCFIRSTPUBTIME` 压成迁移当天。第二次抹除：所有较早记录的 `DOCPUBTIME` 被统一改写为 **2025-10-24**（例如 2025-01-20 那条，`DOCFIRSTPUBTIME` 仍真实，`DOCPUBTIME` 已是 2025-10-24T18:48:55）。

所以：日评按标题可回溯到 **2009-01-09**（共 10858 条），而**可信首发时间戳只回溯到约 2023 年 7–8 月，约 3 年**。

另需明确两点。其一，**该日评不含 CNY030**：正文给的是中债综合指数（净价）108.6384、（财富）262.9598 及各期限收益率曲线，与 `000012CNY030` 不是一个东西。其二，**不要用文档内部元数据**：同日另一份附件（中债公募REITs日报）的 `docProps/core.xml` 显示 `dcterms:created=2022-08-29`、`dcterms:modified=2025-03-21`、`cp:revision=80`，明显是长期复用的模板属性，与 2026-09-21 的发布毫无关系。只有 HTTP `Last-Modified` 与 CMS 的 `DOCFIRSTPUBTIME` 是可用的。

### 5.3 上清所：站点可达，但数据入口未取得

[上清所首页](https://www.shclearing.com.cn/) 与 [指数信息披露栏目](https://www.shclearing.com.cn/xxpl/zsxxpl/) 均 HTTP 200。但该栏目页正文由脚本动态装载，且页面引用 `ase.js`、`crypto-js.js`、`base64.js`、`md5.js`——存在加密/混淆层。本次在未尝试绕过的前提下**未能定位其数据接口**，因而**没有取得任何上清所日频制品**，Q-A / Q-B 对上清所记为**无法判定**，不是"没有"。栏目 HTML 的 `Last-Modified` 显示为本次访问时刻（`Tue, 22 Sep 2026 05:45:21 GMT`），属动态生成，无参考价值。

## 6. 裁决

### 能取到发布时间戳？可回溯多久？

| # | 发布者 / 日频值 | **能取到发布时间戳？** | **可回溯多久？** | 依据 |
|---|---|---|---|---|
| 1 | 中证 — 000985 日收盘 | **不能** | 数值回溯多年；**时间戳 0 天**。当日分时 `tradeTime` 只在当天可得，次日即不可回溯 | 第 1 节 |
| 2a | 上交所 — 融资余额 / 买入额 | **能** | **约 15 个月**（2025-06-27 起真实；此前全被 2025-06-27 迁移覆盖）。数值文件本身回溯至少到 2010-09-02 | 第 2.1 节 |
| 2b | 深交所 — 融资余额 / 买入额 | **不能** | **0 天**。数值回溯至 2010-04-01，发布时间戳一个都没有 | 第 2.2 节 |
| 3 | 中证 — 000300/000905/000852 估值 | **部分，且极短命**：PE 有（`indicator` 文件 `Last-Modified`）；PB 无历史时间戳且 000852 缺；**换手率本次未找到任何官方发布** | **PE 约 1 个交易日**（固定 URL 原地重写，旧时间戳即刻销毁，文件仅存 20 个交易日）；PB 仅最新 1 日快照；换手率 N/A | 第 3 节 |
| 4 | 南华 — NHII 日报 | **能**，且双时间源互证（列表 `createTime` + PDF `Last-Modified`，相差数十秒） | **约 6 年 2 个月**（2020-07-02 起，逐年抽样全部保真）。但列表逐年条数低于交易日数，存在缺日 | 第 4 节 |
| 5 | CNY030 全价 | **不能 —— 且属于"无制品"而非"制品无时间戳"**。中债自身能（`DOCFIRSTPUBTIME`，约 3 年），但其日评不含 CNY030；上清所**无法判定** | CNY030 本身：0。中债日评：标题可回溯至 2009-01-09，可信首发时间戳约 3 年 | 第 5 节 |

### 证据是否会过期？——这一段直接决定排期

**会过期，而且过期速度相差三个数量级；更要紧的是，已有两个发布者被实测到会追溯性地批量抹除历史时间戳。**

把本次量到的保质期排成一行：南华 **约 6 年** → 中债 **约 3 年** → 上交所融资 **约 15 个月** → 中证估值 **约 1 个交易日** → 中证日收盘 / 深交所融资 / CNY030 **从来没有**。

对项目的三条推论：

其一，**中证估值必须当日或次日抓取，否则永久丢失发布时刻。** `indicator` 文件是固定 URL 原地重写、只留 20 个交易日；任何一天的 `Last-Modified` 在下一次重写时被销毁。这一项没有任何补救窗口，历史补抓在原理上不可能。

其二，**"现在还够用"不等于"以后还够用"。** 上交所把 2025-06-26 及以前逐日文件的 `Last-Modified` 统一压成 `2025-06-27 06:0x GMT`；中债把 2023-04-27 及以前的 `DOCFIRSTPUBTIME` 压成 `2023-07-18`，又把较早记录的 `DOCPUBTIME` 统一压成 `2025-10-24`。这三次都是站点迁移/重构的副作用，事前无预警。所以上交所那 15 个月、中债那 3 年、南华那 6 年，都可能被下一次迁移一次性清零。**唯一安全的策略是"取到即固化"——把发布者侧时间戳连同字节一起落成不可变证据，而不是依赖它将来还在原地。**

其三，**对完全没有时间戳的三项（000985 日收盘、深交所融资、CNY030），排期救不了。** 它们缺的不是抓取时机，而是发布者根本不发布这个事实。唯一可能的前向路径是**自建发布观测**：例如按分钟轮询 `index-perf` 或 SSE 的按日 URL，记录其从"无该日行"到"有该日行"、或从 404 到 200 的跃迁时刻。那产出的是**本系统观测到的可得时刻（SYSTEM）**，按 ADR-0006 的双 as-of 口径不能充作发布者的 PUBLIC，且只对**未来**的日子有效，对固定的 2026-03-09 至 2026-08-28 窗口毫无帮助。这一点必须在排期里说清楚，不能让"以后能观测"掩盖"历史永远拿不到"。

## 7. 未核实 / 无法判定

以下条目本次**没有**得到证据，按要求显式记录，不作推断：

1. **中证分时接口在收市后的形态未核实。** 探查发生于北京时间 13:50（未收市），`intraDayPerfList` 中每个 tick 的 `close` 均为 `0.0`。收市后是否会出现一个带非零 `close` 的终值 tick、其 `tradeTime` 是否等于 15:00 或更晚，本次无法验证。
2. **中证 `indicator` 文件的写入节律未裁决。** 第 3 节的读法甲（每日一次写前一日）与读法乙（当日已写、次日重写覆盖）本次无法区分，需要跨日的第二次观测。两种读法不影响"保质期约 1 个交易日"的结论。
3. **中证公告列表接口未取得。** `GET` 与 `JSON POST` 两种方式访问 `/csindex-home/announcement/selectNoticeRe` 均返回 `{"code":"500","msg":"服务器异常,请联系管理员"}`。因此"中证是否有带发布日期的公告归档"记为无法判定。
4. **深交所检索接口未取得。** `https://www.szse.cn/api/search/content?...` 返回 50x 维护页面。深交所是否在别处（如公告栏目）存在带发布时间的归档，本次未能查证。
5. **上清所数据入口未取得。** 栏目页存在 `ase.js` / `crypto-js.js` / `md5.js` 加密层，本次在不尝试绕过的前提下未定位其数据接口。上清所的 Q-A / Q-B 为无法判定，**不可读作"上清所没有"**。
6. **上交所 `Last-Modified` 的语义边界。** 实测的 `23:40:0x GMT` 是服务器文件修改时间，与"该数值首次对公众可见"高度相容但非同一事实；本次没有上交所侧的发布日志或公告来独立佐证。09-22 文件当前 404 只说明此刻未发布，不能反推 404→200 的确切时刻。
7. **南华列表缺日的原因未判定。** 逐年条数低于交易日数（如 2026 年至 09-21 仅 168 个唯一日期），与 research-04 的 6 个缺日同型。缺的是"本次取到的这份官方列表未列出"，**不等于这些日子从未发布过**。
8. **修订账本在所有五个来源均不存在。** 南华 1458 条 `updateTime != createTime` 为 0 条；中债有 `DOCFIRSTPUBTIME` 与 `DOCPUBTIME` 之分但旧记录的后者已被批量改写；上交所、深交所、中证均无任何版本字段。因此本文没有任何来源能回答"某日数值此后是否被修订过"。
9. **北交所未探查。** 按团队指示跳过，research-05 第 4 节记录的 403 阻断状态未复核。
10. **本次未核对 TuShare 侧数值。** 本文只做发布者原生制品探查；文中出现的所有数值均来自本次官方响应，未与库内 `source_claim` 或任何交付渠道比对。

## 8. 本次请求索引

探查时间均为 2026-09-22 UTC。下表只列取得实质内容的请求；第 7 节所列失败请求不重复。

| 请求 / 官方 URL | HTTP / 字节 | 关键发布时间证据 |
|---|---|---|
| [csi-000985-perf](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260915&endDate=20260922&lang=zh_CN) | 200 / chunked | 无（无 `Last-Modified`） |
| [csi-000985-oneday](https://www.csindex.com.cn/csindex-home/perf/index-perf-oneday?indexCode=000985&lang=zh_CN) | 200 / 149449 | `tradeTime` 秒级，仅当日 |
| [csi-000985-perf-autofile](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/perf/000985perf.xls) | 200 / 17920 | `Last-Modified: 2024-11-30`；内容止于 2021-08-27 |
| [csi-000300-indicator](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000300indicator.xls) | 200 / 8192 | `Last-Modified: Tue, 22 Sep 2026 03:30:25 GMT` |
| [csi-000905-indicator](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000905indicator.xls) | 200 / 8192 | `Last-Modified: … 03:31:11 GMT` |
| [csi-000852-indicator](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/000852indicator.xls) | 200 / 8192 | `Last-Modified: … 03:31:18 GMT` |
| [csi-indexValuation](https://www.csindex.com.cn/csindex-home/data-service/indexValuation?indexCode=000300&lang=zh_CN) | 200 | 无；仅 `tradeDate=20260921` |
| [csi-indexCsiDsPe](https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=000300&lang=zh_CN) | 200 | 无；PEG 回溯至 20110628 |
| [csi-cny030-perf](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000012CNY030&startDate=20260901&endDate=20260922&lang=zh_CN) | 200 / 55 | `data:[]` |
| [sse-margin-20260921](https://www.sse.com.cn/market/dealingdata/overview/margin/a/rzrqjygk20260921.xls) | 200 / 480768 | **`Last-Modified: Mon, 21 Sep 2026 23:40:02 GMT`** |
| [sse-margin-20260922](https://www.sse.com.cn/market/dealingdata/overview/margin/a/rzrqjygk20260922.xls) | **404** | 尚未发布 |
| [sse-margin-hz-api](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260921&endDate=20260921&isPagination=false) | 200 / 802 | 无 |
| [szse-margin-json](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-09-21&tab1PAGENO=1) | 200 / 8384 | 无 |
| [szse-margin-xlsx](https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1837_xxpl&txtDate=2026-09-21&TABKEY=tab1) | 200 / 3707 | 无；`dcterms:created` 为本次抓取时刻 |
| [nh-daily-list](https://www.nanhua.net/jSearch/queryNewsListByTypeForJson.shtm?site=newnanhua&type=404205&start=0&limit=2000) | 200 / 803688 | **1458 条 `createTime`，2020-07-02 → 2026-09-21** |
| [nh-daily-20260921-pdf](https://www.nanhua.net/cmsbigfile/2026/09/943264f1-6a3f-40a8-ae1b-f2df5de0d064/%E5%8D%97%E5%8D%8E%E5%95%86%E5%93%81%E6%8C%87%E6%95%B0%E6%97%A5%E6%8A%A520260921.pdf) | 200 / 1165307 | **`Last-Modified: Mon, 21 Sep 2026 08:14:01 GMT`** |
| [nh-daily-20260921-page](https://www.nanhua.net/news/2026/09/943264f1-6a3f-40a8-ae1b-f2df5de0d064.html) | 200 | 正文"发布时间：2026-09-21 16:13:07" |
| [cb-riping-page](https://www.chinabond.com.cn/xxwsy/sy_zdgz_ath/202609/t20260921_855419657.html) | 200 / 22687 | 正文"发布时间：2026年09月21日"（仅日期） |
| [cb-riping-docx](https://www.chinabond.com.cn/xxwsy/sy_zdgz_ath/202609/P020260921667793987177.docx) | 200 / 1048807 | **`Last-Modified: Mon, 21 Sep 2026 10:33:22 GMT`** |
| `POST https://www.chinabond.com.cn/cbiw/trs/content/page`（`channelId=207`） | 200 | **`DOCFIRSTPUBTIME=2026-09-21T18:33:23`**；`total=10858` |
| [shclearing-zsxxpl](https://www.shclearing.com.cn/xxpl/zsxxpl/) | 200 / 31816 | 动态装载 + 加密层，未取得数据接口 |

本次取回的原件保存在会话暂存目录，未写入仓库；文中所列 SHA-256 对应那些副本。若要把这些制品登记为不可变证据，应另起实施票按 CAS 流程固化，本文不代行。
