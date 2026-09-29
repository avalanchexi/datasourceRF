# 候选 4 勘察：加工批次中的获取尝试结果

来源：Codex 只读勘察（2026-09-29，`gpt-6-astra`／high，约 25 万 tokens），原样收录其结论。已抽查属实：第 11 条（`_acquisition_failures` 按受理时间到下一次受理时间取尝试，`freshness.py:839`）、第 15 条（归并键只有指标＋品种、无日期，`freshness.py:857`）、第 16 条（`tushare_context.py:1155` 成功记录不带 `symbol`，Worker 包装记录带，`worker.py:1924`）、第 6 条（`record_retrieval_attempt` 仅在给出回执时补入运行归属，`evidence.py:1310`）。访谈结论见 [README](README.md)。

1. **结论：值得做，但应收成“获取结果的归属、分类与多种读取视图”，不能收成万能回执仓库，也不能统一为最后一条决定一切。** 实际问题包括尝试缺少可靠批次归属、不同写入路径丢失成员信息、异常分类重复，以及读取方各自解包 metadata；单纯移动 SQL 不解决这些问题。依据：`src/pring_cycle/freshness.py:825`、`src/pring_cycle/worker.py:1660`、`src/pring_cycle/context_projection.py:310`。

2. **原候选的“五处各自重建同一问题”不完全成立。** Worker 主要是结果生产者；真正的时效计算读取已持有声明，不读取获取尝试；P2 投影的获取状态、声明可采用性、结构拒收历史也是不同问题。依据：`src/pring_cycle/worker.py:1932`、`src/pring_cycle/freshness.py:575`、`src/pring_cycle/context_projection.py:307`、`CONTEXT.md:189`、`CONTEXT.md:267`。

3. **勘察范围与证据约定。** 本报告仅依据代码、文档和测试源码，未修改文件、运行测试、读取运行数据库或调用外部接口；下文裸文件名均指 `src/pring_cycle/` 下文件，`test_*.py` 除明确注明外均指 `tests/integration/` 下文件。所有“可能遗漏”都是静态判断，不是已实测缺陷。

4. **数据模型：至少有两种“获取尝试”，不能混为一张表。**

| 对象 | 存储与主要字段 | 关联方式、实际粒度 | 证据 |
|---|---|---|---|
| 指标获取尝试 | `retrieval_attempt`：`retrieval_attempt_id, metric_id, channel, outcome, fetched_at, safe_metadata_json` | 没有独立 `run_id/batch_id`、统计期、成员或原因列；相关信息可选地放进 metadata | `evidence.py:1787` |
| 运行检索尝试 | `run_retrieval_attempt`：`run_id, release_event_id, sequence, channel, outcome, classification, occurred_at, physical_request_id`，以及预算、缓存、耗时字段 | 明确按运行归属；指标和期次来自 `run_retrieval_scope`，完整运行则来自初始计划中的 scope | `runs.py:707`、`runs.py:1213` |
| 获取回执 | `acquisition_request`：接口、提供方、参数 JSON、字段、解析器版本、开始/收到/验证时间、状态、原件/规范化哈希、异常类型 | 表中没有指标、成员、运行 id；参数可包含请求区间、品种等 | `acquisition.py:458` |
| 回执校验与入库结果 | 同表追加 `row_count, structure_check, rejection_reason, ingest_result, ingest_rejection_reason` | 结构通过与入库通过是两件事；`validated` 回执仍可能 `ingest_result='rejected'` | `batches.py:29`、`acquisition.py:302`、`acquisition.py:524` |
| 加工批次 | **没有独立批次表**；使用 `parent_run` | `run_id` 即批次 id，记录目标日、模型、截止时间、运行状态、受理时间与代码版本 | `batches.py:1`、`runs.py:1143` |
| 回执归属 | `full_run_acquisition`：`run_id, acquisition_id, phase, metric_ids_json, period` | 一张回执可声明服务多个指标；`period` 可空，表示获取目的，不证明这些指标均已入库 | `full_retrieval.py:859`、`full_retrieval.py:625` |
| 明细血缘 | `source_claim_acquisition(claim_id, acquisition_id)` | 来源声明到回执为多对多，再经回执追溯运行；不是每条明细都直接存 `batch_id` | `acquisition.py:474`、`evidence.py:605` |
| 汇总与时效 | 汇总表的 `batch_id`；`batch_freshness(batch_id, metric_id, …)` | 汇总批次列是普通文本，不是外键；时效按批次和指标记录 | `batches.py:20`、`freshness.py:444` |

