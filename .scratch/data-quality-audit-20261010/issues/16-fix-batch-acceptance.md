Status: blocked
Type: task
Blocked by: 06, 07, 09, 10, 11, 12, 13, 14

# 16：修复批次收尾验收

1. 重装 dev-venv，跑一次 `python tools/check.py full`，用 `flock` 加 C 盘保护，前台守到结束。
2. 跑一次 v0015 真实运行（目标日 2026-10-09），外部调用串行。
3. 用 `python3 tools/quality/audit.py` 体检这次运行，与 [report.md](../report.md)（基于 `run-674411db…`）逐项比对，确认：
   - 票 06：住户短期、中长期改选 −10500 和 188，那 9 条错期声明不再被选中；媒体冲突的复核记录可查；受影响的投影和报告已标注；
   - 票 07、09、10、13：体检不再误判；
   - 票 11：不再产生负缓存失败回执；
   - 票 12：两项新核验都有结论；
   - 票 14：调度判断的单元测试已覆盖；
   - 其余结论没有退化。
4. 结果写入 `acceptance-<日期>.md`，经 Codex 规格轴审查后提交；更新 README、goal-fix 和记忆。

## Comments
