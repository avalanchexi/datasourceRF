Status: done
Category: bug
Type: task

# 09（02c）— 相同定义：原件复核与缓存键

**What to build:** 旧版本声明能通过各来源的原件复核并被采用；按版本组成的缓存键在相同定义下命中。

**Blocked by:** 07

**勿并行：** 07、08

## 验收

- [x] 原件复核认相同定义版本组：TuShare 一般／银行间／仓单 normalized 标量的版本、ECB 声明与原件参数、美债原件参数、`source_claims_matching_registered_contract`、`acquisition_outcome` 的版本条件。
- [x] 仓单解析缓存键、检索负缓存键在相同定义下命中同一结果，定义变化时不命中。
- [x] 回归：v0013 下取得、带原件的声明在 v0014 下通过可采用复核并进入投影（OMO 利率基准沿用、DR007 政策利差算出）。
- [x] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments

**2026-10-03 实施记录**（顺序提前到 08 之前，见票 07 Comments）

- **便捷方法** `EvidenceRepository.defined_alike(metric_id, stored, target)`：存储版本是否与目标版本同一定义（`None` 一律不算，接受未盖版本的由调用点自己写明）。
- **原件复核**：`source_claims_matching_registered_contract` 按行指标判同组；TuShare 一般复核按每个 normalized 标量自身的 `metric_id` 判同组（`_entry_defined_alike`，`None` 仍兼容）；银行间批次内容校验缓存键去掉版本（结果只依赖内容），版本可接受性由调用方逐标量判断，并在单次复核内按（指标，版本）缓存；仓单解析改收允许版本集合，缓存键含排序后的集合；ECB 复核路径按相同定义组比对请求参数版本，入库修订比较路径仍为单一版本；美债官方 CSV 请求参数版本按 `defined_alike`。
- **获取结果**：`BatchAcquisition.failures` 接受相同定义版本（缺版本仍按旧语义接受）；`AcquisitionOutcomes.latest` 指定版本时接受相同定义版本（缺版本仍拒绝）。
- **检索负缓存键**：契约哈希由"目录版本＋代码版本"改为"发布家族定义身份（`same_definition.family_identity`：同族全部指标的比较字段与派生公式）＋代码版本"；定义未变时跨目录版本命中，家族内共享不变。已持久化的旧键会失效一次（与代码版本变化时的既有规则一致）。
- **写入一致性守卫不放宽**：`ingest_context_scalars` 等入库时的版本一致性检查保持严格。票 08 范围（`delivered_values`、`latest_provider_claim`、`source_claim_vintages`、`claims_for_release_source`、`release_events_for_definition`、`SeriesReads`）不在本片。
- **测试**（`tests/integration/test_same_definition.py` 新增 5 例，共 20 例）：v0013 下取得、原件盖 v0013 的 TuShare DR007 在 v0014 下通过复核被采用（撤掉复核改动即失败）；**投影回归**——v0013 下导入真实央行 OMO 公告原件（`evidence-13/ee19f9d0…`，2026-08-28 利率 1.4%）与 DR007，v0014 投影算出 DR007 政策利差 −1.41bp、输入恰为两条旧声明、存储版本仍为 v0013（撤掉 `tushare_context`／`interbank_evidence` 改动即为空值）；`defined_alike` 定义变化与 `None` 边界；旧版本获取尝试对新模型可见、定义变化不可见；负缓存家族身份在未变家族跨版本相同、信用脉冲家族不同。`test_futures_warrant_completeness.py` 一处直接调用改用 `definition_versions`。
- **验证**（`PYTHONPATH=src` 直跑 pytest）：受影响 19 个文件（可采用、登记模型输入、ECB、五个官方回退、美债 CSV、仓单完整性、获取结果、负缓存、检索账本、时点证据、核心沿用、完整目录正例、两例冒烟）375 例中 374 过、1 败（上述仓单旧调用），修复后改动涉及的 4 个文件 173 例全过。ruff、mypy 通过。
- **审查**（Codex 只读，两轮）：首轮 2 个阻断（仓单测试旧调用、缺投影级回归），已修；采纳银行间平方级判断的缓存建议；二轮无阻断。未采纳的建议：负缓存实际跨版本命中、仓单解析缓存复用、ECB／美债／一般 TuShare 跨版本直接回归——由端到端采用与投影用例间接覆盖，留作后续补强。

