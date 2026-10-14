Status: ready-for-agent
Category: enhancement
Type: task

# 13：收尾验收

**What to build:** 全套测试、备份运行库、一次不休眠的 09:30 计划运行（外部调用串行），体检两个口径的真正缺失为 0 或逐项已定性。顺带记录准点提交证据（[来源票 04](04-verify-0930-on-time.md)）并与 `run-0a8dabc2…`、`run-25ac18e4…` 对比有效耗时（[来源票 03](03-effective-run-slower.md)）。规程同[上一批票 05](../../recurring-input-gaps-20261013/issues/05-acceptance.md)。

**Blocked by:** 08、09、10、11、12；用户调好 Windows 电源设置（来源票 04）

**Status:** ready-for-agent

- [ ] 时钟检查退出码 0；全套测试一次通过（ADR-0025），记录耗时与 C 盘最低余量
- [ ] 备份运行库，记录迁移状态与 doctor
- [ ] 09:30 计划运行准点提交并完成
- [ ] 16:30 收盘价持有上一交易日；SOX 持有应有期次
- [ ] 体检：目录全部、仅模型用到两口径真正缺失为 0（或逐项已定性）
- [ ] 有效运行耗时与前两次对比，写入验收记录
- [ ] 规格轴审查用 `codex exec -s read-only`