5. **metadata 目前不是统一契约，尤其 `period` 不能直接当作统计期。** Worker 写的是目标交易日，官方宏观写统计月/季度，国债 CSV 写请求结束日，TuShare 入库另写 `period_end`，郑商所写 `business_date＋period＋symbol`；其他字段包括目录版本、接口家族、原因、异常类型、是否发请求、条数、缺字段、HTTP 信息、发布日期和仓库差额注记。依据：`worker.py:1668`、`official_context.py:671`、`treasury_context.py:333`、`tushare_context.py:1165`、`czce_warrants.py:439`、`czce_warrants.py:517`。

6. **指标尝试的批次关联是有条件补入的，不能假定每条都有。** `record_retrieval_attempt` 只有收到 `acquisition_ids`，且所有回执都能关联到同一个运行时，才补入 `run_id/target_business_date`；无回执的缺凭据记录、Worker 汇总记录、核心历史记录和部分 LPR 失败记录没有这条可靠关联。依据：`evidence.py:1308`、`acquisition.py:111`、`worker.py:1663`、`core_history.py:189`、`official_lpr.py:431`。

7. **写入点如下；同一次获取可能产生底层记录和 Worker 汇总记录两层结果。**

| 写入对象 | 写入者与内容 | 写入点 |
|---|---|---|
| 批次 | `RunRepository.submit` 创建运行；Worker 登记代码版本、开启汇总批次作用域 | `runs.py:269`、`runs.py:562`、`worker.py:217` |
| 回执及运行归属 | `AcquisitionRepository.capture` 创建请求并记录 owner；随后记录收到、验证、失败、入库结果 | `acquisition.py:179`、`acquisition.py:195`、`acquisition.py:273`、`acquisition.py:295`、`acquisition.py:310` |
| 指标尝试通用落库 | `EvidenceRepository.record_retrieval_attempt`，稳定哈希去重、追加写入 | `evidence.py:1296` |
| Worker 汇总尝试 | EIA 缺凭据/异常/回退；ECB 异常补记；TuShare 家族成功、缺字段、失败 | `worker.py:1573`、`worker.py:1663`、`worker.py:1711`、`worker.py:1932` |
| 核心、TuShare、EIA API | 核心历史成功、上下文标量成功、EIA 标量成功 | `core_history.py:189`、`tushare_context.py:1155`、`eia_context.py:327` |
| 官方宏观、LPR | 官方宏观成功与失败；LPR 直接刷新失败 | `official_context.py:665`、`official_context.py:864`、`official_lpr.py:431` |
| 独立官方来源 | 国债、EIA HTML、ECB、行情文件、郑商所的成功/空值/失败记录 | `treasury_context.py:429`、`:468`；`eia_html.py:458`、`:486`；`ecb_reference.py:505`、`:612`；`quote_sources.py:206`、`:257`、`:267`；`czce_warrants.py:460`、`:499`、`:511` |
| 运行检索尝试 | 发布闸门和级联结果，经 `RunRepository.record_retrieval_attempt` 写入 | `worker.py:659`、`:709`；`full_retrieval.py:98`、`:154`；`runs.py:753` |
| 候选验证与物理请求 | 搜索候选记录网址、原因、缺失成员、声明、原件；物理请求另存分类与回执关联 | `search_evidence.py:944`、`:1095`；`ai_websearch.py:556`；`retrieval_ledger.py:753` |

8. **直接解释获取结果的读取方如下；“最新”规则并不相同。**

