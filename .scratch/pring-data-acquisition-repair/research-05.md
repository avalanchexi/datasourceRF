# 第 05 票：沪深北融资官方样本与公开时间补证

审查日：2026-09-06，Asia/Shanghai。固定范围：2026-03-09 至 2026-08-28 的 120 个中国交易日、SSE/SZSE/BSE 三所、融资余额和融资买入额两个标量。依据 [规格](spec.md)、[第 05 票](issues/05-margin-certification.md) 和 [ADR-0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)，本研究只补证，不签发认证；不要求所有历史日逐条双来源数值相等，但官方抽样、时间与其他家族条件仍须实际满足。

**结果：三所交付矩阵和沪深四数再次通过只读复核；仍未取得北交所可对账的官方数值原件。北交所本轮直接访问返回 HTTP 403，正常浏览器打开也超时，不能把拒绝页算作融资原件。三所目标期实际公开时间尚未建立，第 05 票不能标记认证完成。**

本次只新增本文和 `evidence-05/`。没有读取密钥、调用账户 API、写生产数据库、改代码、票据状态、旧审查或第 04 票文件，也没有购买或访问会员服务。本次没有运行应用测试、模型回放或候选入库。已保存的 TuShare 原响应来自既有授权采集，只读验证和复用。

## 1. 产物与复核方法

- [本次脱敏请求回执](evidence-05/receipts.json)：8 次直接匿名 HTTP 请求的 URL、公开参数、必要 Referer、开始/接收 UTC 时间、状态、字节数和 SHA-256；没有认证请求体、token、cookie 或账户资料。
- [旧 CAS 原件复制记录](evidence-05/imports.json)：8 份既有原件校验后复制到本研究目录，保留原 CAS 路径、散列和本次校验时间。校验复制时间不是新的网络接收时间。
- [矩阵、四数与文件差异复核](evidence-05/verification-summary.json)：独立解析原始响应、Decimal 算术、逐日三所集合、两字段组合、官方四数比较、全市场差额与深交所 Excel 内部差异。
- [浏览器尝试记录](evidence-05/browser-observation.json)：正常 Chrome 打开公开页的工具超时，不冒充取得页面内容或 HTTP 响应。

成功数据响应和失败 HTTP 响应都按实际收到的内容字节保存并散列；失败页中的网络诊断不作为融资事实。对已有相同散列文件只验证内容，不覆盖。报告不展示错误页附带的网络地址等无关诊断内容。所有本次直接请求设置连接 10 秒、读取 15 秒超时，禁自动跟随重定向，没有循环猜测后台端点或重试请求。

## 2. 120 日三所矩阵：已验证什么

复用 [TuShare 原始区间响应](evidence-05/a03de595618ce8aa3fa74ce97fff980bbbe3e2197e9f5064b7157756dd7b2afd.json)，其字段为 `trade_date,exchange_id,rzye,rzmre`；原请求是 `margin(start_date=20260309,end_date=20260828)`，既有接收时间为 2026-09-05 10:37:48.446971 UTC。本次没有再次发送此账户请求。[原始日历响应](evidence-05/d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635.json)为同范围 `trade_cal(exchange=SSE)`；目标日期也符合 [上交所 2026 年休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml)（[第 04 票已保存原件](evidence-04/11d8a102d0747eaa8e97d9eda71eb9544ce30adbe83c706f7bdc77be4084686b.html)，只读复用）。

| 检查项 | 本次实际结果 |
|---|---:|
| 唯一应有交易日 | 120，首日 2026-03-09、末日 2026-08-28 |
| 原始交易所行 | 360 = 120 × 3 |
| 每日恰好 `{SSE,SZSE,BSE}` | 120 / 120 日 |
| 缺成员 / 缺整日 / 额外日期或交易所 | 均为 0 |
| 重复 `(trade_date,exchange_id)` | 0 |
| `rzye,rzmre` 非有限、负数或缺值 | 0 |
| 应有合计标量 | 240 = 120 × `{financing_balance,financing_buy_amount}` |
| 本研究授予认证 / 写库 / 重放 | 均未发生 |

