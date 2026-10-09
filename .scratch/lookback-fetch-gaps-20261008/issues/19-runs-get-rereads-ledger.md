Status: needs-triage
Category: enhancement
Type: task

# 19：`runs.get` 每次重读本运行的检索账本，随缺口与物理请求增长

## 现象（票 11 剖析发现，2026-10-09）

票 11 把只看状态的读取（`full_retrieval.py` 每个范围、列表页预读，Worker 的取消与状态检查）改走 `RunRepository.status` 后，`RunRepository.get` 仍在每次读取运行时调用 `RetrievalLedger.for_run`（`runs.py` 的 `_run_record`）。它会全读本运行的缺口（`retrieval_gap` ⋈ `retrieval_run_gap`），以及全部物理请求（`retrieval_physical_request` ⋈ `acquisition_request`），并逐条再查请求关联的缺口（`retrieval_request_gap`）。

剖析冒烟 `core_history` 用例（cProfile，票 11 期间测，当时 `get` 仍是每范围一次，共 774 次）：`get` 共 4.4 秒，其中 `for_run` 775 次、约 3.9 秒，即每次约 5 毫秒。每次读取的成本随本运行的缺口数和物理请求数线性增长。如果某条热路径按范围反复调用 `get`，总成本会随它们的平方增长。票 11 之后，这类热路径改读状态。经 `get` 读账本，每次运行约十几次（`advance`、`freeze_cutoffs` 等的返回值），审计 API、仪表盘与 CLI 每次请求再各读一次；另有直接调用 `for_run` 的地方（如 `full_retrieval.py` 计划收尾一带）。以上 4.4／3.9 秒是票 11 之前逐范围 `get` 时的数据，不代表票 11 之后的剩余耗时。

## 待分流时确认

- 是否值得优化：先在票 11 合入后的代码上复测剖析，确认账本读取在完整运行与受影响测试中还剩多少耗时。
- 若优化，**读取时点有顾虑**：
  - `RunRecord.retrieval_ledger` 是取得记录那一刻的快照。现有测试有"先取记录、后续再读其账本"的用法（如 `test_retrieval_p2_lenient.py` 的 `first.retrieval_ledger`）。
  - 账本内容在运行中会变化（新增请求、缺口状态）。
  - `for_run` 给每个请求判定原件是否过期（`raw_status`），用的是读取时的时钟（`utc_now()`）。
  - 因此改成按需读取会改变快照时点和过期判定。票 11 第二轮审查对检索尝试按需读取提出过同类阻断：记录取得之后、首次访问之前数据库被还原或运行被清理，读到的就是新内容。可选方向：不需要账本的调用方改走专用轻量读取；或给 `get` 加显式开关；或缩小 `for_run` 每次读取的量（如批量查请求关联的缺口，去掉逐条子查询）。

## 验收草案

- [ ] 复测给出账本读取在剖析中的实际占比，据此决定是否实施。
- [ ] 若实施：运行审计 API、仪表盘、CLI 输出不变；账本的快照时点与 `raw_status` 过期判定要么不变，要么经用户确认后再改。

## Comments
