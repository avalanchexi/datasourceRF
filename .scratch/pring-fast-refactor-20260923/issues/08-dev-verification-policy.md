Type: grilling
Status: resolved
Blocked by: 03

# 确定精简后的开发验证策略

## Question

取代 ADR-0014 与 docs/agents/testing.md 中“同版本必需全套、重型验收串行、收据绑定、两轴审查”的要求：日常改动跑什么、何时跑端到端主流程用例、全套是否还保留以及触发条件、被删门禁的测试如何清理；目标耗时各是多少。

## Answer

2026-09-23 与用户两轮访谈确定。取代 ADR-0014 与 `docs/agents/testing.md` 的“冻结全套＋收据绑定＋重型串行＋两轴审查”。

1. **日常改动**：沿用 `python tools/check.py quick <受影响文件或 node id>`，按改动及其调用方选择，拒绝整目录；目标 ≤3 分钟。
2. **端到端冒烟**：由研究 03 建议改写为——两例快速正例（`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability` 补报告断言；`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` 去 `certification_status`，合计约 30 秒）；一例完整目录正例（官方 PPI 回退，改“直接登记＋显式切换”简单模型夹具）；三核心反例按票 07 改为“落后 ≥2 期阻断”并新增“落后 1 期核心沿用”一例。每个实施切片收尾跑两例快速正例；改动涉及 Worker 编排、目录或来源时加跑完整目录与反例。
3. **全套**：保留 `check.py full`，**只在到达终点前、真实运行之前跑一次**；包含全部耗时测试（完整目录端到端、`test_full_run_retrieval.py`、保留的准入测试等）。取消 `--freeze` 收据语义，只看通过与否，并记录实际耗时。
4. **收据与重型清单**：删除软件/材料身份收据机制（`tools/inputs.py` 的收据用途、`tests/maintenance/test_verification_inputs.py`、`.scratch` 材料绑定）；`HEAVY_FILES` 缩为只含改写后的完整目录用例。
5. **被删门禁测试的清理**：与对应模块同一切片删除；22 个专属文件随模块整删，47 个部分耦合文件在修改其模块的切片内一并改写。
6. **两轴审查**：不再强制，用户需要时再跑。
7. **目标耗时**：quick ≤3 分钟、快速冒烟 ≤1 分钟；全套不设硬上限（推断 30–50 分钟，如实记录）。本 effort 不引入 pytest-xdist 并行。

`docs/agents/testing.md` 的改写与取代 ADR-0014 由票 09 统一完成。

## Comments

- 2026-09-23 已解决；答案见上。
