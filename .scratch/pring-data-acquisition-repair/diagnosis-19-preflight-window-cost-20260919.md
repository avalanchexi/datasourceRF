# #19 整窗预检为何跑不完：实测归因（2026-09-19）

## 起因

当前版本整窗预检（2026-03-09–2026-08-28）在 30 分钟监督上限被主动中止：`exit_code=-15`、`reason=preflight_time_limit`、`elapsed_seconds=1830.30`，结果文件 0 字节，收据见 `verification-19-preflight-complete-inputs-terminal-20260919-v3.json`。两份身份及运行库内容前后未变。**这是观察上限中止，不是产品断言失败，也没有产出任何 gaps 结论。**

30 分钟没有留下任何阶段证据：子进程只在结束时一次性输出 JSON，中止后无法说出它停在哪一天。这正是提效计划点名的“子进程无阶段输出”。下面的定位因此全部来自事后有界实验，不是重跑同一条命令。

## 有界实验

同一份已准备输入（`/tmp/datasourceRF-preflight-inputs-20260919-v3`），只读，每次都核对材料身份与运行库内容前后未变：

| 窗口 | 结果 |
| --- | --- |
| 2026-08-28 单日 | 144.17 秒，exit 0，`calendar=available`（120 日）、必需 gaps 0、可选 11，峰值 RSS 3.41GiB |
| 2026-08-24–08-28（5 个交易日） | 超过 420 秒上限，未完成 |

边际成本据此 ≥70 秒/天。后两个更长窗口在取得斜率后主动停止，未跑完也未写 `verification-19-preflight-window-cost-20260919.json`，逐窗记录只保留在过程日志里；停止原因是它们只会再花约 14 分钟重复同一结论。

cProfile 对单日运行放大到 20 分钟仍未结束，被主动停止，未产出报告；改用阶段计时（`measure-19-preflight-phases-20260919.py`），开销可忽略：

| 阶段 | 调用 | 秒 |
| --- | --- | --- |
| `ModelInputSelector.select` | 42 | 108.02（单次最大 49.11） |
| `_core_history_gaps` | 1 | 12.51 |
| `build_context_projection` | 1 | 2.53 |
| `EvidenceRepository.metric_series` | 7136 | 2.12 |
| `ModelInputSelector.series` | 139 | 0.50 |

单日总计 123.73 秒。`_core_history_gaps` 整轮只调一次，不随天数增长；成本几乎全在每天每指标各一次的 `select`。

再按指标拆（`measure-19-preflight-select-by-metric-20260919.py`，总计 136.47 秒）：

| 指标 | 秒（单次 select） |
| --- | --- |
| `CN_COMMODITY_EX_HOG_BASKET` | 53.99 |
| `CN_COMMODITY_SLEEVE_CONTRIBUTION` | 53.33 |
| `CN_EQ_NEW_HIGH_LOW_120` | 3.83 |
| `CN_EQ_ABOVE_MA120` | 3.80 |
| 其余各项 | ≤1.59 |

两个商品指标占单日 107.32 秒。

## 根因判断与边界

`ModelInputSelector.select` 每次调用都重建族校验：`_claim_families` 里每个族用选中的 claim_id 回到 `artifacts/sha256` 重读原件并比对内容，商品族走 `commodity_claims_matching_acquisitions`。篮子是 120 日 × 七分项（既有等价性记录为 960 条），所以每调用一次就重新校验约一千条原件。预检按“每天每指标一次 select”调用它，而**整轮运行期间这些原件不变**：同一批原件被重复读取和指纹比对 120 次。

据此外推：120 天 × 107.32 秒 ≈ 3.6 小时，与整窗在 1830 秒内远未完成一致。该外推只用于说明量级，不作为实测值。

已有 `shared_futures_input_reads()` 包住整个预检入口，但它覆盖的是期货输入读取，显然没有覆盖商品族的原件重校验路径；这一点由上面的实测成本反推，尚未逐行确认覆盖边界。

## 下一步（尚未实施）

在 #19 内按证据修复重复原件校验，而不是放宽上限或重跑。修复必须保留现有正确性：跨截止选值不同、坏原件仍须被拒、离开共享作用域后损坏原件的既有守卫仍须生效（`tests/adapters/test_commodity_basket.py` 与 `tests/models/test_material_preflight.py` 已有对照）。先写会失败的重复读取反例，再改实现；修复后重测单日与短窗口成本，并在受影响重型验收通过后才谈整窗。

本文件只记录诊断，不改产品代码，不勾选 #19 任何验收条件；`checks_complete=false` 保持。
