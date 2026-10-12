# Codex 只读分流取证：票 02、06（2026-10-12）

结论：票 02 的漏提交确实存在，同一计划版本内可沿用现有幂等键补交；但必须补上统一截止判断，并明确“21:00”目前只是执行入口检查。票 06 的 breadth 分类缺陷存在，但两次真实运行均未触发；篮子两次均可优化掉 8 次合约请求；日历失败回退仍存在，但不能把历史网络失败说成漏日应答。

本次只读仓库及指定快照，SQLite 均以 `mode=ro` 打开；未修改文件、运行测试或业务命令、访问网络。以下源码路径省略前缀 `src/pring_cycle/`；R1＝`run-97250978e4b59b1a8d6e`，R2＝`run-b7d59b63bedca39d9d2e`；SQL 中 `:r` 分别代入两者。

**票 02**

1. **跨过 09:00 的实际条件【读码】。** 开启计划后，先要求前后检查属于同一本地日期，再判断 `previous_local < scheduled_at <= observed_local or retrying`；`retrying` 是内存中暂缓任务已到重试时间（`worker.py:200、214、216、219`）。因此并非必须在 09:00 附近检查：同日 08:59→15:00 也会提交，但跨日检查直接返回。

2. **晚启动与重启【读码】。** `run_worker` 将上次检查初始化为启动时间，暂缓状态重新置空，所以正常时钟下，09:00 以后启动当日不会自动提交；恰好 09:00 启动也不满足严格小于条件（`worker.py:138、142、143、219`）。重启会丢失检查时间、暂缓日期和重试时间，但不会删除已入库运行或幂等记录；人工提交的排队运行仍可执行（`worker.py:154、156、179`）。

3. **真实调度证据范围【快照实测】。** `SELECT count(*) FROM parent_run WHERE command_type='scheduled_full'`＝**0**；`SELECT version,enabled,start_time,p0_deadline FROM schedule_configuration ORDER BY version DESC LIMIT 1`＝**3、1、09:00、21:00**。两次验收均为 `manual_full`，所以不能用它们证明真实调度、重启补交或截止行为已验收。

4. **幂等键与重复判断【读码】。** 自动键是 `scheduled-<目标交易日>-v<计划版本>`，数据库唯一约束是 **`(command_type, client_request_id)`**，不是目标日唯一（`worker.py:232、234`；`runs.py:1227`）。重复判断及重启后使用同键会返回原运行，新的判断时间不会引发截止身份冲突，因为自动运行使用 `acquisition_window`；也不会自动重跑已经失败或中断的原运行（`runs.py:233、252、1031`）。

5. **与人工运行、计划变更的关系【读码】。** 同目标日的人工与自动运行互不合并，会产生两份运行；人工去重只检查 `manual_full`，且队列优先执行人工运行，可能挤占自动运行的截止前时间（`runs.py:266、430`）。每次 `configure_schedule` 都增加版本，所以同日关闭再开启可产生新的自动幂等键；“同键一次”不等于“目标日全局一次”（`runs.py:956、963`）。

6. **补交候选及函数范围【建议】。** 将 `submit_schedule_if_crossed` 改为按当天 `09:00 ≤ 当前时间 < 21:00` 判断，保留 `_scheduled_target` 的完整日历验证及每 10 分钟重试，成功后仍使用原幂等键；同时修改 `run_worker` 初始化逻辑、`DeferredSchedule` 注释，并缓存当天已判定结果，避免每秒重复读全部日历（`worker.py:124、175、187、241`）。已有 `RunRepository.submit` 足以支持重启去重；若要求“人工跑过就不自动跑”或“跨计划版本也仅一次”，需另外定义规则，不能视作现有幂等自然提供的能力。

