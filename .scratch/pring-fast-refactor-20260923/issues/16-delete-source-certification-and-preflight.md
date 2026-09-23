# 16: 删除来源认证与预检完整性

**What to build:** 删除来源认证模块（主链仍用的少量函数先迁出）和预检完整性模块，以及 model-source-certify、model-input-preflight* 命令、专属测试与相关表；主链运行不受影响。

**Blocked by:** 14

**Status:** ready-for-agent

Spec: [spec.md](../spec.md)

- [ ] 模块、CLI、专属测试删除；被迁出的函数有新归属且调用方通过
- [ ] 相关旧表经 schema 迁移删除
- [ ] 手动完整运行不经任何认证或预检步骤即完成
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments
