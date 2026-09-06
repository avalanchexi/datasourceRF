# Pring 数据到结论的只读事实审计

审计时点：2026-09-06 10:31:55 UTC 开始（北京时间 18:31:55），最后补充时间见同目录 `model-output-statistics.json`。源码 HEAD：`6edf0cbea95c3c26efa9c24fbb4e8f88f57c0302`。生产数据库：`/home/tywin/.local/share/pring-cycle/pring-cycle.sqlite3`。这次只读生产库并调用无副作用的选值、趋势、阶段纯函数；没有网络、账户请求、Worker、AI、报告生成、模型激活或数据库写入。只新增本说明及统计 JSON。

**结论：旧 Stage III 的机械计算与冻结报告相互一致，但它不是当前交易日的新结论；当前正式全流程被来源认证 guard 阻断。已有数据、历史 passed 记录和 fixture 验收，不足以证明这些输入已满足当前来源与点时认证契约。**

## 1. 真实运行的身份和停止位置

| 对象 | 只读记录 |
|---|---|
| active model | `model-v0011-a734bb6e7dcf415f`；manifest hash `cee65e356c3a0e2b37b686e29c3319f68485f0c787a5d79196f8f0dfffc3c5ea`；目录 `metric-catalog-v0003` |
| current projection | `projection-7a12ff2f7ab7175a31b2`；目标日 **2026-08-03**；SYSTEM AS OF `2026-08-31T20:51:41.285300+00:00` |
| evidence snapshot | `snapshot-3f0689ef288e58868bf5`；`system_as_of`；与投影同一 cutoff；落库时间 `2026-08-31T20:52:05.547348+00:00` |
| 最新持久报告 | `report-e6819df812538cbf6150`；8 月 3 日 Stage III；`completed_degraded` / `deterministic`；创建 `2026-08-31T21:01:44.948379+00:00` |
| 最新真实请求 | `run-cd38330778d23bfb8c45`；`report_generation`；接受时间 `2026-09-05T09:04:57.219371+00:00`；`action_required`，仍在 `queued` |
| 请求错误 | `worker_failure:ValueError:source_certification_contract_unresolved:metric-catalog-v0003` |
| 正式切换 | `system_cutover` **0 行** |

`source_contract_review.py:73–107` 明确隔离 v3，历史结果仍可读。`worker.py:218` 在推进 preflight 前检查整个绑定模型；`projections.py:87`、`reports.py:364,433` 继续保护新投影和报告写入，`models.py:490,704` 保护激活/回滚。`web.py:275–280` 的提示明确“下方保留上次发布的历史结果”。此处阻断的直接原因是来源契约隔离，不能将旧 run 里仍保存的泛化 `next_action=refresh_p0_or_create_gap_notice` 当成“只补一次 P0 即可恢复”的事实。

v3 的静态隔离涉及市场指数、市场广度、融资、估值和商品篮子共五组、15 个指标。新研究与候选输入收据不原地重写这个旧模型；当前库仍只有旧 active 指针。本次核对的 8 个关键模块，已安装 dev-venv 文件 SHA256 均与工作区相同；没有据此推断任一正在运行进程的内存版本。

## 2. 从数据到 Stage III 的实际链路

模型绑定三核心为 `CN_BOND_CORE_000012` / `000012.SH`、`CN_EQUITY_CORE_000985` / `000985.CSI`、`CN_COMMODITY_CORE_NHII` / `NHII.NH`，单位均为 `index_points`。三者 v3 库内各有 2,345 个不同交易日，覆盖 2017-01-03 至 2026-08-28；重复的来源 vintage 数量不等于交易日数量。

`evidence.py:602–626,695–716,947–993` 按明确指标定义版本和 cutoff 选值：PUBLIC 使用 `public_available_at`，SYSTEM 使用 `available_at`，各来源选当前可见 vintage，多认证来源超容差则保留冲突。当前 Worker 使用 SYSTEM（`worker.py:751–759`），并限制业务日不晚于目标日，再检查精确来源身份、完整目标日、认证/质量与数值（`worker.py:770–790,847`）。

