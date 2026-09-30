# 16: 获取结果模块（纯重构）

**What to build:** 把"本批／截至某时点某指标的获取尝试怎样"（`CONTEXT.md`：获取结果）的读取与解释集中到新模块 `src/pring_cycle/acquisition_outcome.py`，P2 获取状态、ECB 失败补记、LPR 发布日历、缺口清单的获取失败归并与结构拒收都改走它。**只动读取端，可观察行为不变；不推断未记录的阶段。**

**Blocked by:** 无

**勿并行：** 01、02、04、05、06、07、08、10、11、15、23、24、25、26、27、28、29、30（同改：Worker 编排与取数；上下文投影；缺口清单与时效；证据仓库；完整运行检索测试文件；缺口展示与国债测试文件；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 4 的访谈记录（2026-09-29）；勘察见 [codex-survey-c4.md](../codex-survey-c4.md)、[codex-survey-c4b.md](../codex-survey-c4b.md)。 规格：[spec.md](../spec.md)「五、获取结果模块」。

## 现状（读取方）

- 目标日截止视图：`EvidenceRepository.latest_retrieval_attempt`（`evidence.py:884`，按指标、`fetched_at≤as_of`，可选 metadata 中期次／目标日／目录版本，精确时间＋哈希 id 倒序）。调用方：P2 获取状态装饰（`context_projection.py:304`–`:340`，把 metadata 逐项解包成 `latest_acquisition`）、LPR 发布日历（`release_calendar.py:198`／`:202`，未传目录版本）、ECB 失败补记（`worker.py:1698`，按指标＋目录版本判断同次失败是否已记）。
- 批次视图：`_acquisition_failures`（`freshness.py:825`，本次受理到下一次受理的时间区间、同目标日；按指标＋品种保留最后一条，再压成每指标一个原因；原因取 `reason→condition→error_type→outcome`）；结构拒收（`freshness.py:930`，`full_run_acquisition` 按运行 id 关联 `structure_check='rejected'` 的回执）。

## 已定决定

- **两个入口**：`AcquisitionOutcomes(database)`。
  - `latest(metric_id, *, as_of, definition_version=None, target_business_date=None, period=None) -> AttemptView | None`：目标日截止视图。`latest_retrieval_attempt` 保留签名、委托到这里。保留"可取到同目标日上一批次尝试"的现状（用户判定维持，如实展示最近一次获取）。
  - `for_batch(run_id) -> BatchAcquisition`：批次视图。`.failures()` 沿用 `_acquisition_failures` 现行口径（时间区间归属、指标＋品种最后一条、压成每指标一个原因）；`.structure_rejections()` 沿用 `freshness.py:930` 现行口径（含 `skipped` 不算拒收）。
- **`AttemptView` 为有类型字段**：outcome、渠道、记录时间、目录版本、condition、是否发出请求、拒收字段数、reason、error_type、stage、品种、回执 id、来源期次／时区／发布时间等 P2 现用字段。消费者不再直接读 `safe_metadata`。
- **消费者类别留在消费者**：缺口清单的 outcome→`fetch_failed`／`ingest_rejected` 映射、LPR 的"有本期即 current，否则看失败"状态机（用户判定维持）、P2 的 `no_attempt_for_target` 都留原处。
- **不收**：检索候选失败 `_failed_candidates`、事件追溯 `_backtracked`、完整检索计划、预算账本、运行检索流水（`run_retrieval_attempt`）、原件复核（票 05）、交易日历读取（票 02）。
- **保持现有差异**：两处"最新"排序不同、缺口清单与 LPR 不按目录版本过滤（见 19）；时间区间归属（见 19）；品种无日期、多品种压成一个原因（见 20）；已解决的拒收仍列入（见 21）。纯重构期间原样保留，写在模块文档里。
- **位置**：新建模块，传入数据库路径；不并入 `acquisition.py`（回执仓库，管写入与存储契约）或 `evidence.py`。

## 验收

