# 10: 预重构：目录迁移与结构校验迁入目录模块

**What to build:** 生效目录（metric-catalog-v0002 加融资口径迁移与 CNY030 可选迁移）的组装不再依赖候选准入模块：迁移定义与主链仍需要的结构校验移到目录模块。用户可见行为不变，为 15 号删除候选准入铺路。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 生效目录仍为 59 项（P0 6 / P1 41 / P2 12，CNY030 为 P2），现有目录数量断言通过
- [x] 目录组装与结构校验的调用方均不再导入候选准入模块
- [x] 候选准入模块剩下的只有准入逻辑本身
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-23 完成：四个迁移定义与 `migrated_catalog`、结构校验 `validate_model_catalog`（目录范围、身份字段、频率、角色、三核心、趋势参数、阶段映射、规则版本、证据窗口、公式）迁入 `catalog.py`；`candidate_admission.py` 只剩认证包、认证状态、执行指纹、回放/校准范围。四个迁移测试 + 目录测试 65 passed / 64 秒；`test_candidate_admission.py` 654 passed / 1609 秒（不属 quick 范围，单独跑）；两例冒烟通过。
