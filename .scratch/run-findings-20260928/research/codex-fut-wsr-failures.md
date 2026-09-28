> Codex 只读调查（codex exec -s read-only，2026-09-28），原样保存最终报告。提示词见文末。

**`fut_wsr` 只读调查报告**

调查对象：`run-dc0bb2d9db7068bf552d`，目标日 `2026-09-24`。已读取源码、测试夹具、相关 ADR、运行库及必要的原始响应；未修改文件、未运行测试、未调用 TuShare 取数。数据库通过 Python `sqlite3` 的 `mode=ro` 打开。

**核心结论：42 张 `received_at=NULL` 的失败，最可能仍由时钟回拨造成，现有证据不支持把它们归因为限频。** 本轮实际有 **752 次请求＝38 次区间刷新＋714 次单日补缺**。“约 720 次”描述的是补缺阶段；“没有收到应答”也需要改为“没有成功记录收件时间”。最终缺日还包含上游返回空数据、入库时间校验失败，不能全部归到这 42 张回执。

以下源码引用使用 `file:line`；数据库是二进制文件，其证据以表、筛选条件、回执 ID 和末尾 SQL 定位。

**1. 发起路径与请求数量**

完整运行先执行 `refresh_context_sources()`，随后执行 `full_retrieval.retrieve()`，因此存在两条不同的取数路径。证据：[worker.py:362](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:362)。

| 路径 | 取数单位 | 日期范围与触发条件 | 是否跳过已持有品种 |
|---|---|---|---|
| Worker 直接刷新 | 按品种取区间 | 目标日往前 220 个自然日，包含首尾；每 31 个自然日分块 | 仓单没有已持有日期过滤，每轮重取 |
| 补缺/重取 | 按日，再逐个请求六个品种 | 120 个交易日窗口内，模型输入尚不完整的日期 | **没有按缺失品种过滤**；当天只缺 CU，也会请求全部六个品种 |

直接刷新通过 `futures_warrants:<symbol>` 分别调用 `acquire_scalars()`；品种为 CU、PP、RB、RU、SC、SP。TA、CF 已退出 TuShare，改由郑商所提供。证据：[worker.py:1759](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1759)、[worker.py:1851](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1851)、[worker.py:1910](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1910)、[tushare_context.py:40](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:40)。

适配器发送的是 `symbol + start_date + end_date`，每块最多 31 个自然日；返回达到 1,000 行就二分日期继续请求，单日仍达到上限则拒收。证据：[tushare_context.py:533](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:533)、[tushare_context.py:557](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:557)。

补缺先按每日模型输入的 `selection.complete` 生成范围，执行前再检查完整性；进入仓单补缺后，无条件遍历六个 TuShare 品种，设置 `start_date=end_date=day`。证据：[full_retrieval.py:395](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:395)、[full_retrieval.py:118](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:118)、[targeted_context.py:65](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:65)。

本轮数据库核实：

| 品种 | 区间刷新请求 | 单日补缺请求 |
|---|---:|---:|
| CU | 5 | 119 |
| PP | 8 | 119 |
| RB | 8 | 119 |
| RU | 8 | 119 |
| SC | 8 | 119 |
| SP | 1 | 119 |
| **合计** | **38** | **714** |

- 区间刷新范围从 `2026-02-16` 开始；无失败、无截断时，正常基数为 `6×ceil(221/31)=48` 次。本轮 CU、SP 提前失败，实际为 38 次。
- 初始缺口计划中，CU 缺 119 天，因此 `04-03～09-23` 共 119 天全部进入仓单补缺；`09-24` 已完整。
- 补缺实际为 `119×6=714` 次，同一阶段没有重复的完全相同参数请求。
- 一般请求数可写为：**直接刷新分块请求＋6×进入补缺的日期数＋截断拆分及实际重试请求**。它不是“仅请求缺失的品种日期”，也不是固定 720 次。

**2. `received_at` 为空时，异常可能发生在哪里**

`capture()` 的顺序是：

`创建 started 回执 → on_started → 检查运行状态 → fetch → _receive → parse → 后续校验`

关键在于 `_receive()` **先检查时间，再更新 `received_at`，最后保存原件**。即使 HTTP 正文已经读取成功，收件时间早于开始时间，也会在记录收件之前抛出 `ValueError("acquisition_time_invalid")`。证据：[acquisition.py:204](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:204)、[acquisition.py:326](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:326)、[acquisition.py:411](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:411)。

