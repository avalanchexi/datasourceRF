# 01: 人民币中间价取得

**What to build:** 10-15 中间价已发布却只能沿用 10-14（决定 3）。使媒体句式"人民币兑美元中间价报……"可解析（保留统计期、币种、报价方向校验）；央行中间价栏目登记为可解析列表，列表页按目标日跟进当天公告正文；获取尝试的失败原因区分首因与负缓存拦截。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 用 10-15 财联社页面原件做夹具，解析得 10-15 中间价 6.7253
- [x] 用央行栏目列表页与公告原件做夹具，经官方直连跟进得到当天中间价（栏目页为原件；副本无 10-15 公告原件，见 Comments）
- [x] 完整运行（检索降级链用夹具）目标日 10-15 持有 10-15 中间价，不再 one_period_behind_carried
- [x] 负缓存拦截与首因分别记录，可在缺口条目与数据链路页读到
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

**改了什么**（分支 `wg-01`，已合入 worker-gaps 7236209）

- 媒体句式：`news_rules` 的 `pbc_usdcny_central_parity` 家族新增一条规则，识别"人民币兑/对美元中间价报 X"与"美元兑/对人民币中间价报 X"；仍只取日频（句中或之前写明的日期须是缺口那天），币种限美元，数值后接"美元"的（反向报价）不取。`NEWS_RULES_VERSION` 未升（沿用历次规则补充的做法）。
- 官方直连：`official_listing.release_listing` 把央行"人民币汇率中间价公告"栏目（`…/125925/` 与 `…/125925/index.html`，即目录登记的地址）登记为列表页；`retrieval_registry` 给该家族加标题变体"{date}中国外汇交易中心受权公布人民币汇率中间价公告"（搜索查询不变），列表按目标日选出当天公告再取正文。检索降级链顺序未改。
- 首因与负缓存：`RetrievalBudgetBlocked` 带上被复用的那次请求（`reused_request_id`）；搜索候选被负缓存拦下时原因记 `negative_cache_active`（其余拦截仍记 `retrieval_blocked`），候选校验行的 `download_request_id` 记那次请求，首因由它的回执拒收原因（无则请求分类）读出（`retrieval_ledger.first_cause`）。未改表结构、未加迁移。
- 可读处：⑦ 缺口条目候选写"（被负缓存拦下，首因 …）"（`dashboard.candidate_reason`）；数据链路页"候选校验与时效"表的"说明"列原先读 `classification`（候选校验行没有此字段，一直为空），改为同一中文原因＋首因。原因文案在 `wording.REASON_LABELS`：`negative_cache_active` 已有；新增两个首因码 `official_context_usdcny_quote_missing`（官方页未见美元中间价）、`official_context_period_identity_mismatch`（官方页日期与所需期不符）。

**夹具**（`tests/fixtures/central_parity/`，README 记来源与 SHA256，均从 `/tmp/pring-cb-real-20261016` 原样复制）

- 财联社 10-15 页面原件（`cls.cn/detail/2505221`，6.7253）。
- 央行中间价栏目第 1 页原件（10-16 08:07 UTC 取得，列有 10-15 公告链接）。
- **副本里没有 10-15 公告正文原件**：当次运行把栏目页当公告解析失败后从未打开它。副本里唯一的公告原件是 4-30 的（9-30 搜索误中所存）。因此：4-30 原件用于"真实公告页能解析"与"跟进到的公告是别日的 → 首因 period_identity_mismatch"两个用例；需要 10-15 公告正文的用例在测试里按 4-30 原件版式自写正文（值取财联社同日 6.7253），文件头注明非原件。未去外网抓取。

**测试（先红后绿）**

- 已存原件解析 `tests/retrieval/test_central_parity_media_wording.py`（6 例；先红：rule_not_matched）。
- 官方直连 `tests/integration/test_central_parity_official_listing.py`（2 例；先红：official_context_usdcny_quote_missing）。
- 完整运行检索 `tests/integration/test_central_parity_full_run.py`（3 例，FullRunRetrieval＋record_run_freshness＋gap_list，与 `test_official_listing_pages` 同一先例）：官方栏目跟进得 10-15、无缺口；公告不可得时 Tavily 找到财联社页得 10-15、无缺口；公告为别日时搜索回到栏目被负缓存拦下，缺口条目 `retrieval_failed`，候选 `{reason: negative_cache_active, first_cause: official_context_period_identity_mismatch}`，数据链路页可读"被负缓存拦下，首因 官方页日期与所需期不符"。说明：测试模型除中间价外什么都不持有，16 次 Tavily 额度会先被其他缺口用完，测试把本次运行的 Tavily 上限调到 1000（10-15 实跑时中间价仍有额度）。
- 首页渲染 `tests/web/test_gap_first_cause.py`（⑦ 候选原因与首因）。
- 受影响：检索/适配器/web 12 文件 305 passed（20 秒）；集成 16 文件（缺口清单、检索台账、搜索证据、负缓存、官方列表、媒体页、严格路径、产能、P2 宽松、AI 检索、注册模型输入、社融/货币回退、仓单）336 passed（685 秒，排 heavy 锁 595 秒）。
- 两项必跑冒烟 2 passed（43 秒）；改了目录来源，加跑 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 4 passed（389 秒）。
- 改动文件 `ruff check`、`ruff format --check` 通过，`mypy -p pring_cycle` 通过。合入 worker-gaps 后 `ruff check` 报 `wording.py:63` E501 一处，来自 7236209（wg-05 的 `stage_name` 文档串），非本票改动，未动。

**遗留／待主 agent 知悉**

- 栏目登记为列表后，`full_retrieval` 对中间价的较早交易日缺口也会经栏目跟进（`EARLIER_SESSION` 且有列表时发现发布），历史缺几天就多几次央行请求（每页 20 条、受每站 50 页限额约束）；每次运行多读一次栏目首页。
- 首因只在负缓存由同一缺口的较早请求设下时可得；按主机设下或旧版负缓存表命中时没有首因，只显示"被负缓存拦下"。
- AI 检索候选的拦截原因也随 `candidate_rejection_reason` 区分出 `negative_cache_active`，但未记首因（本票只接了检索候选校验路径）。


### 2026-10-18 审查修复（wg-07）

审查 Spec 4：别的缺口的请求设下的主机级负缓存（或同页 403）拦下候选时，判定把那次请求记为首因来源（不绑到本缺口、不改表结构）；`official_context_source_http_status_invalid` 加中文（3c825aa）。详见 [../acceptance.md](../acceptance.md)。
