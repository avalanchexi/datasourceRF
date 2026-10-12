# Codex 只读分流取证：票 01、08（2026-10-12）

结论：票 01 的 **34 天过时空值属实，但全窗口空值总数是 44 天**；第二次运行的目标日结果正确，回溯也未被这 34 天误触发。票 08 的成本上限和测试缺口基本属实，但规格是漏写日历成本，不能直接认定实现违反“最多 15 次核心请求”。

本次仅读取仓库与指定快照；SQLite 使用 `file:<指定路径>?mode=ro`，临时排序放在内存；未修改文件、运行测试或业务命令、发起网络请求。以下“实测”仅指快照 SQL 查询，“读码”不代表重新运行验证。

**票 01**

**1. 最新评估与空值分布**

1.1 **【实测＋读码】**窗口为 2026-04-13～2026-10-09，共 **120 天**；`last_confirmed_stage=NULL` **44 天**，`stage_iii` **76 天**，无其他值。生产选择方式是按日期分组，依次取 `system_as_of` 最新、同截止时有 `corrects` 优先、`assessment_id` 降序，**不遍历 `corrects` 链，也不先过滤正式阶段**；依据 `src/pring_cycle/projections.py:219`。

复核 SQL：

```sql
WITH ranked AS (
  SELECT target_business_date AS day, document_json,
         ROW_NUMBER() OVER (
           PARTITION BY target_business_date
           ORDER BY julianday(system_as_of) DESC,
                    json_extract(document_json,'$.corrects') IS NOT NULL DESC,
                    assessment_id DESC
         ) AS rn
  FROM p0_assessment
  WHERE target_business_date BETWEEN '2026-04-13' AND '2026-10-09'
)
SELECT json_extract(document_json,'$.last_confirmed_stage') AS stage,
       COUNT(*) AS days, GROUP_CONCAT(day) AS dates
FROM ranked
WHERE rn=1
GROUP BY stage;
```

1.2 **【实测】**票面所指的 **34 天全部为空**，日期如下，均为 2026 年：

- 08 月：14、17、18、19、20、21、24、25、26、27、28、31。
- 09 月：01、02、03、04、07、08、09、10、11、14、15、16、17、18、21、22、23、24、28、29、30。
- 10 月：08。

这 34 条最新评估全部属于第一次运行 `run-97250978e4b59b1a8d6e`、全部标记 `core-history-v0002`；查询是否有其他评估的 `$.corrects.assessment_id` 指向它们，结果 **0 条**，不存在被遗漏的后继更正。

1.3 **【实测】**其余 **86 天**中，04-13、04-14、04-15、04-16、04-17、04-20、04-21、04-22、04-23、04-24 共 **10 天为空**；04-27～08-13 的 **75 个交易日**及目标日 10-09 均为 `stage_iii`。按“当天正式阶段，否则此前最新正式阶段”对最新评估重新作 SQL 对照，结果为：正确空值 **10**、正确 `stage_iii` **76**、应为 `stage_iii` 却为空 **34**；因此不能把全部 44 个空值都算作本票缺陷。

**2. `_backfill` 是否会自行修复**

2.1 **【读码】**对已有汇总，选择条件确实没有依赖历史变化检查，但也不只是版本比较：本次 `basis` 必须非空、已存版本与之不同、该日未被记为该版本下“无法更正”；无汇总的历史日另行补算，目标日不在此循环内。依据 `src/pring_cycle/day_summary.py:349`、`:355`、`:359`、`:369`；`basis` 的成立条件是三核心在窗口首日均达到测量门槛，见同文件 `:389`。

2.2 **【读码】**在现行代码、同一口径、这些日期继续作为历史日的前提下，这 34 天会一直跳过，原料变化本身也不会触发修复。票面“之后永远不会更正”应限定上述条件：改变口径、改实现或将某日作为目标日重新汇总，均可能产生新版本；否则只能等其移出留存窗口。

**3. 计算依赖、不同步原因及影响**

3.1 **【读码】**历史日发布前，查询该日之前所有仍在库的日期之最新评估，再取最近 `event_kind='formal'` 的 `current_stage`；当天有正式阶段时，以当天阶段覆盖此前阶段。依据 `src/pring_cycle/day_summary.py:483`、`:547`，`src/pring_cycle/projections.py:346`、`:356`，`src/pring_cycle/p0.py:130`；因此依赖的是此前评估的 **`current_stage`**，不是此前评估存下来的 `last_confirmed_stage`。

