# 15: ⑦ 完整度"其他缺失"与全部缺口清单对得上

**What to build:** 读者在 ⑦ 数据说明看到目录口径"其他缺失 N 期"时，能在"全部缺口"里逐期找到这 N 期（或看到为什么某期不列为缺口）。v0016 首个投影（projection-59421326，目标日 10-19）目录口径其他缺失 4 期，缺口清单只能解释 3 期（仓单 07-21、09-09，USDCNY 收盘 10-16）。体检发现 VIX 10-19 在目录 coverage 中缺失、最终计划为 `model_input_missing`，却不在 `cycle_overview.gap_list`（它沿用 10-16 值）；上一投影（10-19 v0015）中两只债券观察指数同样"coverage 缺失却未列缺口"（worker-gap-fixes 07 清单 6 不通过）。先确认差额是哪一期、两处计数口径如何产生，再让两处一致：要么列入缺口清单（注明沿用），要么不计入"其他缺失"并说明归类。依据：`../investigations/browser-v0016-first-day.md` 第 6 条、`../investigations/audit-run-3ebbe323.md` 第 4 节。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 写明差额那一期的根因（file:line），以及选了哪种一致化办法和理由（Comments）
- [x] 测试：目录 coverage 有缺失期（含"沿用上期值"的情形）时，⑦"其他缺失"的期数与全部缺口清单能逐期对上
- [x] 旧投影照旧显示，不前端补算
- [x] 两例冒烟通过

## Comments

- 2026-10-20（ms-15）：**差额那一期**：v0016 首个投影（run-3ebbe323）是 VIX 2026-10-19；v0015（run-153de306）是中债030全价、10年国债930916 的 2026-10-19，同一机制。正式库只读核对：三者 `batch_freshness` 都是 `current`，持有 10-16（VIX `due_period` 为空，两只债券 `due_period`＝10-16），`released_period`＝10-19；最终计划请求了 10-19，没有取到。
- **根因**（74cdb38 行号）：时效判定持有应有期即 current，较新一期已发布只作标注（`src/pring_cycle/freshness.py:391`，2026-10-13 决定），所以 `gap_list` 不列它；`add_projection_gaps` 的 `_historical_periods` 把比已持有更新的计划期当"还没到的期"跳过（`src/pring_cycle/freshness.py:1320` 附近）。而完整度 `coverage_display` 把计划里所有未完成、无门禁、无等待发布的期都算"其他缺失"（`src/pring_cycle/display_projection.py:43-51`）。两处对"已发布、未到应有期"的期口径不一致。
- **一致化办法：不计入"其他缺失"（主 agent 拍板选 B）**。理由：10-13 决定"下一期已公开而尚未持有只作标注，不把 current 降级"，加上术语表"应有期"（推算发布时点已过的最新统计期），这种期不是应有期；完整度表头写的是"应有期"，把它算成缺失是口径错。另一种做法 A（列入缺口清单并注明沿用）先实现过，与 `test_gap_list.py` 的 CSI300、`test_release_preannouncement.py` 的 CPI 两例（断言这种期不算缺口）冲突，已撤回。
- **做法**：
  1. 新增 `freshness.not_yet_due`：最终计划中未完成、无门禁、非等待发布、未持有任何成员的期，若该指标时效为 current 且持有期未覆盖到它，标 `not_due: {carried_period}`。部分持有的期不标，仍由"部分成员未取得"列出。
  2. `DaySummaries.summarize_target` 在 `awaiting_stated_release` 之后调用它，coverage 与 gap_list 用同一份标记后的计划。`RunMaterials` 新增 `freshness_status`，Worker 由同一次 `batch_freshness` 读出状态与持有期一起传入。
  3. `coverage_display` 把 `not_due` 计入 `release_gated`；`_historical_periods` 跳过 `not_due`。
  4. ⑦ 完整度表第四列改名"门禁 / 等待发布 / 未到应有期"，表下加一句"已发布但未到应有期的期沿用上一期，时效仍为当前，也计在门禁一列，不列为缺口。"。gap_list 与上述两例不动。
- **正式库只读模拟**（用新函数重算已发布的 coverage 期列表）：run-3ebbe323 其他缺失 4→3、门禁 2→3（VIX 10-19，沿用 10-16），剩下 3 期即仓单 07-21、09-09 与 USDCNY 10-16，与全部缺口逐期对上；run-153de306 其他缺失 7→5、门禁 3→5（两只债券 10-19），与 WG 清单 6 的 5 期已列出项对上。已发布投影不回填。
- **测试**（venv `dev-venv-ms15`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms15`，`PYTHONDONTWRITEBYTECODE=1`）：
  - 新文件 `tests/integration/test_coverage_matches_gap_list.py`（`summarize_target`＋`RunMaterials` 口径）两例：VIX 式期与只请求目标日的债券期计入门禁、带沿用期、不在缺口清单；历史缺期与 stale 指标的期仍是其他缺失，且逐期能在缺口清单找到。
  - `tests/web/test_reading_section.py` 加两例：新列名与说明句；旧投影按发布时的计数照旧显示，不补算。
  - `tests/integration/test_warrant_historical_gaps.py` 的对账筛选同步排除 `awaiting_release`／`not_due`。
  - 受影响（flock）：`python tools/check.py quick` 27 个文件 → 336 passed（2164 s，超 3 分钟目标，主要是 Worker 全流程模块夹具）；`test_worker_registered_catalog.py` 2 passed（507 s）；两例冒烟 2 passed（59 s）。
  - 合并 macro-followups 6f05b5c（ms-rf）后复跑新测试与 ⑦／结论板／阶段史页面 47 passed，冒烟 2 passed（55 s）。
  - `ruff check`／`ruff format --check`／`mypy`（改动文件）通过；`find src tools -name __pycache__` 为空。
- **偏离**：票面没写要改 Worker；为拿到时效状态，在 `worker.py` 给 `RunMaterials` 多传了 `freshness_status`。完整度表列名与说明句按主 agent 授权直接改（不在 ms-16 范围）。
