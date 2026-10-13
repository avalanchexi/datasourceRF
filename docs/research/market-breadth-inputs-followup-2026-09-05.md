# 市场广度原始行情与点时股票池补充核验

> 日期：2026-09-05，Asia/Shanghai。原件抓取区间：18:17–18:32。
> 范围：`market_breadth` 的五项既有指标；补充官方原始日线、证券名册、除息和停复牌事实，不新增统计口径。
> 方法：读取规格、CONTEXT、ADR-0013 与既有审查；检索一手资料，匿名读取交易所公开 JSON、XLSX、HTML、JS 和发行人公告 PDF。请求超时为 12–14 秒，限制响应大小及并发；北交所重复重定向后停止重试。
> 写入边界：仅新增本文及 WSL 内容寻址原始附件；未修改旧研究、代码或数据库，未读取密钥、调用账户 API、创建来源声明或激活模型。

本轮取得可复核的官方输入：上交所主板、科创板现行名册及终止上市记录，深交所现行完整 A 股名册，两所行情样本，以及深市除息、停牌、复牌公告。**这些附件补足部分来源事实，尚不构成 `market_breadth` 认证通过。** 历史逐日股票池、北交所输入、交付渠道同日比较、发布时间证据和未冻结的统计细节仍未闭合。本记录接续[原语义审查](market-source-semantic-review-2026-09-05.md)，不改变其结论或附件状态。

## 1. 规格已确定的边界

| 已确定规则 | 依据与含义 |
|---|---|
| 输出证据窗口是最近 120 个中国交易日 | [spec 第 109、238 行](../../.scratch/pring-cycle-dashboard/spec.md)及 [CONTEXT 第 119–121 行](../../GLOSSARY.md)。V1 不做十年全市场广度回填；必要公式预热不扩大页面或报告窗口。不能把某股票最后 120 条返回记录当成这 120 个市场日期。 |
| 广度不参与正式阶段机械映射 | [spec 第 19、113 行](../../.scratch/pring-cycle-dashboard/spec.md)。股票核心仍为认证后的中证全指；广度只作确认或环境说明。 |
| 公开点时和系统点时必须分开 | [spec 第 122–123 行](../../.scratch/pring-cycle-dashboard/spec.md)。交易日期、公告落款、网页最新更新时间、抓取时间不是同一事实；不能用本次下载时刻补造历史发布时间。 |
| 官方抽样认证交付渠道，不要求每条日观测双源 | [ADR-0013](../adr/0013-tushare-delivery-with-official-sampling.md)。原始样本、语义/单位比较、历史质量、发布时间和许可各自需要证据；family 未通过时继续保持未认证。 |
| 分析规则或来源变化写入新不可变版本 | [spec 的模型版本与来源认证规则](../../.scratch/pring-cycle-dashboard/spec.md)及 ADR-0013。研究发现不能直接改写已发布历史。 |

规格已经固定了**输出日期窗口**，但上述条款没有完整决定每只股票计算 MA120/新高新低时的资格与回看规则。是否包含存托凭证、ST、停牌日、上市未满 120 日股票，以及零分母和跨停牌回看方式，不能由“120 日”三个字推导出新的统计决策。应先对照已有指标定义及获准口径；仍未决定的项目需明确冻结，不能把当前实现自动当作已批准规则。

## 2. 原始附件及可追溯存储

全部下列 SHA-256 均来自实际下载的响应字节，附件保存于 Ubuntu-22.04：

```text
/home/tywin/.local/share/pring-cycle/artifacts/sha256/<sha256 前两位>/<完整 sha256>
```

同名内容已存在时只读取并验证 SHA-256；新内容使用排他创建，不覆盖已有文件。附件未登记为数据库来源声明，也未填入任何认证包。下载所得 HTML/JS 是端点及语义证据，不是日线数值；表中未成功请求也不算通过样本。

以下抓取时刻均为 **2026-09-05 UTC**，换算北京时间加 8 小时。它们表示 `fetched_at`，不表示 `release_at` 或历史 `public_available_at`。

