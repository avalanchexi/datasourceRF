# 03: 最新期推进后重新展开回看并补取（贷款 2025-09）

**What to build:** 运行中取到新一期（如贷款 2026-09）后，公式回看需求随之变化（ADR-0035 的 t、t−1、t−12、t−13 → 新增 2025-09），但执行队列只遍历初始范围，冻结后才记新缺口（调查第 2 节）。改为发现最新期推进后重新展开依赖并补取新增基期，直到无新增需求或预算耗尽，再冻结截止；不扩大长期留存范围。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 集成测试：初始计划读 t=2026-08，运行中取到 2026-09 后补取 2025-09 全部成员，final 计划无该缺口
- [x] 预算耗尽时如实记缺口、不无限循环
- [x] 两例冒烟通过；完整目录正例 `test_worker_registered_catalog.py` 通过

## Comments

- 2026-10-19 ticket-gl03（分支 `gl-03`）：`FullRunRetrieval.retrieve` 改为多轮。初始计划的各范围取完后，若有范围过了发布闸门（可能取到了新期），就按同一 `decided_at` 重新生成计划，只保留此前未请求过的指标×期（按成员比较，已请求全部成员的期不再请求），记为计划阶段 `expansion:N`（不可变，含 scopes 与 created_at），再取这一轮；直到没有新增范围、本轮无范围过闸门，或重展满 `MAX_EXPANSIONS = 3` 次。中断恢复时按已记录的 `expansion:N` 原样续做。重展后恢复初始计划的判定日历窗口。
- 新增范围接入既有链路：`read_full_retrieval_plan` 返回 `expansions` 列表；`evaluate` 的账本绑定、发布闸门原因、栏目未覆盖原因改用初始范围加各轮重展范围（`planned_scopes`）；`runs.py` 记录补取尝试时，计划范围的查找也包括重展阶段（缓存键改为各阶段文档哈希）；`run_health.gap_diagnostics` 同样按全部计划范围归因。未改留存：重展补到的窗口前基期仍按 ADR-0035 用后清理，只有投影引用的保留。
- 回归：`tests/integration/test_full_run_lookback_reexpansion.py`（v0015 全量运行、目标日 2026-08-28，贷款经官方页离线替身入库）。① 初始计划贷款 t=2026-07，取 7 月时 8 月报告提前到达 → 2025-08 在同一运行请求一次，final 计划 2025-07／2025-08／2026-07／2026-08 全部完整；② 2025-08 取不到时只请求一次即结束，final 计划如实记缺口、9 个成员全缺。两例修复前均失败（2025-08 从未请求），修复后通过。
- 测试：
  - `flock /tmp/pring-heavy.lock python tools/check.py quick` 新测试＋`test_full_run_retrieval.py`、`test_lookback_declaration.py`、`test_retrieval_ledger.py`、`test_official_social_financing_fallback.py`、`test_official_gdp_fallback.py`、`test_database_lifetime.py`、`test_core_stage_lookback.py`、`test_tushare_news.py`、`test_daily_reacquisition.py` → 177 passed、1 failed（1851.7 秒，超 180 秒目标，未删用例）；失败为 `test_database_lifetime.py::test_repeated_runtime_views_remain_available` 断言空计划的字典结构，补 `expansions: []` 后该文件 2 passed（5.9 秒）。
  - 两例冒烟 2 passed（69.2 秒）；`test_worker_registered_catalog.py` 2 passed（428.8 秒，近期记录约 250–280 秒，见下）；`test_core_carry_forward.py` 2 passed（32.2 秒）；均在 `flock /tmp/pring-heavy.lock python -m pytest …` 下，exit 0。ruff、ruff format（改动文件）、mypy（三个源文件）通过。
  - main 头仍为 f285f17，无需合并复跑。
- 开销：临时计时显示完整目录正例里重展的那次重新计划约 7.4 秒（1445 个范围，无新增），初始一轮取数 10.2 秒；该文件比近期记录多出的时间主要不在重展上，同期有其他代理测试占用机器。生产每次运行多一次计划（秒级），T+1 口径下可接受。
- 偏离：票面"预算耗尽"按"取不到时不重复请求、有界结束"验证（重展只请求未请求过的期，另有 3 次上限）；未单独构造搜索预算耗尽的场景，预算耗尽时级联照旧记 `budget_exhausted`，该期在 final 计划中照常记缺口。10-19 正式库的 2025-09 九个成员补取不在本票，待合入安装后由下一次运行（或集成票）取得。GLOSSARY「公式回看」补一句重展说明。

