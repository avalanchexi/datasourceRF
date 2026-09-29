# 候选 4 补充勘察：失败分类从哪里来

来源：Codex 只读勘察（2026-09-29，`gpt-6-astra`／high），原样收录其结论。已抽查属实：TuShare 非零业务码在 `tushare_context.py:893` 抛 `TushareSourceError`（40203 单列限频），该类继承 `ValueError`，进入检索账本 `retrieval_ledger.py:452` 被归为 `semantic_validation_failed`；LPR 失败尝试只记 period／provider，不带原因（`official_lpr.py:430`）。访谈结论见 [README](README.md)。

1. **结论：不能把“异常统一翻译为 outcome”整体交给 Worker，也不能让获取结果模块从现有 outcome 反推失败阶段。**

| 判断 | 依据 |
|---|---|
| 来源适配器应解释来源响应；步骤执行者应记录实际阶段 | TuShare 适配器看得到业务码，官方解析器看得到页面、字段与缺文件信息；Worker 通常只剩异常类和字符串。`tushare_context.py:891`、`official_context.py:810`、`worker.py:1932` |
| 获取结果模块应负责跨尝试归并，不负责重新猜测来源事实 | 目前同一个 `validation_failed` 既表示结构拒收，也表示入库拒收；同一个 `source_failed` 既表示网络失败，也可能表示报价文件解析失败。`worker.py:1961`、`quote_sources.py:205` |
| 消费者类别应留给消费者 | 缺口清单回答“为什么缺”，LPR 回答“是否应获取”，检索账本回答“是否重试及何时重试”，这些问题不能共享一个终态。`freshness.py:868`、`release_calendar.py:96`、`retrieval_ledger.py:782` |
| “阶段＋原始原因＋消费者类别”还不够 | 必须另保留交付范围及完整性，否则 `missing_values`、`missing_fields`、`partial_validation` 仍会混入失败枚举。`worker.py:1943`、`worker.py:1964`、`treasury_context.py:426` |
| 当前分类有明确历史依据，也有偶然的异常类型分流 | VIX 解析错记来源失败有明确票据；`TypeError` 在不同路径中的不同解释，未见统一语义依据。`.scratch/gap-sources-20260925/issues/06-vix-cboe-official.md:8`、`worker.py:1952`、`official_context.py:867` |

本报告仅静态读取本地代码与文档；未修改文件、运行测试、访问网络或调用外部接口。下文裸 `*.py` 路径均指 `src/pring_cycle/`；表中“未写”表示该路径没有对应写入，不能解释为运行中必然没有其他记录。

2. **先校正存储对象：`acquisition_request` 实际字段叫 `state`，不是 `status`；它与 `retrieval_attempt.outcome` 不是同一层。**

| 写入对象／触发条件 | 写入值 | 判断者与写入证据 |
|---|---|---|
| 开始一次 capture | `state=started` | 回执仓库在执行 `on_started`、fetch 之前创建；因此存在回执不证明已经发请求。`acquisition.py:179`、`acquisition.py:204` |
| fetch 返回 bytes，收到时间有效 | `state=received`，随后保存原件 | 通用回执仓库，只证明收到可保存的字节。`acquisition.py:220`、`acquisition.py:330` |
| fetch 抛出未经包装的 `HTTPError` | 读取错误正文，先记 `received`，再重抛 | 通用捕获逻辑保留正文，不先判断 HTTP 业务意义。`acquisition.py:212` |
| parse、normalize、规范化保存通过 | `state=validated`、`structure_check=passed` | 通用回执仓库；这不保证已经生成标量或入库。`acquisition.py:222`、`acquisition.py:273` |
| capture 内任意 `Exception`，原状态为 `started` | `state=failed`、`structure_check=NULL`、`error_type=类名`、`rejection_reason=str(error)[:300]` | 外层笼统 catch；包括网络、回调拒绝、本地时间或字节类型错误。`acquisition.py:229`、`acquisition.py:295` |
| capture 内任意 `Exception`，原状态为 `received` | `state=failed`、`structure_check=rejected`，同样保存类名和原因 | 依据是“是否已 received”，不是“是否真的执行了结构检查”；HTTP 错误正文也会进入此分支。`acquisition.py:285` |
| 上一行异常为 `CandidateSkipped` | 改记 `structure_check=skipped`，`state` 仍为 `failed` | 通用仓库识别类型，但是否该跳过由官方来源解析流程决定。`acquisition.py:67`、`acquisition.py:292` |
| 已 validated，调用入库结果记录 | `ingest_result=accepted/rejected`；拒收时 `ingest_rejection_reason=str(error)[:300]` | 调用方提供成功／异常，仓库只写一次；不会把 `state` 改成 failed。`acquisition.py:302` |
| 调用 `record_retrieval_attempt` | 原样保存调用方的 `outcome` 和 metadata | `reason/condition/error_type/stage` 都不是独立列，也没有在这里按异常再分类。`evidence.py:1296`、`evidence.py:1324` |

**关键限制：**“入库结果为空”不等于“没有入库”；财政部 CSV、EIA、ECB、中证核心等路径没有调用 `record_ingest_result`，详见第 4 条。回执状态枚举定义在 `acquisition.py:469`。

3. **TuShare 写入方：业务响应先由 helper 判断，最终指标级失败多数由 Worker 二次翻译。**

**3.1 通用写入规则**

以下 T1—T7 是本报告对现有分支的编号，不是建议新增的枚举。

| 编号／来源位置 | 最初判断依据 | 写入值 | 写入点／判断者 |
|---|---|---|---|
| T1：所有 `TushareContextAdapter._call` 接口 | JSON `code != 0`；40203 特判，其余保留数字 | 回执为 `failed/rejected`、`error_type=TushareSourceError`；Worker 写 `outcome=source_failed`、同类名及 `reason` | raise：`tushare_context.py:896`；指标写入：`worker.py:1932` 经 `worker.py:1663` |
| T2：上下文请求或后续处理抛 `OSError` | HTTPError、URLError、连接／超时等异常，亦未排除本地 I/O 错误 | Worker 写 `source_failed`、实际类名、异常字符串；不写 `stage` | `worker.py:1932`；按 Python 类型判断，不是按来源码 |
| T3：结构、身份、日期、数值等错误 | helper 明确 raise `ValueError`，或调用中自然发生 `KeyError/TypeError` | `TypeError→adapter_failed`，其余→`validation_failed`；写类名、`reason`、`stage=response` | `worker.py:1942`、`worker.py:1952`；回执按第 2 条处理 |
| T4：入库调用被拒 | `ingest_context_scalars` 抛 `KeyError/TypeError/ValueError`，空标量专用异常除外 | 回执 `ingest_result=rejected`；包装为 `ContextIngestRejectedError`，Worker 写 `validation_failed, stage=ingest, reason` | `tushare_context.py:335`、`tushare_context.py:347`、`worker.py:1961` |
| T5：空标量，且属于增量家族或整族采用 reviewed delivery | `ContextObservationsMissingError`＋Worker 的家族／目录条件 | `missing_values`；只带家族等身份，没有 `reason/error_type/stage` | raise：`tushare_context.py:958`；翻译：`worker.py:1943` |
| T6：成功交付及部分交付 | 底层已有标量入库；Worker 查看实际指标集合和 `rejected_field_count` | 底层 `verified_candidate`；Worker 对已交付指标写 `partial_validation` 或 `verified_candidate`，对未交付指标写 `missing_fields` | `tushare_context.py:1155`、`worker.py:1964`；部分交付由结果内容判断 |
| T7：没有配置 token | 本地 secrets 中 `TUSHARE_TOKEN is None` | 仅 GDP、2Y、10Y 写 `missing_credentials`、`condition=TUSHARE_TOKEN_not_configured`、`request_sent=false` | `worker.py:1761`；Worker 判断，无请求回执 |

**3.2 按接口家族展开**

下表所有上下文家族均共用 T1—T4、T6；T5 是否适用由 `worker.py:1943` 的条件决定。

| 来源／接口家族 | 来源语义或本地校验的起点 | 写入及判断归属 | 证据 |
|---|---|---|---|
| 市场指数：`index_daily/fut_index_daily` | 请求具体指数代码；检查返回代码、重复交易日及数值 | 成功写 T6；业务拒绝写 T1，结构错误经 Worker 写 T3 | `tushare_context.py:668`、`tushare_context.py:1233`、`worker.py:1800` |
| 市场广度：`trade_cal/stock_basic/daily/stk_factor_pro` | 本地以 held days 排除已持有日；检查证券范围、上市信息、重复报价等 | 空增量走 T5；`stk_factor_pro` 的 OSError/ValueError 被 helper 吞掉，日频部分仍可成功，缺失指标走 T6 的 `missing_fields` | `breadth.py:299`、`breadth.py:315`、`breadth.py:329`、`worker.py:1812` |
| 融资余额：`margin`，全市场家族 | 交易所身份、重复交易所日、余额非空，以及交易所覆盖 | 错误经 T3；成功经 T6 | `tushare_context.py:690`、`tushare_context.py:717`、`worker.py:1821` |
| 沪深融资余额：`margin`，SSE/SZSE 家族 | 同一 API，另有沪深成员与覆盖契约 | 与全市场采用同样 outcome 翻译，但由目录选择哪一家族执行 | `tushare_context.py:746`、`tushare_context.py:1350`、`worker.py:1914` |
| 指数估值：`index_dailybasic` | 指定指数身份、重复日期、估值字段 | 错误经 T3；成功经 T6 | `tushare_context.py:841`、`tushare_context.py:1284`、`worker.py:1832` |
| 商品篮子：`fut_basic/fut_trade_cal/fut_daily` | 合约身份、单位、到期选择、结算价及本地链式计算 | 无待算日期走 T5；有待算日期却全部算不出时抛第一条本地原因，走 T3 | `basket.py:164`、`basket.py:195`、`basket.py:261`、`basket.py:296` |
| PMI：`cn_pmi` | `_response_rows` 验证必要列；月度 helper 跳过无数值字段 | 部分指标未生成写 `missing_fields`；整族空值按 T5 条件，否则 T3 | `tushare_context.py:394`、`tushare_context.py:1201`、`tushare_context.py:2164` |
| CPI/PPI：`cn_cpi/cn_ppi` | 两个请求合成一个 `prices` 家族；按月与字段生成标量 | 任一请求抛错可使 Worker 对整家族写失败；成功但只交付部分指标写 `missing_fields` | `tushare_context.py:406`、`worker.py:1848`、`worker.py:1972` |
| 货币：`cn_m` | 目录决定是否请求环比；月度字段缺值被跳过 | T1—T6；空值与已持有无增量不是同一事实，但可能都落成 `missing_values` | `tushare_context.py:441`、`worker.py:1853`、`worker.py:1943` |
| 社融：`sf_month` | 旧 helper 与 reviewed total helper 字段范围不同 | T1—T6；家族选择由目录 marker 决定 | `tushare_context.py:462`、`tushare_context.py:496`、`worker.py:1787` |
| 仓单：`fut_wsr`，CU/RB/PP/RU/SP/SC | 按品种、日期分块；检查截断、品种、单位、负数量、成员字段是否部分缺失 | T1—T4、T6；Worker 失败记录带 `symbol`，底层成功记录不带该字段 | `tushare_context.py:40`、`tushare_context.py:549`、`tushare_context.py:2009`、`worker.py:1924` |
| GDP：`cn_gdp` | 名义累计 level 可交付；同比字段因统计期语义未核实被列入 rejected fields | 有 level 时，底层成功，Worker 可写 `partial_validation`；原因在规范化字段拒绝记录中 | `tushare_context.py:586`、`tushare_context.py:1581`、`tushare_context.py:1611`、`worker.py:1968` |
| 美债：`us_tycr` | 按 `y2/y10` 分别判断是否有数值 | 一项有值、另一项无值时写 `verified_candidate`＋`missing_fields`；不是按 HTTP 成败区分 | `tushare_context.py:610`、`worker.py:1893`、`worker.py:1975` |
| 利率传导：`repo_daily/shibor` | DR007 身份及期限、Shibor 各期限字段；入库另核查来源字段 | 结构错误 T3，注册字段契约拒绝 T4 | `tushare_context.py:644`、`tushare_context.py:1006`、`worker.py:1901` |
| 核心历史：`trade_cal/index_daily/fut_index_daily` | **不用 T1 helper**；非零业务码统一抛普通 `ValueError("tushare_source_failed")` | 失败只留 capture 回执；成功由历史刷新写 `outcome=verified`，不是 `verified_candidate` | `source_adapters.py:227`、`source_adapters.py:394`、`core_history.py:109`、`core_history.py:189` |
| TuShare 资讯：`major_news` | 非零业务码后检查 `msg` 是否含“频率超限” | 回执记普通 ValueError 及 `tushare_rate_limited/tushare_source_failed`；`pull_news` 返回结果字符串，不写指标获取尝试 | `tushare_news.py:133`、`tushare_news.py:150`、`tushare_news.py:160` |
| 发布预告：`cn_schedule` | 非零业务码或 data 非 dict→`cn_schedule_source_failed`；另验字段与日期 | 只写 capture 回执，失败被刷新流程吞掉，转用国家统计局日程 | `release_schedule.py:74`、`release_schedule.py:194`、`release_schedule.py:207` |