当前快照的 **1,001 个唯一 ID 全部解析成功：985 个 source claim、16 个 derived observation**。递归展开派生血缘仍为同一 1,001 个 ID，没有丢失祖先，也没有任何来源 `available_at` 晚于投影 cutoff。三核心各使用 2,326 个截至 8 月 3 日的历史输入计算状态；投影只呈现最近 120 日（2026-02-02 至 2026-08-03），符合隐藏预热与可见窗口分离（`worker.py:802–816`）。

| 资产 | 8/3 被选收盘值 | 距 MA120 | MA120 的 20 日斜率 | 1.5σ20 噪声带 | 稳定状态 | 未确认候选 |
|---|---:|---:|---:|---:|---|---|
| 债券 | 229.5275 | +1.046776% | +0.287116% | 0.037136% | bull | 无 |
| 股票 | 5652.5702 | −9.020022% | −0.987002% | 3.126391% | bull | bear，实际连续 **7 日** |
| 商品 | 3733.13 | −5.795461% | +0.580126% | 1.638181% | bull | 无 |

按冻结 `trend-v0001`，方向信号同时检查价格相对 MA120 距离、斜率和噪声带，持续 8 日才改变稳定状态；没有有效方向信号时保留上个稳定状态（`domain/trend.py:49–118,174–181`）。因此股票虽有 7 日 bear 候选，仍为 bull；商品价格低于均线但斜率为正，没有 bear 方向确认。**bull/bull/bull → Stage III** 是六阶段映射的精确结果（`domain/stage.py:21,28–43`），宏观证据不投票。

离线复算的三核心状态、候选、距离/斜率/噪声带全部与旧投影一致，数值最大误差为 0；末 120 个 claim ID 逐个相同。这里复用了当前确定性引擎并追踪其局部计数，验证历史条目与源码的自洽性，不是独立经济有效性验证。**但候选持续天数字段确有输出/展示缺陷，不能把上述一致性扩展为所有输出字段正确。** 规格 `spec.md:40` 要求展示尚未完成切换的候选“持续天数”；`dashboard.py:730,753` 显示“持续 {candidate_days} 日”，`1201–1224` 列名也是“候选持续”。旧投影却把 `TrendResult.persistence_days` 写成 `candidate_days`（`worker.py:793,818`，`p0.py:287`）；已有稳定状态时该值返回规则阈值 8（`domain/trend.py:113`），而不是实际候选计数。本次股票候选实测为 7 日、字段与页面显示为 8 日；债券/商品无候选的局部计数为 0，字段也仍是 8。未发现把该展示字段定义为“配置门槛”的另一个领域契约。错误位于输出映射/展示语义；稳定状态切换仍使用真正的局部计数，因此 Stage III 没有因此算错。

三个末日 claim 的精确 ID 分别为：

- 债券 `03abcc16e4160073180632d2bc6b38e44db4fa6a7f851fcf10eed0a8e956e49a`。
- 股票 `9218cd3ae25b48361d906f40e1c6b02702778d6d52b9435224e1d364a5053f52`。
- 商品 `3d17c1f1bf1cde5a622d9ef0d55f1081df71cf4a802547c6bc0d9ce29319f8cd`。

以**同一个冻结 SYSTEM cutoff**读取现存截至 8 月 28 日的 2,345 日/资产，仅做无写入取证重算，得到 **bond bull / stock bear / commodity bull → `current_stage=null`、`noncanonical_combination`**。旧 Stage III 只能作为上一确认阶段的历史上下文。本次没有生成新投影、重放记录或对最新业务日做正式认证。当前源码允许有效 P0 的非典型组合发布空阶段；只有真实 P0 无效才拒绝发布（`p0.py:70–117`；规格 `spec.md:106–107,156`）。目前该源码路径仍先被 v3 guard 阻止。

## 3. 派生与宏观解释并没有替代三核心

可逐 ID 重建的例子：`CN_DR007_POLICY_SPREAD` 派生 ID `1f1c5edc4e55f092e65e459185d25211e41bbebe9e87478617a7842457ece4c1`，公式 `dr007-policy-spread-v0001`，SYSTEM cutoff 与投影相同：