| ID / 官方原件 URL | SHA-256 | 字节数 | 抓取时刻 UTC | 有效内容、统计时点与覆盖 |
|---|---|---:|---|---|
| D1 [TuShare daily 文档][ts-daily] | `1ae0c04367235ecd343b1e8b89ba88178020f00ac2a974872e08b5536431068b` | 35884 | 10:17:31.590295 | 接口字段说明；不是本账户日行情。 |
| D2 [TuShare 历史股票列表文档][ts-history] | `c70299c383245b0e43eaa833d28ec15ca6c27b8c8d5faf37c93e6845fa6dfa57` | 15211 | 10:17:31.549604 | `bak_basic` 历史列表能力；未实际调用。 |
| L1 [SSE 主板 A 股名册 JSON][sse-main] | `db6340c4632a92e7b3f4bef7b8a03743a3079be0d200e96b3bf2c286d52748eb` | 951462 | 10:20:43.975897 | 1700 行、1700 个唯一 A 股代码；现行响应，`queryDate` 为空。 |
| L2 [SSE 科创板名册 JSON][sse-star] | `6744dc0f6ae2e7de6ba594df773c42b0b0cc1ceb14462889980ce2fee451997a` | 349410 | 10:20:43.852489 | 616 行、616 个唯一代码，含 689009 存托凭证；`queryDate` 为空。 |
| L3 [SSE 终止上市名册 JSON][sse-delisted] | `614b9a0ff078069e9165a02f245e1c7b7c586aed527f2743a3490a2bfae8eb02` | 50941 | 10:25:48.571706 | 156 行，查询含 A/B 股，含双代码记录；不能称 156 只 A 股。 |
| L4 [SZSE A 股名册 JSON 首页][szse-list-json] | `7cef1463ea60268c0a7f5295f11b6359e6f99a2cb0d3ca28cf456fffcbe7fa59` | 21476 | 10:18:42.725514 | 元数据日期 2026-09-04、总数 2899，但仅返回 20 行。 |
| L5 [SZSE A 股名册完整 XLSX][szse-list-xlsx] | `07f4ca39bf8f286cd32ddeb87b01227d1cfd2fa93c0921c15412a26ae76ef4d1` | 543980 | 10:20:44.583358 | 2900 行含 1 行表头；2899 个唯一 A 股代码，与 L4 总数相符。 |
| Q1 [SZSE 000001 两日日线][szse-exdiv] | `d463a5480032fc7a737a77a9264e7b958522001f3b628fb303b9d619efebb200` | 3735 | 10:18:42.674765 | 2026-06-11、06-12，各 1 行；普通日及除息日。 |
| Q2 [SZSE 002084 停牌日日线][szse-suspended] | `afa20019df3a83a959dce49c0a8470d76ac85ff9e067292cc9f722200ac38d18` | 3526 | 10:22:59.941377 | 2026-08-19，1 行，量额为真实来源报告的零。 |
| Q3 [SZSE 002084 复牌日日线][szse-resumed] | `a27be539f890fbc3edbddae7b586400eeb2627c2150308b916ab96d7e73e3bb8` | 3533 | 10:22:59.983528 | 2026-08-24，1 行。 |
| Q4 [SSE 主板 A 股行情片段][sse-quotes] | `81f7a148611b5250070d7576f62b6823a2764835470214f3fa5fbd543cf0ba43` | 262 | 10:25:48.319936 | 响应日期 20260904、时间 162901；取 600000、600004 两行，总数 1700。 |
| A1 [平安银行权益分派公告 PDF][dividend] | `8e9d5facebfd8c46e049f0e6b0839e2be31ef292a5e3db903591fc08be9af5b8` | 139278 | 10:18:42.819979 | 落款 2026-06-05；登记日 06-11、除息日 06-12，每 10 股派 3.60 元。 |
| A2 [海鸥住工继续停牌公告 PDF][suspension] | `f9ecdaefdf40ec58b7c1d0609eb13e4f03b554759cc13940923b891dc16e7e60` | 152620 | 10:20:44.164181 | 2026-08-19 继续停牌。 |
| A3 [海鸥住工复牌公告 PDF][resumption] | `fc29d9393d7a79c2a28a3261ebde26f7f9ddb0da0fbc28b298688e95072e11d6` | 165678 | 10:22:59.694070 | 发行人公告，巨潮原件；确认 08-17 起停牌、08-24 开市复牌。 |
| A4 [SSE 九号公司存托凭证上市公告][cdr] | `a7f5bb162b021270d3b7ec5752a00e9a28b0efca21dbd879446330591e908ecf` | 27567 | 10:32:21.219737 | 公告日期 2020-10-28；689009 自 2020-10-29 上市，证券类型为存托凭证。 |

