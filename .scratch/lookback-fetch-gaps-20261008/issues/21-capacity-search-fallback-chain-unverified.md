Status: done
Category: enhancement
Type: task

# 21：产能利用率检索补救经 `/zwfwck/sjfb/` 的完整链路没有真实或端到端证据

## 现象（票 17 验收发现，2026-10-09）

票 13 修了两处：一是列表按"规模以上"标题变体选稿；二是统计局 `/zwfwck/sjfb/` 路径登记进检索白名单与正文入口。第二处只有组件级离线测试，票面写明"全链路留票 17 真实运行核验"。实际测试覆盖到：`test_official_context.py` 的正文入口三例、`test_retrieval_registry.py` 的白名单一例；v0001 目录没有产能利用率，所以没有新增 Tavily／AI 全链路用例。

run-8574024f816500ec1a39 中，产能利用率 2026-Q1、2025-Q2 都由统计局列表选稿取到（`/sj/zxfbhjd/…`），没有走到检索补救：

- 运行期间请求参数含 `/zwfwck/sjfb/` 的回执为 0；
- 唯一一次 Tavily 检索是 LPR 2026-02，AI WebSearch 全部 `not_attempted`。

所以，"Tavily／AI 找到 `/zwfwck/sjfb/` 地址 → 白名单放行 → 正文入口按期次校验 → 入库 → 缺口补齐"这条链路，目前既没有真实运行证据，也没有端到端离线用例。列表选稿正常时，真实运行不会走到这条链路，无法靠再跑一次来核验。

## 建议（待分流）

用完整运行级的离线替身补一个端到端用例：统计局列表不含目标期，Tavily（或 AI）返回票 13 已登记的真实原件地址 `/zwfwck/sjfb/202604/t20260416_1963322.html`（夹具 `d038b999…`），断言该期由检索补救入库，缺口为 complete；同一路径的错期页面被拒。

## 验收草案

- [x] 端到端离线用例：列表缺稿时，产能利用率 2026-Q1 经 Tavily 候选 `/zwfwck/sjfb/` 地址补齐，入库值为 73.6／-0.5。
- [x] 同一路径下的错期页面按期次校验被拒。

## Comments

### 2026-10-09 分流

用户决定本轮（第三轮）实施，**只补离线端到端测试，不改生产代码**。若发现必须改生产代码才能走通链路，先停下回报主 agent（那就是缺陷，需要另行分流）。见 [goal-round3.md](../goal-round3.md)。

### 2026-10-09 实施

**改动**（只加测试，未改生产代码）
- 新增 `tests/integration/test_capacity_search_rescue.py`：生效模型（`effective_model_manifest()`）一次手动完整运行（`process_pending_run`），目标日 2026-05-29（2026-Q1 为最新已发布季度，计划同时回看 2025-Q1～Q4）。模块级夹具一次运行、两个用例读取结果。
  - 统计局列表替身：`/sj/zxfbhjd/` 单页（复用 `tests/adapters/test_official_listing_scan.py` 的 `nbs_page`／`nbs_filler`），条目为 5-19、4-16、3-16 的其他发布，已越过 2026-03-31 却不含产能利用率发布稿；其余官方页面一律 `OSError`。
  - Tavily 替身：凡查询含"产能利用率"均返回票 13 登记的 `/zwfwck/sjfb/202604/t20260416_1963322.html`，原件复用 `tests/adapters/test_official_context.py` 的 `zwfwck_capacity_fetch`（夹具 `d038b999…`）；其余查询无结果。本用例把 Tavily 单次运行上限提到 1000，免得排在前面的缺口先把额度用完（同 `test_joint_publication_shares_one_request_for_multiple_full_run_gaps`）。AI WebSearch 由测试环境关闭。
- 未新增夹具文件；合成列表页在测试内构造，原件沿用已登记的 `nbs_capacity_utilization_zwfwck_q1.html`。

**验收证据**
- 框 1：`test_a_quarter_the_listing_lacks_is_filled_from_its_zwfwck_release`。列表只读一次、未跟进任何 `/sj/zxfbhjd/2026…` 稿件；2026-Q1 的 `official` 尝试先记 `failed`／`semantic_validation_failed`（找不到链接，不是读取失败或列表未覆盖），随后 `tavily` 记 `verified`／`complete_model_input`；候选校验 `model_usable`，`fetched_url` 为 `/zwfwck/sjfb/` 地址，`raw_hash` 为 `d038b999…`；最终计划 2026-Q1 缺口 `complete`、`missing_members` 为空；证据库 2026-03-31 `quarter_rate` 73.6、`yoy_change` -0.5，所选声明与缺口所选声明一致，来源引用为 `<地址>#sha256=d038b999…`。
- 框 2：`test_the_same_release_offered_for_another_quarter_is_turned_down_by_its_period`。同一地址作为 2025-Q1～Q4 的候选，均已下载、解析（同一哈希），按期次拒收：`not_model_usable`／`period_mismatch`，`claim_ids` 为空，获取回执拒因 `official_context_period_identity_mismatch`，这四期缺口仍不完整，证据库只有 2026-03-31 一期。
- 变异检查：临时把 `retrieval_registry.py` 的 `_NBS` 去掉 `/zwfwck/sjfb/`，两个用例都失败（候选原因变为 `not_whitelisted`），确认用例确实覆盖白名单这一环；已还原，未提交。

**测试**（`dev-venv-l21`）
- 新文件 2 passed（约 10 秒，运行夹具 9.5 秒）；与两例冒烟一起 4 passed（1:37）。未改生产代码、指标目录或 Worker 编排，不加跑重型两例。
- `ruff check`、`ruff format --check` 通过；`mypy` 本文件无报错（被导入的 `tests/adapters/test_official_context.py` 原有 5 处、`tests/conftest.py` 原有 1 处，均不在本票改动）。

**审查**（Codex，各一次）
- 标准轴：阻断无。采纳：`capacity_points` 返回类型改为 `MetricSeriesPoint`；数据库读取改用 `database_connection`（会关闭连接）。不采纳：两用例共享模块级运行库（与 `test_gap_source_repairs.py` 同一模式，只读结果）；查询文案与事件 ID 精确匹配（用于证明走的就是产能利用率 2026-Q1 这条检索）。
- 规格轴：阻断无。确认走通"Tavily 地址 → 白名单 → 正文入口按期次校验 → 入库 → 缺口补齐"整条链路，没有走捷径；复用 Q1 原件给其他季度满足框 2；无需改生产代码。采纳：官方失败断言补上具体分类 `semantic_validation_failed`。说明：提额后的用例不证明默认额度下检索一定排得到产能利用率，这一点不在本票范围。