4. **官方来源及其他回执写入方：多数没有来源专用异常类，而是“原因字符串＋内置异常类”。**

**4.1 官方来源逐行清单**

表中所有 capture 的 `state/structure_check/rejection_reason/error_type` 均按第 2 条通用规则落库；下表补充各来源自己的判断及指标级写入。

| 来源 | 最初判断依据与异常起点 | 写入的指标级值／入库结果 | 判断者及写入点 |
|---|---|---|---|
| 国家统计局：CPI、PMI、PPI | 官方页面表头、行身份、统计期与数值；共用表格 helper 抛 `official_context_table_schema_mismatch/row_identity_mismatch` 等 ValueError | OSError→`source_failed`；TypeError/ValueError→`validation_failed`，均写类名，仅 ValueError 写 `reason`；成功→`verified_candidate` | 本地来源解析后，由来源刷新外层按异常类翻译；`official_context.py:1068`、`official_context.py:2481`、`official_context.py:864`、`official_context.py:665` |
| 国家统计局：GDP | 页面统计口径、产业成员、现价绝对额／不变价增速契约；错误包括 `registered_gdp_table_contract_mismatch` | 同上一行；实际入库调用成功／拒绝还写 `accepted/rejected` 与拒收原因 | `official_context.py:1236`、`official_context.py:537`、`official_context.py:864` |
| 国家统计局：工业增加值 | 表格身份与字段；一月月值直接抛 `official_context_january_monthly_value_not_reported` | 该来源语义也会被外层翻译成 `validation_failed`，而非统一的“未披露”结果 | `official_context.py:1323`、`official_context.py:867` |
| 国家统计局：工业财务、库存、周转及产能利用率 | 行集合、单位、表格语义；产能映射另检查 Q1、累计列和身份 | 同样写 `source_failed/validation_failed/verified_candidate`；没有家族专用 outcome | `official_context.py:1456`、`official_context.py:1461`、`official_context.py:1689`、`official_context.py:864` |
| 央行：货币、社融、贷款结构 | 货币文本须匹配余额／同比；社融分项及贷款行集合须符合口径 | 例如 `official_context_money_values_missing`、`social_financing_components_mismatch`、`loan_structure_rows_mismatch` 经外层写 `validation_failed＋reason` | `official_context.py:2393`、`official_context.py:2124`、`official_context.py:2305`、`official_context.py:875` |
| 央行：OMO、工具流动性、降准、中间价 | 公告表格／文字身份、生效期、覆盖范围、工具身份及 USD/CNY 报价 | 正常失败采用官方宏观共用分类；成功和入库回写也共用 | `official_context.py:1082`、`official_context.py:1967`、`official_context.py:2081`、`official_context.py:2455` |
| 国家统计局／央行公告列表 helper | 列表中没有指定期公告→`official_context_release_link_not_found`；链接不唯一另抛 ValueError | 列表本身可已 `validated/passed`，随后刷新仍写 `validation_failed＋reason` | `official_context.py:728`、`official_context.py:757`、`official_listing.py:105`、`official_context.py:864` |
| 央行 OMO 同日多份公告 | 非最后一份公告因表格类型不符，不属于要取的指标 | 抛 `CandidateSkipped`，回执为 `failed/skipped`；外层继续下一份，不在这里写指标失败 | `official_context.py:820`、`official_context.py:858` |
| 央行降准追溯栏目／大事记 | 空栏目或变化不可解析；没有变化与“变化但读不懂”分开 | helper 只写回执；`official_context_rrr_change_unreadable` 是本地解析原因，追溯结论另归事件发现流程 | `official_context.py:968`、`official_context.py:1025`、`official_context.py:1033` |
| 中国货币网／外汇交易中心：LPR | 页面须有 LPR 与授权身份、发布日期、正确月份与两期限利率；响应非 200 检查抛 ValueError | OSError→`source_failed`，ValueError→`validation_failed`；失败尝试只带 period/provider，**不带类名、原因或阶段** | `official_lpr.py:129`、`official_lpr.py:404`、`official_lpr.py:430` |
| LPR 成功及入库 | LPR 转成官方上下文 release 后交给公共入库流程 | 成功写 `verified_candidate`，渠道为 `official_direct_candidate`；回执写 accepted/rejected，失败渠道却是 `certified_official_direct` | `official_lpr.py:360`、`official_context.py:537`、`official_context.py:665`、`official_lpr.py:433` |
| 美国财政部国债 CSV | HTTPError 先转成响应对象；非 200→OSError，错误表头、行宽、日期、负名义收益率→ValueError | 每期限写 `verified_candidate/missing_values`；异常写 `source_failed/validation_failed＋error_type`，保存 HTTP 状态，**不写通用 reason/stage，也未回写 ingest_result** | `treasury_context.py:300`、`treasury_context.py:365`、`treasury_context.py:113`、`treasury_context.py:429`、`treasury_context.py:468` |
| EIA API：Brent/WTI | 请求 HTTP 异常；本地校验 response、频率、series、单位、日期和有限数值 | 底层只写成功 `verified_candidate`；失败由 Worker 写 OSError→`source_failed`、TypeError→`adapter_failed`、ValueError→`validation_failed`，仅附类名／family | `eia_context.py:137`、`eia_context.py:363`、`eia_context.py:327`、`worker.py:1591` |
| EIA API：无 key | 本地配置 `EIA_API_KEY is None` | 两指标写 `missing_credentials`、`condition=EIA_API_KEY_not_configured`、`request_sent=false`，随后尝试 HTML | `worker.py:1573` |
| EIA HTML：两张历史价格表 | 非 200→OSError；标题／日列／周坐标／Release Date／单元格格式错误→ValueError | 每指标写 `verified_candidate/missing_values`；异常写 `source_failed/validation_failed＋error_type＋HTTP信息`，未回写 ingest_result | `eia_html.py:380`、`eia_html.py:244`、`eia_html.py:458`、`eia_html.py:485` |
| EIA HTML：Worker 再概括 | 整个两指标循环有没有抛错，不检查每个返回结果 | 出错给两指标统一写 `source_failed/adapter_failed/validation_failed`；无异常给两指标统一写 `verified_candidate` | `worker.py:1609`、`worker.py:1621`、`worker.py:1634` |
| ECB 参考汇率 ZIP/CSV | 非 200、响应不完整→OSError；ZIP、列、日期、腿值、交叉汇率→ValueError | capture 内失败写 `source_failed/validation_failed＋error_type＋HTTP信息`；成功写 `verified_candidate/missing_values`，未回写 ingest_result | `ecb_reference.py:355`、`ecb_reference.py:141`、`ecb_reference.py:504`、`ecb_reference.py:612` |
| ECB：Worker 补记 | adapter 抛错后，检查最新失败是否已关联本次全部 acquisition ids | 缺少同次失败记录时补 `source_failed/validation_failed＋error_type`，没有 `reason/stage` | `worker.py:1698`、`worker.py:1705`、`worker.py:1711` |
| Cboe VIX CSV | HTTP 错、协议错、超大响应→OSError；表头、行、重复日期等→ValueError | 获取／解析阶段两种异常一律 `source_failed＋error_type＋reason`；入库 ValueError 则 `validation_failed, stage=ingest, reason`，并回写 rejected | `quote_sources.py:44`、`quote_sources.py:151`、`quote_sources.py:205`、`quote_sources.py:254` |
| 中国货币网 USD/CNY 16:30 文件 | JSON 字段、正价格、16:30 快照一致性；未到 16:30 或尚无收盘价返回空 | 共用报价写法；非空→`verified_candidate`，空→`missing_values`，没有专门的 awaiting_release 条件 | `quote_sources.py:81`、`quote_sources.py:98`、`quote_sources.py:267` |
| 郑商所 TA/CF 仓单日报 | HTTP 错→`OSError(czce_warrant_http_<码>)`；日期、品种块、表头、负数、仓库重复、总计错误→ValueError | 按品种日写 `source_failed/validation_failed＋error_type＋reason`；入库拒绝写 `validation_failed, stage=ingest` 并回写 rejected；成功写 verified_candidate | `czce_warrants.py:106`、`czce_warrants.py:147`、`czce_warrants.py:250`、`czce_warrants.py:460`、`czce_warrants.py:499`、`czce_warrants.py:511` |
| 上期所／大商所及能源中心 | 本次扫描未发现独立官网获取写入方；相关仓单仍由 TuShare `fut_wsr` 提供 | 不能把 TuShare 参数里的交易所身份算作官网直连；TA/CF 才切换郑商所官网 | `tushare_context.py:40`、`tushare_context.py:508`、`docs/adr/0032-czce-warrants-from-exchange-daily.md:14` |
| 中证指数官网核心 JSON | HTTP 状态／重定向→OSError；JSON 业务 `code!="200"`、错误身份／日期／价格→ValueError | capture 写回执；本函数没有指标级 retrieval_attempt，也没有 ingest_result 回写 | `official_core.py:77`、`official_core.py:133`、`official_core.py:162`、`official_core.py:185` |
| 国家统计局发布日程 | 状态／重定向→OSError；日程表日期及行结构→ValueError | 只写 capture 回执，异常被吞掉，时效计算回退至推定发布时间 | `release_schedule.py:155`、`release_schedule.py:165`、`release_schedule.py:214` |

