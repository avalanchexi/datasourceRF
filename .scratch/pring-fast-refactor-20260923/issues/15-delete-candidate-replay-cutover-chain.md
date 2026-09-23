# 15: 删除候选→回放→验收→切换链；model-activate 直接切换

**What to build:** 删除模型评估、验收、切换、演练、候选准入（剩余准入逻辑）模块及对应 CLI（model-accept/replay、验收、演练、切换、smoke 等）、专属测试与旧表；`model-activate <版本号>` 只移动生效指针，之后的运行把版本号记入批次，已有汇总不重算。见票 07 第 5、6 条。

**Blocked by:** 10, 14

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 上述模块、CLI 子命令及其专属测试文件删除；部分耦合测试改写
- [ ] 相关旧表经 schema 迁移删除，不保留数据
- [ ] 经公开入口断言：`model-activate` 切到新版本后，新运行批次记录新版本号，旧汇总不变；切回旧版本号即回退
- [ ] 生效目录仍为 59 项
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments
