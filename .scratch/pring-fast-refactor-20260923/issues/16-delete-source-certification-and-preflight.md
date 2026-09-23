# 16: 删除来源认证与预检完整性

**What to build:** 删除来源认证模块（主链仍用的少量函数先迁出）和预检完整性模块，以及 model-source-certify、model-input-preflight* 命令、专属测试与相关表；主链运行不受影响。

**Blocked by:** 14

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 模块、CLI、专属测试删除；被迁出的函数有新归属且调用方通过
- [x] 相关旧表经 schema 迁移删除
- [x] 手动完整运行不经任何认证或预检步骤即完成
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 与 15 同一提交完成。删除 `source_certification`、`material_preflight`、`core_input_requirements`、`context_replay_scope`、`rehearsals`、`source_history` 及各适配器的 smoke 函数；CLI 删除 model-source-certify/refresh、model-input-preflight(-read) 与全部 *-smoke。主链未使用这些模块的函数，无需迁出。认证、预检、演练结果只存为内容寻址制品，无专属表可删（“相关旧表”项因此为空操作）。专属测试 7 个文件整删，适配器文件中 3 个 smoke 用例删除。`tools/reclaim.py` 随生命周期材料一并删除，`local-runtime.md` 同步去掉上述命令与材料章节。
- 完整目录正例与三核心反例未跑，理由同 15。

- 2026-09-24 回填：完整目录正例与三核心反例已包含在终点全套（票 28）中一并运行。`check.py full` 退出码 0，1211 例通过，用时 4051.5 秒；其中完整目录正例 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 用时 125.6 秒，三核心反例（`test_core_carry_forward.py`、`test_core_official_fill.py`、`test_structural_rejection.py`）均通过。