| 编号 | 读取方 | 查询范围 | 多条记录的处理 | 成员粒度、输出用途 |
|---|---|---|---|---|
| R1 | `EvidenceRepository.latest_retrieval_attempt` | 指标、`fetched_at≤as_of`；可选 metadata 中的期次、目标日、目录版本；**不按运行 id** | 按精确时间、尝试哈希 id 倒序，第一条符合条件者；不区分成功失败优先 | 指标级，无成员参数；供 R2–R4。`evidence.py:884` |
| R2 | P2 获取状态装饰 | 截止时间＋目标日＋目录版本，`period=None` | R1 的最新记录；同一结果复制到该指标所有投影行 | 指标级；输出 `acquisition_status/latest_acquisition`，美债利差附父指标结果。`context_projection.py:304`、`:407` |
| R3 | LPR 发布日历 | 指标＋统计月＋截止时间；仅 SYSTEM 模式读尝试；未给尝试查询传目录版本 | 有本期观测首先判 `current`；否则只认三种获取失败，再判断发布窗口 | LPR 两期限共用发布事件状态；供发布日历及 LPR 投影。`release_calendar.py:198`、`:202`、`:96`；`context_projection.py:1785` |
| R4 | Worker 的 ECB 失败补记 | 指标＋目录版本＋当前失败时间；不按目标日或运行过滤 | 最新结果已是失败且回执 id 完全匹配时，不重复写；否则补一条 | ECB 指标级；防旧成功隐藏本次异常。`worker.py:1698` |
| R5 | `_acquisition_failures` | 本次 `accepted_at` 到下一次任意运行 `accepted_at`；再检查目标日，缺目标日则默认属于本次 | 只看白名单 outcome，按时间文本、rowid 升序覆盖；最后一次可清除旧失败，也可覆盖旧成功 | 按指标＋`symbol`归并，最终又压成每指标一个失败原因。`freshness.py:825` |
| R6 | `gap_list` 的结构拒收分支 | `full_run_acquisition.run_id` 精确关联，取 `structure_check='rejected'` | 不检查后续成功；已有缺口或候选的指标跳过；多张拒收取首次遍历到的一张，SQL 无排序 | 丢弃期次、品种、仓库；输出指标级 `rejected`。`freshness.py:930` |
| R7 | `_failed_candidates` | 本运行所有 `not_model_usable` 候选，排除重复候选 | 同 URL 后一条失败原因覆盖前一条；最多三个不同 URL；不以之后成功清除历史失败记录 | 原缺口有指标/期次身份，输出降为指标级候选列表。`freshness.py:755` |
| R8 | `_backtracked` | 本运行 `event_backtrack` 计划文档 | 读取已归并的 `found/none_found/source_failed`；不是选最新尝试 | 事件指标级；`none_found` 消除缺失，失败转检索未通过。`freshness.py:784`、`:894` |
| R9 | `read_full_retrieval_plan`、`FullRunRetrieval.evaluate` | 按运行 id 读全部回执及初始/最终计划 | 按 owner.rowid 保留全部；按声明的获取目的关联需求，不用最后一次判定是否补齐 | 回执→指标集合/期次；补齐情况另由 selector 判断。`full_retrieval.py:782`、`:594`、`:625` |
| R10 | `RunRepository._retrieval_attempts` | 精确运行 id | 全部按 sequence 输出，不覆盖失败 | 发布事件/渠道流水；供运行读模型和任务页面。`runs.py:994`、`dashboard.py:1246` |
| R11 | `RetrievalLedger.for_run` | 本运行及本运行复用的旧请求 | 保留全部物理请求、查询和候选；另区分原件保留/过期/不可用 | 缺口、请求、渠道；供运行详情、检索评估和搜索处理。`retrieval_ledger.py:641`、`search_evidence.py:916` |
| R12 | 搜索候选落账 | 本次候选验证的最后一张下载回执＋重新选值结果 | 是否 `model_usable` 取决于取得声明且模型输入完整，不取决于 HTTP 或回执成功 | 缺口成员级，记录缺失成员及原件信息。`search_evidence.py:1076` |

9. **全仓还存在下列回执读取，但它们不应全部改走候选 4。**

| 读取方 | 范围与优先规则 | 用途及所属边界 |
|---|---|---|
| 真正的批次时效 | 按目录版本和截止时间读声明；取最新持有期，仓单要求规定品种齐备；不读尝试 | `current/awaiting_release/stale/missing`，保留在时效模块。`freshness.py:592`、`:603` |
| 三处交易日历读取 | 启动日历取最新合适回执；完整窗口有截止时间；郑商所窗口合并覆盖区间 | 已归票 02。`freshness.py:628`、`full_run_requirements.py:50`、`czce_warrants.py:259` |
| 声明原件复核 | 按明确 claim id 取全部关联回执；要求 validated、哈希一致，任一关联原件不合格可使该声明不可复核 | 可采用声明边界。`evidence.py:366`、`official_context.py:345`、`official_lpr.py:204`、`interbank_evidence.py:146`、`treasury_context.py:206`、`tushare_context.py:1646` |
| 核心、仓单、降准复核 | 核心按明确声明核原件；仓单按期＋品种选择最新可见交付并检查成员；降准按整份公告 | 已归票 05；不是最新失败记录否定旧值。`source_adapters.py:98`、`warrant_inputs.py:95`、`published_events.py:17` |
| 证据追溯 API | 指定观测、查询模式和截止时间，返回可见声明关联的全部回执 | `linked/partially_linked/untraced/not_visible` 描述血缘完整度，不是获取成功率。`evidence.py:1159`、`web.py:128` |
| 回执详情与历史 | 按 acquisition id 或全部 rowid 顺序返回，不归并 | 基础仓储/诊断接口；`AcquisitionReceipt` 本身甚至不带追加的结构与入库字段。`acquisition.py:76`、`:319`、`:356`、`:367`；`web.py:146` |
| TuShare 资讯窗口 | 历次 completed 完整运行中，所有资讯页均 validated 才承认已完整拉取；当前运行读取全部 validated 页并去重 | 获取续接与正文输入；不能只取最后一页。`tushare_news.py:69`、`:181` |
| 检索预算、恢复与去重 | 按渠道、请求、运行尝试次数、缓存期限和候选 URL 分别判断；历史未知完成不能被简单覆盖 | 保留检索账本状态机。`retrieval_ledger.py:243`、`:378`、`:470`、`:484`、`:867`；`search_evidence.py:937` |
| 公告/派生输入读取 | 按明确声明或提供方＋成员＋期次读取交付 | 值与原件一致性、派生血缘；保留证据仓库及相应计算模块。`evidence.py:329`、`:422`；`context_projection.py:2470` |
| 入库契约、留存清理 | 入库按回执身份核对；清理按时间和引用关系处理 | 写入门槛和资源生命周期，不是获取结果归并。`source_contract_review.py:553`、`evidence.py:590`、`retention.py:167`、`:189` |

