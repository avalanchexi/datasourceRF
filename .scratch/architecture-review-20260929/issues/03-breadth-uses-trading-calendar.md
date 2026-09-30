# 03: 市场广度改用交易日历模块

**What to build:** 市场广度不再自己向 TuShare 请求只含开市日（`is_open=1`）的 600 天日历，改向交易日历模块取上交所交易日；广度输入血缘改为指向核心日历回执。

**Blocked by:** 02

**勿并行：** 04（同改：交易日历模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done（真实运行核对留到终点）

来源：[架构评审](../README.md) 候选 1 访谈。`breadth.py:300` 的这份请求就是票 run-findings-20260928/06 与 `7f5a2bb` 的根源：它不是交易日历（按 `CONTEXT.md` 定义），回执 normalized 却存着整组广度标量（`tushare_context.py:280–309`），`row_count` 也因此被误读。 规格：[spec.md](../spec.md)「二、交易日历模块」。

## 要点

- 广度需要目标日前 600 个自然日内的交易日：定最近 120 个交易日的补算日期，并判断股票上市是否满 90/250 个交易日（`breadth.py:251`、`breadth.py:314`）。日历模块按需取得这一范围的核心口径完整日历。
- 会改变实际 TuShare 请求（少一次 `trade_cal`，核心日历可能取更长范围），不是纯重构；按"先重构、后改行为"单独做。
- 广度标量的输入血缘改链核心日历回执；`tushare_context.py:286` 对 `trade_cal` 的特殊关联随之调整。

## 验收

- [x] 广度不再发出 context 口径的 `trade_cal` 请求；七个广度指标的结果与改动前一致（同一夹具下逐值比对）。
- [x] 上市满 90/250 个交易日的判断仍基于完整 600 天范围。
- [x] 广度标量的血缘指向核心日历回执，原件追溯可读。
- [x] 受影响测试通过；切片收尾冒烟通过；涉及来源，另加跑完整目录正例，记录退出码与耗时。
- [ ] 本票不单独做真实完整运行（ADR-0025；用户决定 2026-09-29，集中到终点）：终点真实完整运行时核对缺口清单无新增项、广度指标 `available`，结论记入本票 Comments。

## Comments

**2026-09-30 实施记录**

- **改动**：
  - `breadth_scalars` 不再请求 `trade_cal`，改为接收上交所交易日 `sessions` 和日历回执 id `calendar_ids`。
  - `TushareContextAdapter.breadth` 透传这两项；没有要算的日子时，抛与旧路径相同的"无新数据"异常，Worker 照旧把增量族记为 `missing_values`。
  - Worker 新增 `_breadth_calendar`：从交易日历模块读目标日前 600 天的交易日；只要有一天没被核心回执覆盖，就用核心适配器重取整个范围。
  - 交易日历模块新增 `sessions_between(first, last)`。
  - 血缘：广度标量先列核心日历回执，再列上市资料和当日交付的回执；`tushare_context` 不再把 `trade_cal` 当广度输入。
- **来源失败的分类**：核心适配器对 TuShare 非零业务码原来只抛普通 `ValueError`。新增子类 `TushareRefused`（消息和基类不变，核心刷新的记录不受影响），广度取日历时把它换回 `TushareSourceError`：40203 记为 `tushare_rate_limited`，其他码为 `tushare_source_failed:<码>`，与广度自己请求日历时一致。
- **逐值比对**（测试外的一次性证据）：用 `test_gap_source_repairs` 的完整运行夹具，分别在改动前后的代码上导出七个广度指标全部统计期的值，1560 个值完全相同。仓库里的测试保留原有的部分值断言。
- **测试**：
  - `tests/adapters/test_breadth.py` 改为传入交易日；"无事可做"改为不发任何请求；新增"每个值都带上日历回执"。
  - `test_trading_calendar.py` 新增 `sessions_between`，以及 `_breadth_calendar` 的"已覆盖不再取、未覆盖取一次"和"拒绝 → 来源失败，区分限频"。
  - `test_gap_source_repairs.py` 新增：广度的原件追溯指向核心日历回执且原件可读，库里没有 context 口径的 `trade_cal` 回执。
- **验证**（`PYTHONPATH=src`）：涉及广度、`trade_cal`、交易日历的测试文件，加 Worker 执行、核心刷新、完整目录正例，398 例全过（34.1 分钟）。修正来源失败分类后，重跑核心适配器相关 6 个文件与交易日历模块测试，84 例全过。ruff、mypy 通过。
- **审查**（Codex 只读）已按意见修：来源失败分类的回归；两处 docstring 的描述（交易日历模块里广度请求日历的说法改为历史回执；`_breadth_calendar` 写明覆盖不全时重取整个范围）。审查还更正了我的一个说法：旧代码那份空交付的日历回执结构检查是通过的，并不会在缺口清单里产生"rejected"项，所以本票并没有"消除 rejected 缺口"这一效果。
- **没有补的测试**：上市满 89/90、249/250 个交易日的边界。日龄算法本票没改，原有断言仍在。
- **行为变化（本票授权）**：少了一次 context 口径的 `trade_cal`；核心日历在覆盖不全时按 600 天取，覆盖更长以后，完整运行窗口、郑商所窗口、`launch_calendar` 读到的日历回执也更多（按最新回执合并）。
- **终点待办**：真实完整运行时核对缺口清单没有新增项、七个广度指标 `available`，结论补在这里。

