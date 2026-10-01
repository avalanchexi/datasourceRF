# 24: 信用脉冲回看由模块给出同一个答案

**What to build:** 信用脉冲模块按生效模型的公式版本给出回看，分"计算最少需要"与"取数覆盖范围"两个结果，都从同一个终点与截止时间推出；取数覆盖到 120 日窗口首日也能算出的范围；公式被模型关掉时不取长回看，也不再把信用脉冲列入时效与计划。

**Blocked by:** 23

**勿并行：** 04、09、15、16、17、18、19、20、21、26、27、28（同改：Worker 编排与取数；缺口清单与时效；完整运行规划；信用脉冲模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 5 差异 1、原 Q8／Q18／Q28（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「六、信用脉冲模块与指标尺度」。

## 现状

- 规划只在走年初至今差分、窗口不从 1 月／Q1 起时加基期；Worker 无条件加一期（勘察 2.2）。
- 终点：Worker 用目标日日终按发布规则推最新期；规划优先已持有最新期，截止时间取 `min(selector.as_of, utc_now(), target_end)`（勘察 2.2、2.3）。持有落后于发布规则时，规划要求的起点可能早于取数起点，目前被"目标年份减二"的旧起点兜住（`worker.py:1776`）。
- 取数只为目标日准备；补算到窗口首日时，该日所需回看更早，读码推断会缺期（勘察 2.11，未实测）。
- `_credit_lookback_starts` 不看公式版本，模型关掉公式仍取 25 个月／9 个季度（勘察第二份 34）；时效父映射 `freshness.py:204` 与完整运行计划（`full_retrieval.py:380` 的 `required_input_rule_unavailable`）也不看公式开关（第二份 32、33）。

## 验收

- [x] 先实测补算日缺期推断（首次初始化夹具或真实库任一），结论写入 Comments。
- [x] 模块给出"计算最少需要"与"取数覆盖范围"；Worker 与规划都从同一终点、同一截止时间取用；取数覆盖范围包含窗口首日的计算需要。
- [x] 取数只由生效模型的公式版本决定；公式未配置时不发社融／GDP 长回看请求（社融、GDP 自身的正常取数照旧）。
- [x] 公式未配置时，信用脉冲不进时效清单、不在完整运行计划留 `required_input_rule_unavailable`。
- [x] 按 TDD：持有落后于发布规则时起点一致；窗口首日可算；公式关闭时不取长回看、不列时效。
- [x] 受影响测试经 `check.py quick` 通过；涉及 Worker 取数，加跑完整目录正例。
- [x] 代码审查无阻断。

## Comments

**2026-10-02 实测：补算日缺期推断成立**

- 纯内存对照（Codex 只读探针，`scratchpad/t24-survey.md` 第 4 条；本票已固化为 `test_credit_impulse.py::test_the_window_s_first_day_derives_from_what_the_fetch_covers`）：120 个工作日窗口 2026-04-06…2026-09-18，ytd-flow-v0002，各期公开时间取登记的发布规则。
  - 只取目标日所需（社融 2024-08…2026-08、GDP 2024-Q2…2026-Q2）：首日只看得到社融 19 期、GDP 7 季，`missing_inputs`；全窗 115 日缺输入、5 日可算。
  - 扩到首日所需（社融 2024-02、GDP 2024-Q1 起）：120 日全部可算。
- 真实库只读查询：运行 `run-a0418ed439ef25c9e00c`（目标日 2026-09-23）的 117 个补算日（2026-04-07…2026-09-22，model-v0012）信用公式全部 `missing_inputs`。真实库只证明"补算日确有缺输入结果"，不单独归因；内存对照证明"只按目标日取数"本身足以造成缺期。

**2026-10-02 实施记录**

- **模块** `credit_impulse.py`：
  - `minimum_requirements(formula_version, *, public_cutoff, calendar, direct_held=)`：某一截止下的最少需求。终点取该截止时发布规则已放出的最新期（不随持有落后而后移）；允许差分的输入，在窗口不从 1 月／Q1 起、且窗口各期并非都有直接值时，加同年上一期作基期。
  - `fetch_coverage(formula_version, *, window, public_cutoff, calendar)`：对窗口每一日按 `min(public_cutoff, 该日日终)` 求最少需求，取并集。直接值可能晚于早期某日才公开，所以覆盖范围不借用当前的直接持有，凡允许差分的都保留基期。
  - `InputPeriods`（逐期列出，`start`、`counts`）、`latest_released`、`direct_periods(selector)`（替代 `_reported_count`，按具体期判断直接持有）、`metrics_off(formula_versions)`。
  - 删除 `lookback_start`、`requirements`；未知公式版本显式报错。