10. **口径差异一：`source_failed` 与 `current` 同时出现，通常不是矛盾。** 最新获取失败可以与已持有当前期并存，原件后来不可复核也可以与“曾取到当前期”的时效记录并存；CONTEXT 明确把时效与获取分开，票 09 又明确不把时效改成只认可采用声明。依据：`CONTEXT.md:189`、`freshness.py:592`、`context_projection.py:1632`、`.scratch/architecture-review-20260929/issues/09-gap-list-keeps-conflict-with-source-failed.md:14`。

11. **口径差异二：运行时间区间不等于批次归属，尤其不能从单 Worker 推出两者相等。** R5 使用受理时间边界，R6/R9 使用运行 id，R2 使用目标日＋截止时间；不同目标的运行可先排队，恢复旧运行也不改变原 `parent_run.accepted_at`，因此 R5 有漏归属或串归属的静态风险。时间法有旧票实施记录，但未见要求保持这种错配的依据；ADR-0031 明确保留恢复，依据为 `freshness.py:839`、`runs.py:227`、`runs.py:525`、`.scratch/gap-sources-20260925/issues/04-gap-categories-by-cause.md:16`、`docs/adr/0031-keep-run-resume.md:9`。

12. **口径差异三：批次结果与截止时点结果不能合并。** R5/R6 没有冻结截止时间过滤，而 R2/R3 有；显式历史截止点后的获取可能属于本批次，却不能成为该截止点的投影获取记录，同目标日另一批次的旧尝试则仍可能被 R2 取到。截止可见性有测试依据，但“同目标日旧尝试是否代表本次运行”未见明确要求，必须保留视图区别后另行决定：`freshness.py:845`、`freshness.py:935`、`evidence.py:898`、`test_full_run_retrieval.py:234`。

13. **口径差异四：最新排序和目录隔离也不同。** R1 使用精确 datetime＋哈希 id，R5 使用时间字符串＋rowid；同时间记录、不同 UTC 偏移字符串可能得到不同次序，且 R5 不过滤目录版本，LPR 尝试查询也没传目录版本。微秒截止已有测试，但未见这些排序和目录差异的领域依据，属于可能遗漏：`evidence.py:904`、`freshness.py:847`、`release_calendar.py:202`、`test_full_run_retrieval.py:112`。

14. **口径差异五：“成功覆盖失败”仅在同一归并键内成立，而且并非只允许成功覆盖失败。** R5 对同指标＋品种保留最后一个允许的 outcome，后续失败同样覆盖成功；跨品种不覆盖有明确票据依据，跨渠道回退清除早期失败也有明确依据，但最终压成每指标一个原因会丢掉多个失败品种及各自原因。依据：`freshness.py:850`、`.scratch/run-findings-20260926/issues/01-warrant-family-isolation.md:58`；压缩为单原因的优先顺序未见额外依据。

15. **口径差异六：仓单写入已经按“品种＋日期”，获取失败归并却只有“品种”。** 郑商所某日失败后另一日成功，会在 R5 中清除同品种早一天的失败，而按期次检查的模型输入仍可缺那一天；这不等于缺口一定从最终页面消失，但会失去准确的失败范围解释。ADR-0032 明确要求只缺该品种该日，未见跨日覆盖的依据：`czce_warrants.py:439`、`freshness.py:857`、`full_retrieval.py:594`、`docs/adr/0032-czce-warrants-from-exchange-daily.md:12`。

