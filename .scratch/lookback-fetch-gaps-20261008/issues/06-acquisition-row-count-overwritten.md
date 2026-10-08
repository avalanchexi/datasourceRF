Status: done
Category: bug
Type: task

# 06：取数回执的行数被归一化行数覆盖

## 现象

`acquisition_request.row_count` 记录的是归一化后的行数，覆盖了来源实际返回的行数，复核"来源返回了多少、入库了多少"时对不上。

- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md) 候选票。

## 验收草案

- [x] 回执分别保留来源返回行数与归一化入库行数（`source_record_count`／`normalized_scalar_count`／`ingested_claim_count`，见下方实施记录）。

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：不是"先存原始行数再被覆盖"，而是口径混淆——接收阶段只存字节和哈希，校验阶段才从归一化对象算 `row_count`（`acquisition.py:433`、`:361`），计数器也不识别 `accepted_scalars`/`scalars`（`batches.py:75`）。实测 CPI 原始 20 行记为 60、PPI 20 行记为 180，GDP 原始 7 行、28 个接受标量却记为 1。
- 修复：分别记录来源记录数、规范化标量数、实际入库结果；HTML 原件不冒充一行。约 3–5 模块加数据库迁移。
- 无需用户决定。建议最先实施，便于后续验收读懂三个数量。

### 2026-10-08 实施

- **改了什么**：回执 `acquisition_request` 新增三列（迁移 `0032_receipt_counts`，沿用共享助手 `add_receipt_columns`，0031 改调同名助手）：`source_record_count`（来源记录数：TuShare 在接收原件时、解析前按 `data.items` 计，解析拒收也保留；ECB／财政部 CSV 取 `total_source_rows`；EIA、中证 JSON 解析器逐行全收或整体拒收，取解析长度；HTML／TXT 原件为 NULL，不冒充一行）、`normalized_scalar_count`（各适配器显式声明；TuShare 延迟校验按关联到该回执的标量计，GDP 包装计 `accepted_scalars` 长度；日历、列表、日程、检索发现等不含指标值的为 NULL）、`ingested_claim_count`（入库结果写入时该回执已关联的来源声明数，与 `ingest_result` 一次性同写，触发器要求首次写入同时带计数）。`row_count` 停写，旧值保留随留存期过期；`batches.row_count()` 删除。新增 `AcquisitionRepository.ingesting()`，补上原先不记入库结果的核心历史、中证核心、搜索宽松页、媒体页四条路径（日期晚于截止的拒收记 rejected＋0）。`defer_validation` 与计数回调同用直接拒绝。运行审计读模型 `read_full_retrieval_plan`（`/api/v1/runs/{id}/audit`）返回三数与入库结果；仓库内无页面读取 `row_count`。
- **测试**：新增 `tests/integration/test_receipt_counts.py` 12 例（TuShare 多字段 2 行→2/16/16、GDP 包装 2 行→2/8/8、入库拒收→关联 0、解析拒收仍记来源行数、HTML→NULL、已持有成员过滤→入库少于标量、EIA JSON、运行审计、跨年核心中途失败不误记、延迟校验拒绝计数回调×2、0031→0032 迁移含重复执行／failed 收据／不完整首写）；改 `test_processing_batch.py`（断言三数）、`test_media_page_values.py`（日期拒收记入库结果）、`test_database_lifetime.py`（schema head）。受影响测试 76 个文件 1265 passed，2595.8s（共享 `capture` 改动按 testing.md 扩大范围，超出 3 分钟目标）；两例冒烟 2 passed 39.4s；重型 `test_worker_registered_catalog.py` 2 passed 380s、`test_core_carry_forward.py` 2 passed 36s。ruff check／format 通过；mypy 对改动文件无新错误（18 条均在未改动的 `test_core_history_refresh.py`、`test_context_acquisition_receipts.py`，既有）。
- **审查**：Codex 标准轴、规格轴第一轮均阻断（入库结果在核心／中证／搜索路径缺失、触发器允许不完整首写、延迟校验丢弃计数），已修；第二轮阻断为对上一轮修复的缺陷（跨年核心错误归因、搜索日期拒收绕过记录），已修；定向复审"阻断：无"。
- **未采纳／已知残余**：AI WebSearch 交换与 TuShare 新闻拉取回执不记入库结果（候选与新闻原件可被多次取值，一次性计数会误导；入库情况见候选校验记录）；Cboe CSV 与中国货币网 JSON 快照来源记录数为 NULL（解析器先按日期过滤，不能用选中行冒充来源返回数）；EIA／中证 JSON 被解析拒收时来源记录数为 NULL（仅 TuShare 在解析前计）；`ingested_claim_count` 是关联声明数，含已存在的同身份声明、跨回执共享的声明各计一次，不是新增行数，不可跨回执求和；测试以 PMI 代表多字段 TuShare 行（与 CPI／PPI 同形），未逐一建 CPI／PPI 替身；迁移夹具未含升级前已有入库结果的旧收据（守卫条件对其与本测已有入库结果的情形相同）。
