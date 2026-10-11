Status: done
Category: bug
Type: task

# 01：每次运行固定出现 12 条失败回执（fut_basic 8、fut_trade_cal 4，ContextObservationsMissingError）

## 现象
2026-10-09 以来，各次真实运行（`run-a1110cb8…`、`run-a04dcc78…`、`run-674411db…`、`run-8186b774…`）都有这 12 条失败回执，错误类型都是 `ContextObservationsMissingError`。历次验收都把它们记作“常规失败”，但从没查过原因。体检票 01 还发现，期货交易所日历引用的原件也出自状态为 failed 的回执。

## 待分流确认
是上游接口的正常空应答，还是取数参数或解析有缺陷；是否影响仓单、期货日历等下游；修法与外部调用次数。

## 验收

- [x] 完整运行接缝上先红后绿：窗口已全部持有、上游应答为真实形状的 `fut_basic`／`fut_trade_cal` 时，12 张输入回执正常结束（不再 `failed`），新增声明为 0，旧值不变，指标尝试仍为 `succeeded / nothing_new`
- [x] 保留反例：真实空日历（无有效篮子交易日）、结构错误、入库为空仍按现行规则失败
- [x] 不按异常类批量改成功；同名异常的其他含义（`source_empty`）行为不变
- [x] 每次运行外部调用次数不变（仍 8＋4）
- [x] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

## 主要模块

`src/pring_cycle/tushare_context.py`（篮子返回契约与 `acquire_scalars` 收尾，约 `:441`、`:1057`）、`src/pring_cycle/basket.py`（只读参照）、`tests/integration/test_attempt_classification.py`、篮子替身（`tests/adapters/test_basket.py`、`tests/integration/test_gap_source_repairs.py`）。

## Comments

### 2026-10-11 分流

取证：`codex exec -s read-only`（g1），主 agent 复核了第 2、7 条。

1. **结论：不是上游正常空应答，而是误标缺陷。** 目标运行的 12 份上游应答全部非空、哈希吻合（实测，历史同类 132 份 44,615 行）。篮子窗口 120 日已全部持有时，`basket.py:200-202` 返回空元组，`tushare_context.py:1057` 抛 `ContextObservationsMissingError("nothing_new")`，外层 `tushare_context.py:441` 不分情况对全部回执 `fail_validation`（`acquisition.py:504` 写成 `failed`），随后 `:443` 又把指标尝试记为成功——两套记录自相矛盾。
2. **票面“每次固定失败”不准确**（主 agent 复核属实）：`run-674411db…` 的 12 张全部 `validated`（该次新增了 10-08、10-09 篮子数据）；同类失败最早见于 10-03 的 `run-cfb8d121…`。截至 `run-8186b774…` 共 23 次带完整 8＋4 回执的运行：11 次全被误标，12 次全通过——规律是“有无新增”，不是“每次”。
3. **请求参数**：`fut_basic` 8 次（SHFE CU/RB/RU/SP、DCE PP、CZCE CF/TA、INE SC，`fut_type=1`，无日期）；`fut_trade_cal` 4 次（四所，起 20260306，止为目标日与最远到期日较晚者）。各参数组合均为“11 误标＋12 通过”，没有另一套触发参数。
4. **下游**：期货日历确实取自 failed 回执原件，但四所窗口 120 开市日、0 未覆盖，没有用错日历；仓单生产路径不依赖这 12 张回执（`CN_FUTURES_WARRANTS` 关联为 0，目标运行 42 张 `fut_wsr` 全部 validated）。受影响面是回执真实性、失败统计与排障解释；篮子、袖套 `batch_freshness` 均 `current`，正式阶段不受影响。
5. **测试漏点**：`tests/integration/test_attempt_classification.py:162` 的替身直接抛 `nothing_new`，没有先产生回执，发现不了回执误标。
6. **修复候选**：A（推荐、本票范围）改 `tushare_context.py` 收尾，“无需新增”时已通过输入检查的回执正常完成，外部调用 +0，选值与口径不变，无需用户决定；B（成本优化，不在本票）先取日历判定全持有再取合约，全持有时 12→4 次——另议，不能替代 A。
7. **去向**：`ready-for-agent`，按候选 A 实施。与票 02（日历漏日）不重复。模块不与线 A、B 重叠，另开线 E（worktree）。

