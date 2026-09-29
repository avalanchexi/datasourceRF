首选是加深**“目标交易日／120 日证据窗口”的交易日历 module**；其次是把**来源声明是否可采用**集中到证据仓库的 interface。前者已有三处重复解释回执，后者已有两套家族分派逻辑，都是明确的 locality 问题。[full_run_requirements.py:29](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:29)、[search_evidence.py:185](/mnt/d/cursor/datasourceRF/src/pring_cycle/search_evidence.py:185)、[context_projection.py:1487](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1487)

本次只读，未修改文件、未联网、未运行测试。以下秒数来自你提供的记录；耗时归因是静态读码判断，收益用可消除的工作量和现有耗时上限表达。

**慢测试：最明显的放大项是完整 Worker 的首次初始化，但还不能给出耗时占比。**

| 因素 | 代码证据与判断 |
|---|---|
| 每例初始化运行库 | `prepare()` 在测试函数内初始化运行库、激活模型，因此这些成本被计入 `call`；初始化执行迁移，并创建投影、运行、报告等存储及三个内置模型。[test_full_run_retrieval.py:22](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:22)、[runtime.py:136](/mnt/d/cursor/datasourceRF/src/pring_cycle/runtime.py:136)、[runtime.py:251](/mnt/d/cursor/datasourceRF/src/pring_cycle/runtime.py:251) |
| 逐条写入来源声明 | `seed_core_history()` 默认写入 180 天 ×〔日历＋三核心〕＝**720 条来源声明**，不是 720 张回执；每次单条追加进入一次写事务。已有批量追加 interface，因此这部分首先是夹具用法问题。[test_full_run_retrieval.py:320](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:320)、[evidence.py:551](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:551)、[evidence.py:577](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:577) |
| 首次运行逐日补算 | 空运行库没有汇总，Worker 对窗口内此前 **119 天**逐日调用核心就绪判断、构建上下文投影、发布汇总，然后再发布目标日；上下文投影每次遍历相关指标。这是最强的重复工作证据。[worker.py:530](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:530)、[worker.py:587](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:587)、[context_projection.py:294](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:294) |
| `89.34s setup` | `completed` 是 **module 作用域**夹具，初始化、登记并激活 v0013 后执行一次完整 Worker，再把结果给整个文件复用；不能把 89 秒记成国债收益率自身成本，也不能按测试数量重复计算。[test_gap_source_repairs.py:216](/mnt/d/cursor/datasourceRF/tests/integration/test_gap_source_repairs.py:216)、[test_gap_source_repairs.py:247](/mnt/d/cursor/datasourceRF/tests/integration/test_gap_source_repairs.py:247) |
| 广度与仓单回执 | 上述夹具提供成功的广度、期货、仓单响应；广度逐交易日取得行情和因子，郑商所按品种开回执，因此这个 setup 确实包含大量回执、原件和声明落盘。回执捕获本身经历开始、收到、校验与原件保存等步骤。[test_gap_source_repairs.py:190](/mnt/d/cursor/datasourceRF/tests/integration/test_gap_source_repairs.py:190)、[breadth.py:314](/mnt/d/cursor/datasourceRF/src/pring_cycle/breadth.py:314)、[czce_warrants.py:448](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:448)、[acquisition.py:175](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:175) |
| 外部等待与模型激活 | 当前夹具令官方网站失败立即返回、取消郑商所请求间隔，并关闭真实 AI 搜索；模型激活只是检查与更新生效指针，没有历史回放。现有证据不支持把这些慢例主要归因于真实网络或模型激活。[conftest.py:70](/mnt/d/cursor/datasourceRF/tests/conftest.py:70)、[conftest.py:128](/mnt/d/cursor/datasourceRF/tests/conftest.py:128)、[models.py:288](/mnt/d/cursor/datasourceRF/src/pring_cycle/models.py:288) |

所以，**“所有行为只能穿过 Worker 才能测”不成立**：已有测试直接调用 `FullRunRetrieval.retrieve()`、`ModelInputSelector.select()` 和 `build_context_projection()`。真正的问题是部分领域规则仍在 Worker 内，另一些已有 interface 却没有被慢测试利用。[test_worker_reviewed_context.py:398](/mnt/d/cursor/datasourceRF/tests/integration/test_worker_reviewed_context.py:398)、[test_worker_reviewed_context.py:267](/mnt/d/cursor/datasourceRF/tests/integration/test_worker_reviewed_context.py:267)

