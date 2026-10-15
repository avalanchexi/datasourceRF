Status: ready-for-agent
Category: enhancement
Type: task

# 13：收尾验收

**What to build:** 全套测试、备份运行库、一次不休眠的 09:30 计划运行（外部调用串行），体检两个口径的真正缺失为 0 或逐项已定性。顺带记录准点提交证据（[来源票 04](04-verify-0930-on-time.md)）并与 `run-0a8dabc2…`、`run-25ac18e4…` 对比有效耗时（[来源票 03](03-effective-run-slower.md)）。规程同[上一批票 05](../../recurring-input-gaps-20261013/issues/05-acceptance.md)。

**Blocked by:** 08、09、10、11、12；用户调好 Windows 电源设置（来源票 04）

**Status:** ready-for-agent

- [x] 时钟检查退出码 0；全套测试一次通过（ADR-0025），记录耗时与 C 盘最低余量
- [x] 备份运行库，记录迁移状态与 doctor
- [ ] 09:30 计划运行准点提交并完成
- [ ] 16:30 收盘价持有上一交易日；SOX 持有应有期次
- [ ] 体检：目录全部、仅模型用到两口径真正缺失为 0（或逐项已定性）
- [ ] 有效运行耗时与前两次对比，写入验收记录
- [ ] 规格轴审查用 `codex exec -s read-only`

## Comments

### 2026-10-14 用户决定（主 agent 转达）

10-14 晚准备，用 10-15 09:30 的计划运行（目标日 10-14）做验收；用户把 Windows 设为不休眠。

### 2026-10-14 第一段（收尾验收子代理 ticket-13）

代码为集成分支 `59088cd`。过程文件在会话 scratchpad 的 `acc13/`（`/tmp/claude-1000/-mnt-d-cursor-datasourceRF/71c0b6ae-24e4-4792-a927-97731c5caabc/scratchpad/acc13/`，下称“过程目录”；WSL 重启会丢）。

- **开跑前**：22:03 `python3 tools/clock_check.py` 退出码 0（65 秒内无超过 0.2 秒的跳步）。`systemd-timesyncd` 为 disabled／inactive。C 盘起始 55G。heavy 锁空闲，没有 Worker 在跑。
- **dev-venv**：在本 worktree 下执行 `UV_PROJECT_ENVIRONMENT=$HOME/.local/share/pring-cycle/dev-venv uv sync --extra dev --no-editable --reinstall-package pring-cycle`。安装来源从主工作区换成本 worktree，安装副本与 `src/pring_cycle` 逐文件一致（`diff -rq` 无差异），ruff 0.16.5。
- **全套**：
  - 22:03:53 在 `flock /tmp/pring-heavy.lock` 下开跑 `tools/check.py full`，`tools/disk_guard.sh` 守 pytest 进程 465309，下限 12G。
  - 结果 **2510 passed in 4329.16s（1:12:09）**，退出码 0，23:16:08 结束，墙钟 4335 秒。0 失败，无需复跑。
  - C 盘从 54G 降到 **最低 47G**（145 次采样），保护没有触发。
  - 最慢的文件：`test_full_run_retrieval.py`（383.2 秒）、`test_worker_registered_catalog.py`（260.1 秒）、`test_rrr_backtrack.py`（238.3 秒）、`test_tushare_news.py`（236.5 秒）。前 10%（251 例）占测试阶段耗时的 87.6%。
  - 日志：过程目录 `full.log`、`full.meta`、`guard-full.log`；计时文件 `timings-full.jsonl`。
  - 两个小插曲：worktree 里的 `tools/disk_guard.sh` 没有执行位，改用 `bash` 调用。第一次用 `pgrep -f 'pytest -q'` 误挂到了 shell 自身，那个保护随即退出，没有写日志，不影响结果。
- **备份**：`~/.local/share/pring-cycle/backups/pring-cycle-before-acc13-20261014-2329.sqlite3`，用 SQLite backup API 做，耗时 41 秒，大小 3.0 GB，integrity ok。
  - 当时库中 alembic 为 `0038_scheduled_run_at_0930`，运行 38 个，`run_command` 最大编号 39，评估 295，投影 295（过程目录 `backup.txt`）。
  - 它是 10-15 计划运行之前的回滚点。
