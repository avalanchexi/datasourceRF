# 01: ② 资产卡线图加高与月刻度

**What to build:** ② 三张资产卡的价格＋MA120 线图由 160px 加高到约 240px（图配置与容器高度两处同步），横轴保留交易日分类轴，改为每个月首个交易日一个刻度、标 YYYY-MM；三卡仍等高，908／390 宽下照常堆叠。依据 [../investigation.md](../investigation.md) 第 3 节。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 页面测试：跨月点列时图高 240、刻度为各月首个交易日；无展示点列的兼容分支不变
- [x] 两例冒烟通过

## Comments

- 2026-10-19 ticket-fd01（分支 `fd-01`）：`cockpit.chart` 图高 160→240（图配置 `layout.height` 与 `dcc.Graph.style` 两处）；横轴保留 `type=category`，改 `tickmode=array`，`tickvals` 为各月在点列中首次出现的交易日、`ticktext` 为 YYYY-MM，`tickangle=0`。
- **偏离**：窗口首月不打刻度（点列只有一个月时保留）。首版按调查给 7 个刻度（04–10），浏览器实测 Plotly 因 04（窗口自 04-21 起仅约 7 个交易日）与 05 挤在一起而自动斜置标签，`margin.b=24` 下标签底边被裁切、不可读。窗口首个点通常不是该月首个交易日，故去掉首月刻度并固定水平标签；正式库当前投影得 6 个刻度 2026-05…2026-10。
- 新测试 `tests/web/test_asset_cards.py::test_the_card_chart_is_240px_tall_with_a_level_tick_on_each_months_first_session`（先红后绿）；无点列兼容分支测试未改、照常通过。
- 测试：`python tools/check.py quick tests/web/test_*.py` 178 passed（23.7s）；两例冒烟 `flock /tmp/pring-heavy.lock python -m pytest …test_manual_run_cannot_backdate_daily_core_availability …test_worker_completes_a_valid_noncanonical_projection_and_report` 2 passed（47.0s，另排队等锁约 6.5 分钟）；ruff、mypy 通过。合并 main（bbca17a）后无新提交，结果即合并后结果。
- 浏览器（正式库只读备份到 scratchpad 隔离副本，8071 起站，Codex Playwright 实测，已停站删副本）：1440／908／390 三宽下三卡图与 SVG 均 240px；刻度水平、未裁切，每月一个；`scrollWidth` 等于视口宽，无横向溢出；1440、908 下三卡等高，908／390 纵向堆叠正常。390 下商品卡因标题状态标签换行高 23px（与图高无关；未做改前对照）；390 下 05 与 06 标签间距约 1px（5 月节假日交易日少），仍不重叠。
