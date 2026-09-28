Status: wontfix
Category: bug
Type: task

# 03 — 中秋休市日被当成应到期

## 原始发现

- 2026-09-25（周五）是中秋节，沪深交易所休市。TuShare SSE 交易日历截至 9/25 的查询，最后一个开市日是 9/24。
- 运行 `run-dc0bb2d9db7068bf552d`（目标日 9/24，系统时点 9/28）的缺口清单把以下指标记为 `freshness_gap`、`one_period_behind_carried`，`due_period=2026-09-25`、`held_period=2026-09-24`：`CN_DR007`、`CN_DR007_POLICY_SPREAD`、`CN_OMO_7D_AMOUNT`、`CN_OMO_7D_RATE`、`CN_SHIBOR_ON_1W_3M`。`CN_USDCNY_CENTRAL_PARITY` 同样按 9/25 计，记为 `retrieval_failed`。
- 这些都是银行间或外汇日频指标。中秋是法定假日，银行间市场同样休市，9/25 本不应到期。

## 待决定

- 查时效到期日（`due_period`）用的是哪一份日历，为什么不认中秋。
- 银行间指标该用哪一份日历（交易所交易日历，还是银行间自己的日历）。

### 关闭（2026-09-28）

> *本段由 AI 按用户确认记录。*

用户确认：数据时效只需 T+1。这些指标只是落后一期并沿用上一期的值，在可接受范围内，不修。
