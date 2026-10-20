# 13: 报告宏观陈述校验误拒真实 AI 输出

**What to build:** v0016 首个正式运行（run-3ebbe323，目标日 10-19）的 AI 报告，codex 与 claude 两份输出都被 `macro_stated_stage` 误拒、退回确定性模板。两份输出对阶段、得分、把握程度的陈述都正确，是校验把合法提法归错了 subject。修复后，这两份真实输出应全部通过，真正改写主结论、得分或把握程度的输出仍被拒。根因、两份原文与离线复现见 `../investigations/report-rejection-20261020.md`。

三处误判：
1. 得分前缀缺"各得"："第三阶段、第四阶段、第五阶段各得 3 维"中的第四、第五阶段被归为主结论。
2. 否定的把握程度："不能解释为明确结论""不是明确的结论"被当作肯定的"明确"。
3. 条件推演的作用域："如果 PMI 改按少数方向计票……判断会变为第五阶段，把握程度为明确（5 维中 4 维吻合），对应第三阶段向第五阶段转换"中，阶段、把握程度和转换端点应按 `rejudged` 核对，而不是主结论。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 两份真实输出（artifacts 中 sha256 cefc2e68…、2e134d3a…，配冻结 bundle-612f01b4 的宏观块）固化为离线回归样本：整份文档通过校验，`confidence_told=True`
- [ ] 上面三类真实句子各有整句正例
- [ ] 反例仍拒收："各得 4 维"→ `macro_stated_score`；"宏观判断为第四阶段，把握程度为倾向"→ `macro_stated_stage`；"宏观判断为第三阶段，把握程度为明确"→ `macro_stated_confidence`；条件分句里写与 `rejudged` 不符的阶段或把握程度 → 拒收
- [ ] 不靠扩大 `allowed["conclusion"]` 或"句中有否定词就跳过整句"来放行
- [ ] 两例冒烟通过
