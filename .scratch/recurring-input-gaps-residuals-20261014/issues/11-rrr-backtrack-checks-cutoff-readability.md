Status: claimed
Category: bug
Type: task

# 11：降准回溯复核截止时可读性

**What to build:** 官方降准回溯只停在运行截止（未给时为目标日结束）时可读的声明上：找到的声明按其公开时间在截止时读不到，就跳过并继续往更早的期刊找；解析失败照旧停止；无声明照旧 `none_stated`。落实[来源票 06](06-rrr-lookback-cutoff-readability.md)；见[规格](../spec.md)“降准回溯”。

**Blocked by:** None (can start immediately)

**Status:** claimed

- [ ] `backtrack_rrr_chronicle` 接缝新用例：较新期刊的声明截止时读不到 → 取到更早的可读声明
- [ ] 原有“解析失败即停”“无声明”用例保持通过；受影响测试通过

## Comments

- 2026-10-14 领取：worktree 基于集成分支 `input-gap-residuals` `bb3f930`；venv `dev-venv-rig11`。接缝 `backtrack_rrr_chronicle`（规格指定）。
- 2026-10-14 红→绿切片完成：新用例 `test_a_cut_not_readable_by_the_run_s_cutoff_gives_way_to_an_older_one`（8-12 期刊正文发布时间改为 8-13 10:00；9:30 截止 → 取 2025-05-15、`covered_through` 3-31；10:30 截止 → 取 6-01）先红后绿。实现：回溯入库后按声明的**入库公开时间**（`effective_source_claim` 的公开时间，即正文发布时间，无则按登记规则推断）用 `SummaryCutoff(until, 截止).knows` 复核——与目标日汇总读声明同一规则；读不到就跳过该期，若该期是设定 `covered_through` 的最新一期则一并撤销其覆盖月份（截止时尚未读到），继续往更早的期刊找。
