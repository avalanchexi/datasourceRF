Status: ready-for-agent
Category: task
Type: task

# 06：残余 01／02 的未处理部分

## 现象

(a) 残余 01：breadth 请求后行情为空时，指标尝试记为 `nothing_new` 而非 `source_empty`（既有分类问题）；候选 B：篮子窗口全持有时先取日历判定，12 次请求可降为 4 次。(b) 残余 02：运行中时效截止日补取遇到漏日应答时按工作日回退（方向保守，可能多算应有期）；人工入口在残缺存量被剔除且无 token 时同样回退工作日。是否改为阻断属领域决定。

## 来源

[残余 01](../residual-triage-20261011/issues/01-recurring-context-observation-failures.md)、[残余 02](../residual-triage-20261011/issues/02-calendar-parser-missing-day-read-as-closed.md) 遗留（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

1. **(a) breadth 尝试分类**：`breadth.py` 中实际发出取数后仍无可计算标量的分支，改抛 `ContextObservationsMissingError("source_empty")`；“无待取日期”的空返回仍为 `nothing_new`。只改尝试分类，不动回执（回执仍失败），外部调用 0。
2. **候选 B**（用户 2026-10-12 决定做）：篮子先取四所期货日历；只有四所日历逐日完整、且窗口已全持有时才走快路径返回（12→4 次请求）；日历漏日或失败时不得判“全持有”，退回原流程（先合约、再到期日前日历）。正常应答下选值不变；“全持有”判定不扩展到逐袖套完整性（若需要另开票）。
3. **(b) 日历回退**（用户 2026-10-12 决定保持回退）：运行中判定日日历补取失败或漏日、人工入口无 token 且存量不覆盖时，仍按工作日推定，但在缺口与报告中**醒目标注**“日历依据不足、按工作日推定，时效可能多算”。先核对现有缺口／报告是否已有此类标注，没有才补。

## 主要模块

`breadth.py`、`tushare_context.py`、`basket.py`、`worker.py`（`_reach_judging_day`）、`trading_calendar.py`、`freshness.py`、`context_projection.py`／`dashboard.py`／`reports.py`（标注呈现）；测试 `tests/integration/test_attempt_classification.py`、`tests/adapters/test_basket.py`、`tests/integration/test_gap_source_repairs.py`、`tests/integration/test_worker_calendar_gate.py`。

## 验收

- [ ] (a) 先有稳定变红的测试：请求后行情为空时尝试记为 `nothing_new`；修复后为 `source_empty`、回执仍失败；全持有无需新增时仍为 `nothing_new`
- [ ] 候选 B：全持有且四所日历完整时篮子只发 4 次请求（`fut_trade_cal`），选值与原流程逐字相同
- [ ] 候选 B：四所日历漏日或失败时不判全持有，行为与原流程一致；窗口有缺口时结果不变
- [ ] (b) 日历回退时，缺口与报告（或页面）出现醒目标注；完整日历时不出现
- [ ] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断
- [ ] 收尾验收（票 09）真实运行中篮子请求 12→4

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-02-06.md](../triage-codex-02-06.md) 第 12–25 条。

- (a) 现象在代码中仍在：`breadth.py:307`（无待取）与 `:335`（请求后无标量）都返回空元组，适配器统一抛 `nothing_new`（`tushare_context.py:1068`）。两次真实运行的 7 条 `nothing_new` 都是正常的“无需新增”，请求后为空的误分类实际 0 次。改为 `source_empty` 不改变缺口分类、重试与负缓存（都看 `outcome`，两者都是 `succeeded`），只修正“已全部持有，无需新增”的误导文案。
- 候选 B：两次运行篮子均为 `fut_basic` 8 次、`fut_trade_cal` 4 次（快照实测）；先取日历可降为 4 次。风险：期货日历当前只做日期范围检查（`basket.py:188`），四所共同漏列开市日可能误判全持有，所以快路径前须校验逐日完整。
- (b) 运行中漏日由 `worker.py:_reach_judging_day`（`:2104-2115`）记 `unavailable` 后继续，`trading_calendar.py:417-443` 对未覆盖部分按工作日推定；测试示例多算 5 期（`test_worker_calendar_gate.py:273-349`）。历史上只发生过 1 次（`run-766f5d61…` 的 SSL URLError，不是漏日）。人工入口触发条件为：未给 `--target-date`、存量不覆盖，且无 token（`cli.py:321`、`freshness.py:621-625`）。
- 决定：(a) 按预设做；候选 B 用户决定做并加日历完整性校验；(b) 用户决定保持回退并醒目标注。`ready-for-agent`，线 B 第二票（排在 02 之后）。