---

**1．加深“目标交易日／120 日证据窗口”的交易日历 module — Strong**

- **涉及文件与全部直接调用链：**  
  启动路径：`cli` → `launch_calendar` → 回执 SQL／normalized；完整运行路径：`FullRunRetrieval._plan` → `required_calendar` → 日历来源声明／回执 SQL；仓单路径：`refresh_context_sources` → `window_trading_days` → 回执 SQL／normalized。[cli.py:314](/mnt/d/cursor/datasourceRF/src/pring_cycle/cli.py:314)、[freshness.py:628](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:628)、[full_retrieval.py:358](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:358)、[full_run_requirements.py:29](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:29)、[worker.py:1749](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1749)、[czce_warrants.py:259](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:259)
- **问题：** 三个调用方都必须知道日历回执的 parser、normalized 形状、覆盖区间和失败方式，而这些知识没有集中到日历 interface。启动路径取符合条件的回执并允许工作日推定；完整运行要求完整窗口且检查声明冲突；仓单路径合并覆盖区间，不完整时只取目标日——这些用途差异应保留。[freshness.py:643](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:643)、[full_run_requirements.py:50](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:50)、[czce_warrants.py:272](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:272)
- **方案：** 让交易日历 module 集中解释日历材料、覆盖范围、冲突和可信程度，为目标交易日与证据窗口提供领域结果；用途相关的降级选择继续明确表达。
- **删除测试：** 删除这样的 module，parser 识别、材料读取、区间覆盖和冲突知识会散回上述三个调用方，具有明确 leverage；仅增加一个返回 SQL 行的转手函数则仍是 shallow。广度回执把关联标量写入 normalized，正说明“请求名相同”不等于“材料含义相同”。[tushare_context.py:280](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:280)、[tushare_context.py:309](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:309)
- **依赖类别：** 日期计算为 **in-process**；SQLite 与原件为 **local-substitutable**；需要补取日历时，TuShare 使用 **mock adapter**。现有获取 adapter 已接受替换 transport。[source_adapters.py:152](/mnt/d/cursor/datasourceRF/src/pring_cycle/source_adapters.py:152)
- **测试改善与收益：** 广度回执污染、覆盖断档、截止时间、冲突可统一穿过日历 interface；`test_independent_calendar_keeps_missing_core_day_in_required_window` 的日历断言可移出完整运行，阶段阻断断言保留在汇总测试。可避免一次完整 Worker 和 119 次补算；该慢例现有总成本为 **32.54 秒，净节省小于此值、待测**。已有两组防广度回执污染测试可以合并规则覆盖。[test_freshness_contract.py:295](/mnt/d/cursor/datasourceRF/tests/integration/test_freshness_contract.py:295)、[test_czce_warrant_refresh.py:312](/mnt/d/cursor/datasourceRF/tests/integration/test_czce_warrant_refresh.py:312)、[test_full_run_retrieval.py:880](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:880)
- **ADR：无冲突。** 保留独立日历、完整窗口要求，以及郑商所日历不足只取目标日的决定；不统一成工作日猜测。[0032:19](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:19)

**2．加深证据仓库的“来源声明 → 已验证证据”选值 module — Strong**

