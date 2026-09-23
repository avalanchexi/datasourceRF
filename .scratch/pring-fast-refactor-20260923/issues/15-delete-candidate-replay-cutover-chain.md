# 15: 删除候选→回放→验收→切换链；model-activate 直接切换

**What to build:** 删除模型评估、验收、切换、演练、候选准入（剩余准入逻辑）模块及对应 CLI（model-accept/replay、验收、演练、切换、smoke 等）、专属测试与旧表；`model-activate <版本号>` 只移动生效指针，之后的运行把版本号记入批次，已有汇总不重算。见票 07 第 5、6 条。

**Blocked by:** 10, 14

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 上述模块、CLI 子命令及其专属测试文件删除；部分耦合测试改写
- [x] 相关旧表经 schema 迁移删除，不保留数据
- [x] 经公开入口断言：`model-activate` 切到新版本后，新运行批次记录新版本号，旧汇总不变；切回旧版本号即回退
- [x] 生效目录仍为 59 项
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 与 16 同一提交完成（两票共享演练模块）。删除 `model_evaluation`、`acceptance`、`cutover`、`candidate_admission`、`model_outputs`；CLI 删除 model-accept/replay/replay-show/acceptance-show/rollback、acceptance、rehearse-fixture-recovery/real、cutover-*。`ModelRepository` 只剩登记（新增 `register` 与 CLI `model-register`）、显式激活、历史与读取；迁移 0025 删除 model_acceptance/replay/rollback、model_evaluation_output、system_cutover，0002 内冻结旧模型 schema 文本。投影身份纳入批次 id，同日重跑生成新汇总。
- 测试：`tests/fixtures/model_registration.py` 以直接登记取代准入（原准入测试文件改名 `test_registered_model_inputs.py`，删去 65 个准入门禁用例，保留 80 个家族输入用例）；整删候选回放、校准、回退、隔离生命周期、迁移准入、验收、演练切换等 18 个文件；新增 `test_model_version_switch.py`（登记→激活→新批次记新版本、旧汇总不变、切回即回退）与目录 59/6/41/12 断言。
- 依赖隔离生命周期材料的完整目录正例与三核心反例文件随生命周期一并删除，按 27、21 以“直接登记＋显式切换”重建；此票未跑该两例。

- 2026-09-24 回填：完整目录正例与三核心反例已包含在终点全套（票 28）中一并运行。`check.py full` 退出码 0，1211 例通过，用时 4051.5 秒；其中完整目录正例 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 用时 125.6 秒，三核心反例（`test_core_carry_forward.py`、`test_core_official_fill.py`、`test_structural_rejection.py`）均通过。
