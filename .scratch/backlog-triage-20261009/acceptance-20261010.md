# 验收记录：积压批次收尾（2026-10-10，票 01）

基线：[第三轮验收](../lookback-fetch-gaps-20261008/acceptance-20261009-round3.md)（票 25，`run-657f5d4b31e4665c2242`，投影 `projection-c96e490fa4c25695c1e8`，下称"第三轮运行"）。本批合入见[票 01](issues/01-acceptance.md)票面。验收在 main `d0402d1` 上进行，过程文件在会话 scratchpad `v01/`。

## 结论

- **全套一次通过**：`check.py full` 共 **2259 例全部通过，耗时 1:06:05**（3965.75 秒），退出码 0。第三轮是 2208 例、1:16:56：本轮多 51 例，少用 10 分 51 秒（−14.1%）。C 盘开跑时 53G，最低 **52G**，结束时 52G；basetemp 从 2.2G 升到峰值 **15G**。保护脚本没有触发。
- **排名摘要已存档**：`check.py` 结束时打印了前 30 用例、前 15 文件、前 50 与前 10% 的占比，计时文件也已保存（第一节）。这同时是票 24 验收框 1、5 的证据。
- **真实完整运行成功**：`run-a1110cb8616e39b00f60`（v0015，目标日 2026-09-30）。
  - 这是该目标日第 **7** 次 `manual_full`，也是第 **8** 条运行（另有 1 次 `report_generation`）。
  - Worker 启动到报告完成约 **10.2 分钟**，第三轮是 11.3 分钟。
  - 取数回执 **153 条**，失败 12 条，失败的类别与基线相同；外部调用全部串行。
  - C 盘最低 **52G**。
  - 新投影 `projection-d00bacd990f4e65a21e0`；报告 `report-5a42e12401dd8e93ca46`，由 codex_cli 生成。
- **不退化**：
  - 模型输入缺失数 7→7，构成逐项相同。
  - 17 项计数指标按主要成员缺期计，完整 17→17，其 58 个成员读法全部为 `current`；两次投影的确认度读法输出逐行相同。
  - 资讯来源选值 20→20，逐项相同。
  - 宏观模型输入编号 2775→2775，按（指标、期次、成员、值）比较没有差异。
- **缺口清单 34→35 项**。多出的一项是 `CN_USDCNY_ECB_REFERENCE_CROSS`，类别为 `freshness_gap / one_period_behind_carried`。原因是截止时点变了：本次是北京时间 10-10 11:16，第三轮是 10-09 22:30，而该指标登记的发布时刻是 23:00。这属于票 27 的既有口径，不算退化（第三节）。其余 34 项的类别、原因和期次都与第三轮相同。
- **逐票核对**（第四节）：
  - 1002/05、1002/11、lookback/27、lookback/24 的验收项全部成立。
  - 1002/05 与 1002/11 在本次运行中没有可以区分修复前后的实例。1002/05：本次没有被拒候选。1002/11：相关指标在两种日历下推出的最新发布期同为开市日 09-29。这一点如实记录。
  - lookback/26：本次运行没有调用 AI WebSearch，如实写明。
- **审查**：见第六节。

## 一、全套测试（ADR-0025，只跑一次）

