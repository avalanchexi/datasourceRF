# 17: 获取尝试的归属契约

**What to build:** 每条新写入的获取尝试显式记录所属运行 id、目录版本、品种与日期（适用时）和关联回执，不再依赖"带回执才补入运行"；Worker 不再为整个家族追加覆盖逐项细节的汇总记录。

**Blocked by:** 16

**勿并行：** 02、05、08、10、15、23、24、25、29、30（同改：Worker 编排与取数；证据仓库；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 4 差异 16、19、20（用户判定为遗漏，2026-09-29），并为 19、20 两票提供前提。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状

- `record_retrieval_attempt`（`evidence.py:1296`）只在收到 `acquisition_ids` 且都关联到同一运行时补入 `run_id／target_business_date`；缺凭据（`worker.py:1573`、`:1761`）、Worker 汇总记录（`worker.py:1663`）、核心历史（`core_history.py:189`）、LPR 失败（`official_lpr.py:430`）没有可靠归属。
- TuShare 上下文底层成功记录不带品种（`tushare_context.py:1155`），Worker 失败包装记录带（`worker.py:1924`）；单日补缺走前者（`targeted_context.py:159`），清不掉直接刷新留下的品种失败（差异 16）。
- EIA HTML 底层已逐指标写 `verified_candidate／missing_values`（`eia_html.py:458`），Worker 又按整个循环有无异常给两指标统一写成功或失败（`worker.py:1609`–`:1634`），覆盖逐项结果（差异 19）。
- 郑商所尝试有 `business_date＋symbol`，但没有目录版本（`czce_warrants.py:439`）（差异 20）。

## 已定决定

- 归属字段由模块（票 16）定义，写入方填写；缺凭据等未发请求的记录允许"有运行、无回执"。
- Worker 只记自己的决定（缺凭据、未配置），获取细节由实际执行的适配器记录；家族汇总由获取结果模块读取时生成，不再落库。
- 旧记录不迁移：`retrieval_attempt` 随留存期删除（`retention.py:167`），过渡期读取端对无归属旧记录退回时间区间。

## 验收

- [x] 所有获取尝试写入点带运行 id 与目录版本；仓单带品种与日期；TuShare 成功与失败记录的品种字段一致。
- [x] EIA HTML 不再被 Worker 二次概括；某一项失败不改写另一项的结果。
- [x] 按 TDD：缺凭据记录可按运行 id 取到；TuShare 单日补缺成功能与同品种失败对上；EIA HTML 一项成功、一项失败时两项结果各自保留。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [x] 代码审查无阻断。

## Comments

- **勘察**：Codex 只读，结果在 `t17-survey`。`retrieval_attempt` 没有批次列，写入 API 只凭"回执都属同一运行"推断归属。批次视图全按时间区间归属。
- **实现**：
  - **写入归属**：`record_retrieval_attempt` 在加工批次（即运行，ADR-0022）内时，以批次填 `run_id` 与该运行的目标日（`acquisition.batch_analysis_context`），有无回执都一样；不在批次内时，沿用"回执都属同一运行"的推断。Worker 的 `_execute_run` 整体处于批次内，所以运行中的所有写入都带运行 id。
  - **批次读取**：`for_batch().failures()` 中，记录了 `run_id` 的只归该运行，可以越过受理时间边界；别的运行不会按时间把它捞走。没有 `run_id` 的旧记录仍按时间区间归属，随留存期删除。
  - **TuShare**：
    - 适配器的成功记录按（指标、仓单品种）分条，带 `symbol`、`period_start/period_end`、`rejected_fields`；有被拒字段时直接记 `partial_validation`。
    - Worker 删掉家族成功汇总，只保留自己的判断：缺凭据、增量家族无新增、家族缺指标，以及失败兜底。
    - Worker 的仓单失败记录补上请求起止日。
  - **EIA**：
    - 两个网页逐指标执行，回执也按单指标登记。原来两页共用 `acquisition_metrics(EIA_METRICS)`，一页被结构拒收时两个指标都会进拒收清单。
    - 单页失败不会中断另一页；Worker 不再写网页渠道的汇总。
    - API 成功由适配器记录，Worker 不再重复写；API 失败适配器不记，仍由 Worker 记。
  - **目录版本与回执**：核心历史成功、LPR 失败、郑商所三处补上目录版本；核心历史成功与 LPR 失败补上回执 id。
- **留给票 18（已定决定："适配器在步骤边界翻译，Worker 的异常翻译只作兜底"）**：TuShare 的来源、解析、入库失败与 EIA API 失败仍由 Worker 兜底记录，不带回执；定向补缺失败不写获取尝试。这些迁入适配器属于分类契约。
- **例外（只记录）**：批次外的独立命令行导入本来就没有运行，写入的尝试只有回执能推断出唯一运行时才带运行 id。涉及 `eia-html-refresh`、`treasury-csv-refresh`、`ecb-reference-*`、`lpr-refresh`、`core-history-refresh`。直接调用适配器的测试同理。
- **可观察变化**：
  - 批次内的适配器记录现在带目标日，P2 获取状态能按目标日看到适配器自己的记录。例如 EIA 现在显示发布日、下次发布日，网页 `TypeError` 按适配器记为 `validation_failed`。
  - Worker 汇总独有的 `family`、`publication_precision` 字段不再出现，现有读取方都不读它们。
  - 同一次交付的各指标／品种共用整次调用的被拒字段数，与原先相同。
- **验证**（`PYTHONPATH=src`）：完整运行集合，加上调查列出的各来源适配器、取数、缺口与留存测试文件（78 个文件），共 1019 例全过（48.1 分钟），其中包括两例冒烟；完整目录正例 `test_worker_registered_catalog.py` 通过，耗时 118 秒。ruff、mypy 通过。
- **审查**（Codex 只读，两轮）：
  - 第一轮阻断项中，EIA 回执跨指标归属已修；TuShare 日期补了起止；注释已改。
  - 失败迁入适配器按票 18 已定决定延后，批次外命令行入口记为例外。
  - 复审无阻断。
- **测试**（先红后绿）：
  - `test_acquisition_outcome.py::test_an_attempt_recorded_in_a_batch_is_that_batch_s_without_a_receipt`：场景是在下一运行受理之后，为前一运行记录缺凭据；该记录只归前一运行，没有回执。
  - `test_warrant_symbol_isolation.py::test_a_gap_day_refetch_clears_the_symbol_the_direct_refresh_failed`：直接刷新留下的 CU 失败，被单日补缺成功清掉，只剩郑商所不可达的品种。
  - `test_worker_eia_html_fallback.py::test_each_history_page_keeps_its_own_outcome`，参数化覆盖任一页失败：另一页照常获取，两页结果各自保留，Worker 回调只剩 API 渠道。
  - `test_a_page_refused_by_its_structure_check_names_its_metric_alone`：一页被结构拒收，只列它自己的指标。
  - 旧的两例 EIA 用例改读持久记录。
