Status: done（待真实运行验证）
Category: bug
Type: task

# 03 — 工具流动性：央行表格把行名改成“隔夜、7天期逆回购”，契约不认，整批入库失败

来源：gap-sources 票 09 遗留 2（“工具流动性检索未通过，本规格前就有的问题”）。

## Comments

> *本段由 AI 在分流时生成。*

### 分流记录（2026-09-26）

**已核实：**

- **它从来没有持有过。** `source_claim` 中 `CN_TOOL_LIQUIDITY_MONTHLY` 为 0 条。三轮真实运行（f26f88…、15542949…、64209ab0…）的缺口清单里都是 `retrieval_failed`。acceptance-findings 02 只去掉了片段上限，gap-sources 规格第 140 行说它“已消除”，与运行库不符。
- 检索确实命中了 9/2 发布页（`/5727710/2026090214213398506/`），原件也没变过（三轮 SHA256 都是 `4d104698…`）。解析通过，规范化结果是 `period=2026-08`、24 个标量、发布时间 9/2 17:00，但没有产生任何声明，候选最后记为 `parse_failed`。
- **根因：** 原件表格里的行名是“隔夜、7天期逆回购”（我已亲自在原件中确认），指标契约 `CN_TOOL_LIQUIDITY_MONTHLY` 的成员却写死为“7天期逆回购”。按 Codex 读码推断，这会触发身份不符，整批在写入前校验失败，另外 7 个工具的值也跟着丢了。背景：央行已开展隔夜逆回购，并公告 9/28–10/8 做万亿级隔夜逆回购，表格把两类合成了一行。
- **诊断性缺陷：** 具体的拒收原因没有持久化，只留下 `ValueError`，又被归并成 `parse_failed`，所以从运行库看不出是成员名不符。
- 官方栏目入口上一轮返回 403，负缓存到 9/27 00:05，本轮没有直连。这不是根因：检索已经把发布页送到了。

详见 [Codex 调查](../research/codex-tool-liquidity-omo.md) 第 2–8 条。

**建议：** `bug`，定下成员名后转 `ready-for-agent`。需要你拍板一件事：新行名“隔夜、7天期逆回购”与旧行名“7天期逆回购”，是**同一个成员**（口径随央行扩展，序列连续），还是**另立成员**（旧月份仍是 7 天期，新月份起是隔夜加 7 天期，两段序列不直接可比）？推荐前者：成员改名为能同时覆盖两者的稳定标识，维度里保留原件行名。月度报告看的是“短期逆回购投放”，与央行表格的归口一致。

另附一条验收准则：校验失败的具体原因码要能落到候选结果或回执上，不再只剩 `parse_failed`。

**决定（2026-09-26 用户确认）：** 两个行名是同一个成员，序列连续。转 `ready-for-agent`。

## Agent Brief

**Category:** bug
**Summary:** 工具流动性契约认“隔夜、7天期逆回购”与“7天期逆回购”为同一成员，并让校验失败原因可追溯

**Current behavior:**
`CN_TOOL_LIQUIDITY_MONTHLY` 的官方成员契约（`OfficialMember`，维度 `tool` × `measure`）写死了“7天期逆回购”。央行自 2026-08 的月度表格（9/2 发布）把这一行写成“隔夜、7天期逆回购”，解析器原样保留行名，成员身份核对失败，这一期 24 个标量一个都没入库。到目前为止这个指标从未持有，三轮真实运行都是 `retrieval_failed`。校验失败的具体原因码没有持久化，只留下 `ValueError`，候选又被归并记为 `parse_failed`。

**Desired behavior:**
- 原件行名为“7天期逆回购”或“隔夜、7天期逆回购”时，都归到同一个稳定成员，前后月份接成一条连续序列。原件行名作为来源事实可追溯（例如保留在规范化结果或回执里），但不参与成员身份。
- 其余 7 个工具的成员不变。行名是这两者之外的新写法时，仍然拒收，不做模糊匹配。
- 候选页面解析通过、却在契约或身份校验时失败时，具体原因码（如 `registered_official_source_identity_mismatch`）要落在候选结果或回执上，从运行库能直接看出是哪一类校验失败。

**Key interfaces:**
- 指标契约里 `CN_TOOL_LIQUIDITY_MONTHLY` 的成员清单：逆回购短期那一项改为能覆盖两种行名的稳定标识，并加上原件行名到成员的映射。这是契约或定义的变更，按项目的目录与模型版本惯例处理（ADR-0012）。
- 央行工具流动性解析器：输出行名到成员的归一。
- 检索候选的结局记录：解析通过但入库校验失败时，保留底层原因码。

**Acceptance criteria:**
- [ ] 用 9/2 发布页的真实原件（或按它构造的夹具）解析入库，得到 `period=2026-08` 的 24 个标量，发布时间为 2026-09-02 17:00。
- [ ] 行名为“7天期逆回购”的旧版表格，解析出的成员与新版相同。
- [ ] 两者之外的行名（例如“14天期逆回购”）仍然拒收。
- [ ] 身份或契约校验失败时，运行库里能查到具体原因码，而不只是 `parse_failed`/`ValueError`。
- [ ] 真实完整运行后，工具流动性不再出现在缺口清单里。

**Out of scope:**
- OMO 逐日指标（`CN_OMO_7D_AMOUNT`/`CN_OMO_7D_RATE`）对隔夜逆回购的处理（见票 04 的附注）。
- 央行栏目入口 403 的负缓存策略。

### 实施记录（2026-09-28）

> *本段由 AI 在实施时生成。*

- **稳定成员：** 契约里原“7天期逆回购”一项改为 `短期逆回购`（`metric_contracts.official_source_members`）。解析器只把两个已知行名“7天期逆回购”“隔夜、7天期逆回购”归到它（`official_context._TOOL_LIQUIDITY_ROW_MEMBERS`，按去空白后的全文精确匹配），其他行名原样保留，因此在契约身份校验时被拒，不做模糊匹配。改名没有历史数据要迁移：这个指标此前一条声明都没有持有。
- **原件行名的追溯：** 行名不进入成员身份。原件照旧按 ADR-0022 保留，声明的 `source_reference` 指向原件哈希，从原件可以查到当期实际行名。没有给规范化结果新增字段：`ParsedOfficialContextRelease` 的规范化哈希被所有官方家族的重建复核引用，加字段会让全部既有回执失配。
- **原因码可追溯：** `ingest_acquired_official_release` 在入库成功或失败后都写回执的 `ingest_result`／`ingest_rejection_reason`（沿用 gap-sources 票 03 的机制）。官方直取失败的 `retrieval_attempt` 元数据另加 `reason`（仅 `ValueError`），缺口清单的 `ingest_rejected` 因此能显示具体原因码，而不只是 `ValueError`。
- **测试：** `tests/models/test_registered_model_inputs.py`
  - `test_the_overnight_and_7_day_reverse_repo_row_continues_the_7_day_member`：9/2 发布页真实原件（`evidence-13/4d104698…`），24 个标量，`period_end=2026-08-31`，发布时间 9/2 17:00（北京），`短期逆回购` 净投放 −6415。
  - 7 月真实原件（旧行名）的参数化用例改为断言同一成员 `短期逆回购`。
  - `test_an_unknown_reverse_repo_row_is_refused_and_the_receipt_says_why`：把行名改成“14天期逆回购”，入库拒收，回执为 `("rejected", "registered_official_source_identity_mismatch")`。
- 验收最后一条（真实完整运行后不在缺口清单里）待下次真实运行确认。
