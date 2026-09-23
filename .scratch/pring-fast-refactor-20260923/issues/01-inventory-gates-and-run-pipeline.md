Type: research
Status: resolved
Blocked by: none

# 盘点现有门禁与完整运行流程

## Question

从公开任务命令到投影发布、报告生成，现有手动完整运行和数据准备经过哪些步骤与门禁？逐项列出：门禁名称、所在模块与函数（file:line）、判据、阻断后果、实测或已记录的耗时，以及它对应新三道门中的哪一道（①120 日明细完整 ②时效正确 ③经正确接口/结构校验），还是应当删除（来源认证包、逐值发布证据、预检完整性、候选回放验收、切换验收等）。同时列出哪些模块只为被删门禁服务，删除后可整体移除。

复用已有记录（continuation-status、slow-test-inventory、implementation-context 等），不改代码、不跑重型测试。

## Answer

详见 [研究：门禁与完整运行流程](../research/01-gates-and-run-pipeline.md)（读码推断，关键行号已回核，未实测）。
- 要删的是“认证→候选准入→校准/回放→激活验收→系统验收/演练→切换”这条旁路链，它与 `run-submit`→Worker→投影→报告的主链基本分开。
- 可整文件删除：`material_preflight`、`candidate_admission`、`model_evaluation`、`acceptance`、`cutover`；迁出少量函数后可删：`source_certification`、`rehearsals`。
- 认证标签和逐值发布证据嵌在 `source_contract_review`、`evidence`、`search_evidence`、`full_run_requirements` 等主链模块里，要逐处去掉，同时保留接口/结构校验（③）。
- 现有完整性检查（按统计期相交）和时效检查（固定年龄阈值）不等于新门①②，都要新写；TuShare 非 P2 解析异常会导致整次运行 action_required（`worker.py:1652–1667`），要改成可见缺口。


## Comments

- 2026-09-23 调度方回核订正：`candidate_admission.py:46-60` 定义了 `_MARGIN_SCOPE_MIGRATION` 与 `_CNY030_OPTIONAL_MIGRATION`，生效 59 项目录正是由内置 v0002 加这组迁移组装出来的（见研究 02）。所以 `candidate_admission` **不能整文件删除**：要先把目录迁移定义迁到目录模块（如 `catalog.py`），剩下的准入逻辑才能删。可整删的模块改为 4 个：`material_preflight`、`model_evaluation`、`acceptance`、`cutover`。
