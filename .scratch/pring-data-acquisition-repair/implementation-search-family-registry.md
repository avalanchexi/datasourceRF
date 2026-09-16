# 家族选择链去重（代码健康 P1，2026-09-16）

依据 [巡检](codebase-health-survey-20260916.md) 优先级 1。

## 改前的形状

`ModelInputSelector.select` 为 9 个注册家族各抄一遍同一段：判断目录非内置 → 按该家族的指标集合取点位（有的要 `tuple`、有的要 `metric → series` 映射）→ 调用该家族的 `*_claims_matching_acquisitions` → 得到有效声明集合。随后在接受条件里，**同样 9 个家族又各写一段** `and (metric_id not in FAMILY or 内置目录 or claim_id in valid_family_ids)`。合计 18 处同形重复；新增一个家族要改两处。

## 改后

新增 `_ClaimFamily(name, owns, check)` 注册表条目：`owns` 判断某指标是否属于该家族，`check` 接收本家族在本次范围内的指标集合、返回有效声明集合，家族特有的参数（`definition_version`、`artifacts`、`database_path`、`mode`、`as_of`、`parse`）在各自条目里闭包捕获。

- `select` 先算一次 `registered = self.version not in BUILTIN_CATALOG_VERSIONS`（原先每个家族各写一遍），再遍历注册表得到 `valid_family_claim_ids`。
- 接受条件的 9 段合并为一个 `all(not family.owns(metric_id) or not registered or claim.claim_id in valid_family_claim_ids[family.name] for family in families)`。
- 核心资产（`CORE_API_IDENTITIES`）不进注册表：它的两条判定不是"声明 ID 在集合内"的形状（`selected_core_claim_is_valid` 与 `CoreInputValidator.is_valid`），保持原样。
- 语义保持不变：未注册目录（内置版本）时各家族收到空指标集合，与原先传空序列一致；接受条件里 `not registered` 对应原来的 `self.version in BUILTIN_CATALOG_VERSIONS`。

文件 615 行 → 543 行。新增家族现在只加一条注册表条目。

## 等价性验证

这是完整运行每次选值都会走的热路径，因此用覆盖全部九个家族的既有用例做前后对比，而不是新写断言：

- `tests/integration/test_full_run_retrieval.py` + `tests/models/test_candidate_admission.py`：**691 通过/3104.1秒（51:44），零失败**。
- 抽样对照耗时：`test_p2_projection_separates_acquisition_condition_from_certification` 三个参数改前 163.1 秒、改后 151.8 秒，无性能退化。
- ruff check/format 通过；`mypy src`（96 源文件）通过。

## 未做

巡检的优先级 2（`tushare_context.py` 2,697 行与 `official_context.py` 2,453 行按采集/入库/体检拆分）留待下一批；它与本项同形，但涉及面更大，且会再次使隔离材料失效。
