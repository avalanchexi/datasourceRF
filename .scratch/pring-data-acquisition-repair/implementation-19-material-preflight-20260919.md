# #19 独立材料预检：实施起点（2026-09-19）

基线 c5f0796：默认全套1848项、两项后续验收已完成；本切片是新改动，不借用旧通过数。

公开边界沿用既有 CLI。新增 tests/models/test_material_preflight.py 首条反例：通过完整合法合成候选准入后不导入回放输入，调用 model-input-preflight --model ... --start 2026-03-09 --end 2026-08-28 --json；应列出独立日历、融资、估值等具体缺件，绑定模型和manifest身份，保持模型与激活历史不变。

实际RED：1 failed / 2.65秒，pytest退出1；失败是CLI命令不存在（argparse SystemExit2），候选准入已通过。原始日志 verification-19-material-preflight-red-20260919.txt。仅新增测试，尚未实现产品命令，默认发现新增此失败项；没有启动重型任务。

已核实复用边界：

- model_evaluation.context_replay_gaps仅认证字符串检查，不能当作完整预检。
- ModelInputSelector公开select已有真实原件/规范化/资格/维度检查，不另造宽松规则；需明确PUBLIC历史截止及必要窗口，不能只验最后一天。
- full_run_requirements.formula_requirements提供派生所需窗口与差分基线；FullRunRetrieval._plan会跳过operational_evidence，且为SYSTEM运行计划，不直接冒充候选PUBLIC预检。
- evaluate_context_replay含覆盖、选值、父项和逐日上下文求值，不能简单运行整段回放后换个名字当便宜预检。完整目录、独立日历、维度、原件、双点时和派生父项全部是最终范围。

接续：实现只读材料诊断的首个纵向行为，再补有效材料对照与坏原件、缺维度、PUBLIC未知/未来修订、缺派生父项反例；接到校准/回放之前，缺件先返回而不改生效指针。测试材料保持独立可变运行库，最终按影响进行必要生命周期和同版本完整验证。本票预检条件仍未勾选；真实来源认证及完整候选原依赖不变。

## 当前纵向进展

整合树新增material_preflight.py并接入只读model-input-preflight CLI；完整候选缺材料反例1 passed / 2.36秒。随后通过公开融资采集建立合法原件/损坏原件对照，原件损坏漏报实际RED：1 failed、2 passed / 5.75秒；接入ModelInputSelector.select的真实原件与维度守卫后3 passed / 5.55秒。原始日志见本目录inventory、original-red、original-green三份记录。Ruff/格式已通过。

当前仅缺件清单、目标日选值和独立日历诊断；状态显式checks_complete=false，不能返回ready。历史全窗口逐期校验、双点时、派生父项及日历精确区间仍待实现；pending_checks保留，#19预检不勾选。源码未提交，也未接入生命周期调用或跑新重型；旧c5f0796全套不覆盖新CLI。下一步先用历史中间期缺件、未来/未知PUBLIC、必要维度和父项反例驱动扩展，再有效材料正例与整体审查。当前原件日志已归档两树，修改只在整合树。C盘实测14.53GiB。

## 历史窗口纵向进展

独立日历经公开核心适配器取得，融资末日有值但8/27缺件的3日窗口反例先RED：1 failed、1 passed / 4.43秒；逐日PUBLIC选值后5 passed / 8.83秒，缺口返回business_date，原件反例仍通过。Ruff及两源文件mypy通过。没有重型验证或提交。

重要未决：现阶段每日缺值都会列入gaps，而既有_context_coverage_gaps对部分日频上下文允许95%密度，必须在接入生命周期前统一规则，不能提高门槛；核心日历/价格规则另按原要求。全窗口仍未完成资格：预热、时效、双点时、派生父项、完整目录和范围边界待补；checks_complete=false仍保留。当前selectors按日期保存会保留多份指标序列缓存，整窗运行前应按日处理并释放，避免120份缓存叠加。下一步以20日窗口缺1日合法对照/缺2日失败反例驱动密度一致性，再补历史坏原件不能被末日健康材料掩盖。

## 覆盖率与缓存修正

