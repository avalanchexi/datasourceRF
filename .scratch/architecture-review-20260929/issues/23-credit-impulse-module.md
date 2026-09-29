# 23: 信用脉冲模块（纯重构）

**What to build:** 把信用脉冲（`CONTEXT.md`：信用脉冲）的回看需求、输入解释、算术、失败状态与血缘集中到新模块 `src/pring_cycle/credit_impulse.py`；Worker 取数起点、完整运行规划、上下文投影都改走它。**三个现有公式版本原样收进模块，两套回看口径原样保留，可观察行为不变。**

**Blocked by:** 05、10（05 与本票同改信用父声明复核附近；10 把目标日／补算日的上下文调用与 `persist_derived` 所在路径移入单日汇总模块，本票在其后接入）

**勿并行：** 06、07、08、09、11、15、16、17、18（同改：Worker 编排与取数；上下文投影；完整运行规划；完整运行检索测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

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

- [ ] `worker.py`、`full_run_requirements.py`、`context_projection.py` 不再出现信用脉冲的期数、切片或版本集合判断；`_credit_impulse_proxy` 只剩调用模块、身份持久化、时效标签与拼行。
- [ ] 按 TDD 在模块接口上直接测：24／8、25／8、24／9、25／9 需求；社融与 GDP 两种差分；断期两种状态；GDP 同批交付放行、单季修订拒绝；分母非正；公式未配置；三个版本各至少一例成功计算（补上勘察 7.11 列出的空白）。
- [ ] 现有投影与完整运行用例不改断言、全部通过，作为行为不变的回归网（纯重构期间只增不删）。
- [ ] 迁移（本票最后一步）：`test_full_run_retrieval.py:904`、`:976` 的需求规则断言迁到模块接口，完整运行只留一例验证需求接入计划；`test_context_projection.py:1306` 的差分参数化整体下移；`test_worker_reviewed_context.py:197` 的数据版本规则迁到模块，保留一例交付关联集成；`:277` 的日期规则迁到模块，适配器请求参数断言保留；`tests/domain/test_macro_states.py:89`、`:101` 随函数迁移。删除被迁的断言，不叠加。投影层保留持久化与追溯、时效标签、宏观 support／gap；缺口测试留在缺口清单层。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 取数，另加跑完整目录正例，记录退出码与耗时。
- [ ] 代码审查（规格、标准两轴）无阻断。
