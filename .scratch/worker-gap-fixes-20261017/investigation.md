**结论：⑦ 同时存在真实取数缺陷和展示误导。社融、中间价需要修 Worker；EIA 属于正常发布滞后；完整度缺字段来自较旧投影；AI 原始代号属于报告表达问题。** 全程只读，SQLite 使用 `mode=ro&immutable=1`，未启动 Worker、调用外部接口或访问正式库。

以下数据证据简称：A＝10-15 隔离库，运行 `run-2b21b77b4968f3bbcfc3`；B＝10-14 隔离库，运行 `run-34d49a71553ec24f96ac`。

1. **完整度：10-15 缺字段属实，10-14 已有；属于③历史投影兼容问题。** A 的 `analytical_dataset[macro]` 没有 `coverage`，B 则有：模型口径应有 **1014**、持有 **1013**、门禁 **1**；目录口径应有 **3064**、持有 **3059**、门禁 **3**、其他缺失 **2**。当前代码明确生成该字段，因此不是新代码也不产；建议旧投影标明“生成时尚未提供此统计”，后续由正常新版运行生成，避免前端临时重算历史事实。  
   证据：两库上述数据行；[day_summary.py:284](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/day_summary.py:284)、[display_projection.py:37](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/display_projection.py:37)、[cockpit.py:1812](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1812)。

2. **社融：“9 月尚未发布、整期未请求”不属实，属于①Worker 缺陷并伴随③展示误导。**

   **2.1 发布时间。** 库内历史显示金融数据通常在次月中旬发布，例如 2025 年 9 月数据于 10 月 15 日发布；本次已保存的新华社报道明确记载，2026 年前三季度金融数据在 **10 月 14 日**发布，9 月社融存量同比为 **7.1%**。因此，目标日 10-15 不能解释为确实尚未发布。  
   证据：A `source_claim[period_end=2025-09-30]`；[已存新华社资讯原件:1](/tmp/pring-cb-real-20261016/data/artifacts/sha256/72/72ffaef74d8fa027a55bbe97aaa6032e6c8318c1ccad847f255257101406a07a:1)。

   **2.2 日历与门禁根因。** 两次运行的 `release_schedule` 都没有社融预告，⑦ 的发布日历投影也只有 LPR；实际门禁退回“月末后第 10 个上交所交易日、18:00”的估算，本期算到 **10 月 21 日 18:00**。更关键的是，社融总量与分项被绑成同一补缺范围：总量已有当期数据，分项没有，代码却让任一指标的 `awaiting_release` 否决整个范围，并且不允许这一状态再查官方目录确认提前发布。  
   证据：A/B `full_run_gap_plan[initial].scopes[2026-09]`；[freshness.py:217](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:217)、[freshness.py:283](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:283)、[worker.py:1075](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/worker.py:1075)、[worker.py:1098](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/worker.py:1098)、[full_retrieval.py:198](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/full_retrieval.py:198)。

   **2.3 实际缺什么、怎么修。** 两次最终计划均已选入 9 月社融存量和累计增量，**只缺 `stock_yoy`（存量同比）**，所以“未请求 2026-09”把“补缺被跳过”说成了“整期没取”。建议同一发布事件的可靠已发布证据优先于估算门禁，允许目录发现提前发布，并展示“已取得哪些成员、尚缺哪些成员”；改动落在发布门禁、发布目录和缺口投影。  
   证据：A/B `full_run_gap_plan[final].gaps[CN_SF_TOTAL,2026-09]`；[full_retrieval.py:106](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/full_retrieval.py:106)、[freshness.py:1065](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:1065)。

