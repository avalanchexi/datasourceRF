# Codex 只读调查：工具流动性与 OMO 拒收（2026-09-26，run-64209ab01ac75439cc8c）

1. **结论：工具流动性没有证据表明“消除后又回归”；OMO 则确实仍持有值。** SQL 查询三轮 `analytical_dataset.cycle_overview.gap_list`：`run-f26f88cbd9e0681f397a`、`run-15542949d737d6b62707`、`run-64209ab01ac75439cc8c` 均有工具流动性 `retrieval_failed`；后两轮 OMO 拒收来自香港央票公告，不能与早先“栏目页误作公告解析”视为同一根因。

2. **A／本轮获取链：官方直连被负缓存拦截，Tavily 找到候选但全部未采用。** SQL：本轮 `run_retrieval_attempt.sequence=743–749` 依次为 local `not_found`、TuShare `not_configured/targeted_tushare_family_unavailable`、资讯 `not_configured`、official `not_attempted/negative_cache_active`、Tavily `candidate_source/candidate_validation_unresolved`、Exa `not_attempted/tavily_quota_available`、AI WebSearch `not_configured`；实际搜索词为“2026年8月中央银行各项工具流动性投放情况”。

3. **官方入口失败与 9/2 发布页失败是两次不同尝试。** 入口 `https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/` 本轮对应 `acquisition-8598a4e1b4514f1ea3b59dba67164a12`，错误为 `RetrievalBudgetBlocked`；上一轮同入口实际返回 HTTP 403／`forbidden_unknown`，缓存到北京时间 9/27 00:05（SQL：`acquisition_request` 联查 `retrieval_physical_request`）。

4. **候选①确实命中 9/2 发布页，页面解析成功，后续语义校验失败。** URL：`https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026090214213398506/index.html`；SQL：本轮候选结果 `not_model_usable/parse_failed`，下载请求分类 `semantic_validation_failed`，但取数 `acquisition-2ea02b682d9d449e9bbb024a2ab338ef` 已是 `validated/structure_check=passed`，`rejection_reason=NULL`，没有产生 claim。

5. **候选②③均因该指标未登记媒体取值规则而被拒。** URL 分别为 `https://finance.sina.com.cn/jjxw/2026-05-07/doc-inhxahrf8349883.shtml`、`https://finance.sina.com.cn/jjxw/2026-04-02/doc-inhtazrx7827314.shtml`；SQL：均为 `not_model_usable/rule_not_matched`，无下载请求、无 claim，读码可见这一分支在抓取正文前直接拒绝（`src/pring_cycle/search_evidence.py:1014`）。

6. **A／根因是工具成员名称不匹配〔读码推断〕，不是期间不符。** 原件写“隔夜、7天期逆回购”，解析器原样保留，而契约只接受“7天期逆回购”；会触发 `registered_official_source_identity_mismatch`，整批写入前校验失败，因此其余成员也未入库（原件 `~/.local/share/pring-cycle/artifacts/sha256/4d/4d104698df655c19c27e4a697ef4bd55cc1c0b30ad9aae265e7db3c955bc90c2:394`；`src/pring_cycle/official_context.py:2029`；`src/pring_cycle/metric_contracts.py:238`；`src/pring_cycle/source_contract_review.py:355`；`src/pring_cycle/evidence.py:522`）。该具体异常文本未持久化，现有记录仅保留 `ValueError`，再被归并为 `parse_failed`（`src/pring_cycle/search_evidence.py:497`）。

7. **片段上限修复有效，但“工具流动性已消除”的说法不获运行库支持。** SQL：更早轮的同页拒收码为 `official_parser_fragment_too_large`，后两轮已通过解析，且三轮原件 SHA256 完全相同，均为 `4d104698…bc90c2`；所以没有本次页面变化或未命中发布页的证据。后两轮保存的规范化原件均为 `period=2026-08`、24 个标量、`release_at=2026-09-02 17:00+08:00`，与本轮 SQL `due_period=2026-08-31` 一致（规范化原件 `~/.local/share/pring-cycle/artifacts/sha256/e3/e324713cf1f073f5948ae78786ad05bc4cf58018190af7de7c1651cb1215bd7f:1`）。

8. **A／当前没有已持有的最新一期，也没有已入库值的发布时间。** SQL：`SELECT count(*),max(period_end),max(release_at) FROM source_claim WHERE metric_id='CN_TOOL_LIQUIDITY_MONTHLY'` 返回 `0,NULL,NULL`；本轮 `batch_freshness` 也是 `status=missing,held_period=NULL`，9/2 发布的八月数据目前仅存在于原件及解析产物中。

9. **B／对应指标为 `CN_OMO_7D_AMOUNT`；本轮拒收的是第188号香港央票公告。** URL：`https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026092311141529051/index.html`；SQL：`acquisition-f55c23262e8444e584d7114b6c8747b7`，请求期间 `2026-09-23`，解析器 `official-context-parser-v0004`／家族 `pbc_omo_notice`，拒收码 `official_context_table_schema_mismatch`，原件哈希 `d6c80148…332dd7`。

10. **该原件属于另一种业务表，拒收符合解析器限定。** 解析器接受六列表头“操作日、品种、期限、中标利率（%）、投放量（亿元）、到期量（亿元）”，或逆回购实页的三／四列结构：首格压缩文本含“逆回购操作情况期限”、末两列为“投标量、中标量”，并要求“7天”行（`src/pring_cycle/official_context.py:1764`、`:1775`）。实际为“期次、发行量（人民币）、期限、中标利率”，内容是“2026年第九期央行票据（香港）、600亿元、6个月（182天）、1.37%”（原件 `~/.local/share/pring-cycle/artifacts/sha256/d6/d6c80148468bc0b0708becfc4ef210f9af96caad82bfdb5761eb254b3b332dd7:355`、`:361`）。

11. **B／“仍持有”属实：本轮选中 2026-09-24 的投放量 515 亿元，来自上一轮 TuShare 资讯取数。** SQL 联查本轮 `macro` 投影及 `source_claim`：选中 claim `af747922…780663`，发布时间为北京时间 **9/24 09:50:30**，取数 `acquisition-9506370555a24ac09266c64068468630` 属于 `run-15542949d737d6b62707`；`claim_matched_quote` 确认来源为中新经纬。另有早先官方取数 `acquisition-e4e2b2a9cf5249b79a6b4f97f5997e0f` 保存同日同值、官方发布时间 **09:20:30**；投影中的 **09:15** 是推定公开可用时间，不能当作实际发布时间。

12. **B／拒收并非每轮发生；“本规格前已有”只对同名错误成立，不能证明当前根因早已发生。** SQL 按运行统计 OMO 的该拒收码：`run-f26f88cbd9e0681f397a=0`，上一轮和本轮各 `1`，且后两轮 URL、原件哈希相同；更早的 `run-a0418ed439ef25c9e00c`、`run-a9661509d85921c99eef` 已各有一次同码，但对象都是 `/125475/index.html` 栏目页。〔读码推断〕当前列表逻辑会逐份尝试同日公告、遇此码继续下一份，因此再次遍历 9/23 时可能重复记录香港央票拒收，但不是每轮必然发生（`src/pring_cycle/official_listing.py:119`；`src/pring_cycle/official_context.py:798`）。
