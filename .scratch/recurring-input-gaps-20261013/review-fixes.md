# 集成分支代码审查修复（2026-10-13）

来源：集成分支 `recurring-input-gaps`（d316f82）的 Codex 两轴审查，原文在会话 scratchpad `review/standards.out`、`review/spec.out`。本次修复三项，分支 `worktree-agent-a572a0ed11b6aeafa`，基于 d316f82，收尾已并入集成分支 a6beb7d。票面状态未改。

| 项 | 处置 | 提交 |
|---|---|---|
| Spec 1（阻断）dual-cutoff 次晨修订折叠丢旧值 | 属实，已修 | 6bcb219、f653bc9 |
| Standards 1 采集窗口／冻结判断重复 | 采纳，收拢到 `SummaryCutoff.decision_as_of` | d6e3cb1 |
| Standards 2 体检六字段位置元组 | 采纳，改为标准库 `NamedTuple` | 4f80857 |

Spec 2（PP 只有二手证据）、Spec 3（移出日按 SHFE 日历代算）主 agent 已定为已知局限，本次不处理。

## 1. Spec 第 1 条：dual-cutoff-v0003 下次晨修订遮住旧值

**复现**：审查原文写的触发条件是“没有公开时间”，但这一形状经写入接口到不了：ADR-0021 会把缺失的公开时间推定为 min(登记发布时刻, `fetched_at`)，`effective_source_claim` 里永远非空。对 live 库只读核查：992122 条声明中，生效公开时间为空的 0 条，公开时间晚于 `available_at` 的也是 0 条。

问题仍然属实，只是触发形状不同。写入时并不要求公开时间不晚于入库时间，而 `docs/operations/ecb-reference-cross.md` 说明的 dual-cutoff 用途正是“日期精度导致公开时间晚于实际校验”。触发形状如下：已结束期次的修订在目标日结束后、运行截止前入库，公开时间晚于运行截止（日期精度）。旧实现的仓库查询给 SYSTEM 路径的上限是运行截止，修订因此进入查询，按同来源取最新折叠掉旧声明；随后 `_point_at_target` 的 SYSTEM 路径只认日末前入库的声明，又把修订剔除，旧值丢失。票 01 之前公开截止取 min(冻结截止, 日末)，SYSTEM 上限也是日末，所以这是票 01 引入的回归。

红灯：投影接缝上的用例 3/3 稳定变红（目标日 CPI 7 月一行也没有）；对照组把修订入库时间改到截止之后，用例通过。之后用例按 ADR-0034 迁到单日汇总接缝。临时把 SYSTEM 上限改回运行截止复验，迁移后的用例同样变红（`cpi_periods == {'None'}`），恢复后通过。

**修复**：`EvidenceRepository.metric_series` 的布尔参数 `allow_system_at_public_cutoff` 改为 `system_known_by: datetime | None`，即 SYSTEM 路径自己的上限；SQL 路径与快照路径都在同来源修订折叠之前施加。`TargetBoundEvidenceRepository._query_at_target` 传入目标日日末，与 `_point_at_target` 的判断一致。补算日的截止本来就是日末，PUBLIC 模式和非 dual-cutoff 模型传 `None`，行为不变。期末晚于目标日的点仍走票 01 的“按该日结束重读”。`ecb-reference-cross.md` 的 dual-cutoff 段已按票 01 之后的目标日口径改写。

**测试**：
- 新增 `tests/integration/test_day_summary.py::test_a_revision_held_only_after_the_day_keeps_the_value_it_revises`，在单日汇总接缝上断言：目标日汇总有 7 月 CPI，冻结输入含原声明、不含修订。dual-cutoff 只允许注册目录声明，用例以 monkeypatch 跳过 `validate_model_catalog`，并注明原因。
- `tests/integration/test_series_snapshot.py` 的组合中新增“独立系统上限”（不等于公开截止的日末），快照路径与直查路径逐点一致。

