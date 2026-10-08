Status: done
Category: bug
Type: task

# 07：人民币中间价成员契约缺失

## 现象

AI 检索已取得人民币中间价 6.7351，但因 `dimension_contract_unavailable` 被阻，未入库。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [x] 为人民币中间价补维度成员契约，或明确其不入库并从计划中移除。（补契约；v0001 冻结目录保持无维度）

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：中间价**已入库**（AI 回执关联 1 条 6.7351、2026-09-30、validated，主会话已复核），问题在选值：缺必需成员契约被判 `dimension_contract_unavailable`（`search_evidence.py:236`、`ai_websearch.py:272`）。
- 修复：补 `USD/CNY`、`CNY per USD` 成员契约并验证选择结果，复用现有资讯规则（`news_rules.py:477`）。约 1–2 模块。
- 无需用户决定。独立实施。

### 2026-10-08 实施

- **改动**：`metric_contracts.REQUIRED_DIMENSION_MEMBERS` 补 `CN_USDCNY_CENTRAL_PARITY` 唯一成员 `{currency_pair: USD/CNY, quote_direction: CNY per USD}`，与官方解析器（`official_context._parse_usdcny_central_parity`）和现有资讯规则（`news_rules.py` `pbc_usdcny_central_parity`）写入的维度一致，选值不再落入 `dimension_contract_unavailable`。对 v0002、v0003 与登记目录生效；`metric-catalog-v0001` 登记时该指标无维度，`required_dimension_members` 对其仍返回 `None`，保持旧选值与 Worker 就绪语义（规格轴首轮阻断，已修）。`news_rules.rules_cover` 及资讯规则测试中"成员由解析器决定（中间价）"的注释改为只剩降准范围这一种情形。
- **替身**：`tests/integration/test_ai_websearch.py` 新增两例——"已入库却选不出"（AI 候选 6.7351 入库后选值完成、回执 `verified/complete_model_input`、运行 completed；改前红，复现真实运行现象：已入库但 `candidate_validation_unresolved`）；"报价方向相反"（"1人民币对美元0.1485美元"判 `rule_not_matched`，不入库、缺口不完成）。`tests/adapters/test_official_context.py` 中间价解析例补断言：v0002/v0003/登记目录的契约恰为解析器写出的维度，v0001 为 `None`。
- **测试**：受影响 15 个文件 401 passed（849 s，超 3 分钟目标，主要是 `test_full_run_retrieval.py`，未删测试）；两例冒烟 2 passed（46 s）。改动触及选值成员契约，Worker 上下文就绪校验（`worker.py` 约 1172 行）随之收紧，故照跑重型：`test_worker_registered_catalog.py` 2 passed（421 s）、`test_core_carry_forward.py` 2 passed（42 s），退出码均 0。`ruff check`、`ruff format --check` 通过；`mypy` 两个源文件无错，测试文件仅余改动前已有的 12 处既有错误（新增代码已消除同类写法）。
- **审查（Codex）**：标准轴阻断：无；采纳两条非阻断意见（替身按"期间＋维度键值"取值、契约断言补 v0002）。另一条非阻断——v0002/v0003 下 Worker 就绪只认正确方向成员——属预期的纠错，合法解析结果不受影响，不另改。规格轴首轮阻断：有（v0001 兼容性回归），修复后定向复审阻断：无。
- **说明**：本次未重跑真实运行；既有运行记录不会自动改写，6.7351 能否在下一轮真实运行被选中留待票 09 验收。

