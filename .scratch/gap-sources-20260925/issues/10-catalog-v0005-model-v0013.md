Status: done
Type: task
Blocked by: 08

# 10 — 登记目录 v0005 与模型 v0013

依据 [ADR-0030](../../../docs/adr/0030-breadth-and-basket-from-tushare-inputs.md)。

- 以 v0004 为底生成 `metric-catalog-v0005`：广度删去 `CN_EQ_NEW_HIGH_LOW_120`、`CN_EQ_ABOVE_MA120`，新增 90/250 日新高新低与站上 MA90/MA250 四项（P1 背景，不接卡片）；日涨跌、涨跌比、上涨成交额占比与篮子两项换成 TuShare 输入的新来源码。其余 54 项与 v0004 相同。
- 模型 `model-v0013` 绑定 v0005，公式版本随之更新；`model-v0012` 保留可读。
- 时效登记、缺口清单、检索登记处覆盖新指标（无网页补缺渠道）。
- 验收：`model-register`/`model-activate` 可登记与切换；生效目录完整运行在 v0013 上跑通。

## Comments

- 2026-09-25 实施：`effective_model_manifest()` 现返回 `model-v0013`/`metric-catalog-v0005`（61 项）：删 120 日两项，新增 `CN_EQ_NEW_HIGH_LOW_90/250`、`CN_EQ_ABOVE_MA90/250`，广度来源码 `tushare:daily:breadth-v0003`、`tushare:daily:breadth-amount-v0003`、`tushare:stk_factor_pro:breadth-window-v0003`，篮子 `tushare:fut_daily:ex-hog-calendar-settlement-v0003`；旧清单改名 `model_v0012_manifest()` 保留。时效登记新增 4 项（`tushare:stk_factor_pro`，18:00）。`source_contract_review._tushare_derived_claim` 只做结构校验（ADR-0021）。