20日窗口缺1日应允许、缺2日应报缺件，公开CLI对照先RED（1 failed、3 passed、3 deselected / 8.73秒）；共享metric_contracts.minimum_context_daily_observations保留既有95%向上取整公式，model_evaluation原公式改为调用同一函数。预检上下文允许合法稀疏历史但逐日复核实际最新选值，坏原件/资格不因密度容差豁免；核心价格保留完整日要求。source vintages覆盖统计仍需后续完整维度/父项审查。selectors改为每次处理一天，避免持有120份指标缓存。

当前7 passed / 13.13秒，Ruff、四源文件mypy与git diff --check通过。尚未提交/两轴复核/重型。checks_complete=false保持，必要预热、点时边界、派生父项、日历原件与范围、全目录及完整材料正例仍未验收。最新源码在整合树material_preflight.py、cli.py、metric_contracts.py、model_evaluation.py，新测试test_material_preflight.py。

## 独立日历原件与区间修正

公开核心日历获取后验证有效/坏raw/坏normalized/请求起点超范围四场景，实际RED四失败：有效收据被错误当作缺标量、坏raw未拒绝、坏normalized直接CLI退出、范围不匹配未标不可用。新增独立日历诊断包装，收据raw与normalized均读哈希校验，复用公开TushareCoreAdapter.trading_days从归档raw重新解析并对照normalized；无网络。请求端点必须被所选独立日历覆盖；坏文件返回结构化缺口而非直接退出。CN_TRADE_CALENDAR及其他运维记录不再进入标量缺件列表。

当前11 passed / 19.96秒，Ruff/格式、四源文件mypy、diff-check通过。日志calendar-red与calendar-green已归档两树。日历声明分支的原件资格、PUBLIC/系统截止语义仍须核对；当前测试仅收据路径，不能称全部日历资格已完成。checks_complete=false保持，预热、父项、完整目录与点时矩阵继续开放；尚未提交、两轴复核或新重型验证。

## 派生父项首个纵向行为

复用prepare_credit_component_pair合法公开获取材料：comparison完整父项，candidate缺2026-06社融差分基线但有旧完整窗口。CLI原预检漏报信用脉冲：1 failed / 12.88秒。每个检查日通过build_context_projection(persist_derived=False, PUBLIC)执行实际公式父项守卫，记录公式输入不可用/无血缘；无输入的公式直接列缺口，不启动回放或持久化派生。formula_documents遍历逻辑从model_evaluation提到context_replay_scope.find_formula_documents供两者共用，补齐导入。必要公式的P2父项（如GDP）不能当可选缺口，其他P2仍可选。

初版12 passed / 32秒；修正共享导入与P2分类后，最终新预检12项+既有信用脉冲公开组件反例共13 passed / 46.99秒，Ruff/格式、五源文件mypy及diff-check通过。当前仍不ready：诊断仅列公式/版本/日期，还需具体父项与缺期；预热、历史坏原件、PUBLIC未知/未来修订与SYSTEM边界、日历声明资格、完整目录/完整材料正例及生命周期接入继续开放。未提交/两轴审查/新重型验证。原v7全套不覆盖新改动。

## 父项缺期诊断细化

信用脉冲缺件结果新增missing_input_periods。既有合法完整/缺2026-06社融基线对照先RED（KeyError缺诊断字段，1 failed / 13.11秒），复用formula_requirements与preceding_periods生成当前选值窗口内的缺期后专项1 passed / 12.89秒，精确输出CN_SF_TOTAL:[2026-06]，不把额外旧窗口混入缺件。最终新预检12项全部通过/32.97秒；Ruff/格式、material_preflight类型检查与diff-check通过。

该字段只描述没有观测期次，不代表有期次就有效；资格、原件与差分相容仍由实际公式求值决定。历史坏原件/缺维度要进一步定位到父项原件而非仅列公式失败。checks_complete=false保持；点时矩阵、预热和日历声明资格、全目录/完整材料正例与生命周期接入尚未完成，未提交/两轴审查/新重型。

## 公开时间与日历取得截止

