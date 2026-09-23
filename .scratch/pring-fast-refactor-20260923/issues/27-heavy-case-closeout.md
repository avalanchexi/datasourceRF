# 27: 重型用例收尾：完整目录正例改写与 HEAVY_FILES 缩减

**What to build:** 完整目录正例（官方 PPI 回退）改用“直接登记 + 显式切换”的简单模型夹具，不再依赖隔离生命周期材料；`HEAVY_FILES` 只保留该例。

**Blocked by:** 11, 15, 16

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 完整目录正例在新夹具下通过，记录耗时
- [x] 不再存在依赖认证→准入→回放→激活夹具的测试
- [x] `HEAVY_FILES` 只含改写后的完整目录用例
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 完成。`test_worker_registered_catalog.py` 只保留官方 PPI 回退正例：登记并激活内置 `effective_model_manifest()`（model-v0012），核心为存档 TuShare 原件延至 2026-09-11，其余 TuShare 家族为合成行，PPI 仅官方页面可得（列表同时列出 8 月 CPI 链接，未供正文，CPI 保持缺口），EIA 为存档页面。实测 1 passed / 51.8 秒（旧版单例约 271 秒外加冷建材料约 30 分钟）。三核心反例为 `test_core_carry_forward.py`（21）。
- 同一提交把生效模型补齐为真实交付口径：以 v0003 已审定义为底（单位、维度、交付身份），加广度/商品篮子的注册来源代码、CPI/PPI/PMI/货币/社融/GDP 的 TuShare 官方抽样交付与官方回退页面、同月库存公式；否则官方回退与解析口径对不上。
- `HEAVY_FILES` 只含该文件；删除孤立的 `tests/fixtures/isolated_lifecycle_inputs.py`；testing.md 更新两例重型用例的指向与实测耗时。受影响 34 passed。
