# 第 11 票研究：PP 官方行情与真实月份合约输入

研究时间：2026-09-06，公开请求发生在 15:01–15:10 UTC。代码核查基准 HEAD `0747710`。范围仅为[第 11 票](issues/11-futures-contract-evidence.md)和[已接受规格](spec.md)中的七袖套真实合约、结算、历史日历及可知时间；没有读取密钥、调用账户 API、购买数据、修改应用、生产库、模型、认证状态或票据。本报告不批准第 12 票仍待决的选月、换月缓冲或基点。

**新增正向证据是：取得上期所官方前端实际使用的历史合约表，三份表分别有 300、302、302 个唯一合约，含 CU/RB/RU/SP/SC 的上市、到期和交割日期；取得并核验三日真实月份结算行情。PP 官方实值仍未取得。整个 120 日篮子输入及历史 PUBLIC 可用性仍不能认证。**

本轮共 21 个有界公开 HTTP 请求：18 个取得响应体，其中 15 个 HTTP 200、2 个 412、1 个 404；一个 HTTP 200 实为人机验证页，因此可审查的业务文档／数据响应为 14 个。另有 3 个请求超时，均为大商所请求。既有 CAS 只读导入 10 份原件，28 份实际文件全部通过长度与 SHA-256 校验。上述分母是研究请求，不是应用渠道成功率或模型缺口补齐率。[完整请求回执](evidence-11/receipts.json)、[旧原件导入及来源登记](evidence-11/imports.json)、[逐行检查结果](evidence-11/verification.json)

## 1. 当前输入契约和实现差距

