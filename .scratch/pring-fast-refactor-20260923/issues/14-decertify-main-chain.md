# 14: 去认证主链

**What to build:** 注册来源（TuShare、已注册官方直连）的值不需来源认证包、不需逐值发布证据即可进入投影；公开可用时间只用 13 号的 min 规则，取消 public_as_of / system_as_of 双时点。从来源契约审查、证据、检索证据、完整运行要求等主链模块中逐处剥离认证标签与逐值发布证据，保留接口/结构校验。见 ADR-0021、0022。

**Blocked by:** 13

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 主链不再读取数据源认证状态或逐值发布证据；无认证记录的注册来源值正常进入投影
- [x] 双 as-of 字段不再被写入或查询；公开可用时间来自 min 规则
- [x] 两例快速冒烟按新语义改写（补报告断言、去 `certification_status`）并通过
- [x] 修改到的部分耦合测试同票改写，不留依赖认证前置的断言
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 完成：主链（投影、Worker、输入选择、日历要求、仓单、三核心适配器与核心声明校验、证据写入与注册合同重校）不再以认证标签取舍；投影行去掉认证字段。解析器未给公开时间的声明按 min 规则写入 `inferred_public_at`（迁移 0024），所有选取经视图 `effective_source_claim` 读有效公开时间；解析器原值不被覆盖，原有注册合同重校照旧比对。`SourceClaimInput` 改为仅关键字，认证字段默认 `not_applicable`。两例冒烟已按新语义改写（补报告断言、去认证字段），新增 `test_decertified_main_chain.py` 3 passed。
- `AsOfMode` 接口仍保留给 15/16 将删的模块与既有夹具使用；主链只按运行截止时点与有效公开时间取值。
- 未勾选的“完整目录正例与三核心反例”：两者当前都依赖隔离生命周期材料（经候选准入/回放构建，冷建约 30 分钟），将分别在 27、21 改写后运行并记录，此处未跑。
- 2026-09-23 回归修复（随 15/16 同一提交）：有效公开时间视图让各来源的原件复核（TuShare 宏观、银行间、官方页面、LPR、ECB、美债、仓单、广度、商品篮子）拿推断时间去比解析器时间，复核全部失败，模型输入不完整；摄取去重读取最新声明时同样错比，导致重复摄取产生新声明。修复：视图另出 `inferred_public_at`，`ClaimView.parsed_public_available_at` 给出解析器原值，复核点改用它；最新声明查询改读原表。另：同月库存公式的对齐期 PPI 不再单独判时效（只要求最新 PPI 为 current）；Q1 产能 ytd 别名改为按原件的结构校验，去掉认证包与审查映射链；迁移 0020/0021 在 `model_replay` 已删时跳过。子代理根因分析与对照实验见会话记录（scratchpad `rerun.log` / `noinfer.log`）。
- 同一提交按新语义删改耦合测试：公开时间“保持未知”、修订不回填、认证前隐去、PUBLIC 查询为空、双时点修订、Q1 映射认证链、双截止点（`test_system_target_inputs.py` 整删）等用例删除；其余断言改为比对解析器原值或新状态。

- 2026-09-24 回填：完整目录正例与三核心反例已包含在终点全套（票 28）中一并运行。`check.py full` 退出码 0，1211 例通过，用时 4051.5 秒；其中完整目录正例 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 用时 125.6 秒，三核心反例（`test_core_carry_forward.py`、`test_core_official_fill.py`、`test_structural_rejection.py`）均通过。