- 输入 `8e671261052c580f15b29a9306a8f0071cc53a88cf9041d4a87cff09eecd044f`：8/3 `CN_DR007=1.4204%`，来源 `tushare:repo_daily:weight:2026-08-03`。
- 输入 `9423b3ffea1c5148b6102cd076e3545d6e324e9407eb993bd89d0b567cbc3bfa`：8/3 央行 7 日操作利率 `1.4%`，来源声明绑定央行原件 SHA256 `ac547ddd5e887f9b1fd4b65cbb8247bcd07e5470b71bd9fac26e5c2d521ad87a`；该原件在 CAS 中存在并验 hash 一致。
- `(1.4204−1.4)×100 = 2.04 bp`，库内为浮点数 `2.0400000000000196`。代码：`context_projection.py:650–676`。**抽查实际结论：没有发现这条派生的减法、单位换算或输入 ID 错接；它可以追踪，不代表输入已通过新的官方实值/PUBLIC 认证。** 当前采集源码 `tushare_context.py:534–555` 请求并过滤 `DR007.IB` / `repo_maturity=DR007`，不是拿任意 repo 行作为 DR007；但本次未请求官方 DR007 样本，未将 1.4204% 与其官方当日值重新比较，也没有验证该来源声明的 `2026-08-03T03:00:00+00:00` 公开时间。央行政策率原件 CAS 可校验，只能证明这一个输入的原件留存。

当前投影完整度是 degraded，保存 `p1_evidence_incomplete:34/42`、`p2_evidence_incomplete:2/13` 等警告；宏观确认为政策传导冲突、信用 mixed、过热 cooling、价格 producer_diffusion。它们属于解释层。`domain/stage.py:36–37` 明确舍弃 contextual_evidence，不允许这些宏观状态修改 Stage III。

## 4. 旧输入值是否值得采信

**可支持的范围：** 旧值、版本、来源标签、as_of、派生 ID 和结果链条可以重建。三核心 8/3、8/28 的共 6 个末日值还与已存完整历史标准化 CAS 制品 `0605b3d9a8f2a9eb196fd220a03f90cf31d0acb464430569ead89287702ab61b` 相等；该制品验 hash 一致。它是标准化历史 JSON，不是逐次 HTTP 原始响应，也不是官方对这些值的独立复核。

**不能支持的范围：**

1. **P0 公开时间来自硬编码。** `core_history.py:126–127,170–177` 和 `worker.py:1407–1434` 为每个业务日构造 07:30 UTC，即北京时间 15:30，并同时写 release/public。当前 8/3 三个末日 claim 都是 `2026-08-03T07:30:00+00:00`，实际 fetched/available 是 `2026-08-31T20:47:04.548204+00:00`。本次看到的采集路径没有读取来源实际发布时间。`CONTEXT.md:161–175` 要求可靠官方公开时间，只有日期用次日本地日，无可靠日期则为空，明确排除计划/推测时间。因此不能用这些固定钟点证明当时公众已经可得。
2. **当前 Worker 的系统可用时间也提前取样。** `worker.py:1394` 在每个核心 API 请求和验证之前取一次 fetched_at，随后于 `1435–1436` 写成 fetched/available；这与 `CONTEXT.md:169–171` 的“首次取得并通过校验”定义不符。历史投影 cutoff 晚于这些操作，其重算一致不消除中间时段 SYSTEM 查询的语义问题。历史全量采集的时间取样位置不同，不能将这一点泛化为所有来源路径。
3. **当前刷新保存 hash，未保存对应内容。** 最新三条核心 retrieval attempt 各记录 160 条观测及 normalized_hash（`worker.py:1441–1461`）；这三个 hash 对应的 CAS 文件均不存在。已有全量标准化历史制品可比值，但不能冒充这三次刷新请求的原始字节。链路目前能追到 source claim、来源接口身份、标准化值和旧全量制品；逐次原件还原能力未由此证明。
4. **v3 仍携带已被否定的认证声明。** `source_contract_review.py:73–107` 按五组已知问题拒绝新计算；`docs/research/market-source-semantic-review-2026-09-05.md:70` 对确认指数统一 15:30 已明确指出缺少发布事实。ADR0013 第 7、9 行要求官方语义/字段/单位/统计期/发布时间/许可核验、新不可变目录及模型、120 中国交易日 PUBLIC 重放、显式激活。认证标签、数据条数齐全和来源 hash 都不能代替这些条件。