7. **P0 截止的位置与真正含义【读码】。** 截止不在 `p0.py`，而在 `_scheduled_p0_deadline_elapsed`：取不可变 `run_cutoff_contract.initial_system_as_of` 的上海日期，加计划中的 21:00；冻结时间跨日不会顺延，比较符是 **`>`**，因此正好 21:00 尚未过期（`worker.py:2066、2081、2086`；`runs.py:381`）。执行入口过期即转为 `action_required`；这不是持续倒计时，已进入取数流程后没有再次检查该截止，已发布投影后的报告恢复路径也在检查之前（`worker.py:408、423、486`）。

8. **20:59 与现有截止漏洞【读码】。** 20:59 提交后若排队至 21:00 以后才进入执行，会被拦截；若此前进入执行，则可继续越过 21:00，故“补交越晚可用时间越短”准确指剩余启动窗口，并非保证在剩余时间内完成。另有现存边界：`worker.py:210` 只清除暂缓状态，没有统一拒绝截止后首次跨点提交；同日 08:59→21:01 仍可先提交，再由执行入口拒绝，补交改造应一并封住（`worker.py:219、232、423`）。

9. **ADR 核对与补写【文档＋读码】。** `docs/adr/0041-scheduled-run-identifies-previous-trading-day-next-morning.md:15、16` 规定交易日 09:00、上一交易日及日历失败暂缓，`:28` 只写“时效截止取运行时刻”，**没有写 P0 的 21:00**；这不是 ADR 明文规定了“目标日 21:00”后未更新。提交日口径见原票 `.scratch/model-rules-validation-20261011/issues/03-scheduled-run-t-plus-1.md:21、32`，运行文档已写在 `docs/development/local-runtime.md:412`。

10. **建议 ADR 措辞【建议】。** 在 ADR-0041 的“决定”中、`:16` 后补：“自动运行的 P0 执行入口截止为首次提交日北京时间 21:00，提交日取不可变初始提交时点，不随冻结截止或恢复日期顺延；当前实现仅在进入主体执行前检查，已开始运行不因跨过该时刻中止。” 若批准补交，再补“当天 09:00 后、21:00 前首次可判断时允许补交，仅补当天计划；日历不足继续暂缓，同目标日及计划版本沿用同一幂等键”，并同步 `local-runtime.md:417` 与规格 `spec.md:58`。

11. **所需测试与决策【建议，未运行】。** 改写 `tests/integration/test_worker_execution.py:843` 的晚启动不补交断言，并覆盖跨日醒来、首次/暂缓后重启、重复判断、休市、日历失败、20:59 排队过期、21:00 精确边界及执行跨截止；保留并扩展该文件 `:738、767、808、1057、1160` 和 `test_run_orchestration.py:215`。补交会新增原本漏掉的一整次完整运行，不能称外部调用增量为零；日历已有覆盖时调度额外调用为 **0**，缺覆盖每次补取 **1** 次，补交规则、是否排除人工已跑及是否要求硬性完成截止需用户决定，单纯补记现有 P0 口径无需另作领域决定。

**票 06**

12. **breadth 误分类的确切原因【读码】。** `breadth_scalars` 在“无待取日期”和“已请求但最终无可计算标量”两种情况下都可返回空元组，适配器却统一抛 `ContextObservationsMissingError("nothing_new")`（`breadth.py:306、307、319、335`；`tushare_context.py:1068`）。外层把该异常记为 `succeeded`，完整性直接取异常字段，同时让已收到回执失败；因此错误在交付完整性分类，不是异常被误记为 `source_failed`（`tushare_context.py:449、457、459`）。

13. **两次运行实际触发数【快照实测】。** SQL：`SELECT outcome,json_extract(safe_metadata_json,'$.completeness'),count(*) FROM retrieval_attempt WHERE json_extract(safe_metadata_json,'$.run_id')=:r AND json_extract(safe_metadata_json,'$.family')='market_breadth' GROUP BY 1,2`，R1、R2 均为 **`succeeded / nothing_new / 7`**。但按下条回执 SQL 查询，`stock_basic / daily / stk_factor_pro` 两次均为 **0 次**，所以“请求后空行情误分类”是 **0、0**，不能把这 14 条正常无需新增尝试算成错误实例。

