Status: done
Category: bug
Type: task

# 04：GDP 官方回退成员集合为空，同比期语义被拒

## 现象

GDP 实际季度同比缺 5 季：同比因 `gdp_yoy_period_semantics_unverified` 被拒；Tavily 达上限；官方回退因成员集合为空被取消。

- 位置（读码）：`full_retrieval.py:397`。
- 来源：[验收记录第五节](../../macro-semantics-20261006/acceptance-20261008.md)。

## 验收草案

- [x] 官方回退带上实际缺失的 GDP 成员，不因成员集合为空取消。（按分流订正：传的是选择得出的缺失成员，不要求范围显式列成员）
- [x] 核实 `gdp_yoy_period_semantics_unverified` 的拒收是否应放行实际季度同比，并补测试。（结论：保持拒收，实际季度同比改由官方补；端到端测试断言 TuShare 的同比不入库、官方 4.3 无争议）

## Comments

### 2026-10-08 分流（Codex 只读调查 + 主会话核验，见 [triage-20261008.md](../triage-20261008.md)）

- **订正票面**：回退缺陷属实——`scope.members` 为空时传入空 `missing`，`all(空集合)` 成立，已有名义值便取消官方回退（`full_retrieval.py:503`、`:397`）。但 TuShare GDP 同比拒收**有依据，应保持拒收**：2026Q2 TuShare `gdp_yoy=4.7`，官方实际季度同比为 4.3（`tushare_context.py:1840`）。
- 修复：始终传递实际缺失成员，官方只补缺失的同比，保留已持有名义值保护。约 1–3 模块。
- 无需用户决定。排在 01 之后（共用计划代码）。

### 2026-10-08 实施

- **计划**（`full_retrieval.py` `_plan`）：补缺计划给 `official_candidate` 的始终是选择得出的 `selection.missing_members`，不再只在范围显式列成员时才传。原先范围不列成员时传空元组，`all(空集合)` 成立，只要 TuShare 交付过该期任一成员就取消官方地址；现在只有缺失成员全部由 TuShare 交付时才取消。GDP 名义值已持有、实际季度同比缺失时，计划带上统计局列表地址。事件利率和"上一期新发布"两处探测仍按整期判断，未改。
- **官方只补同比**：未改代码。Worker 官方取数沿用 L02 的 `official_held_members`（全族已持有成员），名义值仍是 TuShare 的修订值，官方首发名义值不入库。
- **TuShare 同比保持拒收**：`gdp_yoy_period_semantics_unverified` 未改。
- **测试**：把 `test_gdp_fallback_respects_delivered_period_without_loosening_required_members` 改名为 `test_gdp_fallback_fetches_the_growth_tushare_withholds_without_loosening_members`，并改正旧预期。旧测试把"TuShare 交付了名义值就不请求官方"当成正确行为，正是本票的缺陷。参数 delivered=True 就是要求的替身（名义已持有、同比缺失、范围未列成员）：计划范围无 `members` 且带列表地址；官方可达时 4 个同比来自统计局（总量 4.3，TuShare 给的 4.6 不入库），4 个名义值的全部声明仍只来自 TuShare，选择完整；官方失败或无匹配公告时，缺失的恰是 4 个同比成员。改前 delivered=True 的 3 个参数为红，改后全绿。另外删掉了同文件里一处与顶层导入重复的局部导入。
- **验证**：本测试文件 23 passed（79 s）。受影响 20 个文件共 320 例，319 passed、1 failed（3478 s，远超 3 分钟目标，未删测试）。失败的是 `test_gap_source_repairs.py::test_the_basket_is_chained_from_its_base_on_settlements`，与本票无关：用 HEAD（aa46a60 之后）源码副本跑同样失败；用 L01 之前 130a337 的源码副本跑能通过，疑为 L01 引入，已报主 agent。冒烟两例 2 passed（231 s）。重型两例经 `flock` 串行：`test_worker_registered_catalog.py` 2 passed（445 s），`test_core_carry_forward.py` 2 passed（pytest 106 s）。改动文件上的 `ruff check`、`ruff format --check`、`mypy` 都通过。
- **Codex 审查**：标准轴和规格轴各一轮，都是"阻断：无"。采纳的非阻断意见：失败分支精确核对缺失成员集合；断言名义值的全部声明（不只是选中的那条）来自 TuShare。不采纳的意见：① 缺失项是 `X:dimension_contract_unavailable` 时，仍会保留官方地址。这条只在已有 TuShare 交付、又缺成员契约时才会出现，登记了官方地址的宏观指标都有成员契约，测不到这种组合；而且显式列成员的范围在改前就是这样处理的。② 补"部分同比已持有""全部齐全不请求"两种 GDP 场景。前者走同一条 held 排除路径（L02 已有测试），后者在选择完整时根本不进入分组，与本改动无关。
- **残余风险**：非 GDP 指标里，只要 TuShare 交付了部分成员、仍缺其他成员，现在也会生成官方候选，每期最多多一次官方列表请求。这符合 ADR-0026 按成员"取到即止"的理解。五季 GDP 能否在真实运行中补齐，还取决于统计局历史列表的覆盖（L05），留待票 09 验收。
