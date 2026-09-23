# 10: 预重构：目录迁移与结构校验迁入目录模块

**What to build:** 生效目录（metric-catalog-v0002 加融资口径迁移与 CNY030 可选迁移）的组装不再依赖候选准入模块：迁移定义与主链仍需要的结构校验移到目录模块。用户可见行为不变，为 15 号删除候选准入铺路。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 生效目录仍为 59 项（P0 6 / P1 41 / P2 12，CNY030 为 P2），现有目录数量断言通过
- [ ] 目录组装与结构校验的调用方均不再导入候选准入模块
- [ ] 候选准入模块剩下的只有准入逻辑本身
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
