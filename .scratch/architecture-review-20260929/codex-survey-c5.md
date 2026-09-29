# 候选 5 勘察：信用脉冲派生观测

来源：Codex 只读勘察（2026-09-29，`codex exec -s read-only`），静态读码、未实测。

**0. 结论：值得建立信用脉冲专用模块，但不能把现状描述为“规则已统一，只需搬代码”。** 目前确有期数重复、取数与规划终点不同、可计算性与时效分离，以及 `stale_inputs` 被缺口合并视作失败等差异；“公式回看不入库”也与实际实现不符。以下仅依据代码、文档及指定提交的静态阅读，未修改文件、运行测试、执行 `uv sync` 或发起网络请求。

**1.1 知识清单——公式【公式／投影】。** 信用脉冲为 `100 ×（最近12个月社融流量÷最近4季度名义GDP－此前12个月社融流量÷此前4季度名义GDP）`，单位为百分点；“此前”是前一整段年度窗口，不是向前移动一个月的滚动窗口。四数算术在 `src/pring_cycle/domain/macro.py:49`，两段输入求和在 `src/pring_cycle/context_projection.py:2319`。

**1.2 所需期数【需求规划／投影】。** 基本需求是连续24个月社融单月流量、连续8季度GDP当季名义量，两组终点各取自己的最新输入，并未要求社融末月与GDP末季对齐。规划常量在 `src/pring_cycle/full_run_requirements.py:108`；投影独立使用24／8以及12／4切片，见 `src/pring_cycle/context_projection.py:2221`、`:2260`、`:2319`。

**1.3 社融累计转单月【投影】。** 优先使用 `monthly_increment`；只有不足24条且公式为 `credit-impulse-ytd-flow-v0002` 时，才用 `ytd_increment` 差分。1月直接采用当年累计值，其他月份要求同年紧邻上月，差分允许为负，父血缘包含差分两端；见 `src/pring_cycle/context_projection.py:2260`、`:2517`。

**1.4 GDP累计转当季【投影】。** 优先使用 `aggregate=total, measure=nominal_quarterly_level`；不足8条时，两个较新版本允许从 `nominal_ytd_level` 转换。Q1直接采用累计值，Q2—Q4必须有同年上一季度，使用十进制差分并跳过非正结果；见 `src/pring_cycle/context_projection.py:2185`、`:2196`、`:2483`。

**1.5 差分基期【需求规划】。** GDP走累计分支且8季窗口首季不是Q1时增加1期，社融走累计分支且24月窗口首月不是1月时增加1期，因此实际需求可以是24／8、25／8、24／9或25／9。是否增加基期，还取决于当前已持有的直接单期输入数量；见 `src/pring_cycle/full_run_requirements.py:149`、`:177`。

**1.6 回看取数起点【Worker】。** Worker以目标日上海时区日终，按发布规则求社融与GDP最新发布期，再分别倒推25个月、9季度，并与旧的“目标日减两年”起点取较早者。结果转换为TuShare所需的 `YYYYMM`／`YYYYQn`，交给社融与GDP适配器；见 `src/pring_cycle/worker.py:1771`、`:1863`、`:1886`、`:1979`。

**1.7 上游输入含义【取数适配器，Worker边界】。** 已审核社融总量交付与旧社融交付不同，Worker依据目录来源代码选择 `social_financing_total` 或 `social_financing`；旧接口同时提供单月增量、累计增量和存量。GDP适配器把名义量明确解释为年初至今累计值，不把同比字段当名义分母；见 `src/pring_cycle/worker.py:1780`、`src/pring_cycle/tushare_context.py:462`、`:496`、`:1581`。

**1.8 来源声明选择【投影依赖的证据仓库】。** 仓库先按可见截止点保留每个provider的最新声明，再优先认证声明、其次按provider排序，并比较合格来源是否冲突。目标日包装层还会按目标日重新筛选、重选；见 `src/pring_cycle/evidence.py:1397`、`src/pring_cycle/context_projection.py:609`、`:730`。

**1.9 输入可采用性【投影】。** 每个实际参与计算的父点必须为 `selection_status=selected`、已报告数值、数值非空且选中声明质量为 `validated`。非内置目录还逐个复核父声明，允许官方原件、TuShare交付及注册契约、命中原话等路径；见 `src/pring_cycle/context_projection.py:2297`、`:2421`、`:576`，以及 `src/pring_cycle/official_context.py:396`。

