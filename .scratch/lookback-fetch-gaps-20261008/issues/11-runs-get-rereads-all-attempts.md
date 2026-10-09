Status: done
Category: enhancement
Type: task

# 11：`runs.get` 每次重读全部检索尝试，随历史期放行呈平方增长

## 现象（第 10 张剖析发现，2026-10-09）

L01 放行历史期后，一次完整运行产生约 746 个历史期的检索级联、7628 条检索尝试记录。`runs.py:1027` 一带每次读取运行都重读全部尝试，耗时随记录数平方增长，剖析中约 19.5 秒，是受影响测试未能回到 L01 前耗时（423 秒→930 秒）的主要剩余原因之一。生产请求策略本身未改。

## 待分流时确认

- 是否改为按需或增量读取尝试记录；对运行审计页面与检查点恢复的影响。

## 验收草案

- [x] 读取运行不再随尝试记录数平方增长（加计数或耗时断言）。
- [x] 运行审计与恢复行为不变。

## Comments

### 2026-10-09 分流

按 goal-round2.md 预设决定实施。

### 2026-10-09 实施（暂停，needs-info，未提交）

**诊断**：反馈回路 `scratchpad/l11/loop.py`（一条运行写 N 条尝试、每写一条读一次运行）：N=500/1000/2000 时读取累计 1.30/3.11/9.38 秒，SQLite 交回的尝试行数为 N(N+1)/2，确认平方增长；去掉逐行组装 dict 后仍有约 2/3 的增量，热点就是 `RunRepository.get` → `_retrieval_attempts` 每次全读。

**当前实现（worktree 未提交，`src/pring_cycle/runs.py`）**：按需读取。`RunRecord.retrieval_attempts` 改为数据描述符字段 `_ReadOnFirstUse`；`get` 只用索引取 `MAX(sequence)` 作快照上界，首次访问时才按 `sequence<=上界` 读取并留在该记录上。审计 API／运行列表（`asdict`）、仪表盘、CLI 取到的仍是同样的 tuple；`replace`、`__eq__` 照常。只看状态的读取（`full_retrieval.py:131`、`:285`）不再读尝试。

**测试**（`tests/integration/test_run_orchestration.py` 新增 3 例）：

- `test_reading_a_run_after_each_attempt_reads_each_attempt_once`：200 条尝试、每条后读一次，SQLite 交回的尝试表行数 ≤600（旧实现 20,300）；对 HEAD 代码为红，改后为绿。
- 数据库还原后重读；中断＋resume 后审计文档（`asdict`）与新仓库实例一致、先取得的记录不含之后的尝试：两版均绿（对照用例）。
- 回路复测：N=500/1000/2000 读取累计 0.51/1.05/2.06 秒（线性）。
- 剖析冒烟 `core_history`（cProfile，flock）：用例 102→72 秒；`RunRepository.get` 774 次 21.1→4.4 秒；`_retrieval_attempts` 775 次 15.8 秒→2 次 0.03 秒。`get` 剩余耗时主要是 `RetrievalLedger.for_run`（约 3.9 秒／775 次）。
- 受影响 14 个文件 204 passed，1670 秒（`test_run_orchestration`、`test_dashboard_contract`、`test_projection_api`、`test_receipt_counts`、`test_retrieval_p2_lenient`、`test_retrieval_ledger`、`test_full_run_retrieval`、`test_worker_execution`、`test_ai_websearch`、`test_search_evidence`、`test_retention`、`test_media_page_values`、`test_retrieval_strict_path`、`test_unsearchable_gaps`）。`ruff check`、`ruff format --check`、`mypy src/pring_cycle` 通过。冒烟两例与重型两例待定案后再跑。

**审查**（Codex 两轴，两轮）：

- 第一轮（实例内增量缓存方案）：标准轴阻断"还原后的副本续写到与缓存末行完全相同的行时返回旧尝试"；规格轴阻断"tuple 累加仍是平方级引用复制"。均属实，已改为上述按需读取。
- 第二轮（按需读取）：两轴都阻断同一类问题——记录取得后、首次访问前，若数据库被还原或该运行被留存清理（`retention.prune_to_window`，Worker 成功收尾时触发）删除，旧记录读到的是新内容或空集，而旧实现在 `get` 时已全部读入。规格轴同时认定：账本 `RetrievalLedger.for_run` 留作另票不违背本票规格；描述符与 dataclass、mypy 的配合正确；计数断言能抓住回退。
- 按规程两轮仍阻断，停下上报。

**需要决定**（预设"按需／增量读取、审计与恢复输出不变"未覆盖的取舍）：