14. **缺口、重试、负缓存与显示影响【读码】。** 仅把 `nothing_new` 改为 `source_empty`，两者仍是 `succeeded`，不改变失败缺口分类、重试控制或负缓存：失败分类读取 `outcome`，增量重取依据七指标实际持有日期，负缓存依据检索尝试的 `not_found/candidate_source` 等结果（`acquisition_outcome.py:73`；`freshness.py:810`；`worker.py:795、1801`）。会修正投影与页面“最近获取：已全部持有，无需新增”的误导文案；报告观察接口输入只选值、方向、状态等字段，没有直接传入此完整性标签，因此不能声称报告正文必然受影响（`context_projection.py:397、410`；`dashboard.py:1612、2480`；`reports.py:454`）。

15. **只修尝试、不改回执的候选【建议】。** 在 `breadth.py` 保留 `:307` 的全持有空返回，对实际执行取数后 `:335` 仍无标量的分支抛普通 `ContextObservationsMissingError("source_empty")`，同步修正 `tushare_context.py:1069` 注释；不要使用篮子的 `WindowAlreadyHeld` 收尾。外部调用增量 **0**、选值和缺口口径不变、无需用户决定；扩展 `tests/integration/test_attempt_classification.py:308`，同时断言尝试 `source_empty` 和回执仍失败。

16. **篮子当前请求数【快照实测】。** SQL：`SELECT a.api_name,a.state,count(*) FROM full_run_acquisition f JOIN acquisition_request a USING(acquisition_id) WHERE f.run_id=:r AND a.api_name IN ('fut_basic','fut_trade_cal','fut_daily','stock_basic','daily','stk_factor_pro') GROUP BY 1,2`；两次结果均仅有 **`fut_basic / validated / 8`、`fut_trade_cal / validated / 4`**。即每次篮子 **12 次**、无结算行情请求；这是篮子子流程的次数，不是完整运行总请求数。

17. **候选 B 的实现与调用成本【读码＋建议】。** 当前先取八品种合约，再按各交易所最远合约到期日取四份日历，最后才判断窗口已持有（`basket.py:162、175、178、200`）；可改为先取四所基准日至目标日的日历，全持有便返回，由 `tushare_context.py:243、1085` 正常收尾。此路径确实 **12→4，增量 −8**；但窗口有缺口时仍需八次合约请求及到期日前日历，若第二轮扩展四所日历，较当前会多 **最多 4 次**，所以不能宣称所有运行都无额外成本。

18. **候选 B 的日历风险与选值【读码】。** 期货日历当前仅做日期范围检查，`basket.py:188` 直接构造开闭市字典，再以四所开市日并集构造窗口；四所共同漏列某个开市日会把它排除，甚至误判全持有，SSE 严格解析修复没有覆盖这里（`tushare_context.py:1119、2519`；`basket.py:189`）。先日历方案应在快路径前校验四所逐日完整性，失败或漏日不得返回“全持有”；正常完整应答下不改变选值，但会收紧残缺日历的接受行为，且全持有时不再检验当次合约应答，需明确纳入优化验收范围。

19. **候选 B 的修复边界【建议】。** 改 `basket.py:basket_scalars`，补期货日历完整性检查，保留 `select_contract` 对到期前日历覆盖的要求及原合约选择规则；“全持有”当前只查篮子 level，不逐袖套确认，若另加袖套完整性判断应单列，不能混作性能优化（`basket.py:110、127、200`；`worker.py:2043`）。正常选值保持不变、调用增量按第 17 条；技术优化本身无需用户决定，若顺便改变袖套补算或不完整日历的领域容忍规则，则需要明确决定，测试落在 `tests/adapters/test_basket.py`、`tests/integration/test_attempt_classification.py`、`test_gap_source_repairs.py`。

