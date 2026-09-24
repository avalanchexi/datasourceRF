# 真实运行仍缺失项目的只读排查（2026-09-24，Codex）

运行 run-1579de05ddf2f0d7f48f。由 Codex CLI 只读排查（gpt-6-astra/high，约 20 分钟）；Claude Code 已复核：`full_retrieval.py` 中 `_period()` 的选期分支、真实库 `full_run_gap_plan` 的 initial/final 记录、9/23 资讯原件中“操作利率1.40%”原句，三处均属实。

**结论：主要是检索计划遗漏，不能归咎于接口失败或没有来源。** 工业三项、VIX、SOX 选错待检索期；OMO 利率在无历史值时被跳过；降准也存在事件发现入口缺失，但本次证据不能证明目标日前确有一次应补的降准。

| 项目 | metric_id | 归类 | 一句话原因 |
|---|---|---|---|
| 工业企业财务 | `CN_INDUSTRIAL_FINANCE` | **(b)** | 只计划尚未发布的8月，漏掉已发布但未持有的7月 |
| 产成品库存 | `CN_FINISHED_GOODS_INVENTORY` | **(b)** | 同上 |
| 库存周转 | `CN_INVENTORY_TURNOVER` | **(b)** | 同上 |
| OMO 利率 | `CN_OMO_7D_RATE` | **(b)** | 被按事件处理，无历史值即不建检索范围 |
| 降准 | `CN_RRR_EVENT` | **(b)，读码推断** | 已登记官方来源，但未持有事件时不触发发现；是否实际漏了公告尚无证据 |
| VIX | `CBOE_VIX_INDEX` | **(b)** | 只计划9/23，被发布时间门禁挡住，漏掉已发布的9/22 |
| SOX | `NASDAQ_SOX_INDEX` | **(b)** | 同上 |

以下 SQL 均限定 `run_id=run-1579de05ddf2f0d7f48f`；源码路径以 `src/pring_cycle/` 为根。需区分：检索发布截止被限定为**目标日9/23结束**，而最终时效表按**实际9/24运行截止**计算；另外代码中的 `due_period` 包含宽限期，检索使用的是最新已发布期（[full_retrieval.py:80](../../src/pring_cycle/full_retrieval.py:80)、[freshness.py:262](../../src/pring_cycle/freshness.py:262)）。

共同证据：

- SQL→七个指标在 `retrieval_run_gap JOIN retrieval_gap` 中各 **0** 条，在 `full_run_acquisition JOIN json_each(metric_ids_json)` 中各 **0** 条，因此没有对应 acquisition 的 `state/rejection_reason`，不能写成“取数拒收”。
- SQL→`source_claim WHERE available_at<=本次最终system_as_of`：七个指标各 **0** 条。
- TuShare **数值接口均未接入这些指标**，依据完整分派表 [targeted_context.py:43](../../src/pring_cycle/targeted_context.py:43) 与未配置出口 [targeted_context.py:95](../../src/pring_cycle/targeted_context.py:95)；这不代表 TuShare 产品本身一定没有相关接口。
- SQL→本次统一 `major_news` acquisition：**4条 validated／rejection_reason=NULL，1条 failed／tushare_source_failed**；统一拉取不等于七个指标逐项尝试过资讯解析。

**A．工业企业财务三项**