**4.2 其他会写同一回执表的入口**

这些入口不能因为共用 `acquisition_request` 就被算成注册来源的指标获取尝试。

| 入口 | 判断依据与写入 | 证据 |
|---|---|---|
| 官方文档本地导入，包括 LPR | `fetch=lambda:content` 也走 started→received→validated/failed；这些状态不证明发生过网络请求 | `official_context.py:496`、`official_lpr.py:312` |
| ECB 本地导入 | 无 fetcher 时读传入 content，渠道为 `ecb_reference_import`；仍产生回执与指标尝试 | `ecb_reference.py:464`、`ecb_reference.py:471` |
| Tavily/Exa 搜索响应 | HTTP 失败被解析为正常的 `RetrievalAdapterResponse("failed", classification=...)`，因未抛异常，回执仍可 validated/passed | `search_discovery.py:69`、`search_discovery.py:150` |
| 搜索候选页／媒体页 | 非 200、白名单、解码或资讯规则失败抛 `CandidateRejected`，capture 记 rejected；候选级原因另入检索记录 | `search_evidence.py:662`、`search_evidence.py:669`、`search_evidence.py:775`、`search_evidence.py:788` |
| AI WebSearch 交换材料 | 把本地组装的问答 JSON 当 capture 原件；候选解析失败写回执 rejected，再将账本记 semantic_validation_failed | `ai_websearch.py:309`、`ai_websearch.py:312`、`ai_websearch.py:327` |

5. **异常源头和信息损失：40203 在 Worker 层仍可辨认，在当前检索账本分类中不可辨认。**