用于证明官方页面、查询参数和字段转换的辅助原件：

| ID / URL | SHA-256 | 字节数 | 抓取时刻 UTC |
|---|---|---:|---|
| P1 [SSE 股票与存托凭证页面][sse-list-page] | `f2ad0c38634b09851aff4c284d3140f5589b04441ba086ff1abbe380d2892186` | 27427 | 10:17:31.425935 |
| P2 [SSE 终止上市页面][sse-delist-page] | `667845f2f50467d77dd0983d7a58fbc381da7961c4c08fb1c3103f377ac08646` | 27529 | 10:23:00.450148 |
| P3 [SSE 名册查询脚本][sse-list-js] | `478fb2a72fc5a3725088adb208756e88171f79628956a9f5ca67c900d37def2f` | 277193 | 10:18:42.695296 |
| P4 [SZSE 股票列表页面][szse-list-page] | `ce51450c3072976fb40683cc66f48eb7bb62da260b056383f2114065502579fd` | 27632 | 10:17:31.419357 |
| P5 [SZSE 个股行情页面][szse-quote-page] | `d12209740871e566a9f4f34c0214d225098313d8f3a96b5c15c18a52ad3edb0c` | 31539 | 10:17:31.422462 |
| P6 [SSE 股票行情页面][sse-quote-page] | `e0df474acb6e3b38a2fed051998020e65aebd1adc541ac4ad79484faa0a9fd44` | 27120 | 10:22:59.971290 |
| P7 [SSE 行情展示脚本][sse-quote-js] | `7cd1bfe577b5dda51ea5d010a1b690bb048355ed6b4b7791d3434892135606bf` | 21980 | 10:24:18.466969 |

## 3. 日线样本核对结果

### 3.1 普通日与除息日：不能用昨日未调整收盘重算涨跌方向

深交所 Q1 的原始字段依次提供日期、证券代码、前收、开高低收、涨跌幅、成交量和成交金额。涨跌幅单位是 `%`，成交量为 **万股**、金额为 **万元**；价格为该证券行情价格，结合人民币权益分派公告可核对本样本的元/股含义。[行情原件 Q1][szse-exdiv]

| 日期 / 000001 | 前收 | 开盘 | 最高 | 最低 | 今收 | 涨跌幅 % | 成交量 万股 | 成交金额 万元 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-06-11 | 11.32 | 11.32 | 11.39 | 11.25 | 11.30 | -0.18 | 11562.22 | 130813.39 |
| 2026-06-12 | 10.94 | 11.00 | 11.25 | 10.88 | 11.24 | 2.74 | 20323.55 | 226304.29 |

A1 确认本次现金分红为每股 0.36 元，6 月 12 日除息。因此 `11.30 - 0.36 = 10.94`，当天 `(11.24 / 10.94 - 1) × 100 ≈ 2.7422%`，与官方 2.74% 相符；若直接比较两天未调整收盘，则约为 -0.53%，涨跌方向相反。这是同一发行人公告和交易所行情的直接交叉验证。[发行人公告 A1][dividend]

TuShare D1 说明 `daily` 的 OHLC 未复权，但 `pre_close` 为除权参考前收，`pct_chg` 使用该前收计算；停牌期间不提供日线。其 `vol` 单位为手、`amount` 为千元，并另列盘后量额字段。**未复权 OHLC 与经过除权前收处理的当日涨跌幅可以同时成立。** 这支持认证时核对除息样本的字段语义，不证明账户实返值已经通过比较。[渠道文档 D1][ts-daily]

当前代码连乘返回的 `pct_chg` 建立归一化序列。以上单日关系不能证明该序列等同于已经认证的精确复权价格序列；涨跌幅精度、送转/配股等其他公司行为以及跨停牌处理仍须按冻结公式验证。

### 3.2 停复牌：官方零交易行与渠道缺行是不同事实

A2/A3 是发行人一手公告，确认 002084 从 2026-08-17 起停牌，08-19 继续停牌，08-24 开市复牌。[继续停牌 A2][suspension]、[复牌 A3][resumption]

| 日期 / 002084 | 状态 | 前收 | 开高低收 | 涨跌幅 % | 成交量 万股 | 成交金额 万元 |
|---|---|---:|---|---:|---:|---:|
| 2026-08-19 | 停牌 | 3.59 | 均为 3.59 | 0.00 | 0.00 | 0.00 |
| 2026-08-24 | 复牌 | 3.59 | 均为 3.95 | 10.03 | 488.62 | 1930.07 |

