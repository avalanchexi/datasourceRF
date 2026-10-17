# 13: ⑦ 展示修正（原因码中文与说明）

**What to build:** 决定 27（第五轮）。⑦"数据说明与解读"在 10-15 投影上仍写原因码与误导说法（截图 `screenshots/1015-home-reading-light-1440.jpg`；根因调查 scratchpad `accept-1017/q3-out.md` 第 1、3、6 条）。只改前端：

1. 原因码中文：缺口与检索未通过条目里的原因码（如 `period_not_requested`、`one_period_behind_carried`、`rule_not_matched`、`period_mismatch`、`negative_cache_active`、`listing_not_covered` 等，以投影中实际出现的全集为准）经一张中文对照表显示，例："未请求（等待发布）""落后一期，沿用上一期"；指标写中文名为主、代号为辅（`wording.display_name`）；未映射原因码显示原值。对照表一处维护（与 `wording` 同处）。
2. "无网页补缺渠道"改为"未配置额外网页检索补缺"。
3. 旧投影无完整度口径时写"该投影生成时尚未提供此统计"。
4. "目标日 … ；时效截至 …"旁加一句："目标日决定分析日期，时效按运行冻结时点判断"。
5. 非典型组合时，⑦ 与阶段事件里"阶段变化记为缺口"类表述改写为"非典型组合，暂无正式阶段"（AI 报告正文本身不改，那是 Worker 批次）。

**Blocked by:** None（基于 `cockpit-layout` 最新）

**Status:** done

- [x] 10-14、10-15 两份投影的 ⑦ 不再出现英文原因码（未映射值除外）；指标名中文为主
- [x] 2–5 条文字按上述出现
- [x] `dashboard_page` 测试断言中文原因、说明句与旧投影提示；受影响 Web 用例、两项必跑冒烟通过

## Comments

### 2026-10-17 实施

**改了什么**

- `wording.REASON_LABELS` 与 `reason_label()`：原因码中文对照表，与显示名对照表并列、一处维护；未映射回退原值。收入缺口行原因（`not_held`、`one_period_behind_carried`、`two_or_more_periods_behind`、`period_not_requested`、`listing_not_covered`、`restricted_license` 等）、发布门禁原因（`awaiting_release`、`earlier_session_not_searched`、`unknown_release_configuration`、`negative_cache_active`）、官方列表停读原因、候选未采纳原因。原 `dashboard` 里的 `CANDIDATE_REASON_LABELS`、`RELEASE_GATE_LABELS`、`LISTING_STOP_LABELS` 并入该表后删除。**B 批次 02–04 新增原因码只在 `REASON_LABELS` 加一行**；"等待发布"分组标题属缺口分类，在 `dashboard.GAP_CATEGORY_LABELS`。
- `wording.metric_label()`：行文中的指标写"中文名（代号）"，无中文名只写代号。
- 缺口行（`dashboard._gap_row`，⑦ 预览、全部缺口抽屉、报告页共用）：原因经对照表；原因为 `period_not_requested`／`listing_not_covered` 且带期明细时由明细代替（"未请求 2026-09（等待发布）"，不再重复）；"无网页补缺渠道"→"未配置额外网页检索补缺"；失败品种原因也经对照表。
- 完整度：⑦ 无 `coverage` 时写"两种完整度口径：该投影生成时尚未提供此统计。"（`coverage_table` 加 `absent` 参数；数据链路页沿用原文案，不在本票范围）。
- 时效行后加"目标日决定分析日期，时效按运行冻结时点判断。"
- 非典型组合：`wording.stage_change_label()`；AI 解读下方加"阶段变化：非典型组合，暂无正式阶段"（仅报告已验证结果为 `change=gap` 且 `reason=noncanonical_combination` 时）；报告详情抽屉加"阶段变化"一项。AI 正文不改。
- 发布日历抽屉（⑦ 内）的事件状态也经对照表（`awaiting_release`→"等待发布"）。

**实测（隔离副本，8113 只读起站，已停）**

- 10-15（`/tmp/pring-cb-real-20261016`）：⑦ 显示"两种完整度口径：该投影生成时尚未提供此统计。"；"P1 社融存量（CN_SF_TOTAL）：未请求 2026-09（等待发布）"；"P2 美元兑人民币中间价（CN_USDCNY_CENTRAL_PARITY）：落后一期，沿用上一期（应有期 2026-10-15，持有 2026-10-14）；候选 …（解析规则未命中）；…（统计期不符）；…（请求被缓存或预算拦下）"；"阶段变化：非典型组合，暂无正式阶段"。⑦ 可见文字里剩余的下划线代号只有 AI 正文里的 `index_daily`、`fut_index_daily`、`stage_iii` 与适配器名 `codex_cli`。截图 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl13/1015-reading-light-1440.png`。
- 10-14（`/tmp/pring-ui-real-20261015`）：完整度表照常；三条缺失为中文名＋"未请求 … （等待发布）"＋"未配置额外网页检索补缺"；剩余代号只有适配器名 `codex_cli`、`claude_code_cli`。截图 `/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl13/1014-reading-light-1440.png`。
- 两份投影实际出现的原因码全集：`period_not_requested`、`one_period_behind_carried`、`awaiting_release`、`rule_not_matched`、`period_mismatch`、`retrieval_blocked`，均已映射；两库全部历史投影另见的技术错误串（如 `eia_history_html:acquisition_time_invalid`、`<urlopen error …>`）按原值显示。

**测试**

- 新增 `tests/web/test_reading_wording.py` 7 例（`dashboard_page`）：中文原因与指标名、未映射回退原值、网页补缺说法、旧投影完整度提示、时效说明句、非典型阶段变化（含典型组合不加注）、日历状态中文。
- 改写过时断言：`tests/web/test_reading_section.py`（3 处）、`tests/web/test_conclusion_board_noncanonical.py`（1 处）、`tests/integration/test_gap_list.py`、`tests/integration/test_unsearchable_gaps.py`（"无网页补缺渠道"）。
- 合并 `cockpit-layout`（70563bf，快进）并重装后：受影响 tests/web 全部 17 个文件＋5 个缺口相关集成文件 238 passed（261 秒，另等锁 811 秒）；两项必跑冒烟 2 passed（50 秒）。改动文件 ruff check／format 通过；mypy 对改动文件 0 错（同批检查中其他文件 59 个错误与改前基线相同）。

**遗留**

- 第 2、4 两条的 TDD 未严格先红：网页补缺说法在第 1 切片已顺手改，测试补写后直接通过。
- AI 正文里的"阶段变化记为缺口"、`stage_iii`、`tushare:index_daily` 仍原样显示，属 B 批次 05。
- 数据链路页"数据完整度与未完成期口径"缺 `coverage` 时仍写"该版本未提供……"，未改（不在本票范围）。
