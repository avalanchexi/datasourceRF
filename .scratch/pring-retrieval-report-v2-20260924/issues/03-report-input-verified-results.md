# 03: 精简报告输入：只交已验证结果

**What to build:** AI 报告只接收已验证结果（正式阶段或空阶段原因、三核心状态与变化原因、宏观与库存结论、核心沿用、缺口概况；每项附结果值、来源、是否有异常），不再附证据链、不再逐段引用证据；生成后只校验结论未被改写与结构合规（ADR-0027）。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言（假 CLI 可执行文件）：报告输入不含证据编号、逐条证据行与观测序列，体积显著小于首次真实运行的 14.6 万字节
- [x] AI 输出改写正式阶段、核心状态或宏观/库存结论时被拒收并降级
- [x] 段落结构不再含证据与治理引用字段，禁用词检查保留
- [x] 两路失败时确定性报告照常生成且不含证据引用
- [x] 新快照记录新的输入与提示版本，旧快照照常可读
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。`reports.EvidenceBundle` 改为 `ReportInput`（仍存于 `evidence_bundle` 表、沿用 `bundle_id`），由 `report_input_from_projection` 构造：`conclusions`（政策、信用、过热、价格、库存象限）、`results`（正式阶段及原因与变化、三核心状态与来源及沿用、各宏观/库存结论的来源名称与异常 `gap:`/`lagging:`/`conflict`、核心沿用、缺口概况：分类计数加 P0/P1 指标）。完整缺口清单只留给阅读器，不进提示。版本升为 `report-schema-v0004`/`report-prompt-v0004`。
- AI 输出结构改为 `bundle_id/current_stage/report_cutoff/core_states/conclusions/sections/proxy_used`，段落只有 `title/explanation`；`core_states` 与 `conclusions` 以 schema `const` 约束且后置校验逐项比对，改写即 `conclusion_mutation_rejected`（阶段仍为 `stage_mutation_rejected`），禁用词与单段检查保留，引用子集校验取消。确定性骨架去掉 support/counterevidence/governance_gaps/evidence_references，改含 `conclusions` 与 `verified_results`。阅读器对旧快照照常显示其证据与治理引用；页面“证据包”字样改为“报告输入”。
- 真实样本：保存首次真实运行投影为 `tests/fixtures/report_input/projection-20260923.json`（stage_history 只留本投影事件），据此生成的提示输入 4,642 字节（原证据包 139,770 字节）。新增 `tests/integration/test_report_input.py`（完整运行＋PATH 上的假 codex/claude，断言提示无 64 位哈希、无证据字段、体积 <1/10）；`test_report_boundary.py`、`test_cli_protocol.py` 按新结构改写，并加结论改写拒收、旧快照可读两例。受影响 51 例＋报告 45 例全过。