深交所 Q2 在停牌日保留了价格延续、量额为零的一行，Q3 则提供复牌日实际成交行。[Q2][szse-suspended]、[Q3][szse-resumed] 结合 TuShare D1 的停牌缺行说明，**不能直接用交易所行情行数要求 TuShare 返回同样行数，也不能不经统计规则判断就把停牌零行算作平盘家数。** 来源实际报告的零与程序把缺失值填为零，必须保持可辨。该样本未对本账户 TuShare 返回行为作实际验证。

### 3.3 金额范围与单位不能合并成一次容差比较

深交所行情 metadata 明确金额覆盖所有交易方式。TuShare 文档把常规 `amount` 与 `ah_amount` 分列，后者示例说明从 2026-07-06 开始提供。单位上，深交所万元需乘 10 才得到千元；**范围上仍不能据此假定 `amount` 已含所有交易方式，或擅自把 `ah_amount` 加入而不核对是否重叠。** 6 月除息样本也不能证明 7 月新增字段后的范围。上涨成交额占比须先证明分子、分母采用一致的交易方式范围，再检查舍入误差。[Q1 原始 metadata][szse-exdiv]、[D1 字段文档][ts-daily]

上交所 Q4 是官方页面使用的行情服务返回的两行样本。600000：开 9.27、高 9.45、低 9.26、收 9.43、前收 9.27、涨 1.73%，原始量 75765982、额 712270967；600004：收 7.89、前收 7.86、涨 0.38%。P7 的字段顺序与转换显示原始量除 100 显示为手、原始额除 10000 显示为万元，故原始量/额分别按股/元解释。此处是主板 A 股 `ashare` 片段，不能视作科创板或全市场历史行情。[Q4][sse-quotes]、[P7][sse-quote-js]

## 4. 股票池：已取得当前完整样本，尚未证明历史每日完整

| 市场 | 已核实范围 | 点时限制 |
|---|---|---|
| SSE 主板 | L1 有 1700 个唯一 A 股代码；官方 P3 使用 `STOCK_TYPE=1`，与科创板分开。L3 另有终止上市的 A/B 股记录与上市、退市日期。 | L1 的 `queryDate` 为空，只能认定为本次抓取的现行名册。L3 不等于全部证券事件历史，也不包括本次未取到的科创板退市历史。 |
| SSE 科创板 | L2 有 616 个唯一代码。689009 在该列表中，A4 则明确它是存托凭证。 | 不能因为字段名为 `A_STOCK_CODE` 就把全部 616 行自动认定为冻结的 A 股统计集合。CDR 纳入与否须对照既定定义。 |
| SZSE | L4 元数据标示 2026-09-04、2899 记录、145 页、每页 20 条。L5 XLSX 实际包含 2899 个唯一 A 股代码，核对了全量而非只看首页。 | 请求里的 `tab1PAGESIZE=5000` 被服务器忽略；L4 自身不完整。L5 是当前导出，不是 120 个历史日的名册，B 股字段也不能拼入 A 股集合。 |
| BSE | 已尝试官方页面和一份发行人公告原始地址。 | 请求陷入 HTTP 302 重定向循环；未取得本轮可保存核对的官方名册、日线或停复牌原件，不能以搜索摘要或其他站点列表代替。 |

上述集合来源分别是 [L1][sse-main]、[L2][sse-star]、[L3][sse-delisted]、[L4][szse-list-json]、[L5][szse-list-xlsx]、[A4][cdr]。

当前名册与历史名册的差别有具体反例：L3 的 600355 退市日期为 2026-04-27，600421 为 2026-06-26，600193 为 2026-07-06；它们不能因为今日已退市就在更早历史日期全部消失。L5 的 301717 上市日期为 2026-08-11，也不能出现在该日期之前的历史股票池。这些日期事实足以否定“直接用今日存续名单回填历史”的做法，但不足以独自证明每个历史日的有效交易资格、停复牌状态和当时已公开的事件信息。[终止上市原件 L3][sse-delisted]、[深市名册 L5][szse-list-xlsx]

