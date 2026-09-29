# 05: 可采用声明模块（纯重构）

**What to build:** 把"已选来源声明能否采用"（`CONTEXT.md`：可采用声明）的家族分派集中到新模块 `src/pring_cycle/claim_adoption.py`，检索选值、上下文投影、投影内派生输入与 Worker 核心就绪共用一张家族表。**只收复核、不收选值；可观察行为不变。**

**Blocked by:** 无

**勿并行：** 02、08、15、16、17、18（同改：Worker 编排与取数；上下文投影；核心就绪；缺口展示与国债测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 2 的访谈记录（2026-09-29）；勘察见 [codex-survey-c2.md](../codex-survey-c2.md)。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状（调用点）

- 检索：`ModelInputSelector._claim_families`（`search_evidence.py:185`，8 个家族），另有仓单（`:322`）、降准（`:345`）、核心 P0（`:293`、`:416`）三条专门路径。
- 投影行：`_metric_rows`（`context_projection.py:1470–1590`）逐家族手写 `if` 分支（LPR、官方宏观、银行间、美债、ECB、降准、仓单）。
- 投影派生输入：`context_projection.py:775`（OMO 金额）、`:898`（OMO 到期推算用核心交易日）、`:943`／`:960`（政策利差）、`:1097`（贷款结构）、`:1413`／`:1421`（PMI、国债最新合格期）、`:2303`（信用脉冲父声明）。
- Worker 核心就绪：`worker.py:1146`、`:1183`（`CoreInputValidator` 核对整段输入历史）。
- 家族核对函数本身不动：`official_lpr.py:204`、`official_context.py:345`、`interbank_evidence.py:146`、`treasury_context.py:206`、`tushare_context.py:1646`、`news_rules.py:925`、`warrant_inputs.py:95`、`published_events.py:17`、`evidence.py:475`（注册契约）、`source_adapters.py:76／98`（核心）。

## 已定决定

- **只收复核**：模块输入已选好的序列，输出可采用结果。选值（`evidence.py` 的 `metric_series`、投影的 `TargetBoundEvidenceRepository` 目标日重选与降准整份公告优先）不进本模块。仓单（最新完整交付）与降准（整份公告）的选择与复核本在一个函数里，原样作为家族挂入。
- **接口形状**：输入定义版本与"指标 → 待复核的点"批量映射；**复核范围由调用方决定**（检索传 adoptable 统计期内的点，投影传可见窗口整条序列）。输出按指标给可采用声明 ID、不可采用声明 ID、缺失成员（仓单按期＋品种，降准按公告）。**不加原因码**。
- **留在检索侧**：逐成员期望（`required_dimension_members`）、事件类指标"最新一件过期不退回旧件"、`material_checks`。
- **家族表**：核心（来源身份＋原件重解析）、ECB 交叉汇率、LPR（原件∪命中原话）、官方宏观 12 族（原件∪命中原话）、银行间、美债、融资余额、指数行情、估值、降准、仓单。
- **核心 P0 纳入**：检索、Worker 核心就绪、投影 OMO 到期推算三处改走模块；核心就绪的落后期数、沿用、阻断规则仍在 Worker。
- **内置目录豁免收进模块一处**：调用方不再各写 `not in BUILTIN_CATALOG_VERSIONS`；核心来源身份检查在内置目录下照旧执行。不删除内置目录路径。
- **保持现有差异**：投影不复核融资、指数、估值（见 06）；仓单缺成员时投影判整日不完整（见 07）。纯重构期间两侧口径差异都原样保留，只把"哪一侧跳过什么"写在调用处。ECB 投影侧少的 `BUILTIN` 外层判断随集中而消失（底层已豁免，无行为差异）。
- **位置**：新建模块，传入 `EvidenceRepository`；不挂到 `evidence.py`（各家族核对函数依赖它，会循环导入）。

## 验收

- [ ] `claim_adoption.py` 持有唯一家族表；`search_evidence.py`、`context_projection.py`、`worker.py` 不再直接调用上列家族核对函数或 `CoreInputValidator`，也不再自行判断 `BUILTIN_CATALOG_VERSIONS` 以决定是否复核。
- [ ] 按 TDD 在模块接口上覆盖：每个家族至少一例"原件或命中原话损坏即不可采用"；降准官方整份公告缺成员；仓单缺仓库成员只缺该品种（模块输出层面）；内置目录豁免；补 `CoreInputValidator`、`news_claims_matching_quotes`、`select_published_rrr_events`、`treasury_claims_matching_acquisitions` 的直接测试。
- [ ] 现有穿过选值器／投影的用例（`tests/models/test_registered_model_inputs.py` 等）不改断言、全部通过，作为行为不变的回归网；纯重构期间只增不删，删除只发生在最后一步迁移。
- [ ] 迁移（本票最后一步）：`test_gap_source_repairs.py::test_treasury_yields_are_held_from_tushare_us_tycr` 的国债取值断言迁到模块接口，删除原处被迁的断言，缺口展示断言保留；不叠加。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 核心就绪，另加跑完整目录正例与三核心反例，记录退出码与耗时。
- [ ] 代码审查（规格、标准两轴）无阻断。
