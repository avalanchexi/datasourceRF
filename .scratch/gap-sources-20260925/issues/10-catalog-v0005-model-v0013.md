Status: ready-for-agent
Type: task
Blocked by: 08

# 10 — 登记目录 v0005 与模型 v0013

依据 [ADR-0030](../../../docs/adr/0030-breadth-and-basket-from-tushare-inputs.md)。

- 以 v0004 为底生成 `metric-catalog-v0005`：广度删去 `CN_EQ_NEW_HIGH_LOW_120`、`CN_EQ_ABOVE_MA120`，新增 90/250 日新高新低与站上 MA90/MA250 四项（P1 背景，不接卡片）；日涨跌、涨跌比、上涨成交额占比与篮子两项换成 TuShare 输入的新来源码。其余 54 项与 v0004 相同。
- 模型 `model-v0013` 绑定 v0005，公式版本随之更新；`model-v0012` 保留可读。
- 时效登记、缺口清单、检索登记处覆盖新指标（无网页补缺渠道）。
- 验收：`model-register`/`model-activate` 可登记与切换；生效目录完整运行在 v0013 上跑通。

## Comments