3.2 **【实测＋读码】**第二次运行更正前 85 天后，其中 **67 天**出现 `stage_iii`，最后一天为 **08-03**；但后面的 34 天已是 v0002，被 `_backfill` 跳过，已发布字段不会自动联动更新。第二次目标投影内冻结的 `stage_history.events` 也实测为 **120 条、44 空／76 stage_iii**，所以问题同时存在于最新评估和该投影的历史事件中；依据 `src/pring_cycle/p0.py:261`。

3.3 **【实测＋读码】**目标日不受此次过时空值影响：补算结束后重新查此前正式阶段，取得 08-03 的 `stage_iii`，目标日评估、总览、报告均为该值。回溯只在“目标日无正式阶段且上述查询也为空”时执行，因此第二次不触发；依据 `src/pring_cycle/day_summary.py:276`、`:283`、`:285`，第二次运行 `full_run_gap_plan WHERE phase='core_lookback'` 为 **0 行**。

3.4 **【读码】**窗口开头 10 天为空符合当前实现：逐日补算不单独回溯，目标日回溯结果也不写回历史评估；即使第一次回溯找到了窗口前的阶段，它仍只作为投影上的回溯结果。依据 `src/pring_cycle/p0.py:225`、`:239`、`:250`；若要求补齐这 10 天，是另一项领域行为变更。

**4. 页面与报告展示位置**

4.1 **【读码】**阶段历史页确实逐行显示这 34 天的“上一确认 尚无”：页面取最新评估的入口是 `src/pring_cycle/web.py:498`，列表构建为 `src/pring_cycle/dashboard.py:670`、`:690`，字段读取与文案为同文件 `:1850`、`:1871`。首页读取当前总览的上一确认阶段，位置为同文件 `:190`，此次显示的是正确的目标日 `stage_iii`。

4.2 **【实测＋读码】****报告没有为这 34 个更正日逐日生成“上一确认阶段”展示。**查询 `report_snapshot` 与这 34 个最新 `projection_set_id` 的关联数为 **0**；报告取本报告投影的总览值，见 `src/pring_cycle/reports.py:253`、`:256`，阅读页显示位置为 `src/pring_cycle/dashboard.py:2396`，第二次目标日报告实测为 `stage_iii`，不能把阶段历史页的问题直接说成目标日报告错误。

**5. 修复候选与推荐**

5.1 **【方案 A：升级核心历史 basis，读码推演】**将 v0002 升级，复用现有更正路径；主要涉及 `day_summary.py`、更正回归用例和规则文档，外部调用增量 **0**，不需 schema 迁移，但需运行时追加历史更正。当前快照会选中 **119 个历史日**，不只 34 天：重算核心，上下文是否重算仍由原有留存判据决定，选值算法不变，但重新选取和计算的结果不保证只改上一确认阶段。

5.2 **【方案 A 的风险与规模，读码推演】**单改常量虽小，可靠实施估计涉及 **3～6 个文件、约 100～250 行含测试与文档**；它把“历史依赖修复”伪装成“核心历史口径变化”，还会使旧 basis 的无法更正记录失去拦截作用，需用户决定这种扩展是否可接受。另有具体风险：85 天已有 `core_only` 投影的上下文是空的“未重算”文档，`context_details_held()` 对无引用集合返回真，再次升级可能走整日重算；依据 `src/pring_cycle/p0.py:75`、`src/pring_cycle/projections.py:285`、`:295`、`src/pring_cycle/day_summary.py:425`，不能把它当作无副作用的一行修复。

5.3 **【方案 B：追加仅修复上一确认阶段的版本，推荐】**在 `day_summary.py` 补算后检查历史依赖，在 `projections.py` 查询依赖并追加版本，在 `p0.py` 增加专用更正原因／范围，`worker.py` 记录计数，`dashboard.py` 显示对应原因。依据最新正式阶段历史计算应有值，只有与已存值不一致才追加；保留原核心、宏观、库存、确认度和证据引用，外部调用增量 **0**，不重算核心或上下文，不改变选值、趋势或阶段映射规则。

