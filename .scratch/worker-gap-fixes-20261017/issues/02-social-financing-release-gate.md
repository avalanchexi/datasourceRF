# 02: 社融发布门禁按成员判断

**What to build:** 9 月社融 10-14 已发布，⑦ 却写"未请求 2026-09（等待发布）"（决定 2）。同一发布事件已取得可靠已发布证据时，估算门禁不再拦其他成员；门禁按成员评估；估算门禁未到时每次运行允许查一次官方目录发现提前发布；⑦ 写出已取得与仍缺的成员（原因文案进票 A13 建的中文对照表）。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** done

- [x] 完整运行：社融总量当期已持有时，存量同比等成员被请求，不再整期 period_not_requested
- [x] 估算门禁未到期时，运行内对官方目录探查一次
- [x] `awaiting_release` 仍只用于发布判定，不进证据时效
- [x] `dashboard_page` 断言 ⑦ 写出社融已取得与仍缺成员
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

分支 `wg-02`，已三次并入 `worker-gaps`（B01、B03、B04，冲突在本分支解决，三边行为都保留）。

**改了什么**
- 发布门禁（`worker.retrieval_release_states`，`_retrieval_release_status` 由它汇总）：逐个指标判定；同一补缺范围（同一发布事件、同一期）里任一指标持有截止前可知的已校验证据，就视为该次发布已出，估算门禁不再拦同组其他指标。10-15 的情形：TuShare 已交付 9 月社融存量和累计增量，`CN_SF_COMPONENTS` 和存量同比不再被"10-21 估算"拦住整期。定向运行共用这条规则。
- 目录探查（`FullRunRetrieval._gate`）：`awaiting_release` 并入只读官方栏目的发现集合，有栏目的范围在完整运行里各查一次（与较早交易日、未登记规则走同一条路，只开官方渠道，不开检索）。栏目未列出时不开其他渠道。
- 缺口清单：最终计划的未完整期带上 `held_members`；某指标**最新**计划期部分持有时，缺口行附 `members_missing`（期、已取得、仍缺）。⑦ 写成"2026-09 已取得 期末存量、累计增量，仍缺 存量同比"。新原因码 `members_missing`（部分成员未取得）加在 `wording.REASON_LABELS`；`MEMBER_NAMES` 补社融存量三个成员中文名。
- `awaiting_release` 只用于发布判定，`freshness` 的 current/stale 未改；不新建模型版本，不改预期表。

**测试**（先红后绿）
- 完整运行：`test_official_social_financing_fallback.py::test_a_release_the_run_already_holds_part_of_is_not_held_back_by_its_estimate`、`::test_a_release_not_due_by_its_estimate_is_looked_for_once_on_its_official_column[True/False]`；`test_full_run_retrieval.py::test_a_release_partly_held_lists_the_members_taken_and_those_still_missing`（Worker 完整运行到投影缺口清单）。
- 首页：`tests/web/test_reading_release_members.py`（`dashboard_page` ⑦ 文本）。
- 并入 B01 前受影响 26 个文件 436 passed（22 分 36 秒）；最后一次并入后受影响 18 个文件/节点含两项必跑冒烟 126 passed（8 分 30 秒）；`test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 4 passed（6 分 24 秒）。改动文件 ruff check/format、mypy 通过（`wording.py:63` 的 E501 是基线已有，B 批次合并后已修）。

**按推荐实现的领域选择（规格未覆盖）**
1. 夹具：10-15 隔离副本没有 9 月金融统计报告原件（当时被门禁拦下，从未取），所以用仓库已有的人民银行 2026-08-14 16:30 原件 `tests/fixtures/official_period_fallback/pbc_money.html`，场景设在 08-14 16:45（早于 18:00 估算），等价复现"已发布但估算未到"。
2. "可靠已发布证据"沿用门禁原有判据：已校验、公开时点在截止前可知的声明（TuShare 推算公开时点不晚于首次取得时点）。
3. 没有拆分混合范围：无证据时同一发布事件的成员估算相同（社融总量与分项都是第 10 个交易日），按成员拆请求没有实际收益，范围仍按最差状态汇总。
4. 目录探查只加在完整运行；定向运行的门禁只享有证据优先规则。
5. `members_missing` 只列最新计划期；更早期的部分缺失归 B04 的"历史缺期"，以免两处重复列出。

**遗留**：未见。真实运行中的效果（9 月社融存量同比当次取得）待 07 集成验收确认。


### 2026-10-18 审查修复（wg-07）

审查 Spec 2：`members_missing` 改取最新的已请求期（门禁拦下或等待发布的期不算更新的期），否则上一期部分缺成员会三路都漏掉（84da04b）。验收中发现社融分项成员都显示"社融分项"，`MEMBER_NAMES` 补分项 × 口径中文名（0b96b2b）。详见 [../acceptance.md](../acceptance.md)。