可能留下 `started → failed`、无收件时间的相关位置：

| 位置 | 异常 | 与本轮的关系 |
|---|---|---|
| `_receive()` 时间检查 | `ValueError: acquisition_time_invalid` | **最吻合本轮证据** |
| `fetch()` 或 `_receive()` 检查原件类型 | `ValueError: acquisition_raw_response_bytes_required` | 注入非 bytes transport 时可能发生；生产 `_post()` 明确返回 bytes |
| 请求前的 owner 检查 | `acquisition_owner_database_mismatch` / `acquisition_run_not_running` | 此时可能尚未真正发 HTTP 请求 |
| 补缺 `on_started` 回调 | 如 `retrieval_previous_acquisition_not_validated` | 同样可能发生在 HTTP 请求之前 |

证据：[tushare_context.py:902](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:902)、[tushare_context.py:934](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:934)、[acquisition.py:233](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:233)、[retrieval_ledger.py:411](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:411)。

各种上游失败的正常记录方式如下，前提是收件时间检查本身通过：

| 情况 | 回执 `error_type` | `received_at` / 原件 | 上层分类 |
|---|---|---|---|
| TuShare JSON 非零 `code`，包括示例中的 40203 | **`TushareSourceError`** | 已记录 / 已保存 | Worker：`source_failed`；补缺账本：`semantic_validation_failed` |
| 网络连接失败、超时 | 原异常类名，如 `URLError`、`TimeoutError` | 通常为空 / 无完整原件 | `transient_transport_error` |
| HTTP 非成功状态 | `HTTPError` | 特殊分支会先记录响应体与收件时间 | 429：`rate_limited`；5xx：`transient_transport_error`；其他状态另分类 |
| JSON 格式错误 | `JSONDecodeError` | 已记录 / 已保存 | `semantic_validation_failed` |
| JSON `code` 无法转换成整数 | `ValueError` | 已记录 / 已保存 | `semantic_validation_failed` |
| 字段、日期、仓单数量校验失败 | 通常 `ValueError` | 已记录 / 已保存 | 校验失败 |

非零业务码统一被改写成 `TushareSourceError("tushare_source_failed")`，**没有保留结构化的业务 code、msg，也没有专门识别“每分钟最多访问该接口”**；原始 JSON 正常情况下仍在原件里。补缺账本把这个 `ValueError` 子类归入语义校验失败，这是分类上的问题，但它通常不会形成这里的 `error_type=ValueError、received_at=NULL`。证据：[tushare_context.py:146](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:146)、[tushare_context.py:891](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:891)、[worker.py:1913](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1913)、[retrieval_ledger.py:444](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:444)、[retrieval_ledger.py:843](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:843)。

**`rejection_reason` 为空是明确的写库逻辑造成的。** `fail_validation()` 仅在失败前状态为 `received` 时保存原因和 `structure_check`；状态仍为 `started` 时只保存异常类名，丢失异常消息。证据：[acquisition.py:285](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:285)。因此，空原因不等于无应答，更不等于限频。

**3. 重试、重复取数及最终缺口**

- **直接刷新没有重试或退避。** 一个品种取数中途失败，会结束该品种本轮区间取数；此前尚未完成校验的同品种回执也会被统一失败，其他品种继续。证据：[tushare_context.py:351](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:351)、[worker.py:1891](/mnt/d/cursor/datasourceRF/src/pring_cycle/worker.py:1891)。
- **补缺有最多三次尝试，但只针对 `transient_transport_error`。** 循环没有 `sleep`、指数退避或主动限速。耗尽后改为 `transient_retries_exhausted`，避免外层再按瞬时错误重复。`ValueError` 不触发这一重试。证据：[targeted_context.py:126](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:126)、[targeted_context.py:153](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:153)、[retrieval.py:219](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval.py:219)。
- **负缓存不等于等待后重试。** 语义失败按优先级缓存 6/24 小时；HTTP 429 使用 `Retry-After`，否则默认 60 分钟。本轮 39 张补缺失败均进入 `semantic_validation_failed`，对应缓存为 6 小时。证据：[retrieval_ledger.py:793](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:793)、[retrieval_ledger.py:817](/mnt/d/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:817)。

**同一运行可以重复覆盖同一品种同一天**：先包含在区间刷新中，再因当天其他成员缺失而被单日补缺重取。本轮 RB、RU、SC 已有区间成功数据，仍各发了 119 次单日请求；补缺阶段内部则没有完全相同参数的重复请求。