**1.10 GDP vintage规则【投影＋证据读取】。** 对每一个累计差分季度，只要存在一次TuShare交付同时陈述了其全部输入端点，且数值与当前选中值完全一致，即免做公告当季量核对；不要求当前选中声明共享同一回执，也不要求整个8季窗口共享一次交付。未获豁免的季度必须与其关联统计局公告中的当季名义量完全相等；见 `src/pring_cycle/context_projection.py:2448`、`src/pring_cycle/evidence.py:329`、`src/pring_cycle/official_context.py:435`。

**1.11 连续性、时效及血缘【投影】。** 连续性按月／季度序号相邻检查；时效只检查社融末月与GDP末季，不因历史回看父点较老而拒算。成功结果携带全部实际父声明ID、公式版本、两组窗口、最大系统／公开可用时间及派生ID；见 `src/pring_cycle/context_projection.py:2291`、`:2432`、`:2332`、`:2353`、`:2390`。

**1.12 目录、模型及术语【目录／模型配置】。** 信用脉冲属于P1信用响应、单位为百分点，新目录按月频；GDP为季度输入，社融和GDP分别以 `measure`、`aggregate+measure` 区分口径，公式版本则由模型清单冻结。证据见 `src/pring_cycle/catalog.py:93`、`:433`、`:445`、`:553`、`:593`、`:613`及 `src/pring_cycle/models.py:65`；`CONTEXT.md`并没有单独的“GDP”或“信用脉冲公式”条目，只有信用响应、派生观测、可采用声明等定义，见 `CONTEXT.md:161`、`:229`、`:271`。

**2.1 重复——24／8并未真正集中。** `CREDIT_IMPULSE_INPUT_PERIODS`只被规划和取数起点共享，投影仍另写8、24、4、12，规划分支内部也另写8／24。当前数值一致，但修改常量不会自动修改计算窗口，证据为 `src/pring_cycle/full_run_requirements.py:108`、`:156`、`:164`与 `src/pring_cycle/context_projection.py:2221`、`:2260`、`:2319`。

**2.2 不一致——Worker与规划并非共用完整回看决策。** Worker无条件按25／9期倒推；规划按公式版本、已持有口径及年界条件决定是否增加基期，因此直接单期输入充足或窗口始于1月／Q1时会多取一期。更关键的是Worker以最新发布期为终点，规划 `_period()` 对月／季频优先采用已持有最新期，只有完全没有数据时才退到发布规则；见 `src/pring_cycle/worker.py:1989`、`src/pring_cycle/full_run_requirements.py:117`、`src/pring_cycle/full_retrieval.py:504`。

**2.3 不一致——规划与取数使用的时间截止也不同。** Worker回看起点固定用目标日日终，规划发布期用 `min(selector.as_of, utc_now(), target_end)`；同日尚未到发布时点时，两者可能得出不同最新期。其后果是“共用发布注册表”不等于“起止期完全一致”，见 `src/pring_cycle/worker.py:1989`与 `src/pring_cycle/full_retrieval.py:551`。

**2.4 不一致——规划数可用点，投影先数有声明的点。** 规划 `_reported_count()`要求选中、数值存在、质量合格；投影决定是否走直接单期分支时只要求 `point.claims`，之后才检查可用性。因此存在24个月／8季度直接口径但其中有坏点时，投影会失败而不再尝试完整累计口径；见 `src/pring_cycle/full_run_requirements.py:177`与 `src/pring_cycle/context_projection.py:2165`、`:2221`、`:2260`、`:2297`。

**2.5 不一致——直接口径优先并不比较“哪个口径更新”。** 只要直接单期口径达到数量门槛，投影就选它，即使累计口径更新；累计路径则额外要求转换结果末期等于累计原序列末期。读码后果是可能采用较旧直接窗口，或因直接窗口断期拒算，而不是采用可计算的较新累计窗口；见 `src/pring_cycle/context_projection.py:2221`、`:2232`、`:2260`、`:2269`。

**2.6 父指标映射一致，但不能据此推断可计算性。** `freshness.py:204`与 `context_projection.py:363`都映射到 `CN_SF_TOTAL、CN_GDP`，没有父指标集合冲突。时效读取各指标“持有到哪期”，不复核公式所需口径、连续历史或原件，因此父项current而信用脉冲 `missing_inputs` 是现行可能状态；见 `src/pring_cycle/freshness.py:527`、`:594`与 `src/pring_cycle/context_projection.py:2291`。

