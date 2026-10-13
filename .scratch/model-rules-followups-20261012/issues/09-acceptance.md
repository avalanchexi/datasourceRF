Status: claimed
Category: task
Type: task

# 09：收尾验收（模型规则后续批次）

**What to build:** 本批合入了改动生产代码的票 01、02、06（08 只改测试与文档），按 [goal.md](../goal.md) 阶段 3 做一次收尾验收。内容是：一次全套测试、一次 v0015 真实运行加体检，以及与 `run-b7d59b63bedca39d9d2e`（目标日 2026-10-09，下称“对照运行”）的逐项比对。体检脚本的票 03、04、05、07 也在新运行上一并核对。

**Blocked by:** 01、02、06、08（体检线 03、04、05、07 已合入）

## 做法

1. 重装 dev-venv，在 flock 下跑一次 `check.py full`。跑的时候用 `disk_guard.sh <pytest PID> <log> 12` 守着 C 盘，前台守到结束。
2. 备份运行库，用 SQLite backup API 做一致性备份，放到 `~/.local/share/pring-cycle/backups/`（job 临时目录以外）。有新迁移就执行 `pring-cycle init`，执行后跑 `doctor`。
3. 真实运行：v0015，目标日取当时的上一交易日，**优先用调度运行**，同时作为票 02 的第一个真实样本：
   - 若在交易日 09:00 之后、21:00 之前启动 Worker，按票 02 会在首次判断时补交上一交易日（`scheduled_full`，幂等键 `scheduled-<目标日>-v<计划版本>`）。启动时间要给运行留足余量：P0 执行入口截止是提交当天 21:00，建议 19:30 前启动。
   - 也可以让 Worker 在下一个交易日 09:00 前常驻，取“跨过 09:00”的样本。
   - 两种都不可行时才手动提交，并在记录中写明原因。
   - 外部调用串行。跑完停掉 Worker，并确认没有其他排队运行。
4. 跑 `python3 tools/quality/audit.py --run <新运行>`，再对 `run-b7d59b63…` 重跑一次体检作为对照。两份报告逐节比对，差异逐项写出原因（目标日由 10-09 变为新目标日、窗口前移等）。
5. 把记录写成本目录下的 `acceptance-<日期>.md`。经 Codex 规格轴审查无阻断后提交，再更新 README 和 goal 进度表。

## 验收

- [ ] `check.py full` 通过（记录用例数、耗时和 C 盘最低余量）
- [ ] 备份完成，integrity 检查为 ok；迁移状态与 doctor 结果已记录
- [ ] 真实运行成功：记录运行类型（scheduled_full／manual_full）、回执数、失败数、URLError 数和耗时
- [ ] **票 02**：若取得调度样本，核对提交时刻、目标日、幂等键、P0 截止，以及“补交”或“跨过 09:00”属于哪一种；没取得要写明原因
- [ ] **票 01**：真实库中 08-14～10-08 的 34 天，最新评估的 `last_confirmed_stage` 变为 stage_iii。每天各追加一个 `corrects.reason=stage_history_changed`、`scope=last_confirmed_stage` 的版本，核心、上下文和证据引用都与原版本相同；其余日子不变；外部调用增量为 0；运行计划中有 `last_confirmed_relinks` 计数；阶段历史页显示更正说明
- [ ] **票 06**：(a) breadth 尝试分类与回执状态逐条写明；候选 B 写明篮子的请求数。新目标日的窗口通常没有全部持有，所以未必出现 12→4，要写明本次走的是哪条路径、请求数是多少、原因是什么；(b) 有没有发生日历回退，发生的话标注是否出现
- [ ] **体检票 03／04／05／07** 在新运行上的表现：第三层（一）的回溯核对；只更正核心日计为“未重算”；派生节“待开票”的数目及其原因；清理明细按成员列出；时间按时刻比较
- [ ] 与对照运行的差异都有原因
- [ ] 记录经 Codex 规格轴审查无阻断；README、goal 进度表和记忆已更新

## Comments