20. **运行中漏日回退路径【读码】。** 漏日由 `source_adapters.py:334` 抛 `china_trading_calendar_incomplete`，`worker.py:_reach_judging_day` 捕获后记录 `unavailable`，仍冻结截止并继续；同日没有像调度入口那样每 10 分钟重试（`worker.py:2104、2109、2115`）。随后 `judging_calendar` 保留已有明确休市日，仅对未覆盖部分按工作日推定；残缺应答整体不提供覆盖，并非只回退漏掉的那一天（`trading_calendar.py:304、417、438、443、89`）。

21. **可能多算多少期【读码示例，未运行测试】。** 增量取决于失去覆盖范围中的工作日休市日，以及指标发布滞后、宽限，不是“漏一日最多多一期”；已有测试源码给出同一场景：目标 09-30、判定至 10-09，完整日历落后 **1 期**，漏日/取数失败后落后 **6 期**，多 **5 期**，缺口也从“一期沿用”变成“至少两期缺失”（`tests/integration/test_worker_calendar_gate.py:273、283、318、326、340、349`）。因此“方向保守”仅表示避免低估陈旧程度，不代表对时效、缺口展示没有实质影响。

22. **两次运行及历史发生情况【快照实测】。** `SELECT run_id,document_json FROM full_run_gap_plan WHERE phase='judging_calendar' AND run_id IN (:r1,:r2)` 只返回 R1 的 **1 次 `fetched`**；回执连接查询显示 R1 成功取得 10-09～10-12 日历，R2 **1 次 referenced、0 次 judging_calendar 请求**，两次记录的漏日回退均为 **0**。全快照按 `json_each(document_json,'$.fetches')` 汇总该阶段为 **fetched 3、unavailable 1**，唯一失败属于 `run-766f5d612930bda6f251` 的 SSL `URLError`，不是漏日；该运行核心时效确实记录 `periods_behind=6`，不能把所有日历回退都说成“从未发生”。

23. **人工入口条件与概率【读码＋记录核对】。** 实际触发条件比票面完整：CLI 未给 `--target-date`，`SseCalendar.around(启动日)` 返回空，且没有 TuShare token；“残缺存量被剔除”只是存量不覆盖的一种原因，空库或覆盖过期也会触发（`cli.py:321`；`freshness.py:621、625`）。有 token 时补取异常会向外抛，不会走这个无 token 回退；两次验收均显式指定目标日，故该入口触发 **0 次**，但快照没有历史凭据与全部 CLI 参数，无法据此估算日常发生概率（验收记录 `.scratch/model-rules-validation-20261011/acceptance-20261012.md:91、329`）。

24. **运行中改阻断的候选与后果【建议】。** 在 `_reach_judging_day` 补取后重新确认覆盖，仍不足则先记录原因再转 `action_required`，并让 `judging_calendar` 对该执行路径拒绝工作日替代；改动集中于 `worker.py`、`trading_calendar.py`。正常完整日历调用增量 **0**，失败后立即阻断也不新增请求，但该轮已做的取数成本仍在，且不再发布原本可降级完成的投影/报告；若选择自动重试则每次增加 **1 次日历调用**，这涉及可用性与准确性取舍，需要用户决定。

25. **人工入口改阻断的候选与后果【建议】。** 将 `freshness.py:625` 的空 `TradingCalendar()` 改为明确的日历不可用错误，仅阻止无法可靠推导目标日的提交，仍允许显式 `--target-date` 进入原有后续校验。调用增量 **0**，会避免节假日被选成目标日，同时取消缺凭据、缺日历情况下的自动选日便利，需要用户决定；补充 `test_freshness_contract.py`、`test_trading_calendar.py` 及 CLI 测试，覆盖完整存量、残缺存量、无 token、有 token 补取失败和显式目标日绕过。
