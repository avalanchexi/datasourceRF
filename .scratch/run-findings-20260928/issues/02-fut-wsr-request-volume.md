Status: needs-triage
Category: bug
Type: task

# 02 — 按品种逐日取 `fut_wsr` 请求量过大，缺日

## 原始发现

- 20260926 票 01 改成按品种单独取以后，6 个 TuShare 品种在 120 日窗口里逐日请求，约 720 次。
- 本轮 `fut_wsr` 失败 62 张：20 张是时钟问题（票 01），**42 张没有收到应答**（`received_at` 为空，没有原因码），分布在 6 个品种和各个日期上。疑似触发 TuShare 限频。
- 结果：CU 持有 110/120 天，PP、RB、RU、SC、SP 各 119/120 天（7/21 五个品种都缺）。20260926 票 01 的最后一条验收因此未达成。

## 待决定

- 先确认 42 次没有应答的原因（限频、超时还是别的），并让失败回执记下原因码。
- 取数单位：继续按品种逐日取，还是按日取整族、入库时再按品种隔离（请求数降到约 120 次）。

## Comments

> *本段由 AI 在分流时生成。*

### 调查结论（2026-09-28，[Codex 报告](../research/codex-fut-wsr-failures.md)，关键数据已人工核对）

- **撤回“限频”的判断。** 42 张没有收件时间的失败，根因也是时钟回拨：补缺中的 39 张，账本里的完成时间全都早于开始时间（−5.7～−7.8 秒，已核对）；另 3 张直接刷新失败，`retrieval_attempt` 明确记为 `acquisition_time_invalid`。`_receive()` 先查时间再写 `received_at`，所以时钟一回拨，就留下“没收到应答”的假象（`acquisition.py:326`、`acquisition.py:411`）。
- **原因码为什么是空的：** `fail_validation()` 只在状态已是 `received` 时才保存原因；状态还是 `started` 时只存异常类名，异常消息丢了（`acquisition.py:285`）。票 08 郑商所 CF 失败没有原因码，是同一个毛病。
- TuShare 非零业务码一律改写成 `tushare_source_failed`，`code`/`msg` 没有结构化保留（`tushare_context.py:146`、`:891`）；补缺账本还把它归为语义失败，不会重试（`retrieval_ledger.py:843`）。
- **请求量：** 本轮 752 次 = 直接刷新 38 次（按品种、31 天分块）+ 补缺 714 次。补缺对每个不完整的日期逐一请求全部 6 个品种，不看缺的是哪个品种（`targeted_context.py:65`）。本轮 CU 缺 119 天，于是 119 天 × 6 个品种都重取了一遍，RB、RU、SC 已经持有的数据也被重复请求。
- **最终缺日的原因：** CU 的 10 天里，3 天是收件后报 `acquisition_time_invalid`，5 天是没有收件时间的时钟失败，1 天（9/07）是入库时报 `acquisition_availability_time_invalid`，都与时钟有关；另外 7/21 这一天 CU、RB、RU、SC、SP 都缺，PP 缺 9/09（不是之前写的 7/21），这两处都是 TuShare 应答 `code=0` 但没有数据，属于上游本身缺数据。
