# Tavily / Exa 检索效果只读审查

核查时间：2026-09-06 10:28:24 UTC（北京时间 18:28:24）。运行库为 `/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3`，以 SQLite URI `mode=ro` 和只读事务查询。完整 SQL、实际 schema、统计结果、文件哈希见 [search-statistics.json](search-statistics.json)，SHA-256 为 `8c582c5be89679636494a3b8d70de5a50e53258933866dc70c9c2a603ce92bad`。

本次没有网络请求、没有读取密钥值，没有修改代码或运行数据库；只新增本审查与统计文件。统计范围是当前正式运行库及正式日志，测试目录中的 fixture 数据库不计入。

## 结论及主口径

**当前生产数据不能给出 Tavily 或 Exa 的有效命中率。** 正式运行库中两渠道均没有调用记录；完整刷新也没有进入搜索降级链。现有生产搜索实现只能发现首个候选 HTTPS URL，缺少“候选下载→官方来源/字段/单位/期次/公开时间校验→SourceClaim→selected observation→投影”的连接。不能把已实现 HTTP 请求、离线测试通过或历史候选命中说成已经补齐模型证据。

用户 Q1 已确认的主指标是“模型可用缺口补齐率”，定义已冻结于 `CONTEXT.md:243-249`。在固定审查范围内，**分母是某渠道实际请求处理的唯一证据缺口数；分子是其中被该渠道取得、满足模型输入条件的证据完整补齐的唯一缺口数**。没有实际请求样本时为 N/A。一个缺口应至少用指标/定义版本、统计期、维度及目标模型和 as-of 约束标识；重复查询、重试、多个搜索结果以及同一证据的不同 URL 不能重复计数。仅列入计划但未实际请求的缺口不进入该渠道主指标分母；候选 URL、只通过字段校验、未认证 claim 和不在目标窗口内的证据不进入分子。

满足模型输入条件后，即可按完整补齐计入主指标；是否已被正式模型实际选用另作下游指标，不能混入主指标分子。另列两个独立指标：**需求总体覆盖率**以固定审查范围内全部待补齐需求缺口为分母，统计其中已获得模型可用完整证据的唯一缺口；**实际模型采纳率**以已完整补齐且满足模型输入条件的唯一缺口为分母，统计其中证据实际被指定正式模型/投影采纳的唯一缺口。两者都需固定同一审查范围及观察时点；当前缺少持久 `gap_id`、渠道归因和完整校验/采纳关联，不能可靠量化。

| 层级/分母 | Tavily | Exa | 可以作出的判断 |
|---|---:|---:|---|
| 当前生产检索 scope / 已登记搜索缺口 | 0 | 0 | 没有 targeted/manual 搜索任务 |
| 当前生产可观测请求尝试 | 0 | 0 | 未调用记录；不能写 0% 命中 |
| HTTP 成功率：成功 HTTP / 物理 HTTP 请求 | N/A | N/A | 0 请求；还缺请求级持久审计 |
| 候选命中率：有候选查询 / 实际逻辑查询 | N/A | N/A | 0 查询；候选也不等于官方有效证据 |
| 可归因的模型可用唯一缺口补齐数 | 0 | 0 | 没有任何可归因成功链条 |
| 模型可用缺口补齐率：完整补齐且模型可用 / 该渠道实际请求处理的唯一缺口 | N/A | N/A | 无实际请求样本；不能写成 0% |
| 独立指标：需求总体覆盖率 | 不可计算 | 不可计算 | 全部需求缺口集合与完整补齐归因未被持久定义；不替代渠道主指标分母 |
| 独立下游指标：实际模型采纳率 | N/A | N/A | 没有可归因的模型可用补齐样本，且缺少其到正式模型/投影的采纳关联 |
| 提供商实际账单/credit 消耗 | 不可计算 | 不可计算 | 数据库预算计数不是提供商账单 |

这里“可观测请求为 0”针对当前正式账本。由于 HTTP 响应未持久保存，且整个 cascade 返回后才批量写尝试账本，不能从这个数字证明所有机器、所有历史脚本从未请求过供应商。下面单列已发现的早期探针摘要。

## 正式运行数据及可复核 SQL

以下关键查询均在该正式库执行，完整版本及结果在 JSON 中：

