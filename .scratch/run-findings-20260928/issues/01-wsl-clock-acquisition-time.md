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

## Comments

> *本段由 AI 在分流时生成。*

### 根因与环境处理（2026-09-28 14:16）

- 用三台外部服务器（baidu、cloudflare、apple）的 HTTP `Date` 做参照：WSL 与服务器差在 1 秒内，**Windows 快约 9.6 秒**。原先的判断“WSL 慢”应改为“Windows 快”。
- Windows 的 `w32tm` 状态为未同步（Leap 3），来源为 `Local CMOS Clock`，从未做过网络对时。WSL 里的 `systemd-timesyncd` 在工作。于是 Hyper-V TimeSync 把 WSL 拉向 Windows 时间，timesyncd 又拉回网络时间，时钟来回跳约 9 秒，回执时间不再单调。
- `sudo hwclock -s` 和 `sudo date -s` 都无效：几秒后就被拉回去。
- 已处理：以管理员身份运行脚本，把 Windows 时间服务设为自动启动，对时源设为 `ntp.aliyun.com`、`ntp.tencent.com`、`time.windows.com`，然后强制重新同步。
- 处理后两分钟内测量 5 次，WSL − Windows 从 +0.72 秒收敛到 −0.44 秒，两边与服务器的差都在 1 秒内。

**剩下的决定**：代码是否还要对时钟回拨做防护（例如用单调时钟判断先后，墙钟只做记录；或者在 `doctor` 里检查两边时钟偏差）。环境已经修好，这一项可以降级，下次真实运行复验后再定。