真实公开融资获取对照已知PUBLIC/原件损坏/未知PUBLIC/未来PUBLIC四场景4 passed / 7.30秒；后两者由原选值守卫正确保持缺口，无生产时间规则改动。日历late_capture对照则先RED：目标8/28、有效收据8/29取得却被拒，1 failed / 2.77秒。预检是在当前已取得材料上诊断历史PUBLIC；运维日历改按本次inspected_at取得截止（SYSTEM），经济值仍逐目标日PUBLIC，不制造发布时间。新增inspected_at输出。

最终新预检15 passed / 41.17秒，Ruff/格式、五源文件mypy与diff-check通过。日志归档两树。本批未提交、未两轴审查/重型；checks_complete=false继续保留。仍须未来修订不污染旧选值、日历声明原件资格、历史坏父项/维度的具体定位、完整目录与预热、完整有效材料及生命周期接入等验收。当前只有“当前材料上的历史PUBLIC”模式，不声明任意双截止SYSTEM回放已验证。

## 未来坏修订隔离验证

通过公开融资获取先存有效8/28材料，再存数值变化且PUBLIC为8/29的修订，确认两份raw哈希不同后损坏新原件。8/28预检不受未来坏修订污染，8/31预检实际拦截新版本，不能恢复旧值。专项2 passed / 4.12秒；修正测试循环闭包绑定及类型注解后，新预检文件17 passed / 43.09秒，Ruff/格式/diff-check通过。生产逻辑未改，本场景复用已实现PUBLIC选择守卫。

仍checks_complete=false。下一实质工作：日历声明分支的原件/资格、历史坏父项/维度定位、预热与完整目录检查，随后完整有效材料预检/生命周期接入、两轴复审与同版本必需验证。不要将17项通过当作#19预检完成；无新重型进程、未提交当前切片。

## 日历声明分支假设复核

原件关联/未关联/损坏三场景均在公开append_source_claims前置失败，原因registered_source_contract_not_implemented:CN_TRADE_CALENDAR，3 failed / 5.82秒。这不是预检RED；当前完整注册候选不能通过合法公开入口新增这类标量声明，禁止绕合同造夹具。原日志calendar-claims-red命名保留但语义明确是前置失败。

改为验证公开拒绝边界（无收据/有合法收据两场景），随后调用CLI：无收据仍缺日历、有原件收据可正常预检。当前新预检19 passed / 50.04秒，Ruff/格式/diff-check通过，无生产增量。此结论仅针对本票合法注册候选；不扩展为旧builtin/外部篡改数据库所有日历声明已认证。

下一主线历史坏父项/必要维度的具体定位、预热/完整目录、完整有效材料及生命周期接入。checks_complete=false仍保留；未提交、两轴审查或新重型。

## 历史坏父项具体定位

独立候选的2024-Q3 GDP原件损坏、末期仍完整。CLI原先已拦截公式但缺invalid_parent_claims，实际RED 1 failed / 12.92秒。父项诊断现在按现有公式必要窗口收集选中声明，批量经公开source_claim_acquisitions_many校验原件与规范化内容，精确返回CN_GDP/2024-Q3/claim_id；未参与窗口的旧声明不纳入此诊断。只在公式不可用时收集，正常公式路径不增加这轮原件读取；实际公式仍决定可用性，诊断不能替代语义校验。

专项1 passed / 12.65秒；本文件20项+既有历史父项公开组件反例共21 passed / 75.65秒。其后仅把局部period变量改名latest_period解决mypy可空类型冲突，五源文件mypy和Ruff通过；21项结果是改名前实际批次，不冒充冻结最终全套。源码未提交/两轴审查/新重型，checks_complete=false继续保留。下一步预热/完整目录与完整有效材料验证、生命周期接入；维度细节与全部公式诊断范围仍需审查。

## 公式输入预热覆盖

沿用公开准入、真实适配器传输边界和预检CLI，DR007材料仅有2026-08-28时未报告缺少前10天预热，实际RED为1 failed、1 passed / 4.81秒；从2026-08-18开始的对照已有足够覆盖。预检现返回input_warmup_missing并明确required_start=2026-08-18。将既有重放的公式预热天数表和计算共享到context_replay_scope，重放数值规则未改变；覆盖起点沿用现有重放的认证/质量/PUBLIC非空及最早期次/公开日判定。这个元数据覆盖检查不替代历史父项原件和点时选值校验，也不代表核心趋势预热已检查。

