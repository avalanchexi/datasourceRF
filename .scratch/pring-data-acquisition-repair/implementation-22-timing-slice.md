# 票22 计时规则纵向切片（2026-09-16）

基线 HEAD `5c3149d`。按 [`issues/22-live-acceptance-cutover.md`](issues/22-live-acceptance-cutover.md) 的「2026-09-13 计时规则独立纵向切片」实施，`Software blocked by: None`。

## 交付的行为

用户从统一验收拿到质量制品、再交给切换清单校验时，看到一致的硬门结论与真实测试时长；仅超过十分钟不再导致软件验收或切换阻断。

- 生成端 `src/pring_cycle/acceptance.py`：`acceptance_suite_seconds` 不再是 `performance_gates` 中的硬门。新增文档字段 `suite_timing`，含 `target_seconds`（默认常量 `SUITE_TARGET_SECONDS = 600`）、`measured_seconds`、`target_met`、`scope="acceptance_internal_phases"` 与 `includes_failure_injections=False`（故障注入在该测量之后执行，明确不计入）。`status` 只由回归、硬门与故障注入决定，时长不参与。
- 受控边界：`run_v1_acceptance(..., suite_target_seconds=...)` 可传目标秒数，测试以极小目标触发"未达标"，不靠真实等待十分钟，也不调用私有函数。
- 消费端 `src/pring_cycle/cutover.py`：`_quality_gates_passed` 更名为公开的 `quality_gates_passed`（语义不变：全部硬门与 35 项回归通过），新增 `suite_timing_summary(document, total_seconds=...)`，把验收自身的阶段计时与整批 pytest 总耗时分列为 `acceptance_internal_phases` 与 `pytest_total` 两个口径，清单文档新增 `suite_timing` 字段。旧制品没有该字段时只报告 scope，不判失败，也不改写历史通过标记。
- CLI：`cutover-manifest` 新增可选 `--suite-total-seconds`，用于记录整批测试从开始到实际终态的总耗时。
- 文档同步为一致分类：`docs/development/local-runtime.md`、`docs/operations/direct-cutover.md`、`docs/quality/regression-traceability.md` 均改为"硬门失败才 blocked，套件耗时是优化目标并以 `suite_timing` 可见"，并说明两种计时口径不相加、不互相替代。

## TDD 与验证

- RED：新测试 `tests/integration/test_acceptance_timing.py` 6 项因接口缺失全部失败（首版用伪造时钟，因为同一时钟会拉长其他硬门而改为传入目标秒数的接缝）。
- GREEN：该文件 6 项通过；`tests/integration/test_rehearsal_cutover.py` 中原有的就绪清单用例补充断言——硬门全过而时长超标时 `quality_and_performance` 仍为 true，且清单发布两个计时口径。
- 相关回归：`test_acceptance_timing.py`、`test_rehearsal_cutover.py`、`tests/acceptance/test_v1_acceptance.py`、`tests/e2e/test_v1_cli.py` 共 25 项通过/73.9秒。
- 静态检查：ruff check/format 通过；`mypy src`（MYPYPATH=src）96 源文件通过。
- 未触发隔离材料重建（本切片不改材料构建器）。

## 未包含

- 最终同版本冻结全套（票22 的「2026-09-13 最终软件冻结与9月11日真实交付」第一项）属于计划步骤2，本切片不代替。
- 真实切换、真实来源与目标日 2026-09-11 的真实交付仍按票18/20/21 的原依赖开放。

## 两轴审查（2026-09-16）及处理

**硬缺陷（两轴都指出，已修）**：`record_direct_cutover` 重建清单时不回传 `suite_total_seconds`，因此按 `docs/operations/direct-cutover.md` 带该参数生成的清单在记录切换时必然抛 `cutover_manifest_stale`。新增 `reported_total_seconds(manifest)` 从清单自身读回该值并回传；就绪清单用例改为带 `suite_total_seconds=1975.0` 生成，随后走原有的记录切换路径。变异检查：去掉回传后该用例即以 `cutover_manifest_stale` 失败。

其余处理：

- 反例补齐三类并到达真实门禁：功能失败（某 `REG-*` 为 false）、产品性能失败、必要证据缺失，均经 `quality_gates_passed`；就绪清单用例新增断言——时长未达标时 `quality_and_performance` 仍为 true、清单 `status=ready`，两个计时口径都发布。
- 两端贯通：新增用例把 `run_v1_acceptance` 的真实产物直接交给 `quality_gates_passed` 与 `suite_timing_summary`，不再只用手写文档。
- `pytest_total` 是操作员填报值，新增校验：负数或非有限值抛 `cutover_suite_total_seconds_invalid`，并有参数化反例。
- 口径名提取为常量 `SUITE_TIMING_SCOPE`（acceptance）与 `TOTAL_TIMING_SCOPE`（cutover），消除多处硬编码字符串。
- 保留：制品 `schema_version` 仍为 `v1-acceptance-v0001`。旧制品缺 `suite_timing` 时按 scope 报告即可读，消费方以字段存在与否区分，不改写历史通过标记；若改版本号会使既有清单校验与历史比较失效。
- 说明：`acceptance.py` 中三处行宽重排不是本切片引入的噪声，而是该文件在 HEAD 上本就不满足 `ruff format`，格式化时一并规范（HEAD 版本单独跑 `ruff format --diff` 同样有差异）。

最终验证：`tests/integration/test_acceptance_timing.py` 9 通过/18.8秒；`tests/integration/test_rehearsal_cutover.py` 12 通过/68.4秒；`tests/acceptance/test_v1_acceptance.py` 与 `tests/e2e/test_v1_cli.py` 随相关回归通过；ruff check/format 通过；`mypy src` 96 源文件通过。