- A（推荐，即当前实现）：接受"记录取得后、首次访问前数据库被还原或该运行被清理"这一窄缝。生产中清理只删窗口外的旧运行，当前运行不受影响；审计 API 与仪表盘都是取得后立即序列化。在 `RunRecord` 注释里写明快照只保证"之后追加的尝试不可见"。
- B：`RunRecord` 保持立即全读（快照语义完全不变），另加只读状态的轻量接口（如 `RunRepository.status(run_id)`），把 `full_retrieval.py:131`、`:285` 与 Worker 的状态轮询改用它。需改 `full_retrieval.py` 两行（与票 16 的 `:936` 一带不重叠，但属并行规则要求先上报的模块）；其余仍走 `get` 的调用（`advance` 等，每运行十余次）各全读一次，属线性。
- 遗留（两方案都不处理）：`RetrievalLedger.for_run` 每次读取运行全读缺口与物理请求，剖析约 3.9 秒，建议另开票。

### 2026-10-09 用户决定

选方案 B：`RunRepository.get` 保持立即全读，快照语义与旧代码完全一致；另加只读状态的轻量接口，`full_retrieval.py` 两处状态检查与 Worker 的状态轮询改用它（批准改 `full_retrieval.py` 这两处）。账本每次全读另开票 19（needs-triage），随本票提交。

### 2026-10-09 实施（方案 B）

**改动**：

- `src/pring_cycle/runs.py`：新增 `RunRepository.status(run_id)`，只查 `parent_run.status`，运行不存在时与 `get` 一样抛 `LookupError("run_not_found")`。`get`、`_run_record`、`_retrieval_attempts` 一行未改。
- `src/pring_cycle/full_retrieval.py`：逐范围检查（原 `:132`）与列表翻页检查（原 `:286`）改用 `status`。
- `src/pring_cycle/worker.py`：失败或中断收尾的两处取消检查、检索后的状态检查，以及报告生成的 `cancel_requested`（`cli_process` 等待子进程时会反复轮询）改用 `status`。
- 测试：新增 `tests/fixtures/attempt_reads.py`，经所有连接统计 SQLite 交回的 `run_retrieval_attempt` 行数。`test_full_run_retrieval.py::test_full_run_shares_hard_search_budget_across_periods` 断言完整检索读回的尝试行数不超过尝试条数（旧实现约 370 万行，对应 7,878 条尝试）。`test_run_orchestration.py` 新增 3 例：每写一条尝试轮询一次状态，读取尝试行数为 0，`get` 仍恰好全读 200 行；另有两个对照用例，分别覆盖数据库还原后重读、中断与 resume 后的审计文档一致和先取记录的快照。

**修复前后耗时**：

- 反馈回路 `scratchpad/l11/loop_b.py`（每写一条尝试轮询一次状态）：`get(...).status` 在 N=500/1000/2000 时累计 0.82/2.55/7.88 秒，呈平方增长；`status` 为 0.22/0.60/1.08 秒，呈线性。
- 剖析冒烟 `core_history`（cProfile，flock，修复前取 main f322e25 源码）：用例 68→50 秒；`RunRepository.get` 调用 774→26 次，耗时 17.4→0.96 秒；`_retrieval_attempts` 12.7→0.63 秒；`RetrievalLedger.for_run` 777 次 3.75 秒→29 次 0.33 秒；`status` 748 次共 0.37 秒。
- 账本读取在热路径上随之消失，票 19 待分流时复测确认剩余占比。

**验证**：

- 受影响 17 个文件 315 passed，1920 秒（日志 `scratchpad/l11/affected-b2.log`）。文件为前一轮的 14 个，加上与票 16 相交的 `test_lookback_declaration.py`、`test_credit_impulse.py` 和 `test_official_listing_pages.py`。
- 两例冒烟 2 passed，85 秒。重型 `test_worker_registered_catalog.py`、`test_core_carry_forward.py` 4 passed，486 秒。
- `ruff check`、`ruff format --check`（改动文件）通过；`mypy src/pring_cycle` 无问题。测试文件的 34 个 mypy 错误在 main 上原样存在，改动行未新增。

**审查**：方案 B 由 Codex 定向复审，标准轴与规格轴均为"阻断：无"（`scratchpad/l11/review-b.out`）。处理非阻断意见如下：

- 已采纳：票 19 的措辞（`for_run` 还有直接调用点；过期判定是 `raw_status`，不是 `expired` 字段）已更正。
- 未采纳：计数断言没有覆盖 Worker 调用点退回 `get(...).status`。不采纳的理由是，Worker 这几处每运行只走一次或只在报告生成时轮询，不随尝试数逐条触发；即使退回，成本也只是线性增长，不会重现本票的平方增长。热路径 `full_retrieval.py` 已由计数断言把守。
