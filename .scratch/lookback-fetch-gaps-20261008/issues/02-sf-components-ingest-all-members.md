Status: done
Category: bug
Type: task

# 02：社融分项未按原件全部入库

## 现象

人民银行社融官方原件中已有 24 个分项值，但入库只按请求的总量成员过滤，分项没有入库。v0015 社融辅成员（政府债与 7 个非政府分项，票 04 用户确认）因此缺期。

- 位置（读码）：`official_context.py:563`。
- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md)。

## 验收草案

- [x] 同一原件内的分项按维度成员全部入库，不因请求只要总量而丢弃。
- [ ] F3"只靠政府债撑"所需的 7 个分项在真实运行中可读。（留待票 09 真实运行验收；本票只有离线替身证据）

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- 根因属实（`official_context.py:563–575` 按请求 metric_id 过滤完整公告）。实测 2026-06、07 两份原件各规范化出 24 个分项与 3 个总量，却只关联 1 条总量声明。
- **并入 run-findings 10（OMO 公告利率被丢），同一过滤点**；本票为实施主票。
- 修复：同一原件中目录支持的同族成员一并处理，保留 `held_members` 保护（旧公告名义 GDP 与已持有修订值的冲突，`worker.py:990`）与查重。改正 `test_official_social_financing_fallback.py:228` 断言分项不存在的旧预期，补"只请求总量但原件含分项""只请求金额但公告含利率"替身。约 2–3 模块。
- 无需用户决定（ADR-0028 已要求随操作量检查利率变化）。

### 2026-10-08 实施

- **入库范围**（`official_context.py`）：新增 `official_family_metrics`（官方族中当前目录定义了的指标，只跳过 `unknown_metric_id`，其他目录错误照抛）。`_ingest_acquired_official_release` 在给定 `metric_ids` 时，入库范围 = 请求指标 ∪ 同族目录指标，仍按 `held_members` 排除、仍经 `append_source_claims` 查重；"请求指标一个都没剩"才拒收 `official_context_requested_metrics_missing`，语义不变。`metric_ids=None`（文档导入、LPR、搜索候选）保持原样。
- **已持有保护随之扩到全族**（`search_evidence.py`）：新增 `ModelInputSelector.official_held_members(scope)`，以同族目录指标、清空点名成员的范围求 held；Worker 官方取数与搜索官方候选共用。否则"只请求分项"会让页面上的社融总量与 TuShare 已交付值并存，"只点名实际同比的回看"会让旧公告名义 GDP 与修订值并存（两者都经变异验证会失败）。
- **事件类 held 按期**（`ModelInputSelector.select`）：事件类指标只有最新事件落在本期时才算已持有；旧日利率仍被选中、仍作现行基准，但不再挡住当天公告自己的利率（ADR-0028"持有与否都查，查到即记新观测"）。这是 run-findings 10 中"范围含利率时利率仍被丢"的第二个原因。
- **测试**：改正 `test_official_social_financing_fallback.py` 旧预期（官方页入库时 24 个分项全部入库，否则 0）；新增社融"只请求分项、TuShare 已交付总量"（总量保持 TuShare 值，缺的存量同比与 24 分项来自人民银行）、OMO"只请求金额／金额＋利率、已有前一日旧利率"两参数（9/24 利率与金额都入库）、GDP"回看只点名实际同比"（名义值只有 TuShare）。新用例修前均红、修后绿。
- **验证**：受影响 4 个文件 70 passed（168 s）；扩大范围 25 个文件 483 passed（1350 s，超 3 分钟目标，部分时段与 Codex 审查并行，未删测试）；冒烟两例 2 passed（41 s）；重型逐个串行 `test_worker_registered_catalog.py` 2 passed（427 s，与 L06／R06 记录的 380–421 s 相当）、`test_core_carry_forward.py` 2 passed（41 s）。`ruff check`、`ruff format --check`、`mypy`（三个源文件）通过。
- **Codex 审查**：标准轴无阻断；采纳去重局部导入、收敛两处扩族逻辑为共享方法、收窄 `KeyError`、改写辅助函数说明、加强社融用例断言（带期与值）。规格轴第一轮两条阻断：LPR 经共享入库入口时 `chinamoney_lpr` 不在官方族（改为 `metric_ids=None` 不扩族）；扩族保留了点名成员致 GDP 名义值不受保护（改为清空成员并补 GDP 用例）。定向复审：两条均已修复，阻断：无。
- **遗留**：`metric_ids=None` 路径（文档导入、搜索候选）仍不按目录过滤同族指标，目录缺某同族指标时整页入库会因 `unknown_metric_id` 失败——既有行为，本票未改。规格轴建议的"重复获取查重""真正变息"替身未补（查重走既有 `append_source_claims`，变息与同值在入库路径上无分支差异）。F3 七分项真实可读待票 09 验收；未取得的历史原件依赖 01／05。