最终缺口由证据选择结果生成：每个品种必须有可验证的交付，缺少则记录 `CN_FUTURES_WARRANTS:symbol_missing:<品种>`；运行结束重新计算 `complete` 和 `missing_members`。**失败回执不会自动等同一个最终缺日，旧的有效交付可能仍能满足输入。** 证据：[warrant_inputs.py:125](/mnt/d/cursor/datasourceRF/src/pring_cycle/warrant_inputs.py:125)、[warrant_inputs.py:151](/mnt/d/cursor/datasourceRF/src/pring_cycle/warrant_inputs.py:151)、[full_retrieval.py:583](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:583)。

运行库与原件核实出的最终缺口：

| 品种 | 缺失日期 | 对应原因 |
|---|---|---|
| CU | 04-16、04-27、05-20 | 已收件，随后 `acquisition_time_invalid` |
| CU | 05-07、06-18、07-03、07-27、09-09 | 本报告调查的无收件时间 `ValueError` |
| CU | 07-21 | `code=0`，原始 `items=[]` |
| CU | 09-07 | 回执已 validated，入库被 `acquisition_availability_time_invalid` 拒绝 |
| RB、RU、SC、SP | 各缺 07-21 | `code=0`，原始 `items=[]` |
| PP | **09-09** | `code=0`，原始 `items=[]` |

所以 CU 为 110/120，其他五个品种各 119/120，但 **PP 缺的是 09-09，并非 07-21**。空数据在完成回执校验后触发 `ContextObservationsMissingError`；入库还有独立的可用时间检查。证据：[tushare_context.py:331](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:331)、[tushare_context.py:954](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:954)、[evidence.py:528](/mnt/d/cursor/datasourceRF/src/pring_cycle/evidence.py:528)。

**4. 接口能力、请求数与品种隔离**