3. **EIA：本次滞后正常，属于②；列成“缺失”和“无网页补缺渠道”则有③误导。**

   **3.1 已存原件支持正常等待。** A 的 Brent、WTI 原件均标示发布日 **10-15**、下次发布日 **10-21**，最新数值到 **10-14**，10-15 单元格为空；B 拿到的版本发布日为 **10-07**、下次发布日 **10-15**，最新数值到 **10-06**。这是“日频观测、分批发布”，不能要求目标日当天必有值，也不宜笼统固定为滞后两三天。  
   证据：[A WTI 原件:20490](/tmp/pring-cb-real-20261016/data/artifacts/sha256/49/49c2a4d582a2029287d8dec1a6b633f99a4a2319dd194663a2383a6feccffd96:20490)、同文件 `:20515`；B `acquisition_request[acquisition-a96487f3a2014b33b59f25f315eaea6e]`。

   **3.2 建议口径。** 已采用最新可得值的正常等待应单列，**不计入真正缺失**；当前 `freshness.py` 却把所有未请求项直接归为 `missing`。此外，两次运行实际都用了官方 HTML，“无网页补缺渠道”仅表示没有登记通用网页检索家族，应改成“未配置额外网页检索补缺”，并优先依据原件发布日历判断等待状态。  
   证据：A/B `batch_freshness[EIA_*].status=current`、`acquisition_request.api_name=eia_history_html`；[freshness.py:1065](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:1065)、[retrieval_registry.py:207](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/retrieval_registry.py:207)。

4. **中间价：10-15 已发布但未进入模型属实，属于①；并非发布时间未到。**

   **4.1 财联社。** 保存页面明确写有 **10-15 09:16:03、6.7253**，但规则只接受“人民币汇率中间价为1美元对人民币……元”，不接受“人民币兑美元中间价报……”，因此报 `rule_not_matched`。应补充这种媒体句式，同时保留统计期、币种和报价方向校验。  
   证据：A `retrieval_candidate_validation[candidate-validation-efa4276d73884b0e9d8992ecdebad09f]`；[news_rules.py:625](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/news_rules.py:625)。

   **4.2 新浪。** 搜索返回的是 **10-12 公告，值为 6.7313**，所以 `period_mismatch` 拒收正确，问题在候选命中质量。另一个 AI 检索候选已给出 10-15 的 6.7253，却同样因媒体句式不匹配失败，修解析规则比放松日期校验更直接。  
   证据：A `retrieval_candidate_validation[candidate-validation-91df536f91ad4c9899875e3339fc2f97]`、`[candidate-validation-b0f65609cb27420ebfebad7a77af694b]`。

   **4.3 央行。** 首次请求成功拿到**栏目列表页**，其中已有 10-15 公告链接，但该栏目未登记为可解析列表，代码直接找正文汇率，报 `official_context_usdcny_quote_missing`；搜索再次返回同一 URL 时，被 `negative_cache_active` 拦截，**不是预算耗尽**。应登记中间价栏目、按目标日期跟进公告正文，并把首因和缓存阻断分别展示。  
   证据：[央行原件:477](/tmp/pring-cb-real-20261016/data/artifacts/sha256/d1/d123b27cb9d03f6155a8945a97c36c7a079e689fa1a810b8f27470ce9cbec496:477)；A `acquisition_request[acquisition-991b4b3f231b40848f859d66967db8d8]`、`[acquisition-ea98294268084931a8f2af456a29eb0b]`；[official_listing.py:14](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/official_listing.py:14)、[official_context.py:2998](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/official_context.py:2998)。

   **4.4 是否反复出现。** 最近目标日 **10-09、10-12、10-13、10-14** 均持有对应日期中间价，来源为 `tushare_news/major_news`；10-15 才在这些最近运行中出现持有 10-14、落后一期。因此是持续存在的解析与目录缺陷本次暴露，证据不支持“近几天每天都拿不到”。  
   证据：A `parent_run JOIN batch_freshness[CN_USDCNY_CENTRAL_PARITY]`，以及 `source_claim_acquisition` 对应来源记录。

