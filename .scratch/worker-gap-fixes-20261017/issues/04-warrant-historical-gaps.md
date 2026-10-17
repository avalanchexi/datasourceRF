# 04: 仓单历史缺期进缺口清单

**What to build:** 仓单 07-21 五品种、09-09 聚丙烯的历史缺期在 ⑦ 找不到（决定 4）。最终补缺计划中的历史缺期并入缺口清单，按指标归组（如"仓单：历史缺期 6 个"），期与品种明细进抽屉；完整度"其他缺失"能对上。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** done

- [x] 完整运行：最终计划含历史缺期时，缺口清单按指标归组并带期与成员
- [x] 完整度"其他缺失"数与缺口清单条目一致
- [x] `dashboard_page` 断言 ⑦ 归组行与抽屉明细
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

分支 `wg-04`（基于 worker-gaps 7236209，已并入 1b335db）。

**改了什么**
- `freshness.add_projection_gaps`：最终计划里未完成、且没有发布门禁（`release_gate`）、没有列表未覆盖（`listing_not_covered`）的期，只要该指标持有更晚的期（本次时效 `held_periods`，或计划里更晚的期已完成），就并入该指标的缺口行 `missing_periods: [{period, missing_members}]`；指标原本未列出时新增一行 `missing / historical_periods_missing`。排除：时效行持有期之后的期（那一行已代表）、派生公式 `missing_inputs` 已点名的父指标期。
- `RunMaterials.held_periods`：Worker 把批次时效的持有期传入单日汇总（`worker.py`、`day_summary.py`）。
- ⑦（`cockpit.gap_preview`）：页面行只写"历史缺期 N 期共缺 M 个成员（起 至 止）"，并给"缺期明细 →"打开"全部缺口"抽屉；抽屉（及运行页、报告详情的缺口清单）逐期写"YYYY-MM-DD 缺 铜（CU）、螺纹钢（RB）……"。成员中文名取 `wording.display_name`；原因码 `historical_periods_missing` → "历史缺期" 加在 `wording.REASON_LABELS`。

**领域选择（规格未明定，按推荐实现）**
1. 归组行计数写"N 期共缺 M 个成员"：完整度按"指标×期"计（10-15 例为 2），决定 4 的例子"历史缺期 6 个"是成员数；两个数都写出，"其他缺失"按期数对得上。
2. "历史缺期"只认持有更晚期的期：目标日当期未到（如 test_gap_list 中 CSI300 等待发布那类）不算历史缺期，留给 B03 的"等待发布"分组处理。
3. `test_gap_source_repairs::test_usdcny_1630_close…` 原断言"1630 收盘不在缺口清单"；该夹具里 CFETS 只给当日，计划要求的 07-31 未取到、完整度记为其他缺失，现按本票列为历史缺期，断言改为"原因 historical_periods_missing、缺期仅 2026-07-31"。

**测试与耗时**
- 新增完整运行 `tests/integration/test_warrant_historical_gaps.py`（2 例，夹具跳过 CU/RB 07-28、PP 07-30；断言缺口行逐期带成员，且完整度目录口径每条"其他缺失"都能在缺口清单找到）：先红（两例均失败）后绿，约 2 分钟。
- 新增 `tests/web/test_reading_section.py::test_historical_warrant_days_are_one_row_with_periods_and_symbols_in_the_drawer`：先红后绿。
- 合入 worker-gaps 1b335db 后重装复跑受影响 18 个文件 212 passed（478 秒）；两项必跑冒烟 2 passed（45 秒）；改动涉及 Worker 编排，加跑 `test_worker_registered_catalog.py` 2 passed（358 秒）。
- 改动文件 ruff check / ruff format --check / mypy 通过。

**遗留**
- 目标日当期缺成员（持有期即该期、计划未完成）仍可能计入"其他缺失"而缺口清单不单列（如仓单目标日某品种缺失由 `failed_members` 说明的情形之外）；本票未改。

### 2026-10-18 合入 worker-gaps ae015ce（B03 等待发布分组）

- 冲突在 `freshness.add_projection_gaps` 与 `dashboard._gap_row`，两边行为都保留：历史缺期先归组，等待发布随后附在同一行或单独成 `awaiting_release` 行；历史缺期排除一切带 `release_gate` 的期，所以等待发布期既不算历史缺期，也不算完整度"其他缺失"（`coverage_display` 计入 `release_gated`）。行首原因在明细已写出时省略，四种明细（未请求、列表未覆盖、等待发布、历史缺期）同等对待。
- 重装后复跑受影响 19 个文件 213 passed（504 秒）＋ `tests/web/test_awaiting_release_group.py` 3 passed；两项必跑冒烟 2 passed（41 秒）；`test_worker_registered_catalog.py` 2 passed（358 秒）。
- 注意：B03 的 `tests/integration/test_awaiting_release_group.py` 与 `tests/web/test_awaiting_release_group.py` 同名，在同一次 pytest 调用里收集会报 import file mismatch（退出码 2），须分开跑或改名。
