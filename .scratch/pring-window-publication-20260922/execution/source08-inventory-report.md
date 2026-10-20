**票 08 尚不能形成合格认证材料：两核心已有大量日值原件，但已核原件均缺逐值、逐版本发布证据；当前核心正式交付链也确实限定 TuShare。** 本次未改文件、任务或应用库，未联网、读取凭据、运行测试或材料构建，未再委派。以下为 CLI 输出报告。

1. **日值覆盖与哈希**

按固定日历计算：正式窗口为 **2026-04-01—09-22，120 日**；默认公式输入为 **2025-08-29—2026-09-22，259 日**。本次重验两份日历来源哈希、窗口日期哈希及旧复核摘要哈希均通过。

| 核心／来源与取得批次 | 原件实际范围 | 正式窗口覆盖 | 259 日需求覆盖 | SHA-256 前缀，本次核验 |
|---|---|---:|---:|---|
| 000985／CSI，09-06，120 日请求 | 2026-03-09—08-28，120 日 | 103 | 120 | `6e8498041711`，通过 |
| 000985／CSI，09-06，259 日请求 | 2025-08-06—2026-08-28，259 日 | 103 | 242 | `ffe3b20f7c9a`，通过 |
| 000985／TuShare，09-11 | 2017-01-03—2026-08-28，2345 日 | 103 | 242 | `426a275fa698`，通过 |
| 000012／CSI，09-06，120 日请求 | 2026-03-09—08-28，120 日 | 103 | 120 | `a5cc98b01d04`，通过 |
| 000012／CSI，09-06，259 日请求 | 2025-08-06—2026-08-28，259 日 | 103 | 242 | `30b9736664d9`，通过 |
| 000012／TuShare，09-11 | 2017-01-03—2026-08-28，2345 日 | 103 | 242 | `a8a1d69f3a59`，通过 |
| 000012／CSI，09-22 | 2026-09-21，收盘 **230.70** | 1 | 1 | `493e2c43c585`，通过 |

以上均按原件实际日期集合求交，不按行数推算；CSI 两次区间请求的重叠收盘一致，但这不证明历史上没有修订。完整哈希、请求和原件路径见 [CSI 收据](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-04/receipts.json:3)、[TuShare 收据](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/core-transport-196/receipts.json:37)、[000012 单日收据](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-publication-followup-20260922/parent-access-064638454950.json:61)。

在本次已定位并验哈希的日值原件中：

- **000985：103/120、242/259。** 缺值原件日期为：08-31；09-01、02、03、04、07、08、09、10、11、14、15、16、17、18、21、22。
- **000012：104/120、243/259。** 缺值原件为上述集合去掉 09-21，即 16 日。
- 另有旧报告记载 **000985 的 09-15、16、17、18、21 共 5 日**，末日收盘 5921.92；但报告仅称原件保存在会话暂存目录，未给可定位路径及完整哈希，本次不计入已验原件覆盖。见 [探查结果](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-publication-timestamps-20260922.md:25)、[保存限制](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-publication-timestamps-20260922.md:268)。

这是一份**材料覆盖盘点，不是应用认证或 PUBLIC 可用日期矩阵**。

2. **发布证据缺口、日期含义与补证入口**

两核心均缺“承载该日收盘的具体版本，在何日／何时实际公开”的可靠绑定，以及当前回填版本与当时版本的修订关系。259 日计算预热不能豁免；仅有可靠发布日期时，次日本地零点才可见。依据 [ADR0018:7](/mnt/d/cursor/datasourceRF/docs/adr/0018-tiered-evidence-for-historical-publication-dates.md:7)、[ADR0019:7](/mnt/d/cursor/datasourceRF/docs/adr/0019-formula-warmup-requires-publication-evidence.md:7)。

- **000985：** API `tradeDate` 是交易／统计日；基本信息和 factsheet 的 `publishDate=2011-08-02` 是指数推出日。
- **000012：** 同样如此，`publishDate=2003-01-02` 是指数推出日。每日债市页面的“页面生成时间 2023-11-08”是模板时间，不能绑定 2026-09-21 收盘。
- 两份已保存 factsheet 页眉均为 **2026-08-31 资料日期**；本次直接读取 PDF，创建／修改元数据分别为 **09-02 17:42:42+08（000985）**、**09-02 20:36:21+08（000012）**，不是逐日行情首发时间。

已有官方链接中，最直接的后续核查入口是：

