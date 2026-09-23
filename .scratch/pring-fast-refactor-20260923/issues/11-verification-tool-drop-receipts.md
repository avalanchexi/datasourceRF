# 11: 验证工具去收据：check.py full 去掉 --freeze

**What to build:** 开发者跑 `check.py full` 时不再需要 `--freeze`，也不产出或绑定软件/材料身份收据；只看通过与否并记录实际耗时（ADR-0025）。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] `check.py full` 无需 `--freeze` 即可运行，输出通过/失败与耗时
- [ ] 收据工具中的收据用途及其维护测试删除；`check.py quick` 行为不变（仍拒绝整目录与重型文件）
- [ ] docs/agents/testing.md 中“落地前仍需 --freeze”的注记移除
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
