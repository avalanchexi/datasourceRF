Status: ready-for-agent
Type: task
Category: acceptance

# 05：收尾验收

**What to build:** 证明一次正常的 T+1 运行输入完整：体检“真正缺失”为 0，若不为 0 即为真实数据异常并写明。

**Blocked by:** 01、02、03、04；以及 [残余票 01](../../model-rules-residuals-20261013/issues/01-clock-two-time-syncs-fight.md) 的时钟持久处置（真实运行前用 65 秒时钟检查确认无回拨）。

**主要模块：** 无新代码；全套测试、真实运行与体检。

- [x] 全套测试一次通过（ADR-0025），记录耗时与 C 盘最低余量
- [x] 备份运行库，记录迁移状态与 doctor
- [ ] 一次真实 T+1 运行（优先 09:30 的计划运行；外部调用串行）完成
- [ ] 目标日两融值进入冻结输入；DR007 等 5 项时效为 current
- [ ] 体检：“真正缺失”为 0；上游未发布、已知历史缺口各自单列
- [ ] 与 `run-0a8dabc2e820321b84e1` 的差异逐项有原因，写入验收记录
- [ ] 规格轴审查用 `codex exec -s read-only`

## Comments

### 2026-10-13 用户决定（主 agent 转达）

真实运行用 10-14 09:30 的计划运行（目标日 10-13）：10-13 晚 06 合入后跑全套（`tools/clock_check.py` 退出码 0 才开跑，带 `tools/disk_guard.sh`）；通过后备份运行库、集成分支代码装入真实 dev-venv、`pring-cycle init`（迁移 0038 → 计划 09:30）、常驻 Worker；跑完停 Worker，体检与验收。验收通过后再问用户是否并入 main。

### 2026-10-13 第一段（收尾验收子代理 ticket-05）

代码为集成分支 `d6b3126`（之后的 `25aadc0` 只改 goal.md）。过程文件在会话 scratchpad 的 `acc05/`（`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/3c98b852-8a48-470d-b56a-0661f8b7cfa4/scratchpad/acc05/`，下称“过程目录”；WSL 重启会丢）。

- **开跑前**：20:53 `python3 tools/clock_check.py` 退出码 0（65 秒内无超过 0.2 秒的跳步）；`systemd-timesyncd` 为 disabled／inactive；C 盘起始 57G；锁空闲、无 Worker。
- **dev-venv**：`UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv uv sync --extra dev --no-editable --reinstall-package pring-cycle` 重装，安装副本与 `src/pring_cycle` 逐文件一致（`diff -rq` 无差异）。
- **全套**：20:55:24 在 `flock /tmp/pring-heavy.lock` 下开跑 `tools/check.py full`，`tools/disk_guard.sh` 守 pytest 进程（下限 12G）。**2466 passed in 3722.22s（1:02:02）**，退出码 0，21:57:31 结束；0 失败，无需复跑。C 盘全程 57G（124 次采样都是 57G），保护未触发。日志：过程目录 `full.log`、`full.meta`、`guard-full.log`，计时 `timings-full.jsonl`（`guard-misfire.log` 是开跑后第一分钟误挂在 shell 进程上的保护脚本，已换成 pytest 进程，不影响结果）。
- **备份**：`~/.local/share/pring-cycle/backups/pring-cycle-before-acc05-20261013-2157.sqlite3`（SQLite backup API，42 秒，2.9 GB），integrity ok；alembic `0037_uncorrectable_day`，运行 37、`run_command` 最大编号 38、评估 296、投影 296（过程目录 `backup.txt`）。这是 0038 迁移与 10-14 计划运行之前的回滚点。
- **迁移与 doctor**：init 前 doctor `action_required`（database `migration: outdated`／`degraded`），计划版本 3（09:00／21:00，开启，Asia/Shanghai）。`pring-cycle init` 返回 `ok`、网络请求 0；之后 alembic `0038_scheduled_run_at_0930`，doctor `ok`（migration current），计划**版本 4：09:30／21:00，开启，Asia/Shanghai**（`requested_by=migration-0038-scheduled-run-at-0930`）。凭据：tushare、tavily、exa enabled，eia disabled。过程目录 `doctor-pre.json`、`init.json`、`doctor-post.json`、`schedule-pre.json`、`schedule-post.json`。
- **Worker**：21:59 复测 `clock_check.py` 退出码 0；**22:00:12** 用 `setsid nohup` 脱离会话启动 `~/.local/share/pring-cycle/start-worker-acc05.sh`（`flock /tmp/pring-heavy.lock pring-cycle worker`，进程父为 `/init`）。Worker PID **199568**（flock 199567，脚本 199565）。日志：`~/.local/share/pring-cycle/worker-acc05-20261013.out`（stdout／stderr）、`worker-acc05-20261013.meta`（起止时刻与退出码）、运行时事件 `~/.local/state/pring-cycle/logs/worker.jsonl`。C 盘保护 `~/.local/share/pring-cycle/disk_guard.sh` 守 199568，下限 20G，日志 `~/.local/share/pring-cycle/guard-worker-acc05-20261013.log`。
- **首次判断**：判断“已过截止”时 Worker 不写事件，所以用以下证据确认：
  - `worker.jsonl` 新增 `worker_started`（14:00:12.723Z）一条，没有 `scheduled_run_deferred`；
  - `service_heartbeat` 为 PID 199568，心跳在走；`worker_lease` 为空；
  - `run_command` 仍是 38 条（最大编号 38），`parent_run` 37 个，没有排队或运行中的运行，**没有新建运行**；
  - 22:00:40 用全新的 `ScheduleCheck` 对真实库重放一次 `submit_schedule_if_due`（脚本只允许 21:00:30 之后、09:00 之前运行）：返回 `None`，`ScheduleCheck(day=2026-10-13, retry_at=None, settled=True)`，即“已过 21:00 截止、今日不提交”（过程目录 `verdict.txt`）。
- **留意**：Worker 持有 `/tmp/pring-heavy.lock`，停 Worker 前其他重型测试会排队等锁。停止用 `kill -TERM 199568`（不要 `kill -9`），flock 与脚本随后退出，`.meta` 记退出码。若 WSL 在夜间被关闭或 Windows 休眠，Worker 会随之停止或暂停：明早 09:30 前先确认 199568 仍在、心跳是新的。
