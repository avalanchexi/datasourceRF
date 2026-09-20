# #19 选择族校验按期收窄：消除重复原件校验（2026-09-19）

起点是[整窗成本诊断](diagnosis-19-preflight-window-cost-20260919.md)：单日预检 123.73 秒里 `ModelInputSelector.select` 占 108.02 秒，其中 `CN_COMMODITY_EX_HOG_BASKET` 53.99 秒与 `CN_COMMODITY_SLEEVE_CONTRIBUTION` 53.33 秒。

## 根因

`select()` 的族校验（`_claim_families`）通过 `points_of`/`series_by_metric` 拿到 `self.series(metric_id)` —— **整条序列**。但族校验的结论 `valid_claim_ids` 只在下方 `matches` 循环里被查阅，而 `matches` 只包含本期可采用的点。同一函数里的 `core_inputs` 早已按 `matches_retrieval_period` 过滤，族校验没有。

于是每次 `select()` 都把整条序列的声明送去重校验。商品篮子是 120 日 × 七分项，每个日快照一次重算，所以一次调用约 54 秒；预检按“每天每指标一次 select”调用，重复 120 次。

十个族的 check 函数（ECB 合同、LPR、official、interbank、treasury、margin/index/valuation 的 tushare、breadth、commodity）已逐一核对：全部是 `selected = {point.selected_claim_id: point}` 后**逐声明**对自己的父原件校验，没有跨期推理。因此收窄传入点集不改变任何结论。

## 改动

`ModelInputSelector.adoptable(metric_id, period)` 返回本期可采用的点，按 selector 生命周期缓存；`_claim_families(period)` 的两个助手改用它。判定与下方 `matches` **完全同源**：

- 普通指标用 `matches_retrieval_period`。
- `EFFECTIVE_UNTIL_CHANGED_METRICS`（当前为 `CN_OMO_7D_RATE`）走事件分支，保留 `period_end <= event_limit` 的更早期次——事件在被改变前持续有效，这些更早声明确实可能被采用，过滤过头会让本该被校验的声明免检通过，方向危险。为此把原先内联的季度换算提成 `metric_contracts.event_period_limit`，收窄与采纳两处共用一个定义，不会各自漂移。
- 维度成员不参与收窄（取各成员并集），是安全的超集。

## 验证

反例先 RED：`test_period_selection_rechecks_only_the_claims_it_can_adopt` 记录商品族实际被问到的期次，存 2026-03-09 与 03-10 两日后按 03-10 选择，实际得到 `{'2026-03-09', '2026-03-10'}`，断言失败（1 failed、1 passed / 6.53 秒）。

同批的 `test_a_damaged_original_outside_the_period_leaves_the_selection_complete` **修复前后都通过**，不冒充产品 RED：它钉住“收窄不可能改变结论”——损坏期外那天的原件，本期选择仍 complete 且采用本日声明。

修复后两项 2 passed / 6.26 秒。Ruff、格式、五源文件 mypy 通过。

受影响回归（9 个直接消费选择的文件）：**765 passed / 2426.51 秒（40 分 26 秒）、退出 0**，日志 `verification-19-period-scoped-recheck-related-20260919.txt`。最慢项为 `test_full_run_retrieval.py` 的若干用例（40.31/37.18/29.55 秒）与 `test_candidate_admission.py` 的 120 日窗口用例（34.60 秒）。**远超 3 分钟快速反馈目标，如实记录**，不删测试凑时限。

## 收益与边界

同一份已准备输入、同一天（2026-08-28）、只有代码不同的对照：

| 阶段 | 修复前 | 修复后 |
| --- | --- | --- |
| 单日总计 | 123.73 秒 | **26.63 秒** |
| `selector.select` | 108.02 秒 / 42 次 | **10.14 秒 / 42 次** |
| `_core_history_gaps` | 12.51 秒 / 1 次 | 12.30 秒 / 1 次 |
| `build_context_projection` | 2.53 秒 | 3.59 秒 |
| `evidence.metric_series` | 2.12 秒 / 7136 次 | 2.16 秒 / 7136 次 |