- [x] `context_projection.py`、`release_calendar.py`、`worker.py`、`freshness.py` 不再直接查询 `retrieval_attempt` 或解包其 metadata；结构拒收查询移入模块。
- [x] 按 TDD 在模块接口上用少量尝试与回执记录覆盖：`latest` 的微秒截止（迁入 `test_full_run_retrieval.py:112`）、目标日过滤、目录版本过滤、ECB 同次失败去重；`for_batch().failures()` 的时间区间归属、同品种后续成功清除失败、跨品种不清除；`.structure_rejections()` 的 `skipped` 不算拒收。
- [x] 缺口清单原因映射改为直接调用 `gap_list(database, run_id, …)` 加预置记录测试，不跑完整 Worker。
- [x] 现有穿过完整运行与投影的用例不改断言、全部通过，作为行为不变的回归网。
- [x] 迁移（本票最后一步）：`test_full_run_retrieval.py:38` 起的 EIA 获取状态断言、`:217` 的 P2 `input_acquisition` 断言、`test_gap_source_repairs.py:347`／`:360` 的获取失败与入库拒收原因移到模块或 `gap_list` 接口，删除被迁的断言，不叠加。取数行为（缺 key 不发请求、API 失败走 HTML、品种分别请求）留在各来源直接刷新测试；`test_processing_batch.py` 与 `test_gap_list.py` 各保留一例完整运行验证批次关联与缺口清单输出。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（ADR-0025）；涉及 Worker 取数，另加跑完整目录正例，记录退出码与耗时。
- [x] 代码审查（规格、标准两轴）无阻断。

## Comments

**2026-09-30 实施记录**

- **模块** `src/pring_cycle/acquisition_outcome.py`：`AcquisitionOutcomes(database)`，两个入口：
  - `latest(metric_id, as_of=, definition_version=, target_business_date=, period=) -> AttemptView | None`：目标日截止视图。
  - `for_batch(run_id)`：批次视图，`.failures() -> dict[指标, AttemptView]`，`.structure_rejections() -> tuple[StructureRejection, ...]`。
  - `AttemptView` 保留原始 metadata，用属性按文本读出各字段（目录版本、期次、目标日、品种、condition、reason、error_type、stage、request_sent、rejected_fields、acquisition_ids、P2 来源期次与时区等）。`detail` 按原始值依次取 reason → condition → error_type → outcome，与旧口径一致。
  - `EvidenceRepository.latest_retrieval_attempt` 保留签名和返回类型，委托给模块。
- **消费者**：P2 获取状态装饰（`context_projection`）、LPR 发布日历、Worker 的 ECB 失败补记、缺口清单的获取失败与结构拒收，都改走模块。outcome 到缺口类别的映射留在 `freshness`：来源失败 → `fetch_failed`，校验失败 → `ingest_rejected`。模块外的生产代码不再直接查询 `retrieval_attempt` 或解包 metadata（`run_retrieval_attempt` 按票面不收）。
- **测试**：
  - 模块接口 9 例（`tests/integration/test_acquisition_outcome.py`）：`latest` 的微秒截止（迁入）、目标日与目录版本过滤、回执 id（ECB 去重所比较的内容，按目录版本区分）；批次时间区间归属、同品种后续成功清除失败（不带品种和具名品种各一）、跨品种不清除、null 原因退让给下一项；`skipped` 不算结构拒收；`gap_list` 直接测试（迁入 `test_gap_source_repairs` 两例的类别、原因、`no_web_fallback`、不出现 `no_searchable_source`）；投影的 P2 行显示目标日最新获取、美债利差显示输入获取状态（迁入）。
  - 迁移：`test_full_run_retrieval` 删去微秒截止用例，EIA 用例删去投影展示获取状态的三条断言，美债利差的 `input_acquisition` 断言迁出；`test_gap_source_repairs` 删去两例原因用例。取数行为（缺 key 不发请求、API 失败走 HTML、各渠道各自记录）仍留在 EIA 完整运行用例和直接刷新测试里。
- **验证**（`PYTHONPATH=src`）：涉及获取状态、缺口清单、发布日历、ECB、批次的测试文件，加收尾冒烟与完整目录正例，共 776 例全过（53.6 分钟，审查修复前）。修复后重跑直接相关文件 581 例全过（31.4 分钟）。ruff、mypy 通过。
- **审查**（Codex 只读两轴）已按意见修：
  - metadata 被提前转成字符串。旧的批次视图按原始 JSON 判断，null 或空值会退让给下一项，品种分组也用原始值；现在批次视图用原始值，目标日视图照旧按文本读。
  - `latest` 在排序前就解析所有候选的 metadata，一条旧的坏记录会让整个读取出错；改为只解析实际检查到的候选。
  - 模块文档补上"LPR 不按目录版本过滤"。
  - `request_sent` 的 docstring 更正；`INGEST_REJECTED_OUTCOMES` 改名为 `VALIDATION_FAILED_OUTCOMES`。
  - 补同品种清除、ECB 按目录版本区分回执、null 原因退让三例。
- **行为差异**：无新增。批次视图现在会先解析每条记录的 `fetched_at`，时间字段损坏的记录会报错（旧代码只做字符串比较）；写入端校验过时间字段，正常数据不会出现这种情况。