| 异常／来源 | raise 位置及携带信息 | 向外传播时保留与丢失 |
|---|---|---|
| `TushareSourceError(ValueError)` | 唯一实时请求 raise 位于 `_call.parse`；40203→`tushare_rate_limited`，其他码→`tushare_source_failed:<code>` | 没有结构化 code/msg 属性；`msg` 未进入异常，原 JSON 在 capture 成功保存原件时仍可追溯。`tushare_context.py:146`、`tushare_context.py:893` |
| 上述异常进入 Worker | Worker 特判该类，写 source_failed、类名和最多 300 字的 reason | **限频与其他业务码仍能从 reason 区分**；但没有权限业务码映射表，不能把所有其他码直接称为无权限。`worker.py:1932`、`tushare_context.py:897` |
| 上述异常进入补缺账本 | `trace_acquisition` 只看到它是 ValueError | 统一变成 `failed/semantic_validation_failed`，不检查其字符串；随后 `_RequestFailed` 只带已翻译的 response。`retrieval_ledger.py:452`、`targeted_context.py:153`、`targeted_context.py:28` |
| `ContextObservationsMissingError(ValueError)` | `ingest_context_scalars` 在 scalars 为空时抛出；固定消息 `tushare_context_observations_missing` | 没有“因为都已持有”或“上游空交付”的原因字段；Worker 靠家族／目录猜分支，不能由该类型证明无新增。`tushare_context.py:139`、`tushare_context.py:958`、`worker.py:1943` |
| `ContextIngestRejectedError(ValueError)` | 只在 `acquire_scalars` 包围入库调用的 catch 中包装；字符串沿用原异常，`__cause__` 保留原异常对象 | Worker 所记类名变为包装类，原 KeyError/TypeError 类别没有单独落库；阶段和原因字符串保留。`tushare_context.py:344`、`worker.py:1955` |
| TuShare 核心／日历普通 ValueError | `_response_document` 对所有非零业务码抛 `tushare_source_failed` | code 和 msg 均从异常信息中丢失；与上下文 adapter 的保留方式不同。`source_adapters.py:394` |
| TuShare 资讯普通 ValueError | 非零码后用 `msg` 的“频率超限”子串判断限频 | 只保留二分后的字符串，不保留 code 或原 msg；不是 40203 专用判断。`tushare_news.py:133` |
| 官方来源一般错误 | 未发现 NBS/PBC/LPR/Treasury/EIA/ECB/Cboe/CZCE 各自定义的 SourceError 类；主要为内置 ValueError/OSError 加原因字符串 | 同一种类跨越配置、传输、解析、契约与本地时间错误，外层只按类型分类必然丢语义。`official_context.py:861`、`treasury_context.py:466`、`quote_sources.py:205`、`acquisition.py:417` |
| 官方宏观／LPR 收到非 200 响应对象 | 宏观抛 `official_context_source_http_status_invalid`，LPR 抛 `lpr_source_http_status_invalid`，均为 ValueError | 没有把具体 HTTP 数字加入异常；LPR 指标失败记录连字符串也不保留。`official_context.py:2559`、`official_lpr.py:404`、`official_lpr.py:436` |
| Treasury/EIA HTML/ECB 收到 HTTPError | 各自把错误变成响应对象，保存正文／状态，parse 再抛普通 OSError | 指标 metadata 保留 HTTP 数字，但异常已不再是 HTTPError；只看异常的账本无法取得该数字与 Retry-After。`treasury_context.py:300`、`eia_html.py:330`、`ecb_reference.py:372`、`retrieval_ledger.py:444` |
| Cboe/CFETS 报价文件 HTTPError | 包装为 `OSError("quote_source_http_<code>")` | 数字在 reason 中，原 HTTPError 留在异常链；通用 capture 看不到 HTTPError，因而不会走错误正文接收分支。`quote_sources.py:161`、`acquisition.py:212` |
| 郑商所 HTTPError | 包装为 `OSError("czce_warrant_http_<code>")` | 与报价文件相同；另外 `_DayResponse.unreachable` 还会解析这个字符串，区分“答复了”与“没连上”。`czce_warrants.py:250`、`czce_warrants.py:386` |
| ECB 协议／半截响应 | `HTTPException` 包成 `ecb_reference_http_protocol_failed`；IncompleteRead 转成 `complete=false`，后续抛 response_incomplete | 前者具体协议类只在 cause 中；后者仍在 metadata 中保留完整性及 Content-Length，但失败尝试不保存通用 reason。`ecb_reference.py:378`、`ecb_reference.py:393`、`ecb_reference.py:511` |
| `CandidateSkipped(ValueError)` | OMO 非最后一份候选的表格不匹配；沿用原错误字符串 | 回执明确 skipped，循环继续；来源语义没有完全丢失。`official_context.py:820`、`acquisition.py:292` |
| `CandidateRejected(ValueError)` | 搜索验证根据 HTTP、白名单、统计期、日期、规则等显式 raise | 消息本身就是候选原因码，候选原因翻译优先原样保留；它不是官网专用异常。`search_evidence.py:498`、`search_evidence.py:502` |
| 注册契约拒绝 | evidence 检查目录、单位、维度、合法值，并调用来源契约；另检查回执时间和 validated 状态 | 原因来自本地契约，不来自上游响应码；是否保留为入库阶段，取决于来源是否包围入库调用并回写。`evidence.py:1499`、`source_contract_review.py:190`、`evidence.py:574`、`evidence.py:602` |
| 自然发生的 TypeError/KeyError | 所查主要来源模块未见显式 `raise TypeError/KeyError`；它们主要由索引、转换、回调或其他调用自然抛出 | 不能仅靠类型确认“适配器故障”还是“坏数据”；例如 EIA 数值转换的 TypeError 先被主动包装成 ValueError。`eia_context.py:403`、`worker.py:1952` |

另有一个反例说明“未 received”也不能直接解释为网络失败：`on_started` 可在 fetch 前因预算拒绝抛 `RetrievalBudgetBlocked`，回执因此 failed，却没有发出该请求。证据：`acquisition.py:204`、`retrieval_ledger.py:430`、`retrieval_ledger.py:180`。

6. **相同事实被不同写入方翻译成不同值的地方。**

“有依据”在这里区分“明确要求”和“实施记录承认现状”；后者不能自动成为永久保留的设计理由。

