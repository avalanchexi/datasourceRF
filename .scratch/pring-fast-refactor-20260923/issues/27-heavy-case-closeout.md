# 27: 重型用例收尾：完整目录正例改写与 HEAVY_FILES 缩减

**What to build:** 完整目录正例（官方 PPI 回退）改用“直接登记 + 显式切换”的简单模型夹具，不再依赖隔离生命周期材料；`HEAVY_FILES` 只保留该例。

**Blocked by:** 11, 15, 16

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 完整目录正例在新夹具下通过，记录耗时
- [ ] 不再存在依赖认证→准入→回放→激活夹具的测试
- [ ] `HEAVY_FILES` 只含改写后的完整目录用例
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments
