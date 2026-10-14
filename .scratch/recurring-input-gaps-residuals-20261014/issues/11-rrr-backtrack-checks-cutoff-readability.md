Status: done
Category: bug
Type: task

# 11：降准回溯复核截止时可读性

**What to build:** 官方降准回溯只停在运行截止（未给时为目标日结束）时可读的声明上：找到的声明按其公开时间在截止时读不到，就跳过并继续往更早的期刊找；解析失败照旧停止；无声明照旧 `none_stated`。落实[来源票 06](06-rrr-lookback-cutoff-readability.md)；见[规格](../spec.md)“降准回溯”。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `backtrack_rrr_chronicle` 接缝新用例：较新期刊的声明截止时读不到 → 取到更早的可读声明
- [x] 原有“解析失败即停”“无声明”用例保持通过；受影响测试通过

## Comments

- 2026-10-14 领取：worktree 基于集成分支 `input-gap-residuals` `bb3f930`；venv `dev-venv-rig11`。接缝 `backtrack_rrr_chronicle`（规格指定）。
- 2026-10-14 红→绿切片完成：新用例 `test_a_cut_not_readable_by_the_run_s_cutoff_gives_way_to_an_older_one`（8-12 期刊正文发布时间改为 8-13 10:00；9:30 截止 → 取 2025-05-15、`covered_through` 3-31；10:30 截止 → 取 6-01）先红后绿。实现：回溯入库后按声明的**入库公开时间**（`effective_source_claim` 的公开时间，即正文发布时间，无则按登记规则推断）用 `SummaryCutoff(until, 截止).knows` 复核——与目标日汇总读声明同一规则；读不到就跳过该期，若该期是设定 `covered_through` 的最新一期则一并撤销其覆盖月份（截止时尚未读到），继续往更早的期刊找。

### 2026-10-14 实施

- **改了什么**：`backtrack_rrr_chronicle`（`src/pring_cycle/official_context.py`）在某期刊找到降准、入库后，新增 `_claims_known` 复核：取这些声明在 `effective_source_claim` 中的公开时间（正文发布时间；无则为登记规则推断值），按 `SummaryCutoff(until, public_as_of).knows` 判断，与目标日汇总（`TargetBoundEvidenceRepository`）读声明同一规则。读不到：不返回，继续往更早期刊找；若该期是设定 `covered_through` 的最新一期，一并撤销（截止时尚未读到它覆盖的月份，尾段交 AI WebSearch 检索）。解析失败照旧抛出停止；全无声明照旧返回空（`none_found`/`none_stated` 不变）。晚发期刊的声明仍入库（截止后的运行可读），只是不算本次回溯的结果。
- **测试**：`test_rrr_backtrack.py` 新增参数化用例（8-12 期刊正文发布时间改为 8-13 10:00，含 6-01 降准；9:30 截止取 2025-05-15、覆盖至 3-31；10:30 截止取 6-01、覆盖至 6-30），先红后绿。`dev-venv-rig11`：并入集成分支（`bb3f930`，无新提交）并重装后，受影响集合 `test_rrr_backtrack.py`＋`tests/adapters/test_rrr_context.py`＋两例冒烟 38 过（273 秒，超 180 秒目标：`test_rrr_backtrack.py` 是接缝本身，须全跑）。未跑重型：未改 Worker 编排、指标目录或来源。`ruff check`、`ruff format --check`、`mypy` 改动文件通过。
- **审查**：Codex 两轴各一次，均“阻断：无”。非阻断建议（补默认截止、恰等于截止、连续跳过多期、已有覆盖后跳过旧期刊等用例）不采纳：等于截止的边界是 `SummaryCutoff.knows` 的既有规则；多期跳过与本用例走同一分支；票面只要求一例。
- **遗留**：无声明的期刊仍只按栏目日期判断，不复核其正文发布时间（规格只要求复核找到的声明；若无声明期刊正文晚发，其覆盖月份仍计入 `covered_through`）。
