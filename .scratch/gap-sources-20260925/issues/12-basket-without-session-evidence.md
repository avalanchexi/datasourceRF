Status: done
Type: task
Blocked by: 10

# 12 — 商品篮子不再要交易时段证据，逐日接续

依据 ADR-0030。

- 选合约只用前一交易日收盘时已知的 `fut_basic`、`fut_trade_cal`；v0002 的日历选月规则（距最后交易日严格多于 10 个开市日的最近到期合约）不变。
- 基日 2026-03-06、基值 1000；当日水平 = 上一日持有水平 ×（1＋当日篮子收益）；上一日水平缺失时临时从基日重建整条链，只算不入库。
- 收益仍取所选同一合约的 `settle/pre_settle − 1`，来自 `fut_daily`。
- 验收：主接缝完整运行中篮子与 7 个袖套持有、不在缺口清单；适配器测试覆盖换月、断链重建、上一日水平接续。

## Comments

- 2026-09-25 实施：`src/pring_cycle/basket.py`，适配器 `TushareContextAdapter.ex_hog_basket`，公式版本 `ex-hog-calendar-settlement-v0003`。合约只看上市日早于 T 的；`fut_trade_cal` 取基日至候选合约最晚到期日；只为被选中的合约各取一次 `fut_daily`。最近持有的水平为锚，无锚时从基日重建，只输出窗口内未持有的日子；某日缺结算价或选约失败即停链。
