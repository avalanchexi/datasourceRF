Status: done
Category: bug
Type: task

# 02：日历解析器把应答里漏列的日子当作休市

## 现象
体检发现票 14 实施时指出：核心日历解析器不检查请求区间内每天是否都有一行；区间内没有列为开市的日子，一律当作休市。如果 TuShare 应答漏了某天（例如当天），调度会把它当成休市，不提交运行，也不重试，结果是漏跑一次。所有已存的日历回执都是这样读的。

## 待分流确认
上游应答是否真的会漏日；收紧为“开市、休市都必须列出”会影响多少取数路径和测试替身；修法候选。

## 验收

- [x] 先红后绿：应答漏列请求区间内某天（漏今天、漏中间日、漏上一交易日）时，视为日历覆盖不足，而不是休市；调度走补取／暂缓重试，不误判休市
- [x] 入口严格校验：请求区间内每个自然日恰有一行、开闭市标记合法（`source_adapters.py`）
- [x] 存量读取：从已存原件确认完整性后才认可覆盖（`trading_calendar.py`）；本库 32 份完整核心日历回执继续可用，不靠全局提升 `CORE_PARSER_VERSION`
- [x] 只返回工作日开市行的测试替身改为逐日列出（`test_core_history_refresh.py`、`test_context_acquisition_receipts.py`、`test_full_run_retrieval.py`、`test_worker_registered_catalog.py` 组合替身）；`tests/adapters/test_fixed_window_calendar.py` 的“周日开市”负例补齐周六
- [x] 完整应答下外部调用次数与选值不变
- [x] 与票 03（T+1 调度）联合验证：漏今天、漏上一交易日时的补取与暂缓
- [x] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

## 主要模块

`src/pring_cycle/source_adapters.py`（`_calendar_rows`，约 `:313-319`）、`src/pring_cycle/trading_calendar.py`（约 `:277`、`:310-313`）、上列测试替身；`worker.py` 的盘后调度由票 03 维护，本票尽量不动。

## Comments

### 2026-10-11 分流

取证：`codex exec -s read-only`（g2）。

1. **现象仍在（读码推断＋内存实测）**：`source_adapters.py:313` 的 `_calendar_rows` 只查重复、越界、周末开市、开市日非空，`:319` 只留开市日；`trading_calendar.py:313` 以 `is_open = day in sessions` 把区间内未列为开市的日子一律当休市。内存实测：“只返回 10-08 开市”与“10-08 开市、10-09 休市”解析结果相同。调度 `worker.py:248` 得到 `False` 后 `:210-212` 清空暂缓、不提交、不重试。
2. **没有真实漏日或漏跑的证据（实测）**：32 份核心日历成功回执逐份核对，请求天数与行数全部相等（合计 11,866 行＝7,927 开市＋3,939 休市），漏日 0；`scheduled_full` 运行数为 0。旧上下文 15 份 `trade_cal` 明确带 `is_open=1`，按核心解析版本筛选不会被当作核心日历读——票面“所有已存日历回执都这样读”不准确。
3. **影响面**：取数业务路径 5 条（调度补取、时效截止日补取、三核心历史、人工目标日判定、广度日历补取），`SseCalendar(...)` 读取 12 个调用点跨 6 个模块；可能传播到三核心预期日期、120 日窗口、广度、郑商所仓单日期与公式回看（读码推断，不能据此说现有结果有错）。体检独立实现不受此误读影响（`tools/quality/common.py:58、350、361`）。
4. **测试替身**：需改 4 条路径、5 个实现位置（见验收）；`test_worker_registered_catalog.py` 组合替身对 293 天只返回 289 行。
5. **修复候选**：入口严格校验＋存量原件完整性复核（推荐）；正常运行外部调用 +0；漏日时改为覆盖不足，调度按既有重试每次 1 次 `trade_cal`。`CONTEXT.md:142` 已规定只认开闭市完整的日历，**无需用户决定**。不要全局提升 `CORE_PARSER_VERSION`（它还参与核心价格原件身份校验，`source_adapters.py:50`）。
6. **去向**：`ready-for-agent`。与模型规则票 03 不重复（03 改触发时刻与目标日，本票保证日历依据可信），但同属日历与调度，排在线 B 的票 03 之后实施，并做联合验证。

### 2026-10-11 实施

线 B（worktree `worktree-agent-a58753515a2e2ccad`）。前任子代理做完 TDD 与两轮审查后被用户中途停止；接手的子代理在工作树上核对改动与第二轮审查一致，补做静态检查、存量回执实测、rebase 与复跑，然后收尾。