| 核心 | 已有官方入口 | 能补什么、当前限制 |
|---|---|---|
| 000985 | [每日指数信息页面](https://www.csindex.com.cn/#/dataService/indexDashboard)、[已用日线接口](https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20260915&endDate=20260922&lang=zh_CN) | 可定位行情与实际附件链接；目前没有已证实合格的逐日发布归档 |
| 000012 | [每日债市页面](https://bond.sse.com.cn/trainings/research/daily/indexD.shtml?TRADEDATE=2026-09-21)、[页面实际指数查询](https://query.sse.com.cn/commonQuery.do?isPagination=false&sqlId=COMMON_BOND_PXYFW_YJFX_MEZS2_L&TradeDate=2026-09-21) | 页面确实存在，但既存目标日查询返回空 `result`；未取得值与发布时间共同出现的记录 |

**不应原样重试的已失败路径：** CSI 公告接口 `selectNoticeRe` 的 GET／JSON POST 均返回业务码 500；000985 旧研究 PDF 路径只得到首页／JS 提示；分时接口忽略历史日期、返回当天数据，不能充当历史发布归档；000012 上述动态查询已有空响应。详见 [既有失败记录](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-publication-timestamps-20260922.md:25)、[独立探测](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-publication-followup-20260922/delegated-probe.md:9)。

本地权限错误、代理错误、业务异常和空响应必须分别记录，均不能推导“来源不存在”。

3. **API／历史 sheet 是否藏有可利用字段**

- **两核心已保存行情 JSON：** 本次检查全部行键，仅有 `tradeDate`、代码名称、OHLC、涨跌、成交、样本数、`peg` 等字段；没有发布时刻、发布日期、修订号或版本号。两份 TuShare 原响应也仅有 `ts_code,trade_date,close,pre_close,pct_chg`。
- **已保存 factsheet：** 两份 PDF 均验哈希通过：000985 为 `bade84f86721…`，000012 为 `14a822151568…`。可利用的是资料日期、身份及方法线索，不能从曲线重建逐日精确收盘或发布时间。000012 原件索引见 [收据:30](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-tavily-document-0.json:30)，既有逐栏核对见 [复核:87](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/search-preexperiment-document-review.md:87)。
- **历史 XLS：** 旧报告称 `000985perf.xls` 仅含 **2021-07-27—08-27 的 24 行**，对本轮覆盖为零；其 2024 年 `Last-Modified` 不能给这些日值定首发时间。本次未定位该暂存副本，不能宣称已重新检查全部 sheet／隐藏字段。000012 没有在所查索引中定位到对应日线历史工作簿，不能外推 000985 的情况。
- 官方文件服务规范中的 18:00／20:00／23:00 是正常服务时限或打包计划，不是实际逐值发布证据。[研究依据:116](/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/research-04.md:116)。

4. **正式合同与 CSI 最小交付入口——以下为只读代码推断**

**两核心现有完整链路只支持 TuShare；通用收据和双点时仓库本身并非如此。**

| 环节 | 实际限制 |
|---|---|
| 公开采集命令 | `core-history-refresh` 构造 `TushareCoreAdapter`：[cli.py:365](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:365) |
| 原件重解析 | 固定 provider、API、字段及 `tushare-core-parser-v0002`：[source_adapters.py:25](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_adapters.py:25) |
| 声明／目录合同 | 固定 `provider=tushare` 及来源引用格式：[source_contract_review.py:164](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:164) |
| 消费者 | 选中声明仍检查 TuShare 身份，并重验原件：[source_adapters.py:72](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_adapters.py:72)、[worker.py:945](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:945) |

最小可审阅交付应是：**为这两个固定核心增加明确的 CSI 来源分支和本地原件导入入口**，复用 [AcquisitionRepository.capture](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:144) 保存真实字节、原获取收据和解析版本；同步接通解析、声明合同与消费者校验，逐声明绑定发布证据。CSI JSON 没有 `pre_close`，而当前 `MarketBar` 要求它；应明确支持所需的收盘字段合同，不能反造 TuShare 响应或伪造前收盘。[adapters.py:35](/mnt/d/cursor/datasourceRF/src/pring_cycle/adapters.py:35)。

未知 PUBLIC 保持空；导入时 SYSTEM 按实际取得并校验记录，不能回填旧抓取时间。通用日期转换已有实现，但**转换不认证证据**：[evidence.py:50](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:50)。来源合格后仍须形成新的审核包、目录／模型绑定，沿 [候选认证入口](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:434) 验收，不能把 parser 的 `certified` 字符串当认证。

优先操作建议：

- 先找回 000985 新增 5 日的暂存原件及完整收据；找不到则保留“报告记载、原件未核验”。
- 后续授权采集只补上述缺日期，并优先寻找**同时承载数值、版本及实际发布日期**的官方记录；不重复空端点网格。
- CSI 软件接入与发布证据补齐分别推进；两者未齐前，票 08 不具备完成依据。票状态由主代理处理。