Status: done
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

## 验收

票面原本没有验收框，下面按第 1–5 步列出。证据见 [acceptance-20261011.md](../acceptance-20261011.md)，节号标在括号里。

- [x] 重装 dev-venv，副本与 HEAD 一致；`check.py full` 在 flock 与 C 盘保护下通过：2362 passed，0:45:39（一）
- [x] 票 09 重处理：先备份运行库，在 flock 下执行；`restored` 恰为 12 天，`restored_claim_count=12`，`skipped` 为空，`network_requests=0`；再执行一次，补回 0 条；三个时点符合双时间语义（二）
- [x] v0015 真实运行（目标日 10-09）成功，外部调用串行：`run-8186b774087648d921e3`（三）
- [x] 票 06：住户两个成员改选 −10500、188；9 条错期声明不再入选；复核表可查（本运行没有冲突，0 行）；14 个受影响投影已标注，10-09 的旧投影与旧报告有更正关系（四）
- [x] 票 07、09、10、13：体检不再误判；12 天利率已补回，不再报“原件含值、未入库”（四）
- [x] 票 11：没有负缓存失败回执（四）
- [x] 票 12：两项新核验都有结论（四）
- [x] 票 14：调度判断的单元测试在全套中通过；真实调度待观察（一、四）
- [x] 其余结论没有退化，与 report.md 的差异逐项说明（五）
- [x] `acceptance-20261011.md` 通过 Codex 规格轴审查，已提交；README、goal-fix 已更新（七）
- [ ] 记忆：交主 agent 更新

## Comments

### 2026-10-11 实施

**结果**：全部步骤完成，验收记录见 [acceptance-20261011.md](../acceptance-20261011.md)。过程文件放在 `/tmp/claude-1000/fix-16/`，运行库备份为 `/tmp/claude-1000/fix-16/backup/pring-cycle-before-16.sqlite3`。

- **全套**：重装 dev-venv 后，副本与 HEAD `4ad106b` 一致。`check.py full` 在 flock 下运行，挂 C 盘保护：**2362 passed，2739.04 秒（0:45:39）**，退出码 0。C 盘全程 58G，basetemp 峰值 27G。
- **迁移**：0034、0035 不会在新代码首次访问运行库时自动执行，迁移只在 `init`／`test`／`verify` 中发生。因此本次在备份之后、重处理之前，显式执行了 `pring-cycle init`（18:27:30Z）。执行后 doctor 为 current，标出 14 个受影响投影。
- **重处理**：补回 12 天，正好是票面所列；`restored_claim_count=12`，`skipped` 为空，0 次外调；再执行一次，补回 0 条。时点符合双时间语义。
- **真实运行**：`run-8186b774087648d921e3`，用时 11 分 29 秒；回执 148 条，失败 12 条（`fut_basic` 8、`fut_trade_cal` 4，属已有类别）；URLError 0。投影 `projection-c54d60de147a721489f8`，报告 `report-4e190187541910920fe5`。
- **体检比对**：
  - 票 06：住户两个成员改为 −10500、188；错期声明为 0；10-09 的旧投影和旧报告有更正关系。
  - 票 07、09、10、13：都不再误判。
  - 票 11：0 条失败回执，6 格都按 `warrant_day_empty_in_run_answer` 跳过。
  - 票 12：52 项检查全部一致。
  - 与 report.md 的差异逐项说明，没有退化。
- **复核成本与 `rechecks_first`**：本运行没有媒体冲突，所以 AI 复核为 0 次。`rechecks_first` 的耗时影响无法单独归因：扣除请求时间后，本地处理多 40 秒，其中混有其他因素。
- **新开票**：[17](17-audit-multi-source-note-lists-excluded-claims.md)，体检备注仍列出已排除的错期值。窗口基日 04-10 每次重取，是留存的设计内行为，不开票。
- **审查**：Codex 规格轴两轮。首轮有 2 项记录阻断，已订正；定向复审为“阻断：无”。
- **待观察**（不阻断）：
  - 票 06：真实冲突下的复核成本；
  - 票 11：暂缓形态的真实样本；
  - 票 14：跨过 18:30 的真实调度。
- **记忆**交主 agent 更新。