| 项 | 值 |
|---|---|
| 准备 | `uv sync --extra dev --no-editable --reinstall-package pring-cycle` 重装共享 dev-venv，耗时 2 秒；安装副本与 `src/pring_cycle` 逐文件比对无差异。`/tmp/pring-heavy.lock` 空闲，没有 `check.py`、pytest 或 Worker 进程 |
| 命令 | `flock /tmp/pring-heavy.lock /usr/bin/time -v $HOME/.local/share/pring-cycle/dev-venv/bin/python tools/check.py full --timings v01/timings-full.jsonl`，nohup 后台运行，前台每分钟轮询，守到结束。完整输出 `v01/full.log` |
| 结果 | **2259 passed in 3965.75s（1:06:05）**，退出码 0。含启动的命令总耗时 3969.23 秒，`/usr/bin/time` 计 1:06:09。user 2035 秒、sys 329 秒；最大常驻内存约 722 MiB |
| 排名摘要 | `v01/full-summary.txt`，计时文件 `v01/timings-full.jsonl`。2259 例的测试阶段合计 3955.90 秒；**前 50 例占 48.0%，前 10%（226 例）占 83.7%** |
| 最慢用例 | 窗口前取数 231.7 秒；PPI 回退 89.1 秒；共享检索预算 82.3 秒；美债 setup 76.9 秒；OMO 栏目回查 73.5 秒；模型切换 55.9 秒；留存 setup 49.3 秒 |
| 最慢文件 | `test_full_run_retrieval.py` 503.4 秒／31 例；`test_worker_registered_catalog.py` 320.8 秒／2 例；`test_lookback_declaration.py` 291.0 秒／40 例；`test_rrr_backtrack.py` 215.3 秒／16 例；`test_tushare_news.py` 209.9 秒／19 例（前 15 见摘要） |
| C 盘 | `disk_guard.sh <pytest PID> v01/guard-full.log 12`，每 30 秒记录一次，共 132 条。起点 53G，最低 **52G**，结束 52G（显示精度 1G）。basetemp 从 2.2G 升到峰值 **15G**。未触发 |
| 并发 | 全套期间 `/tmp/pytest-of-tywin` 下没有新建其他 basetemp 编号：`pytest-83`、`pytest-84` 早于开跑，`pytest-85` 就是本次。重型锁由本次独占，没有并行争用 |
| 覆盖 | 第三轮 HEAD `b54e57d` 到当前，`tests/` 下没有删除任何文件，也没有删除任何 `def test_` 行；新增 40 个测试函数，含参数化共 +51 例 |
| 偏离 | 无 |

**与第三轮对比**

- 总耗时少 10 分 51 秒（−14.1%），同时多了 51 例。
- 五个最慢用例都更快：

  | 用例 | 第三轮（秒） | 本轮（秒） |
  |---|---:|---:|
  | 窗口前取数 | 277.6 | 231.7 |
  | 完整目录正例（PPI 回退） | 114.3 | 89.1 |
  | 美债 setup | 91.3 | 76.9 |
  | 模型切换 | 85.0 | 55.9 |
  | 留存 setup | 82.1 | 49.3 |

- 这些用例的主要成本是完整业务运行，与票 24 连接复用的作用面一致。票 24 在单票内做过同口径交替 A/B：−28%／−50%。
- 全套这次只跑了一轮，两轮之间的代码和测试集合也不同，所以 −14.1% 只是本次的观察值，不作为严格的提速结论。

## 二、真实完整运行

**过程**

1. 在线备份运行库：用 sqlite backup API 以只读方式打开源库，备份到 `v01/backup/pring-cycle-before-v01.sqlite3`，耗时 24 秒。`integrity_check` 结果 ok；库中 26 条运行。
2. `doctor`：`status=ok`，`migration: current`，`dependency_lock: present`（在仓库目录执行）。EIA 凭据仍是 disabled，与基线相同。本批没有新迁移，因此**没有执行 `init`**。
3. 提交运行：`run-submit --json --type manual_full --target-date 2026-09-30 --request-id v01-acceptance-v0015-20261010`，得到 `run-a1110cb8616e39b00f60`，模型 v0015（`v01/submit.json`）。截止时点冻结在北京时间 **10-10 11:16:12**（`system_as_of` = 2026-10-10T03:16:12.931Z）。
4. 启动 Worker 与保护：在 `flock /tmp/pring-heavy.lock` 下后台启动 `pring-cycle worker`，用 `disk_guard.sh` 监视，阈值 20G，日志 `v01/guard-run.log`；轮询记录在 `v01/run-progress.log`。
   - 偏离（与第三轮相同）：保护脚本第一次挂在了发起命令的 shell 上，不是 Worker。约 17 秒后改为监视 Worker 的 Python 进程（PID 1413232），日志里有标注。这段时间 C 盘是 52G。
5. 停止 Worker：运行完成后发 SIGTERM。Worker 日志依次记录 `worker_started`（03:09:11Z）和 `worker_stopped`（03:19:36Z），重型锁随即释放。运行库的盘后调度设在 18:30，Worker 在 11:19 就已停止，没有留到那个时刻。
6. 运行后检查：运行库 `integrity_check` 结果 ok（只读打开，用时 11.7 秒），共 27 条运行；运行后备份放在 `v01/rt/data/`，供后面的只读核对使用。

**指标**（回执按 `acquisition_request.started_at` 落在运行期间统计，口径与基线相同；`v01/runstats.txt`）

