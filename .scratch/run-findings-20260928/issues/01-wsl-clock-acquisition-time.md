Status: needs-triage
Category: bug
Type: task

# 01 — WSL 时钟跳变让回执报 `acquisition_time_invalid`

## 原始发现

- 2026-09-28 13:56 北京时间，WSL `date` 比 Windows `Get-Date` 慢约 **9 秒**。WSL 已运行约 3.3 天，`dmesg` 里有 `hv_utils: TimeSync`，Hyper-V 在周期性校时，时钟会跳变。
- `acquisition._check_time` 要求时间单调（`value < previous` 即报 `acquisition_time_invalid`）。时钟往回跳时，同一张回执的 `received_at`/`validated_at` 会早于前一个时间点。
- 本轮受影响的回执：`fut_wsr` 20 张、`fut_basic` 1 张、`eia_history_html` 1 张、`major_news` 1 张、央行 `official_listing_get` 1 张。
- 由此进入缺口清单的：`CN_FUTURES_WARRANTS`、`CN_COMMODITY_EX_HOG_BASKET`、`CN_COMMODITY_SLEEVE_CONTRIBUTION`、`EIA_BRENT_RBRTE`、`EIA_WTI_RWTC`（都是 `rejected`）。
- 提交运行时不指定 `--target-date`，`run-submit` 直接报 `Error: acquisition_time_invalid`。

## 待决定

1. 环境：校准 WSL 时钟（如 `sudo hwclock -s`，或启用 `systemd-timesyncd`/`chrony`），需要用户执行。
2. 代码：回执时间校验是否容忍小幅回拨（例如用单调时钟计时序，墙钟只做记录），还是维持严格校验、把时钟当作运行前置检查（`doctor` 报出偏差）。