| 相同事实／差异 | 现行翻译与影响 | 票据／ADR／CONTEXT 依据 |
|---|---|---|
| TypeError | Worker 的 TuShare/EIA→`adapter_failed`；官方宏观、Treasury、EIA HTML、ECB→`validation_failed` | **未见依据**要求按调用层采用不同语义。`worker.py:1591`、`worker.py:1952`、`official_context.py:867`、`ecb_reference.py:508` |
| 入库内部 TypeError | TuShare 包成 ContextIngestRejectedError 后→`validation_failed, stage=ingest`；EIA API 原 TypeError→`adapter_failed` | TuShare 包装有明确依据，但跨来源差异未见统一要求。`.scratch/gap-sources-20260925/issues/03-receipt-ingest-result.md:14`、`eia_context.py:89`、`worker.py:1597` |
| TuShare 非零业务码 | 上下文 Worker→`source_failed`；核心 helper→普通 ValueError；账本→`semantic_validation_failed` | 保留业务码有明确要求；账本差异被记为“既有行为，本次没改”。`.scratch/run-findings-20260928/issues/02-fut-wsr-request-volume.md:48`、同文件`:75` |
| HTTP 错误正文 | 回执可 `structure_check=rejected`，指标尝试却为 `source_failed`；错误正文不等于指标结构被检查过 | 回执“收到后失败记 rejected”的既有规则有实施依据，但未见依据把所有 HTTP 错误认定为结构失败。`.scratch/run-findings-20260928/issues/02-fut-wsr-request-volume.md:47`、`acquisition.py:212` |
| 非 200 响应对象 | 宏观/LPR/EIA API 检查抛 ValueError→validation_failed；Treasury/EIA HTML/ECB 抛 OSError→source_failed | **未见依据**支持这种按来源变化的 HTTP 失败语义。`official_context.py:2560`、`eia_context.py:216`、`treasury_context.py:366` |
| 报价文件解析 ValueError | VIX/CFETS→`source_failed`；财政部 CSV/ECB→`validation_failed` | VIX 有明确票据；CFETS 票记“与 VIX 同一接法”，未单独论证异常分类。`.scratch/gap-sources-20260925/issues/06-vix-cboe-official.md:8`、`.scratch/gap-sources-20260925/issues/07-usdcny-1630-chinamoney.md:24` |
| 官方表格解析错与注册契约拒绝 | 都可写 `validation_failed`；缺口清单都映射为 `ingest_rejected`，不读 stage | 映射本身有明确实施记录，不能当作无意漏写；但其名字比实际覆盖范围窄。`.scratch/gap-sources-20260925/issues/04-gap-categories-by-cause.md:16`、`freshness.py:863` |
| 同为入库拒收 | TuShare、报价、郑商所有指标 stage；官方宏观有回执 ingest_result 但无指标 stage；Treasury/EIA/ECB 未回写 ingest_result | 入库分段记录有明确票据；覆盖不一致**未见依据**。`.scratch/gap-sources-20260925/issues/03-receipt-ingest-result.md:8`、`official_context.py:537`、`treasury_context.py:413` |
| 同一 OMO 表格不匹配 | 非最后候选→`skipped`；最后候选→`rejected`，最终可 validation_failed | 有明确要求：跳过同日其他公告，不提示拒收。`.scratch/run-findings-20260926/issues/04-omo-sibling-notice-rejection.md:42`、同文件`:64` |
| EIA HTML 空交付／单项失败 | adapter 已写每指标 missing_values 或失败；Worker 可再把两指标写成功或统一失败 | 无依据要求丢失单项结果；访谈已将其列为后续修正。`worker.py:1621`、`worker.py:1634`、`.scratch/architecture-review-20260929/README.md:92` |
| 缺少标量 | reviewed/增量家族→`missing_values`；其他上下文家族→`validation_failed`；EIA API 空 data→validation_failed | reviewed delivery 有实施说明，增量有源码分支；**未见统一的空交付分类依据**。`.scratch/pring-data-acquisition-repair/implementation-25-worker-reviewed-delivery-20260918.md:9`、`worker.py:1943`、`eia_context.py:375` |
| 结构化 HTTP 失败作为返回值 | 搜索 provider 返回 `failed` 对象，回执仍 passed；官方 adapter 抛异常则回执 rejected | **未见依据**把这两个回执的 passed/rejected 解释成相同的“来源成功／失败”。`search_discovery.py:69`、`search_discovery.py:150` |
| 成功枚举不同 | 核心历史写 `verified`，其他指标多数写 `verified_candidate`；freshness 的集合没有 verified | **未见依据**说明为何同一指标尝试读取集合应排除核心成功值。`core_history.py:192`、`freshness.py:815` |
| “已收到答复但缺文件”与“未连上” | 郑商所两者都写 source_failed，但调度用原因字符串决定继续后续日期还是停止 | 有明确 ADR，说明相同 outcome 下仍有不可丢失的来源／调度事实。`docs/adr/0032-czce-warrants-from-exchange-daily.md:18`、`czce_warrants.py:386` |

7. **读取方翻译：它们既不共享同一输入，也不共享同一种失败语义。**

| 读取方 | 映射规则 | 是否读取 reason／condition／stage |
|---|---|---|
| freshness `_FETCH_FAILED` | `source_failed/adapter_failed/missing_credentials`→`fetch_failed` | 类别仅由 outcome 决定；说明优先取 `reason→condition→error_type→outcome`，不读 stage。`freshness.py:815`、`freshness.py:860` |
| freshness `_ACQUISITION_OUTCOMES` | 再纳入 validation_failed、verified_candidate、partial_validation、missing_fields、missing_values；后三种及成功不产出 acquisition failure | 非失败值仍参与“最后一条”选择，可清除此前失败；`verified/permission_denied/rate_limited/not_attempted` 不在集合。`freshness.py:816`、`freshness.py:853` |
| freshness `validation_failed` | 无论结构还是入库阶段，一律→`ingest_rejected` | 使用上述说明优先级，不检查回执 ingest_result，也不检查 stage。`freshness.py:863` |
| freshness 获取归并范围 | 受理时间到下一次受理时间、同目标日；按指标＋symbol 保留最后记录，之后压回每指标一条失败 | 没有按渠道、日期完整隔离，也没有按目录过滤；这是为何完整性不能只交给 outcome。`freshness.py:839`、`freshness.py:857`、`freshness.py:859` |
| `gap_list` 最终类别 | 先根据持有／时效得到 missing、freshness_gap、unconfigured；仅 missing 才被授权缺失或获取失败覆盖 | 候选未通过可改成 retrieval_failed；事件追溯 none_found 取消 missing，source_failed→retrieval_failed/backtrack_incomplete。`freshness.py:892`、`freshness.py:910`、`freshness.py:924` |
| `gap_list` 结构拒收补列 | 同批回执 `structure_check=rejected`，且指标未在其他缺口／候选中列出→`rejected` | 直接读取回执 rejection_reason，忽略 skipped；当前未检查是否被后续成功解决。`freshness.py:930`、`freshness.py:942` |
| P2 投影 | 最近尝试 outcome 原样成为 `acquisition_status`；无记录→`no_attempt_for_target` | 传出 condition、request_sent、rejected_fields、来源期次／发布时间等；**不传通用 reason、error_type、stage**。`context_projection.py:310`、`context_projection.py:317` |
| P2 最近记录筛选 | 目标日、目录版本、截止时刻匹配后取最近一条 | 不据 outcome 决定已有值能否采用；筛选还依赖 metadata 身份字段。`evidence.py:918`、`context_projection.py:338` |
| LPR 发布日历 | 当前期已持有→current；否则识别 source_failed、permission_denied、rate_limited；其余按窗口→awaiting_release/stale | 获取分类只读 outcome，不读 reason/condition/stage；PUBLIC 模式不读获取尝试。`release_calendar.py:96`、`release_calendar.py:202` |
| 检索账本 `trace_acquisition` | HTTPError→HTTP 分类；OSError→transient_transport_error；TypeError/ValueError→semantic_validation_failed；预算阻止→not_attempted | **不是读取指标 retrieval_attempt 再映射**，而是重新捕获 operation 异常；不解包指标 metadata。`retrieval_ledger.py:433` |
| `retrieval._adapter_attempts` | 字符串→verified；None→not_found；OSError→failed/transient；ValueError→failed/semantic | 这里没有单独捕获 HTTPError，也**没有捕获 TypeError**；transient 最多循环三次。`retrieval.py:210`、`retrieval.py:229` |
| 搜索候选原因翻译 | CandidateRejected 原样；OSError→fetch_failed；预算阻止→retrieval_blocked；其余可按错误字符串识别白名单、期次、发布日期，否则 parse_failed | 这是明确依赖 reason 字符串语义的读取／翻译层，属于候选验证。`search_evidence.py:502`、`CONTEXT.md:295` |

