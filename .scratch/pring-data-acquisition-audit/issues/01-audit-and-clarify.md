Status: superseded (was needs-info)
Type: grilling

# 全面审查数据获取至 Pring 结论

范围是本项目全部 61 项目录指标及正式运行链，包括数据正确性、可用性、Tavily / Exa 效果、阶段和报告输出。事实审查已形成[总报告](../audit.md)、[目录矩阵](../metric-inventory-notes.md)、[检索审查](../search-effectiveness.md)和[模型追溯](../model-output-trace.md)，对应 JSON 保存查询与验证证据。

Q1 已确认以模型可用缺口补齐率为主指标，定义同步到根 CONTEXT.md。Q2 关于阶段/指标计算与报告解释分别验收仍待回答；这不改变现有降级输出语义。完整讨论见[访谈记录](../interview.md)。

本票 needs-info 指访谈口径尚未闭合；不是宣称事实取证无法推进。应用修复、来源认证、新模型回放、生效及真实切换尚未完成，不将本轮审查完成记作原总目标完成。

## Comments

- 2026-09-06：事实查询只读运行库，无网络请求，无生产写入。新增文档、已确认的术语；保留旧五家族审查及原任务22/25状态。
- 2026-09-29 标记为被取代：Q1 已落入根 CONTEXT.md；待答的 Q2（阶段/指标计算与报告解释分别验收）已由 [ADR-0027](../../../docs/adr/0027-report-input-is-verified-results-without-evidence-chain.md) 取代——报告只接收已验证结果、不再逐条引用证据，"报告解释有完整证据支持"这一验收项不复存在。审查结论已于 `aeb6b41` 转成 [pring-data-acquisition-repair](../../pring-data-acquisition-repair/spec.md) 票，那批票又被 fast-refactor 路线（ADR-0021–0025、`.scratch/pring-fast-refactor-20260923`）取代。本票不再等待回答。