导出单位也需按附件分别解释：L4 JSON 的 A 股总股本/流通股本标题以亿股列示；L5 对 000001 的原始数值为 `19,405,918,198` / `19,405,684,991`，是股数级别而非亿股。不能因为同一页面就共用 JSON/XLSX 的单位转换。股本在此仅辅助核对名册 schema，没有据此新增广度权重。[L4][szse-list-json]、[L5][szse-list-xlsx]

TuShare D2 提供从 2016 年起的历史列表接口说明，可作为后续渠道覆盖核验入口；它本身仍是交付渠道文档，不是交易所独立历史股票池，更不能替代同日原始交付和官方事件抽样。[D2][ts-history]

## 5. 120 个市场日期与 120 条个股观测

复核时 [tushare_context.py](../../src/pring_cycle/tushare_context.py) SHA-256 为 `5aceb1f1249e596da924d6c97d796407641eb8e2d18590130610f606a0714b8b`；其他主线工作仍可能改变源码。该快照 `market_breadth` 第 758–864 行先取得市场交易日，默认读取 `120 + 120 - 1 = 239` 个日期，只在最后 120 个日期输出；每股却在收到有效 `pct_chg`/`amount` 后才向长度 120 的 deque 追加一次。

这产生两个不同窗口：

- **输出窗口**：共同市场日历的最后 120 个日期。该边界已由规格确定。
- **个股计算窗口**：最近最多 120 次有效返回。停牌缺行不推进 deque；因此某日“120 条个股记录”的起点可以早于共同市场日历的第 120 日边界。新上市或缺数股票也可能尚不满 120 条，被排除出 MA 分母。

002084 的停牌事实证明这种差别不是纯假设。若共同 120 日窗口内存在无个股交易的市场日，就不能把“恰有 120 条个股观测”与“恰覆盖同一 120 个市场日期”互换。选择是否在停牌日承接价格、跳过、判定资格不足或采用其他获准规则，属于须冻结的统计定义；本记录不替用户选择。

现实现还把有效返回集合标记为 `point_in_time_traded_a_shares`。一个来源返回若干带代码的行，并不自动证明它完整覆盖当日获准股票池：完整性要与独立名册/事件、应交易与停牌状态、分页/行数限制共同核对。当前仅凭本文官方样本，不能为该维度名称提供全历史认证。

## 6. 发布时间、失败请求与剩余事实

公开点时方面：Q4 返回的 2026-09-04 16:29:01 只能证明该响应携带的行情更新时间；本次未证明它是初次对公众可得时间。Q1–Q3 的 metadata 给出行情统计日，没有给出当日初次发布时间。PDF 的公告落款和 HTTP `Last-Modified` 也不能混同。按 CONTEXT，可靠日期但无可靠时分时适用既定保守日期规则；无法确定可靠发布日期时保留未知，不使用收盘时刻或抓取时刻补齐历史公开点时。[CONTEXT 的公开可用时间定义](../../GLOSSARY.md)

TuShare 的日常入库时间段是渠道计划说明，不证明每条历史记录准时入库；本次不据此把所有观测统一赋予某个当日小时。[D1][ts-daily]

一次深交所跨 2026-08-18 至 08-24 的请求返回空主表；客户端 schema 的日期条件标示 `5d`，随后拆成单日请求取得 Q2/Q3。因此该空响应只能记录为未取得数据，不能作为停牌、零交易或样本通过证据。其原始响应已保留：URL [X1][szse-empty-range]，SHA-256 `45ae9da89e37b305669025d689bfab75cc597199d9e3abd80604a873512c707b`，19575 字节，抓取时刻 10:20:44.268016 UTC。这里观察到的是范围请求与单日请求的差异，没有把服务端空表的原因当成已经证明的因果关系。

北交所以下三个匿名地址在本轮发生重定向循环，无成功原件/哈希，不登记为通过样本：