调用次数不变，省下的是每次调用内部的重复原件校验，不是少验了行为。

边界要说清：这两次测量所用的 v3 输入是在**旧代码**下准备的，本次代码改动已使 `code_hash` 变化，所以这是**成本对照探针，不是同版本材料收据**；`material_identity_unchanged`/`runtime_contents_unchanged` 仅表示探针自身只读。另外 `_core_history_gaps` 的约 12.3 秒是整轮一次，所以每天边际成本从约 111 秒降到约 14 秒，120 天仍约 28 分钟加固定开销，**不能据此宣称整窗预检已可在 30 分钟上限内完成**；整窗要在新版本下重新准备输入后实测。

#19 预检的 `checks_complete=false` 保持，本票验收条件不勾选；真实来源认证与完整候选依赖不变。

## 受影响重型验收

按影响触发全部四个重型文件，串行，同一时刻仅此一个重型任务。驱动 `verify-19-period-scope-heavy-20260919.py` 用 `tools/inputs.py` 在前后各取一次软件身份，并向子进程自身取实际导入的发行物。

| 退出码 | 耗时 | 文件 | 结果 |
| --- | --- | --- | --- |
| 0 | 2261.55 秒 | `tests/models/test_isolated_lifecycle.py` | 7 passed |
| 0 | 2400.13 秒 | `tests/integration/test_worker_registered_catalog.py` | 10 passed |
| 0 | 1307.57 秒 | `tests/integration/test_integrated_worker_delivery.py` | 2 passed |
| 0 | 13.46 秒 | `tests/integration/test_integrated_worker_core_gap.py` | 1 passed |

总计 5982.80 秒（1 小时 39 分 43 秒），`software_inputs_unchanged=true`，`imported_package_path` 为整合树 `src/pring_cycle`。收据 `verification-19-period-scope-heavy-20260919.json`，逐文件日志同目录。

期间一次系统低内存只杀掉了会话的等待进程，没有触及验证本身；重型进程全程存活，不存在环境中断后的重跑。

至此本改动的相关回归与受影响重型均已通过。仍未完成：同版本默认全套（属 #22 收尾统一执行）、新版本下重新准备输入后的整窗预检实测、两轴复核与提交。#19 预检 `checks_complete=false` 与各票勾选状态不变。

## /code-review 后的修正（2026-09-20）

评审结论为「未发现会导致错误结果的缺陷」，三条非致命问题全部成立并已修复，不留待后续。

**1. 密度规则只提取了一半（中）**：`minimum_context_daily_observations` 已是共享定义，但 `worker.py:1207` 与 `warrant_inputs.py:76` 仍各留一份 `(n * 95 + 99) // 100` 字面副本。失配方向很实在：日后改阈值只会改到有名字的那一处，worker 的候选准入密度门与 evaluation/preflight 判定就会打架——worker 放行的候选被 evaluation 判为覆盖缺口，或反向卡死。两处已改为调用共享函数，现在全仓只剩 `metric_contracts.py:27` 一处定义。这是既有重复、非本次引入，但重型验收本就要重跑，捎带修的边际验证成本为零。

**2. 事件分支其实没有收窄（低）**：`adoptable` 的事件分支返回 limit 内**全部**历史点，而 `CN_OMO_7D_RATE` 同属 `OFFICIAL_CONTEXT_INTEGRITY_METRICS`——唯一没有 `claims_checked_once` 去重的族，跨调用也摊不掉。已核实等价性：采纳循环对事件指标在**质量检查之前**就只保留 `period_end` 最大的点（「A bad newer event must not silently resurrect an older rate」），更早的点进不了采纳。故改为按 `dimensions` 分组只保留各成员最新期次。评审未提但本实施保留的一点：同一成员在最新期次上可能有多个点，那种冲突正是调用方必须看见的，所以不做去重只留一条。