**检索 HTTP 分类与退避具体值**

| 最初事实 | 分类 | 退避规则／证据 |
|---|---|---|
| HTTP 200 | 无失败分类 | `retrieval_ledger.py:843` |
| HTTP 401 | `authentication_failed` | 次日上海时间 00:05；`retrieval_ledger.py:846`、`retrieval_ledger.py:813` |
| HTTP 403 | `forbidden_unknown` | 同上，不自动认定“无权限”；`retrieval_ledger.py:848` |
| HTTP 402/432/433 | `quota_exhausted` | Tavily 至下月 1 日 00:05，其他至次日；`retrieval_ledger.py:850`、`retrieval_ledger.py:808` |
| HTTP 429 | `rate_limited` | 优先 Retry-After 秒数或 HTTP 日期，否则 60 分钟；`retrieval_ledger.py:793` |
| HTTP ≥500，或一般 OSError | `transient_transport_error` | 15 分钟负缓存；`retrieval_ledger.py:817`、`retrieval_ledger.py:854` |
| 其他非 200；一般 TypeError/ValueError | `semantic_validation_failed` | P2 24 小时，其他 6 小时；`retrieval_ledger.py:819`、`retrieval_ledger.py:856` |
| `not_found` | 并非 HTTP 分类，但参与负缓存 | 同上述 24／6 小时；`retrieval_ledger.py:819` |

因此，TuShare 40203 目前可能在 Worker 是“来源失败／限频原因”，在补缺账本却采用“语义失败”的退避；账本没有利用来源适配器已经知道的限频事实。

8. **非失败或部分失败：谁判断、写不写、消费者怎么理解。**

| 情形 | 最初判断者／是否写指标 retrieval_attempt | 消费者是否当失败 |
|---|---|---|
| 调度判定尚未发布 | 发布状态解析／日历与 Worker；通常不写指标尝试，写的是 `run_retrieval_attempt: not_attempted＋awaiting_release` | cascade 可直接返回空 attempts；不进入 freshness 的获取失败集合。`worker.py:645`、`worker.py:659`、`full_retrieval.py:95`、`retrieval.py:97` |
| CFETS 文件显示尚未到 16:30 | 来源 adapter 根据文件时间和收盘字段返回空，并写指标 `missing_values` | freshness 不当获取失败；P2 展示 missing_values，不显示专门的尚未发布原因。`quote_sources.py:98`、`quote_sources.py:270` |
| 缺 token／API key | Worker 根据本地配置写 missing_credentials、condition、request_sent=false；没有该请求回执 | freshness 映射 fetch_failed；P2 原样展示并传 request_sent=false；EIA 后续成功可在当前归并中清掉该失败。`worker.py:1573`、`worker.py:1761`、`freshness.py:861` |
| adapter 未配置／目录不采用该家族 | cascade 可写运行级 not_configured；Worker 的部分家族直接 continue，不写指标尝试 | 与 missing_credentials 不同，不能从“无指标尝试”反推缺凭据。`retrieval.py:135`、`worker.py:1914` |
| 预算／负缓存未发请求 | ledger 决策；返回 not_attempted 与阻止分类，capture 回调路径还可能留下 failed 回执 | 是调度阻止，不是来源拒绝；候选层可另翻译 retrieval_blocked。`retrieval_ledger.py:440`、`search_evidence.py:508` |
| 增量没有待计算日 | breadth/basket 根据 held days/levels 判断，返回空，最终 Worker 写 missing_values | freshness 不当获取失败；但该 outcome 没有表达“已全部持有”。`breadth.py:313`、`basket.py:195`、`worker.py:1943` |
| 来源空交付，reviewed 家族 | adapter 只知道 scalars 为空；Worker 同样写 missing_values | 不能与上一行等同；本分支没有证明所有应有成员已经持有。`tushare_context.py:958`、`worker.py:1943` |
| 财政部／EIA HTML 窗口内没有数值 | 来源 adapter 区分“日期格存在但无数值”和“窗口内没有日期格”，写 missing_values＋condition | freshness 不当获取失败，但持有不足仍可构成普通 missing／时效缺口；P2 能传 condition。`treasury_context.py:447`、`eia_html.py:449` |
| ECB 腿值缺失／窗口无日期 | 来源 adapter 写 missing_values，condition 为 reference_legs_missing 或 source_dates_missing | 同上；单行原始腿值缺失原因保存在规范化 missing 记录。`ecb_reference.py:177`、`ecb_reference.py:625` |
| GDP 部分字段拒绝 | adapter 判断 YoY 统计期语义未核实，保留 level；Worker 写 partial_validation＋拒绝字段数量 | freshness 不当获取失败；P2 展示部分校验结果，但具体字段原因没有从该装饰路径传出。`tushare_context.py:1602`、`worker.py:1968`、`context_projection.py:328` |
| 家族只交付部分指标 | Worker 比较预期 metric_ids 与实际 result.metric_ids，未交付者写 missing_fields | freshness 不当获取失败，但实际缺值仍可列普通缺口；没有自动记录哪条原始响应导致缺字段。`worker.py:1972`、`freshness.py:816` |
| 个别日期／成员缺失但有部分交付 | Treasury/EIA HTML/ECB 只要该指标有交付即可写 verified_candidate，同时另带 missing count | 不是完整交付证明；“partial_validation”并未覆盖所有部分交付。`treasury_context.py:432`、`eia_html.py:461`、`ecb_reference.py:615` |
| OMO 主动跳过其他公告 | adapter 判断 CandidateSkipped；只写 failed/skipped 回执，继续候选 | 缺口不当拒收，账本将前一请求结成 candidate_source/intermediate_candidate_skipped。`official_context.py:823`、`retrieval_ledger.py:411` |
| 仓单差额核对不一致 | TuShare／郑商所来源处理记录 reconciliation 注记 | 不拒收，也不应因注记升级为失败；有明确 ADR。`czce_warrants.py:528`、`docs/adr/0029-p2-quote-sources-and-warrant-members.md:12` |

