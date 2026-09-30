# 23: 信用脉冲模块（纯重构）

**What to build:** 把信用脉冲（`CONTEXT.md`：信用脉冲）的回看需求、输入解释、算术、失败状态与血缘集中到新模块 `src/pring_cycle/credit_impulse.py`；Worker 取数起点、完整运行规划、上下文投影都改走它。**三个现有公式版本原样收进模块，两套回看口径原样保留，可观察行为不变。**

**Blocked by:** 05、10（05 与本票同改信用父声明复核附近；10 把目标日／补算日的上下文调用与 `persist_derived` 所在路径移入单日汇总模块，本票在其后接入）

**勿并行：** 06、07、08、09、11、15、16、17、18（同改：Worker 编排与取数；上下文投影；完整运行规划；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 5 的访谈记录（2026-09-29）；勘察见 [codex-survey-c5.md](../codex-survey-c5.md)。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 现状

- 期数 24／8 写在 `full_run_requirements.py:108`，只被规划（`formula_requirements`，`:120`，按版本与已持有口径条件加基期）和 Worker 取数起点（`worker.py:1979`，无条件加一期）共用；投影 `_credit_impulse_proxy`（`context_projection.py:2143`，约 250 行）另写 24、8、12、4。
- 版本分派在规划（`:147`）与投影（`:2196`、`:2267`）各写一次 `in {...}`；三个版本：`credit-impulse-v0001`、`credit-impulse-rolling-share-v0001`、`credit-impulse-ytd-flow-v0002`（`models.py:66`、`:89`、`:150`）。
- 投影返回松散三元组（行、公式诊断文档、ID 元组）；多条失败分支都只报 `missing_inputs`。
- `calculate_credit_impulse` 在 `domain/macro.py:49`，生产调用只有投影一处。

## 已定决定

- **只做信用脉冲**；派生观测身份与保存（`_derived_observation_identity`）仍共用、不收；其余 7 个派生公式不并入。
- **收**：回看需求、输入解释（直接单期／年初至今差分、连续性、GDP 同批交付即同一数据版本及公告核对）、算术、失败状态、血缘。**不收**：TuShare 取数、父声明能否采用（调用票 05 的可采用声明模块）、派生身份与保存、时效标签（`_period_freshness`）与投影行拼装。
- **接口**：
  - `lookback_start(metric_id, latest_period)`：Worker 取数用，保留现行"无条件加一期"。
  - `requirements(formula_version, selector, periods)`：规划用，替代 `formula_requirements` 里的信用分支，保留现行条件加基期。
  - `derive(repository, formula_version, *, as_of, as_of_mode, definition_version) -> CreditImpulseResult`：投影用。
  - `CreditImpulseResult`：状态、值、单位、统计期、GDP 输入口径、社融与 GDP 窗口、父声明 ID、公式版本、最大系统可用时间与公开可用时间。
- **三个版本作为模块内显式版本策略**，调用方不再写版本集合判断；`calculate_credit_impulse` 并入模块，`domain/macro.py` 中删除。
- `persist_derived` 语义不变（控制整个上下文，补算日仍为 `False`，见票 12）；票 10 之后该开关由单日汇总模块传入。
- **保持现有差异**（写进模块文档，另票处理）：回看两套口径（24）、直接口径按"有声明"而非"可用"计数且不比较终点（26）、`stale_inputs` 在缺口清单被当失败（27）、笼统 `missing_inputs`（28）。

## 验收

