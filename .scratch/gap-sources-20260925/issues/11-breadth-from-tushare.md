Status: done
Type: task
Blocked by: 10

# 11 — 广度 7 项由 TuShare 输入计算

依据 ADR-0030。

- 成员：`stock_basic` L/D/P 分页取全，重建上市区间；沪深北普通 A 股，含北交所与 ST，排除 B 股与 CDR。
- 日涨跌与涨跌比：`daily` 的 `close` 对 `pre_close`；新股首日计入；停牌或成交量为 0 不参与。
- 上涨成交额占比：分子分母都只用 `daily.amount`。
- 窗口 4 项：`stk_factor_pro` 的 `topdays`/`lowdays` ≥ 90/250，前复权收盘价严格大于 MA90/MA250；分母为当天有交易、上市满 N 个交易日、因子非空。
- 每个交易日 `daily` 与 `stk_factor_pro` 各一次，全市场分页；已持有的交易日不再取。
- 验收：主接缝完整运行中 7 项持有、不在缺口清单；适配器测试覆盖分页、首日、停牌、零成交、上市不满 N 日与因子为空。

## Comments

- 2026-09-25 实施：`src/pring_cycle/breadth.py`，适配器 `TushareContextAdapter.breadth`。先取 SSE 日历（目标日前 600 天），取最近 120 个交易日中尚未持有的日子，才取 `stock_basic` L/D/P；每页 6000 行、满页才翻页（2026-09-25 实测 `daily` 5557 行、`stk_factor_pro` 5556 行、`stock_basic` L 5569 行，均一页取完）。涨跌比在无下跌时不出值；未识别的证券代码整批拒收（`tushare_breadth_security_scope_unknown`）。每个值只关联当日的 `daily`/`stk_factor_pro` 与名册、日历回执。维度沿用 `universe=point_in_time_traded_a_shares`。
