# 05: 不可检索的缺口不搜，列为“无可检索来源”

**What to build:** 完整运行中，不可检索的缺口（派生指标、NHII）经 TuShare 与资讯级后不进入搜索级（Tavily/Exa/AI），缺口清单出现“无可检索来源”分组。

**Blocked by:** 01

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 经公开入口断言：派生指标缺口不发起 Tavily 请求，列为“无可检索来源”
- [ ] 页面与报告缺口清单显示“无可检索来源”中文标签
- [ ] 可检索缺口的搜索行为不变
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