专项2 passed / 4.51秒；首次相关24 passed / 66.03秒后，mypy要求显式排除可空发布时间，完成类型窄化。最终同一源码的预检22项及既有覆盖2项：24 passed、19 deselected / 69.18秒，句柄36655退出0；五源文件mypy、Ruff、格式及diff-check通过。四份warmup原始日志两树归档。C盘实测14.51GiB，没有重型任务在途，无需清理。

预检仍checks_complete=false，未提交/两轴审查/新重型；原c5f0796全套不覆盖本批。后续须补核心趋势历史范围/维度覆盖、完整有效材料正例和生命周期接入，检查完整目录/全公式诊断再给ready结论。真实候选及来源依赖仍开放。

## 核心历史输入前缀

本轮核对evaluate_history确认：核心求值遍历绑定history_input_start以来的PUBLIC输入前缀，不只取报告期最后一点。通过公开核心适配器和append_source_claims构建三个核心各两日材料，设置前一日债券缺失、前一日债券PUBLIC延迟两反例及完整对照。第一次三例均在准入前失败claim_acquisition_not_validated，因为测试available_at误用了received_at；这属于夹具前置错误，不是产品RED（原core-history-red日志保留，3 failed / 5.59秒）。改为真实receipt.validated_at后，实际RED 2 failed、1 passed / 6.27秒。

预检增加核心历史前缀检查：复用求值的model_history_input_start和CoreInputValidator，逐既有核心观测日期的PUBLIC截止核对三核心前缀选值/正值/资格/原件，返回core_history_input_missing或core_history_original_invalid及metric_id/period/首次失败business_date/claim_id。重复故障按指标、期次、声明和原因去重；完全无输入的来源仍由库存检查报告。只核材料，不计算趋势结果。专项3 passed / 6.06秒。

最终新预检及既有历史预热/晚修订/不合格旧版本相关回归：36 passed、11 deselected / 73.16秒，句柄19882退出0。五源文件mypy、Ruff、格式及diff-check通过。四份core-history原始日志归档两树。C盘14.50GiB，无重型在途。

仍checks_complete=false：核心历史日期目前与既有求值一样从已观察序列联合取得，不能据此声称独立日历证明了所有预热日期；完整有效材料正例、维度/全目录覆盖、全公式诊断和生命周期接入仍需完成。当前改动未提交/两轴审查/新重型；c5f0796旧版本全套不替代本批最终验证。

## 独立日历识别核心共同历史缺口

新增公开输入场景：三个核心都缺少2026-03-06，但各自仍有3/5及报告日8/28的合法输入；独立日历原件保留报告120日之前的这一天。原预检只取行情日期联合，实际RED 1 failed / 3.02秒。现在在原件哈希及重解析一致后保留history_dates，并与核心历史日期合并检查；报告120日裁剪不再丢弃已验证的预热日期。专项4 passed / 7.32秒；最终新预检及既有历史行为相关37 passed、11 deselected / 75.25秒，句柄14879退出0。五源mypy、Ruff/格式/diff-check通过。原件本身未覆盖的更早区间仍不能凭此宣称已证明，checks_complete=false保留。

已启动当前版本完整隔离输入准备，未启动校准/激活/全套。监督句柄68446，子进程2374789，目标/tmp/datasourceRF-preflight-inputs-20260919，profile=acquisition-repairs；输入身份先保存，结束再比对，C盘4GiB停止保护、30分钟上限。监督和日志为verification-19-preflight-input-preparation-20260919.{json,txt}，运行状态必须以实际句柄/进程终态核实，禁止重复启动。启动C盘14.50GiB。当前源码/构建输入冻结；下一步取得合法输入准备终态后运行预检完整路径，依据真实缺口完成实现，而非先运行昂贵校准。

### 完整输入准备等待核验