因此不能把当前旧输入整体称为已认证、无前视且可据以发布当前结论。也不能反向声称三个旧收盘数值本身已被证明错误；本次证明的是可重复性，以及尚未满足的信任边界。

## 5. 报告和验收分别证明了什么

对生产库全部 **8 份、正文均保留**的历史报告，选择核验了 bundle SHA256、报告/投影/bundle 的模型与目标日身份、bundle cutoff 与投影 SYSTEM cutoff、正文 report_identity、核心状态一致性、三核心机械映射与存储阶段、正文 formal_stage_basis、引用是否在白名单内；这些结构化检查全部通过。没有重新调用 AI，也未将这一检查称为每条宏观叙述的独立事实核验。

全部 8 份都是 `deterministic`、`completed_degraded`，不是实际双 CLI 成功产物。最新报告绑定 `bundle-b8d0d3b7d18b284cf3f9`，hash `44e6f39226dada99b01a1b7fceb68f61a9be715404b50d27da3110bd2e6ab7ba`。其 Codex attempt 为 `timed_out`（20:57:10 至 21:01:43 UTC），Claude attempt 为 `cli_not_installed`；两者 tool_events=0、output_hash=null。报告仍完整保留确定性事实骨架和 5 项治理缺口。这符合双失败简版的降级语义，不是 AI 分析质量的成功证据。

库内最新 `model_replay` 是 8 月 31 日 20:37:03 UTC 的 replay_id=18，旧 active 对比 `model-v0011-d5b30f6c4855e04a`，2026-03-09 至 2026-08-28 恰好 120 日，passed=1、差异为 0。它早于 9 月 5 日来源审查，不能覆盖后续查明的认证缺口，也不是这次重新跑通的记录。

既有 `verification-resolution-2026-09-05/acceptance.json`：35 个 REG 全通过、network_requests=0，CAS `ff7c56f8eef9afc0128683edc25845e53be227f46e5d84a4400035c4cc8d8836` 验证一致；`acceptance.py:114–140` 明确在临时目录/SQLite 做回归。`fixture-recovery.json` 明确 acceptance_only=true、publication_history_written=false，CAS `cb2ef286585366981cbcc76be4ed74c6a32d1d8141c534b0f33f9bb7b6c7e0f1` 验证一致。与之并列的 `doctor.json` 是 action_required。fixture 证明离线流程与故障处理的行为，不证明生产真实数据的新认证、正式 PUBLIC 重放、真实恢复演练或 cutover 已完成。

## 6. 复核方法和范围

数据库通过 `sqlite3.connect(Path(db).as_uri() + '?mode=ro', uri=True)` 打开，设置 `PRAGMA query_only=ON`、读事务 `BEGIN`。未实例化会执行建表或 journal mode 写操作的 Repository。统计 JSON 保存实际 SELECT、参数、统计时点、关键模块文件 SHA256、模型/投影/快照/报告完整身份、逐资产重算结果、CAS 验证和逐报告检查项。

主要查询缝为 active_model→model_version、current_projection→projection_set→analytical_dataset、evidence_snapshot→source_claim/derived_observation、report_snapshot→evidence_bundle/report_attempt，以及 parent_run/model_replay/system_cutover。数据选值复用了无副作用 `_select_claim_rows`，趋势复用了 `evaluate_trend`，阶段复用了 `derive_formal_stage`；8/28 的 last_confirmed_stage 在取证调用中未注入，仅验证当前组合应为空，不能将其 null 误读为数据库没有历史确认阶段。

尚未做的验证明确保留：没有逐条独立核验三核心 2,345 日的官方原件，没有新网络采样，没有生产端到端执行，没有新模型认证/激活，没有真实 CLI 成功报告，也没有 cutover。这些均不从历史或 fixture 的通过结论推导。

