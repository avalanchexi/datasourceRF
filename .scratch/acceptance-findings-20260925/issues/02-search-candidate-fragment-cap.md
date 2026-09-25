Status: done
Type: task

# 02 — 检索候选整页交给登记解析器

**问题：** `CN_TOOL_LIQUIDITY_MONTHLY` 本轮央行栏目 `/5727710/` 与 9/2 发布页已可访问，但均被拒（记为 `parse_failed`，底层 `official_parser_fragment_too_large`）。检索路径（`search_evidence.py`）对重抓原文的**全文**设 1600 字上限；央行页面仅导航即超出（9/2 页 3794 字）。去掉上限后该页解析出 24 值（8 工具 × 投放/回笼/净投放），发布时间 2026-09-02 17:00。

**根因：** 1600 字片段上限来自 ADR-0005“最小化证据片段降低模型 Token”（v1 规格第 25 条）。ADR-0023 已取代 ADR-0005：检索只是到达白名单页面的传输手段，按网址重抓原文由登记确定性解析器解析——与官方直连同一解析，直连路径从无此上限。

**修复：** 删除 `parser_text_limit` 参数（`official_context.py`、`official_lpr.py`、`search_evidence.py`）；文档字节上限 `MAX_OFFICIAL_CONTEXT_BYTES` 不变。原测试 `test_candidate_parser_limit_preserves_original_without_claiming_complete_fields` 断言旧行为，改为 `test_candidate_page_is_parsed_whole_however_long_its_surroundings`（超长页面整页解析并采纳；摘要 1800 字预算断言保留）。

- 同因还挡住了社融：`CN_SF_COMPONENTS` 候选央行 9/14 页（`pbc_social_financing`）底层同为 `official_parser_fragment_too_large`，去掉上限后解析出 27 值（CN_SF_COMPONENTS、CN_SF_TOTAL），发布时间 2026-09-14 17:00。
- 栏目页 `/5727710/index.html` 仍 `official_context_table_schema_mismatch`，属列表页，拒收正确。
- 摘要合计 1800 字预算同源于 ADR-0005，本票未动；如需复议另立。

## Comments
- 2026-09-25 验证（01–03 合并一轮，dev-venv 重装后）：受影响 28 个文件 `check.py quick` 569 例过，用时 2137.8 秒（超 180 秒目标：文件多且含检索集成用例，照实记录）；切片冒烟 2 例过，86 秒；完整目录正例 `test_worker_registered_catalog.py` 1 例过，133 秒；三核心反例 `test_core_carry_forward.py` 3 例过，185 秒。C 盘始终 67G 余量。