续接轮已实际poll68446并以ps核2374789仍Rs，最近7分48秒/约289MiB RSS；只读查库确认commodity_basket已有59条validated材料，C盘14.50GiB，准备未终态，未重复启动。当前没有修改冻结源或开始校准。后续只读预检driver已写入/tmp/datasourceRF-complete-preflight-20260919-driver.py并通过compile语法检查，尚未启动；归档副本verification-19-preflight-complete-inputs-driver-20260919.py。它要求准备finished/exit0/输入未变，执行当前CLI整窗3/9–8/28预检，比较运行前后_runtime_contents（排除SQLite侧车）及material_identity，监督C盘余量/30分钟上限，输出complete-inputs-result/terminal/runtime-before三件。语法检查不是执行通过，仍须先取得准备实际终态后启动一次。

## 当前版本完整输入准备终态与整窗预检启动

准备监督68446实际退出0，子进程2374789已不存在；elapsed_seconds=1061.0516737049911（约17分41秒）、reason=null、frozen_inputs_unchanged=true。当前新候选model-reviewed-985c03cfd1d6a2a76f99f216d42efaba0a62a029e8b56722712b0ef00b40e710，未校准/激活。末次C盘14.49GiB。原始准备json/txt已两树归档，这是真实冷准备成本，不宣称3分钟目标已覆盖重型输入准备。

整窗只读预检已启动一次：监督会话24054，CLI子进程2385608，目标2026-03-09至2026-08-28。监督输出verification-19-preflight-complete-inputs-terminal-20260919.json，CLI结果complete-inputs-result-20260919.json，运行前内容哈希complete-inputs-runtime-before-20260919.json。开始前已确认准备身份与当前身份相同；终态还要核frozen_inputs_unchanged及runtime_contents_unchanged。当前仍运行，结果文件尚空不是失败证据；继续poll24054，不重启。源码继续冻结。

已读代码确认两个可能的后续提效落点（尚未实施或验证收益）：材料构建逐日persist_commodity_basket各自开启读取作用域；独立preflight没有像evaluate_context_replay一样包住整个只读循环的共享读取作用域。shared_read_scope允许嵌套复用且仅可缓存作用域内不改变的输入；若优化须验证跨截止、坏原件和新增派生记录仍正确。先取得当前完整预检结果，不为猜测中断本次必要验证。

## 整窗预检主动中止及单次读取作用域

旧预检24054已真实终态：监督退出1，CLI2385608已不存在、exit_code=-15，elapsed_seconds=565.7334794499911。这是根代理确认命令身份后主动SIGTERM，原因是预检遗漏现有重放的shared_futures_input_reads，决定先修复重复读取；不是产品断言失败、观察超时或成功验证。监督reason=null仅表示其自身没有触发保护，不能误解为无中止原因。frozen_inputs_unchanged=true、runtime_contents_unchanged=true、changed_runtime_files=[]。结果stdout为空，没有完整gaps结论。原terminal/result/runtime-before三件两树归档。

运行期间/proc/2385608/io两次实际rchar从14160897853增至14640942280，约20秒增加480044427字节；这只说明进程读取活跃，不足以归因全部原件IO。strace附加因环境ptrace权限拒绝，未取得追踪，不升级权限。当前候选真实目录59项（P0=6/P1=42/P2=11）；#27已批准删除两项黄金，_admission_catalog按迁移处理，所以不要按旧票61项硬编码误报缺件。该计数仅清单，不是59项材料全部通过。

新增跨调用守卫：公开CLI第一次读取合法融资材料，破坏原件后第二次必须报告input_selection_missing。优化前该保护1 passed / 2.87秒，不冒充产品RED；性能问题的证据是上述未完成整窗运行。预检入口现包一层shared_futures_input_reads，只在一次不变输入检查中复用，返回后释放。实际全新预检文件27 passed / 78.08秒（82382退出0）；五源mypy、Ruff、格式/diff-check通过。未测得完整耗时收益，不能宣称提速倍数。

源码已改变，旧准备identity不匹配新版本，禁止将旧材料作为最终同版本缓存命中；仍checks_complete=false。下一步可先验证完整输入构建末尾的逐日商品篮子循环共享读取是否安全（输入早已捕获，循环只生成派生材料；已有公开注册商品篮子/坏原件/修订回归可复用），再准备新版本完整输入并测整窗预检。此建议尚未实现。随后须完整材料正例/维度及全目录审计、生命周期接入、两轴审查、同版本必需验证；未提交当前WIP。

