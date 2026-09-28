Status: done
Category: bug
Type: task

# 04 — OMO：同日的香港央票公告按设计被跳过，却在缺口清单里显示为拒收提示

来源：gap-sources 票 09 遗留 2（“OMO 操作量官网页 `official_context_table_schema_mismatch`”）。

## Comments

> *本段由 AI 在分流时生成。*

### 分流记录（2026-09-26）

**已核实：**

- 指标是 `CN_OMO_7D_AMOUNT`。被拒原件是 9/23 第 188 号公告，内容为 **2026 年第九期央行票据（香港）**，600 亿元，6 个月。表头是“期次、发行量、期限、中标利率”，不是逆回购表格，所以解析器拒收**是对的**。
- 这是设计内的行为：OMO 列表页同一天可以有几份公告，`release_urls` 把它们都列为候选。除最后一份外，`official_context_table_schema_mismatch` 会被吞掉，接着试下一份（`official_context.py` 的 OMO 候选循环）。但被跳过的那份公告仍留下一张被拒回执，缺口清单于是显示“rejected 提示”。
- 值仍持有属实：9/24 投放量 515 亿元，来自上一轮的 TuShare 资讯取数（中新经纬），同日官方取数的值与之一致。
- 更早运行里的同名拒收码对应的是栏目页 `/125475/index.html`，与这次不是同一个根因。所以“本规格前就有”的说法只对拒收码成立，对根因不成立。

详见 [Codex 调查](../research/codex-tool-liquidity-omo.md) 第 9–12 条。

**建议：** `bug`（只是提示噪声，不缺数），优先级低。定下方向后转 `ready-for-agent`。两种修法：

- **推荐：** 同日另一份公告如果被识别为不是逆回购公告，它的回执记为“非本指标公告/已跳过”一类的结局，不算拒收，缺口清单不再提示。
- 另一种：列表阶段按标题排除央行票据公告，不去抓取。但 `release_urls` 的注释说明这些公告标题相近，只能靠路径和解析区分，按标题过滤不可靠。

**顺带留意：** 9/28–10/8 央行将开展隔夜逆回购。如果某天只有隔夜操作、没有 7 天期，解析器要求有“7天”行，会拒收。那属于另一个问题，到时看真实运行再说，本票不处理。

**决定（2026-09-26 用户确认）：** 采用推荐修法，回执记为“已跳过”，不算拒收。转 `ready-for-agent`。

## Agent Brief

**Category:** bug
**Summary:** 同日非逆回购公告按设计被跳过时，不再记为拒收，也不在缺口清单里提示

**Current behavior:**
OMO 列表页同一天可以有几份公告（逆回购、央行票据，包括香港央票）。取数时把它们逐份当作候选，某份的表格结构不是逆回购表（`official_context_table_schema_mismatch`）就跳到下一份。这是设计内的行为，但被跳过那份的取数回执仍然记为拒收，缺口清单对已持有的 `CN_OMO_7D_AMOUNT` 显示 “rejected” 提示。例如 2026-09-23 的第 188 号公告：2026 年第九期央行票据（香港）。

**Desired behavior:**
- 同日的候选公告，只要不是最后一份且因表格结构不符被跳过，回执结局就记为能与拒收区分的“非本指标公告/已跳过”，不计入拒收，缺口清单也不提示。
- 当日所有候选都不符（包括最后一份）时，照旧拒收并出现在缺口清单里。这是真失败，不能被“跳过”掩盖。
- 其他拒收原因（任何不是 `official_context_table_schema_mismatch` 的错误）照旧拒收，照旧中止。

**Key interfaces:**
- OMO 公告候选循环（`release_urls` 给出的同日候选）：对被跳过的候选改用新的回执结局。
- 取数回执的入库结果或结局枚举：新增“已跳过”一类取值。缺口清单与报告里读取拒收提示的地方要认出它，不算拒收。

**Acceptance criteria:**
- [ ] 同一天有央票公告和逆回购公告：逆回购值入库；央票那份回执是“已跳过”，缺口清单没有拒收提示。
- [ ] 同一天只有央票公告（没有任何可解析的逆回购公告）：仍记拒收，缺口清单照旧提示。
- [ ] 候选抛出结构不符以外的错误时，行为不变。
- [ ] 已有的 OMO 公告解析用例全部通过。

**Out of scope:**
- 按标题在列表阶段过滤公告。
- 只有隔夜、没有 7 天期逆回购的日子怎么处理（9/28–10/8 看真实运行再定）。

### 实施记录（2026-09-28）

> *本段由 AI 在实施时生成。*

- 同日候选里不是最后一份、因 `official_context_table_schema_mismatch` 被跳过的公告，在解析处改抛 `CandidateSkipped`（`ValueError` 子类）。回执照旧 `state=failed`，但 `structure_check='skipped'`，`rejection_reason` 仍记原因码。缺口清单只读 `structure_check='rejected'`，因此不再提示。
- 最后一份候选（包括当日只有央票公告）照旧 `rejected`；其他错误照旧中止。
- 测试：`tests/integration/test_official_listing_pages.py` 用 9/23 的第 187、188 号公告真实原件，分别验证“跳过不提示”和“只有央票仍拒收”。
- 验收第 1–4 条：前两条由上述两例覆盖；其他错误行为不变、已有 OMO 用例全部通过（`test_official_listing_pages.py`、`test_omo_invalid_flow.py`）。
- 审查补正（2026-09-28）：检索账本在逐份候选之间只放行“已验证”的上一份回执，被跳过的央票公告会让下一份公告直接报 `retrieval_previous_acquisition_not_validated`，因此跳过在检索路径上并不生效（改动前就有这个问题）。现在 `structure_check='skipped'` 的上一份也放行，物理请求记为 `intermediate_candidate_skipped`。新增用例 `test_a_passed_over_notice_does_not_stop_the_next_under_the_retrieval_ledger`：去掉修复即失败。
