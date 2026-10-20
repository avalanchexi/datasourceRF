# 银行间 raw + normalized 消费校验：下一公开切片

2026-09-09，只读研究；HEAD `99c495a217b66d4bca9d6ceae4688ee69d4382bb`。源码指纹来自本轮实际读取字节，末次取证时钟为 `2026-09-09T06:30:20.586683+00:00`，不是一份原子工作树快照。主线后续改动不回写这些指纹。本轮未运行应用、测试、WSL、SQL 或网络，也未认证真实来源。

**最小实现是银行间专用的联合回执重解析与声明匹配，复用已有 CAS 批读和四处消费资格入口。** 不能把 DR007 加入官方 HTML 解析器，也不能照搬 LPR 的“每份原件各自包含当前标量”：同一 API 的多日回执可能共同承载一份联合 normalized。以下缺口是当前源码的静态判断，公开反例尚未由本研究执行。[规格 Testing 1–6](spec.md#L130)要求真实公共路径、独立期望和实际 RED，不能以检查器单元测试替代消费验收。

## 1. 已有机制与仍缺的内容

| 层次 | 当前确实已做 | 本切片不能误认的边界 |
|---|---|---|
| 公开采集 | [`transmission`](../../src/pring_cycle/tushare_context.py#L603)经 `_call` 捕获 `repo_daily` / `shibor` 精确响应，校验返回码、字段和日期范围，再生成标量。 | 初次解析正确不证明以后保存的 normalized、声明或磁盘原件仍对应。 |
| 入库守卫 | [新目录源契约](../../src/pring_cycle/source_contract_review.py#L289)限制 provider、单位、维度、business_day 起止同日；[入库字段守卫](../../src/pring_cycle/tushare_context.py#L1221)限制 API/source_field。 | 两处都没有重新读取物理响应来证明 `weight` 或 Shibor 三值。不能称“已核原文”。 |
| 收据关联 | [`append_source_claims`](../../src/pring_cycle/evidence.py#L427)核收据 validated、fetched_at 等于关联 received_at 最大值、available_at 不早于 validated_at；只有核心输入另作物理重解析。 | 一条银行间声明可以在身份、时钟都合格时，仍与响应数字不同。 |
| CAS 读取 | [`source_claim_acquisitions_many`](../../src/pring_cycle/evidence.py#L303)返回 exact claim 的全部关联收据及 raw/normalized；每份收据在该批只读一次。任一关联收据无效，整条 claim 返回空 tuple。[`read_content`](../../src/pring_cycle/acquisition.py#L303)核可读与 SHA256。 | 可直接复用，无需新表或另建原件目录；但两个制品各自 hash 正确仍不证明语义对应。 |
| 追溯展示 | [`trace`](../../src/pring_cycle/evidence.py#L1013)由关系表得出 linked/partially_linked。 | `acquisition_status=linked` 本身不是重解析结果；保留诊断引用，不把其当模型资格。 |
| 现有语义 helper | [LPR helper](../../src/pring_cycle/official_lpr.py#L206)、[官方宏观 helper](../../src/pring_cycle/official_context.py#L293)已提供“所选 claim → 全部关联制品 → 有效 claim 集合”的模式和本次调用内缓存。 | 二者的 parsed release 是公告对象；银行间 normalized 是 ContextScalar 数组，不能复用其形状或直接共用解析函数。 |

## 2. 真实字段与批次形状

| metric_id | 必须从 raw 重建的身份与数值 | normalized / claim 契约 |
|---|---|---|
| `CN_DR007` | API `repo_daily`；请求 `ts_code=DR007.IB`，字段 `ts_code,trade_date,repo_maturity,weight`；仅 `ts_code=DR007.IB` 且 `repo_maturity=DR007` 的行；取 `weight`，不取 close、open 或其他期限。 | `source_field=weight`，空 dimensions，`unit=percent`，business_day 起止等于 trade_date；引用 `tushare:repo_daily:weight:YYYY-MM-DD`。 |
| `CN_SHIBOR_ON_1W_3M` | API `shibor`；字段 `date,on,1w,3m`；分别从原行取得三值。 | `on→{"tenor":"overnight"}`、`1w→{"tenor":"1w"}`、`3m→{"tenor":"3m"}`；percent，同日 business_day；引用 `tushare:shibor:字段:YYYY-MM-DD`。 |

这些对应关系由 [transmission 原实现](../../src/pring_cycle/tushare_context.py#L615)拥有事实；[Shibor 既定最低成员](../../src/pring_cycle/metric_contracts.py#L84)是三个期限。`_response_rows` 按响应 fields/items 配对，允许响应字段调整顺序或多出字段，拒绝重名列、缺必需列、错行宽；[`_validate_response_periods`](../../src/pring_cycle/tushare_context.py#L1865)已经验证每个 daily 日期处于该请求 start/end，不能重复声称 daily 没有日期边界。daily 分支没有月/季分支的显式重复期检查，重复/冲突不能在新验证器中用 set 去重后假装全量相符。

[`_daily_scalar`](../../src/pring_cycle/tushare_context.py#L1639)以 `_number` 转换字面数；None 是缺值并导致失败，不是 0；布尔、非有限数不合法。原值真 0 和有限负数不会在当前数值函数中被改成 NA，本切片不新增利率正数业务门。[数值函数](../../src/pring_cycle/tushare_context.py#L2003)与原字段构造应成为重解析共同实现，避免写另一套近似映射。

[`acquire_scalars`](../../src/pring_cycle/tushare_context.py#L152)的确切关系如下：

| 公开回调的正常形状 | 物理回执 | 最终 per-receipt normalized 与声明关联 |
|---|---|---|
| 一次单日 transmission，保留全部返回值 | 1 repo + 1 shibor；4 scalars | repo 数组含 1 DR；shibor 数组含 3 tenor；各 scalar 只关联本 API 收据。 |
| 一次 transmission 返回两日 | 仍 1 repo + 1 shibor；8 scalars | repo 数组含 2 DR；shibor 数组含 6 tenor。 |
| 同一次 acquire 回调内先后调用两个单日 transmission，并拼接结果 | 2 repo + 2 shibor；8 scalars | 每个 DR scalar 关联两个 repo ID；两份 repo normalized 都含同一联合 2 DR 数组。每个 Shibor scalar 关联两个 shibor ID；两份 shibor normalized 都含联合 6 tenor。 |
| 定向只取 DR007 metric | 仍捕获两 API；只交付 DR scalar | [`retrieve_tushare_context`](../../src/pring_cycle/targeted_context.py#L139)在回调中按 metric_ids 过滤。未关联任何交付 scalar 的 shibor 回执 normalized 合法为 `[]`，不应阻断 DR。 |

原因是 `matching` 按 api_name 找整批收据（L173），不是按 scalar 的统计日找单个请求；每份回执 normalized 又按 acquisition_id 归集关联 scalar（L198）。因此“每个 raw 的标量数必须等于该 normalized 的长度”“每个关联 raw 都必须有当前日”都会误拒第三行。也不能要求无关 API 的全部原始值都必须交付，第四行已有生产调用。

原始 `ContextScalar` 还有 release_at、public_available_at、definition_version 和 acquisition_ids。正常 normalized 是数组；若该公开 acquire 批次有字段拒绝，代码还可写 `accepted_scalars/rejected_fields` 对象。当前 transmission 缺值直接抛错，不产生这类自身拒绝明细；新 parser 不应把未知或任意包装默认为成功。要支持混合批次包装时须明确核其 schema，并保留拒绝事实，不能将 rejected_fields 当补 0 指令。[序列化与封装位置](../../src/pring_cycle/tushare_context.py#L184)

## 3. 最窄复用方案及时间约束

建议新增银行间专用的纯解析/匹配层，名称可由实现选择，不要求新的注册表或全系统重构：

1. 从 `transmission` 提取公共生产代码共享的“API 响应行 → ContextScalar”部分；物理重解析核 provider=`tushare`、API、`tushare-context-parser-v0002`、原请求 fields/params、响应返回码/结构/日期范围，并调用相同字段构造。严格对照**请求契约**，同时保留响应 fields/items 合法换序。[capture 身份](../../src/pring_cycle/tushare_context.py#L1096)
2. 外层按 exact claim 批量调用 `source_claim_acquisitions_many`，在一次消费内按 acquisition_id 缓存解析；缺 raw/normalized、hash 不符、收据非 validated、关联空均不合格。先对每份 raw 按自己的日期范围解析，再按声明所关联的**同 API 收据集合**核联合 normalized；所有关联收据都必须可验证，但所选经济标量只需由联合原文中实际对应的响应行证明，不能要求每份不同日期 raw 都含它。
3. 比较 metric、API、source_field、period_kind/start/end、dimensions、value、unit，保留记录重数及来自哪份原文的信息；不以“存在一条同值”掩盖重复、冲突或跨期代用。normalized 的实际交付子集必须由关联 raw 证明；所选 claim 所需成员完整性仍由消费者契约检查。相同 API 联合回执的 normalized 及其 acquisition_ids 必须一致地描述实际交付，不能仅检查“其中包含当前 ID”。无关 API 的合法空交付不参与当前 claim 的资格。
4. 把物理资格结果作为所有四处消费者的同一条件。返回有效 claim ID 集合即可；不要在仓库 `metric_series` 中删除诊断历史，也不要以 source_claim_publication 解析银行间 JSON。`source_claim_publication` 是官方公告路径；当前官方完整性 metric 集合[不含 DR/Shibor](../../src/pring_cycle/official_context.py#L93)。

时间/版本须单独核对，不能简单将 raw 重解析 dataclass 与 stored normalized 整体字节比较：

- 原始银行间 JSON 和 `_daily_scalar` 不提供发布时刻；raw 重建 release/public 默认 None。已有公开测试会在 acquire 回调中明确添加**合成**时刻，normalized 已经记录该断言。须验证 normalized 时间是有时区值或 None，并与所选 claim 的可证明断言相符；raw 默认 None 不能把这类正例全部拒绝，也不授予真实来源时间认证。
- normalized 的 definition_version 默认 None 合法；入库时由已登记的新目录 version 赋予 claim。若 normalized 显式给了版本，则必须匹配，不能接受任意字符串。acquisition_ids、来源引用和字段也须匹配 exact claim，不能把整个元数据部分全部忽略。[入库版本检查](../../src/pring_cycle/tushare_context.py#L1193)
- [`ingest_context_scalars`](../../src/pring_cycle/tushare_context.py#L1289)在物理同值/首次取得时可保留显式 PUBLIC；变值且缺可成立的新发布时间时，把 claim 的 release/public 两者降为 None，normalized 可仍记录原回调时刻。允许这种**保守降级**；claim 有任一已知时间时要与 normalized 的对应时间对照，不能从 normalized 再抬升一个已降级 claim，也不能让 claim 比 normalized 更早或凭空已知。
- fetched_at 取关联 receipt.received_at 最大值，available_at 至少为全部 validated_at 的最大值、可被真正 append 时钟推迟。[入库边界](../../src/pring_cycle/tushare_context.py#L1331)已有实现；新校验不可要求 normalized 具备它本来没有的 fetched_at，也不可把 available_at 强行等同 validated_at。
- `[PUBLIC, cutoff]` 与 `[SYSTEM, as_of]` 选择之后，只核**该次所选 claim**的 exact acquisition。后续新修订不应反向替代早期 PUBLIC；未知 PUBLIC 可在普通 SYSTEM metric_series 留存，却仍不能通过历史目标投影，因为 [TargetBoundEvidenceRepository](../../src/pring_cycle/context_projection.py#L574)对 SYSTEM 也叠加目标日中国日末 PUBLIC 上界。
- 先以当前可见期次选最新，再核原件/quality；坏最新 DR 不能删掉后回取旧日。现有新目录 [`_latest_certified_point`](../../src/pring_cycle/context_projection.py#L1356)已经先保留最新质量状态再判定；不应把这次进展撤回。内置旧目录的分支兼容、旧 v3 隔离、候选认证/active 门保持既有边界。

## 4. 四处实际消费边界

| 入口 | 当前读取链与缺口 | 下一公开可见结果 |
|---|---|---|
| 检索/Worker 本地命中 | [`ModelInputSelector.select`](../../src/pring_cycle/search_evidence.py#L100)已有 core、LPR、官方宏观、RRR、仓单校验；DR/Shibor 仍走普通 selected/value/certified/quality 分支，未调用银行间制品重解析。[Worker 本地检索](../../src/pring_cycle/worker.py#L759)与[定向取得完成判定](../../src/pring_cycle/targeted_context.py#L154)都复用它。 | 坏所选 claim 不进入 selected_claim_ids，所需成员计缺，complete=false；不得因本地数据库已有值而认定已补齐。其他 API 的完好成员可继续返回。 |
| 原报上下文及方向父项 | [`_metric_rows`](../../src/pring_cycle/context_projection.py#L1379)目前只将 LPR/官方宏观/RRR/仓单制品不合格纳入处理。DR/Shibor 原报和 previous 方向父项未有对应完整性集合。 | 最新坏行 source_failed，可保留诊断值/claim；坏前期不得作为方向父项。实际采用以 [`model_input_observation_version_ids`](../../src/pring_cycle/context_projection.py#L515)为准，不能删除全部诊断 observation_version_ids 来假装已处理。 |
| 政策利差派生 | [当前 L854–892](../../src/pring_cycle/context_projection.py#L854)仍从 series 单独取 DR；OMO 最新 rate 已新增 official helper，不再是未校验。 | 在做差前核 DR 同一资格，坏 DR 不产生合格 CN_DR007_POLICY_SPREAD 或新的合格派生父项链；不得回退旧 DR 或恢复旧已存派生结果。 |
| PUBLIC 组件回放 | [`evaluate_context_replay`](../../src/pring_cycle/model_evaluation.py#L802)逐中国日末调用选择门与 PUBLIC 投影；[`_context_selection_gaps`](../../src/pring_cycle/model_evaluation.py#L1091)目前专用完整性分支只覆盖既有几类，DR/Shibor 尚无银行间分支。 | 对受影响的所选成员增加对应 side/metric 的 invalid gap；输出中坏 claim 不成模型采用，完好 comparison 不被误伤。仅修投影但回放门无 invalid，或仅修回放门但输出仍采用，都不足以收口。 |

DR007 变化会影响政策利差，因为 [ContextReplayScope](../../src/pring_cycle/context_replay_scope.py#L10)明确列出两个父项；Shibor 独立参与 transmission。回放测试应实际让新旧来源定义有差异，保留公式依赖，不把两个只有 catalog_version 不同、其他定义完全相同的 manifest 当作已触发组件回放。跨日预加载只减少查询，不能拿窗口末最新版替代每个 cutoff。优先本次消费/回放内按 receipt 身份和 hash 复用解析结果；不要新增跨运行永久正缓存，使下次 CAS 损坏无法被观察。

## 5. 可直接执行的公开反例顺序（本报告未执行）

现成基线是 [`test_registered_interbank_acquisition_preserves_public_boundary`](../../tests/models/test_candidate_admission.py#L1771)：公开候选登记 → `transmission`/`acquire_scalars` → metric_series/trace → RunRepository.submit → select_retrieval_input → build_context_projection。它已有 2 transport/4 claim 和 PUBLIC 已知/未知断言，但不足以证明损坏后拒绝或派生资格。测试只在隔离运行库模拟外部 transport，不读取账户；合成 PUBLIC 应在回调返回前设置，随最终 normalized 一起归档。

| 顺序 | 最小改造与独立断言 |
|---|---|
| 1. 单日物理损坏 | 先证明 DR=1.3859、Shibor 三期限完整与模型采用，再由公开收据定位该 API 的 raw/normalized 制品，分别损坏和移走测试制品。检索 incomplete；相应原报 source_failed；坏 ID 不入模型采用。损坏 repo 不应误伤不关联它的 Shibor；损坏 shibor 应影响其三个期限而非假装仅一个成员有问题。 |
| 2. 两个 hash 都正确但语义错 | raw 保持 DR `weight=1.3859`，在公开 acquire 回调把返回 DR scalar.value 改为 `1.3806`，照常生成合法 hash 的 normalized 和同值 claim。当前入库字段守卫不会证明数字；新消费必须由原字段拒绝。这比只写坏字节更直接检验重解析。Shibor 可在回调调换 overnight 与 3m 的 value，保留其各自字段名；必须拒绝错配，不能靠 1w 那一值正确放行整个三成员集合。 |
| 3. 先保多日正例再加坏关联 | 覆盖第 2 节三种多日/过滤形状及响应列换序；两单日 transmission 的正例明确 4 receipts/8 scalars、每 API 两个关联 ID。第二份同 API 回执坏时，不能只核第一份；联合 normalized 有多期并不意味着当前期超出其实际对应 raw 请求。不同采集批次的旧期原件不受牵连。 |
| 4. 派生不绕过 | 直接扩展[现有 OMO 最新父项公共用例](../../tests/models/test_candidate_admission.py#L3482)，将损坏对象换成 DR 的收据；保留原 OMO 正反例。正确值 −1.41 bp，父项恰为 08-28 DR 与 08-28 OMO rate。坏最新 DR raw/normalized/quality 不能退回另一个旧日；仅同值断言不足，必须核 input_observation_version_ids 与 derived_trace。 |
| 5. PUBLIC 组件正反例 | 借[现有 LPR 回放公开 seam](../../tests/models/test_candidate_admission.py#L4993)或[PMI seam](../../tests/models/test_candidate_admission.py#L2436)构造独立登记的比较/候选来源变体，在公开 evaluate_context_replay 中检验 gap 和逐日实际采用。分离两侧 CAS（可改变合成响应中的无经济影响 JSON 元数据/编码，保持 4 独立数值），避免破坏共享 hash 同时伤两侧。组件临时 manifest 的范围选择只用于该公开组件测试，不能写回存量 manifest 或绕全模型门。 |
| 6. 时间/修订/缺成员 | 保留未知 PUBLIC、已知合成时刻前后、新目录 definition 默认 None、同值再取得、多收据最大验证时刻、变值修订的 PUBLIC 降级正例。Shibor 缺列/None 走真实采集失败，不补零；过滤掉一个 tenor 的合成交付至少由现有三成员选择契约判不完整。后续 PUBLIC 已知版本用显式的合成新版本声明和对应 normalized 构造，再检验早期 cutoff 仍选旧版本；不能误以为给变值回调一个新时间就能越过现有保守降级分支。 |

已有[政策利差测试](../../tests/models/test_candidate_admission.py#L3585)现在确实断言两个父项、derived_trace、raw/normalized/invalid_quality 后不再生成利差；这是主线新增代码/测试事实，不是本研究重跑结论。前份[政策利差边界报告](policy-spread-public-fixture-boundary.md)的“OMO 尚未接原件、最新 quality 会回退”属于更早快照，已由当前源码取代，不再作为本批缺陷陈述。

## 6. 最少真实数值锚点与原件

| 既存原件 | 本轮独立读取的字面锚点 | bytes / SHA256 |
|---|---|---|
| [CFETS DR007 JSON](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d) | `data.lastDate=2026-08-28`；`records[instrmntCd=DR007].wghtdAvgRepoRate="1.3859"`，不同字段 `clsngRepoRate="1.3806"`。 | 1425 / `d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d` |
| [CFETS Shibor JSON](evidence-13/365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62) | `records[showDateCN=2026-08-28]` 的 ON=`1.3390`、1W=`1.3870`、3M=`1.4300`。 | 2112 / `365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62` |
| [08-21 PBC 公告仓库副本](evidence-macro-derived/d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834#L26) | description 字面“950亿元7天期…1.40%”，页头 L327 `2026-08-21 09:20:30`；已有逐表审计定位保留。 | 30798 / `d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834` |
| [08-28 PBC 公告](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a#L26) | description 字面“200亿元7天期…1.40%”，另有隔夜操作，不能混作 7 天；页头 L327 `2026-08-28 09:20:30`。 | 31000 / `ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a` |

四原件共 **65,335 bytes**，本轮 SHA 与文件名 4/4 相符。独立手算 `(1.3859 − 1.40) × 100 = −1.41 bp`；误取收盘为 −1.94 bp。两个 OMO 日率相同，旧事件回退只能用父项 ID 可靠区分。字段单位、请求来源和历史时间边界沿用[已根核的样本说明](policy-spread-public-fixture-boundary.md#L7)：CFETS 原文提供数值锚点，**不是 TuShare 历史交付原件**，其响应生成时间及 `publishedTime=2200` 不是当日首发证据。以上离线合成 TuShare transport 仅验证软件，不给真实 PUBLIC、来源认证、120 日重放或 active 切换授予通过。

## 7. 读取快照指纹与交付自检

下面仅记录拥有结论的输入快照；不是要求主线继续保持同一工作树。代码行号亦绑定这些读取版本。

| 输入（相对项目根） | bytes | SHA256 |
|---|---:|---|
| `src/pring_cycle/tushare_context.py` | 76846 | `5a642d4a7275c8991d76f6e5ec24f271ff1fc8693e213fc7abeca26d0602c443` |
| `src/pring_cycle/evidence.py` | 60796 | `d27332e14065b179f510c6253e06088f376341349657b598bc692070d9c35ec2` |
| `src/pring_cycle/acquisition.py` | 14584 | `ed81eef2b153417009c0beb356be64bbe8fd164a9f3ea0d6eafe9cdc66ad69f8` |
| `src/pring_cycle/search_evidence.py` | 18220 | `81a6b6fdcb4482de7ae33d075eb0990fab9a7b2f1f8b51635d8153f0a0814bcb` |
| `src/pring_cycle/context_projection.py` | 86437 | `7bad11570abec2cabc7cb1a91f496dd85a5ae738c4e3ed592298a547ce594df4` |
| `src/pring_cycle/model_evaluation.py` | 49072 | `2beb799b373e3e834ea1ad92e466a7b537229ec2ffb49940f7039ed5336684c8` |
| `src/pring_cycle/official_context.py` | 84300 | `fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11` |
| `src/pring_cycle/official_lpr.py` | 19119 | `9f7339b36e288cbe808299a76c8b3a61fa67683197245112a2319f8982b4936f` |
| `src/pring_cycle/targeted_context.py` | 6396 | `3601a81cd1b505c38f4762cf2c885ee2214851ec8b5f3dd523eb35b124a5cdeb` |
| `src/pring_cycle/source_contract_review.py` | 14630 | `c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772` |
| `src/pring_cycle/metric_contracts.py` | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| `src/pring_cycle/worker.py` | 58810 | `34a9a9e332872269852a22d7b8f0798a6cb8ab610fd09a9644b4f6739732d96b` |
| `src/pring_cycle/context_replay_scope.py` | 3580 | `588b5fc7e823334b1fdcc1d01e03a6659d10c652f96c7aeaccc288e1c762cb10` |
| `tests/models/test_candidate_admission.py` | 258285 | `09ca0df672257e60f0974cedc51d34acb528b5745fa0f9c598bc4201f7f3c9af` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/policy-spread-public-fixture-boundary.md` | 11775 | `04d3f195476bfb5a32d09d8f1047bc04d2b5ee34f836581dde663fa13c4298b3` |

唯一交付文件为本 Markdown；未新增原件或复核脚本。交付前用 Windows 标准库只读核 UTF-8、本地引用存在及行号可定位、4 原件 SHA/长度和本文件 bytes/SHA；不重新核对主线正在变动的源码与历史指纹是否相同。实际应用/测试/网络请求数均为 0；不计入 Tavily/Exa 分母。

自检结果：45 个本地链接、20 个唯一目标文件均可解析；16 条读取快照指纹；4 份原件共 65,335 bytes，SHA 全部相符。UTF-8 无替换字符或编码损坏问号串。最终本文件 bytes/SHA 随交付消息提供，避免自引用哈希。
