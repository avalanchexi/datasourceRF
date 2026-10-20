# EIA 完整 Worker 场景的独立日历夹具诊断（2026-09-19）

v6 默认全套实际退出1：914 passed、1 failed，pytest 4543.60秒；监督4548.27秒，原因null，冻结输入不变，独立后代无残留。money变异和独立进程验收队列未启动。原始日志见 `verification-current-full-v6-20260918.txt`，终态归档清单 `verification-evidence-archive-v6-terminal-20260919.json`。

失败为 `test_worker_full_run_publishes_the_registered_projection_across_eia_conditions[missing-missing_credentials]`：期望completed，实际action_required / p0_required_calendar_unavailable。场景未配置TuShare，合成生命周期材料的三个trade_cal收据属于tushare-context-parser-v0002，未提供核心独立日历门所需的tushare-core-parser-v0002收据；日历声明为0。不是EIA异常，不应放宽生产门。

## 快速反馈

`repro-eia-calendar-fixture-20260919.py` 从停止后的失败DB只读备份到WSL原生新目录，调用实际 `required_calendar` 和 `ModelInputSelector`，不修改原现场。复现命令使用v6/project测试及v2/site安装，参数red-v2；实际0.36秒断言available失败。初版选用了不存在的client_request_id列，其设置失败日志保留为red文件，不冒充有效RED。旧v1 seed辅助函数对新目录仍不可用，green参数的失败日志保留。

参数green-receipt使用公开 `TushareCoreAdapter.acquire_calendar`、已有独立日历归档原件及显式合成时钟（取原运行截止点，仅用于副本诊断），0.43秒返回available、120日、末日2026-08-28、basis validated_independent_calendar_response。旧运行的失败状态不改；此控制只证明日历前置，不证明完整Worker通过。

## 修改及剩余验证

整合树仅修改 `tests/integration/test_worker_registered_catalog.py`：四个EIA条件运行前，经已有real_core_opener与公开核心适配器取得日历。这里使用运行时当前时钟，不倒填收据，不配置TuShare凭据，原EIA缺密钥/成功/网络/解析条件、completed、发布身份、通道、认证边界及原异常断言均保持。生产门与缓存身份未改。

Ruff/格式/diff-check通过。专项驱动 `verify-eia-calendar-worker-20260919.py` 冻结v6全部输入，仅替换该文件；沿用相同安装及有效材料，四个场景串行执行，3GiB/3600秒监督，已通过且无引用独立副本才清理。该专项尚待实际终态；随后按影响和原要求做同版本完整默认验证，不能拼接v6旧通过冒称新全套。