5.4 **【方案 B 的规则、迁移与规模】**依赖标记可存现有评估 JSON，例如所依赖的正式阶段评估 ID／日期及修复规则版本，无需 schema 迁移；对旧文档首次执行一次值比较，当前快照应只追加 **34 个**修复版本。需用户明确扩展“同口径已汇总不再重算”的例外，但按此设计不改变其他领域规则，旧评估、投影、报告仍保留且页面不现场计算；估计 **5～8 个生产／测试／文档文件、约 200～450 行**，并须同步新投影中的总览与历史事件，不能只改评估字段。

**票 08**

**6. 回溯触发条件与真实成本**

6.1 **【读码】**每次目标日汇总在补算完成后，若当前正式阶段为空、此前最新有效评估中也无正式阶段，就调用回溯；没有跨运行缓存，`record_first_outcome()` 只是记录首次结果，不阻止再次调用。依据 `src/pring_cycle/day_summary.py:283`、`src/pring_cycle/worker.py:2210`、`:2221`、`src/pring_cycle/full_retrieval.py:1057`。

6.2 **【读码】**生产默认最多回溯 **5 年、15 次核心请求＋5 次 `trade_cal` 请求**，全部串行，找到即停，失败提前结束；每年按日历为搜索下界向前准备 `history_required-1`，当前即 **139 个交易日**。依据 `src/pring_cycle/stage_lookback.py:36`、`:105`、`:109`、`:117`、`:122`；此上限针对一次回溯调用，不是整次运行全部取数。

6.3 **【实测】**回溯成本应查下面的关联，不能直接统计 `retrieval_physical_request`：

```sql
SELECT f.run_id, a.api_name, COUNT(*) AS requests,
       ROUND(SUM(
         (julianday(a.received_at)-julianday(a.started_at))*86400
       ),3) AS request_seconds
FROM full_run_acquisition f
JOIN acquisition_request a USING(acquisition_id)
WHERE f.phase='core_lookback'
GROUP BY f.run_id, a.api_name;
```

| 运行 | 核心请求 | 日历请求 | 请求记录耗时合计 | 回溯结果 |
|---|---:|---:|---:|---|
| 第一次 `run-97250978e4b59b1a8d6e` | 3 | 1 | **6.973 秒** | 回溯 1 年，找到 2026-04-10 的 `stage_iii` |
| 第二次 `run-b7d59b63bedca39d9d2e` | 0 | 0 | 无回溯请求耗时 | 未触发 |

6.4 **【实测】**第一次按 API 分别为：`trade_cal` **1 次／1.953 秒**，`index_daily` **2 次／3.325 秒**，`fut_index_daily` **1 次／1.695 秒**；从首条请求开始到最后一条验证结束为 **7.045 秒**。这是回执时间口径，不能等同纯网络耗时或包含趋势计算的完整回溯耗时；快照未提供独立覆盖全部回溯计算的计时区间。

6.5 **【实测】**两次运行的 `retrieval_physical_request` 总行数分别为 **56、54**，但与 `phase='core_lookback'` 的 acquisition 关联均为 **0**；第一次对应的 `full_run_acquisition` 则有 **4 条 validated 回执**。因此该表关联不到回溯不能解释为“没发请求”，也不能把两次运行总行数的差额当作回溯请求数。

6.6 **【实测＋读码】**第二次不触发是因为更正后已有 08-03 的正式阶段，与是否修复后面 34 个空值无关。今后若长期处于非典型组合／核心不可用，并且正式阶段全部移出留存窗口或被更正为空，则每次符合条件的运行都会再回溯；同目标日重跑、上次已找到窗口前阶段、上次未找到或失败，都不会天然阻止下一次尝试，依据 `src/pring_cycle/projections.py:356`、`src/pring_cycle/p0.py:225`、`:250`。

**7. “同窗口首日、同口径不重复回溯”缓存设计**

7.1 **【设计建议】**不能只用 `(window_start, core_history_basis)`：还应包含模型版本／趋势与阶段映射规则摘要、回溯算法版本、最大年数，并校验窗口前已持有核心价格及日历依据的内容摘要。模型规则或输入变化却复用旧结果可能改变上一确认阶段的选取；当前回溯确实使用传入规则及已持有价格，依据 `src/pring_cycle/stage_lookback.py:184`、`:185`、`src/pring_cycle/worker.py:2224`。