**2.7 明确缺陷——`stale_inputs`与缺口合并的状态集合不一致。** 信用脉冲能够算出并保存旧值，输出行是 `stale`、公式状态是 `stale_inputs`，但 `_USABLE_DERIVED_STATUSES`包含 `stale`却不包含 `stale_inputs`，且公式状态优先。因此未已有缺口时会新增 `derived_failed`，已有时效缺口时则附加 `formula_status=stale_inputs`；见 `src/pring_cycle/context_projection.py:2385`、`:2404`与 `src/pring_cycle/freshness.py:975`、`:1043`。

**2.8 不一致——规划缺口并不等于公式缺失输入。** 信用公式只需要社融流量和GDP总量名义值，但完整运行按父指标整组成员执行 `selector.select()`，缺口合并再按父指标名收集所有未齐成员。所以 `missing_inputs`可能包含公式并不消费的存量、GDP同比等成员，也可能在vintage不相容时为空；见 `src/pring_cycle/full_retrieval.py:404`、`:598`与 `src/pring_cycle/freshness.py:1052`。

**2.9 与文档冲突——回看输入实际先入库，再清理。** `CONTEXT.md:68`及 `docs/adr/0022-uniform-120-day-retention-and-processing-batches.md:7`写的是“不入库”，但TuShare导入遍历全部交付标量并追加来源声明，成功运行末尾才按统计期删除超窗明细。证据为 `src/pring_cycle/tushare_context.py:970`、`:1144`、`src/pring_cycle/worker.py:523`及 `src/pring_cycle/retention.py:154`，因此原勘察的“ADR无冲突”只能描述重构目标，不能作为现状判断。

**2.10 血缘保存不等于父输入长期可回读。** 派生记录按 `as_of_cutoff`留存，父声明按 `period_end`留存；当前信用脉冲留下的父ID可指向已经清理的回看声明。派生trace仍能返回ID和值，却不能据此保证全部父原件可追溯，见 `src/pring_cycle/retention.py:147`、`:154`及 `src/pring_cycle/evidence.py:1282`。

**2.11 补算窗口的回看需求尚未由同一规则覆盖。** 当前取数起点为目标日准备24月／8季窗口，随后补算较早交易日时按该日公开边界重新选择输入，较早日期可能需要更早的回看数据。代码没有把回看起点扩展到120交易日窗口首日的公式需求；这是读码推断的补算覆盖风险，见 `src/pring_cycle/worker.py:1775`、`:437`、`:595`及 `src/pring_cycle/context_projection.py:659`。

**2.12 已知选值差异也会影响信用父声明。** 仓库按认证状态再按provider排序，目标日重选却只按provider排序，冲突比较也不再限定认证声明；这正是候选2记录并交给票08的差异。信用脉冲使用目标日包装仓库，因此受影响，见 `src/pring_cycle/evidence.py:1435`、`src/pring_cycle/context_projection.py:730`及 `.scratch/architecture-review-20260929/README.md:50`。

**3.1 `credit-impulse-v0001`仍可执行。** 它由 `certified_model_v0001_manifest()`配置，只接受24个月直接社融流量和8季度直接GDP量，不启用两类累计转换。它仍在支持版本集合中，且有保持版本身份的投影测试；见 `src/pring_cycle/models.py:66`、`src/pring_cycle/context_projection.py:116`、`:2196`、`:2267`及 `tests/integration/test_context_projection.py:858`。

**3.2 `credit-impulse-rolling-share-v0001`仍可执行。** 它由model-v0002配置，model-v0003及v0006继承，允许GDP累计转当季，但社融仍须直接单月流量。证据为 `src/pring_cycle/models.py:75`、`:103`、`:126`以及 `src/pring_cycle/context_projection.py:2196`、`:2267`。

**3.3 `credit-impulse-ytd-flow-v0002`是后续模型继承的版本。** model-v0007将信用公式切到该版本，后续v0008—v0011以及v0012、v0013继续继承，允许社融与GDP累计转换，同时仍优先直接单期输入。证据为 `src/pring_cycle/models.py:143`、`:166`、`:203`、`:561`、`:484`；这只能证明配置和执行路径仍活着，本次没有读取运行数据库来确认实际生效模型。

