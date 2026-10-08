Status: done
Category: bug
Type: task

# 10：L01 后的回归——同日第三次运行三核心预热未读入；受影响测试变慢

## 现象（L08 在 rebase 到含 L01 的 main 后发现，2026-10-08）

1. `tests/integration/test_retention.py` 中 L08 新增的核心用例：同一目标日**连续第三次**运行时，三核心都变成 `insufficient_history`，模型输入只剩窗口内 120 条，本轮取到的预热没有读进来。rebase 前（基于 130a337，不含 L01 `aa46a60`）同一用例通过；把 `retention.py` 换回 main 版复跑，结果相同——疑为 L01 引入。L08 已把该用例的"已知代价"断言移到第一轮之后，未修此问题（见 [L08 票面](08-pre-window-lookback-claims-untraceable.md) 实施记录）。
2. 受影响测试耗时从约 423 秒变为约 1287 秒；L01 自报冒烟从约 41 秒变为约 238 秒。L01 票面"残余风险"：历史期放行后 PMI、CPI/PPI、M1/M2、社融、GDP 每个历史期再按期请求 TuShare，受分钟限额等待。

## 要做的事

- 用二分或对照（130a337 与 aa46a60）复现并定位现象 1 的根因，先写会失败的回归测试（同一目标日连续三次运行，三核心历史充足），再修复。核心趋势计算逻辑本身不得改变（L08 方案 B 的约束）。
- 核实现象 2 的来源：是测试替身里的限频真实等待，还是生产路径多出的请求。生产上新增请求属于 L01 的既定行为；若只是测试替身等待，按仓库惯例让离线测试不真实 sleep。若涉及"历史期要不要再请求 TuShare"的取舍（与 L03 相关），按推荐方案实现并标 needs-info。

## 验收

- [x] 回归测试：同一目标日连续三次运行，三核心不出现 `insufficient_history`（修复前红、修复后绿）；L08 的已知代价断言可恢复到原位置。
- [x] 受影响测试与冒烟耗时回到 L01 前的量级，或在票面写明不可避免的原因。
- [x] 受影响测试、冒烟、重型两例通过；Codex 两轴审查无阻断。

## Comments

### 2026-10-08 追加现象 3（L04 发现）

`tests/integration/test_gap_source_repairs.py::test_the_basket_is_chained_from_its_base_on_settlements` 在 HEAD 源码上失败、在 130a337（L01 前）源码上通过：断言篮子与板块贡献不应出现在缺口里，现在出现了。疑同为 L01（aa46a60）引入，一并定位修复。

### 2026-10-09 实施（worktree 分支）

**根因**

- 现象 1 不在生产代码，在测试替身。`tests/conftest.py` 原 `quota_pacing` 把 TuShare 分钟限额的等待改为 skip，并把跳过的时长加到回执时钟 `pring_cycle.acquisition.datetime` 上。三核心入库的可用时钟却是未打补丁的 `datetime.now(UTC)`（`core_history.py:220`）。skip 累积后，回执的 `validated_at` 晚于这个时钟，`evidence.py:637` 抛 `acquisition_availability_time_invalid`，三核心整批拒收，模型输入只剩窗口内 120 条。L01 让每轮多出几十次 `sf_month` 等调用，超过分钟额度才开始 skip，所以 L01 后才暴露。第一轮总能入库，因为每个用例的 skip 从 0 开始；同一用例里再跑一轮就会失败。
- 对照（L08 版 `retention.py` 与用例，断言恢复到循环后）：130a337 通过，第四轮后 skipped 约 2 秒，模型输入 480 条；aa46a60 失败，skipped 约 85 秒，三核心状态为空，模型输入 360 条，核心回执 `ingest_rejection_reason=acquisition_availability_time_invalid`。
- 现象 2 主要也在替身：① 模块级夹具（`test_retention.py` 的 `pruned`、`test_gap_source_repairs.py` 的 `completed` 等）先于函数级 autouse `quota_pacing` 建立，其中的完整运行用真实 `time.sleep` 等分钟额度（`pruned` 建立 290 秒，篮子用例建立 466 秒，用户态只占 85 秒）；② 自设回执时钟的用例（冒烟的 `StableDateTime`）里，skip 只推进被替换掉的那个时钟，`admit` 一直空转到真实一分钟过去。
- 现象 3：L01 起，被门禁跳过的 scope 一律记 `release_gate` 并进缺口清单。日窗口 `whole_window` 要求篮子与板块贡献在 120 个交易日都有值，但篮子从 `BASE_DATE`（2026-03-06）之后才有值，于是测试日历替身上的 02-17..03-06 共 14 期以 `earlier_session_not_searched` 进了缺口清单。改前同样不完整，只是不显示。