- **调用方**：
  - `full_run_requirements`：
    - `public_cutoff(run, decided_at)` 统一为 `min(选择器时刻, 决策时刻, 目标日日终)`；
    - `credit_inputs(paths, rules, run, *, decided_at, window=, direct_held=)` 给出目标日最少需求与窗口覆盖，发布规则日历取决策时刻已知的上交所日历（`SseCalendar.around`，未覆盖处回退当前日历），窗口默认 `SseCalendar.window(target, 120)`；
    - `formula_requirements` 的信用条目保留 `required_input_periods`（目标日最少期数），新增 `covered_input_periods`（窗口覆盖首末期）。
  - Worker：直接取数前读一次 `decided_at`，算出覆盖后传给 `refresh_context_sources(..., credit=)`，并传给 `FullRunRetrieval.retrieve(run, decided_at=)`，首次规划用同一时刻。`_credit_lookback_starts` 删除。
  - 规划 `_plan`：社融／GDP 的需求期为原有期数与信用覆盖期的并集，但覆盖期只取到该指标的规划终点为止：起点与取数一致，已放出而尚未持有的新一期仍只作发现对象、不列为必需（保持"寻找新发布不等于要求它"，`test_official_gdp_fallback.py::test_gdp_discovers_next_completed_quarter_without_making_unpublished_values_required` 首轮回归即因此失败后修正）。
  - 窗口与发布规则日历都按决策时刻读取（`SseCalendar(as_of=决策时刻的选择器时刻)`），首次规划不再用取数后才读的日历窗口，避免广度刷新补进的日历回执让规划比取数要得更早。最终评估传当前时刻，冻结运行的选择器时刻即 `system_as_of`，与 `required_calendar` 一致。
  - 公式关闭（生效模型无 `credit_impulse` 键）：覆盖为空，社融／GDP 只按自身范围取数；`_plan` 跳过 `CN_CREDIT_IMPULSE`（不再留 `required_input_rule_unavailable`）；Worker 记时效时排除它。
- **测试**：
  - `test_credit_impulse.py`：单日需求 6 例（三版本、直接持有、年初窗口）；持有落后仍按发布规则终点；窗口覆盖包含每日最少需求；公式关闭为空；首日可算对照（窗口覆盖／仅目标日）。
  - `test_full_run_retrieval.py`：完整运行计划覆盖到窗口首日 2026-03-16 的需求（社融 2024-03…2026-07 共 29 期、GDP 2024-Q1…2026-Q2 共 10 季），目标日最少仍 24/8；Worker 取数起点与计划起点一致；公式关闭时无信用条目、无信用时效，社融／GDP 时效仍在。
  - `test_worker_reviewed_context.py`：取数起点参数化公式开／关；直接调用 `refresh_context_sources` 的用例传入与 Worker 同法算出的覆盖。
- **行为差异（只记录，未改）**：
  - 完整运行最终评估仍按冻结截止重新规划，截止推进后若新放出一期，最终缺口按新终点判断（与首次规划可差最新一期）。
  - 旧检查点恢复（`recover_legacy_plan`）按新规则重建计划但不补取，若旧取数只覆盖目标日，恢复后首日仍可能 `missing_inputs`。
  - 计划需求变多后，缺少的早期社融／GDP 会进入缺口检索，请求量随之增加。
  - 社融／GDP 自身的普通取数范围仍是两年（票 30 处理）；公式关闭后宏观卡片的固定角色与解释性完整性检查仍可能显示信用缺项（不属本票）。
  - `derive` 仍按"有声明的点"选直接分支（票 26）。
  - 未加"决策后新增／修订日历回执"与"跨发布时刻"的专门用例（审查建议）；两者现由同一 `decided_at` 传参保证，只有完整运行用例比对取数与规划起点。
- **验证**（`PYTHONPATH=src`）：受影响 62 个测试文件（含两例收尾冒烟、完整目录正例 `test_worker_registered_catalog.py`、三核心反例 `test_core_carry_forward.py`）共 794 例全过，耗时 44.9 分钟。ruff、mypy（改动的源文件）通过。
- **审查**（Codex 只读，三轮）：首轮 3 项阻断，即截止时刻未真正共用、需求计算未用上交所日历、目标日的直接值被套用到历史日，均已修；次轮余 1 项阻断，即首次规划窗口取自取数后的日历，已修；第三轮确认无阻断。
