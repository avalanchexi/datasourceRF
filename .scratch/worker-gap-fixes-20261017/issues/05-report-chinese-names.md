# 05: AI 报告用中文名

**What to build:** AI 解读正文出现 `tushare:index_daily`、`stage_iii`（决定 5）。报告输入保留机器字段并附中文展示名（指标、来源、阶段）；提示词要求正文用中文名；报告解释校验发现原始代号时照常保存、报告详情标"含未翻译代号"，不判失败。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 报告输入含中文展示名，机器字段不变
- [ ] 正文含原始代号的报告照常保存并带标注；不含时无标注
- [ ] 报告详情抽屉显示该标注
- [ ] 两项必跑冒烟通过