### 2026-10-13 进展（收尾验收子代理 fub-09）

- 10-13 10:19 已领取。dev-venv 已重装（安装副本与 src 逐文件一致）；`check.py full` 于 10:18 在 flock 下开跑，C 盘保护 12G（监视 check.py 进程），起点 C 盘 52G。日志 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub09/full.log`、`guard-full.log`。下一步：守到结束后备份、doctor，再启动 Worker 取调度样本。
- 10-13 11:26 全套结束：**1 failed, 2447 passed in 4150.03s（1:09:10）**，退出码 1；C 盘最低 58G，保护未触发。失败例 `test_tushare_call_quota.py::test_a_call_over_the_minute_waits_for_the_oldest_to_age_out`（`acquisition_time_invalid`：校验时刻比接收时刻早 2.425 秒）。判断与本批无关：该文件与 `acquisition.py`、限额模块、conftest 本批都没改；单独复跑该文件 3 次均 20 passed；实测本机墙钟每约 30 秒回拨约 2.45 秒（90 秒内回拨 3 次：2.448／2.451／2.456 秒，Hyper-V TimeSync），与失败的差值吻合。日志 `fub09/full.log`、`quota-rerun-{1,2,3}.log`。下一步：备份、doctor，再启动 Worker。
- 10-13 11:28 备份 `~/.local/share/pring-cycle/backups/pring-cycle-before-fub09-20261013-1126.sqlite3`（backup API，integrity ok，运行 35、评估 262、投影 262），alembic `0037_uncorrectable_day`，doctor ok（migration current），计划版本 3 09:00／21:00 开启，生效模型 v0015。运行前对对照运行体检一次（`fub09/audit-b7d59b63-pre.md`）。11:27:24 在 flock 下启动 Worker（不手动提交），首次判断即补交 `run-742bf2b787a6feca48a7`（scheduled_full，目标日 2026-10-12，幂等键 `scheduled-2026-10-12-v3`，system_as_of 03:27:25Z）。下一步：守到运行结束（`fub09/drive.log`、`worker.out`）。
- 10-13 12:05（主 agent）WSL 重启后墙钟仍约每 32 秒回拨 2.0–2.5 秒。根因：内核 adjtimex `tick=10833`（正常 10000），系统时钟偏快约 8.3%（对网络时间测 150 秒，单调时钟走了 150.59 秒，网络时间只走了 139 秒）；`systemd-timesyncd` 每 32 秒轮询一次，按约 −2.45 秒步进拉回。用户已把时钟源切到 `hyperv_clocksource_tsc_page`，走速不变，说明与时钟源无关。修复要 root 把 `tick` 改回 10000，脚本在本会话 scratchpad 的 `fix_tick.py`，等用户执行。重启前 `tick` 已经是 10833，开机时有东西设置它，待查。**断点**：tick 修复 → 复测 65 秒无跳变 → 查明 `run-742b…` 在库中的残留 → 10-12 manual_full 重验 → 重跑 `check.py full` → 体检比对 → 写记录、审查。
- 10-13 12:20（主 agent）**更正根因**：不是单纯 tick 设错，而是两套校时互相打架。Windows 宿主时钟比 NTP 快约 3 秒（`w32tm` Leap 3，未同步，上次成功同步是 10-12 11:51）。内核 Hyper-V 同步（`hv_utils.timesync_implicit=1`）按 ±8.33% 调 tick（实测 9167／10000／10833），把客户机往宿主时钟拉；`systemd-timesyncd` 按 NTP 每 32 秒往回拨约 2.5 秒。手动把 tick 设成 10000，1.4 秒后又被改回 10833。**处置**：用 `wsl.exe -u root systemctl stop systemd-timesyncd` 停掉 timesyncd，只在本次启动内有效，未 disable。停掉后 180 秒内最大回拨为 0；墙钟比网络时间快约 3 秒，对 T+1 无影响。验收期间不要启动 timesyncd，也不要对宿主执行 `w32tm /resync`。持久处置（禁用 timesyncd，或修复宿主校时）转入下一批积压。
