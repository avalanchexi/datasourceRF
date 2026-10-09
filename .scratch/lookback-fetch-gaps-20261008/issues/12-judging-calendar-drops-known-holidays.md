Status: done
Category: bug
Type: task

# 12：截止日超出已存日历一天时，判定日历丢弃已知休市日，日频指标被误判落后多期

## 现象（票 09 真实运行发现，2026-10-09）

run-8a3779cff80f6bd586a0 的目标日为 2026-09-30，取数截止冻结在北京时间 10-09 06:39。已存的交易日历回执最远覆盖到 10-08。`judging_calendar` 要把日历从窗口末日（09-30）延伸到截止日（10-09），`sessions_between` 发现 10-09 未覆盖，返回 None（`trading_calendar.py:344`），于是整段延伸被放弃，退回只含窗口的日历（`trading_calendar.py:404`）。窗口外的日子按周一至周五推定，国庆休市的 10-01、02、05、06、07 被当成交易日。

结果：与基线相比，27 个国内日频指标在 `batch_freshness` 中由 `current`（或 `awaiting_release`）变为 `stale`：25 个 `periods_behind=5`，2 个 `periods_behind=4`（两融余额、USDCNY 16:30）。其中包括三核心价格、DR007、OMO 净投放、SHIBOR、人民币中间价等，而基线对同样的 09-30 数据判为 `current`。本次 `stale` 共 33 项，另外 6 项（VIX、美债三项、DR007 政策利差、OMO 利率）在基线中已经是 `stale`，原因不同。发布的缺口清单因此有 36 项（基线 7 项），大部分是这类虚假的"落后 4–5 期"。确认度中流动性投放与 DR007 的主要成员 `evidence_status=stale`；本次为非典型组合，确认关系是"不适用"，没有改变结论。在典型阶段下，`confirmation.py:1202` 会把它们记为"未确认"。

三核心就绪与阶段判定走另一条路径，不受影响（与基线逐项一致）。

- 只读调查：Codex（scratchpad `lfg-codex-stale.out`），主会话已复核 `trading_calendar.py:344`、`:404` 与 `batch_freshness` 记录。
- 既有缺陷：该回退逻辑在 `e439ae4`（10-03）已存在，本批 `39fb148..3b3c3a8` 没有修改它。触发条件是"截止日比已存日历多出至少一天，且窗口末日与截止日之间有休市日"。按默认目标日在收盘后提交时，窗口末日与截止日之间通常没有休市日，因此不易触发。
- 该函数的 docstring 写的是"未覆盖的日子仍按工作日推定"，实现却是"缺一天就整段丢弃"，与说明不一致。

## 建议

已知的日子按日历回执判定，只有未覆盖的日子才按工作日推定，不要因为一天未知就丢掉已知的休市日。

## 验收草案

- [x] 替身：日历回执覆盖到 T，截止日为 T+1，窗口末日与 T 之间有长假；断言假期内不计交易日，日频指标判为 `current`。
- [x] 截止日完全在已存日历内时，行为不变。

## Comments

### 2026-10-09 分流

按 goal-round2.md 预设决定实施。

### 2026-10-09 实施

**复现（/diagnosing-bugs）**：替身回执覆盖 9-01..10-08、截止北京时间 10-09 06:39、目标日 09-30，`assess` 对三核心、DR007、两融、中间价等一律 `stale`、`periods_behind=5`，与 run-8a3779cff80f6bd586a0 一致；同一场景把回执延到 10-09 即正常。根因即票面所述：`judging_calendar` 用 `sessions_between` 要求窗口末日到截止日每天都已覆盖，缺一天就整段丢弃。

**改动**（`src/pring_cycle/trading_calendar.py`）：
- `SseCalendar.stated_between(first, last)`：返回区间内有回执覆盖的每一天是否开市（允许缺日）。
- `judging_calendar`：从窗口末日起沿已覆盖日连续延伸到第一个未覆盖日之前（`through`），其中的开市日计入；更远处回执仍说明休市的日子经新参数 `TradingCalendar(closed=...)` 保留为非交易日；只有无回执说明的日子按工作日推定。开市日超出连续覆盖段时不必单独保存——解析器已拒绝周末开市，工作日推定与之等价。
- `closed` 只参与 `is_trading`，不进入 `covers()` 的连续覆盖段，`sessions_to/from/back`、`stated_to` 等严格方法仍不跨越未知日。`judging_calendar`、`TradingCalendar`、`covers()` 的 docstring 与实现对齐。
- `SseCalendar.sessions_between` 保留（`worker.py` 仍用它做完整区间检查）。

**测试**（`tests/integration/test_holiday_freshness.py`，先红后绿，两个切片）：
1. 回执覆盖到国庆最后一天 10-07、截止 10-08 08:00：10-01..07 非交易日、10-08 按工作日推定，四个国内日频指标 `current`、落后 0 期（验收第 1 框）。
2. 回执覆盖到 10-08、截止 10-09 06:39（本次真实运行的情形）：结果与回执覆盖到截止日时相同，均为 `awaiting_release`、落后 0 期（修复前 `stale`/5）。
3. 回执覆盖 9-01..9-30 与 10-05..10-20、中间缺口：10-05..07 仍休市，缺口日按工作日推定，且不算"覆盖"。
4. 截止日在已存日历内：与旧实现构造的 `TradingCalendar(…, through=截止日)` 在 8-20 起 70 天内 `is_trading`、`covers` 逐日一致（验收第 2 框的独立基线）；既有国庆／中秋／外国市场用例全部不变通过。

**验证**：
- 受影响测试（引用 `TradingCalendar(`、`use_run_calendar`、`record_run_freshness`、`batch_freshness`、`judging` 的 21 个文件）：454 passed，1:09:51（远超 3 分钟目标；与其他线的 worktree 测试同时运行，最慢为 `test_full_run_retrieval`、`test_release_preannouncement` 单例 85–88 秒）。采纳审查意见后（仅 docstring 与测试）重装复跑 `test_holiday_freshness.py`＋`test_trading_calendar.py`：32 passed，13 秒。
- 两例冒烟：2 passed，3:09（同样有并行负载）。
- 未改 Worker 编排、指标目录或来源，未跑重型两例；按要求未跑 `check.py full`。
- `ruff check`、`ruff format --check`、`mypy`（改动的两个文件）通过。

**审查（Codex，各一轮）**：标准轴、规格轴均"阻断：无"。非阻断意见均已采纳：`covers()` docstring 改为"连续覆盖段"语义；第 2 个用例补上预期状态与落后期数，不只做两边比较；新增第 4 个用例，以旧实现的构造作独立基线证明"截止日在已存日历内行为不变"。规格轴提示：用例 1 的 `current` 依赖截止在 08:00（当日值尚未到更新时间），不代表 T+1 全天都是 `current`——这符合预期，T+1 当日值发布后按宽限判定。

**遗留**：本次真实运行中"缺口清单 36 项"的回落需在票 17 真实运行中核验。