16. **口径差异七：TuShare 单日补缺成功不一定能清掉直接刷新留下的品种失败。** 直接刷新包装记录带 `symbol`，底层 `ingest_context_scalars` 成功记录不带 `symbol`，而单日补缺走后者；因此旧 `(指标,CU)` 失败与新 `(指标,None)` 成功可能并存，若指标因其他品种仍缺数，旧原因可能继续被选中。未见要求这种差异的依据，属于可能遗漏：`worker.py:1924`、`tushare_context.py:1155`、`targeted_context.py:159`、`freshness.py:857`。

17. **口径差异八：结构拒收与当前获取失败不是同一种“最后结果”。** R5 后续成功可清除失败，R6 却仍能显示本批次曾经发生的结构拒收，R7 也保留候选失败历史；已有票据明确规定候选失败只在指标仍缺失/落后时展示、并避免重复拒收，但未见明确规定“已经修复的结构拒收是否仍应作为缺口”。依据：`freshness.py:924`、`freshness.py:930`、`.scratch/pring-fast-refactor-20260923/issues/19-retrieval-strict-path-and-failed-verification.md:22`；新模块应分别输出历史事件和尚未解决的结果。

18. **口径差异九：LPR 的单一 `status` 仍混合发布时效和获取失败。** 持有本期时失败尝试不影响 `current`，未持有本期时 `source_failed/permission_denied/rate_limited` 会覆盖等待发布或过期判断，而 `validation_failed` 不会；这与统一时效表及 P2 独立获取字段的设计不同。旧测试明确锁定了这种行为，但未见新 ADR 要求保留此例外，应作为待确认差异而非静默统一：`release_calendar.py:96`、`tests/catalog/test_release_calendar.py:42`、`test_context_projection.py:935`、`CONTEXT.md:189`。

19. **口径差异十：某些结果差异来自生产者的二次概括，而非读取 SQL。** EIA HTML 底层按指标记录 `verified_candidate/missing_values`，Worker 却在两项均未抛异常后给两项再写 `verified_candidate`，某一项抛错又给两项统一写失败，可能覆盖另一项的具体结果及发布信息；未见这种信息损失的要求。依据：`eia_html.py:458`、`worker.py:1609`、`worker.py:1621`、`worker.py:1634`。

20. **口径差异十一：metadata 字段缺失不能一律解释为“没有尝试”。** 郑商所尝试没有目录版本，但当前仓单属于 P1，不能据此宣称它已被 P2 查询漏掉；实际意义是新模块若统一要求目录版本，必须解决这类旧记录的归属，而不能照搬 P2 过滤条件。依据：`czce_warrants.py:439`、`catalog.py:51`、`catalog.py:75`、`context_projection.py:307`。

21. **失败分类没有统一状态枚举，现状如下。**

| 分类层 | 定义/翻译位置 | 当前语义及差异 |
|---|---|---|
| 回执状态 | `acquisition.py:469` | SQL CHECK 限定 `started/received/validated/failed`；只描述请求处理阶段 |
| 结构、入库结果 | `acquisition.py:292`、`:310` | `passed/rejected/skipped` 与 `accepted/rejected` 分开；收到 HTTP 错误正文后抛错，也可能留下结构 `rejected` |
| 尚未发布 | `worker.py:659`、`full_retrieval.py:98`、`retrieval.py:97` | 通常是 `not_attempted＋awaiting_release`，甚至没有尝试行；不是统一的 `not_published` 枚举 |
| 无权限、限频、源失败 | `tushare_context.py:146`、`:895`；`worker.py:1932` | TuShare 非零业务码抛 `TushareSourceError`，40203 原因是 `tushare_rate_limited`，Worker outcome 仍统一为 `source_failed`；并未完整统一成 `permission_denied/rate_limited` |
| 缺凭据 | `worker.py:1573`、`:1761` | `missing_credentials`＋配置条件＋`request_sent=false`；TuShare 无 token 时只给 GDP、2Y、10Y 写该记录，并非所有指标 |
| 校验、适配器失败 | `worker.py:1591`、`:1942` | `TypeError→adapter_failed`，多数其他结构异常→`validation_failed`；缺口层又把 `adapter_failed` 归为 `fetch_failed` |
| 官方来源异常 | `official_context.py:861`、`treasury_context.py:466`、`ecb_reference.py:504` | 多处重复 `OSError→source_failed，TypeError/ValueError→validation_failed`，与 Worker 对 TypeError 的解释不同 |
| VIX/报价文件异常 | `quote_sources.py:205` | 解析 ValueError 也归 `source_failed`；**有票据明确依据**，不能直接当遗漏：`.scratch/gap-sources-20260925/issues/06-vix-cboe-official.md:8` |
| 部分/空交付 | `worker.py:1943`、`:1964`；`treasury_context.py:426` | `missing_values/missing_fields/partial_validation/verified_candidate` 并存；增量无新值也可能是 `missing_values`，不等于全部数据缺失 |
| 检索传输分类 | `retrieval_ledger.py:444`、`:843`；`retrieval.py:229` | HTTP 401/403/429 等分别归认证、禁止、限频；一般 TypeError/ValueError 归语义失败，因而 TuShare 同一业务错误在直接刷新与补缺账本中解释不同 |
| 搜索候选原因 | `search_evidence.py:474`、`:502` | 白名单、解析、期次、发布日期、截止时间、数值不符、输入不完整、预算阻止等常量；这是候选验证层，不应全部映射成源失败 |
| 用户缺口类别 | `freshness.py:801`、`:815`、`:897` | 获取失败、入库拒收、检索未通过、授权缺失、时效缺口等；原因优先取 `reason→condition→error_type` |

