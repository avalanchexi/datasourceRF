# 07: Worker 缺陷集成验收

**What to build:** 01–06 合入 `worker-gaps` 后整体验证：全套测试；在 10-15 隔离副本的拷贝上用新代码重放（不访问外网，检索用已存原件）核对 ⑦：中间价持有 10-15、社融成员如实、EIA 在等待发布组、仓单历史缺期可见、AI 报告标注；写验收记录交用户。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** 01、02、03、04、05、06

**Status:** ready-for-agent

- [ ] 全套测试通过（或失败逐条说明并处理）
- [ ] 隔离副本重放结果与截图记入 acceptance.md
- [ ] 用户验收清单待勾选；正式 dev-venv 未改动
