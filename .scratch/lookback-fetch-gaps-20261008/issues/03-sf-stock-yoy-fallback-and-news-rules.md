Status: done
Category: bug
Type: task

# 03：社融存量同比的补缺路径与资讯规则

## 现象

社融存量同比（v0015 社融主成员）缺 8 个月。补缺调用旧社融适配器后被拒收；资讯与 AI 规则没有社融存量同比的提取规则。

- 位置（读码）：`targeted_context.py:69`、`news_rules.py:382`。
- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md)；Tavily 当轮已达上限（16 次）。

## 待分流时确认

- 补缺优先走官方原件历史页，还是资讯／AI 检索；后者涉及检索预算。

## 验收草案

- [x] 社融存量同比有可用的补缺适配器，拒收原因若属契约问题则修正。
- [x] 资讯或 AI 规则能提取社融存量同比（若分流决定走这条路）。

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- 两层根因属实：补缺仍调用旧适配器，输出契约外的 `monthly_increment`（`targeted_context.py:69`、`tushare_context.py:619`），13 次单月 `sf_month` 均被身份契约拒收而直取成功；总量 `stock_yoy` 无资讯规则（`news_rules.py:382`），覆盖门禁又忽略它，AI 实际被调用 8 次（`metric_contracts.py:311`、`worker.py:800`）。
- 缺 8 个月中目标日一年读法缺 6 个月，另 2 个月服务更早回看。
- 修复：补缺复用正确适配器、补总量同比规则、规则覆盖按实际请求成员判断。约 3–5 模块。
- 无需用户决定（沿 ADR-0026 降级顺序与现有预算）。接在 02 之后。

### 2026-10-09 实施

- **补缺适配器**（`targeted_context.py`、`tushare_context.py`、`worker.py`）：新增 `reviewed_delivery(paths, metric_id, definition_version)`，判断目录是否登记了某指标的 TuShare 已审核交付。直取与定向补缺都用它：社融总量登记了就调 `social_financing_total`（只取 `inc_cumval` 年内累计、`stk_endval` 月末存量），不再调旧的 `social_financing`（多出契约外的 `monthly_increment`，累计值还被标成 `month`）。M1/M2 同属这类缺陷，一并修正：登记了就不取环比，旧路径会因 `m1_mom/m2_mom` 被身份契约整批拒收。只对实际匹配到的单个指标查定义；直取也从查全部八项改为只查社融、货币两项。
- **总量同比资讯规则**（`news_rules.py`）：新增 `CN_SF_TOTAL stock_yoy`，要求"社会融资规模存量为金额"后紧接"同比增长/下降 x%"，同一句里的分项同比不会被误取。真实夹具 `pbc_20260914_financial_statistics.json` 可取到 7.2%。
- **覆盖门禁**：`rules_cover(scope)` 改为按范围实际请求的成员判断。回看点名了成员的指标，按点名成员算；没点名的，按目录必需成员算，与选值口径一致。v0015 回看点名社融存量同比，原先只核对 `ytd_increment` 和 `stock_end`，误判为"可覆盖"，导致 AI 被调用 8 次却取不到值。现在点名成员没有规则时，不装配 AI。连带影响：回看只点名 GDP 总量实际同比时，规则能覆盖，会装配 AI（原先按 8 个必需成员判，不装配）。这仍是 ADR-0026 的末级，预算未改。
- **替身与测试**（修前均红、修后均绿）：新文件 `test_targeted_monthly_refetch.py` 覆盖累计期边界。一月、上年十二月、年中三期，断言请求字段、入库 accepted、年内累计从当年 1 月 1 日起算、存量按月；另有 M1/M2 不带环比。`test_news_rules_families.py` 的真实样本加入总量同比；新增总量与分项写在同一句的两种语序，分别得 7.2 与 5.0。"每条规则写的成员须属目录"一例原只认必需成员，现在也认回看可点名的成员（社融存量同比）。`test_ai_websearch.py` 新增四个参数测装配：GDP 只点名总量时装配 AI；含分项季度同比时不装配；社融同比有规则时装配；去掉同比规则（"规则补不齐"替身）时不装配。
- **验证**：受影响 20 个文件 335 例，334 passed、1 failed（2464 s，远超 3 分钟目标，未删测试）。失败的是 `test_gap_source_repairs.py::test_the_basket_is_chained_from_its_base_on_settlements`，属既有失败，归票 10。审查修复后，直接相关的 7 个文件 90 passed（122 s）。冒烟两例 2 passed（228 s）。重型两例经 `flock` 串行：`test_worker_registered_catalog.py` 2 passed（545 s，同时有票 10 的测试在另一 venv 并行；L04 记录为 445 s），`test_core_carry_forward.py` 2 passed（115 s）。改动文件上的 `ruff check`、`ruff format --check` 通过，`mypy`（4 个源文件）通过。
- **Codex 审查**：规格轴"阻断：无"；确认三项修复和三种替身都在，M1/M2 属相邻修复，没有改变历史期是否再请求 TuShare 的行为（票 10 范围）。标准轴阻断 1 条：原 `reviewed_deliveries` 查全部八项定义，目录缺任一项时补 CPI 也会抛错。已改为只查匹配到的指标，定向复审"阻断：无"。不采纳的非阻断意见：① 缺指标目录的替身没补，因为构造缺项目录成本高，而修复后不再查无关指标，读码可证。② 请求字段字符串断言对顺序敏感，这是有意为之，字段顺序本身就是请求的一部分。③ 月末日手工拼接只适用于当前三个样例，可以接受。
- **残余风险**：① 简写"社融存量同比增长 x%"（标题式、无"存量为金额"）不会取值，属漏取而非误取。② 定向补缺成功后，社融历史期仍会按期请求 TuShare（行为未变，限频耗时见票 10）；存量同比仍需官方页或资讯/AI 补，历史官方覆盖依赖 05。③ GDP 只点名总量同比的回看现在可能消耗 AI 时长，受现有运行预算约束。