1. 三项均 **P1**，发布家族 `nbs_industrial_finance`、release rule 为 `source_schedule_required`，官方为国家统计局 `/sj/zxfbhjd/`，TuShare 数值接口未接入，三项资讯规则均已登记（[catalog.py:85](../../src/pring_cycle/catalog.py:85)、[catalog.py:167](../../src/pring_cycle/catalog.py:167)、[catalog.py:676](../../src/pring_cycle/catalog.py:676)、[retrieval_registry.py:67](../../src/pring_cycle/retrieval_registry.py:67)、[news_rules.py:283](../../src/pring_cycle/news_rules.py:283)）。
2. 应检索 **2026-07**，而非8月：SQL→`batch_freshness` 三项均 `due_period=released_period=2026-07-31`；`release_schedule` 的“工业经济效益月度报告”为 **8/27 09:30、9/28 09:30**，分别对应7月、8月，故目标日7月已发布、8月未发布（映射：[release_schedule.py:44](../../src/pring_cycle/release_schedule.py:44)、[freshness.py:617](../../src/pring_cycle/freshness.py:617)）。
3. SQL→`full_run_gap_plan(initial)` 只含三项合并的 `period=2026-08, release_status=awaiting_release`，final 仍缺该期；`run_retrieval_attempt` 对该家族 **0条**，local、TuShare、资讯、官方、Tavily/Exa、AI 均无逐项尝试，也无 acquisition。
4. 原因是未持有月频值时 `_period()` 直接返回目标日上月，再被发布门禁静默跳过；因此“8月未发布”只能解释为何不取8月，不能解释为何7月也不取（[full_retrieval.py:368](../../src/pring_cycle/full_retrieval.py:368)、[full_retrieval.py:86](../../src/pring_cycle/full_retrieval.py:86)）。
5. **修复** [full_retrieval.py:368](../../src/pring_cycle/full_retrieval.py:368)：依据同一目标截止与发布日历选择最新已发布期，再生成缺口；官方列表识别也未包含工业财务家族，建议补齐，但这是尚未在本次请求中暴露的后续问题（读码推断，[official_listing.py:8](../../src/pring_cycle/official_listing.py:8)）。

**B．OMO 利率**

1. `CN_OMO_7D_RATE` 为 **P1**、家族 `pbc_omo_notice`，官方央行公开市场业务公告已登记，release rule 为 `source_schedule_required`，时效为交易日 **09:15**，TuShare 数值接口未接入、资讯利率规则已登记（[catalog.py:65](../../src/pring_cycle/catalog.py:65)、[catalog.py:155](../../src/pring_cycle/catalog.py:155)、[freshness.py:105](../../src/pring_cycle/freshness.py:105)、[news_rules.py:465](../../src/pring_cycle/news_rules.py:465)）。
2. SQL→最终 `batch_freshness.due_period=2026-09-23`，该日09:15已过；但消费语义另将其解释为“有效直到变更”的事件，不能要求每天必须产生新利率观测（[metric_contracts.py:9](../../src/pring_cycle/metric_contracts.py:9)）。
3. SQL→initial/final 都只记 `event_presence_unknown`、没有利率 scope；同家族9/23的 `local/not_found/NULL → tushare/not_configured/targeted_tushare_family_unavailable → tushare_news/verified/NULL` **仅覆盖 `CN_OMO_7D_AMOUNT`**，利率自身各渠道尝试与 acquisition 均为0。
4. 排除链为 `evidence_frequency→event`、无历史值返回 `None`、随后 `continue`；而本次保存的资讯原件已含9/23财联社17:21:58稿件中的“操作利率1.40%”，所以并非已经证明来源无值（[metric_contracts.py:37](../../src/pring_cycle/metric_contracts.py:37)、[full_retrieval.py:359](../../src/pring_cycle/full_retrieval.py:359)、[full_retrieval.py:250](../../src/pring_cycle/full_retrieval.py:250)；SQL→资讯原件 hash=`bf1a39439954a61b25de62d2fd07ff82544f6ecaf14f9eb57b176ce674c61063`）。
5. **修复** [full_retrieval.py:359](../../src/pring_cycle/full_retrieval.py:359)：无利率基线时仍建立目标日公告检索范围，可与操作量合组并要求两者完整后才停止级联；资讯仅解析 scope 内指标，现有操作量成功不会顺带补利率（[tushare_news.py:249](../../src/pring_cycle/tushare_news.py:249)）。

**C．降准**

1. `CN_RRR_EVENT` 为 **P1**、家族 `pbc_rrr_notice`，央行官方候选与专用解析器均已登记、release rule 为 `source_schedule_required`，TuShare 数值接口未接入、资讯规则未登记（[catalog.py:70](../../src/pring_cycle/catalog.py:70)、[catalog.py:161](../../src/pring_cycle/catalog.py:161)、[retrieval_registry.py:79](../../src/pring_cycle/retrieval_registry.py:79)、[official_context.py:845](../../src/pring_cycle/official_context.py:845)、[news_rules.py:501](../../src/pring_cycle/news_rules.py:501)）。
2. **没有应有期，也没有固定发布时点**：SQL→`batch_freshness.frequency=event, due_period=NULL, released_period=NULL`，故不能据日历宣称9/23应该降准，也不能把未持有解释为“尚未发布，正常”（[freshness.py:156](../../src/pring_cycle/freshness.py:156)、[CONTEXT.md:185](../../CONTEXT.md:185)）。
3. SQL→initial/final 只有 `event_presence_unknown`、无 scope，全部渠道尝试 **0条**、acquisition **0条**，没有接口失败、无权限或解析失败的运行证据。
4. **归(b)是对发现入口遗漏的判断，标注读码推断**：未持有事件便在 [full_retrieval.py:359](../../src/pring_cycle/full_retrieval.py:359) 返回 `None`，再由 [full_retrieval.py:250](../../src/pring_cycle/full_retrieval.py:250) 排除；现有证据不足以证明实际漏了哪次降准，但官方来源已登记，故不符合(d)。
5. **修复事件发现流程**：在上述 `None` 分支建立截至目标日的官方公告发现任务，并补 [official_listing.py:8](../../src/pring_cycle/official_listing.py:8) 的降准列表识别与发布事实确认，区分“查过未发现事件”和“没有查过”，不能凭空造 due period。