22. **分类集中应保留“阶段＋原始原因＋面向消费者的分类”，不能只剩一个失败枚举。** `retrieval_attempt.outcome/classification` 多数只是任意字符串，P2 投影又只转发 condition 等少数字段、没有传出通用 `reason/stage/error_type`；读取侧确有信息解释缺口，但解析器的具体原因码、候选验证规则和检索退避策略不宜全部搬入新模块。依据：`evidence.py:1787`、`runs.py:1221`、`context_projection.py:317`、`search_evidence.py:502`、`retrieval_ledger.py:782`。

23. **与已定候选的边界如下；这些是已定计划，不应当作已经实施完成。**

| 已定范围 | 已划走或将划走的逻辑 | 候选 4 应避开 |
|---|---|---|
| 票 01 | 预算测试走现有检索入口；720 条夹具改批量写入 | 不把这些提速重复计入候选 4。`.scratch/architecture-review-20260929/issues/01-test-speed-existing-seams.md:13` |
| 候选 1，票 02–04 | 日历回执读取、口径、覆盖、目标日与窗口；外盘日历另做 | 不解释 `trade_cal` 原件，不计算应有期或交易日。票 02:13、`:20`，README:29 |
| 候选 2，票 05 | 已选声明的原件/原话/契约复核，成员完整性，核心及派生输入家族分派 | 不以尝试成功代替可采用；不再建第二张家族复核表。票 05:21、`:24` |
| 票 06–08 | 投影补齐家族复核、仓单逐品种完整性、目标日选值排序 | 不顺手修改这些行为；获取品种结果与“已选声明缺成员”是相邻但不同的规则。README:47 |
| 票 09 | 同一成员同时冲突和原件复核失败时，保留两种信息；查看冲突期时效 | 不把这里的 `source_failed` 误认为一次网络获取失败，也不另做冲突清单合并。票 09:3、`:13` |
| 候选 3，票 10 | 核心就绪→上下文→发布；运行材料由 Worker 组装 | 新模块供给获取结果材料，不接管发布、阶段、报告、检查点或运行终态。票 10:20、`:30` |
| 票 11–14 | 按日窗口缺口、补算快照、当前指针、阶段史 | 不用本批次获取状态污染补算日的历史值与缺口判断。README:71 |
| 票 15 | `_retrieval_release_status` 的序列重复读取优化 | “已公布没有”仍属发布/时效判断，不是获取结果模块。票 15:3 |

表中“票 NN”均位于 `.scratch/architecture-review-20260929/issues/`；完整票据索引见 `.scratch/architecture-review-20260929/README.md:83`。

24. **自然输入应是两个明确入口，而不是让 `batch_id` 与截止时间互相替代。** 批次入口接受 `run_id＋cutoff＋目录版本`，目标日从运行记录取得；目标日历史入口接受 `target_business_date＋as_of＋目录版本`，允许读取此前批次的可见尝试。前者回答本批做了什么，后者维持 P2/LPR 现有可见性需求；依据为 R1、R2、R5、R6 的实际查询差异。

25. **自然输出应保留明确身份及多轴结果，而不是原封不动返回 metadata。**

| 输出部分 | 建议内容 |
|---|---|
| 归属 | 批次、目标日、目录版本、归属依据；旧记录可标为“无明确归属”，不要猜成确定事实 |
| 结果身份 | 指标、请求统计期或区间、已知维度/品种；请求范围与实际取得范围分开 |
| 请求结果 | 未发请求/获取失败/收到响应/部分交付/已入库等，保留渠道与记录时间 |
| 校验结果 | 结构结果、入库结果、失败阶段、规范化分类、原始原因码、是否主动跳过 |
| 取得内容 | 可证明的声明 id、实际期次/成员、交付计数；不得把请求目的当作已取得内容 |
| 多次尝试关系 | 渠道历史、当前相关结果、已被后续交付解决的失败、尚未解决的成员失败 |
| 追溯 | 尝试 id、回执 id、候选 URL；批次信息仅供内部追溯，不进入页面/报告 |

