# 20: P2 宽松路径、预算与 Exa 备用

**What to build:** P2 在主机属于白名单时接受 Tavily 或 AI 抽出的值（保存原文及哈希），放开 P2 的 AI WebSearch；USDCNY 16:30、VIX、SOX 登记白名单主机。预算：取消每日硬上限，Tavily/Exa 每次运行上限 16/8，AI WebSearch 每缺口每次运行至多一次；Exa 只在 Tavily 月度限额耗尽后顶替。

**Blocked by:** 19

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 经公开入口断言：P2 宽松路径被采纳，记录抽取方式与原文哈希
- [ ] Tavily 未达月限额时不调用 Exa；达限后由 Exa 顶替
- [ ] 每次运行 Tavily ≤16、Exa ≤8；同一缺口 AI WebSearch 每次运行至多一次
- [ ] 三项 P2 有登记主机，可经宽松路径取值
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments
