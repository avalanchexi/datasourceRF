# 15: 验收后调整的集成验收

**What to build:** 票 11–14 合入 `cockpit-layout` 后，整体验证并交用户逐段确认（规格 [../spec-adjust-20261017.md](../spec-adjust-20261017.md)）：全套测试；按 `docs/agents/codex-delegation.md` 第五节由 Codex 在 1440/908/390 宽、明暗两主题下截图并实测（② 三卡底边差、⑥ 两栏对齐、各限高、无横向溢出）；8067（10-14）、8068（10-15）预览换成新代码；`acceptance.md` 追加本轮清单。

**Blocked by:** 11、12、13、14

**Status:** ready-for-agent

- [ ] 全套测试通过（或失败逐条说明并处理）；两项必跑冒烟通过
- [ ] Codex 截图与实测数值记入 acceptance.md，主 agent 抽查关键截图
- [ ] 8067、8068 已换新代码并可访问
- [ ] acceptance.md 有本轮逐段确认清单，等用户勾选
