Status: resolved
Type: grilling

# 08 — 广度五项与商品篮子两项的输入契约

**2026-09-25 实施时发现：** 规格假设“日广度、窗口广度、成交额广度、结算价篮子的计算与持久化代码已存在，只是没接入 Worker”。更准确的说法（Codex 只读核对）：v0002 的计算、校验与持久化代码存在且有测试，缺的是自动生产其要求的输入、Worker 编排与部分消费端。

- 生效目录（`metric-catalog-v0004`）登记的 v0002 契约要求人工审阅的原件包：广度要历史成员池（`market-breadth-universe-v0001`）、复权参考价事件（`market-breadth-window-inputs-v0001`，`official-reference-ratio`）、成交额覆盖规则（`market-breadth-amount-inputs-v0001`），各自带 `review_hash`（`reviewer`、`decision=accepted`）；篮子要交易时段与发布时间的审阅证据（`futures_input_evidence`）。见 `src/pring_cycle/market_breadth.py` `load_breadth_universe`、`_reviewed_breadth_window_inputs`，`src/pring_cycle/market_amount.py` `_reviewed_breadth_amount_inputs`，`src/pring_cycle/commodity_basket.py` `select_commodity_contracts`（无时段证据即 `commodity_session_missing`）。
- 运行库里没有任何流程产出这些包；ADR-0021 取消认证后，这类人工审阅输入也与“注册来源免验证”不一致。
- 用户 2026-09-25 决定：本轮不接，缺口清单如实显示“入库校验失败＋原因码”；另行决策是否改为纯 TuShare 输入（成员取 `stock_basic` 上市区间、复权用 `adj_factor`、时段用 `fut_trade_cal`），并按 ADR-0021 登记新目录与模型版本。

**建议：** 用 `/grilling` 决定新契约口径（成员池、复权、成交额口径、篮子时段与固定基日），再立实施票。

## Comments

## Answer

2026-09-25 用户决定，见 [ADR-0030](../../../docs/adr/0030-breadth-and-basket-from-tushare-inputs.md)：

- **广度（5 项 → 7 项）**：全部改用 TuShare 自动取得的输入。成员为沪深北全部普通 A 股（含北交所、含 ST，排除 B 股与 CDR），按 `stock_basic` L/D/P 重建上市区间、分页取全；日涨跌用 `daily` 的 `close` 与 `pre_close`，新股首日也算，停牌或成交量为 0 不参与；120 日两项取消，改为 90/250 日新高新低（`stk_factor_pro` `topdays`/`lowdays` ≥ N）与站上 MA90/MA250（前复权收盘价严格大于均线），分母为当天有交易、上市满 N 个交易日、因子非空的股票；成交额占比分子分母都只用 `daily.amount`。每个交易日 `daily` 与 `stk_factor_pro` 各一次，首次初始化约 240 次，之后增量。仍是 P1 背景指标，不接入卡片。
- **商品篮子（2 项）**：不再需要交易时段证据，选合约只用前一交易日收盘时已知的 `fut_basic`、`fut_trade_cal`，v0002 日历选月规则不变；基日 2026-03-06、基值 1000，每天在上一日水平上乘当日收益，上一日缺失时临时从基日重建整条链、只算不入库；不接入价格压力卡。
- **版本与代码**：登记 `metric-catalog-v0005` / `model-v0013`，`model-activate` 切换；新目录生效后删除 v0002 审阅输入路径（官方参考价比例调整链、成交额覆盖规则校验、审阅材料载入）与 v0001 统一广度、收盘价篮子计算，连同对应测试（用户确认一并删除 v0001）。
- 实施票：[10](10-catalog-v0005-model-v0013.md)、[11](11-breadth-from-tushare.md)、[12](12-basket-without-session-evidence.md)、[13](13-remove-reviewed-and-v0001-paths.md)。