## 2. Standards 第 1 条：可见时点判断重复

“采集窗口开放时取决策时刻，冻结后取运行截止”原先写在 `summary_cutoff.py`、`search_evidence.py`、`full_run_requirements.py` 三处，`full_retrieval._gate` 还有第四处。现统一为 `SummaryCutoff.decision_as_of(run, decided_at)`；`SummaryCutoff.target` 写成 `min(decision_as_of, decided_at)`，删去 `full_run_requirements._decision_as_of`。

各分支逐一等价，Codex 规格轴已逐分支核对。唯一差别是选值器和门禁原来各取两次 `utc_now()`，现在合成一次，只在两次取时之间发生墙钟回拨时才有区别（回拨已由残余票 01 处置）。

未改：`full_retrieval._pull_news` 里同形的判断。票 06 正在改新闻窗口，为免冲突留给它，可在票 06 合入后顺手改用 `decision_as_of`。

## 3. Standards 第 2 条：体检六字段位置元组

`tools/quality/model_input.py` 新增 `StoredClaim(NamedTuple)`（只用标准库 `typing`），字段与 SELECT 前六列同序，`public_at` 属性给出读视图的生效公开时间（声明的，否则推定的）。三个消费者 `_latest_published`、`_one_behind`、`_held_reason` 改为按名访问。

对账：`python3 tools/quality/audit.py --run run-0a8dabc2e820321b84e1` 改前改后各跑一次，报告 666 行，除末行耗时（27.3 秒对 24.1 秒）外逐字相同。三个消费者都在报告中出现：上一可得期 4 处、上一期 2 处、已持有 2 处。

## 测试与耗时

venv `dev-venv-rigfix`，basetemp `/tmp/pytest-rigfix`。

- 受影响集合 15 个文件。选择依据：投影与选值器的时点规则及其调用方（投影、快照、dual-cutoff 两个 Worker 用例、ECB、单日汇总、时点选值、完整运行检索、lookback、补缺门禁相关的官方页／GDP 回退／仓单／注册模型输入、选值器生命周期）。
  - 修复后首轮：461 过、1 败，耗时 18 分钟。失败的 `test_official_listing_pages.py` 一例报 `unable to open database file`。原因是我在后台运行期间用同一 basetemp 单跑了一例，pytest 启动时清空 basetemp，删掉了正在运行用例的库，属环境操作失误。
  - 该文件与改动文件单独复跑：91 过，177 秒。
  - 收尾复跑：并入集成分支 a6beb7d（只改了 goal.md）并重装 venv 后，全集合 462 过，耗时 14.7 分钟。超过 3 分钟反馈目标，原因是改动落在共享的时点选值逻辑上，调用方面广。
- 冒烟两例：2 过，33 秒。
- 重型 `test_worker_registered_catalog.py` 与 `test_core_carry_forward.py`（`flock /tmp/pring-heavy.lock`）：4 过，281 秒。
- `ruff check`、`ruff format --check`、`mypy`（改动的生产文件）通过。

## 审查（Codex，`codex exec -s read-only`，只审 d316f82 之后本次修复）

- Standards 首轮：阻断，1 条硬违规。新增的汇总规则用例直接调用 `build_context_projection`，违反 ADR-0034（新增汇总规则测试放在单日汇总接缝上）。另有 2 条判断题：复制 `certified_definition` 替身；`system_known_by` 缺时区时的错误信息有误导。三条均已在 f653bc9 处理：用例迁到单日汇总接缝、不再复制替身，缺时区单独报 `system_known_by_must_be_timezone_aware`。定向复审：阻断无。
- Spec：阻断无。第 1 项修复成立，PUBLIC 模式、补算日、期末晚于目标日的点、嵌套包装、快照路径均未出现新回归；第 2、3 项行为不变。唯一的低严重度备注是上述墙钟回拨前提，已在第 2 节写明。
