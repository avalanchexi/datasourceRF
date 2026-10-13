Status: done
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

- [x] (a) 先有稳定变红的测试：请求后行情为空时尝试记为 `nothing_new`；修复后为 `source_empty`、回执仍失败；全持有无需新增时仍为 `nothing_new`
- [x] 候选 B：全持有且四所日历完整时篮子只发 4 次请求（`fut_trade_cal`），选值与原流程逐字相同
- [x] 候选 B：四所日历漏日或失败时不判全持有，行为与原流程一致；窗口有缺口时结果不变
- [x] (b) 日历回退时，缺口与报告（或页面）出现醒目标注；完整日历时不出现
- [x] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断
- [ ] 收尾验收（票 09）真实运行中篮子请求 12→4

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-02-06.md](../triage-codex-02-06.md) 第 12–25 条。

- (a) 现象在代码中仍在：`breadth.py:307`（无待取）与 `:335`（请求后无标量）都返回空元组，适配器统一抛 `nothing_new`（`tushare_context.py:1068`）。两次真实运行的 7 条 `nothing_new` 都是正常的“无需新增”，请求后为空的误分类实际 0 次。改为 `source_empty` 不改变缺口分类、重试与负缓存（都看 `outcome`，两者都是 `succeeded`），只修正“已全部持有，无需新增”的误导文案。
- 候选 B：两次运行篮子均为 `fut_basic` 8 次、`fut_trade_cal` 4 次（快照实测）；先取日历可降为 4 次。风险：期货日历当前只做日期范围检查（`basket.py:188`），四所共同漏列开市日可能误判全持有，所以快路径前须校验逐日完整。
- (b) 运行中漏日由 `worker.py:_reach_judging_day`（`:2104-2115`）记 `unavailable` 后继续，`trading_calendar.py:417-443` 对未覆盖部分按工作日推定；测试示例多算 5 期（`test_worker_calendar_gate.py:273-349`）。历史上只发生过 1 次（`run-766f5d61…` 的 SSL URLError，不是漏日）。人工入口触发条件为：未给 `--target-date`、存量不覆盖，且无 token（`cli.py:321`、`freshness.py:621-625`）。
- 决定：(a) 按预设做；候选 B 用户决定做并加日历完整性校验；(b) 用户决定保持回退并醒目标注。`ready-for-agent`，线 B 第二票（排在 02 之后）。

### 2026-10-13 实施进展（fub-06，分支 `worktree-agent-a5e806d126dc436fa`）

- 10-13 09:28 (a) 红测试稳定：`test_attempt_classification.py::test_breadth_s_empty_quotes_for_a_day_not_held_still_fail` 断言 `'nothing_new' == 'source_empty'` 失败；新增 `test_breadth_with_every_day_held_asks_nothing_and_has_nothing_new`（全持有仍为 `nothing_new`、不发请求）。实现：`breadth.py` 请求后无标量抛 `source_empty`；转绿，`test_attempt_classification.py`＋`tests/adapters/test_breadth.py` 36 passed。(b) 现状核对已交 Codex 只读（`/tmp/fub06/codex-b.txt`）。
- 10-13 09:35 候选 B 红测试 5 例（`tests/adapters/test_basket.py` 新增：全持有只发 4 次日历；四所/一所漏日不判全持有并退回原流程；首份日历失败退回原流程；窗口有缺口时选值与原流程相同）均红。实现：`basket.py` 新增 `_window_held`（四所 `fut_trade_cal` 基准日至目标日，逐日恰好一行、`is_open` 为 0/1 才可判全持有；失败或漏日即停、走原流程）。同步改 3 处旧断言（12→4 次、`contract_refused` 改为留一日缺口以读到合约）。`test_basket.py`＋`test_attempt_classification.py` 32 passed，`test_gap_source_repairs.py` 9 passed（94 秒）。
- 10-13 09:38 (b) 现状核对结论（Codex）：判定日日历补取失败只在 `full_run_gap_plan` 的 `judging_calendar.fetches[].outcome` 记 `unavailable:…`；缺口清单、投影 `cycle_overview`、报告 `freshness_basis` 与页面均无“日历依据不足／按工作日推定”的标注；人工入口选日依据不入运行记录。需补。
- 10-13 09:42 (b) 红测试：`test_worker_calendar_gate.py` 两例回退（取数失败、应答漏日）新增断言投影 `cycle_overview.freshness_calendar`、报告 `freshness_basis.calendar`、首页与报告页出现标注，稳定变红；三例完整日历断言不出现（原即通过）。`test_freshness_contract.py` 新增人工入口无日历无 token 时 CLI 输出 `target_selection`，变红（KeyError）。实现：`freshness.judging_calendar_basis`＋`CALENDAR_FALLBACK_NOTE`；Worker 经 `RunMaterials.freshness_calendar` → `P0ProjectionService.publish`（仅回退时写入 `cycle_overview` 与身份文档）→ 报告 `results.freshness_calendar` 与骨架 `freshness_basis.calendar`（含文案）→ 页面缺口区与报告阅读页 `warning-label` 标注；CLI `run-submit` 回退选日时输出 `target_selection`。两文件转绿（10 passed 80 秒；26 passed）。
- 10-13 09:55 受影响测试（确认、回溯、日汇总、缺口、报告、页面、P0、交易日历、Worker 执行等 23 个文件）577 passed，647 秒（日志 `/tmp/fub06/affected-1.log`）。ruff check／format、mypy（改动的 10 个源文件）通过。下一步：冒烟、重型两例。
- 10-13 10:00 冒烟两例＋相关文件 61 passed（52 秒）；重型两例（`flock`）4 passed，326 秒（`/tmp/fub06/heavy.log`）。
- 10-13 10:03 Codex 两轴第 1 轮：规格轴无阻断（`/tmp/fub06/review-spec-r1.txt`）；标准轴 1 处阻断——`_window_held` 捕获 `OSError, ValueError` 过宽，会吞掉本地落盘失败（`/tmp/fub06/review-standards-r1.txt`）。已修：按 `capture_failure` 分类，只在 `source_failed`／`structure_rejected` 时回退，`start`／`store`／`normalize` 原样上抛。
- 10-13 10:06 标准轴第 2 轮无阻断（`/tmp/fub06/review-standards-r2-out.txt`）；按其建议补强测试（首份日历按环节失败：上抛 3 例、回退 3 例），`test_basket.py` 26 passed。

