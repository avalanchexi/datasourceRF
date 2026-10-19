# 02: 报告输入剔除嵌套溯源 ID

**What to build:** 10-19 报告输入比 10-16 大 48%，主要来自注册仓单嵌套的 389 个首末日 claim ID（调查第 1 节）。报告输入改为字段白名单或递归剔除溯源 ID，AI 仍能引用所需事实；报告解释校验不受影响。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 报告入口测试：输入不含嵌套 claim／observation ID，体积显著下降；必需事实字段仍在
- [ ] 两例冒烟通过
