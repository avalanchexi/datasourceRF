# 本批双轴静态审查

基点 `68c87eaef1fa21ef62f74400f6c9b8e772fbf0ec`，工作区限定差异：
`git diff 68c87ea -- src/pring_cycle/context_projection.py src/pring_cycle/dashboard.py`，
并直接审查新测试 `tests/integration/test_derived_context_freshness.py` 和
`.scratch/pring-data-acquisition-repair/derived-freshness-boundary.md`。
不包含既有未归属CSS/JS变更。来源：spec.md、票13/14、AGENTS.md、CONTEXT.md、ADR0006/0007/0012。

## Spec

0项发现。保留派生值、期次和血缘；按模型绑定父项频率检查终止期；PMI使用月频，
信用脉冲独立检查社融月与GDP季，不误判政策生效日及预热输入。
模型采纳与当前解释排除陈旧派生值；新增测试直接验证派生ID在支持证据与缺口中的归属。
仅静态审查；不代表官方发布日历、来源认证或生产模型验收完成。

## Standards

硬规范违例0，需处理smell 0。鲜度判断复用原阈值，读取模型绑定父项频率；只检查终止期，
保留政策有效期与必要预热。stale贯通解释信号和模型采纳过滤，数值及血缘保留。
测试使用公开存取、投影和派生追踪入口，覆盖新旧期次、双as-of和采纳。
最后断言增量复核0问题：当前ID进入support，陈旧ID进入gaps。
仅静态审查，未运行应用或测试。