### 2026-10-13 实施

**改了什么**

- (a) `breadth.py`：实际取数后仍无标量时抛 `ContextObservationsMissingError("source_empty")`；无待取日期仍空返回，由适配器记 `nothing_new`（`tushare_context.py` 注释同步）。回执照旧失败，外部调用 0 增量。
- 候选 B `basket.py`：新增 `_window_held`，先取四所 `fut_trade_cal`（基准日至目标日）；每所须逐日恰好一行、交易所相符、`is_open` 为 0/1，且窗口篮子日全部持有才返回空（12→4 次）。任一所漏日、重复、异常值或来源失败／应答被拒即停（不再取其余各所），退回原流程（8 次合约＋4 次到期日前日历）；本系统落盘失败或未发请求则上抛。选合约、复利与袖套计算未改；“全持有”仍只看篮子 level，未扩展到逐袖套。
- (b) 现状核对：判定日日历补取失败或漏日只在 `full_run_gap_plan.judging_calendar.fetches[].outcome` 记 `unavailable:…`，缺口区、报告、页面都没有标注，所以补上：`freshness.judging_calendar_basis`（判定日不在日历覆盖内即 `weekday_inferred`）→ Worker `RunMaterials.freshness_calendar` → `P0ProjectionService.publish`（只在回退时写入身份文档与 `cycle_overview.freshness_calendar`）→ 报告 `results.freshness_calendar`（AI 输入可见）与骨架 `freshness_basis.calendar`（含文案 `CALENDAR_FALLBACK_NOTE`，AI 与确定性报告共用）→ 首页缺口区与报告阅读页顶部 `warning-label calendar-fallback` 醒目标注“日历依据不足、按工作日推定，时效可能多算”。日历完整时不写字段、不显示；旧投影缺字段照常读取。
- 人工入口：`cli.py run-submit` 未给目标日且日历不覆盖启动日（无存量且无 token）时，返回文档附 `target_selection`（`basis: weekday_inferred` 与文案）。运行本身若判定日仍无日历，由上面的运行级标注覆盖。

**测试与耗时**：受影响 23 个文件 577 passed（647 秒）；`test_worker_calendar_gate.py` 10 passed（80 秒）；`test_gap_source_repairs.py` 9 passed（94 秒）；冒烟两例＋相关 61 passed（52 秒）；重型两例 4 passed（326 秒）；改动文件 ruff check／format、mypy（10 个源文件）通过。改了 4 处旧断言：全持有篮子 12→4 次（`test_attempt_classification.py` 两处、`test_gap_source_repairs.py` 一处）；`contract_refused` 留一日缺口才会读到合约。

**审查**：规格轴第 1 轮无阻断；标准轴第 1 轮 1 阻断（异常捕获过宽），修后第 2 轮无阻断。

**非阻断意见与处理**

- 已采纳：漏日用例给出明确预期；补重复日／异常开闭值／他所行用例；页面断言检查警示类；`judging_calendar_basis` 文档写明输入前提；`p0.py` 注释改为“缺字段即未声明”；首份日历按环节失败的上抛／回退用例。
- 不采纳，记为已知差异：① 回退时比原流程多 1–4 次预检日历请求，已解析的预检回执也会随篮子标量链接为输入，失败请求留有记录。所以“与原流程一致”指的是退出快路径、走原流程、计算结果相同，不是请求与证据链接逐字相同（分流取证第 17 条已说明这项成本）。② 回退后的原流程照旧宽松接受日历（四所共同漏日时仍可能读成无此日），本票只保证不凭残缺日历走快路径。③ 人工入口的选日依据只在 CLI 输出中，没有进运行记录；持久化要改提交事务或加记录相（Codex 建议 `full_run_gap_plan` 加 `target_selection` 相），超出本票的“醒目标注”范围，如需要另开票。④ 页面断言是两个字符串分别查找，没有逐节点定位。

**遗留**：验收最后一框（票 09 真实运行篮子请求 12→4）待收尾验收取证。本票没有改 `spec.md`。