**3.4 版本分派在投影，算术函数不认识版本。** `ContextProjectionRules.from_manifest()`检查版本支持性，`build_context_projection()`把版本传给同一个 `_credit_impulse_proxy()`，后者用条件分支控制输入解释；三个版本最终都调用同一四数公式。证据为 `src/pring_cycle/context_projection.py:147`、`:425`、`:2196`、`:2267`、`:2324`。

**4.1 派生观测确实持久化。** 目标日调用默认 `persist_derived=True`，由投影中的 `_derived_observation_identity()`调用 `EvidenceRepository.append_derived_observation()`，写入SQLite表 `derived_observation`。证据为 `src/pring_cycle/worker.py:417`、`src/pring_cycle/context_projection.py:250`、`:1361`及 `src/pring_cycle/evidence.py:1239`。

**4.2 持久化内容包含结果和精确输入身份。** 表中保存指标、公式版本、父ID JSON、as-of模式与截止时间、计算时间、数值、单位及批次ID；派生ID由排序后的父ID、公式、截止点、数值等共同哈希生成。相同输入在不同截止点也可产生不同派生ID，追加采用 `INSERT OR IGNORE`，见 `src/pring_cycle/evidence.py:1226`、`:1239`。

**4.3 表的直接业务读取方是证据追溯。** `derived_trace(id, mode, as_of)`按明确ID读取，并检查模式、计算时间和截止时间；Web证据追溯在普通观测查找失败后调用它。没有发现按指标“取最新派生值”的读取路径，见 `src/pring_cycle/evidence.py:1260`、`src/pring_cycle/web.py:127`。

**4.4 缺口、时效、报告和检索不直接靠派生表取值。** 缺口消费本次投影文档与计划，时效消费来源声明及父映射，报告消费已发布投影，完整检索跳过独立派生输出并规划其父项。证据分别为 `src/pring_cycle/freshness.py:978`、`:575`、`src/pring_cycle/reports.py:147`与 `src/pring_cycle/full_retrieval.py:364`、`:378`。

**4.5 `persist_derived=False`只是关闭派生表写入。** 它仍计算结果、生成与持久化路径同构的哈希身份、把结果和血缘放入投影；并不等于不派生、不返回血缘或整个调用只读。生产调用点是补算日 `src/pring_cycle/worker.py:608`，实现见 `src/pring_cycle/context_projection.py:1373`。

**4.6 `False`的测试调用点并不限信用脉冲。** 还出现在 `tests/fixtures/public_context.py:57`、`tests/integration/test_context_projection.py:990`、`tests/integration/test_inventory_period_alignment.py:62`、`:147`、`:246`以及 `tests/integration/test_p2_source_timing.py:81`、`:103`。它控制整个上下文的派生持久化，不能在信用模块重构时改变其他派生指标的行为。

**4.7 票12关于“历史派生污染最新查询”的猜测没有得到支持。** `git log -S`定位到提交 `edb8b1d`引入补算调用中的 `False`，但该提交说明和旧票24没有解释关闭原因；当前又未见“按指标取最新派生表记录”的消费者。因此只能报告“动机未查明”，不能据此断言可以安全开启，见 `.scratch/architecture-review-20260929/issues/12-backfill-day-evidence-snapshot.md:14`、`src/pring_cycle/evidence.py:1272`。

**5.1 `_credit_impulse_proxy()`只有一个生产调用方。** `build_context_projection()`传入已经按目标日约束的仓库、as-of、配置公式版本、目录版本、指标定义、模式和持久化开关；得到“可选证据行、公式诊断文档、父ID加派生ID”。调用及结果接入位置为 `src/pring_cycle/context_projection.py:425`、`:434`、`:477`，返回定义为同文件`:2407`。

**5.2 `calculate_credit_impulse()`只有一个生产调用点。** `_credit_impulse_proxy()`传入两段社融总流量和两段GDP总量，取得浮点百分点值，或捕获非正GDP引起的 `ValueError`。直接测试调用只有 `tests/domain/test_macro_states.py:90`、`:103`，生产调用见 `src/pring_cycle/context_projection.py:2324`。

**5.3 `CREDIT_IMPULSE_INPUT_PERIODS`只有两个直接使用位置。** `credit_lookback_start()`取其中期数加一，返回最早月／季字符串；`formula_requirements()`取其副本并按口径与年界调整，返回各输入最大需求期数及派生需求列表。证据为 `src/pring_cycle/full_run_requirements.py:117`、`:128`、`:174`；投影没有调用这个常量。

**5.4 回看与需求函数的上层调用链。** `refresh_context_sources()`调用 `_credit_lookback_starts(target)`，后者分别调用两次 `credit_lookback_start()`；完整运行规划另由 `FullRunRetrieval._plan()`调用 `formula_requirements()`，再用 `preceding_periods()`枚举需求。证据为 `src/pring_cycle/worker.py:1775`、`:1993`及 `src/pring_cycle/full_retrieval.py:364`、`:402`，没有发现对回看函数的直接测试调用。

**6.1 不计算——未配置或非法模型。** 未配置 `credit_impulse`返回公式状态 `disabled_by_model`、无结果和血缘，缺口合并明确跳过该状态；未知版本则在清单解析时抛 `context_model_formula_version_unsupported`，依赖指标缺失抛 `context_model_metric_missing:…`。后两者不是普通派生缺口，在Worker边界转为 `worker_failure:ValueError:…`并进入action-required，见 `src/pring_cycle/context_projection.py:169`、`:367`、`:2163`、`src/pring_cycle/freshness.py:975`及 `src/pring_cycle/worker.py:229`。

**6.2 算不出——数量不足、缺基期、末期无法转换。** GDP转换结果不足8季，或末期落后原累计序列；社融不足24月且不能走累计分支，或累计转换不足24月／末期落后，均返回 `missing_inputs`。这包括错误口径、缺差分基期、缺值及不允许累计转换的旧版本，且GDP检查先执行，可能先遮住社融问题；见 `src/pring_cycle/context_projection.py:2232`、`:2267`、`:2287`、`:2295`。

**6.3 算不出——断期。** 社融24个选定月不连续返回 `nonconsecutive_social_financing_inputs`，GDP8个选定季不连续返回 `nonconsecutive_gdp_inputs`。累计转换会先跳过无法构造的单期，所以同一种缺期可能因剩余数量不同呈现为 `missing_inputs`或连续性错误，见 `src/pring_cycle/context_projection.py:2291`、`:2502`、`:2534`。

**6.4 算不出——父声明不能使用。** 冲突、非报告数值、空选值、缺选中声明或质量未验证统一归为 `missing_inputs`，并未提供各自独立的信用公式原因码；非内置目录原件／原话／注册契约复核不通过才返回 `incomplete_source_artifacts`。证据为 `src/pring_cycle/context_projection.py:2297`、`:2308`、`:2421`，父指标冲突另可在缺口清单记录 `value_disagreement`或 `unit_scale_mismatch`，见 `src/pring_cycle/freshness.py:1062`。

**6.5 算不出——GDP版本或分母不合法。** 未获同交付豁免且公告当季量不匹配，返回 `incomparable_gdp_vintages`；两段GDP合计任一非正，纯函数抛 `credit_impulse_gdp_must_be_positive`，投影转为 `invalid_gdp_denominator`。注意累计GDP的Q2—Q4非正差分会更早被跳过，最后可能表现为缺期，而不是分母错误；见 `src/pring_cycle/context_projection.py:2315`、`:2330`、`:2511`及 `src/pring_cycle/domain/macro.py:56`。

**6.6 陈旧不是“没有算出”。** 末期落后达到投影不可用门槛时，仍生成数值和派生记录，但证据行为 `stale`、公式为 `stale_inputs`，不进入当前模型采用输入。投影门槛是落后至少2期，落后1期仍可参与计算并由时效清单揭示；见 `src/pring_cycle/freshness.py:738`、`src/pring_cycle/context_projection.py:2362`、`:520`。

**6.7 投影与状态的呈现。** 正常没有直接信用来源声明时，公式失败留下 `value=None/status=missing`的占位行，并在 `macro.credit.formula`保留详细状态；信用脉冲缺失会使过热所需credit角色不齐，但不必然使信用响应状态不足，因为后者强制要求的是货币、社融、贷款结构。证据为 `src/pring_cycle/context_projection.py:434`、`:477`、`:1721`及 `src/pring_cycle/domain/macro.py:88`、`:109`。

**6.8 缺口清单与报告的呈现不同。** 目标日投影后补入 `derived_failed`、`formula_status`及父项未齐列表，已有同指标条目则保留原类别和原因；补算路径不执行这一运行级缺口合并。报告保留完整缺口列表供确定性输出，但AI输入删除完整列表，只接收类别计数和P0/P1指标摘要，不含精确公式失败原因或父期清单；见 `src/pring_cycle/worker.py:497`、`:610`、`src/pring_cycle/freshness.py:1021`、`src/pring_cycle/reports.py:107`、`:317`。

