Status: needs-triage
Type: grilling

# 08 — 广度五项与商品篮子两项的输入契约

**2026-09-25 实施时发现：** 规格假设“日广度、窗口广度、成交额广度、结算价篮子的计算与持久化代码已存在，只是没接入 Worker”，这一前提不成立。

- 生效目录（`metric-catalog-v0004`）登记的 v0002 契约要求人工审阅的原件包：广度要历史成员池（`market-breadth-universe-v0001`）、复权参考价事件（`market-breadth-window-inputs-v0001`，`official-reference-ratio`）、成交额覆盖规则（`market-breadth-amount-inputs-v0001`），各自带 `review_hash`（`reviewer`、`decision=accepted`）；篮子要交易时段与发布时间的审阅证据（`futures_input_evidence`）。见 `src/pring_cycle/market_breadth.py` `load_breadth_universe`、`_reviewed_breadth_window_inputs`，`src/pring_cycle/market_amount.py` `_reviewed_breadth_amount_inputs`，`src/pring_cycle/commodity_basket.py` `select_commodity_contracts`（无时段证据即 `commodity_session_missing`）。
- 运行库里没有任何流程产出这些包；ADR-0021 取消认证后，这类人工审阅输入也与“注册来源免验证”不一致。
- 用户 2026-09-25 决定：本轮不接，缺口清单如实显示“入库校验失败＋原因码”；另行决策是否改为纯 TuShare 输入（成员取 `stock_basic` 上市区间、复权用 `adj_factor`、时段用 `fut_trade_cal`），并按 ADR-0021 登记新目录与模型版本。

**建议：** 用 `/grilling` 决定新契约口径（成员池、复权、成交额口径、篮子时段与固定基日），再立实施票。

## Comments
