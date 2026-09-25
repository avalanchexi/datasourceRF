Status: ready-for-agent
Type: task

# 06 — VIX 由 Cboe 官网直连取得

规格“VIX”一节（用户故事 17–19），依据 ADR-0029。

- 来源：`https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`（`DATE,OPEN,HIGH,LOW,CLOSE`，自 1990 年起）。只取日期与收盘值；表头或行结构不符记来源失败，不取值。
- 时效登记由 `search:cboe` 改为官方来源，移除宽松检索家族。

## 实测更新时刻

- 2026-09-25 19:29（北京时间）：CSV `last-modified` 为 2026-09-23 01:51 GMT，最新一行 09/22；09/23、09/24 两个美股交易日尚未出现。
- 即 9/22 收盘约在北京时间次日 09:51 写入，但之后两个交易日未更新，更新并不逐日稳定。本次会话内无法连续观察多日，滞后按保守值登记（见下方 Comments 的实施记录），后续真实运行再核。

## Comments