7.2 **【设计建议】**可将缓存键、结果、来源运行、计算时间写入现有 `full_run_gap_plan.document_json`，从仍保留的已完成运行中查匹配结果，**无需 schema 迁移**；旧记录缺完整缓存键时按未命中处理。修改 `worker.py` 的调用前查询、`full_retrieval.py` 的结果存取，必要时抽出 `stage_lookback.py` 的键构造；新运行记录必须写“复用、实际请求 0、来源运行”，不能复写旧结果中的 3／1 次为本次成本。

7.3 **【设计建议】**窗口首日、basis、模型／算法、已知输入变更、缓存来源过期或人工刷新时失效；只缓存 `found`／`not_found`，失败不永久缓存，以免一次故障阻止后续恢复。相同输入下复用不改变计算规则，但不再联网就无法保证发现上游对更早历史的修订，因此必须让用户决定有效期和刷新政策；这涉及 ADR-0040“每次运行重新取得”的现行约定，依据 `docs/adr/0040-core-price-history-covers-window-and-last-confirmed-stage.md:17`。

7.4 **【读码推演】**这种严格按窗口首日的缓存主要节省同窗口重跑，窗口随交易日向前移动时仍会未命中，不能消除长期非典型组合下的每日回溯成本。若要跨窗口复用，还需处理新增搜索日期及最近正式阶段判定，已超出本候选的简单缓存范围。

**8. 测试缺口逐项确认**

8.1 **【读码确认】**回溯模块针对 `TushareCallNotAttempted` 的核心／日历计数减一分支，没有发现独立覆盖用例；分支在 `src/pring_cycle/stage_lookback.py:137`。现有失败用例只参数化 `OSError`、`IncompleteRead`，见 `tests/integration/test_core_stage_lookback.py:353`，日历缺日用例 `:383` 断言的是已发日历 **1**、核心 **0**，不是限额拦截；`tests/integration/test_tushare_call_quota.py:185` 等虽测限额异常，也不等于覆盖回溯计数。

8.2 **【读码确认＋限定票面】**三核心首日不一致时，会以最晚首日作为公共 `reach`，三核心请求同一区间，所以较早已有数据的核心会重取重叠段；合并时已持有价格覆盖回溯返回价格，依据 `src/pring_cycle/stage_lookback.py:100`、`:127`、`:184`。现有替身按同一日历生成三核心数据，没有首日错位专测，见 `tests/integration/test_core_stage_lookback.py:75`、`:90`；“现行不会出现”只能描述正常共同取数路径，不能当作模块保证，正常路径依据 `src/pring_cycle/core_history.py:95`、`:102`。

8.3 **【读码确认】**原票 08 的贷款窗口根因回归直接调用 `build_context_projection()`，随后直接调用窗口校验函数，未经过单日汇总接缝。位置为 `tests/integration/test_context_projection.py:1946`、`:1988`、`:2004`；`persist_derived=True/False` 的参数标签虽叫目标日／补算日，也不能替代真实接缝覆盖，但不能据此说整个票 08 都没有完整运行测试，后者见 `tests/integration/test_core_only_correction.py:156`。

8.4 **【读码确认】**“核心自身声明移出仍不算上下文缺失”的用例确实替换私有 `_evidence_status`，强制商品核心返回 `current` 后运行。位置为 `tests/integration/test_core_only_correction.py:320`、`:323`、`:328`，随后删除相关声明并断言 `context_details_held()` 为真，见 `:337`、`:342`；票面若表达为“尚需替换私有函数”不准确，当前测试已经这样做，缺口是依赖私有替身构造状态。

**9. 规格中的日历请求表述**

9.1 **【文档核对】**`.scratch/model-rules-validation-20261011/spec.md:35` 用户故事 11 明写“回溯时每年每个核心一次，最多 15 次”；`:56` 的 Implementation Decisions 写“三核心各请求一年区间、最多 5 年”，**没有直接写“15 次”，也没有提日历请求**。因此票面对两处文字的概括略有失真：共同问题是日历成本未列出，而非两处都明确规定全部请求最多 15 次。

9.2 **【读码】**每个回溯年份先调用日历的位置为 `src/pring_cycle/stage_lookback.py:105`、`:109`、`:110`，经 `src/pring_cycle/trading_calendar.py:473` 转到 `src/pring_cycle/source_adapters.py:182`、`:187` 的 `trade_cal` 请求。建议将规格明确补为“核心最多 15 次，另有日历最多 5 次，合计最多 20 次；串行、找到或失败即停止”，保留用于验证 139 个交易日预热的日历逻辑。