**3. 两处判定靠「逐字相同」维系（低）**：整个改动的正确性论证建立在 `adoptable()` 与采纳循环判定一致上，却无结构约束。采纳循环已改为直接调用 `self.adoptable(metric_id, scope.period)` 再按维度成员过滤，两处现在同源；顺带消除了每个维度成员重算一次 `event_metric`/`event_limit` 的浪费。

Ruff、格式、四源文件 mypy、`git diff --check` 通过。

### 修正后的验证

改动扩到 `worker.py` 与 `warrant_inputs.py`，受影响面相应扩大到 17 个文件（新增 OMO 事件分支与密度规则的消费者：`test_model_lifecycle.py`、`test_worker_execution.py`、`test_context_projection.py`、`test_derived_context_freshness.py`、`test_context_model_certification.py`、`test_official_context.py`、`test_metric_catalog.py`、`test_macro_states.py`）：**954 passed / 2453.40 秒（40 分 53 秒）、退出 0**，日志 `verification-19-period-scoped-recheck-related-v2-20260920.txt`。

上一轮 4/4 通过的重型验收因 `worker.py` 改动已作废，不能复用，已按原四个文件重跑：

| 退出码 | 耗时 | 文件 | 结果 |
| --- | --- | --- | --- |
| 0 | 2238.73 秒 | `tests/models/test_isolated_lifecycle.py` | 7 passed |
| 0 | 2318.57 秒 | `tests/integration/test_worker_registered_catalog.py` | 10 passed |
| 0 | 1288.60 秒 | `tests/integration/test_integrated_worker_delivery.py` | 2 passed |
| 0 | 13.48 秒 | `tests/integration/test_integrated_worker_core_gap.py` | 1 passed |

总计 5859.47 秒（1 小时 37 分 39 秒），`software_inputs_unchanged=true`，`imported_package_path` 为整合树 `src/pring_cycle`。收据 `verification-19-period-scope-heavy-20260920.json`。其中 `test_worker_registered_catalog.py` 正是覆盖 worker 准入密度门的文件。

评审自身跑的 `tests/integration tests/models` 被它自设的 50 分钟 shell 超时杀掉（exit 143），且用的是 `uv` 新建的 `.venv` 而非本项目锁定解释器，**不构成验证证据**，评审报告亦如此声明。`.venv/` 在 `.gitignore` 内，软件清单仍为 231 条且不含它。

### 评审修正后的成本复测

同一份已准备输入、同一天（2026-08-28）、只读：

| 阶段 | 修复前 | 评审前 | 评审后 |
| --- | --- | --- | --- |
| 单日总计 | 123.73 秒 | 26.63 秒 | 26.82 秒 |
| `selector.select` | 108.02 秒 | 10.14 秒 | 9.79 秒 |
| `_core_history_gaps` | 12.51 秒 | 12.30 秒 | 12.51 秒 |
| `build_context_projection` | 2.53 秒 | 3.59 秒 | 3.98 秒 |

三次预检结论完全一致（必需 gaps 0、可选 11、`checked_business_dates` 同为 2026-08-28），`material_identity_unchanged`/`runtime_contents_unchanged` 均真。

**如实说明收益归属**：事件分支收窄（评审第 2 条）实测只省下 `select` 的 0.35 秒（10.14→9.79），与先前逐指标测得的 `CN_OMO_7D_RATE` 0.35 秒吻合；单日总计 26.63→26.82 秒的差异在噪声范围内，**不构成可宣称的提速**。该项的真实价值是正确性与结构：事件分支的 docstring 不再名不副实，且与采纳循环共用同一判定。本切片可宣称的提速仍只来自商品族的重复原件校验消除（123.73→26.63 秒）。

`_core_history_gaps` 的约 12.5 秒是整轮一次的固定开销，不随天数增长。每天边际成本从约 111 秒降至约 14 秒；120 天外推约 28 分钟加固定开销，**仍不能宣称整窗预检可在 30 分钟上限内完成**，须在新版本下重新准备输入后实测。