```sql
SELECT count(*) AS n FROM run_retrieval_scope;
-- 0
SELECT count(*) AS n FROM run_retrieval_attempt;
-- 0
SELECT * FROM run_retrieval_attempt
WHERE channel IN ('tavily','exa') ORDER BY retrieval_attempt_id;
-- []
SELECT channel,outcome,count(*) AS n,min(fetched_at),max(fetched_at)
FROM retrieval_attempt GROUP BY channel,outcome;
SELECT command_type,status,outcome,count(*) AS n
FROM parent_run GROUP BY command_type,status,outcome;
SELECT command_type,consumed_budget_json,count(*) AS n
FROM parent_run GROUP BY command_type,consumed_budget_json;
SELECT * FROM artifact_reference
WHERE lower(source_reference) LIKE '%tavily%'
   OR lower(source_reference) LIKE '%exa.ai%';
-- []
```

- `parent_run` 共 13 个：10 个 `manual_full`、3 个 `report_generation`，没有 `targeted_refresh` 或 `manual_deep_search`。13 个运行的 Tavily/Exa/AI 消耗字段均为 0。
- `run_retrieval_scope`、`run_retrieval_attempt`、`retrieval_negative_cache` 都是 0 行。
- 指标级 `retrieval_attempt` 共 5,745 行：官方直连 verified 95；官方候选 verified_candidate 4,914、source_failed 4；TuShare verified 27、verified_candidate 599、source_failed 22；TuShare-history verified 84。**这些是指标/批次级审计，不能当作 5,745 次物理网络请求。** 同一个原件或调用可能服务多条指标。
- `source_claim` 共 272,949 行，provider 只有 TuShare、中国人民银行、国家统计局、中国货币网。provider/来源引用包含 Tavily 或 Exa 的 claim 为 0；artifact_reference 的搜索服务 URL 为 0。来源归属于官网时也可能由人工搜索发现，所以“无 provider 字符串”本身不能证明完整发现渠道归因；现有 schema 正是缺少这条归因关系。
- 正式日志 `/home/tywin/.local/state/pring-cycle/logs/web.jsonl` 27 行、`worker.jsonl` 20 行，没有搜索渠道/检索文字记录。这些日志只有 component、event_code、error_code、job_id、run_id、timestamp 等字段，没有请求、结果数、查询或费用明细。
- 7 个 projection、8 个 evidence_bundle。8 个 bundle 的规范 JSON 哈希均复核通过，未出现搜索渠道或 candidate_source 字符串。这是结构和身份核对，不替代指标语义审查。
- 8 个报告快照全为 `completed_degraded` / deterministic；16 条报告适配器尝试包括 Codex 超时 8、Claude 未安装 6、启动失败 1、超时 1，tool_events 均为 0。不能将这些称为 Tavily/Exa 获取成功或成功 AI 报告。

## 当前代码实际调用及断点

| 环节 | 可核查代码 | 实际行为/限制 |
|---|---|---|
| 用户入口 | `src/pring_cycle/web.py:549`；`cli.py:681` | 公开命令包含 targeted_refresh/manual_deep_search；CLI 可传 release_event、metric、period、source_url |
| scope 绑定 | `runs.py:940-986` | 从指定模型 manifest 取指标定义，验证指标属于该模型、priority 一致；手动深搜恰好一个指标。scope 不是任意 fixture |
| Worker 默认执行 | `worker.py:140-150,265-274,456-472` | retrieval_adapters 默认 None；生产路径构建真实 adapter。测试可注入 adapter，不能把注入测试计为外部实测 |
| 完整刷新 | `worker.py:276-287` | 调 `_refresh_core_sources` 和 `_refresh_context_sources`；不调 retrieval cascade。因此已有 manual_full 的缺口不会自动成为 Tavily/Exa 请求 |
| 发布门禁 | `worker.py:531-549` | LPR 按窗口；其他必须有 source_url 且属于已知 official family，否则 False，随后记 awaiting_release/not_attempted。一般“尚未知官方 URL”的指标缺口可能在搜索前被拦住；未发布与未实现路由被合并 |
| 生产 adapter 集合 | `worker.py:552-600` | 构造 local、部分 official，凭据存在时构造 Tavily/Exa；没有构造 TuShare 和 ai_websearch。领域 cascade 中的这两个位置实际会 not_configured |
| 认证及本地复用 | `worker.py:603-638` | 用目标 model 的 definition_version、SYSTEM as_of；要求 selected + certified + validated 才返回本地证据。这是已存在正式证据复用，不是搜索命中 |
| 搜索 query | `search_discovery.py:29-40`；`catalog.py:396-405` | 指标 ID/中文名/source_codes + period +“官方 发布”；没有官方域名参数。query 调默认 metric_definition，没有传目标模型 definition_version，与 scope/本地证据的版本绑定不完全一致 |
| 真实 HTTP | `search_discovery.py:44-72,79-104,107-137` | 默认 transport 是 `_post_json`，固定 Tavily/Exa HTTPS POST，15 秒 timeout、1 MB 上限；Tavily basic/max_results=5，Exa auto/numResults=5。本次未执行它们，也未核验凭据状态 |
| 返回候选 | `search_discovery.py:60-69,157-178` | 只选前 10 项内首个语法合规 HTTPS URL。验证 scheme/hostname/长度/无用户密码，不验证官方域、指标身份、统计期、单位、字段、数值或发布时间。`not_found` 是没有合规候选 URL，不必然是 API results 数量为 0 |
| 候选消费断点 | `retrieval.py:117-161`；`worker.py:473-528` | 候选进入 attempts/candidate_sources；没有候选页下载或 parser 调用。worker 只保存 candidate_source URL，再标 unresolved/manual_review。生产代码没有 candidate_sources 后续消费者 |
| 已有 official 路线 | `worker.py:641-708` | 使用调用前就提供的 source_url 调官方 refresh/ingest。它与搜索返回 URL 没有桥接；不能当成搜索后已完成验证 |
| 投影/报告边界 | `worker.py:300-304`；`reports.py:194-239,630-634` | 正式刷新从 EvidenceRepository 构建投影；报告从已经发布的投影收集 allowed_evidence_ids 和结构上下文。检索运行 verified 后 `worker.py:500-508` 只写 checkpoint、completed，不重建投影 |