| 项 | 本次 | 第三轮运行 |
|---|---|---|
| 耗时 | **约 10.2 分钟**：Worker 启动 11:09:11 → 取数截止 11:16:12 → 报告完成 11:19:24。其中 `refreshing_evidence` 8.4 分钟，`deriving_states` 32 秒，报告 68 秒 | 约 11.3 分钟（`refreshing_evidence` 9.5 分钟，报告 74 秒） |
| 取数回执 | **153 条**，失败 12 | 153 条，失败 12 |
| 检索尝试记录 | 63 条，按渠道与结果逐项相同；走过检索渠道的发布事件 12 个 | 63 条；12 个 |
| 统计局 | 列表页 36、正文 6、日程 1 | 相同 |
| 人民银行 | 列表页 7、正文 1 | 相同 |
| TuShare | 95 次，按接口分布逐项相同（`fut_wsr` 50、`fut_basic` 8、`index_daily` 7、`cn_gdp` 5、`major_news` 5、`fut_trade_cal` 4 等） | 95 次 |
| 检索 | Tavily 1（LPR 2026-02，verified，`model_usable`）；AI WebSearch 0；Exa 0 | 相同 |
| 其他 | EIA 2、ECB 1、Cboe 1、外汇交易中心 1、中国货币网 1 | 相同 |
| 失败回执 | 只有 `fut_basic` 8、`fut_trade_cal` 4，都是 `ContextObservationsMissingError／tushare_context_observations_missing` | 相同 |
| C 盘 | 最低 **52G**（24 条记录） | 最低 58G |

外部调用全部串行：单 Worker 运行，运行期间没有另外调用 TuShare 或其他接口。

本次少用约 1.1 分钟（−10%，67 秒），请求数、渠道和失败数都与第三轮相同。按两轮 preflight→completed 区间统计各回执 `started_at→received_at` 之和（Codex 标准轴审查指出，验收代理复核）：第三轮 274.2 秒，本次 209.3 秒，少 64.9 秒，几乎就是总差额。这段区间既包含网络等待也包含部分本地处理（`acquisition.py:283`、`:324`），无法再拆分。因此 10.2 分钟只作为观察值记录，不归因于票 24 的连接复用或网络快慢。

## 三、不退化与缺口清单对比

**模型输入缺失**（`v01/run-missing.txt`，`lfg_missing.py`）

最终计划仍是 7 个，与第三轮逐项相同：

| 指标 | 期次 |
|---|---|
| 期货仓单 | 07-21、09-09 |
| 两融余额 | 09-30 |
| USDCNY 16:30 | 09-29 |
| EIA 布伦特、WTI | 09-30 |
| SOX | 09-29 |

最终计划状态计数也相同：`local_complete` 3057、`model_input_missing` 7、`operational_evidence` 3。

**17 项计数指标**

- 本次仍是非典型组合（`noncanonical_combination`），17 项全部"不适用"。
- 沿用基线口径，看主要成员在发布读法中有没有缺期。两次投影的确认度读法输出（`v01/conf-r3.txt`、`v01/conf-v01.txt`，`conf_dump.py`，不输出观测编号）**逐行相同**。
- 结论：**完整 17／仍有缺期 0**，58 个成员读法全部为 `evidence_status=current`。

**资讯来源选值**（`v01/news-sel.txt`，`news_sel.py`）

| 指标 | 路径 | 第三轮 | 本次 |
|---|---|---:|---:|
| OMO 7 天利率 | tushare_news | 1 | 1 |
| LPR | ai_websearch | 2 | 2 |
| 工业增加值 | media_page | 1 | 1 |
| 工业增加值 | tushare_news | 2 | 2 |
| 工业企业财务 | tushare_news | 4 | 4 |
| 贷款结构 | media_page | 9 | 9 |
| 人民币中间价 | ai_websearch | 1 | 1 |
| 合计 | | **20** | **20** |

两次选中的资讯声明编号逐项相同，没有差异行，所以没有需要逐项说明的变化。

票 26 存量重取之后，3 个 `ai_websearch` 选值都仍被采用：LPR 2026-04 两个成员、中间价 09-30。这与票 26 的记录一致。

**模型输入编号**（`v01/model-input-diff.txt`，`micmp.py`，按（指标、期次、成员、值）比较）

| 数据集 | 第三轮 | 本次 | 说明 |
|---|---:|---:|---|
| `macro` | 2775 | 2775 | 没有差异；其中派生 15 个，两次相同 |
| `core_assets` | 480 | 480 | 两次都有 120 个不可追溯（基线已知） |
| 各数据集合并去重 | 3252 | 3252 | |