**7.1 纯公式测试。** `tests/domain/test_macro_states.py:89`的 `test_credit_impulse_is_change_in_rolling_flow_share_of_nominal_gdp`覆盖算术，`:101`的 `test_credit_impulse_rejects_nonpositive_gdp_denominators`覆盖当前分母为0／负数。两者均为纯函数层，可保留为内部算术测试，或把相同断言迁至新模块，不需要Worker。

**7.2 版本身份投影测试。** `tests/integration/test_context_projection.py:858`的 `test_v1_credit_formula_identity_is_not_rewritten_to_v2`经过完整上下文投影，但只验证空输入时保留旧公式名，并不证明旧版本能成功计算。版本支持／选择断言可迁到新模块，保留一个投影装配断言即可。

**7.3 成功计算与持久血缘投影测试。** `tests/integration/test_context_projection.py:1113`的 `test_credit_impulse_is_persisted_with_exact_point_in_time_input_vintages`覆盖24月直接社融、8季直接GDP、数值、方向、统计期、父ID及派生trace。计算及血缘选择可迁至模块接口，派生表写读仍需要仓库集成覆盖。

**7.4 累计转换投影测试。** `tests/integration/test_context_projection.py:1306`的 `test_credit_impulse_derives_quarter_levels_from_reported_ytd_gdp`参数化覆盖直接社融、累计社融、累计社融断期，并验证GDP累计转换及父ID。它经过投影而非Worker，是最适合整体下移到信用模块的现有测试之一。

**7.5 末期时效投影测试。** `tests/integration/test_derived_context_freshness.py:188`的 `test_credit_impulse_checks_both_terminal_periods_without_rejecting_preheat`覆盖PUBLIC／SYSTEM、两类父项分别陈旧、仍计算保存及采用过滤。终点选择和“回看老输入不导致陈旧”的断言可迁模块，宏观support／gap和模型采用列表断言留在投影层。

**7.6 真正经过完整Worker的需求测试。** `tests/integration/test_full_run_retrieval.py:904`的 `test_credit_formula_expands_required_history_in_full_run_plan`与`:976`的 `test_credit_gdp_ytd_baseline_matches_required_window`均调用 `process_pending_run()`。24／8需求与GDP8／9期基期规则可迁模块，完整运行只需保留少量验证需求接入计划的断言。

**7.7 名称带Worker但没有经过完整Worker的测试。** `tests/integration/test_worker_reviewed_context.py:197`的 `test_credit_impulse_computes_from_levels_tushare_delivered_together`走直接刷新、适配器导入和投影，覆盖同次交付、单季重取同值、单季修订值；`:277`的 `test_credit_inputs_are_fetched_back_to_the_differencing_baseline`只验证直接刷新请求范围。前者的vintage规则可迁模块并保留交付关联集成例，后者的日期规则可迁模块，但适配器请求参数断言应保留。

**7.8 缺口规则已有纯函数接缝。** `tests/integration/test_derived_context_freshness.py:281`的 `test_a_formula_missing_inputs_is_a_gap_naming_the_parent_periods`、`:344`的 `test_a_metric_already_listed_keeps_one_row_with_what_the_projection_adds`及`:370`的 `test_a_computed_formula_leaves_no_gap`直接测试 `add_projection_gaps()`。`:321`的 `test_a_conflicted_metric_is_one_gap_listing_each_conflict`覆盖父项冲突去重；这些应留在缺口消费者层，无须迁入信用模块。

**7.9 通用持久化和Web测试不能算信用公式覆盖。** `tests/evidence/test_point_in_time.py:587`的 `test_trace_derived_lineage_attempts_and_snapshots_are_immutable_ledger_entries`、`:672`的 `test_derived_trace_is_point_in_time_gated`，以及 `tests/web/test_projection_api.py:226`的 `test_evidence_trace_rest_resolves_derived_formula_lineage`只是以信用指标ID直接写入人工派生值。它们分别属于仓库集成／Web层，应保留，不迁入公式模块。

**7.10 目录与下游状态测试。** `tests/catalog/test_metric_catalog.py:44`的 `test_multiscalar_metric_groups_freeze_measure_dimensions_and_allowed_units`验证信用月频，`:73`的 `test_contract_and_derived_metric_identities_preserve_required_semantics`验证百分点单位；`tests/domain/test_macro_states.py:39`的 `test_overheat_and_price_pressure_publish_named_states_without_scores`用信用信号验证过热。它们是目录／纯状态函数覆盖，不是输入解释与公式计算覆盖。

