# 票13：日数据采集口径与仍然缺失的历史原件（2026-09-16）

用户 2026-09-16 的答复：「取日数据即可。日数据 T+1 核对无误后不重复获取。」本记录把该口径钉成可查行为，并把**日抓取无法产生**的三项历史缺件明确分开。

## 口径落地

现有缺口计划已经实现"已有有效本地证据不重复调用"：`full_retrieval.py` 对每个需求先做一次选择，本地已完整的记为 `local_complete` 且不进入检索分组；不完整的才生成缺口并请求。T+1 由既有 PUBLIC 规则保证——某交易日的值只有在其发布时间之后才可见、可采用，因此当日运行不会去要尚未发布的当日值。

新增用例 `tests/integration/test_daily_reacquisition.py::test_a_verified_daily_series_is_not_requested_again` 把这条钉住：同一目标日连续跑两次完整运行，核心日线需求两次都是 `local_complete`、最终缺口为空，且两次都没有再调用日线接口。TuShare 与 EIA 页面在用例中均被挡为离线，确保"没有请求"是真的没请求，而不是请求成功被忽略。

- 通过：1 项 / 105.2 秒。
- 变异检查：把 `local_complete` 改成恒为 `model_input_missing` 后该用例立即失败，说明它确实在检验这条行为。

## 仍然缺失、且日抓取无法补的三项

| 缺件 | 为什么日抓取补不了 |
|---|---|
| DR007 历史首次公开时间 | 需要"当时几点公开"的历史锚点；今天抓只能得到今天响应的生成时间 |
| PP / CF / TA 仓单明细与单位 | 需要官方口径说明文档，不是日行情 |
| 存款准备金率历史事件 | 历史发布时间与使用边界，事件已过去 |

这三项继续作为票13 的开放缺口，不因日数据口径落地而勾选；票13 的五项验收条件维持未勾。

## 连带修正

`tests/integration/test_full_run_retrieval.py::test_p2_projection_separates_acquisition_condition_from_certification` 原先断言"无密钥即不发任何请求"。[票14 的页面回退](implementation-14-eia-html-fallback.md)落地后，任何无可用密钥的分支都会继续尝试无密钥页面，因此该用例改为：页面在夹具中离线，API 渠道保留各自的原有结论（`missing_credentials`/`source_failed`/`validation_failed`），页面渠道记 `source_failed` 并成为该行的最新采集。3 个参数全部通过/163.1秒。该用例不再触网。
