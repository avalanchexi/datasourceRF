# 三指数估值：2026-09-09 官方增量补证

**新增一份上交所官方历史公告，补强沪深300静态 PE 与滚动 PE 的实际发布口径证据；没有新增 2026-08-28 的 PE/PB/换手率样本，也没有补齐三指数当前算法。** 本轮完成 6 个逻辑搜索、2 次 web 搜索调用、1 次直接 GET（HTTP 200），保存 28,619 字节原始 HTML。其历史统计期与目标日严格分开，未用其他指数、基金或第三方数据替代。

先读 [research-07](research-07.md)、[票 07](issues/07-valuation-certification.md)、[待冻结草案](business-decisions-draft.md#L9)、[前轮官方调查](../../docs/research/market-indices-valuation-followup-2026-09-05.md)及[旧回执](evidence-07/receipts.json)。三指数九成员的软件完整性问题已在[票 07 后续记录](issues/07-valuation-certification.md#L42)修复，不能继续把早期研究中的六成员代码状态写成当前事实；本轮只研究来源，不执行应用或复验软件。

## 1. 新原件提供了什么

来源：[上海证券交易所《沪深交易所和中证指数公司即日起联合发布重要指数市场指标》](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988252.shtml)。实际 HTML 的[标题 L327](evidence-valuation-20260909/2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd.html#L327)、[日期 L336](evidence-valuation-20260909/2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd.html#L336)和[正文 L340](evidence-valuation-20260909/2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd.html#L340)已直接读取；正文由四段组成，在源码中同处 L340，以 `<br><br>` 分隔。以下不是搜索摘要核值。

| 新增可核声明 | 字段 / 单位 / 统计期 | 可用边界 |
|---|---|---|
| 联合发布范围明确包含沪深300 | 指数身份；该篇 2008 年公告的发布范围 | 增加了具体指数的官方发布说明，超出只有一般统计定义的证据层；不证明 2026 年所有交付仍使用同一算法。 |
| 静态与滚动利润期分别说明 | 静态通常采用上年年报；滚动采用最近四季度财务数据；PE 为倍 | 支持两者不能混用。没有给总/计算用股本选择、亏损股筛除或财报切换的精确规则。 |
| 沪深300静态 / 滚动样本为 **14.58 / 13.66** | 两个独立 PE 字段，单位倍；原文统计期为“昨日收盘” | 相对页头 2008-10-24，**推断**为 2008-10-23 收盘；这不是正文直接打印的完整统计日期，更不是 2026-08-28。 |
| 市净率属于所公布指标 | PB 名称被提及；本公告未给其值、单位公式或财报期细则 | 不据此补 PB 数值或替代当前 PB 聚合说明。 |
| 页面声明发布时间 | **2008-10-24，精度为日** | 无精确时分秒。可靠日精度可按项目规则提出次日本地日候选边界，但本轮不写 PUBLIC 或授认证。 |

该文没有提供中证500/中证1000的完整估值契约，也没有换手率分母/交易范围或当日数值。页面路径含 `20150912`，不能覆盖可见 2008-10-24；本次原件不单独证明历史每次字节版本未修订。统计期、页头声明日、实际取得日须分别保存，不用当前抓取时钟回填历史。[新原件](evidence-valuation-20260909/2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd.html)、[双点时 ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)。

## 2. 对三指数四种度量的实际影响

| 度量 / 要求 | 原有证据保留 | 本轮改变与剩余缺件 |
|---|---|---|
| 静态 PE，倍 | 三指数官方 XLS 已有 P/E1、P/E2 及目标日值；股本聚合公式已有依据。[旧原件与公式](research-07.md#L45) | 新公告补强沪深300的静态/滚动区别；未建立当下 XLS、网页、TuShare 三者等价，也未补财报切换、负/零利润及成分变动规则。 |
| TTM，倍 | 旧历史 `peg` 有官方滚动列绑定及目标窗口值；与单张同日结果存在未解释差异。[字段绑定](research-07.md#L61)、[同日差异](research-07.md#L85) | 不把新历史说明变成当前 `peg` 完整算法或静态替代授权；新声明不增加目标期样本数。 |
| PB，倍 | 08-31 单张有三指数“计算用股本”PB，包括中证1000；日期晚于目标。[已证单张](research-07.md#L85) | 2026-08-28 官方同义值、完整聚合/负净资产规则、财报期更新与 120 日覆盖仍缺。本轮只增加历史公告提及 PB 的出处。 |
| 换手率，百分数 | 旧统计标准区分股本/市值及流通/自由流通口径；一般定义不等于渠道实现。[既有标准](research-07.md#L37) | 没有新增目标指数换手率定义或样本；需具体分子、分母、跨成分聚合与交易范围。成交金额 `Turnover`、股息率均不能代替。 |

本轮没有重抓现有 indicator.xls、历史 `indexCsiDsPe`、dashboard JSON、三份单张或已有方法 PDF，没有多日期重试 TuShare 的中证1000空响应。最新原件可读不等于历史公开时间已知；服务更新安排、交易日期、文件 `Last-Modified` 与实际首发/修订记录的区别仍依[旧时间缺件](research-07.md#L131)。未接受或修改 [business-decisions-draft.md](business-decisions-draft.md) 中的规则建议。

## 3. 六个真实查询及候选筛选

所有查询使用 web 工具，限定 CSI 或 SSE 官方域；未调用 Tavily/Exa。时钟记录的是工具调用前后 UTC，并非网页发布日期。

| 调用 / UTC 起止 | 逻辑查询文本 |
|---|---|
| S1，2026-09-09 01:53:48—01:53:50 | `site:csindex.com.cn "沪深300" "换手率" "2026-08-28"` |
| S1，同上 | `site:csindex.com.cn "中证1000" "市净率" "2026-08-28"` |
| S1，同上 | `site:csindex.com.cn "市盈率" "滚动" "计算" "指数"` |
| S2，2026-09-09 01:54:15—01:54:18 | `site:csindex.com.cn "指数指标" "市净率" "计算" -factsheet` |
| S2，同上 | `site:csindex.com.cn "换手率" "计算" "指数"` |
| S2，同上 | `site:sse.com.cn "沪深300" "静态市盈率" "计算"` |

工具按三查询合并返回，不能编造逐查询命中率。S1 没有目标日期原表；返回的 [931167 方法 PDF](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/931167_Index_Methodology_cn.pdf)、[931226 中证1000质量成长单张](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/931226factsheet.pdf)等是其他指数，不能因带“1000”或 PE 字段就当中证1000（000852）。它们只有搜索索引，本轮未 GET。

S2 的一般算法查询仍多为其他指数单张，未发现可补当前三指数公式的新适用文件；SSE 查询提供上述联合发布公告，列为 R1 并取得原文。另外出现的 [2012 年调样公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988631.shtml)和[2013 年调样公告](https://big5.sse.com.cn/site/cht/www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3987651.shtml)不是目标期数据，未下载，也不把调样假设下的旧估值当成目标真实指数值。

R1 的精确路径在本轮所查 research-07、evidence-07 的 receipts/imports、前轮官方调查和 market-source-semantic-review 中没有命中；因此没有重复这些材料中的已知请求。该去重限于已查记录，不声称检索了用户所有文件。

## 4. 唯一 GET、原件与分母

| 字段 | R1 实际记录 |
|---|---|
| 官方 URL | `https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988252.shtml` |
| 方法 / 超时 / 读取上限 | GET / 15 秒 / 8,388,608 bytes；无自动重试、无自动跳转 |
| 开始 UTC | `2026-09-09T01:54:59.014279+00:00` |
| 完整响应取得 UTC | `2026-09-09T01:54:59.714259+00:00` |
| 完成 UTC | `2026-09-09T01:54:59.714277+00:00` |
| HTTP / Content-Type | **200 / text/html**；无截断 |
| HTTP Date | `Wed, 09 Sep 2026 01:54:59 GMT`；仅本次响应时间 |
| Last-Modified / ETag | 响应未提供 |
| 精确原件 | **28,619 bytes**；SHA256 **`2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd`** |

[receipt-1.json](evidence-valuation-20260909/receipt-1.json) 保存请求及响应元数据，[HTML](evidence-valuation-20260909/2d033e2d42eacf904f9a1a60532a6acdd58546464b90d3dc24fda5464f3a8bfd.html)是精确响应体；UTF-8 只用于读取，不重写原件。内容确有标题、日期和公告正文，未把 200 空壳/挑战页当有效材料。

本轮 **6 逻辑搜索、2 web 搜索调用、1 直接 GET、1 HTTP 200、1 官方正文原件、0 目标日新样本**。直接 GET 成功率 1/1 只表示这一读取得到正文；当前三指数公式完整认证、120 日覆盖、模型可用补齐率和模型采用均 **N/A：本轮未评估/执行**。搜索工具底层 HTTP、缓存和重试次数未知；搜索返回文本不是已保存的搜索原始响应字节。所有数量独立于 Tavily/Exa 基准，不修改旧实验分母或结果。

## 5. 最小后续与精确交付

新材料可加入沪深300静态/滚动字段正式审查的历史一手出处，不必再泛搜一般 PE 定义。真正仍需的是：选定交付所适用的当前聚合/财报更新/负值处理说明，三指数目标期 PB 和换手率同义样本，以及可核实际发布/修订依据；若使用历史 TTM，仍独立保留静态未证状态和两种官方交付的差异。所需证据没有出现，四次 GET 上限不补足，不猜新接口或申请账户、采购。

已读取的稳定输入快照如下；只是引用绑定，不覆盖旧报告：

| 输入 | bytes | SHA256 |
|---|---:|---|
| [research-07.md](research-07.md) | 20891 | `148f13126e27d2e5dad77965991629981eabd353032beddabac78adbe437206b` |
| [business-decisions-draft.md](business-decisions-draft.md) | 5314 | `7d17453b12975869eed360d3047d862c562e1e4f697fbe8a97321af6f0919064` |
| [旧 receipts.json](evidence-07/receipts.json) | 8688 | `00b866af06ab89f96648f4af17f58e5117e3981d1783a87ef4e3458bffe4ffaf` |

[delivery-files.txt](evidence-valuation-20260909/delivery-files.txt) 列出本报告和新证据目录全部交付；[manifest.json](evidence-valuation-20260909/manifest.json) 保存交付文件字节/SHA（manifest 不自哈希）。默认只读复核命令：

```powershell
C:/Python313/python.exe -B .scratch/pring-data-acquisition-repair/evidence-valuation-20260909/verify_delivery.py
```

[verify_delivery.py](evidence-valuation-20260909/verify_delivery.py)仅用标准库核对原件、请求身份、来源锚点、输入与交付哈希及本地链接，不联网、不导入应用、不运行测试、不写文件。来源解释仍接受正式审查，不把脚本断言通过叫来源认证。唯一写入范围为本新报告与 `evidence-valuation-20260909/`。