9. **我的归属判断：保留分层方向，但不要把“阶段”设计成由读取模块推断出来的单一失败枚举。**

| 责任 | 应归谁 | 基于本次事实的理由 |
|---|---|---|
| 请求是否实际发出、是否收到响应、是否本地导入 | 执行请求的获取设施／适配器；未请求的调度决定归 Worker 或账本 | capture 在 fetch 前已建回执，本地导入也经历 received；仅凭回执存在或 state 无法准确推断网络动作。`acquisition.py:179`、`acquisition.py:204`、`official_context.py:502` |
| 来源业务拒绝及外部原因解释 | 来源适配器/helper | 只有这里同时持有 TuShare code/msg、CFETS 时点、郑商所缺文件、ECB 响应完整性等信息。`tushare_context.py:893`、`quote_sources.py:98`、`czce_warrants.py:386`、`ecb_reference.py:355` |
| HTTP／网络原始事实 | 传输边界记录，适配器保留，不依赖后续异常链恢复 | 现有包装已经使 ledger 丢失 HTTPError 身份、HTTP 数字或 Retry-After；读取端不该重读错误正文补猜。`quote_sources.py:161`、`treasury_context.py:300`、`retrieval_ledger.py:444` |
| 结构解析／来源语义校验结果 | 执行解析和校验的 adapter | 表头、统计期、字段语义、空单元格都来自来源契约；Worker 无法从 TypeError/ValueError 还原是哪条规则。`tushare_context.py:2147`、`official_context.py:1236`、`eia_html.py:244` |
| 入库拒收结果和原因 | 注册契约／evidence 校验者提供原因，包围实际入库调用的边界记录阶段 | 正确做法已有 TuShare、报价、郑商所先例；`stage=ingest` 应来自确实调用入库后被拒，而不是 outcome 名称。`tushare_context.py:335`、`quote_sources.py:254`、`evidence.py:1499` |
| 本地程序／存储／时间异常 | 出错的执行边界记录为本地处理失败，Worker 只作兜底 | 本地时钟回跳也抛 ValueError，文件写入也可能抛 OSError；不能据此分别断言“坏响应”或“来源失败”。`acquisition.py:417`、`evidence.py:574`、`acquisition.py:262` |
| 原始原因码 | 最初判定者拥有；公共结果记录保留其命名空间与原始值 | HTTP 数字、TuShare 业务码、解析器原因码、配置条件是不同种类，不能都压成 Python 类名。`tushare_context.py:897`、`worker.py:1578`、`official_context.py:875` |
| 异常→规范获取结果 | 在异常发生的明确步骤边界翻译；公共模块可以提供统一类型和存储协议 | 可统一表达方式，不能把所有来源异常交给一个全局 `isinstance` 表；目前 TushareSourceError 继承 ValueError 已证明全局类型分类会误判。`tushare_context.py:146`、`retrieval_ledger.py:452` |
| 跨尝试的“本批取得了什么／什么尚未解决” | 获取结果模块 | 需要结合批次、指标、品种、日期、交付范围及后续尝试，正是现有 freshness 归并所承担但尚不完整的职责。`freshness.py:853`、`CONTEXT.md:181` |
| 缺口类别、P2 展示、LPR 状态、重试与退避 | 各消费者 | 同一来源拒绝可以同时是账本的限频、缺口的获取失败、P2 的最近获取状态，而不改变已经持有值的时效。`retrieval_ledger.py:782`、`freshness.py:861`、`context_projection.py:341`、`CONTEXT.md:193` |

**三层方案需要的具体修正：**

| 原设想 | 我的修正 | 事实依据 |
|---|---|---|
| 一个“阶段”值：未发请求／源失败／结构拒收／入库拒收 | 拆成执行进度与各步骤结果；“源失败”本身是结果，不是单纯的时间阶段 | HTTP 已收到但业务拒绝、结构通过但入库拒绝、主动 skipped 却 state failed，均无法用一个顺序终态准确表达。`acquisition.py:212`、`acquisition.py:302`、`acquisition.py:292` |
| 一个“原始原因”字符串 | 保留外部状态／业务码、本地规则原因、异常类三个不同事实；文本消息只能作为补充 | 40203 的业务含义、TypeError 的诊断信息、registered_* 的契约拒绝不是同一种原因码。`tushare_context.py:897`、`worker.py:1959`、`source_contract_review.py:316` |
| 消费者类别从 outcome 直接映射 | 消费者依据规范结果及自身语义映射，旧 outcome 只作为兼容输入 | freshness 当前不读 stage，LPR 不读 reason，账本不读指标尝试；不能指望换一个统一 outcome 自动修复三者。`freshness.py:860`、`release_calendar.py:102`、`retrieval_ledger.py:433` |
| 部分成功归入某种失败 | 单独表达交付完整性、缺失成员与“无需新增” | verified_candidate 可伴随缺格；missing_values 可表示无需计算，也可表示真实空交付。`treasury_context.py:438`、`basket.py:195`、`worker.py:1943` |
| Worker 对整家族再写总结果 | Worker 记录自己的调度／配置决定，获取细节由实际执行者提供；家族汇总由获取结果模块读取生成 | EIA 的二次记录会覆盖逐指标事实；TuShare 的底层成功与 Worker 包装记录携带的成员信息也不一致。`worker.py:1634`、`tushare_context.py:1155`、`worker.py:1924` |

这与现有访谈的“先纯重构、后修写入契约”可以分步兼容，但两步必须明确区分：只改读取时应如实保留旧分类及不确定性，不能把推断出的阶段当成已记录事实；生产者契约修订后，才有条件让获取结果模块可靠解释尚未解决的成员结果。依据：`.scratch/architecture-review-20260929/README.md:86`、同文件`:90`、`CONTEXT.md:182`。
