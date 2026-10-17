# 14: 验收遗留 a、c–f

**What to build:** 决定 28（第五轮）。票 10 验收记录 `acceptance.md`"发现 1–6"与已知点 2 中用户同意处理的五条，只改前端：

- a. ② 家数类指标（上涨/下跌/平盘/净上涨/参与交易家数）的"近 5 日"显示家数差（如"−1,814 家"），不再显示百分比；页面用投影已有数值换算，不改 Worker。
- c. 空库（无投影）时 ④⑤ 用新卡片结构的空态，去掉英文小标题，④ 不再约 1900px 高。
- d. 桑基图合并节点写"其他 N 个来源 · 请求数"。
- e. 数据链路页"目录逐项期与未完成原因"表限高 480px 内滚（同请求表）。
- f. 390 宽时 ③ 海外卡片每行两张。

**Blocked by:** None（基于 `cockpit-layout` 最新）

**Status:** done

- [x] a–f 各条在 10-14 投影（d、e 用 10-14 链路页；c 用空库）截图核对
- [x] 390 宽无横向溢出
- [x] `dashboard_page` / `data_chain` 测试断言家数差文本、桑基合并节点标签、空态文本；受影响 Web 用例、两项必跑冒烟通过

## Comments

### 2026-10-17 实施

分支 `cl-14`（基于 `cockpit-layout` db39431）。只改前端，投影、Worker、模型规则、指标目录未动。

**改了什么**

- a. 家数近 5 日：`cockpit.window_change` 对单位为"家"（`count`）的行，用投影点列里 `change_5.start_date`、`end_date` 两端的值相减，写"±N 家"（千分位、正数带 `+`）；两端缺点时写"—"（悬停写原因），投影本身无 `change_5` 的旧投影仍写"—（旧投影未提供）"。② 同类观察表与行抽屉的"近 5 日"都换算；抽屉的"近 120 日"同样换算（同一函数，口径一致）。`change_5` 字段不改。
  - 领域选择（按推荐实现，供主 agent 核对）：规则按单位"家"判断，因此除上涨/下跌/平盘/净上涨/参与交易家数外，**90/250 日新高/新低家数**也一并改为家数差（原为 408%、542% 这类百分比，同样失真）。涨跌家数比（比值）、上涨成交额占比（%）不受影响。
- c. 空库（无投影）：④ 五张维度卡（政策、信用、过热、物价、库存）各写"等待首次完整运行。"；⑤ 象限卡"库存象限 — 等待首次完整运行。"＋需求/生产/库存三张线卡同样写法。不再走旧 `view._macro_page` / `_inventory_page`，无英文小标题。有投影但缺确认结构的旧投影仍走旧兜底（不在本票范围）。缺线的线卡改为与其他线卡同样式的卡片（`div.line-card`，悬停不高亮）。
- d. 桑基合并节点：`其他（N） · 数` → `其他 N 个来源 · 数`（`cockpit_operations.flow_sankey` 一处）。
- e. 数据链路"目录应有期与未完成原因"表包一层 `requirement-table`，新增规则限高 480px 内滚、表头吸顶（与请求表同写法，未改 `.request-table` 选择器）。
- f. `report.css` 删去 ≤560px 时 ③ 卡片一列的规则，沿用 ≤1100px 两列；"其他背景指标卡"在 ≤560px 也两列。

**测试**（`dashboard_page` / `data_chain` 两个测试缝）

- 新增：`test_asset_cards.py::test_counts_of_companies_read_their_5_day_change_in_companies_not_percent`（净上涨 -3,260 家、参与交易 +2 家、零基线平盘 +88 家、行抽屉同值、卡内无 %）、`::test_a_count_whose_window_start_is_missing_shows_no_percent`；`test_report_board.py::test_an_empty_library_shows_the_dimension_and_inventory_cards_waiting_for_a_run`。
- 改写：`test_asset_cards.py` 的 `ADVANCES` 夹具改为真实投影形状（`change_5` 为百分比收益、点列含窗口起点），原断言"-222 家"不变；`test_data_chain_sankey.py` 合并节点标签三处；`test_dashboard_contract.py::test_domain_pages_expose_fixed_sections_instead_of_generic_documents` 原断言空库旧书签页含"政策方向""四象限解释""七张阶段特征卡"——正是本票要去掉的旧结构，改为断言五张维度卡各写"等待首次完整运行。"、有"库存象限"、无"七张阶段特征卡"。
- `tests/web/` 全目录 155 passed（31 秒）。
- 两项必跑冒烟（flock）：2 passed，58 秒（另排队等锁约 21 分钟）。
- 改动文件 `ruff check`、`ruff format --check` 通过；`mypy`（`cockpit.py`、`cockpit_operations.py`）无问题。

**浏览器实测**（dev-venv-cl14 起只读 Web，端口 8114，按 PID 起停；Playwright 无头，明暗 × 1440/908/390，全程无控制台错误；截图在会话 scratchpad `cl14/shots/`，探针 `cl14/probe.py`，结果 `cl14/probe-{1014,1015,empty}.json`）

- a（10-14，`/tmp/pring-ui-real-20261015`）：上涨 978 家 -1,588 家；下跌 4,496 家 +1,672 家；平盘 88 家 -82 家；净上涨 -3,518 家 -3,260 家（原 1,263.57 %）；参与交易 5,562 家 +2 家；90 日新高 +17、新低 +510；250 日新高 -15、新低 +320 家；涨跌家数比仍 -76.06 %。10-15（`/tmp/pring-cb-real-20261016`）投影无 `change_5`，家数行照旧"—"。
- c（空库，新建隔离目录 `cl14/empty-runtime`，`initialize_runtime` 初始化）：④ 1440 高 340（原约 1913）、908/390 为 511；⑤ 1440/908 为 277、390 为 426。截图 `empty-{confirmation,inventory}-{light,dark}-1440.jpg`、`-light-{908,390}.jpg`。
- d（10-14 链路页）：合并节点读"其他 5 个来源 · 5"，截图 `1014-sankey-*.jpg`。
- e（10-14 链路页）：逐项表可视高 480、内容高 3268（1440）/12956（390），`overflow-y: auto`，表头 `sticky`；链路页 1440 总高 6980 → 4190。截图 `1014-requirements-*.jpg`。
- f：390 宽 ③ 卡片两列（左 12、200，宽 178），段高 1787 → 1007（10-14、10-15 相同）；截图 `1014-overseas-light-390.jpg`。
- 横向溢出：10-14、10-15、空库首页，10-14 链路页，明暗 × 1440/908/390 `scrollWidth` 均等于视口宽。

**遗留**：无。注意浏览器自检中一次"空库"探针因起站脚本 `$!` 拿到外壳 PID、旧站未停而实际测到了 10-14，已发现并按真实 PID 停站后重测，上列空库数值为重测结果。