## 材料构建循环读取复用：完整冷准备实测

新增公开商品篮子保护：同一shared_futures_input_reads内连续persist 3/9及3/10，逐日检索选中的claim_ids等于新生成集合、值分别1033.3333333333333与1012.6666666666666，两日声明不混用；离开作用域损坏父原件后，新作用域必须拒绝，恢复后再次可用。既有能力验证1 passed / 3.92秒，不冒充产品RED。构建函数import_commodity_basket现仅在全部输入捕获及审查绑定完成后，共享最后120日派生结果循环的读取；循环没有新增期货输入。

实际相关回归tests/models/test_registered_commodity.py与test_material_preflight.py共37 passed / 134.04秒，41304退出0；Ruff、格式与diff-check通过。生产代码本轮未再改，上轮五源mypy仍针对同一生产内容通过。已归档guard/related日志和v2两driver。

v2新完整输入准备48166退出0，子进程2396565终态，315.33635828399565秒，reason=null，frozen_inputs_unchanged=true。原准备1061.0516737049911秒。本次两记录从17分41秒降至5分15秒；输入文件、profile、依赖与配置hash相同，code_hash及builders随已说明修改变化，未控制全部机器噪声，不外推整套或业务提速倍数。通过公开EvidenceRepository.metric_series对比，两侧120日期、960条篮子及七分项的PUBLIC值/维度/状态完全一致，见verification-19-builder-read-scope-equivalence-20260919.json；这不是两边模型/父项id相同的声明。

新输入路径/tmp/datasourceRF-preflight-inputs-20260919-v2。v2整窗预检已启动一次：监督会话52884，CLI2400111；driver=/tmp/datasourceRF-complete-preflight-20260919-v2-driver.py。看verification-19-preflight-complete-inputs-terminal-20260919-v2.json/result对应文件，当前真实ps仍Rs（约50秒，RSS约2.67GiB），没有终态。C盘14.52GiB，保持源码/材料冻结；继续poll52884，完成后核状态、gaps及runtime_contents_unchanged/frozen_inputs_unchanged，不重复启动。checks_complete=false仍保留，当前切片未提交/两轴审查/最终全套。

## v3 整窗预检终态与成本归因

v2 整窗预检实际已终态（监督退出 0、179.99 秒、两项 unchanged），结果为 `independent_calendar_unavailable`、`checked_business_dates` 仅 2026-08-28，不是完整窗口结论。随后 v3 输入准备退出 0、349.52 秒、`frozen_inputs_unchanged=true`，候选仍为 `model-reviewed-a30abe0b…`。

v3 整窗预检启动一次即被 30 分钟观察上限主动中止：`exit_code=-15`、`reason=preflight_time_limit`、`elapsed_seconds=1830.30`，结果文件 0 字节，无 gaps 结论。`frozen_inputs_unchanged`、`software_inputs_unchanged`、`runtime_contents_unchanged` 均真，`changed_runtime_files=[]`，`imported_from` 为整合树 `material_preflight.py`。该驱动现按[软件输入清单切片](implementation-22-software-input-identity-20260919.md)分别绑定软件与材料身份。

中止后未重跑同一命令，改以有界实验归因，结论见[整窗成本诊断](diagnosis-19-preflight-window-cost-20260919.md)：单日 123.73 秒中 `ModelInputSelector.select` 占 108.02 秒，`CN_COMMODITY_EX_HOG_BASKET`（53.99 秒）与 `CN_COMMODITY_SLEEVE_CONTRIBUTION`（53.33 秒）两项即 107.32 秒，来源是每次 select 重新读取并指纹比对整批不变的商品原件；`_core_history_gaps` 12.51 秒整轮只一次。120 天外推约 3.6 小时，仅说明量级。

