Status: done
Category: bug
Type: task

# 14：2025 年社融单独成报告，历史期选错稿；AI 候选只保留存量金额

## 现象（票 09 真实运行发现，2026-10-09）

run-8a3779cff80f6bd586a0 中，社融存量同比（`CN_SF_TOTAL measure=stock_yoy`）2025-07、2025-08 仍然缺失。这两个月不在社融主要成员的一年读法范围内（一年读法要求 2025-09 至 2026-08，已经齐全），只用于更早的回看。

- 官方渠道选中的是 116225 栏目中同月的"金融统计数据报告"（`retrieval_registry.py:85` 把社融指向这类报告）。2025 年 7、8 月的这份报告不含社融段落，解析时抛 `official_context_social_financing_components_mismatch`（`official_context.py:2467`）。同一栏目已读列表中另有"2025年7月社会融资规模存量统计数据报告"（`4405816f…`）和 8 月的对应报告，但它们没有被识别，请求数为 0。
- AI 候选 app.www.gov.cn 的引句含"431.26万亿元，同比增长9%"，返回的 `value` 却是 431.26。`ai_websearch.py:484` 只保留数值等于 `value` 的提取项，所以只留下了 `stock_end`，丢掉了 `stock_yoy`。验证记录写成 `model_usable`（`:566`），最终缺口检查却仍是 `candidate_validation_unresolved`（`:289`），两处记录的语义不一致。
- 不是 L02 的回归：`e10db1b` 之前同样会拒收缺段页面。
- 归属：选稿属于 L01、L05 历史定位范围内的遗漏；AI 只取金额属于 L03 补同比链路的遗漏。
- 只读调查：Codex（scratchpad `lfg-codex-gaps.out`），主会话已复核列表原件第 429 行的标题。

## 建议

在 2025-09 之前、社融单独发布的月份，补上"社会融资规模存量统计数据报告"的标题与解析，或按期选择报告类型。AI 补缺时按实际缺失的成员给出提示并采用结果；验证记录要反映真实的选值完整性。

## 验收草案

- [x] 用真实 2025-07 列表与社融存量报告原件做替身，能取到存量同比。
- [x] AI 候选的引句同时含金额和同比、而缺的是同比时，入库的是同比。

## Comments

### 2026-10-09 分流

按 goal-round2.md 预设决定实施。

### 2026-10-09 实施

**改动**
- `retrieval_registry.py`：新增 `EarlierRelease` 与 `RetrievalFamily.earlier`、`titling(period)`，用来登记"某期之前数据发布在另一份稿件里"。社融族登记为：2025-09 之前查询与选稿用"{year}年{month}月社会融资规模存量统计数据报告"，标题变体为"…月末…"（2017—2019 年写法）。从 2025-09（前三季度）起仍用金融统计数据报告。`search_query` 与 `title_variants` 都按期次取值，所以 Tavily、AI 的查询词也随之切换。货币、贷款结构不变。
- `official_listing.py`：`release_titles` 中的季度/半年/全年聚合标题改为按当期报告名生成，例如"2024年社会融资规模存量统计数据报告""2016年上半年社会融资规模存量统计数据报告"。货币与贷款仍然生成"…金融统计数据报告"，行为等价。
- 解析不用改：`official_context._parse_social_financing_live` 已经能处理只有存量段落的稿件。用真实 2025-07 原件实测，可得总量存量 431.26 万亿元、同比 9%，以及 8 个分项的存量与同比。
- `ai_websearch.py`：
  ① 提问前先做一次选值，取得实际缺失成员 `missing_members`。`_asked_members(scope, missing)` 从 scope 读取的成员里只保留仍缺的那些，提示词新增 `members` 字段列出它们。
  ② `_adopt` 先核对 CLI 给的数值确实是原句经规则读出的某个值（金额或同比都可以），再只采用原句中所缺成员的提取项。缺同比就入同比，已持有的金额不会再入库。原句只陈述已持有成员时，记 `incomplete_model_input`（不用 `rule_not_matched`，避免 Tavily 去重时把同一 URL 当作终局拒收）。
  ③ 全部候选采用完成后统一选值一次，再写候选验证记录：缺口补齐才记 `model_usable`；已入库但缺口仍不完整的记 `incomplete_model_input`。同时写入 `selected_claim_ids` 与 `missing_members`，与 Tavily 页面的口径一致，也与请求结果 `complete_model_input`/`candidate_validation_unresolved` 相互一致。回溯路径 `discover_event` 不变。