- [x] `worker.py`、`full_run_requirements.py`、`context_projection.py` 不再出现信用脉冲的期数、切片或版本集合判断；`_credit_impulse_proxy` 只剩调用模块、身份持久化、时效标签与拼行。
- [x] 按 TDD 在模块接口上直接测：24／8、25／8、24／9、25／9 需求；社融与 GDP 两种差分；断期两种状态；GDP 同批交付放行、单季修订拒绝；分母非正；公式未配置；三个版本各至少一例成功计算（补上勘察 7.11 列出的空白）。
- [x] 现有投影与完整运行用例不改断言、全部通过，作为行为不变的回归网（纯重构期间只增不删）。
- [x] 迁移（本票最后一步）：`test_full_run_retrieval.py:904`、`:976` 的需求规则断言迁到模块接口，完整运行只留一例验证需求接入计划；`test_context_projection.py:1306` 的差分参数化整体下移；`test_worker_reviewed_context.py:197` 的数据版本规则迁到模块，保留一例交付关联集成；`:277` 的日期规则迁到模块，适配器请求参数断言保留；`tests/domain/test_macro_states.py:89`、`:101` 随函数迁移。删除被迁的断言，不叠加。投影层保留持久化与追溯、时效标签、宏观 support／gap；缺口测试留在缺口清单层。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 取数，另加跑完整目录正例，记录退出码与耗时。
- [x] 代码审查（规格、标准两轴）无阻断。

## Comments

**2026-09-30 实施记录**

- **模块** `src/pring_cycle/credit_impulse.py`：
  - `lookback_start(metric_id, latest_period)`（Worker 取数，照旧无条件多取一期）；
  - `requirements(formula_version, selector, periods)`（规划，照旧条件加基期）；
  - `derive(repository, formula_version, as_of=, as_of_mode=, definition_version=) -> CreditImpulseResult`（投影用）；
  - `calculate(...)`：从 `domain/macro.py` 迁入，原处删除；
  - `VERSIONS` 用显式策略写出三个版本：GDP 能否由年初至今差分、社融能否由年初至今差分。
  - 父声明能否采用改为调用可采用声明模块。派生身份与保存、时效标签、拼行仍留在投影。
- **调用方**：
  - `_credit_impulse_proxy` 只剩调模块、派生身份、时效标签和拼行；
  - `full_run_requirements.formula_requirements` 的信用分支改调 `requirements`；
  - Worker 的 `_credit_lookback_starts` 改调 `lookback_start`；
  - `_SUPPORTED_FORMULA_VERSIONS` 的信用集合改为 `set(credit_impulse.VERSIONS)`。
- **附带搬迁**：
  - `preceding_periods` 移到 `retrieval.py`（与 `matches_retrieval_period` 同属统计期计算），避免信用模块反向依赖规划模块；
  - 投影的 `_selected_claim`、`_usable_point` 移到 `evidence`，成为公开的 `selected_claim`、`usable_point`，投影按原私有名导入，调用处不变。
- **测试**：
  - 模块接口 20 例（`tests/integration/test_credit_impulse.py`）：算术（从 `test_macro_states` 迁入，分母非正分当期和前期）；取数起点；规划需求 24/8、25/8、24/9、25/9，以及直接期数足够、窗口从年初开始两种不加基期；三个版本各一例成功（其中两种差分由 `test_context_projection` 的参数化整体下移，精确比较父声明 id 集合）；不能差分的版本不差分；社融断期、GDP 断期；GDP 分母非正；公式未配置。
  - `test_worker_reviewed_context` 的 GDP 同批交付用例改为直接调 `derive` 判定，另加一例"社融原件损坏 → `incomplete_source_artifacts`"；只保留"交付后不重取"那一例投影层的集成断言。取数起点的适配器请求参数断言保留。
  - `test_full_run_retrieval` 删去 GDP 基期参数化用例，只留一例完整运行验证需求接入计划。
- **验证**（`PYTHONPATH=src`）：信用、社融、GDP、计划相关测试文件，加 `tests/domain`、Worker 执行、收尾冒烟与完整目录正例，共 699 例全过（36.4 分钟）。审查后只改了测试与文档，重跑 `test_worker_reviewed_context.py` 与模块测试 34 例全过。ruff、mypy 通过。
- **审查**（Codex 只读两轴）：生产路径逐分支对照 HEAD，未发现可观察行为变化。已按意见修：差分用例恢复精确父声明断言；补"前期分母非正"与"父声明原件损坏"；模块文档补上"`stale_inputs` 在缺口清单被当作失败"（票 27 处理）；`calculate` 补 docstring。
- **行为差异**：无。