**7.11 静态可见的测试空白。** 未找到直接断言信用公式 `nonconsecutive_gdp_inputs`、`invalid_gdp_denominator`、`incomplete_source_artifacts`、缺版本禁用，以及 `stale_inputs`进入缺口合并行为的专门测试；分母纯函数测试也只改变当前分母。前述两类完整Worker用例测的是需求计划，不能当成“完整Worker成功派生信用脉冲”的覆盖证明，证据见 `tests/domain/test_macro_states.py:103`、`tests/integration/test_full_run_retrieval.py:904`、`:976`。

**8.1 与候选2票05的直接重叠。** 两者都会改 `src/pring_cycle/context_projection.py:2299`至父声明复核调用附近，票05明确列了信用父声明入口 `:2303`。建议先落票05，让信用模块消费可采用声明能力，避免重新复制官方／资讯／TuShare家族分派；GDP跨累计端点相容性仍属于信用输入解释，不应随普通声明复核全部搬走，见 `.scratch/architecture-review-20260929/issues/05-claim-adoption-module.md:3`及 `src/pring_cycle/official_context.py:439`。

**8.2 与候选3票10的重叠。** 票10会搬走目标日／补算日上下文调用和发布装配，即 `src/pring_cycle/worker.py:417`、`:497`、`:595`；信用模块若只替换投影内部实现，这些不是必然同一代码行，但若同时调整派生需求和缺口装配就会相撞。建议先完成票10的编排迁移，再接信用模块，保留目标日与补算日持久化差异，见 `.scratch/architecture-review-20260929/issues/10-day-summary-module.md:3`。

**8.3 与票12的交叉是持久化契约，不是已经决定打开写入。** 票12明确要求维持 `persist_derived=False`，先查原因，另议是否对齐；信用模块必须能返回未落库的结果、身份与父血缘，供补算快照引用。共同边界是 `src/pring_cycle/worker.py:608`和 `src/pring_cycle/context_projection.py:1361`，见 `.scratch/architecture-review-20260929/issues/12-backfill-day-evidence-snapshot.md:3`、`:20`。

**8.4 票13没有信用公式的直接同线修改。** 它改的是投影发布是否切换当前指针，主要在 `projections.py`及单日汇总发布调用，不改社融／GDP选择、差分或血缘。与信用模块的关系是补算产物可见性，而非算法依赖，见 `.scratch/architecture-review-20260929/issues/13-backfill-does-not-move-current-pointer.md:3`、`:13`。

**8.5 与候选4票16的交叉应控制在边界。** 票16主要修改 `context_projection.py:304`的获取状态装饰及 `freshness.py:825`、`:868`附近获取失败归并；信用核心在 `context_projection.py:2143`，不是同一算法块。若信用改造同时重写缺口合并或Worker取数编排，应与票16串行；建议顺序为05→10→信用模块，16在涉及这些共享消费者前完成，12／13按各自依赖推进，见 `.scratch/architecture-review-20260929/issues/16-acquisition-outcome-module.md:5`。

**9.1 建议接口：一个信用模块、两个公开操作。** 建议新建 `src/pring_cycle/credit_impulse.py`，提供 `requirements(formula_version, terminal_periods, inputs) -> CreditRequirements`与 `derive(formula_version, inputs, cutoff) -> CreditImpulseResult`，由同一输入解释规则决定直接／累计口径、精确所需期和差分基期。需求结果至少区分“最小计算需求”和“取数覆盖范围”，避免继续把Worker无条件多取一期伪装为公式必需；理由见现有分裂点 `src/pring_cycle/full_run_requirements.py:149`与 `src/pring_cycle/context_projection.py:2221`。

**9.2 建议输入输出：隐藏窗口细节，保留证据边界。** 输入可由模块持有窄化的证据读取依赖，取得已按目录、目标日和截止点选择的社融／GDP序列，并调用票05复核能力及GDP交付／公告核对；调用方不应再负责凑24／8个数。输出应有状态、值／单位、经济统计期、实际输入口径、两组窗口、父ID、公式版本和结构化失败详情，替代当前松散三元组；现有信息来源为 `src/pring_cycle/context_projection.py:2152`、`:2332`、`:2390`。