下一步在 #19 内以重复原件校验的失败反例驱动修复，保留跨截止选值、坏原件拒绝与离开共享作用域后的既有守卫；修复后重测单日与短窗成本，再谈整窗。`checks_complete=false` 保持，本票预检条件仍不勾选，未提交、未两轴审查、无新重型在途。

## 当前版本整窗预检首次完成（2026-09-20）

本轮源码（含期收窄修复与评审修正）下重新准备输入：监督 2797814、子进程 2797875，exit 0、277.12 秒、`frozen_inputs_unchanged=true`，新候选 `model-reviewed-eede5cf46a3ec3bc1d70b71bace3a4993ee32c7cc240a3e05990525fefa6dad1`，路径 `/tmp/datasourceRF-preflight-inputs-20260920-v4`。

整窗预检（2026-03-09 至 2026-08-28）监督 2800814、CLI 2800933，**exit 0、310.18 秒、reason=null**，`frozen_inputs_unchanged`/`software_inputs_unchanged`/`runtime_contents_unchanged` 均真，`changed_runtime_files=[]`。收据 `verification-19-preflight-complete-inputs-terminal-20260920-v4.json`，结果 62733 字节。

**这是该路径第一次真正跑完**：v1 主动中止于 565 秒，v2 因 `independent_calendar_unavailable` 只检查 1 天，v3 撞上 30 分钟观察上限无结论。本次检查 120 个交易日，独立日历 available、120 日，必需 gaps **0**，可选 gaps 130。

**「必需 gaps 0」必须加两条限定**（2026-09-20 规格轴复核指出，已逐条核实代码属实）：

1. **两项 P0 根本不参与判定**。`material_preflight.py:101-106` 按 id 硬编码跳过 `CN_TRADE_CALENDAR`、`CN_RELEASE_SCHEDULE`、`SOURCE_OBSERVED_AVAILABILITY`。日历另有专项检查，但后两项实为 **P0 / awaiting_source_certification**，材料全缺也不产生任何条目。它所仿照的 `full_retrieval.py:213-220` 仍会输出 `{"metric_id": ..., "status": "operational_evidence"}` 保留逐项可见性——「P0 运维证据不伪装标量」不等于「从清单里消失」。
2. **点时在密度维度未生效**。`material_preflight.py:152-163` 统计 `observed` 时只要求 `public_available_at is not None`，**从不与该 business_date 比较**。故某日频指标若 120 天数据全部在窗口结束后才发布，`daily_coverage_missing` 仍为空；下方逐日 `select` 只覆盖最新期次，补不上这个洞。

因此该结论的准确表述是：**在当前已实现的检查范围内**，这份合成材料的必需缺口为 0。它不覆盖上述两项 P0，也不覆盖密度的点时约束。

可选缺口全部是已知外部阻塞，无软件缺陷迹象：10 项来源材料缺失（`CN_USDCNY_CENTRAL_PARITY`、`CN_USDCNY_ECB_REFERENCE_CROSS`、`CN_USDCNY_CLOSE_1630`、`EIA_BRENT_RBRTE`、`EIA_WTI_RWTC`、`UST10Y_NOMINAL_YIELD`、`UST2Y_NOMINAL_YIELD`、`CBOE_VIX_INDEX`、`NASDAQ_SOX_INDEX`、`UST_2S10S_SPREAD`），以及 `UST_2S10S_SPREAD` 因父项缺失在 120 天每天各报一次 `formula_inputs_unavailable`。

**外推更正**：先前据单日约 14 秒边际成本外推「120 天约 28 分钟」，并据此把观察上限从 30 分钟调到 60 分钟。实测 310.18 秒，边际约 2.5 秒/天——线性外推高估了，因为收窄后每天族校验只覆盖当日声明，`claims_checked_once` 与共享读取作用域跨天摊薄了大部分成本。该次调参事后看并无必要；记录在此以免后人重复这个高估。

**边界**：本次运行的是隔离生命周期的合成准备输入，不是真实采集。必需 gaps 为 0 只说明**这份材料**在整窗上无缺口，不代表真实候选已就绪，也不代表来源认证完成。`checks_complete=false` 保持，`pending_checks` 仍为 calendar/originals/dimensions/point_in_time/parents 五项，#19 预检验收条件继续不勾选。