- [官方页面](https://www.bse.cn/myhead.html)，约 10:17 UTC。
- [官方挂牌公司页面](https://www.bse.cn/nq/listedcompany.html)，约 10:18 UTC。
- [2026-07-29 发行人公告地址](https://www.bse.cn/disclosure/2026/2026-07-29/b899aab3f3f142e88c6a3c53505a9b5d.pdf)，约 10:20 UTC；搜索索引线索未替代原件。

认证前仍需闭合的内容如下，均在既有 family 范围内：

| 剩余项目 | 当前缺口与可以观察的验收证据 |
|---|---|
| 历史股票池与身份 | 沪深北每日有效证券集合、上市退市/代码变更/停复牌等事件及各自公开时点；逐日对比交付返回集合与获准集合，保留差集和原因。当前名单不能回填为历史事实。 |
| 同日渠道抽样 | 使用获准渠道实际返回，与本文普通、除息、停牌、复牌样本按代码/日期/字段比较；本轮未调用账户 API，因此没有此项通过结论。北交所官方样本仍缺。 |
| 量额口径 | `amount` 与所有交易方式汇总的关系、盘后字段新增前后及是否重叠；冻结后分别检验单位换算、范围和舍入容差。 |
| 计算定义 | 对照既定规则确认 CDR、ST、新股、停牌资格、120 日个股回看、零分母、新高低并列和涨跌幅精度；尚未明确者形成有依据的冻结决定，不能自动接受当前实现。 |
| 120 日与预热覆盖 | 用共同日历证明输出精确覆盖目标 120 个市场日；证明所选计算定义的最小预热、个股缺口与资格分母，不以总行数或恰好返回 120 条替代。 |
| 点时与认证登记 | 为原始输入建立可靠公开时间和系统获取事实，再核对许可、派生血缘和认证包。附件存在、文档哈希或当前页面可用，都不等于这些检查通过。 |

[ts-daily]: https://tushare.pro/document/2?doc_id=27
[ts-history]: https://tushare.pro/document/1?doc_id=262
[sse-main]: https://query.sse.com.cn/commonQuery.do?isPagination=false&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&STOCK_TYPE=1&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&pageHelp.pageSize=3000&pageHelp.pageNo=1
[sse-star]: https://query.sse.com.cn/commonQuery.do?isPagination=false&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L&STOCK_TYPE=8&REG_PROVINCE=&CSRC_CODE=&STOCK_CODE=&COMPANY_STATUS=2%2C4%2C5%2C7%2C8&type=inParams&pageHelp.pageSize=3000&pageHelp.pageNo=1
[sse-delisted]: https://query.sse.com.cn/commonQuery.do?isPagination=false&sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_ZZGP_L&STOCK_TYPE=1%2C2&COMPANY_STATUS=3&STOCK_CODE=&type=inParams&pageHelp.pageSize=2000&pageHelp.pageNo=1
[szse-list-json]: https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1110&TABKEY=tab1&tab1PAGENO=1&tab1PAGESIZE=5000
[szse-list-xlsx]: https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1110&TABKEY=tab1
[szse-exdiv]: https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1815_stock_snapshot&txtDMorJC=000001&txtBeginDate=2026-06-11&txtEndDate=2026-06-12
[szse-suspended]: https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1815_stock_snapshot&txtDMorJC=002084&txtBeginDate=2026-08-19&txtEndDate=2026-08-19
[szse-resumed]: https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1815_stock_snapshot&txtDMorJC=002084&txtBeginDate=2026-08-24&txtEndDate=2026-08-24
[sse-quotes]: https://yunhq.sse.com.cn:32042/v1/sh1/list/exchange/ashare?select=code,name,open,high,low,last,prev_close,chg_rate,volume,amount,tradephase&begin=0&end=2
[dividend]: https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-05/bde1eece-e914-4a31-a51d-5de619feb208.PDF
[suspension]: https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-08-19/f427ffb0-9834-47c9-995e-831d9aeb6018.PDF
[resumption]: https://static.cninfo.com.cn/finalpage/2026-08-22/1225492873.PDF
[cdr]: https://www.sse.com.cn/disclosure/announcement/listing/c/c_20201027_5242851.shtml
[sse-list-page]: https://www.sse.com.cn/assortment/stock/list/share/
[sse-delist-page]: https://www.sse.com.cn/assortment/stock/list/delisting/
[sse-list-js]: https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_stocksDepositoryReceipts_2021.js
[szse-list-page]: https://www.szse.cn/market/product/stock/list/index.html
[szse-quote-page]: https://www.szse.cn/market/trend/index.html?code=000001
[sse-quote-page]: https://www.sse.com.cn/market/price/report/
[sse-quote-js]: https://www.sse.com.cn/xhtml/home/2021public/querySearch/search_price_2021.js
[szse-empty-range]: https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1815_stock_snapshot&txtDMorJC=002084&txtBeginDate=2026-08-18&txtEndDate=2026-08-24