**9.3 建议把计算结果与保存动作分开表达。** 信用模块产生派生结果及血缘，通用派生记录仓库负责稳定身份和保存，投影／单日汇总层明确决定是否持久化；这能使需求、差分、连续性和vintage规则直接测试。现有真假持久化两条路径重复哈希算法，可作为小范围共用能力收敛，但不应顺带改变补算行为，见 `src/pring_cycle/context_projection.py:1361`与 `src/pring_cycle/evidence.py:1226`。

**9.4 不该收入信用模块的内容。** TuShare网络请求与获取失败分类、通用来源选值排序、原件家族解析、交易日历、运行生命周期、缺口展示类别、过热／信用响应状态、报告及留存均应留在各自模块。信用模块只负责表达自己需要什么输入、怎样解释和计算、为何不能计算、结果依赖什么；这些边界分别已有实现，例如 `src/pring_cycle/worker.py:1863`、`src/pring_cycle/evidence.py:1397`、`src/pring_cycle/freshness.py:978`及 `src/pring_cycle/domain/macro.py:109`。

**10.1 政策利差有“需求＋解释＋血缘”，但不是固定长回看。** 规划声明DR007与OMO利率各1期，计算选最新可用DR007和不晚于其日期的政策利率，复核后相减乘100并记录两个父ID。政策利率可能是窗口外现行基准，因此实际需求不是简单“同一天两点”，见 `src/pring_cycle/full_run_requirements.py:129`、`src/pring_cycle/context_projection.py:932`、`:948`、`:967`。

**10.2 贷款结构最接近信用脉冲的累计差分形状。** 它按公式版本选择存量差或累计增量差，按借款人／期限分组，要求相邻月份，新版1月直接采用本月累计，并记录实际父ID。规划仍固定要求2期，而1月计算只需1期，这是另一处需求与计算规则分散，见 `src/pring_cycle/full_run_requirements.py:130`及 `src/pring_cycle/context_projection.py:1080`、`:1114`、`:1129`。

**10.3 OMO到期推算也是派生，但需求比期数复杂。** 新版从历史投放日加7个自然日，再顺延至已知交易日，优先使用显式到期量，计算净投放并把操作输入及日历证据纳入血缘。规划却只声明OMO金额1期，没有完整表达7日回看与日历依赖；见 `src/pring_cycle/full_run_requirements.py:131`、`src/pring_cycle/context_projection.py:834`、`:885`、`:1186`、`:1241`。

**10.4 PMI价差具有同月输入解释和血缘。** 订单－产成品库存、生产－订单分别找父成员共同最新月份，再做差并记录具体父声明；它们只需同月输入，不需要24／8式长回看。证据为 `src/pring_cycle/full_run_requirements.py:132`、`src/pring_cycle/context_projection.py:1017`、`:1041`、`:1060`。

**10.5 实际库存近似与美债期限利差也有共同结构。** 实际库存要求名义库存与PPI同月、价格调整分母为正，新版会回找库存月份的PPI；美债2s10s取两个期限共同最新日期并保留父ID。证据为 `src/pring_cycle/full_run_requirements.py:137`、`src/pring_cycle/context_projection.py:2080`、`:2115`、`:983`，说明可以共用派生结果／血缘存储类型，但各指标需求算法差别明显。

**10.6 不宜据此立即建立万能派生引擎。** 现有派生至少包含固定长窗口、年内差分、事件现行基准、日历推算、同月／同日对齐等不同机制，适合先建立信用专用深接口，再从第二个真实迁移案例提取共性。ECB交叉汇率更是ADR明确规定的例外，虽然经过计算，仍保存为单条来源声明，不能强行纳入派生观测模块；见 `docs/adr/0015-computed-cross-rate-stored-as-one-source-claim.md:7`。

**11. 指定提交的核对结论。** `174d282`修复回看起点并补投影缺口，`ef4a20e`记录分流与实施；`a8455c4`先按共同回执放行GDP，`403cba4`再改为按共同交付的数值匹配，`87c82d2`仅记录验收成功。当前应以最后一种规则为准，文档记载的−3.93是历史验收结果，本次没有重新验证运行数据；证据为 `src/pring_cycle/context_projection.py:2448`、`.scratch/run-findings-20260928/issues/13-gdp-vintage-check-rejects-tushare.md:21`、`:25`及 `.scratch/run-findings-20260928/issues/09-credit-impulse-missing-silently.md:79`。
