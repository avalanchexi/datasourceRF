Status: in-progress
Type: task
Category: enhancement

# 04：仓单历史缺口核实并单列

**What to build:** 一次性只读核实上期所（CU、RB、RU、SC、SP，2026-07-21）与大商所（PP，2026-09-09）当天是否发布了仓单日报。按结果在体检文档新增“已知历史缺口”内置表：交易所发布过标“来源缺失”（交易所已发布、TuShare 无），没发布标“上游未发布”；每条写明预计移出 120 日窗口的目标日（按上交所日历）。体检把表中条目单列，不静音、不计入真正缺失。不新接来源。

**Blocked by:** 03

**主要模块：** 体检第一层日频与第二层缺失明细；体检文档。

- [ ] 核实结果附原始来源（交易所页面或文件网址、取得时间），外部访问串行
- [ ] 内置表写入文档，脚本只依据文档实现
- [ ] 对 `run-0a8dabc2e820321b84e1` 实跑：仓单 6 格单列为已知历史缺口，“真正缺失”为 0
- [ ] 不导入 `pring_cycle`，运行库只读

## Comments

- 2026-10-13 领取：worktree 基于 recurring-input-gaps `8fc1888`；交易所核实沿用 `notes/warrant-gaps-verification.md`（六格均来源缺失，PP 为二手证据），本票不再访问外网。改动前对 `run-0a8dabc2e820321b84e1` 实跑，与 `audit-run-0a8dabc2-ticket03.md` 除耗时外逐字一致（基线）。
- 2026-10-13 文档阶段完成：`docs/development/data-quality-audit.md` 新增“日频：已知历史缺口”一节（内置表 `KNOWN_GAPS` 六格：成员、日期、来源判定、证据网址与取得时间、预计移出窗口的目标日 07-21→2027-01-14、09-09→2027-03-12，推算依据与“届时以 SSE 日历为准”），第一层类别表加“已知历史缺口”，第二层“不计入真正缺失”追加第 ③ 类。
- 2026-10-13 脚本阶段完成（按文档）：`acquisition.KNOWN_GAPS`／`KNOWN_GAP` 类、第一层专表与 `leaves_window`；`model_input` 的 `EXEMPT_ORDER` 追加 `KNOWN_GAP`。对 `run-0a8dabc2…` 实跑：仓单 6 格单列为已知历史缺口，真正缺失 7→1（仅模型用到 6→0），余下 1 项为 SOX（只计目录全部）。报告存 `audit-run-0a8dabc2-ticket04.md`。
