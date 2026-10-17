# 06: 确认度第二阶段报错

**What to build:** 价格阶段为第二阶段、贷款少增且动量未知时，确认度缺失诊断抛 `AttributeError: 'MemberReading' object has no attribute 'action'`（决定 6，Codex 内存探针）。先在单日汇总测试缝写会失败的回归测试，再修为按规则记"未确认"；不改预期表与模型版本。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 回归测试先红后绿
- [ ] 该情形下贷款确认关系为未确认并写明缺什么
- [ ] 两项必跑冒烟通过
