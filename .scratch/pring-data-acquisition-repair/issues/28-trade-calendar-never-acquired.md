Status: ready-for-agent
Execution: in-progress
Scope: 阻断所有正式阶段产出；优先级高于票13 的认证工序
Decision: 2026-09-18 为前端改版查证"核心资产数据集为何全空"时发现。见[发现记录](../finding-empty-trade-calendar-20260918.md)。
Correction: 2026-09-21 只读核对发现下方「现象」与「根因」两节多处已过时，四项验收里三项其实已被覆盖。**照本票原文实施会做错东西**，先读[事实对齐](../finding-28-calendar-facts-20260921.md)。

# 28: 交易日历从未被采集，运行因此全部降级

**What to build:** 完整运行能取得交易日历并产出正式阶段；用户看到的阶段为空时，是因为三资产确实构成非典型组合，而不是因为日历缺失。

**Blocked by:** 无。

**Dependency rationale:** 三个核心资产各有 43,300 条已认证声明（2017-01-03 → 2026-08-28），数据齐备；缺的只是日历。本票不依赖票13 的认证工序。

## 现象

运行库 7 次投影**无一例外**：`current_stage` 为 `None`、`completeness` 为 `degraded`、`core_assets` 数据集 0 条。**系统从未产出过一个正式阶段。**

## 根因：两处规则口径相反

| 位置 | 口径 |
|---|---|
| `full_retrieval.py:164` | `CN_TRADE_CALENDAR` 属 `operational_evidence`，**不生成缺口、不采集** |
| `full_run_requirements.py:20`、`worker.py:343` | 没有 120 个交易日即 `unavailable`，标记 `p0_required_calendar_period_missing`，**运行降级** |

`trade_cal` 的采集请求数为 **0**——不是失败，是从未发起。`full_run_requirements.py:44` 留有一条回退去找 `api_name='trade_cal'` 的已校验回执，说明设计上预期有人取它，但没有适配器负责。

## 待设计的可观察行为

- 交易日历有明确的采集归属：要么进入某个通道的例行刷新，要么进入缺口计划。**两处规则必须对齐**，不能一处说不用采、一处说没有就不能跑。
- 日历缺失时的失败分类**与非典型组合明确区分**：前者是采集问题，后者是正确的领域结论。当前两者都表现为"无阶段"，用户无法分辨。
- 补上日历后，三资产能否形成稳定状态由 `trend-v0001` 决定（120 日窗口、8 日持续）。**仍可能是非典型组合，那时当前阶段为空是正确行为**，不得为了"有阶段"而放宽规则。

## 验收条件

- [ ] 公开反例：日历齐备的完整运行产出 `core_assets` 数据集非空，且当前阶段按 `stage.py` 的映射表得出（或如实为空并说明是非典型组合）。
- [ ] 公开反例：日历缺失时的失败分类与非典型组合在查询结果中可区分。
- [ ] 两处规则对齐，有用例证明不会再出现"不采集但又必需"的组合。
- [ ] 不放宽 `trend-v0001` 的稳定性要求，不为产出阶段而降低门槛。

## 2026-09-21 事实对齐（只读，未勾选验收）

`4be17e2`「Block new Worker publication without an independent calendar (#28)」已于 2026-09-18
落地，但本票面此前从未更新。逐条核对见[事实对齐](../finding-28-calendar-facts-20260921.md)，摘要：

- **根因三条过时**：`trade_cal` 会被 `worker.py:323` 的 `_refresh_core_sources` 采集（在缺口计划之前）；
  适配器 `source_adapters.py:164` 一直都在；「7 次投影无正式阶段」已由 `4be17e2` 的实施记录反证。
- **验收 1 已被覆盖**：`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`
  断言 `daily_window` available、`plan["acquisitions"]` 含 validated 的 `trade_cal`、
  `core_assets` 3 条资产、且 `current_stage == "stage_iii"`——系统确实能产出正式阶段。
  唯一隐患是这些断言寄居在一个主旨不同的测试里，可能随它改写而无声消失。
- **验收 2 已被覆盖**：`test_worker_calendar_gate.py` 钉住缺日历侧；两类分类分开使用
  （`worker.py:342` 的 `p0_required_calendar_unavailable` 与 `:348` 的 `p0_required_calendar_period_missing`）。
- **验收 3 只剩一个分支**：正常路径上日历已有明确归属（例行刷新），`full_retrieval.py:213` 的
  `operational_evidence` 标注不再是缺陷。但 `_refresh_core_sources`（`worker.py:1700`）在
  `TUSHARE_TOKEN` 缺失时**静默 return**，此时无人负责日历而 `required_calendar` 仍必需它，
  「不采集但又必需」原样成立；运行以 `p0_required_calendar_unavailable` 停下，分类指向
  「日历不可用」，真实原因却是没配 token。**这是目前唯一确定的实质剩余工作。**
- **验收 4 未被违反**：缺日历即拒绝发布，方向与放宽相反。

实施切片应做三件事：补上 token 缺失分支的可分失败分类；给验收 1 一条以本票为主旨的用例；
逐项勾选并附证据。**不要新建日历采集器**——`4be17e2` 的实施记录已写明不新增重复采集器。

## 与票13 的关系

此前把关键路径判为"票13 的 18 项 A 类认证"。那个判断方向没错但不完整：**即使 18 项全部认证完成，只要日历仍为空，运行照样降级、阶段照样为空。** 本票应排在票13 之前。