这些轴分别已有数据基础：`acquisition.py:302`、`evidence.py:1296`、`full_retrieval.py:625`、`CONTEXT.md:333`；新模块无需重算声明可采用性。

26. **优先改走模块的调用点应限定为 R2、R4、R5、R6，并让 R1 成为兼容委托。** 即替换 `context_projection.py:310` 的查询与 metadata 装饰、`worker.py:1702` 的 ECB 同次失败识别、`freshness.py:825` 的归并和 `freshness.py:930` 的拒收读取；LPR 可共用尝试读取接口，但其发布状态机保留，候选列表与追溯发现可通过明确适配接入。完整检索计划的获取目的关联、预算账本、原件复核和日历读取不必改走它。

27. **只改读取端不够，最小生产者契约也应纳入范围。** 至少让新写尝试明确记录批次、目录、请求范围、品种和关联回执，缺凭据时允许“有批次、无回执”，避免 Worker 再追加会覆盖细节的家族成功记录；旧记录不能靠时间区间自动升级为可靠归属。依据：`worker.py:1660`、`tushare_context.py:1155`、`acquisition.py:133`、`czce_warrants.py:439`。

28. **必须保留不同视图，不能合成一个统一终态。** 当前已持有/可采用视图不应被后续失败抹掉，目标日最近获取视图允许失败覆盖成功，批次拒收历史保留已发生事件，未解决成员视图只允许相同相关范围的成功解决失败，预算恢复视图还须保留未知完成与缓存记录。依据：`test_gdp_semantics.py:201`、`release_calendar.py:96`、`freshness.py:930`、`retrieval_ledger.py:249`；核心待处理和缺口说明继续由各自领域决定，不能由获取失败直接推出（`CONTEXT.md:105`、`:113`）。

29. **现有测试覆盖及可迁移部分如下。**

| 测试与位置 | 夹具、执行范围 | 候选 4 可直接测什么；必须保留什么 |
|---|---|---|
| `test_full_run_retrieval.py:42`，参数化在 `:38` | `prepare＋seed_core_history＋runtime_clock`；假 EIA opener、离线 HTML 回退；经过完整 Worker | 可迁移渠道结果归并及投影字段装饰；缺 key 不发请求、API 失败后走 HTML 必须继续经获取接口测试 |
| `test_full_run_retrieval.py:134`，断言在 `:217` | 三分支：GDP 无 level、国债结构错、缺 2Y；核心/上下文假 HTTP；完整 Worker | 可迁移按指标部分成功及父输入获取信息；P2 不否决核心归候选 3/少量完整运行 |
| `test_full_run_retrieval.py:112` | 初始化运行库、写一条尝试；不跑 Worker | 微秒截止过滤直接迁；这是已有窄测试，不会产生整轮提速 |
| `test_gdp_semantics.py:92`、`:201` | 本地官方 GDP 原件、明确 owner、HTTP/解析失败替身；直接获取＋投影 | 后失败成为最新尝试、旧值仍保留、回执/目标日/批次关联；保留原件解析覆盖 |
| `test_worker_ecb_refresh.py:90`、`:137` | ZIP/网络失败替身、注册目录、`own_acquisitions`；直接刷新，不跑完整 Worker | 失败补记去重、明确批次关联；保留异常后其他来源继续执行 |
| `test_worker_eia_html_fallback.py:49`、`:96`、`:130` | 本地历史 HTML；前两例直接刷新，后一例完整运行 | 前两例已可测缺 key/坏 key 回退，适合承接从慢例拆出的获取断言 |
| `test_treasury_csv_acquisition.py:183`、`:350`、`:443` | 本地 CSV 及 N/A/HTTP 变体；直接获取 | 2Y/10Y 独立结果、后失败不删旧值、后缺格不删旧值；解析正确性留在来源测试 |
| `test_warrant_symbol_isolation.py:146`、`:176`、`:217` | 多品种假 TuShare；直接刷新；补缺用直通账本替身；无完整 Worker | CU 失败不被其他品种成功清掉，可缩到结果接口；品种分别提交和请求隔离仍保留 |
| `test_czce_warrant_refresh.py:117`、`:149`、`:163` | 本地日报/缺文件/网络失败；直接刷新 | 品种日结果解释可直测；逐日请求、停请求、结构解析仍留来源测试 |
| `test_context_acquisition_receipts.py:730`、`:756`、`:774` | 假 `index_response`、不同目录契约；直接 adapter | 结构通过但入库拒收、入库结果只写一次；不应把这些存储契约测试删掉 |
| `test_official_listing_pages.py:217`、`:239`、`:259` | 本地央行公告列表、央票与逆回购原件；直接刷新/账本/缺口清单 | `skipped` 不等于拒收、真实拒收原因展示；列表选择仍在获取流程测 |
| `test_gap_source_repairs.py:347`、`:360`、`:372` | `completed` 模块级夹具 `:216`，注册完整目录、假各来源、一次完整 Worker | 获取失败、入库拒收原因可拆到接口；SOX 不检索仍保留获取/运行验证 |
| `test_gap_list.py:118`、`:175` | 模块级 `published` 夹具 `:103`，180 日证据、一次完整运行 | 原因适配可直测；页面/报告共用缺口清单保留；`:157/:169` 已归票 10 |
| `tests/catalog/test_release_calendar.py:42`、`:82` | 纯发布时间对象，无运行库 | LPR 的值优先及失败分类已有直接覆盖；不需要候选 4 才能提速 |
| `test_processing_batch.py:94`、`:111`、`:136`、`:148` | `completed_run` 模块级夹具、假 HTTP、完整 Worker | 批次贯穿明细/汇总及不进入页面报告的关联必须保留 |
| `test_rrr_backtrack.py:357` | 本地栏目、追溯与缺口接口 | “查过没有”不等于检索失败；规则属于事件发现，模块只消费其领域结果 |

