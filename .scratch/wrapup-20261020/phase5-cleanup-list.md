# 阶段 5 清理清单（等用户批准）

生成时间 2026-10-20 15:45。规则：只删已并入 main（或上线后将并入 main 的 `macro-followups`）且工作区干净的 worktree 与分支；分支一律 `git branch -d`（未合并的会被拒）；删前再核一次合并状态与工作区。

## A. 现在可删（已并入 main、工作区干净）

worktree（`git worktree remove`）与同名分支（`git branch -d`），约 5.2G：

- conclusion-board、cockpit-layout、cl-11～cl-15（`/home/tywin/worktrees/datasourceRF-cb`、`-cl`、`-cl-11`～`-cl-15`）
- input-gap-residuals（`-igr`）
- macro-stage（`-ms`）
- worker-gaps、wg-01～wg-07（`-wg`、`-wg-01`～`-wg-07`）
- `.claude/worktrees/` 下 6 个代理 worktree：agent-a4647e05…、agent-a54c8d41…、agent-a6e01e25…、agent-a90aac76…、agent-a9161553…、agent-ad5379ac…（分支 worktree-agent-*、rig-09-sox-source）
- 无 worktree 的已合并分支：report-reading-20261015

测试 venv（`~/.local/share/pring-cycle/` 下），共约 1.3G：dev-venv-cl10～cl15、fd01～fd03、gl01～gl05、golive、ms02～ms10、msfix、mspre、rig08、rig09、rig11、rigfix、wg01～wg07。

旧备份（保留最近 3 份），约 8.5G：
- pring-cycle-before-fub09-20261013-1126.sqlite3（及 -shm/-wal）
- pring-cycle-before-acc05-20261013-2157.sqlite3（及 -shm/-wal）
- pring-cycle-before-acc13-20261014-2329.sqlite3（及 -shm/-wal）

旧 Worker 启动脚本与日志：start-worker-acc05/acc13/golive-20261019/makeup-*.sh 及对应 .meta/.out、guard-worker-*.log（resident 的保留）；web-8069-20261019.out、web-8069-20261020.out（web-8069-v0016.out 保留）。

## B. 上线并入 main 后再删

- 集成分支 macro-followups 与 ms-11～ms-16、ms-rf、ms-rf2a/2b/2c、ms-rf3a、ms-rf4 共 13 个 worktree 与分支（约 3.2G）
- 测试 venv：dev-venv-mf、ms11～ms16、msrf、msrf2a/2b/2c
- 上线前新备份完成后，pring-cycle-before-golive-20261019.sqlite3 成为第 4 份，删除（保留 smallbatches、v0016、macro-followups 三份）

## C. 保留

- 主工作区 main；`prototype/macro-stage`（`-ms-proto`）与 `prototype/ui-replan-20261003` 两个原型分支（未合并，按约定保留）
- 正式环境：dev-venv、pring-cycle.sqlite3、artifacts、start-worker-resident.sh 与 resident 日志
- `/home/tywin/worktrees/macro-stage-notes/`（代码地图）

## D. 需要你看（不在本次删除范围）

- `/home/tywin/worktrees/datasourceRF-window-20260922/ticket-01～06`：分支已并入 main，但每个 worktree 有约 25 个已修改的 `.scratch` 票文件和约 870 个未跟踪文件（共约 3.6G）。删除会丢掉这些本地改动，是否要先看一下内容再定？

## 执行记录（2026-10-20 16:00，用户"全部确认"）

- A 组：删 23 个 worktree 与分支（cb、cl、cl-11～15、igr、ms、wg、wg-01～07、6 个 .claude 代理 worktree）及 report-reading-20261015、worktree-agent-ad5379ac 两个分支；删前逐个复核工作区干净且已并入 main，分支均 `git branch -d`。
- B 组（上线后）：删 macro-followups 与 ms-11～16、ms-rf、ms-rf2a/2b/2c、ms-rf3a、ms-rf4 共 13 个 worktree 与分支。
- 测试 venv：删除 48 个，只留正式 dev-venv。
- 备份：删 fub09、acc05、acc13、golive-20261019；保留 smallbatches、v0016、macro-followups 三份。
- 旧 Worker 启动脚本、meta/out、guard 日志与旧 web 日志已删，resident 与 v0016 起的保留。
- D 组 window-20260922 六个 worktree 按推荐保留未动。
- 磁盘：WSL 内部已用 136G → 121G（另有全套与子代理临时目录约 31G 已清）；C 盘余量 24G → 23G 未回升，因 WSL 虚拟磁盘不自动收缩，需用户在 Windows 侧 `wsl --shutdown` 后压缩 VHD 才能回到 C 盘。