复核以完整日期×交易所笛卡尔积比较键集合，再检查每个键计数为 1；不是只看 360 行总数。两个指标分别对三所求和，再除以 `100000000` 将元转换为亿元，`scope=SSE+SZSE+BSE`；没有混入融券余额、融资融券总余额、偿还额或市场残差。逐日算术和成员键已保存在复核 JSON，**它是研究计算明细，不是新来源声明或已验证模型输入**。

[TuShare margin 官方文档](https://tushare.pro/document/2?doc_id=58)（[本次 HTML 原件](evidence-05/9f84649b54199c0f4d89dbb2cfd4235ac7ef816aab2f8d2dcd5867f6a32a1e7c.html)）明确 SSE/SZSE/BSE 标识，`rzye` 和 `rzmre` 单位均为元，单次最多 4000 行。这个上限与已验证的 360 行矩阵相容，但上限本身不证明完整性，也不证明北交所官方值已经对账。

既有 [候选清单原件](evidence-05/c0bbdf18fa19fcf0a2025b602c7a57f7317e60822b54ac90ff3fc11fd3d5dc6f.json)记录 `margin-financing-v0002`、240 条未知公开时间观测、`public_as_of_points=0`。本次只核验其内容和输入算术，没有重新运行该隔离运行时或把旧清单的测试结果冒充本次应用验收。现实现定位可查 [候选入口](../../src/pring_cycle/tushare_context.py#L713)；代码变化及入库行为由实施票单独负责。

## 3. 沪深四数：保留旧原件，并实际重新取回

本次匿名重新请求同一 2026-08-28 官方报表，结果如下。比较值来自旧 [TuShare 单日原响应](evidence-05/3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548.json)，也与区间响应对应行相同。

| 交易所 / 字段 | 官方值，元 | TuShare 值，元 | 结论 |
|---|---:|---:|---|
| SSE 融资余额 `rzye` | 1,342,943,855,079 | 1,342,943,855,079 | 元级相同 |
| SSE 融资买入额 `rzmre` | 94,338,686,041 | 94,338,686,041 | 元级相同 |
| SZSE 融资余额 `rzye` | 1,278,973,655,069 | 1,278,973,655,069 | 元级相同 |
| SZSE 融资买入额 `rzmre` | 95,431,661,788 | 95,431,661,788 | 元级相同 |

SSE [官方汇总 JSON](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260828&endDate=20260828&isPagination=false)（[本地原件](evidence-05/fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed.json)）`result[0].opDate=20260828`，`rzye`、`rzmre` 为上表整数；本次与 09-05 原件散列完全相同。[上交所汇总说明](https://www.sse.com.cn/market/othersdata/margin/sum/)区分当前标的明细与包含调出标的余额余量的汇总，故不能用当前标的明细求和替代。

SZSE [官方 JSON](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-08-28&tab1PAGENO=1)（[本地原件](evidence-05/c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277.json)）`metadata.catalogid=1837_xxpl,tabkey=tab1,subname=2026-08-28`，同样与旧 JSON 散列一致。相应 [官方 Excel 导出](https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1837_xxpl&txtDate=2026-08-28&TABKEY=tab1)（[本次 XLSX](evidence-05/30b9f549a2d603efb49f502c638eb93dce59a67175427675abed0cfe2eb2a9dd.xlsx)、[旧 XLSX](evidence-05/a0bccdd0398381440b43432cb8fc777f6e46a7e271a79d08ac6fdc56b031ab1c.xlsx)）工作表 `融资融券交易总量` 的 A1/B1 明确为融资买入额/融资余额，单位元；A2/B2 是相应精确值。Excel 无单独日期单元格，日期身份依赖同一报表目录、tab 与 JSON 内日期共同绑定，不能仅凭 URL 参数确认。

深交所网页摘要是亿元展示值，旧研究已发现不能假设其使用标准两位四舍五入；本次继续使用元级 XLSX，不扩大容差强配。四数通过仅证明同日同字段样本与已保存渠道值相容；没有新增“120 日都必须双来源逐条相等”的要求，也没有因此放宽实际公开时间条件。

### 3.1 新发现：Excel 文件变化不等于融资数值修订

两次同日 Excel 大小同为 3711 字节，但完整散列不同。解压后对所有成员内容逐一比较，**仅 `docProps/core.xml` 内容不同**；工作表、共享字符串、样式、工作簿等内容相同，所有可见单元格相同。变化为：

| 内部元数据 | 09-05 已保存文件 | 本次文件 |
|---|---|---|
| `dcterms:created` | `2026-09-05T09:30:53Z` | `2026-09-06T13:01:35Z` |
| ZIP 成员时间 | `2026-09-05 17:30:52` | `2026-09-06 21:01:34` |
| 创建者 | `Apache POI` | `Apache POI` |

这些时间明显晚于统计日。它们支持导出制品生成元数据变化，**不能作为 08-28 首次公开时间，也不能当成融资数值修订发生的证明**。本次两份都保留，不覆盖旧制品，不因数值相同抹除文件版本差异。其根本原因是否为按需生成或缓存重建，本次没有服务端日志，保持未判定。

## 4. 北交所：真实访问结果与仍缺原件

### 4.1 官方内容线索与取得结果分开

[北交所融资融券交易信息](https://www.bse.cn/disclosure/rzrq_trans_list.html)的官方索引文本仍可通过 web 检索读取：总量表列融资买入额、融资余额，单位 **万元**；说明汇总还包含调出标的股票的余额余量，不能用当前标的明细替代。这是官方内容线索，**本次没有得到包含目标日期数值行的官方 HTML、JSON、Excel 或 PDF**，无法核验该页面的精度/舍入和任何一天 BSE 两字段。

| 本次直接公开请求 | 实际结果 | 保存内容的性质 |
|---|---|---|
| [融资交易页](https://www.bse.cn/disclosure/rzrq_trans_list.html) | HTTP 403；14:09:46.137143 UTC 接收 | [拒绝响应](evidence-05/bbbfe0e59c1c3d196d98dcc9b21066cb3df3614b068b3edd91c53151a9a9d329.html)，2025 字节，不是融资表 |
| [现行融资业务指南页](https://www.bse.cn/jygl_list/200013680.html) | HTTP 403；14:09:46.135338 UTC 接收 | [拒绝响应](evidence-05/5b58ef7d458e50eed94c4eb437ba598a2933142f9c1acad942e41997700939fb.html)，2011 字节，不能称已下载指南 |
| [已知官方备用站公开页](https://www.bseinfo.net/disclosure/tradepublic.html) | HTTP 403；14:09:47.185529 UTC 接收 | [拒绝响应](evidence-05/1009ae5b6db3373aaa0982b52576ad6adeec18757c727678ec3355604a1817ef.html)，2929 字节；该页本来也不是融资数值样本 |
| [2025 年融资技术指南 PDF](https://www.bse.cn/uploads/6/file/public/202510/20251010190514_4qgms4u8gx.pdf) | HTTP 403；14:11:21.799487 UTC 接收 | [HTML 拒绝响应](evidence-05/32fe74eb10683b4da4da95782d3a7d5f0b78ba289d50ec4bb3f509895b48fa57.html)，2077 字节；没有 `%PDF` 原件 |

上述 URL 均来自已有官方入口或本次检索到的官方文件路径，不是猜测 API。主站错误页表示访问控制拒绝本次请求；这不等于目标融资数据为空、不等于数据永不存在，也不能判断用户账户是否有许可。未尝试绕访问控制、解验证码、读取 cookie、使用源站 IP 或访问会员 FDEP。

另以正常 Chrome 打开融资页，创建标签页操作在约 **15.073 秒**后由控制工具超时并重置会话；未取得页面状态、日期查询结果或下载附件。故它只记为浏览器工具失败。web 的直接读取另报重定向循环；这些与本轮直接 HTTP 403 是不同访问路径的实际结果，不能互相覆盖或沿用旧研究的 1488 秒等待时长。

当前可比目标仍是渠道 BSE 2026-08-28 的 **融资余额 8,332,418,348 元、融资买入额 659,105,185 元**。这是 [TuShare 原响应](evidence-05/3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548.json)中的明确 BSE 行，**不是北交所官方抽样通过值**。未取得官方值时不填零、不扩大容差、不根据其他总量推算。

### 4.2 发布和修订规则只证明制度，不证明每一日实际发生

[北交所《融资融券业务指南》官方页面](https://www.bse.cn/jygl_list/200013680.html)的检索全文列公告/实施日 2022-11-11，并标注现行有效；可定位这些条款：6.1.3–6.1.4 规定交易日 22:00 前申报与校验，以时限内最后申报为准，未及时成功申报按当日无交易统计披露；6.1.5 允许至下一交易日 15:00 的监管补报，明确不影响已披露数据；7.1 规定每交易日开市前公布前一交易日市场总量。这也提示监管补报口径与公众披露版本可能不同。**本轮原网页/附件未取得，引用的是官方索引文本，不给它伪造成功原件散列。**

规则中的两个限制应保留：第一，它可能解释为什么监管汇总与交易所公开数不必相等，但没有证明本次中证数据差额就是补报造成；第二，开市前是规定窗口，仍不能替代 120 次真实发布事件、迟发事实或可核验的数值 vintage。不能依据 08-28 是周五，就自动填 08-31 某时刻已公开。

[TuShare margin 文档](https://tushare.pro/document/2?doc_id=58)（[实际 HTML](evidence-05/9f84649b54199c0f4d89dbb2cfd4235ac7ef816aab2f8d2dcd5867f6a32a1e7c.html)）的次日上午更新说明及深交所/北交所周五数据下周一更新提示同样是交付安排；它未提供目标每行实际首次发布时间或历史修订时间。`trade_date` 仍只是统计交易日。

## 5. 全市场汇总差额继续保留，不反推 BSE

再次从已保存的 [中证数据官方 XLSX](https://www.csdata.cn/cmsmc/articleFileDir/2026-08/28/d1c3478a84f34f56872c7d954b284199.xlsx)（[原件](evidence-05/0c5fed810954d46dfe7379890f7316ae1f2511886b7bb72c459f5745b0d7b616.xlsx)）解析日期和数值：C2 为 2026-08-28；C3 融资余额、C7 融资买入额，单位亿。它没有三所分行，不能把它当北交所汇总。

| 字段 | 中证数据，元 | TuShare 三所合计，元 | 合计减中证数据，元 |
|---|---:|---:|---:|
| 融资余额 | 2,630,222,014,595 | 2,630,249,928,496 | 27,913,901 |
| 融资买入额 | 190,429,452,981 | 190,429,453,014 | 33 |

差额再次以 Decimal 算术确认。其统计范围、版本和修订来源尚未解释，不认定任何一方必然错误、不平均取值，也不做“总额减沪深”北交所官方样本。相关首次取得时间和目录/生成元数据的有限证明范围见 [既有官方补证](../../docs/research/margin-official-resolution-2026-09-05.md)，本次不把旧文件复制时间写成新网络取得时间。

## 6. 认证维度与精确剩余阻塞

| 维度 | 本次结论 | 完成第 05 票还需要 |
|---|---|---|
| 交付范围与结构 | 120 日 × 三所 × 两字段齐全；240 个合计的算术可复算 | 后续新采集/候选读取入口必须保留实际请求原件与三所组成关联，不能只保存总量；本研究未运行该应用入口 |
| 沪深官方数值 | 08-28 四数元级一致，旧/新原件均保留 | 不要求全部 120 日双来源数值逐条相等，但不能以四数抽样替代时间证明 |
| 北交所官方身份/单位 | 官方索引表头支持 BSE 市场总量与万元单位 | 至少取得可对账的官方总量实际内容，含日期、两字段、单位、精度、汇总范围；当前 08-28 乃至另一天均未取得有效原件 |
| 北交所官方值 | **未通过**，只有渠道 BSE 值 | 正常可用官方页面/公开导出或已有合法授权的官方原件；不以残差、明细求和或其他市场替代 |
| 实际发布日期/时间 | SSE、SZSE、BSE 的目标 120 日均未由现有原件证明实际首次公开链 | 可解释的发布事件/历史元数据及对应数值版本；只有可靠日期才按次一本地日，缺日期保持 null |
| 修订/版本 | 两次沪深官方 JSON 相同；深交所 XLSX 元数据变但数据内容不变 | 不将生成时间、取回时间或日历期限当历史首发；仍需真正的公开数值修订依据 |
| 全市场汇总差额 | 两差额保留，原因未知 | 如需解释，必须取得同口径/同版本对接证据；不影响继续明确拒绝 BSE 官方样本认证 |
| 家族、模型和验收状态 | **未签发认证，未入库，未回放，未激活** | 必要外部证据齐备及应用正负验收后，才允许后续不可变认证流程 |

三所合计的 PUBLIC 边界必须晚于或等于每个输入的实际公开边界；任一交易所日期/时刻未知，该合计仍未知。现有 240 条候选的未知公开时间应继续保留。本轮证明北交所当前直接入口受访问阻断；下一步的外部缺件是可读官方数值和真实发布/修订证据，不能用一份记录阻塞的研究文档代替认证完成。

## 7. 原件及请求索引

完整散列在下表链接文件名和回执中。HTTP 403 的文件特意标为失败响应，不计入数据样本数；请求时间均为 2026-09-06 UTC。

| Request / official URL | HTTP / bytes | Received at UTC | SHA-256 / saved content |
|---|---|---|---|
| [bse-margin-page](https://www.bse.cn/disclosure/rzrq_trans_list.html) | 403 / 2025 | 2026-09-06T14:09:46.137143+00:00 | [bbbfe0e59c1c3d196d98dcc9b21066cb3df3614b068b3edd91c53151a9a9d329](evidence-05/bbbfe0e59c1c3d196d98dcc9b21066cb3df3614b068b3edd91c53151a9a9d329.html) |
| [bse-business-guide](https://www.bse.cn/jygl_list/200013680.html) | 403 / 2011 | 2026-09-06T14:09:46.135338+00:00 | [5b58ef7d458e50eed94c4eb437ba598a2933142f9c1acad942e41997700939fb](evidence-05/5b58ef7d458e50eed94c4eb437ba598a2933142f9c1acad942e41997700939fb.html) |
| [bseinfo-known-public-page](https://www.bseinfo.net/disclosure/tradepublic.html) | 403 / 2929 | 2026-09-06T14:09:47.185529+00:00 | [1009ae5b6db3373aaa0982b52576ad6adeec18757c727678ec3355604a1817ef](evidence-05/1009ae5b6db3373aaa0982b52576ad6adeec18757c727678ec3355604a1817ef.html) |
| [bse-tech-guide-2025](https://www.bse.cn/uploads/6/file/public/202510/20251010190514_4qgms4u8gx.pdf) | 403 / 2077 | 2026-09-06T14:11:21.799487+00:00 | [32fe74eb10683b4da4da95782d3a7d5f0b78ba289d50ec4bb3f509895b48fa57](evidence-05/32fe74eb10683b4da4da95782d3a7d5f0b78ba289d50ec4bb3f509895b48fa57.html) |
| [tushare-margin-public-doc](https://tushare.pro/document/2?doc_id=58) | 200 / 34682 | 2026-09-06T14:11:23.869777+00:00 | [9f84649b54199c0f4d89dbb2cfd4235ac7ef816aab2f8d2dcd5867f6a32a1e7c](evidence-05/9f84649b54199c0f4d89dbb2cfd4235ac7ef816aab2f8d2dcd5867f6a32a1e7c.html) |
| [sse-20260828-refetch](https://query.sse.com.cn/commonSoaQuery.do?sqlId=RZRQ_HZ_INFO&beginDate=20260828&endDate=20260828&isPagination=false) | 200 / 804 | 2026-09-06T14:12:18.635447+00:00 | [fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed](evidence-05/fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed.json) |
| [szse-20260828-json-refetch](https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate=2026-08-28&tab1PAGENO=1) | 200 / 8383 | 2026-09-06T14:12:18.720677+00:00 | [c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277](evidence-05/c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277.json) |
| [szse-20260828-xlsx-refetch](https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1837_xxpl&txtDate=2026-08-28&TABKEY=tab1) | 200 / 3711 | 2026-09-06T14:12:18.679401+00:00 | [30b9f549a2d603efb49f502c638eb93dce59a67175427675abed0cfe2eb2a9dd](evidence-05/30b9f549a2d603efb49f502c638eb93dce59a67175427675abed0cfe2eb2a9dd.xlsx) |

既有原件的实际原始取得时间沿用 [前轮融资研究](../../docs/research/margin-inputs-followup-2026-09-05.md) 和其清单；本次只复核散列并复制。沪深 JSON 的新请求正好返回同样字节，也分别有新回执。其他旧原件不可仅因目录新建就算作本次新增外部证据。

| Previous artifact | Bytes | SHA-256 / local copy |
|---|---:|---|
| sse-20260828 | 804 | [fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed](evidence-05/fa7f73716372a7be474ff766b2eb8cebd7260d71d7e87c94884cd5727d6e5eed.json) |
| szse-20260828-json | 8383 | [c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277](evidence-05/c795098426ebe987b7971ffcadc1bd36a34cbe3f5b9fc2295baa1883fbc77277.json) |
| szse-20260828-xlsx | 3711 | [a0bccdd0398381440b43432cb8fc777f6e46a7e271a79d08ac6fdc56b031ab1c](evidence-05/a0bccdd0398381440b43432cb8fc777f6e46a7e271a79d08ac6fdc56b031ab1c.xlsx) |
| tushare-20260828 | 328 | [3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548](evidence-05/3cb57edb3e560a118fd2a84c94d471a53179547489b5ef0936649c63e4ae4548.json) |
| tushare-calendar | 2759 | [d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635](evidence-05/d0740f44c9648b5adc6ba98fe9acb59565858e8195cdf25df09e59f691b94635.json) |
| tushare-margin-120d | 17550 | [a03de595618ce8aa3fa74ce97fff980bbbe3e2197e9f5064b7157756dd7b2afd](evidence-05/a03de595618ce8aa3fa74ce97fff980bbbe3e2197e9f5064b7157756dd7b2afd.json) |
| margin-review-manifest | 2619 | [c0bbdf18fa19fcf0a2025b602c7a57f7317e60822b54ac90ff3fc11fd3d5dc6f](evidence-05/c0bbdf18fa19fcf0a2025b602c7a57f7317e60822b54ac90ff3fc11fd3d5dc6f.json) |
| csdata-total-20260828 | 5581 | [0c5fed810954d46dfe7379890f7316ae1f2511886b7bb72c459f5745b0d7b616](evidence-05/0c5fed810954d46dfe7379890f7316ae1f2511886b7bb72c459f5745b0d7b616.xlsx) |