所以当前不是把 raw snippet 错当模型事实；**当前连 snippet 都不保留，候选也未被接入模型证据**。这是可信边界保守但闭环未完成，不能通过降低认证条件来提高主指标。

## 三类历史数字必须分开

1. **当前正式生产层：** 上述 SQLite/日志实查，Tavily/Exa 请求记录 0，主指标 N/A。
2. **2026-08-21 原型探针摘要层：** `.scratch/pring-cycle-v1-wayfinding/issues/07-validate-retrieval-budgets.md:21,28-35` 报告 Tavily 3/3、Exa 2/2 返回限定官方域且覆盖预设语义组，每次 3 条结果，中位延迟 2.713 秒/1.638 秒。可标成“历史摘要报告的候选命中”；不能称完整补齐且通过来源、字段、时间等模型输入条件校验的 5 个唯一缺口。实际模型采纳也未被证明。
3. **旧 datasource 项目摘要层：** 同票第 31 行的 12 次运行、97 次尝试、9 次成功（9.3%）明确属于旧项目；本次未复核旧项目原日志，绝不能作为 datasourceRF 的效果。

该票第 35 行明确临时探针已删除，未保存 URL、查询结果正文。仓内可定位的原型 HTML 也是汇总/逻辑演示，不是原始响应。3/3、2/2 的候选语义无法重审；没有请求到唯一缺口的对应、目标模型版本、认证状态及完整补齐校验，不能计算主指标。另因缺少 SourceClaim、selected observation 和 projection 关联，也不能复算下游实际模型采纳率。

探针与当前生产还存在方法差异：探针声称限定官方域、3 条结果、Exa fast；当前代码没有域过滤，请求 5 条、Exa auto、只留下一个 URL。不能外推当前生产命中率。

## 计量、预算及持久化契约差异

