Status: ready-for-agent
Type: task
Blocked by: 06, 07, 09, 10, 11, 12, 13, 14

# 16：修复批次收尾验收

1. 重装 dev-venv，跑一次 `python tools/check.py full`，用 `flock` 加 C 盘保护，前台守到结束。
2. 执行票 09 的重处理，补回 12 天七天逆回购利率（0 次外部调用）：
   - 先停 Worker，或确认没有运行中的 run；以下都在 `flock /tmp/pring-heavy.lock` 下执行。
   - 备份运行库（SQLite backup API 连同 WAL 一并备份；备份路径自定）：
     `python3 -c "import sqlite3; s=sqlite3.connect('file:$HOME/.local/share/pring-cycle/pring-cycle.sqlite3?mode=ro', uri=True); d=sqlite3.connect('<备份路径>.sqlite3'); s.backup(d); d.close()"`
   - 执行：`pring-cycle official-reprocess --metric CN_OMO_7D_RATE --start 2026-04-13 --end 2026-10-09 --definition-version metric-catalog-v0006 --json`
     - 区间取 `run-674411db…` 的 120 日窗口（目标日 10-09）。窗口外原件所述、已被留存清理的值（如 04-08～04-10 的操作量）不会补回。
     - 定义版本取生效模型 v0015 的目录版本。
   - 核验：
     - `restored` 恰为 09-01、09-07、09-08、09-10、09-11、09-16、09-17、09-18、09-21、09-22、09-23、09-29 共 12 条，`restored_claim_count=12`；
     - `skipped` 为空，`network_requests=0`；
     - 再执行一次，`restored_claim_count=0`。
   - 补回声明的时点：
     - 系统可用时间为执行时刻；
     - 原件取得时间沿用原回执；
     - 公开时间为公告发布时刻。
   - 因此第 3 步的新运行能读到这些声明，`run-674411db…` 的冻结截止读不到。这是正确的双时间语义。
3. 跑一次 v0015 真实运行（目标日 2026-10-09），外部调用串行。
4. 用 `python3 tools/quality/audit.py` 体检这次运行，与 [report.md](../report.md)（基于 `run-674411db…`）逐项比对，确认：
   - 票 06：住户短期、中长期改选 −10500 和 188，那 9 条错期声明不再被选中；媒体冲突的复核记录可查；受影响的投影和报告已标注；
   - 票 07、09、10、13：体检不再误判；票 09 的 12 天利率由第 2 步补回，不再报“原件含值、未入库”；
   - 票 11：不再产生负缓存失败回执；
   - 票 12：两项新核验都有结论；
   - 票 14：调度判断的单元测试已覆盖；
   - 其余结论没有退化。
5. 结果写入 `acceptance-<日期>.md`，经 Codex 规格轴审查后提交；更新 README、goal-fix 和记忆。

## Comments