30. **用户给的两个行号不是同一个测试的两例。** `:38` 是 EIA 测试的三分支参数化，`:217` 是另一个 GDP/国债测试的结果断言；当前 EIA 三分支最终都断言 HTML 回退 `source_failed`，API 自身的缺凭据/源失败/校验失败另外查询记录验证。依据：`test_full_run_retrieval.py:38`、`:82`、`:104`、`:133`、`:217`。

31. **耗时收益只能引用既有记录，不能报成预计节省。** 原勘察记了约 35.37/34.46 秒，但没有足够依据逐一对应当前全部参数分支；720 条夹具来自 180 天×日历及三核心，且票 01/02 已计划优化或替换它，`test_gap_source_repairs` 的 89 秒还是共享 setup 而非单例成本。依据：`.scratch/architecture-review-20260929/codex-survey.md:58`、`test_full_run_retrieval.py:330`、`.scratch/architecture-review-20260929/issues/01-test-speed-existing-seams.md:14`；`docs/agents/testing.md:5` 的三分钟是目标，不是这些测试的测量结果。

32. **新接口最值得补的分支，是现有源码测试中未见集中覆盖的归并边界。** 包括不同运行先受理后执行、旧运行恢复、同目标日跨批次、截止之后尝试、同时间并列、目录不符、同品种跨日、品种失败后单日成功补齐、多品种不同原因、成功后空交付、成功后历史拒收仍存在；分别对应第 11–19 条静态风险。应先用少量领域事实和回执锁定这些行为，再保留一例完整运行验证关联，不能只造预期 metadata 后断言原样返回。

33. **“删除测试”的判断：只搬 SQL、仍返回未经解释的 metadata，模块深度没有增加。** 删除这样的模块，只会把查询语句搬回去；删除真正加深的模块，则调用方必须重新实现批次归属、请求范围、品种隔离、失败阶段、替代关系和可见性视图，这才说明隐藏了有价值的复杂度。README 已明确反对仅凭回执 SQL 数量建万能读取模块：`.scratch/architecture-review-20260929/README.md:19`。

34. **建议范围是一个受限模块、两步实施，不扩成新的获取编排系统。** 第一步集中现有读取语义并显式保留差异、引入解释后的结果类型；第二步分别修订已确认的归属、成员键和二次记录问题，VIX 等有依据的例外保留，候选 2/3 已划走的复核、冲突、汇总逻辑不重做。收益主要是解释一致和直接测试，而不是已证明的运行性能瓶颈；票 15 的性能依据更充分。

35. **新增正式测试接缝还需要在后续设计中说明与 ADR-0034 的关系。** 该 ADR 已把获取、检索、时效和运行级缺口材料列为完整运行覆盖事项，并要求每项保留少量用例；可以把纯结果解释分支迁到候选 4 接口，但不能据此删除所有获取与生命周期覆盖。依据：`docs/adr/0034-day-summary-second-test-seam.md:11`、`:12`、`:18`。
