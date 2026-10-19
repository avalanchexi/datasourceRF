# 07: ④ 宏观判断依据五卡

**What to build:** ④ 改名"宏观判断依据"，五张维度卡写维度方向与高低位、各关键指标读法及其在多数决中的投向；分化指标标"分化"并写按主要成员的投向；贷款写"不参与信用维投票，分化见信号清单"。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 02

**Status:** done

- [x] `dashboard_page` 断言 ④ 标题、五卡顺序、投向文本、分化与贷款标注
- [x] 旧投影无宏观字段时 ④ 保持现状
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms07，分支 ms-07）

- 页面：投影带 `cycle_overview.macro_judgement` 时，④ 标题（目录与段头）改为"宏观判断依据"（`cockpit.section_titles`，词 `wording.MACRO_BASIS`），正文换成新小模块 `macro_basis.py` 的五卡；旧投影（无宏观块）与首次运行前仍走原 `confirmation_cards`／`_macro_page`，标题"宏观事后确认"不变。
- 五卡按 `DIMENSIONS` 顺序（政策、信用、增长、物价、库存），卡头写维度方向 · 高低位（取 `position_from` 指标名）· 吻合／不吻合／不计分 · 判法：政策沿用 ① 的动作规则句；库存"库存象限即维度方向"；投票维写"多数决：下行 2 票、上行 1 票"，打平写"多数决打平（…），取社融"（决定 46）或"不明"，不足半数写"明确者不足半数（k/n），不明"。
- 每个关键指标一行：指标名、主要成员读值与读取期（`cockpit._main_reading`，由 `_own_reading` 拆出，旧卡不变）、投向——"投下行"；分化"分化 · 按主要成员投下行"；无票"缺当期读数，不投票"或"方向未读出，不投票"；贷款"不参与信用维投票，分化见信号清单"；政策三项写"日期 下调 → 宽松"／"120 日内无动作 → 中性"／"无可读记录，不计"，流动性投放与 DR007"附注，不参与判定"；库存写象限。全部读已发布的维度块，页面不重新多数决，也不用确认度关系代替投向。
- 行仍打开原指标抽屉（成员、派生、缺口、命题），抽屉内确认度关系与宏观投向并存（code-map 07）。卡上方一句口径说明，指向 ① 价格验证中的确认度（票 06）。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms07`（每次改动后 `uv sync --extra dev --no-editable --reinstall-package pring-cycle`），`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms07`，`PYTHONDONTWRITEBYTECODE=1`。

- 新增 `tests/web/test_macro_basis_cards.py`（6 例：④ 标题；旧投影保持"宏观事后确认"与旧卡；五卡顺序与卡头；各指标投向含分化、贷款、政策附注；行打开成员抽屉；打平取社融、不足半数、政策下调三种卡头）。
- 受影响测试：`python tools/check.py quick tests/web/test_macro_basis_cards.py tests/web/test_confirmation_cards.py tests/web/test_report_board.py tests/web/test_macro_judgement_board.py tests/web/test_macro_signal_board.py tests/web/test_macro_fallback_board.py tests/web/test_dashboard_contract.py tests/web/test_conclusion_board.py tests/web/test_conclusion_board_right.py tests/web/test_conclusion_board_noncanonical.py tests/web/test_inventory_section.py tests/web/test_cockpit_http.py` → 92 passed，42 秒。
- 两例冒烟（`flock /tmp/pring-heavy.lock`）：`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 2 passed，49 秒（含等锁共 3 分 41 秒）。
- ruff check／format 通过；mypy 对改动源文件无新增错误。

### 偏离与取舍

- 维度名沿用 ① 的 `MACRO_DIMENSIONS`（"增长"），旧卡仍为"过热"。
- 卡内不再标"不计数"，改写投向；行内不重复主要成员方向箭头（投向已写方向）。
- 分化行与贷款行只写文字"见信号清单"，未链接到清单条目锚点。
- 未加样式（沿用 `dimension-card`／`indicator-row`），投向文字 `className="macro-vote"` 留作后续样式钩子。
