Status: done
Type: task

# 06 — VIX 由 Cboe 官网直连取得

规格“VIX”一节（用户故事 17–19），依据 ADR-0029。

- 来源：`https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`（2026-09-26 起 `cdn.cboe.com` 307 跳转到此）（`DATE,OPEN,HIGH,LOW,CLOSE`，自 1990 年起）。只取日期与收盘值；表头或行结构不符记来源失败，不取值。
- 时效登记由 `search:cboe` 改为官方来源，移除宽松检索家族。

## 实测更新时刻

- 2026-09-25 19:29（北京时间）：CSV `last-modified` 为 2026-09-23 01:51 GMT，最新一行 09/22；09/23、09/24 两个美股交易日尚未出现。
- 即 9/22 收盘约在北京时间次日 09:51 写入，但之后两个交易日未更新，更新并不逐日稳定。本次会话内无法连续观察多日，滞后按保守值登记（见下方 Comments 的实施记录），后续真实运行再核。

## Comments

- 2026-09-25 实施：`src/pring_cycle/quote_sources.py` 的 `CBOE_VIX`。按 ECB 参考汇率的先例放在 Worker 取数阶段（`refresh_context_sources`），作为注册来源每轮取一次，不进检索降级链；表头不是 `DATE,OPEN,HIGH,LOW,CLOSE`、日期重复或行格式不符即拒收，记 `source_failed`＋原因码（缺口清单显示“取数失败”）。时效登记 `cboe:vix_history`，滞后 1 日、宽限 3 个交易日（保守值，只有 2026-09-25 一次观察：CSV 停在 9/22，已晚两个美股交易日）；后续真实运行若仍常超宽限，再按实测调整。`cboe_vix` 宽松检索家族删除。
