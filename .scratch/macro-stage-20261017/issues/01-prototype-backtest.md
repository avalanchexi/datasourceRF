# 01: 原型回测

**What to build:** 特征表冻结前的回测（决定 4、13）。用完即弃的脚本，在隔离副本上逐月取时点，只用 `available_at` 已到的数据，复用现有关键指标读法按决定 7 算五维方向、按决定 8 特征表与决定 9 选取规则算六阶段得分与宏观判断；输出每月表格（五维方向、各阶段得分、判断、当时价格阶段）与小结（跳变次数、并列与证据不足月数、与价格阶段一致/偏离分布、I 与 VI 混淆情况、3 分门槛是否合适）。不写测试；脚本与输出保存在 `prototype/macro-stage` 分支，结论写回规格 Further Notes。终点交用户决定特征表与门槛是否调整。规格 [../spec.md](../spec.md)，决定 [../decisions.md](../decisions.md)，调查 [../investigation.md](../investigation.md)，ADR-0043。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 回测范围（月数）与数据缺口如实说明
- [ ] 10-15 时点结果与手算（第五阶段 4/5）一致或说明差异
- [ ] 小结覆盖跳变、并列、证据不足、价格偏离、I/VI 混淆、门槛
- [ ] 用户已看过并决定特征表与门槛（记入 decisions.md）