七袖套由八个品种构成：CU、RB、PP、CF/TA 各半的纺织袖套、RU、SP、SC。SC 权重 1/5，其余六袖套各 2/15。[代码中的品种和权重](../../src/pring_cycle/tushare_context.py#L46)与[规格第 16 条](spec.md)要求真实月份合约的同合约结算收益；NHII 商品核心及不重复投票的约束保持。

检查时 `src/pring_cycle/tushare_context.py:993–1069` 仍对 `CU.SHF` 等连续码调用 `fut_daily`，请求 `close/pre_close`，按两者比值计算，并从请求区间起点初始化 1000。这既没有实际月份映射链，也不是已确认的结算口径。`src/pring_cycle/domain/market.py:43–59` 的通用函数在跨合约时乘入调用方提供的调整因子，但不证明因子来源、上市／到期身份或历史可知性；`src/pring_cycle/acceptance.py:489–509` 的 GCZ26/GCG27 是隔离示例，不是八个中国品种的历史证据。这些是代码事实，不在本研究范围内修复。

TuShare 官方 [fut_daily 文档](https://tushare.pro/document/2?doc_id=138)将 `settle/pre_settle` 与 `close/pre_close` 分列，并另外列出交割结算价 `delv_settle`；普通结算、收盘、交割结算不能互换。[文档原件](evidence-11/8662dc734be76deb9e64e6cc4e12ad725ffefe29dec53e7702bfa992f8b9f905.html)仅证明字段契约，**不证明本次取得任何账户行情**。

## 2. 历史真实合约表：取得了实际官方数据

上期所 [api.js](https://www.shfe.com.cn/images/api.js) 中 `api_future_currinstrumentprop_f(date)` 直接给出 `ContractBaseInfoYYYYMMDD.dat` 路线；不是从第三方猜测的合约列表。[脚本原件](evidence-11/888923e303b7178af9b3bfac83621c60f2f6ae0871894bf1ebe75a3a2708f86b.js)

| 官方历史快照／本地原件 | 响应字节 | 总行／唯一合约 | CU/RB/RU/SP/SC 行数 | 正文 `update_date` | 本次接收时间 UTC |
|---|---:|---:|---|---|---|
| [2026-02-02 官方表](https://www.shfe.com.cn/data/busiparamdata/future/ContractBaseInfo20260202.dat)；[SHA 0f069e8f…](evidence-11/0f069e8fedf1d36922c862ad596289071b0774217c14165f825588c6b9b2352e.dat) | 80,439 | 300/300 | 12/12/10/12/20 | 20260202 16:40:16 | 2026-09-06T15:04:06.220744Z |
| [2026-03-09 官方表](https://www.shfe.com.cn/data/busiparamdata/future/ContractBaseInfo20260309.dat)；[SHA 28beb369…](evidence-11/28beb369dbdd9642006237d378a2e9f4f75a4dff290dcb5c73112e03f8dedb20.dat) | 80,986 | 302/302 | 12/12/10/12/20 | 20260309 17:15:07 | 2026-09-06T15:04:06.208045Z |
| [2026-08-28 官方表](https://www.shfe.com.cn/data/busiparamdata/future/ContractBaseInfo20260828.dat)；[SHA b46f8fcb…](evidence-11/b46f8fcb29cae52997017aa80c58f274abb7e6028c67b0f9647e45a4ede4d57b.dat) | 80,997 | 302/302 | 12/12/10/12/20 | 20260828 16:05:09 | 2026-09-06T15:04:06.237675Z |

三份原件都有 `report_date`，每行有 `INSTRUMENTID`、`COMMODITYID`、`TRADINGDAY`、`OPENDATE`、`EXPIREDATE`、`STARTDELIVDATE`、`ENDDELIVDATE`、`BASISPRICE`。日期是该历史快照声明的业务事实；**`BASISPRICE` 不是该交易日结算价**。当前样本中的具体边界如下，完整选中原始行保存在 verification.json。

| 真实合约原始标识 | 上市日 `OPENDATE` | 最后交易日 `EXPIREDATE` | 交割首日—末日 | 核查来源 |
|---|---|---|---|---|
| cu2602、rb2602、sp2602 | 2025-02-18 | 2026-02-24 | 2026-02-25—02-26 | 02-02 快照 |
| ru2603 | 2025-03-18 | 2026-03-16 | 2026-03-17—03-18 | 02-02 快照；该表无 ru2602 |
| sc2603 | 2023-03-01 | 2026-02-27 | 2026-03-02—03-06 | 02-02 快照 |
| cu2609、rb2609、ru2609、sp2609 | 2025-09-16 | 2026-09-15 | 2026-09-16—09-17 | 三份快照均有 |
| sc2609 | 2023-09-01 | 2026-08-31 | 2026-09-01—09-07 | 三份快照均有 |
| sc2610 | 2025-10-09 | 2026-09-30 | 2026-10-08—10-14 | 三份快照均有 |

**保留一个原始字段冲突：这些汇总表的 SC 行 `EXCHANGEID` 也写 SHFE。** INE 官方原油手册的合约表明确交易场所为上海国际能源交易中心；因此不能依据这个字段把法定交易所或 TuShare 后缀改成 SHFE/SHF。本次没有证据解释这个汇总字段是否另有内部含义，应分别保留原始字段、发布渠道、品种的法定场所和渠道标识，再显式认证映射。[INE 手册 PDF 第 75 页](https://www.ine.com.cn/upload/20240410/1712738949255.pdf)、[本地原件](evidence-11/c0467343d9811db50c1b83c4431293142a9c9000ce649cb3abdb30d559e6fb18.pdf)

这三天不是完整的 120 日合约表，也没有覆盖 PP、CF、TA 的历史身份表。02-02 是春节边界研究样本，不是已批准的篮子预热起点。官方页面的备用查询路线分别返回 404 和人机验证页；不计为成功合约证据，也没有绕过验证。

## 3. 真实结算样本与同合约检查

上期所[日行情页面](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/)实际列绑定为 `PRESETTLEMENTPRICE`、`CLOSEPRICE`、`SETTLEMENTPRICE`；后者的中文列名是结算参考价，页面说明交易期数显示后为结算后数据。[保存的页面原件](evidence-11/27828a95b60eb2a3ad1b5fbadb42367f38fbf83cff01caea54116d8d919b3ba9.html)保留了绑定和说明。三份 DAT 均有非空年度／总期数、交易日期和更新时刻，可作为本次的结算后字段样本；不把盘中同路线响应自动当作最终结算。

| 交易日／官方原件 | SHA-256 与本地文件 | 字节 | 年度期数／正文更新时间 |
|---|---|---:|---|
| [2026-08-27](https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260827.dat) | [8037f2658b20df41aa118aab25e814400b43225fa1ab67a6b752cc57654d3926](evidence-11/8037f2658b20df41aa118aab25e814400b43225fa1ab67a6b752cc57654d3926.dat) | 123,139 | 158／15:23:04 |
| [2026-08-28](https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260828.dat) | [09820b4ff6132309da7ac0690519e5108cf4b429bbbd27ee10989524135f3ae3](evidence-11/09820b4ff6132309da7ac0690519e5108cf4b429bbbd27ee10989524135f3ae3.dat) | 123,009 | 159／15:34:05 |
| [2026-08-31](https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260831.dat) | [81686cd4f0a5724726e31795acafeb720297a244126736af0e995a81f2a32a89](evidence-11/81686cd4f0a5724726e31795acafeb720297a244126736af0e995a81f2a32a89.dat) | 123,352 | 160／15:30:57 |

日行情行没有 `INSTRUMENTID`，而是 `PRODUCTID`（如 `cu_f`）与 `DELIVERYMONTH`（如 `2609`）。应与同一品种的真实合约表连接，保留两个原始字段及连接依据，不能把产品汇总行当月份行情。

下表为 08-28 的代表性数字，来自上述当天原件；CF/TA 来自郑商所当天的 UTF-8 TXT。单位规则见下一节；这里没有查询 TuShare 月份行情进行第二渠道数值比对。

| 品种／真实月份行 | 前结算 | 当日结算 | 收盘 | 报价单位 |
|---|---:|---:|---:|---|
| CU／cu_f + 2609 | 108760 | 109010 | 109240 | CNY/吨 |
| RB／rb_f + 2609 | 3042 | 3058 | 3065 | CNY/吨 |
| RU／ru_f + 2609 | 17680 | 17830 | 17950 | CNY/吨 |
| SP／sp_f + 2609 | 4768 | 4720 | 4750 | CNY/吨 |
| SC／sc_f + 2609 | 640.1 | 584.2 | 581 | CNY/桶 |
| SC／sc_f + 2610 | 573.7 | 592.3 | 596.5 | CNY/桶 |
| CF／CF609 | 16570 | 16760 | 16775 | CNY/吨；2026 有效规则链待补 |
| TA／TA609 | 5756 | 5822 | 5866 | CNY/吨；2026 有效规则链待补 |
| PP | 未取得 | 未取得 | 未取得 | 待补实际原件认证 |

郑商所三份原件均重新从旧 CAS 读取并验 hash，再拷入本轮目录：[08-27 官方 TXT](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260827/FutureDataDaily.txt)／[ff03d4cc…](evidence-11/ff03d4cc6a853010f5ea5a2e3b4d257e862a49d509e56d789dc5517b15ca8dfb.txt)，[08-28 官方 TXT](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260828/FutureDataDaily.txt)／[1e5a1fc5…](evidence-11/1e5a1fc5094eee5b3626a1d53df19c932a4f2c28403e36197ed7b8797e33099d.txt)，[08-31 官方 TXT](https://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260831/FutureDataDaily.txt)／[75cc18e5…](evidence-11/75cc18e546ea324d310c85e3bae2c3d962796dec3e0b0a0b8755fd420565b2f2.txt)。每份 37,607 字节，首行有完整交易日期，普通结算、收盘和交割结算分列。`CF609/CF701/TA609/TA701` 的完整交割年月及渠道代码仍需身份表证明，不能只凭字符串补年份。

使用 Decimal 复核得到：上期所五品种各 2609/2610 共 10 个标识 × 3 日 = 30 行唯一样本，全数满足结算减前结算等于涨跌2；20 条相邻样本交易日的同合约连接均满足上日结算等于下日前结算。郑商所四个原始标识 × 3 日 = 12 行也全部通过，8 条连接通过。这些是原件内部及同源跨日检查，**不是双渠道认证，更不是已冻结的持有合约链**。[逐行数字及检查分母](evidence-11/verification.json)

SC2609 在 08-28 的正确同合约研究算式为 `584.2/640.1-1`，SC2610 为 `592.3/573.7-1`；不能把 `592.3/640.1-1` 当作任一合约的当日收益。三日还显示收盘与结算存在实际差异，足以形成非镜像的错误列和跨合约失败样例。08-31 是目标期末以外的到期边界探针；目标 2026-03-09—08-28 内这里只抽到了 08-27、08-28，不是 120 日完整性验收。

## 4. 七袖套的单位、月份与到期规则证据

| 袖套／品种 | 已核实官方规则依据 | 月份／正常最后交易日 | 报价与每手单位 | 尚未闭合的范围 |
|---|---|---|---|---|
| 铜 CU | [2026 细则](https://www.shfe.cn/regulation/exchangerules/productrules/202512/t20251231_829954.html)第 3/4/6/8 条；[本地原件](evidence-11/424a28732e0a3fdc1837e2bc32122415b12e61b05fa3a7cc2648d2a8db58a2af.html) | 1–12；交割月 15 日，假日顺延，可有通知调整 | CNY/吨；5 吨/手 | 120 日身份／行情及适用调整公告链 |
| 螺纹 RB | [2026 细则](https://www.shfe.cn/regulation/exchangerules/productrules/202512/t20251231_829962.html)同条款；[原件](evidence-11/1623ea4f156653e9e54ba6f2d99c4320616b00565e5d377a1c741aa2a6a4db61.html) | 1–12；同上 | CNY/吨；10 吨/手 | 同上 |
| 聚丙烯 PP | 既有研究定位的 [2024 官方细则 PDF](https://www.dce.com.cn/dalianshangpin/fgfz/6142914/6142926/6146588/%E5%A4%A7%E8%BF%9E%E5%95%86%E5%93%81%E4%BA%A4%E6%98%93%E6%89%80%E8%81%9A%E4%B8%99%E7%83%AF%E6%9C%9F%E8%B4%A7%E4%B8%9A%E5%8A%A1%E7%BB%86%E5%88%99%EF%BC%88%E6%A0%B9%E6%8D%AE2024%E5%B9%B411%E6%9C%881%E6%97%A5%E3%80%942024%E3%80%95102%E5%8F%B7%E6%96%87%E4%BB%B6%E4%BF%AE%E6%94%B9%EF%BC%89.pdf)，本次仍超时 | 旧官方索引线索为 1–12、交割月第 10 个交易日 | 索引线索为 CNY/吨、5 吨/手 | **没有本机规则原件、真实行情、历史合约表或发布证明**；索引线索不算已验收原件 |
| 纺织 CF/TA | [郑商所历史合约 PDF](https://www.czce.com.cn/cn/rootfiles/2014/12/05/1415698821329524-1415698821331547.pdf)第 3/7 页；[原件](evidence-11/58c03806b3de89558d75c01ab5e07cff1608b20b34bf918e666c0dd8c0df2776.pdf) | CF 为 1/3/5/7/9/11；TA 为 1–12；历史表均为交割月第 10 个交易日 | CNY/吨；各 5 吨/手，CF 公定重量 | 2014 原件不能替代 2026 有效版本链；真实完整年月、上市到期表缺失 |
| 橡胶 RU | [2026 细则](https://www.shfe.cn/regulation/exchangerules/productrules/202512/t20251231_829973.html)第 3/4/6/8 条；[原件](evidence-11/3de7a1887f6b6c528bae6e013825e3add2517ef91685843d3309e0bbaa45748e.html) | 1/3/4/5/6/7/8/9/10/11，**无 2/12 月**；15 日规则 | CNY/吨；10 吨/手 | 120 日、历史公告链及生效边界 |
| 纸浆 SP | [2026 细则](https://www.shfe.cn/regulation/exchangerules/productrules/202512/t20251231_829972.html)同条款；[原件](evidence-11/2ce54ba6d669069b70fe4c08d5caae81686d388aff8ca4de8c3cf067d1a44fcf.html) | 1–12；15 日规则 | CNY/吨；10 吨/手 | 同上 |
| 原油 SC | [INE 2024 手册](https://www.ine.com.cn/upload/20240410/1712738949255.pdf) PDF 第 75–76 页；[原件](evidence-11/c0467343d9811db50c1b83c4431293142a9c9000ce649cb3abdb30d559e6fb18.pdf) | 最近 12 连续月及随后 8 季月；交割前月最后交易日，可公告调整 | CNY/桶，不含税；1000 桶/手 | 三份真实 2026 身份表提供样本到期事实；尚非完整规则修订／公告链 |

单位价格不乘以每手数量再和渠道价格对账。旧审查 M2 配置 hash `99906f7461e5a4078839e2e14112830e88a3d5c2371cc9ecf86863d0c7f8784c` 在登记的运行 CAS 路径实际不存在；本报告没有把该文件算作已重新验证的原件。以上单位依据来自实际导入的规则文件，仍保留各自的版本限制。

另取得[上期所 2026 假日安排](https://www.shfe.cn/eng/CircularNews/Circular/202512/t20251217_829807.html)／[原件 62b1cb96…](evidence-11/62b1cb96ca859433c6264643655312f8043aecda42d7746947be1292ce0d394a.html)，页面声明更新日为 2025-12-17：春节后 02-24 恢复交易，02-13 无夜盘。[能源中心春节交易通知](https://www.shfe.cn/eng/CircularNews/Circular/202602/t20260209_830413.html)／[原件 1f9be5c0…](evidence-11/1f9be5c00c7d9e25a49befeb02eb7708906ea7fe82b0635f34d155b68ef88107.html)页面声明 2026-02-09，明确相关休市及 02-24 恢复安排。这两份公告支持日期核查，**不是 SC 全部历史到期调整通知，也不是期货全部交易所的已认证日历**。

上期所[交易时间](https://www.shfe.cn/services/calenderandholidays/tradinghours/)／[原件](evidence-11/6152fe0799f49b2243c3f0e4887d010eaf4d6c1be82516fef42c620803c17ca1.html)把夜盘纳入下一交易日。工程上不能用公历当日 09:00 一刀切作为全部品种的整日选约截止点；周末、假日无夜盘等边界需按交易所日历处理。

## 5. PP 与新版规则：具体失败及最小缺件

大商所官网根页、PP 规则 PDF、候选公开日行情 POST 本次均为 ReadTimeout，没有任何可保存的 PP 行情响应体。POST 路线为 `https://www.dce.com.cn/dcereport/publicweb/dailystat/dayQuotes`，参数原样留在 receipts.json：

```json
{"contractId":"","lang":"zh","optionSeries":"","statisticsType":"0","tradeDate":"20260828","tradeType":"1","varietyId":"pp"}
```

该路线承接旧研究的第三方实现发现线索；本轮未正常读到大商所前端的参数／字段绑定，所以 `lastClear/clearPrice` 不能仅靠第三方重命名就认定为官方前结算／结算。超时不等于 PP 无交易、空数组或官方拒绝数据。请求设连接／读取超时 10/15 秒，无账户登录或重复变换协议试探。

郑商所[2026-01-09 CF 修订页](https://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2026/1/b02d47b1df0043c4a1a59fa86c939ee4.htm)返回 412；[2026-05-07 相关规则公告](https://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2026/5/e4f303d3856241fbb023093817d38c34.htm)也返回 412。失败响应原件分别为 [da9c3230…](evidence-11/da9c32302a3df4cde44b602a822f071f187276276f1a3c38a477445f5a85a13d.html)和 [9e0b3d71…](evidence-11/9e0b3d71ad044c5ae2c7ab246433eff84ae4a6848e649e10f6b9c43da57a74c5.html)。这些没有提供可审核的新规则正文，不能据此宣布 2026 规则无变化。

最小正向补证是：通过能正常访问的官方日行情界面取得一个确定日期、真实 PP 月份合约、明确结算／前结算列的原始响应，并取得其完整交割年月、适用单位及上市到期身份。随后抽样对齐已保留原始响应的渠道真实月份数据。PP 的这一条样本也不能代替 120 日完整输入，且不新增逐日双源数值相等的要求。

## 6. 连续码映射、PUBLIC 和待冻结方法分开处理

TuShare [fut_basic](https://tushare.pro/document/2?doc_id=135)／[原件](evidence-11/7bad6377bdf34d78f421b2d823233784cbcf4f734f015cd3d6051fdac2a0d222.html)提供普通／连续合约类别、交易所、上市／最后交易日、交割月份、每手／报价单位；[fut_trade_cal](https://tushare.pro/document/2?doc_id=467)／[原件](evidence-11/a57207b67932f04c325b9478c0ef12d3407da42f9e2a784769dad19a461917b3.html)提供交易所、日期、开市及上一交易日。它们是可执行的渠道输入路线，但本轮只取得文档，没有取得这些接口的实际账户响应。

[fut_mapping 文档](https://tushare.pro/wctapi/documents/189.md)／[原件](evidence-11/084495ddd4340fb4320c133717382d71ac8a4bc123a051d7799b028be236aed9.md)只有连续代码、日期、映射月份代码三个输出字段。输入日期叫交易日期，输出同名字段叫起始日期；没有主力判定算法、信息截止点、首发时刻、历史快照或修订版本的保证。**当前历史映射或统一滞后一天不证明当时可知；本轮没有生成已认证的历史映射。**

时间证据分层如下：

| 材料 | 可以证明 | 不能自动推出 |
|---|---|---|
| DAT `report_date`、TXT 首行日期 | 数据所属交易日期 | 历史首次发布或盘前已知 |
| DAT `update_date` | 发布方返回的这份版本更新时刻声明 | 原始第一版的首发时间、更新前内容、修订是否追溯 |
| HTTP Last-Modified | 服务器声明的资源修改时刻 | 全部行在此前已公开且没有修订 |
| 公告页面的 Updated on／正文公告日期 | 官方页面声明的公告日期，可作为进一步审核的日期证据 | 本机当日已抓取、对应文件版本首次公开精确时刻 |
| 本轮 received_at；旧 CAS 原始取回登记 | 本轮实际接收到字节；旧研究声明其原观察时间 | 自动倒填交易日的 PUBLIC 可用时间 |

三份合约表的 Last-Modified 分别为 02-02 08:40:16、03-09 09:15:07、08-28 08:05:09 UTC；三份行情则为 08-27 07:23:04、08-28 07:34:05、08-31 07:30:57 UTC，与各自正文更新时钟相差八小时。该一致性支持服务器元数据核对，仍没有首发／修订历史。日期级公开证据若经项目认定可靠，才按规格从下一本地日适用；不能擅自将上述更新字段或 15:30 模板填入 `public_available_at`。SYSTEM 取得时间与通过验证后的 `available_at` 继续独立记录。[规格第 6–8 条](spec.md)

INE 手册 PDF 第 48–50 页给出了用到期日前交易日计数切换输入的官方月均结算价先例；它说明确定性日历选择具有官方应用基础，但输出是月均结算价。其倒数第 12/11 日边界不是本篮子已接受的日收益换月参数。[官方手册及本地原件](evidence-11/c0467343d9811db50c1b83c4431293142a9c9000ce649cb3abdb30d559e6fb18.pdf)

基于实际原件，可以立即采用的输入校验约束是：真实合约／连续映射分表；保存完整身份和原始发布字段；按品种有效月份及到期事实拒绝错月；结算和前结算必须来自同一真实合约；未知时点、缺 PP、缺必需日期明确报缺；保留异常与原件。尚需项目冻结的是具体合格月份序列、到期前缓冲、生效时段、夜盘截止、缺失政策、基日与基值。不能把本报告的例子或 INE 月均先例自动升级成业务规则。

## 7. 第 12 票可用范围与剩余阻塞

可以交付：五个上期所／能源中心品种的三份真实历史身份快照；五品种十个月份标识的三日结算样本；CF/TA 四个原始月份标识的三日结算样本；四份 2026 上期所细则、INE 2024 手册、郑商所历史规则、两份 2026 日历公告；全部原件哈希和字段检查。它们可以支撑真实解析及错误列、错月、SC 到期、RU 无 2 月、跨合约收益等失败样例。

不能交付为通过项：PP 官方结算样本；PP/CF/TA 的完整历史月份身份；八品种适用规则和到期调整的完整版本链；目标 120 日及所需预热的全部实际合约行情；当时可知的供应商映射或已冻结日历选约；历史公开／修订时间证明；固定基点和生效边界。未查询账户行情，因此没有声称对齐任何实际 TuShare 月份原响应或用标准化包冒充原响应。

结论保持为部分输入证据已取得、完整认证未完成。应用可以明确查询这些已证样本及具体缺件，不能据研究附件数量解除商品家族隔离或发布完整篮子认证。原始存证、代码实现、方法接受和模型正式采纳是不同交付边界。
