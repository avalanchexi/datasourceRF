Status: needs-triage
Category: bug
Type: task

# 01：WSL 墙钟两套校时打架，尚无持久处置

## 现象

Windows 宿主时钟比 NTP 快约 3 秒（`w32tm` Leap 3，未同步，上次成功同步是 10-12 11:51）。内核 Hyper-V 同步（`hv_utils.timesync_implicit=1`）按 ±8.33% 调 tick（9167／10000／10833），把客户机往宿主时钟拉；`systemd-timesyncd` 按 NTP 每 32 秒往回拨约 2.5 秒。结果是墙钟每约 32 秒回拨 2.0–2.5 秒，重启 WSL、换时钟源都无效。10-13 只用 `systemctl stop` 临时停掉 timesyncd（未 disable），WSL 重启后会复发。

## 候选（需用户定）

- 禁用 WSL 内的 `systemd-timesyncd`，只靠 Hyper-V 同步跟随宿主（宿主偏差直接传到客户机，绝对时间可能差几秒，对 T+1 无影响）；
- 修复宿主校时（管理员 `w32tm /resync`，查明为何不同步），并视情况保留 timesyncd；
- 在 `docs/development/local-runtime.md` 写明检查方法（65 秒内比较 `time.time()-time.monotonic()`）。

## 来源

[票 09 Comments](../../model-rules-followups-20261012/issues/09-acceptance.md)、[acceptance-20261013.md](../../model-rules-followups-20261012/acceptance-20261013.md) 遗留 1。

## Comments

### 2026-10-13 用户决定

- 选第一个候选：在 WSL 内永久禁用 `systemd-timesyncd`，只靠 Hyper-V 同步跟随宿主。执行属人工步骤，可用 `/wizard` 生成带回滚的脚本。
- 它是 [反复出现的输入缺口](../../recurring-input-gaps-20261013/spec.md) 收尾验收真实运行的前提。

### 2026-10-13 执行

- 用户 15:2x 同意后执行 `wsl.exe -u root systemctl disable --now systemd-timesyncd`：两个 wants 链接已删除，`is-active` inactive、`is-enabled` disabled，WSL 重启不再自启。
- 65 秒检查（每 0.5 秒比较 `time.time()-time.monotonic()`）：最大偏移 +0.0000 秒，无回拨。`timedatectl`：NTP service inactive。
- 回滚：`wsl.exe -u root systemctl enable --now systemd-timesyncd`。宿主时钟仍比 NTP 快约 3 秒，偶尔用 `w32tm /query /status` 查看即可。