### 2026-10-11 实施

- **改动**：`src/pring_cycle/tushare_context.py` 新增 `ContextObservationsMissingError` 的子类 `WindowAlreadyHeld`（`completeness` 仍为 `nothing_new`），只由 `ex_hog_basket` 在 `basket_scalars` 返回空时抛出。`acquire_scalars` 只捕获这个子类，把已收到的回执按“已通过检查、无值入库”收尾：`complete_validation(..., [], normalized_scalars=0)`，再 `record_ingest_result(None)`，结果为 `validated / passed / accepted`、计数 0，与 `quote_sources.py` 的 nothing_new 先例一致。随后照旧抛出，指标尝试仍为 `succeeded / nothing_new`。收尾前把 `stage` 置为 `store`，收尾写入失败归为 `local_failed`。外部调用不变。
- **为什么不按 completeness 判断**：第一轮规格轴审查指出，breadth 在请求了未持有日的 `stock_basic`／`daily`／`stk_factor_pro` 后、行情为空时，同样抛普通 `nothing_new`，那并不是窗口全持有。所以改成只有篮子明确声明，breadth 回执照旧 failed。篮子在发出请求后返回空只有一种可能，即其日历给出的窗口已全部持有：无法计算的请求日会抛出原因，无篮子交易日抛 `source_empty`。第二轮 Codex 逐分支核实了这一点。
- **测试**：
  - 完整运行接缝：`tests/integration/test_gap_source_repairs.py::test_the_basket_s_inputs_end_checked_when_its_window_is_all_held`。在首次运行的运行库副本上，对同一目标日再跑一次手动完整运行，断言 12 张回执为 `validated/passed/accepted`、无 `fut_daily`、篮子与袖套整窗值及声明数不变、尝试为 `succeeded/nothing_new`。修复前稳定变红（12 张为 `failed`）。
  - 上下文取数接缝：`tests/integration/test_attempt_classification.py` 新增五个用例：全持有正例（外部请求精确为 8＋4）；反例“无篮子交易日”“合约结构错误”，回执仍 failed；breadth 空行情反例，在第一版修复上变红、终版变绿；收尾写入失败的注入测试（`local_failed`）。
  - 结果：rebase 到 `bad2c85` 后，受影响测试与两例冒烟共 431 passed（26:45，含 `test_lookback_declaration`、`test_registered_model_inputs` 与官方回退各文件）；末次小改后 4 个直接文件 56 passed（2:07）；重型两例 `test_worker_registered_catalog.py`＋`test_core_carry_forward.py` 经 flock，4 passed（6:20）。ruff check、ruff format --check、mypy（改动的源文件）通过。再次 rebase 到 `37b24e0`（含线 A 改动的 `worker.py`）后复跑：直接文件、上下文回执与计数、`test_worker_reviewed_context`、两例冒烟共 113 passed（3:31）；重型两例 4 passed（6:38）。
- **审查**（Codex 两轴）：第一轮标准轴阻断 1 项（二次运行夹具污染共享运行库，改为在副本上运行），规格轴阻断 1 项（breadth 误收尾，改为专用子类）。第二轮两轴均“阻断：无”。采纳了非阻断建议“补收尾失败注入测试”，并把篮子注释的措辞收窄为“日历给出的窗口”。
- **遗留**（不在本票范围）：
  1. 规格轴指出：四所日历都漏列某个开市日时，该日不进入窗口，篮子会把“全持有”判为成立。这是日历覆盖问题，与残余 02（日历漏日）同源，本票不改窗口构造。
  2. breadth 请求后行情为空时，指标尝试被记成 `nothing_new`，而不是 `source_empty`。这是既有分类问题，本票只保证其回执不被误改为成功；是否另开票由主 agent 定。
  3. 候选 B（全持有时 12→4 次请求）照分流记录另议。
