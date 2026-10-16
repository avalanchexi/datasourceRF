# 07: ⑥ 阶段史区间列表

**What to build:** 读者在 ⑥ 段看到四条色带与天数汇总，其下是几行区间列表（同一状态连续日合并，如"04-27～08-04 Stage III""08-05～10-14 非典型组合"），默认最近 120 个交易日；点区间在抽屉看逐日明细与更正版本说明。见 [规格](../spec.md) 用户故事 58–62，实现决定"⑥ 区间列表"。

**Blocked by:** 01

**Status:** done

- [x] 按"同一状态（阶段 / 无正式阶段原因）连续日"合并区间，状态变化处断开；默认最近 120 个交易日
- [x] 区间抽屉：逐日日期、阶段 / 原因、更正版本与原因、投影链接（固定投影上下文）
- [x] 交易日等价表格进抽屉；页面不再逐日列出更正事件
- [x] 首页渲染入口测试：连续合并与断开、区间抽屉内容、更正版本可追溯、固定历史投影不漂移；改写依赖逐日事件全量的既有断言；两项必跑冒烟通过

## Comments

### 2026-10-16 实施

分支 `cl-07`（基于 cockpit-layout fec5d33，收尾并入 509d4b6）。

**改了什么**
- `cockpit.py`：⑥ 段在色带与天数汇总下新增"阶段区间（最近 120 个交易日）"列表。`history_days` 取投影 `stage_history.display.days`（无对齐色带的旧投影或无投影时按阶段事件逐日构造），并按日期并入当日事件，取最近 120 日；`history_intervals` 按 `official`（正式阶段或无正式阶段原因）连续合并，每行"起～止 状态 N 日 含更正 K 日"，是抽屉触发器。
- 区间抽屉逐日列出：日期 · 阶段/原因；有事件时写上一确认、原因、P0 缺口、模型；更正版本写"更正版本：更正 <被更正的投影>（原因）"，被更正投影与当日投影均链接到 `/?projection=<id>#history`（固定该投影上下文）。
- "交易日历与色带等价表格"由原地展开改为抽屉；"修正记录"列（原为字典原文）改为"更正的版本"投影链接。
- 首页 ⑥ 不再调用 `dashboard._stage_history_page`（逐日事件全量）；该函数保留，仅 `tests/integration/test_core_stage_lookback.py` 的旧入口仍直接调用。更正说明抽成 `dashboard._stage_correction_note`，逐日行与区间抽屉共用。
- `HISTORY_LABELS` 补 `BLOCKED_REASONS`（核心数据待处理、核心状态不可用、P0 未过门禁）与 `canonical_combination`→"典型组合"，天数汇总与区间不再出现原始码。
- `report.css`：区间列表四列行（窄屏换行）、抽屉内逐日行与表格日期不换行。

**按推荐实现的选择（规格未覆盖）**
- 区间日期写月-日；窗口跨年时写完整日期。区间行附"含更正 K 日"，"更正版本"字样只在抽屉逐日行出现（与既有每日计数断言一致）。
- 原 ⑥ 内"窗口前的上一确认阶段"小节（回溯年数、区间/日历请求次数）不再显示于首页；上一确认阶段与"回溯得出"仍在 ① 结论板"上次确认"行。若要保留回溯请求次数，可放入等价表格抽屉，需用户决定。

**测试**
- 新增 `tests/web/test_stage_history_intervals.py` 5 例（连续合并与断开、区间抽屉内容与更正可追溯、最近 120 日、等价表格进抽屉且无原地展开、固定历史投影不混入读模型后续日）；改写 `test_dashboard_contract.py` 中"正式区间与空档"断言为新标题与空状态。
- 并入集成分支后：`tests/web/` 全部 123 passed（26.6 s）；两项必跑冒烟 2 passed（59 s，flock）；`test_core_history_correction.py`、`test_core_only_correction.py` 11 passed（11 m 34 s，flock，每日更正计数断言照常通过）。并入前另跑 `test_core_stage_lookback.py`、`test_model_version_switch.py`、`test_publication_corrections.py` 等 44 例，除已修的标题断言外全部通过（19 m 38 s）。
- `ruff check`、`ruff format --check` 通过；`mypy` 改动源文件无问题（测试文件既有 mypy 报错与本票无关，新测试文件无报错）。

**浏览器自检**（8107，隔离副本 `/tmp/pring-ui-real-20261015`，10-14 投影）
- 区间 3 行：04-16～04-24 核心数据待处理 7 日（含更正 7 日）、04-27～08-03 第三阶段 · Stage III 67 日（含更正 67 日）、08-04～10-14 非典型组合 46 日（含更正 42 日）。
- ⑥ 段高度：1440 宽 611 px（改前约 8,000 px），390 宽 717 px；明暗两种主题下 1440/908/390 的 `scrollWidth` 都等于视口宽度，无横向溢出。
- 区间抽屉宽 520 px（908 宽时 363 px＝40vw）；Esc 关闭、后退关闭；分享锚点 `#drawer-history-interval-2026-04-27` 直达打开（67 日）；等价表格抽屉 120 行。
- 截图：`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/98152580-dc82-4790-be5a-d146e59f2771/scratchpad/cl07/`（history-{light,dark}-{1440,390}.png、drawer-interval-light-1440.png、drawer-calendar-light-1440.png、drawer-anchor-light-908.png）。

**遗留**
- 色带 x 轴日期在 390 宽下重叠（改前已有，色带本票未改）。