5. **AI 代号：输入和提示词两方面都有原因，属于③。** 报告输入直接传入 `rule.source` 和 `last_confirmed_stage` 原始值，提示词要求写来源，却没有要求来源、阶段使用中文名称；ADR-0027 要求保留来源名称，并不要求暴露接口码。建议保留机器字段用于校验，另提供中文展示名并约束正文用词；B 的新式“非典型组合解读”已经使用“阶段 III”，A 的旧报告则由前端原样显示，旧投影重新生成报告也未必自动补齐新版解读基础字段。  
   证据：A `report_snapshot[report-0123080db982b28815a8]`、B `[report-fa0beb6e19272133cead]`；[reports.py:281](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/reports.py:281)、[reports.py:556](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/reports.py:556)、[reports.py:1141](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/reports.py:1141)、[cockpit.py:1164](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/cockpit.py:1164)。

6. **还有三处需要区分或修正。**

   **6.1 目标日与时效截至没有写错，属于②。** A 应显示“目标日 **10-15**；时效截至 **10-16 16:08（北京）**”，B 应显示“目标日 **10-14**；时效截至 **10-15 21:34（北京）**”，均与冻结记录一致；建议增加一句“目标日决定分析日期，时效按运行冻结时点判断”。  
   证据：A/B `report_snapshot.body_json.freshness_basis`；[dashboard.py:484](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/dashboard.py:484)、[freshness.py:939](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:939)。

   **6.2 缺口列表不完整，属于①投影遗漏和③展示问题。** 两份最终计划都还缺仓单 **07-21 的 CU/RB/RU/SC/SP**、**09-09 的 PP**，但⑦缺口列表未列出；这也解释了 B 完整度表的“其他缺失 2”为什么找不到对应详情。建议从最终计划补入历史缺期与缺成员，并明确完整度按“指标×期”计数、缺口列表按指标归组。  
   证据：A/B `full_run_gap_plan[final].gaps[CN_FUTURES_WARRANTS]` 与 `cycle_overview.gap_list` 对照；[freshness.py:892](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/freshness.py:892)、[display_projection.py:42](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/display_projection.py:42)。

   **6.3 “阶段变化记为缺口”容易误导，属于③。** A 三核心齐全且未沿用，正式阶段为空是牛／熊／牛构成非典型组合，不能让读者理解为核心数据缺失。应将阶段事件里的 `gap` 结合 `noncanonical_combination` 翻译为“非典型组合，暂无正式阶段”，同时统一指标名、原因码和候选失败原因的中文表达。  
   证据：A `cycle_overview.stage_reason`、报告首段；[reports.py:282](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/reports.py:282)、[dashboard.py:534](/home/tywin/worktrees/datasourceRF-cl/src/pring_cycle/dashboard.py:534)。

| 问题 | 类别 | 根因 | 建议修法 | 改动范围 |
|---|---|---|---|---|
| 10-15 无完整度 | ③ | 较旧投影无 `coverage` | 标明历史版本能力；新版正常生成 | 前端／Worker 投影 |
| 社融 9 月等待发布 | ①＋③ | 预计日期偏晚；同组分项否决已发布总量 | 同发布事件证据优先；允许目录确认；显示缺存量同比 | Worker／目录／前端 |
| EIA 被算缺失 | ②＋③ | 正常批次发布，却统一归入 `missing` | 等待发布单列，不计真正缺失 | Worker 投影／前端 |
| EIA“无网页渠道” | ③ | 把未登记通用检索说成无网页来源 | 明示已有官方 HTML、无额外检索补缺 | 前端 |
| 中间价未取得 | ① | 媒体句式遗漏；央行栏目未跟进正文 | 扩展规则、登记栏目、保留精确失败原因 | Worker／目录 |
| AI 原始代号 | ③ | 原始码直接入报告，缺中文表达约束 | 提供展示名，约束正文；区分非典型与数据缺口 | Worker 报告输入／提示词／前端 |
| 仓单历史缺口漏列 | ①＋③ | 最终计划与指标时效缺口未完整汇合 | 补入历史缺期及成员，统一统计解释 | Worker 投影／前端 |
| 目标日与时效跨日 | ② | 两个时间承担不同语义 | 保留现有值，补一句解释 | 前端 |
