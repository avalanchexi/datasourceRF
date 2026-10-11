Status: ready-for-agent
Category: bug
Type: task

# 01：每次运行固定出现 12 条失败回执（fut_basic 8、fut_trade_cal 4，ContextObservationsMissingError）

## 现象
2026-10-09 以来，各次真实运行（`run-a1110cb8…`、`run-a04dcc78…`、`run-674411db…`、`run-8186b774…`）都有这 12 条失败回执，错误类型都是 `ContextObservationsMissingError`。历次验收都把它们记作“常规失败”，但从没查过原因。体检票 01 还发现，期货交易所日历引用的原件也出自状态为 failed 的回执。

## 待分流确认
是上游接口的正常空应答，还是取数参数或解析有缺陷；是否影响仓单、期货日历等下游；修法与外部调用次数。

## 验收

- [ ] 完整运行接缝上先红后绿：窗口已全部持有、上游应答为真实形状的 `fut_basic`／`fut_trade_cal` 时，12 张输入回执正常结束（不再 `failed`），新增声明为 0，旧值不变，指标尝试仍为 `succeeded / nothing_new`
- [ ] 保留反例：真实空日历（无有效篮子交易日）、结构错误、入库为空仍按现行规则失败
- [ ] 不按异常类批量改成功；同名异常的其他含义（`source_empty`）行为不变
- [ ] 每次运行外部调用次数不变（仍 8＋4）
- [ ] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

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
