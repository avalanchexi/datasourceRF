# #16 回放上下文输出：点表与按日引用（实施记录，2026-09-15起）

设计见 [design-16-context-output-references.md](design-16-context-output-references.md)。用户指示"继续"后按推荐方案实施。票17仍由前台会话 configure-claude-model 负责，已约定文件边界：本项只改 `model_outputs.py`、`model_evaluation.py`、`models.py`（`replay_matches_current_evidence`）以及上下文输出相关测试，不改票17的6个文件，不运行复制隔离材料或生成大文档的测试（C盘剩约6.5GB，随时可能 `wsl --shutdown`）。

## 行为

- 新写入的文档是 `context-replay-output-v0002`：`source_points` 按首次引用顺序保存去重后的点，`source_point_hashes[i] = sha256(model_output_json(points[i]))`；每天每侧的 `source_inputs[metric]` 是点序号列表。
- 生成：`ContextSourcePoints.references` 在 `_evaluate_context_replay` 中逐日把快照换成序号，当天快照对象不保留。
- 校验：`validate_context_output` 同时接受 v0001（内联，原逻辑）和 v0002，v0002 另做以下检查：
  - 点表与哈希列表长度一致；哈希无重复；逐点重算的哈希一致；
  - 引用必须是真整数（bool 不算）且不越界；
  - 所有点都被引用。
  - 以上任一不满足，抛出 `context_output_references_invalid`。
  - 解析后的当日快照继续走原有的全部输入检查。
- `context_day_source_inputs`：按日解析引用，v0001 原样返回。`compact_context_output` / `expand_context_output`：两种形式互转，用于小文档、测试和旧文档比较。
- `replay_matches_current_evidence`：已存的 v0001 文档先按其 v0002 形式计算哈希，再与重算结果比较。旧收据不改写。

## TDD 与验证

- RED：新测试 `tests/models/test_context_output_references.py` 在收集阶段即因接口缺失失败。
- GREEN：同一文件 8 通过/12.2秒。覆盖三日 LPR 回放去重（点数小于引用数、每个点都被引用）、保存读回相等、按日解析出 3.0/2.9/2.9、展开与压缩互为逆操作、5 种引用损坏、解析后快照损坏仍由输入检查拒绝、v0001 文档可保存和读取。
- 变异检查（在临时 src 副本上）：去掉孤立点检查、去掉哈希重算、把 `type(index) is not int` 放宽为 `isinstance`，分别被 `orphan_point`、`changed_point`、`boolean_index` 捕获。
- 既有回放测试 `tests/models/test_candidate_replay.py`：改前 15 失败/60 通过，失败的都是直接读写内联点对象的用例。改为"展开→修改→压缩"或 `context_day_source_inputs` 后，75 通过/23.0秒。
- `tests/models/test_candidate_admission.py` 中期货仓单快照的两处读取改用解析函数，该用例 2 通过。
- ruff check/format 通过；`mypy src`（MYPYPATH=src）通过。
- 模型目录回归（`test_candidate_admission.py`、`test_model_evaluation_regressions.py`、`test_model_lifecycle.py`、`test_model_replay_rollback.py`、`test_registered_commodity.py`）：708通过/6失败，1769秒。6个失败都是 `test_registered_treasury_*` 系统上下文采用断言（`claim_ids <= set(adopted)`，采用集合为空），不涉及回放输出。在 HEAD 源码与 HEAD 测试的导出副本上单独运行 `test_registered_treasury_context_rechecks_hash_consistent_receipts[none]`，同样失败，属于既有问题，与 #16 无关（推测与当前日期超出 2026-09-04 美债数据的新鲜度窗口有关，未深入定位）。
- 集成与 e2e 中调用回放的文件（`tests/e2e/test_v1_cli.py`、`test_candidate_duration.py`、`test_full_run_retrieval.py`、`test_rehearsal_cutover.py`、`test_retrieval_ledger.py`、`test_search_evidence.py`、`test_source_contract_quarantine.py`）：118通过/1466.6秒。
- 以上运行都在工作区进行（PYTHONPATH=src），工作区同时含票17未提交的改动；提交前另在 HEAD 加 #16 文件的干净导出副本上复核。
- 待完成：票19材料上的容量证据（会触发材料重建，需要先确认C盘空间，暂缓）。

## 两轴审查（2026-09-15）及处理

**Standards**（无硬性违规）
- 写入路径仍接受 v0001，会让大文档重新入库：`validate_context_output` 新增 `accept_inline_v0001`，默认 False。只有 `replay_details` 读取时传 True，`record_replay` 拒绝 v0001（`context_output_schema_invalid`）。
- 哈希列表含不可哈希元素时会抛 `TypeError`：先检查每个哈希都是 `str`，否则抛 `context_output_references_invalid`。
- 解析出的点是共享对象：在 `context_day_source_inputs` 的文档里注明只读。`expand_context_output` 改为整份 JSON 往返生成独立副本，并注明只用于小文档和测试夹具（生产代码不调用）。
- `models.py` 注释改为准确描述：v0002 形式小于已持有的内联文档。
- 行映射重复：抽出 `_with_day_source_inputs`。`referenced` 更名为 `uses_point_table`。`context_output_document` 的文档字符串去掉了未强制执行的承诺。
- 保留：schema 分支集中在 `model_outputs.py` 的读取、转换和校验函数中。常量沿用 `CONTEXT_OUTPUT_SCHEMA` 表示当前写入版本，旧版加后缀 `_V0001`，与设计文档中的 `_V1`/`_V2` 命名有偏差，功能相同。

**Spec**
- 补上独立期望：测试中直接对每天每侧调用 `_context_source_snapshot`，与 `context_day_source_inputs` 的解析结果逐项比较。
- 旧文档兼容改为不依赖 `expand`：用直接快照手工构造 v0001 收据，模拟旧版本写入（仅在该测试中放开写入校验），再断言：
  - 读取相等；
  - 按日解析原样返回；
  - `compact_context_output(legacy)` 等于当前版本的文档；
  - `replay_matches_current_evidence` 为 True；
  - 当前版本写入 v0001 被拒绝。
- 新增引用损坏用例：点表缺失、长度不一致、哈希不可哈希。
- 保留偏差：`expand_context_output` 作为测试辅助公开（设计写的是"不提供整份展开"）；生产路径只按日解析。
- 切片 4 容量证据仍标为暂缓，不声称完成。

**修复后验证**
- 工作区：`test_context_output_references.py` 11 通过。
- 变异检查：旧文档比较改回直接比保存的哈希，`replay_matches_current_evidence` 断言失败；`accept_inline_v0001` 默认值改为 True，写入拒绝断言失败。
- 干净导出副本（HEAD 加 #16 的 6 个文件，不含票17改动）：ruff 通过；`mypy src`（94 个文件）通过；`test_context_output_references.py`、`test_candidate_replay.py` 与仓单快照用例共 88 通过/37.1 秒。
- 干净副本补跑：`test_model_replay_rollback.py`、`test_model_lifecycle.py`、`test_model_evaluation_regressions.py`、`tests/e2e/test_v1_cli.py` 共 54 通过/17.2秒。