TuShare 官方文档列出的 `trade_date`、`symbol`、`start_date`、`end_date`、`exchange` 均为可选参数，单次最多返回 1,000 行。因此支持按品种指定日期区间；按参数契约，也可以只指定一天、省略品种获取多品种数据，但完整性受行数上限约束。[TuShare 仓单日报官方文档](https://tushare.pro/document/2?doc_id=140)。

仓库已经实现并测试了区间请求：长区间按 31 天分块，达到上限后递归拆分；测试包含“两个日期合计超 1,000 行”和“单日仍达到上限必须拒收”。证据：[tests/adapters/test_tushare_context.py:283](/mnt/d/cursor/datasourceRF/tests/adapters/test_tushare_context.py:283)、[tests/adapters/test_tushare_context.py:327](/mnt/d/cursor/datasourceRF/tests/adapters/test_tushare_context.py:327)、[tests/integration/test_futures_warrant_completeness.py:16](/mnt/d/cursor/datasourceRF/tests/integration/test_futures_warrant_completeness.py:16)、[tests/integration/test_futures_warrant_completeness.py:75](/mnt/d/cursor/datasourceRF/tests/integration/test_futures_warrant_completeness.py:75)。

| 方案 | 120 日窗口的请求量估计 | 隔离与代价 |
|---|---:|---|
| 按日取整族，按品种独立校验入库 | 理想约 **120 次**；本轮补缺日期为 **119 次** | 能保持隔离，但需改回执和解析契约；全市场单日达到 1,000 行时需进一步分拆 |
| 每品种一次整段请求 | 理想 **6 次** | 仅在各品种整段响应都未截断时成立，不能承诺完整取回 |
| 沿用已有 31 天分块，覆盖 04-03～09-24 | 基数 **36 次**，达到上限再增加 | 约 175 个自然日，`6×ceil(175/31)`；现有按品种隔离可直接保留 |
| 沿用当前 Worker 的 220 天回看 | 基数 **48 次**，达到上限再增加 | 已存在；应重点减少随后无差别的逐日重取 |

这里的 119/120 次指替代单日补缺或整个相关取数环节；如果仍保留原有直接刷新，总数还需加上直接刷新请求。

**“按日取整族”不能只删掉请求参数里的 `symbol`。** 当前成员解析器遇到其他品种就抛 `tushare_warrant_symbol_mismatch`，原件重解析契约也严格要求参数集合为 `{start_date,end_date,symbol}`。需要先按品种划分数据，再独立校验、提交和记录结果，并更新原件重解析及证据血缘；不能伪装成六次物理 HTTP 请求。证据：[tushare_context.py:1893](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1893)、[tushare_context.py:2013](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:2013)。

隔离要求针对的是**品种的校验与入库结果**，并不要求每个品种必须独占一次 HTTP 请求。郑商所路径已经采用“一天请求一次，TA、CF 分别记录回执和结果”。证据：[ADR-0032:17](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:17)、[隔离任务:35](/mnt/d/cursor/datasourceRF/.scratch/run-findings-20260926/issues/01-warrant-family-isolation.md:35)。

无论采用哪种方案，都应保留 ADR-0029 的仓库成员合计、差额只记注记，以及 ADR-0032 的 TA/CF 仅走郑商所来源；整族响应里的 TA/CF 不应重新进入 TuShare 选值。证据：[ADR-0029:12](/mnt/d/cursor/datasourceRF/docs/adr/0029-p2-quote-sources-and-warrant-members.md:12)、[ADR-0032:9](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:9)。

**5. 42 张失败的时序与每分钟统计**

统计范围严格限定本运行的 `api_name='fut_wsr'`：

| 阶段 | 请求数 | validated | 无收件时间失败 | 有原因 `acquisition_time_invalid` |
|---|---:|---:|---:|---:|
| 直接刷新 | 38 | 24 | 3 | 11 |
| 单日补缺 | 714 | 666 | 39 | 9 |
| **总计** | **752** | **690** | **42** | **20** |

`validated` 只表示回执校验成功，不保证入库成功，上一节的空数据和入库拒绝包含在其中。

按 `started_at` 排序的间隔分布：

| 统计口径 | 样本数 | 最小值 | 中位数 | 最大值 |
|---|---:|---:|---:|---:|
| 全部相邻请求 | 751 | 0.013 秒 | 1.914 秒 | 274.764 秒 |
| 42 张失败彼此相邻 | 41 | 4.899 秒 | 40.246 秒 | 310.536 秒 |
| 每张失败与时间排序中的上一请求 | 42 | 0.057 秒 | 4.313 秒 | 17.150 秒 |

失败之间的 41 个间隔：`<5秒` 4 个、`5～10秒` 2 个、`10～60秒` 19 个、`≥60秒` 16 个。

**这些是墙钟差值，不能直接当作真实发包间隔。** 按回执插入顺序检查，出现 33 次下一请求 `started_at` 倒退，最深为 **−7.747 秒**，且这 33 次都紧跟无收件时间失败。源码使用 `datetime.now(UTC)`，并直接比较墙钟先后。证据：[acquisition.py:21](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:21)、[acquisition.py:411](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:411)。

更强的证据来自补缺账本：

- **39/39** 张补缺无收件时间失败的 `completed_at` 都早于自身 `started_at`。
- 差值范围 **−7.756～−5.733 秒**，中位数 **−6.274 秒**。
- 全部分类为 `semantic_validation_failed`。
- 另外 3 张直接刷新失败，对应 CU、PP、SP 的 `retrieval_attempt` 全部明确记录 `reason=acquisition_time_invalid`。

例如回执 `acquisition-dded5d98587545bdb77f3e90635d8ad1`：

```text
started_at   = 2026-09-28T05:09:42.125267+00:00
completed_at = 2026-09-28T05:09:36.065427+00:00
```

这与已记录的 Windows/WSL 校时冲突高度吻合；相关调查指出两套校时把时钟来回拉动约 9 秒，随后已调整 Windows 网络对时。证据：[时钟调查:24](/mnt/d/cursor/datasourceRF/.scratch/run-findings-20260928/issues/01-wsl-clock-acquisition-time.md:24)。

以下为 **2026-09-28 北京时间**每分钟统计。“空收件失败”为本次 42 张，“其他失败”为明确带时间错误原因的 20 张。13:05～13:08 无 `fut_wsr` 请求。

| 分钟 | 请求数 | 空收件失败 | 其他失败 |
|---|---:|---:|---:|
| 13:02 | 12 | 1 | 11 |
| 13:03 | 19 | 1 | 0 |
| 13:04 | 7 | 1 | 0 |
| 13:09 | 17 | 1 | 0 |
| 13:10 | 19 | 1 | 0 |
| 13:11 | 18 | 0 | 1 |
| 13:12 | 18 | 2 | 0 |
| 13:13 | 18 | 0 | 1 |
| 13:14 | 18 | 1 | 1 |
| 13:15 | 18 | 1 | 0 |
| 13:16 | 18 | 0 | 1 |
| 13:17 | 18 | 0 | 0 |
| 13:18 | 18 | 0 | 1 |
| 13:19 | 18 | 1 | 0 |
| 13:20 | 18 | 0 | 1 |
| 13:21 | 18 | 0 | 0 |
| 13:22 | 18 | 1 | 0 |
| 13:23 | 18 | 1 | 0 |
| 13:24 | 18 | 1 | 0 |
| 13:25 | 19 | 1 | 0 |
| 13:26 | 18 | 2 | 0 |
| 13:27 | 17 | 0 | 0 |
| 13:28 | 18 | 0 | 0 |
| 13:29 | 20 | 3 | 0 |
| 13:30 | 17 | 1 | 0 |
| 13:31 | 18 | 1 | 0 |
| 13:32 | 17 | 0 | 0 |
| 13:33 | 17 | 0 | 0 |
| 13:34 | 19 | 7 | 0 |
| 13:35 | 12 | 0 | 0 |
| 13:36 | 18 | 1 | 0 |
| 13:37 | 15 | 0 | 0 |
| 13:38 | 15 | 1 | 0 |
| 13:39 | 18 | 0 | 0 |
| 13:40 | 13 | 0 | 0 |
| 13:41 | 17 | 0 | 0 |
| 13:42 | 18 | 2 | 0 |
| 13:43 | 15 | 1 | 0 |
| 13:44 | 15 | 0 | 0 |
| 13:45 | 14 | 1 | 0 |
| 13:46 | 18 | 2 | 1 |
| 13:47 | 16 | 2 | 1 |
| 13:48 | 17 | 1 | 0 |
| 13:49 | 16 | 1 | 0 |
| 13:50 | 9 | 2 | 1 |
| **合计** | **752** | **42** | **20** |

失败最多的是 13:34，19 次请求中有 7 次；但其他同为 18～19 次的分钟可以完全成功。失败也出现在分钟内第 1 次请求，未呈现稳定的“超过某个请求序号后开始失败”模式。按记录时间计算，固定分钟最大 20 次，滚动 60 秒最大 26 次。**这些统计不能排除账号其他进程的流量，但本运行没有支持限频归因的直接证据。**

可复核的只读 SQL：

```sql
-- 每分钟请求数与失败数；NULL 不能写成 = NULL。
SELECT
  strftime('%Y-%m-%d %H:%M', a.started_at, '+8 hours') AS minute_cn,
  COUNT(*) AS requests,
  SUM(a.state='failed' AND a.received_at IS NULL) AS failed_no_received,
  SUM(a.state='failed' AND a.received_at IS NOT NULL) AS failed_received
FROM acquisition_request a
JOIN full_run_acquisition f USING (acquisition_id)
WHERE f.run_id='run-dc0bb2d9db7068bf552d'
  AND a.api_name='fut_wsr'
GROUP BY 1
ORDER BY 1;

-- 核实补缺失败的完成时间倒退。
SELECT
  a.acquisition_id, a.started_at, p.completed_at, p.classification,
  ROUND((julianday(p.completed_at)-julianday(a.started_at))*86400, 3)
    AS elapsed_wall_seconds
FROM acquisition_request a
JOIN full_run_acquisition f USING (acquisition_id)
JOIN retrieval_physical_request p USING (acquisition_id)
WHERE f.run_id='run-dc0bb2d9db7068bf552d'
  AND a.api_name='fut_wsr'
  AND a.state='failed'
  AND a.received_at IS NULL
ORDER BY a.rowid;
```

**6. 结论与修复方向**

最可能的因果链是：**时钟回拨 → `_receive()` 在写收件时间前拒绝 → 回执只留下 `ValueError` → 补缺把它归为语义失败，不重试并负缓存 → 部分日期仍缺失。** 3 张直接刷新失败有明确时间错误记录；39 张补缺失败全部具有完成时间倒退证据。由于它们没有保存异常消息和原件，无法逐张从回执证明具体抛错点，但“限频导致无应答”的原判断应撤回。

建议考虑三个方向：

1. **先补齐失败诊断与分类，再复验已修好的时钟环境。**  
   对所有失败阶段保存错误原因、失败阶段；保留 TuShare `code/msg`，区分业务限频、网络错误、解析错误和时间错误。对真正可重试的传输/限频错误增加有上限的等待与退避。收益是避免继续误诊；代价是回执字段及分类逻辑调整。时钟票已按用户决定关闭，先遵循“环境修复后真实运行复验”，无需立即另加时间容错。证据：[acquisition.py:285](/mnt/d/cursor/datasourceRF/src/pring_cycle/acquisition.py:285)、[tushare_context.py:891](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:891)、[时钟票:38](/mnt/d/cursor/datasourceRF/.scratch/run-findings-20260928/issues/01-wsl-clock-acquisition-time.md:38)。

2. **优先优化为按缺失品种合并日期区间，保留现有分块与截断检查。**  
   当前已具备区间能力，主要问题是补缺丢掉了 `missing_members` 的品种粒度。按缺失品种合并相邻日期，并让成功分块及时独立提交，可减少重复请求及一次失败牵连整个品种历史的范围。收益是改动较小、保留已有隔离；代价是需要区间规划、逐块提交和补缺账本适配。证据：[full_retrieval.py:419](/mnt/d/cursor/datasourceRF/src/pring_cycle/full_retrieval.py:419)、[targeted_context.py:72](/mnt/d/cursor/datasourceRF/src/pring_cycle/targeted_context.py:72)、[tushare_context.py:351](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:351)。

3. **按日共享整族响应，作为另一种批量方案。**  
   理想请求量约 120 次，能按品种隔离坏行；但必须处理全日 1,000 行截断、物理请求与品种结果的映射，以及原件重解析契约。收益是按日组织简单、天然共享响应；代价明显大于复用现有区间方案，且 120 次只是未触发拆分时的估计。证据：[tushare_context.py:1893](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1893)、[tushare_context.py:2013](/mnt/d/cursor/datasourceRF/src/pring_cycle/tushare_context.py:2013)、[ADR-0032:17](/mnt/d/cursor/datasourceRF/docs/adr/0032-czce-warrants-from-exchange-daily.md:17)。

## 提示词

```text
只读调查，用中文输出一份 Markdown 报告（直接打印到标准输出，不要改任何文件）。仓库：pring-cycle（src/pring_cycle/）。

背景：真实运行 run-dc0bb2d9db7068bf552d（目标日 2026-09-24）里，TuShare `fut_wsr` 按品种逐日取仓单（6 个品种 CU/PP/RB/RU/SC/SP × 120 日窗口，约 720 次请求）。其中 42 张回执 state=failed、error_type=ValueError、received_at 为空、rejection_reason 为空；结果 CU 缺 10 天，其他品种各缺 1 天。运行库：~/.local/share/pring-cycle/pring-cycle.sqlite3（表 acquisition_request、full_run_acquisition，可只读查询，用 `sqlite3 "file:...?mode=ro"`）。

请回答，每条都给出 file:line 证据：
1. `fut_wsr` 在一次完整运行里是从哪里发起的（Worker 取数阶段的仓单家族、补缺/重取路径），按品种逐日还是按品种区间？一次运行实际会发多少次请求，由什么决定（窗口内未持有的日期？每轮全量？）。
2. 在请求已发出、但没有记录 received_at 的情况下，哪些位置会抛出 ValueError？特别是：TuShare 返回非零 code（如 40203 频率超限、"每分钟最多访问该接口"）时如何处理、记成什么；网络超时、HTTP 错误、JSON 解析失败各记成什么。为什么 rejection_reason 会是空。
3. 失败后有没有重试、间隔或退避？同一运行内会不会再取同一品种同一天？失败的日期最终怎样进入缺口清单。
4. TuShare `fut_wsr` 接口是否支持一次请求取一个品种的整段日期区间，或一次取某一天的全部品种（查代码里已有用法、tests 夹具、docs/ 与 ADR-0029/ADR-0032、.scratch/run-findings-20260926/issues/01-warrant-family-isolation.md 里的说明）。如果改成"按日取整族、入库时按品种隔离"或"按品种取区间"，请求数分别约是多少，隔离语义（一个品种的坏行不连累其他品种）还能否保持。
5. 用运行库核实：这 42 张失败回执的 started_at 间隔分布（相邻请求相隔多少秒），是否集中在某些时间段（例如每分钟请求数超过某个阈值后开始失败）。给出每分钟请求数与失败数的统计。

最后给出结论：最可能的失败原因，以及两三个修复方向和各自的取舍。
```
