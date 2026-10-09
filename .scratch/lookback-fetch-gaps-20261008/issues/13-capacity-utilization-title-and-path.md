Status: done
Category: bug
Type: task

# 13：产能利用率发布稿标题含"规模以上"，列表识别漏掉；正确地址又不在检索白名单

## 现象（票 09 真实运行发现，2026-10-09）

run-8a3779cff80f6bd586a0 中，产能利用率 2026-Q1（`quarter_rate`、`yoy_change`）仍然缺失。这是 17 项计数指标中唯一仍有缺期的主要成员。

- 本轮读过的统计局列表 `/sj/zxfb/index_6.html` 和 `/sj/zxfbhjd/index_11.html` 都列有 `./202604/t20260416_1963322.html`，标题是"2026年一季度全国**规模以上**工业产能利用率为73.6%"。登记的标题模板是"{year}年{quarter}全国工业产能利用率"（`retrieval_registry.py:74`），`release_url` 用前缀严格匹配（`official_listing.py:131`），所以漏识别。官方渠道最后记为 `official_context_release_link_not_found`。
- 2025-Q2 也是同样原因：正确链接 `t20250715_1960404.html` 已经出现在已读列表里，却没识别出来；扫描继续往下翻，直到统计局本轮 50 页额度用完，记 `listing_not_covered_page_limit`，最后由 Tavily 补齐。2025-Q3、Q4 也由搜索补齐。
- 检索补救也失败了：Tavily 与 AI 都找到了 `https://www.stats.gov.cn/zwfwck/sjfb/202604/t20260416_1963322.html`，但统计局主机只放行 `/sj/` 路径（`retrieval_registry.py:40`、`:185`；正文入口 `official_context.py:2875` 也有同样限制），所以记 `not_whitelisted`，没有下载。另一个 Tavily 候选是 2023 年的页面，被 `official_context_period_identity_mismatch` 正确拒收。
- 归属：L01 已把这一族纳入列表识别，所以这是 L01 范围内的遗漏。`/zwfwck/sjfb/` 白名单属于相邻的新问题。
- 只读调查：Codex（scratchpad `lfg-codex-gaps.out`），主会话已复核列表原件中的标题和模板。

## 建议

标题模板补上"规模以上"的写法，或改为能同时匹配两种写法。检索白名单与正文入口同步登记 `/zwfwck/sjfb/`，同时保留期次和正文校验。

## 验收草案

- [x] 用真实列表原件（含"规模以上"标题）做替身，能选出 2026-Q1、2025-Q2 的发布稿。
- [x] `/zwfwck/sjfb/` 下的统计局发布稿能通过白名单，并经期次校验。

## Comments

### 2026-10-09 分流

按 goal-round2.md 预设决定实施。

### 2026-10-09 实施

**改动**
- `retrieval_registry.py`：`RetrievalFamily` 新增 `title_variants`（同一发布稿的其他标题，只供列表选稿，检索仍用 `query_template`）与 `title_variants(metric_id, period)`；产能利用率登记 `{year}年{quarter}全国规模以上工业产能利用率`。统计局登记两个路径前缀 `/sj/`、`/zwfwck/sjfb/`，对全部统计局族生效（AI 路径的 `registered_host` 随之放行）。
- `official_listing.py`：`release_titles` 并入登记的标题变体；"解读／图解"等排除、同期多链接报"不唯一"的规则不变。
- `official_context.py`：正文入口 `_validate_source_identity` 改为按该族登记的路径前缀判断（取自注册表，不再硬编码 `/sj/`）；人民银行前缀仍为 `/`，行为不变。期次、发布时间与表格校验不动。
- 夹具：本机运行库制品 `/sj/zxfbhjd/index_11.html`（`6489b013…`，含 2026-Q1）、`index_28.html`（`00fa6afe…`，含 2025-Q2），复制后哈希一致；`/zwfwck/sjfb/202604/t20260416_1963322.html` 串行联网取一次（`d038b999…`，HTTP 200 无跳转）。均已在两个夹具 README 登记。

**验收证据**
- 框 1：`tests/adapters/test_official_listing_samples.py::test_capacity_utilization_is_selected_under_its_above_designated_size_title`（两例，真实列表选中 `202604/t20260416_1963322.html`、`202507/t20250715_1960404.html`）；旧标题写法仍可选中（`…_still_selected_under_its_earlier_title`）。
- 框 2：`tests/adapters/test_official_context.py::test_nbs_release_under_zwfwck_sjfb_is_fetched_and_held_to_its_period`（真实原件经正文入口入库，2026-Q1 当季 73.6、同比 -0.5）、`…_for_another_period_is_rejected`（按 2025-Q4 请求被拒，候选原因归为 `period_mismatch`）、`test_other_nbs_paths_stay_outside_the_release_entry`（`/zwfwck/` 其他路径、`/xw/` 仍拒）；`tests/retrieval/test_retrieval_registry.py::test_nbs_releases_under_zwfwck_sjfb_are_on_the_registered_host`。覆盖到组件级，未新增 Tavily／AI 全链路用例（v0001 目录无产能利用率，全链路留票 17 真实运行核验）。

**测试**（`dev-venv-l13`）
- 红→绿两切片：列表选稿 2 例先红后绿；白名单 3 例先红后绿。
- 受影响：`test_official_listing_samples`、`test_search_discovery`、`test_retrieval_registry`、`test_official_context`、`test_official_listing_scan`、`test_official_listing_pages`、`test_retrieval_strict_path`、`test_ai_websearch`、`test_search_evidence`、`test_retrieval_p2_lenient`、`test_media_page_values`、`test_official_full_run_fallback`、`test_capacity_column_completeness`：全部通过（前三个文件 115 passed，9 秒；其余 10 个 106 passed，5:05）。
- 冒烟两例＋`test_lookback_declaration`＋`test_official_negative_cache`：37 passed（11:58）。
- 重型 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py`（flock）：4 passed（10:44；与其他线的测试同时运行，比参考值慢）。
- `ruff check`、`ruff format --check` 通过；`mypy` 仅 `test_official_context.py` 原有 5 处报错（基线同为 5，均不在本票改动行）。

**审查**（Codex，各一次）
- 标准轴：阻断无。确认人民银行行为等价、各注册表消费者兼容、测试期望值来自原件。
- 规格轴：阻断无。三处失败链都已修复，src 内没有其他 `/sj/` 限制会拦住发布稿；未见放宽过度，也没有超出预设决定。非阻断：同一期两种标题如果指向不同 URL，会报"链接不唯一"而不是任选一个。这是有意保留的保守行为，不另加测试。