| 对照项 | 早期已接受契约/文档 | 当前可证行为 |
|---|---|---|
| 原始响应 | Wayfinding `issues/07:19,33` 原始响应保留 30 天，URL/内容指纹/审计长期保存 | `docs/research/search-discovery-contracts.md:3-5,19-21` 和 `docs/development/local-runtime.md:301` 改为只记候选 URL、不保存完整响应；`search_discovery.py:124-137` 解码后无 CAS 写入。两个文档口径不一致，没有本次擅自选择其一 |
| 候选/片段 | 同票 `:15,33` 最多 3 候选、摘要合计 1,800 字符、解析片段 1,600 字符 | 请求 5 个，实际保存首 URL，既没有结果数，也没有片段/逐候选处理审计 |
| 物理请求与逻辑预算 | 单事件一次、单运行 8/4/1、日 16/8/2 | `retrieval.py:100-116,135,170-193` 预算先减一次，transient 最多执行 3 次，只首个 attempt budget_charged。一次逻辑消费可产生 3 次物理 HTTP；不能用 sum(budget_charged) 当 API 次数或账单 |
| 中断审计 | 持久检索逐级可追溯 | `worker.py:462-487` 整个 cascade 结束才保存 attempts；进程在已调用 HTTP、尚未返回/落账时终止可能缺账。没有 durable request_started/provider_request_id |
| 跨运行单事件限制 | 同票 `:17` 同一事件同一渠道当日一次自动请求 | run_retrieval_attempt 只 UNIQUE(run_id,sequence)，未见 event/channel/day 的计数门禁；run scopes 可重复事件。日预算是全渠道 aggregate，不能证明跨运行事件去重 |
| 手动深搜预算 | Wayfinding `issues/10-decide-refresh-and-recovery-model.md:43` 上限提高但仍受日 16/8/2 限制 | `retrieval.py:100-102` manual 跳过 `_consume_budget`，`runs.py:686-690` 日统计排除 manual_budget_exemption；当前实现是运行/日消费豁免。与旧票表述不同 |
| 负缓存与 Retry-After | `issues/07:17` 分错误类型 15 分钟/6 小时/24 小时，429 使用 Retry-After 或 60 分钟 | `worker.py:509-522` 对全为 not_found/not_configured/candidate 的 unresolved 固定 30 分钟；failed 不进该缓存。`search_discovery.py:127-128` HTTPError 只留状态，丢弃 Retry-After 及 quota-reset 信息 |
| 时间与费用 | 逐请求延迟、预算、下一重试 | ledger 有 latency_ms、outcome、余量等；没有真实 HTTP 状态、请求开始/结束、返回条数、计费单位/价格/实际成本/价格版本。occurred_at 统一使用进入本轮的 now（`worker.py:487`），不能当各 HTTP 实际时间 |

以上为代码/文档差异，不代表本次已发生超额或额外供应商费用。没有实账时不估算单价或成本。

## 可复核样本与缺失字段

搜索原始响应：没有可提供的正式 CAS hash。早期探针也没有原始响应 hash。不能伪造一个 URL 记录的哈希作为响应哈希。

可复核的历史文档/日志样本：

- 早期探针票 SHA-256 `77df9dfd8be1fa9f1b6cac1419a073ac35526480b1bb8dc3c52fb6c4a952671d`（5,124 字节）；逻辑原型 HTML `89f9f6f549887f6c9ae9263df23e63327bfb128ffd56b242e188812ba212e221`（40,209 字节）。这两个是文档内容 hash。
- 正式 web 日志 `3e9f7d0645157bbb51f7b10ead4979d06efe0d0ef033a42435ced0ee9bbd3a44`；worker 日志 `ca8fbbe1faa144b95cd0dfe6db909555514e51e6abafd448bad53b16340b13c9`。
- 作为“官方直连与搜索必须区分”的正样本，CAS `5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5`，11,000 字节，DB 指向 `https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html`；`52066ba7f8d92a5152b0e6ed8204999f77c3915621fdc91837c260d1b28e40b4`，168,668 字节，DB 指向 `https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_1964130.html`。本次只读本地字节并确认 hash 相符，未请求网址；这些不是 Tavily/Exa 响应，也未声称本次重审该样本全部语义。

要复算用户选定主指标，当前至少缺：持久唯一 `gap_id`；该渠道实际请求与所处理缺口的对应及去重规则；绑定 model_version/definition_version/target_date/as-of 的审查范围；物理请求与逻辑查询/重试关联；请求契约与原始响应 hash 或经过明确保留政策的可审计结果；候选总数及各候选淘汰原因；下载原件 hash；来源/字段/单位/统计期/实际可证公开时间的验证结果；搜索渠道、候选、完整补齐证据及 claim_id 的归因；补齐前后状态和满足模型输入条件的判定。现有两张 retrieval 表、source_claim 和 artifact_reference 之间没有这一闭环。

需求总体覆盖率还需要固定范围内全部需求缺口集合，包含没有实际请求的缺口；实际模型采纳率则另外需要从已满足输入条件的证据到 selected observation、projection_set_id 的关联。全部需求集合与正式采纳结果分别服务这两个独立指标，不是主指标的分母和分子。

审查建议是先明确并补上这条审计及验证连接，再用相同生产认证/模型窗口下的真实缺口做授权测量；不应以候选命中、预算消费或原型逻辑测试替代主指标。