- **迁移与 doctor**：
  - init 前 doctor 为 `ok`（migration current），计划**版本 4：09:30／21:00，开启，Asia/Shanghai**。
  - 本批没有新迁移。`pring-cycle init` 返回 `ok`，网络请求 0。之后 alembic 仍为 `0038`，doctor `ok`，计划不变。
  - 凭据：tushare、tavily、exa enabled，eia disabled。
  - 过程目录 `doctor-pre.json`、`init.json`、`doctor-post.json`、`schedule-pre.json`、`schedule-post.json`。
- **Worker**：
  - 23:31 复测 `clock_check.py`，退出码 0。
  - **23:31:23** 用 `setsid nohup` 脱离会话启动 `~/.local/share/pring-cycle/start-worker-acc13.sh`（`flock /tmp/pring-heavy.lock pring-cycle worker`，脚本的父进程是 `/init`）。Worker PID **489556**（flock 489555，脚本 489553）。
  - 日志：`~/.local/share/pring-cycle/worker-acc13-20261014.out`（stdout／stderr）、`worker-acc13-20261014.meta`（起止时刻与退出码），运行时事件在 `~/.local/state/pring-cycle/logs/worker.jsonl`（启动前 184 行）。
  - C 盘保护：`~/.local/share/pring-cycle/disk_guard.sh` 守 489556，下限 20G，日志 `~/.local/share/pring-cycle/guard-worker-acc13-20261014.log`（起始 47G）。
- **首次判断**：
  - `worker.jsonl` 新增一条 `worker_started`（15:31:23.761Z），没有 `scheduled_run_deferred`。
  - `service_heartbeat` 为 PID 489556，心跳在走；`worker_lease` 为空。
  - `run_command` 仍是 39 条（最大编号 39），`parent_run` 38 个，**没有新建运行**。
  - 23:31:54 用全新的 `ScheduleCheck` 对真实库重放一次 `submit_schedule_if_due`，返回 `None`，`ScheduleCheck(day=2026-10-14, retry_at=None, settled=True)`，即“已过 21:00 截止，今日不提交”。过了截止的这条分支不读日历、不发请求（过程目录 `verdict.txt`）。
- **0:00 后预期的外部调用（票 08 次晨补取）**：
  - 已存的上交所日历写明 10-12、10-13、10-14 开市；`CN_USDCNY_CLOSE_1630`（`metric-catalog-v0006`）已持有的最近一期是 10-09。
  - 10-14 晚间窗口（16:35–21:00）没有 Worker 在线，所以 10-15 0:00 之后到 09:30 之前，Worker 会向外汇交易中心请求一次，目标是 10-14 的收盘价。持有后不再请求；没取到会每 10 分钟重试。
  - 第二段核对：这次补取是否持有 10-14，以及 09:30 运行的冻结输入里是否有它。
- **留意**：
  - Worker 持有 `/tmp/pring-heavy.lock`，停 Worker 前其他重型测试会排队等锁。
  - 停止用 `kill -TERM 489556`，不要 `kill -9`；flock 与脚本随后退出，`.meta` 记退出码。
  - 明早 09:30 前先确认 489556 仍在、心跳是新的。另外查保护日志有没有断档，以确认机器没有休眠。

### 2026-10-15 补交（主 agent）

- 10-15 00:00:00 Worker 按票 08 次晨补取 10-14 的 16:30 收盘价：回执 `acquisition-5b9f2fe5…` validated，入库 1 条（6.6925）。
- 02:27:48 WSL 停止：Windows 更新（KB5127648、KB5127690）约 02:28 自动重启，系统事件 02:30 开机、02:33 记安装成功；WSL 到 09:22:54 才随用户登录重启。Worker 489556 随之终止，`.meta` 无退出码行，09:30 计划运行未提交，**准点样本再次落空**（原因是更新重启，不是休眠）。
- 09:4x 时钟检查退出码 0、timesyncd disabled／inactive；dev-venv 安装副本与集成分支 `src/` 逐文件一致。用户同意后 09:49:22 用同一脚本重启 Worker（PID 11056，flock 11055），C 盘保护 `guard-worker-acc13-20261015.log`（下限 20G）。
- 首次判断即补交：`run_command` 40，`scheduled_full`，幂等键 `scheduled-2026-10-14-v4`，`run-0eb9553118ba92a183b9`，受理 01:49:24Z。
- 第一段过程目录（scratchpad `acc13/`）随 WSL 重启丢失；第一段要点已记在上文。
