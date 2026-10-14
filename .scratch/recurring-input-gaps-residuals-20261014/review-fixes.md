# 集成分支审查修复（2026-10-14）

审查基点：`input-gap-residuals` `205ace3`；审查原文为两轴 Codex 结论（规格轴阻断 1 条，标准轴无阻断、判断题 2 条，均采纳）。分支：`worktree-agent-a90aac76b3ed04594`。票面状态未改。

| 项 | 处置 | 提交 |
|---|---|---|
| 规格阻断：次晨补取在日历不完整时把来源空应答当作已持有 | 已修（先红后绿） | `da92eac` |
| 标准判断题：`worker.py` P0 截止时刻拆分与构造重复 | 已收拢为 `_p0_deadline` | `9b7f6d0` |
| 标准判断题：`OfficialFile(BytesIO)` 响应桩在测试间重复 | 改为共用 `tests/conftest.py` 中的一份 | `9b7f6d0` |

## 1. 次晨空应答被误判为补取完成（票 08）

- **复现**：`tests/integration/test_usdcny_close_refresh.py::test_an_empty_morning_answer_is_asked_again_while_the_calendar_leaves_a_day_unstated`。已存日历只到周二、周二收盘价已持有；周四 08:00 文件停在周三 16:00（尚无收盘值），解析器返回空、记 `source_empty`、不抛异常。原实现在 `known` 为假时以 `held = not failed` 判定，本晨即记为完成，08:10 文件给出周三收盘价也不再请求。用例首跑红（第二次请求为 `False`）。
- **修复**：`fetch_close_if_due` 把来源的 `parse` 包一层（`dataclasses.replace`），记录文件在请求区间内实际给出的行。`known` 为假时改为 `held = bool(gave)`：只有文件给出收盘值才算完成；空应答与失败一样 10 分钟后重试，09:30 起不再取。`known` 为真时仍按 `holds(target)`。“周末未写明、周五已持有”时文件给出周五值（无新增）仍算一次完成，不会每 10 分钟重复请求。`refresh_quote_source` 的接口与记录口径均未改。

## 2. P0 截止时刻重复

- **复现**：`submit_schedule_if_due`、`fetch_close_if_due`、`_scheduled_p0_deadline_elapsed` 三处各自拆分 `schedule["p0_deadline"]` 并构造截止时刻（审查点名前两处）。
- **修复**：新增 `_p0_deadline(schedule, day)`，按计划时区构造当天截止时刻，三处共用。比较关系不变（21:00 本身仍在时限内；运行超时仍按提交日计算）。`tests/integration/test_worker_execution.py` 覆盖这三处。

## 3. 官方文件响应桩重复

- **复现**：`test_sox_quote_source.py`、`test_usdcny_close_refresh.py` 与更早的 `test_gap_source_repairs.py` 各有一份逐字相同的 `class OfficialFile(BytesIO)`。
- **修复**：移入 `tests/conftest.py`，放在 `install_runtime_clock` 之后；三个文件改为 `from tests.conftest import OfficialFile`。没有新建模块，桩的行为不变。

## 验证

- 受影响测试（rigfix venv，从本树重装）：`test_usdcny_close_refresh.py`（27）、`test_sox_quote_source.py`、`test_gap_source_repairs.py`、`tests/adapters/test_quote_sources.py`、`test_worker_execution.py`，共 105 例通过，用时 125 秒。
- 重型测试（`flock /tmp/pring-heavy.lock`）：`test_worker_registered_catalog.py` 与 `test_core_carry_forward.py`，4 例通过，用时 302 秒（在 9b7f6d0 上跑）。
- ruff：`ruff check` 通过，本次改动的文件 `ruff format` 无差异（ruff 0.16.5，与其他 rig venv 相同；仓库中另有 9 个文件格式不符，均为既有问题，与本次改动无关）。mypy：改动文件无新增错误，只有 `tests/conftest.py:22` 与 `test_gap_source_repairs.py:298` 两处既有错误。
- Codex 定向复审（`codex exec -s read-only`，只核对上述三项）：**阻断：无**。三项均确认已修复，语义等价。另提到新用例没有单独断言“10 分钟内不重试”，该守卫由现有用例 `test_a_failed_morning_make_up_is_asked_again_ten_minutes_later_but_not_from_0930` 覆盖。