- **涉及文件：** `ModelInputSelector` 按家族选择原件核对函数；上下文投影又分别处理 LPR、官方宏观、银行间、国债收益率、仓单等家族；官方核对函数内部还分派 TuShare 解析器及注册来源检查。[search_evidence.py:185](/mnt/d/cursor/datasourceRF/src/pring_cycle/search_evidence.py:185)、[context_projection.py:1487](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1487)、[official_context.py:396](/mnt/d/cursor/datasourceRF/src/pring_cycle/official_context.py:396)
- **问题：** 调用方取得来源声明后，仍须知道家族归属、原件核对、资讯命中原话与成员完整性，才能判定是否可采用。[search_evidence.py:221](/mnt/d/cursor/datasourceRF/src/pring_cycle/search_evidence.py:221)、[context_projection.py:1500](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:1500)
- **方案：** 加深现有证据仓库／选值 module，把家族分派、原件解释和可采用结果集中在同一 seam，让检索与投影共享其判断。
- **删除测试：** 删除加深后的 module，这些规则至少散回检索选值与上下文投影两处；当前 `source_claim_acquisitions_many()` 已集中批量读取和哈希检查，是可保留的 deep implementation 基础，缺的是上层领域判断的 locality。[evidence.py:366](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:366)
- **依赖类别：** 选值与成员判断为 **in-process**；SQLite、已保存原件为 **local-substitutable**。这条 seam 可完全离线；获取原件的 TuShare／官方网站另用 **mock adapter**。
- **测试改善与收益：** 原件错配、成员缺失、官方与资讯来源取舍可用少量声明和回执直接测试，不需要三核心 180 天历史。`test_gap_source_repairs` 的国债取值断言可移到该 interface，缺口展示另测；但 **89.34 秒是共享 setup，只有其他用例也脱离它后才能整体省下**。已有直接选值测试证明这个方向可行。[test_gap_source_repairs.py:274](/mnt/d/cursor/datasourceRF/tests/integration/test_gap_source_repairs.py:274)、[test_worker_reviewed_context.py:410](/mnt/d/cursor/datasourceRF/tests/integration/test_worker_reviewed_context.py:410)
- **ADR：无冲突，须明确保留当前规则。** 不恢复来源认证包或逐值发布时间证明；注册来源结构校验、资讯家族规则、郑商所来源替换、0.5% 来源冲突规则分别按现行 ADR 执行。[0021:7](/mnt/d/cursor/datasourceRF/docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[0026:13](/mnt/d/cursor/datasourceRF/docs/adr/0026-news-and-media-values-by-family-extraction-rules.md:13)、[0032:21](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:21)、[0033:9](/mnt/d/cursor/datasourceRF/docs/adr/0033-cross-source-values-compatible-within-half-percent.md:9)

**3．加深“目标交易日 → 汇总结果／分析投影集”module — Worth exploring**

- **涉及文件：** 目标日路径自行计算核心就绪、上下文、冻结快照并发布；补算路径另做一遍核心就绪、上下文与发布；现有 `p0` 发布 interface 要求调用方先准备核心状态、宏观、库存、缺口等材料。[worker.py:407](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:407)、[worker.py:445](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:445)、[worker.py:571](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:571)、[p0.py:59](/mnt/d/cursor/datasourceRF/src/pring_cycle/p0.py:59)
- **问题：** “怎样从某日证据得到一致的汇总”仍是 Worker 的 implementation 知识，调用现有发布 interface 前必须完成大量领域工作。
- **方案：** 把单日核心就绪、上下文计算与汇总一致性集中为可直接调用的 module，由目标日运行和漏跑日补算共同使用。
- **删除测试：** 删除后，规则会散回目标日与补算两条路径；若只是把 `_summarize_day` 原样挪文件、仍要求调用方准备相同材料，则 depth 没有增加。[worker.py:417](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:417)、[worker.py:595](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:595)
- **依赖类别：** 趋势与阶段计算为 **in-process**，证据与原子发布为 **local-substitutable**；单日汇总 seam 不需要真实外部 adapter。
- **测试改善与收益：** P2 失败不否决核心、核心沿用、来源冲突、补算日公开时间限制，可直接准备必要证据并计算目标日。对于只验证单日结果的场景，汇总计算可从 **120 天减至 1 天，少做 119 次**，并省去检索和报告步骤；对应 P2 慢例现有 **32.69–35.37 秒**是收益上限，不是预计节省。完整首次初始化及报告关联仍需保留少量完整运行测试。[test_full_run_retrieval.py:134](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:134)、[test_core_carry_forward.py:89](/mnt/d/cursor/datasourceRF/tests/integration/test_core_carry_forward.py:89)、[test_backfill.py:86](/mnt/d/cursor/datasourceRF/tests/integration/test_backfill.py:86)
- **ADR：无冲突。** 保留原子分析投影、首次初始化与漏跑日补算、显式恢复检查点；后者仍属于运行管理。推荐强度未定为 Strong，是因为目标日和补算日的快照、可见时间与报告职责确有差异，不能机械合并。[0008:7](/mnt/d/cursor/datasourceRF/docs/adr/0008-atomic-analytical-projection-sets.md:7)、[0024:7](/mnt/d/cursor/datasourceRF/docs/adr/0024-interrupted-runs-restart-as-new-batches.md:7)、[0031:9](/mnt/d/cursor/datasourceRF/docs/adr/0031-keep-run-resume.md:9)

**4．加深“加工批次中的获取尝试结果”module — Worth exploring**

- **涉及文件：** Worker 将异常解释为获取结果；`freshness` 按运行时间区间读取尝试、按品种归并；证据仓库另按截止时间、目标日与目录筛选最新尝试；上下文投影再次解释 metadata；缺口清单另外查询结构拒收回执。[worker.py:1932](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1932)、[freshness.py:829](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:829)、[evidence.py:884](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:884)、[context_projection.py:304](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:304)、[freshness.py:930](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:930)
- **问题：** “本批次某指标／成员取得了什么、为何失败”被多处从回执、尝试与 metadata 重建，调用方承担时间归属、后续成功覆盖失败、品种隔离等规则。
- **方案：** 将批次获取结果的归属与解释集中到一个 module，为运行读模型、缺口清单和投影提供一致的领域结果。
- **删除测试：** 删除后，归属、优先关系和错误解释会散回 Worker、缺口清单与投影；只有 SQL 搬家、继续返回未经解释的 metadata，则复杂度仍留给调用方。[freshness.py:850](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:850)、[context_projection.py:317](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:317)
- **依赖类别：** 结果归并为 **in-process**，SQLite 为 **local-substitutable**；触发真实获取行为的测试使用 TuShare、官方网站的 **mock adapter**。
- **测试改善与收益：** `test_p2_projection_separates_acquisition_condition_from_certification` 的缺凭据、获取失败、结构失败分支，可以用少量尝试和回执测试；保留一次完整运行验证输出关联。你列出的两例为 **35.37／34.46 秒**，每个迁移的分支可避开 720 条核心夹具声明与整轮补算，净秒数待测。国债部分字段缺失、仓单品种失败隔离也可复用该 seam。[test_full_run_retrieval.py:38](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:38)、[test_full_run_retrieval.py:217](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:217)
- **ADR：无冲突。** 获取失败与证据时效继续独立，P1/P2 失败只形成可见缺口；不同消费者的视图可以不同，不应强行统一为“最后一条决定一切”。[0021:7](/mnt/d/cursor/datasourceRF/docs/adr/0021-registered-sources-freshness-replaces-certification.md:7)、[CONTEXT.md:181](/mnt/d/cursor/datasourceRF/CONTEXT.md:181)

**5．加深“信用响应中的信用脉冲派生观测”module — Worth exploring**

- **涉及文件：** 取数起点在 Worker，公式所需期数在 `full_run_requirements`，累计转单期、连续性、输入选择和血缘在 `context_projection`，算术函数只接收四个已汇总数字。[worker.py:1979](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1979)、[full_run_requirements.py:107](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:107)、[context_projection.py:2143](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2143)、[domain/macro.py:49](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:49)
- **问题：** 信用脉冲的 interface 要求调用方先理解 24 个月、8 个季度、累计差分基期及输入血缘，真正复杂的公式知识散在取数、缺口规划和投影中。
- **方案：** 将信用脉冲的公式回看需求、输入解释、计算失败原因与派生血缘集中成一个领域 module。
- **删除测试：** 删除当前四数算术函数，主要只剩几行运算；删除加深后的 module，期数、差分基期和缺失解释会散回取数、规划与投影三个调用方，后者才有足够 leverage。[domain/macro.py:56](/mnt/d/cursor/datasourceRF/src/pring_cycle/domain/macro.py:56)、[full_run_requirements.py:149](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:149)、[context_projection.py:2221](/mnt/d/cursor/datasourceRF/src/pring_cycle/context_projection.py:2221)
- **依赖类别：** 期数、差分与运算为 **in-process**；来源声明读取与派生观测保存为 **local-substitutable**。公式 seam 不需要外部 **mock**。
- **测试改善与收益：** `test_credit_formula_expands_required_history_in_full_run_plan`、GDP 累计基期和现有信用脉冲投影测试，可直接测试需求与结果的一致性，避开三核心夹具和完整运行。没有提供这些例子的单独耗时，不能报秒数；明确可省的是完整 Worker、119 次无关补算，以及全上下文计算。[test_full_run_retrieval.py:904](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:904)、[test_full_run_retrieval.py:976](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:976)、[test_context_projection.py:1306](/mnt/d/cursor/datasourceRF/tests/integration/test_context_projection.py:1306)
- **ADR：无冲突。** 公式回看仍临时取得、只用于计算，不扩大证据窗口；不恢复旧的逐值发布时间取证或历史回放要求。[0022:7](/mnt/d/cursor/datasourceRF/docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7)、[0021:11](/mnt/d/cursor/datasourceRF/docs/adr/0021-registered-sources-freshness-replaces-certification.md:11)

---

**回执 SQL 全部生产调用点**

全仓检索后，`src/pring_cycle` 中直接 `FROM/JOIN acquisition_request` 共 **21 处、10 个文件**，如下。测试中的 SQL 断言不计为生产调用方。

| 文件与行号 | 当前承担的解释 |
|---|---|
| [freshness.py:639、934](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:639) | 启动日历；结构拒收进入缺口清单 |
| [full_run_requirements.py:54](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:54) | 完整运行所需日历 |
| [czce_warrants.py:268](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:268) | 仓单窗口与覆盖范围 |
| [tushare_news.py:81、192](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_news.py:81) | 上次完整资讯拉取的结束位置；本运行资讯原件 |
| [full_retrieval.py:803](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:803) | 完整运行回执追踪 |
| [search_evidence.py:1088](/mnt/d/cursor/datasourceRF/src/pring_cycle/search_evidence.py:1088) | 候选验证记录中的网址、原件哈希、parser |
| [retrieval_ledger.py:396、402、475、616](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:396) | 请求绑定、前次完成状态、恢复检查点、原件过期清理 |
| [evidence.py:379、431、590、1168](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:379) | 声明关联原件、发布材料、入库时间约束、查询追踪 |
| [acquisition.py:322、361、371](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:322) | 入库结果、单张回执、回执历史 |
| [retention.py:226、248](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:226) | 资讯原件过期与孤立原件清理 |

`source_claim`／`effective_source_claim` 的直接读取则主要集中在 `evidence.py`；外部命中是 `full_retrieval` 的采用记录以及 `retention` 的留存清理。因此，**声明表 SQL 外泄的证据弱于“取出声明后重复解释其含义”的证据**。[evidence.py:624](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:624)、[full_retrieval.py:738](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:738)、[retention.py:154](/mnt/d/cursor/datasourceRF/src/pring_cycle/retention.py:154)

不建议仅凭这些 SQL 新建一个万能回执读取 module：现有获取 module 已隐藏状态推进、时间约束、原件保存及哈希校验，已有 depth；日历、资讯读取进度、恢复与留存各有不同领域语义。应优先集中重复的领域解释，而不是只把 SQL 改成方法调用。[acquisition.py:153](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:153)、[acquisition.py:244](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:244)、[acquisition.py:377](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:377)

另外，**共享搜索预算的慢测试不必等新 module**：已有 `FullRunRetrieval.retrieve()` 可直接执行检索，它使用持久账本计费；可以把跨期预算断言移到这条现有 interface，另保留完整运行关联验证。这样避免把“已有 seam 未使用”误判成“缺少 seam”。[full_retrieval.py:116](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:116)、[test_full_run_retrieval.py:615](/mnt/d/cursor/datasourceRF/tests/integration/test_full_run_retrieval.py:615)

**首选交易日历 module。** 它有三个真实调用方、已经发生的 normalized 含义混淆，以及可直接迁移的回归测试；加深后能让调用方不再学习 parser 身份和材料覆盖规则，同时保留各用途的降级语义。相较扩大 Worker 或拆分大文件，这项改动的 leverage、locality 与验证范围最明确。[freshness.py:639](/mnt/d/cursor/datasourceRF/src/pring_cycle/freshness.py:639)、[full_run_requirements.py:54](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:54)、[czce_warrants.py:268](/mnt/d/cursor/datasourceRF/src/pring_cycle/czce_warrants.py:268)、[test_freshness_contract.py:295](/mnt/d/cursor/datasourceRF/tests/integration/test_freshness_contract.py:295)