人民币 16:30 收盘价 09-24／09-28 两个编号在两次运行中都不在模型输入里，原因同第三轮第五节：截止时点都晚于 10-09 16:35。

**缺口清单**（`v01/gapcmp.txt`，`gapcmp.py`）

| 类别／原因 | 第三轮 | 本次 |
|---|---:|---:|
| `freshness_gap / one_period_behind_carried` | 24 | **25** |
| `missing / two_or_more_periods_behind` | 6 | 6 |
| `missing / period_not_requested` | 3 | 3 |
| `license_missing / restricted_license` | 1 | 1 |
| 合计 | 34 | **35** |

- 共同的 34 项：类别、原因、持有期、应有期、落后期数**逐项相同**。包括第三轮第五节说明的 20 个国内日频指标：本次截止在 10-10 11:16，10-09 的数据已推定发布，应有期仍是 10-08，所以同样落后 1 期。
- 新增 1 项：`CN_USDCNY_ECB_REFERENCE_CROSS`，类别为 `freshness_gap / one_period_behind_carried`。
  - 原因：批次时效由 `awaiting_release` 变为 `stale`。前者是"发布到 10-08，应有 09-30，落后 0 期"，后者是"发布到 10-09，应有 10-08，落后 1 期"。
  - 归因：`freshness.py:149` 登记的 ECB 参考价发布时刻是北京 **23:00**。第三轮截止在 10-09 22:30，早于 10-09 的发布时刻；本次截止在 10-10 11:16，晚于它。
  - 结论：这是票 27 保持的口径，即历史目标日选值以目标日为限，时效按运行截止点判定。确认度沿用 `current`，选值与模型输入都不变（见上），**不算退化**。
- 批次时效的其余指标，第三轮与本次的状态都相同：`stale→stale` 30、`current→current` 24、`awaiting_release→awaiting_release` 2、`missing→missing` 1。

## 四、逐票核对

| 票 | 证据 | 结果 |
|---|---|---|
| 1002/05 被拒候选改判 | 新投影缺口清单 35 项中，`retrieval_failed` 为 **0**，类别只有 `freshness_gap`、`missing`、`license_missing`。本次运行的 `retrieval_candidate_validation` 只有 1 条：LPR 2026-02 `model_usable`；`not_model_usable` 为 0。第三轮也一样。所以本次没有"被拒候选"这种输入，修复前后的行为在真实运行中**没有可区分的实例**。区分修复前后的证据是票 05 的离线用例（`test_gap_list.py`，全套通过） | **达成**（无反例实例） |
| 1002/11 首次规划日历 | 用安装副本中的 `FRESHNESS_REGISTRY` 选出按上交所日历计的日频指标，共 32 个，其中 28 个出现在计划中。然后以首次计划自己的 `initial_system_as_of` 用 `SseCalendar` 读取窗口内的休市声明（`v01/initcal.py`、`v01/initcal.txt`，在运行后备份副本上执行）：<br>· 首次计划（`full_run_gap_plan` initial）共 2910 条日频期次，范围 2025-09-04～2026-09-30，窗口内声明休市 132 天，日历无未覆盖日。**落在休市日的期次为 0**。最终计划同样是 0。<br>· 融资余额、16:30 收盘价最后几期是 09-28／29／30、09-29，都是开市日。<br>· 15 个检索范围与第三轮相同。<br>说明：融资余额、16:30 收盘价都登记 `lag=1`（`freshness.py:133`、`:155`），发布判定截到目标日日终（`full_retrieval.py:808`）。所以两种日历推出的最新发布期都是 09-29，这一天开市；初始计划中收盘价的最后一期正是 09-29。第三轮（修复前）同样是 0，本次运行**不能区分**修复前后。区分证据是票 11 的离线用例（`test_full_run_retrieval.py`，目标日 09-28，全套通过） | **达成**（非区分性实例） |
| lookback/27 时效标注 | 冻结截止点 `parent_run.system_as_of` = `2026-10-10T03:16:12.931406Z`，在下面四处一致（`v01/basis27.py`、`v01/basis27.txt`，在运行后备份副本上执行）：<br>· 缺口清单：`cycle_overview.gap_list_assessed_at` 等于该时点；`batch_freshness.assessed_at` 全部也是该值。<br>· 报告：确定性骨架 `freshness_basis.assessed_at` 等于该时点，`statement` 为"目标日 2026-09-30；时效截至 2026-10-10 11:16（北京）"。<br>· 首页：缺口区（`_home_page`）显示的正是这句话，没有其他时点。<br>· 报告阅读页：`_report_reader` 显示的同样只有这句话。<br>结论：三处一致，并且等于本次冻结时点 | **达成** |
| lookback/26 AI 页面重取 | 本次运行**没有调用 AI WebSearch**：检索账本中 `ai_websearch` 4 条，全部是 `not_attempted`；`consumed_budget.ai_websearch=0`；期间没有 `media_page_get` 回执。因此本次没有页面下载回执和拒收原因可核。<br>原话表运行前后都是 141 行，其中 AI 声明 35 条：31 条有标题，4 条主语分句为 NULL。这 4 条就是票 26 存量重取时取不到的那几条，按 `_awaiting_subjects` 不予采用。<br>选中的 3 个 AI 值都在存量重取的"采用"之列 | **未调用，如实写明**（证据见票 26 离线用例与存量重取记录） |
| lookback/24 连接复用 | 运行成功，`error_classification` 为 NULL。Worker 标准输出与错误输出（`v01/worker.out`）为空。Worker 日志只有启动、停止两条 info，**全文没有** `locked`、`ResourceWarning`、`unclosed` 字样。12 条失败回执都是 `error_type=ContextObservationsMissingError`、`rejection_reason=tushare_context_observations_missing`；`error_type`、`rejection_reason`、`ingest_rejection_reason` 三个字段中没有任何回执含 `lock`。运行前后（只读打开）`integrity_check` 都是 ok。<br>注意：Python 默认的告警过滤器不显示 `ResourceWarning`，所以"无未关闭连接告警"只表示在默认设置下没有输出；本次没有用 `-W` 另跑 | **达成** |

