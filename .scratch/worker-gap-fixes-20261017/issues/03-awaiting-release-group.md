# 03: "等待发布"分组

**What to build:** EIA 布伦特、WTI 正常的分批发布滞后被列为缺失（决定 1）。缺口清单新增"等待发布"分组：来源原件写明下次发布日（EIA）或按登记发布滞后未到期的期归入此组，不计入缺失与完整度缺口；⑦ 单列一组（中文文案进对照表）。证据时效仍只有 current/stale。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** A13（⑦ 原因码中文对照表）

**Status:** done

- [x] 以 10-15 EIA 原件为夹具，完整运行把 10-15 期归入等待发布并带下次发布日
- [x] 完整度缺口数不含等待发布
- [x] `dashboard_page` 断言 ⑦ 有"等待发布"组且不在"缺失"组
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

**改了什么**
- `freshness.add_projection_gaps`：最终计划中门禁原因为 `awaiting_release` 的未完成期不再进 `not_requested`（原先整行记"缺失·未请求"），改记 `awaiting_release` 明细：每期带 `next_release_date` 与 `basis`。依据优先取来源原件写明的下次发布日（P2 行 `latest_acquisition.next_release_date`，EIA 历史表的 Next Release Date），须晚于该期；否则按登记时效规则 `release_at` 推算（`registered_release_lag`）；无规则或事件类只记期。只有等待发布期的指标单列一行，分类 `awaiting_release`；已因其他原因列出的指标保留原分类，在该行附注等待发布期（一指标一行的约定不变）。`_GAP_ORDER` 末尾加 `awaiting_release`。
- 完整度：`coverage_display` 本就把有门禁的期计入"门禁 / 等待发布"、不计"其他缺失"，未改；集成测试断言 EIA 的 10-15 期按 `release_gate=awaiting_release` 计入门禁列。首页结论板"数据边界"的缺口数改为不含等待发布行，另写"（另 K 项等待发布）"。
- ⑦：`dashboard.GAP_CATEGORY_LABELS` 末尾加"等待发布"组（排在最后，预览先显示真正缺口）；行文"等待发布 2026-10-15（下次发布 2026-10-21，来源原件写明）"；等待发布行不写"未配置额外网页检索补缺"。依据中文进 `wording.REASON_LABELS`（`source_next_release_date` 来源原件写明、`registered_release_lag` 按登记发布滞后推算）。
- 夹具：10-15 运行的 Brent、WTI 历史表原件复制为 `tests/fixtures/eia/RBRTED_20261015.htm`、`RWTCD_20261015.htm`（README 记 sha256 与来历）。
- 门禁本身（`worker._registered_release_state`）与 `freshness` 的 current/stale 二值未动。

**测试与耗时**
- 新增 `tests/integration/test_awaiting_release_group.py`（完整运行，夹具 TuShare 三核心与交易日历＋EIA 10-15 原件，目标 10-15、冻结 10-16 16:08 北京）：EIA 两行归入等待发布、下次发布日 2026-10-21 取自原件、无 `not_requested`、完整度按门禁计；单例 call 33.8 s。
- 新增 `tests/web/test_awaiting_release_group.py`（`dashboard_page`）3 例：⑦ 有"等待发布（2）"组且"缺失"组无 EIA；结论板"1 项缺口（另 2 项等待发布）"；兼有其他缺口的指标附注等待发布期。实现前红（KeyError '等待发布' 等 3 例失败），实现后绿。
- 受影响：网页 8 个文件 81 例通过（7 s）；集成（新增＋`test_full_run_retrieval` 两例门禁用例＋`test_derived_context_freshness`、`test_official_pmi_fallback`、`test_display_projection`）57 例通过 156 s；两项必跑冒烟 2 例通过 41 s（均在 heavy 锁下，等锁约 1 小时 40 分，主要是 cl15 全套）。
- ruff check / format --check、mypy（freshness、dashboard、cockpit、wording）通过。

**遗留 / 领域选择（按推荐实现）**
- 旧投影（如 10-15 已发布的那份）仍按原样显示"缺失·未请求 2026-10-15（等待发布）"；不在前端重算历史投影，新版运行才会分组。
- 仅 `release_gate=awaiting_release` 归入此组；`earlier_session_not_searched`、`unknown_release_configuration`、负缓存等其他门禁仍算缺失（不是发布未到）。
- 登记滞后已到期、但原件写明下次发布日未到的期（计划会请求、原件无该格）未改：此时门禁放行，期仍按"其他缺失"计。如需按原件下次发布日改门禁，另开票。
- 完整度表列名仍为"门禁 / 等待发布"，未把等待发布与其他门禁拆成两列。

