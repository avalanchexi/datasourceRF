# #28 日历门禁后的候选天数夹具修复（2026-09-18）

v4 默认顺序完整验证已终止：416 passed、1 failed，pytest 151.27 秒，监督单调 152.75 秒，exit 1；冻结输入未变、监督器无终止原因、后代残留为空。统一离线验收和 11 项 acceptance timing 已通过。失败节点为 `tests/integration/test_candidate_duration.py::test_new_model_reports_actual_candidate_days_and_preserves_old_snapshots`，尚不能关闭完整验证。

## 实际失败路径

旧夹具只保存 180 日核心价格，没有独立交易日历。第一个 `old_run` 预期 completed，实际 action_required；失败运行库的 error_classification 为 `p0_required_calendar_unavailable`，符合 #28 修复后的公开发布门。现场保留在 `/tmp/datasourceRF-current-verify-20260918-v4/pytest/test_new_model_reports_actual_0/runtime/data/pring-cycle.sqlite3`。

该测试还意外发起 EIA HTTP 请求，失败 acquisition 记录显示 08:19:46 至 08:19:59 UTC，约 12.78 秒。不能把这轮 v4 描述成完全隔离外网的测试。

## RED → GREEN

先只在真实外部传输接缝 `eia_html.open_no_redirects` 与 `official_context.urlopen` 注入不可用：原测试仍以同一日历门禁失败，1 failed、1 passed，pytest 2.53 秒（入口 3.29 秒）。见 [RED](verification-duration-calendar-offline-red-20260918.txt)。

再经既有 `seed_independent_calendar` / EvidenceRepository 公开写入路径补入合成独立日历。原文件 2 passed，pytest 28.06 秒（入口 28.85 秒），见 [GREEN](verification-duration-calendar-green-20260918.txt)。保留新旧候选 7/8 日、Stage III、CLI/API/页面/报告及旧快照不可变的所有断言。产品代码、发布门和业务预期均未放宽。

Ruff 与格式检查通过；Spec 与 Standards 分别独立审查，未解决问题各 0。随后运行其余直接调用 Worker 的 13 个 integration 文件，收据为 `verification-calendar-related-fixtures-20260918.json`；重型生命周期文件另随最终完整批次执行。这批相关回归不是完整验证，实际状态以收据为准。

## 后续验证身份

v2 冻结 project/site 及 v3/v4 历史收据保持原样。相关批次完成后，创建包含本夹具修正的新快照，并逐文件核对整合树与冻结输入。应用安装仅在源码字节一致时复用；两种生命周期材料必须重新计算完整 identity/key 并验证有效性，不手工强制旧 key。新完整批次保留默认发现、原始顺序和全部重型用例，最终以自身完整终态为准，不拼接旧节点的通过结果。

## 相关回归实际终态

13 个文件 **187 passed / 923.74 秒**，quick 入口 exit 0 / 924.76 秒；测试监督无终止原因、无残留。原驱动随后在序列化 Popen 时 TypeError / exit 1，原始异常保留于 `verification-calendar-related-fixtures-driver-error-20260918.txt`。从实际监督终态恢复的 [收据](verification-calendar-related-fixtures-recovered-20260918.json)明确：运行中审计至结束的 201 个 Python 输入一致，但原驱动启动前后哈希比较未成功记录；不把恢复收据冒充完整冻结验收。恢复执行 exit 0，没有重跑测试。

此批超过约 3 分钟目标，主要耗时为 `test_full_run_retrieval.py` 中约 30 秒的完整检索场景；保留实际慢项，不能把 quick 入口名称当作耗时保证。v5 须按自己的完整冻结输入、默认发现与实际终态验收。
