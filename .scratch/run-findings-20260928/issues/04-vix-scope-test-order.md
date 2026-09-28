Status: done
Category: bug
Type: task

# 04 — VIX 检索范围用例只在全套里失败

## 原始发现

- 全套（`18899cf`）中，`tests/integration/test_full_run_retrieval.py::test_full_run_plans_the_latest_released_period_of_a_metric_not_held` 在最后一条断言失败：检索范围里出现了 `full:cboe_vix_index:2026-09-22`（ADR-0029 规定 VIX 从 Cboe 文件读取，不检索）。
- 单独运行这个用例能通过。9/26 的全套（`9d230f9`）里它也是通过的。
- 真实运行 `run-dc0bb2d9db7068bf552d` 的检索计划里没有 VIX 范围，所以生产行为正常。

## 待决定

- 找出全套中是哪个先跑的用例留下了状态（模块级缓存、没有还原的补丁、共用的运行库等）。可能与今天新增的 `czce_warrants` 补丁或按品种取数的改动有关。

## 诊断记录（2026-09-28）

> *本段由 AI 在诊断时生成。*

**结论：不是用例之间的串扰，而是这条用例真实访问了 Cboe。** `tests/conftest.py` 的会话级离线默认挡住了中证、统计局、官方页面和郑商所，但漏了 `pring_cycle.quote_sources.open_no_redirects`；这条用例又没有自带 Cboe 替身。全套在 9/28 上午跑到它时，真实请求 `cdn-api.cboe.com` 失败，VIX 没取到，于是和其他缺数指标一样进入检索范围。生产行为没有问题：检索范围本来就按"缺什么列什么"生成，SOX 这类不检索的指标同样会进入范围，是否真的去检索由 `retrieval.py` 的 `NO_SEARCHABLE_SOURCE` 决定。

**排除过程**（HEAD `7461b1a`，重装 dev-venv 后）：

| 尝试 | 结果 |
|---|---|
| 单独运行 | 通过 |
| 整个文件（28 例） | 全过，23 分 48 秒 |
| 全套中排在前面的 51 个其他文件，加目标用例（528 例） | 全过，16 分 20 秒 |
| 用 time-machine 把时钟拨到失败时的 UTC 03:48 | 通过 |
| 全套前 551 例按原顺序，并把时钟拨到开跑时刻 UTC 03:10:53 | 全过，37 分 06 秒 |
| **把代理指向不可达端口（相当于断网）后单独运行** | **3/3 失败，与原症状一致，约 6 秒** |

**修复：**

- `tests/conftest.py`：会话级离线默认加上 `pring_cycle.quote_sources.open_no_redirects`。Cboe 和中国货币网 16:30 收盘价的文件，只有测试自己提供时才能取到。加上后，目标用例联网也稳定失败，这就是回归锁。
- 目标用例用 `tests/fixtures/quote_sources/VIX_History-20260925.csv`（数据到 9/22）提供 Cboe 文件。联网和断网都通过。

**同类遗留：** 这条用例联网要 30 秒，断网只要 6.5 秒，说明还有别的来源（EIA、ECB 等 `open_no_redirects` 取数）在测试里真实访问外网，只是目前没有断言依赖它们的结果。它们还没有加进会话级离线默认；是否要加、加了会影响哪些用例，另开票评估。

**验证：** 受影响测试 79 例全过（`test_full_run_retrieval.py`、`test_gap_source_repairs.py`、`test_warrant_symbol_isolation.py`、`test_worker_execution.py`、`test_worker_registered_catalog.py`、`test_core_carry_forward.py`、冒烟 `test_manual_run_cannot_backdate_daily_core_availability`），用时 32 分 31 秒。