附带核对（不是本票的验收框）：

- **1002/12 调度**：运行库调度仍是开启状态（18:30）。Worker 只在 11:09–11:19 运行，运行数从 26 增加到 27，只多了本次这一条，没有 `scheduled_full`。这只说明本次没有误提交，不证明休市日不会调度；后者的证据是 `test_worker_execution.py` 的 `test_enabled_schedule_skips_a_stated_sse_holiday_and_submits_a_session_once` 与 `test_enabled_schedule_falls_back_to_weekdays_only_where_no_calendar_states_the_day`（全套通过）。
- **1002/04(a)**：本次没有郑商所请求（CF、TA 仓单都已持有），这条路径在真实运行中没有走到；证据是票 04 的离线用例，全套通过。
- **三核心状态**仍是债牛、股熊、商品牛，报告为 `noncanonical_combination`。

## 五、偏离与遗留

- Worker 的保护脚本起初挂错了进程，约 17 秒后改正（见第二节第 4 步），这期间 C 盘是 52G。
- 1002/05、1002/11 在本次真实运行中都没有能区分修复前后的实例。如果以后要做真实区分，需要两个条件之一：有被拒候选的运行；或者目标日的前一日是休市日（如 09-28 目标）。本票不另开票。
- `CN_USDCNY_ECB_REFERENCE_CROSS` 因截止时点不同，新增了一项"落后 1 期"缺口（第三节），属既有口径。
- 盘后调度仍然开启，并且票 12 已改为按上交所日历判断。如果 18:30 时有常驻 Worker，开市日就会自动提交 `scheduled_full`。本次 Worker 已停止，不受影响。

## 六、审查

Codex 两轴审查（标准轴、规格轴），对象是本记录和票 01 票面；本票没有代码改动。输出在 `v01/review-std.out`、`v01/review-spec.out`、`v01/review-directed.out`。

- 首轮共 3 条阻断，都是记录与证据不符，不涉及验收结论：
  - 标准轴：真实运行提速归因越过证据；失败回执两个字段被合写成一个。
  - 规格轴：1002/11 的最新发布期应为 09-29，原文写成了 09-30。
- 三条都已按证据订正。另采纳规格轴的一条非阻断建议，在 1002/12 一项补上调度用例引用。
- 定向复审结论：三条均已修正，没有引入新的不符，"阻断：无"。
- 两轴都独立抽查了全套与运行的数字、不退化各项、ECB 新增缺口的归因、27 的三处一致，以及 8 个验收框的证据，认为都可以勾选。