**D．VIX**

1. `CBOE_VIX_INDEX` 为 **P2**，目录发布家族 `cboe_vix_index`、检索家族 `cboe_vix`，release rule 为 `source_schedule_required`，登记 `www.cboe.com`、`cdn.cboe.com` 的宽松搜索路径，TuShare 数值接口及资讯规则均未登记，但宽松路径可进入 AI 搜索（[catalog.py:107](../../src/pring_cycle/catalog.py:107)、[catalog.py:666](../../src/pring_cycle/catalog.py:666)、[retrieval_registry.py:120](../../src/pring_cycle/retrieval_registry.py:120)、[worker.py:857](../../src/pring_cycle/worker.py:857)）。
2. 按登记的 **滞后1个中国交易日、北京时间06:00**，目标日可检索最新期是 **9/22**，于9/23 06:00到时；SQL→最终时效表 `due_period=9/22, released_period=9/23`，后者是在9/24实际运行截止下得到，不能代替目标日检索边界（[freshness.py:121](../../src/pring_cycle/freshness.py:121)）。
3. SQL→initial 仅 `period=2026-09-23, release_status=awaiting_release, source_url=NULL`，final 仍缺9/23；所有渠道尝试和 acquisition 均 **0条**。
4. 日频 `_period()` 硬取目标日，9/23这一期需9/24 06:00才发布，因此被正确门禁挡住，但计划没有回退到9/22，构成(b)（[full_retrieval.py:355](../../src/pring_cycle/full_retrieval.py:355)、[worker.py:826](../../src/pring_cycle/worker.py:826)、[full_retrieval.py:86](../../src/pring_cycle/full_retrieval.py:86)）。
5. **修复** [full_retrieval.py:355](../../src/pring_cycle/full_retrieval.py:355)：让此类指标按目标截止调用最新已发布期计算，保留次日发布时间限制；本次没有证据支持“VIX接口无数据/无权限”。

**E．SOX**

1. `NASDAQ_SOX_INDEX` 为 **P2**，目录发布家族 `nasdaq_sox_index`、检索家族 `nasdaq_sox`，release rule 为 `source_schedule_required`，登记 `www.nasdaq.com`、`indexes.nasdaqomx.com` 的宽松路径，TuShare 数值接口及资讯规则均未登记（[catalog.py:108](../../src/pring_cycle/catalog.py:108)、[catalog.py:666](../../src/pring_cycle/catalog.py:666)、[retrieval_registry.py:127](../../src/pring_cycle/retrieval_registry.py:127)）。
2. 与VIX相同，目标日可检索最新期为 **9/22**、9/23 06:00已到时；SQL→最终 `due_period=9/22, released_period=9/23`（[freshness.py:122](../../src/pring_cycle/freshness.py:122)）。
3. SQL→initial 仅 `period=2026-09-23, release_status=awaiting_release, source_url=NULL`，final 仍缺9/23；全部渠道尝试及 acquisition 均 **0条**，不存在本次解析拒收记录。
4. **归(b)**：同一日频选期分支选到未发布期，再被门禁跳过，缺的是已发布期的检索计划，并非目录没有可用来源（[full_retrieval.py:355](../../src/pring_cycle/full_retrieval.py:355)、[full_retrieval.py:86](../../src/pring_cycle/full_retrieval.py:86)）。
5. **修复**与VIX共用的选期逻辑即可；补独立 TuShare 接口属于可选扩展，不是解释或修复本次零检索的前提。