- 夹具：`official_listing/pbc_116225_11871-2_20261009.html` 取自本机运行库制品（acquisition-5f9b7028…，`35070319…`，复制后哈希一致）。`official_period_fallback/pbc_social_financing_stock_202507.html` 在 2026-10-09 01:13 UTC 用 curl 串行联网取一次（HTTP 200、无跳转，`b137eea7…`），因为运行库里没有该原件（真实运行从未请求过它）。两份都已在 README 登记。

**验收证据**
- 框 1：`tests/adapters/test_official_context.py::test_social_financing_stock_growth_before_september_2025_is_read_from_its_stock_report`。真实栏目第 1、2 页加真实存量报告：先翻到第 2 页，选中 `4405816f…`，再入库 2025-07 的 `stock_end` 4312600 和 `stock_yoy` 9.0。修复前，选稿会落到金融统计数据报告 `2972dbe4…`。选稿另有 `tests/adapters/test_official_listing_samples.py::test_social_financing_before_september_2025_is_selected_by_its_stock_report`（6 例，覆盖 2025-07、2025-08 选存量报告，2025-09、2025-10 选金融统计数据报告，货币与贷款不变）和 `…_under_its_earlier_titles`（3 例，"月末"、全年、上半年三种写法）。查询词由 `tests/retrieval/test_retrieval_registry.py::test_social_financing_is_searched_by_the_report_its_period_was_released_in` 覆盖。
- 框 2：`tests/integration/test_ai_websearch.py::test_the_member_a_lookback_misses_is_taken_from_a_sentence_stating_others_too`。用的是 run-8a3779… 中 Codex 的真实候选：引句同时含金额与同比，`value` 为 431.26。结果是提示只要同比，入库 `{"stock_yoy": 9.0}`，请求记 `verified/complete_model_input`，候选记 `model_usable`。另有三例：`…_neither_asked_for_nor_taken`（金额已经官方入库，scope 点名金额加同比时，只问同比、只新增一条声明）；`…_leaves_the_gap_incomplete_is_recorded_so`（未点名成员时，入库金额但缺年内累计增量，记 `incomplete_model_input` 并写出缺失成员）；`…_stating_only_members_the_gap_holds_fills_nothing`。

**测试**（`dev-venv-l13`）
- 红→绿切片：选稿与查询 7 例先红后绿；端到端取同比 1 例（去掉登记即红，请求落到金融统计数据报告）；AI 采用 1 例；验证记录 2 例；按缺失成员收窄 2 例（审查后补）。
- rebase 到 main（含 2a3935f、0effd27）后，受影响 23 个文件 393 passed（22:25，超出 3 分钟目标，主要耗时在 `test_retrieval_strict_path` 等集成用例的建库）。冒烟两例 2 passed（3:36）。重型 `test_worker_registered_catalog.py` 加 `test_core_carry_forward.py`（flock）4 passed（11:49）。
- 改动文件的 `ruff check`、`ruff format --check` 都通过。改动的 3 个源文件 `mypy` 通过。测试文件里只有既有报错（`test_ai_websearch.py` 4 处 `retrieval_ledger` 可空索引，`test_official_context.py` 5 处），都不在本票的新增行。

**审查**（Codex）
- 标准轴：阻断无。非阻断意见两条：① 成员命名不准，没有扣除已持有成员，已随规格轴阻断一并修正；② 原句不含目标成员时记 `rule_not_matched`，可能被 Tavily 去重当作终局拒收，已改为 `incomplete_model_input`。
- 规格轴：第一轮阻断 1 条，问题是 scope 成员包含已持有成员，被当成了缺失成员。已改为按提问前的选值缺口收窄，并补"完整 scope、已持有金额、缺同比"用例。定向复审结论为"阻断：无"，并确认回溯路径、未点名成员的 scope、RRR 由公告决定成员的语义都保留。
- 不采纳：规格轴提到验证记录反映的是整组候选处理后的缺口状态，不是每条候选单独能否补齐。这是有意为之：AI 的多个候选合起来才补齐一个缺口，如果逐条判断，会把有贡献的候选记成失败。

**已知残余与影响**
- 2025-09 之前的月份，官方路径现在只取存量报告，所以官方回退拿不到年内累计增量（`ytd_increment`）。该成员由 TuShare 已审核交付提供（票 03）；需要时，另一份"社会融资规模增量统计数据报告"仍未接入。
- 2015 年前后的季度标题（例如"2015年一季度社会融资规模存量统计数据报告"）可以按聚合标题选中；更早的年份没有核对样本。
- 同一句同时陈述多个所缺成员时（CPI 的同比与环比、RRR 的多个适用范围），现在会一次全部采用。原先只采用与 CLI 数值相等的那一项。这与资讯路径按规则全取的口径一致。
- 真实运行中 2025-07、08 是否取到，留给票 17 核验。