**改动**
- `source_adapters.py`：`_calendar_rows` 要求请求区间内每个自然日恰有一行、`is_open` 只认 0/1（数字或数字字符串）；有行但漏日报 `china_trading_calendar_incomplete`，空应答仍是 `missing`。新增 `calendar_sessions(raw, start, end)`，对已存原件按取数时同样的口径复核。
- `trading_calendar.py`：`SseCalendar` 只有在原件复核通过、且与规范化结果一致时才认可覆盖；复核不过的存量应答不提供任何一天的覆盖（这些天会重新取数），不一致的记入 `unreadable`。不提升 `CORE_PARSER_VERSION`。
- 测试替身改为逐日列出开市与休市：`test_core_history_refresh.historical_response`、`test_context_acquisition_receipts`、`test_full_run_retrieval`、`test_processing_batch`、`test_worker_registered_catalog` 组合替身（归档终点 20260828 之后逐日补齐）。`test_fixed_window_calendar` 的“周日开市”负例补上周六。`test_core_history_refresh.py` 顺带删掉 HEAD 上已有的两行多余空行（ruff format）。
- 新测试：适配器层覆盖漏今天、漏中间日、漏上一交易日、非法标记、数字字符串加乱序、空应答；存量层覆盖原件漏日不认可、与规范化不一致记 unreadable、原件缺失；调度层（票 03 的 09:00 触发入口）覆盖取到的日历漏今天、漏上一交易日或漏中间日时暂缓，恢复后重试，以及存量日历漏今天时重新取数而不是当作休市；判定日漏列按取数失败处理（`test_worker_calendar_gate`）。

**证据**
- 先红后绿：red 时 16 failed／23 passed，修复后全绿（前任 red.log、green1／green2）。
- 存量实测（只读，直接读运行库与原件）：`tushare-core-parser-v0002` 的已验证 `trade_cal` 回执 32 份，严格复核 32 份通过、0 份拒绝，规范化开市日与原件 32/32 一致。正常数据下选出的开市日不变。
- 完整应答下外部调用次数不变：原有断言调用次数与区间的测试，在逐日完整替身下全部照旧通过（如 `test_core_history_refresh.py` 的调用计数、`test_worker_execution` 的 `tushare.ranges` 与目标日断言）。
- 静态检查：rebase 前后各一次，对改动文件跑 `ruff check`、`ruff format --check` 通过，`mypy src/pring_cycle` 通过（127 个文件）。
- rebase main 后（main 带入票 01、残余 01、体检若干；无冲突）：专用 venv 重装；受影响测试 12 个文件，含 main 新增的 `test_core_window_history.py` 及 `test_attempt_classification.py`、`test_gap_source_repairs.py`，201 passed，用时 13m23s（超过 180s 目标，主要耗在 `test_worker_execution` 与 `test_worker_calendar_gate`）；两例冒烟 2 passed，48s；重型两例（flock，`python -m pytest`）4 passed，6m04s。rebase 后对改动文件复跑 ruff 与 mypy，均通过。

**审查**（`codex exec -s read-only`，两轴两轮）
- 第一轮规格轴有阻断：漏日时运行中的时效路径会按工作日回退。定性后撤回：漏日应答与 `OSError` 走同一条既有失败分支，并记录 outcome；工作日回退方向保守，而且不是本票新增；运行前调度的入口会暂缓并重试（ADR-0041）。第一轮小改：漏日检查提前，使有行但不全时报 `incomplete`；补字符串标记与乱序、空应答、原件与规范化不一致、判定日漏列等测试。
- 第二轮：标准轴“阻断：无”，规格轴“阻断：无”。
- 非阻断意见：`calendar_sessions` 的 docstring 去掉“只抛 ValueError”的承诺，已采纳。漏日且其余行全为休市时报 `incomplete` 而不报 `missing`，已采纳（漏日检查提前）。补字符串标记与乱序正例、规范化不一致、原件缺失等用例，已采纳。存量复核失败一律不认可覆盖、不区分格式损坏与漏日，不采纳：两种情况都应重新取数，原件缺失与哈希不符已单独记入 `unreadable`；第二轮审查认可。不另加 `ARCHIVE_END` 一致性断言，不采纳：已跟踪归档的请求终点确为 20260828，与常量一致；第二轮审查认可。

**遗留**（都是 HEAD 上原有的行为，本票不改）：
1. 运行中的时效截止日补取收到漏日应答时，记录 unavailable 后按工作日回退（`worker.py` `_reach_judging_day`、`trading_calendar.py` `judging_calendar`）。方向保守，可能多算应有期。是否改为阻断属于另一项领域决定。
2. 人工入口在“残缺存量被剔除且无 TuShare token”时同样回退到工作日（`freshness.py` 约 `:621`），第一轮规格审查建议单列跟踪。