**修复**

- `tushare_quota.Pacing.now()` 加上 `skipped`（生产中恒为 0）：只推进限额自己的时钟，回执和其他业务时钟不动。
- `tests/conftest.py`：`_clock_datetime` 不再加 skipped；`quota_pacing` 不再替换回执时钟；新增模块级 autouse `_module_quota_pacing`，模块级夹具里的等待同样跳过。
- `full_retrieval.py`：计划只要求篮子两指标在 `BASE_DATE` 之后的交易日；之后各期的完整性检查不变。
- `test_tushare_news.py` 中用 `skip(一天)` 模拟次日的用例改为 `install_runtime_clock` 整体换到一天后，让次日调用计入次日额度（审查阻断，见下）。
- `docs/agents/testing.md` 补一条说明。核心趋势计算未改。

**回归测试**

- `test_retention.py`：已知代价断言恢复到循环后（b38f209 的原位置）；每轮断言三核心状态与首轮一致，并断言首轮三核心都有状态。改前红（3c0ccf8 记录的现象，本次在 HEAD 复现：第四轮失败），改后绿。
- `test_tushare_call_quota.py` 新增三条：模块夹具的等待不真实 sleep；skip 后核心仍能入库；测试自设回执时钟时不空转。改前三条都红（共 670 秒，含真实等待），改后绿。
- 现象 3 的回归测试就是 `test_the_basket_is_chained_from_its_base_on_settlements`：改前红，改后绿。

**测试与耗时**（独立 venv `dev-venv-l10`）

- 改后、rebase 前：
  - L08 那组受影响测试 58 passed，930 秒（L08 记 423 秒，L01 后 1287 秒；部分时段与 Codex 审查并行）。
  - 冒烟两例 2 passed，131 秒（L01 前 41 秒，L01 后 238 秒）。
  - 篮子、限额、计划、缺口等 8 个文件 196 passed，1316 秒。
  - 7 个模块级夹具文件 68 passed，346 秒。
- rebase 到 main（含 L04、L03）后：
  - 受影响 6 个文件（含 L03 新增的 `test_targeted_monthly_refetch.py`、`test_ai_websearch.py`）76 passed，733 秒。
  - 冒烟 2 passed，130 秒。
  - 重型两例（flock 排队）4 passed，578 秒：完整目录正例 314＋135 秒，三核心反例 69＋59 秒。
- 改动的源文件 `ruff check`、`ruff format --check`、`mypy` 通过；测试文件 ruff 通过。

**耗时为何没回到 L01 前**（不可避免，属 L01 既定行为）：剖析冒烟 `core_history` 用例（81 秒，用户态 54 秒），已经没有 sleep，时间都花在生产路径的 CPU 和 SQLite 上。

- `retrieve` 共 58 秒：历史期放行后有 746 个检索级联（local、资讯、官方、搜索各渠道离线逐一失败），每轮另记 2232 条 `earlier_session_not_searched` 门禁尝试，`record_retrieval_attempt` 共 7628 次，23 秒。
- `RunRepository.get` 每次都重读全部尝试（`runs.py:1027`），调用 774 次，19.5 秒，随尝试数近似平方增长。

是否让历史期走完整级联与 L03、用户取舍相关，本票不改生产请求策略，所以不标 needs-info。`runs.get` 的重复读取可另开票优化。

**审查**（Codex 两轴）

- 第一轮规格轴"阻断：无"。
- 第一轮标准轴阻断 1 条：资讯用例 `skip(一天)` 改后只推进限额时钟，次日调用仍记在原日，日额度断言被绕过。已改为整体换时间轴，定向复审"阻断：无"。
- 采纳的非阻断意见：`_skipping_pacing` docstring 如实说明普通测试不再保持分钟速率；首轮三核心状态断言；testing.md 说明加"默认夹具下"限定。
- 未采纳"篮子基日后缺一天仍列缺口"的反例。过滤只去掉 `BASE_DATE` 及以前的期，之后各期仍走原有 whole_window 检查；为此再建一次完整运行夹具成本高，收益有限。

**已知残余**

- 默认替身下，skip 一次后限额时钟领先，后续调用落在分钟窗口外，普通离线测试实际不再模拟分钟限频。精确限频由 timeline 专测。
- 本票调查时在共享 scratchpad 根目录写过同名 `review-std.txt`、`review-spec.txt`，可能覆盖了其他票当时的审查提示词；本票文件已移到 `scratchpad/l10/`。
