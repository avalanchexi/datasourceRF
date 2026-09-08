# 核心历史回放的修订版本边界

本轮只读研究，2026-09-08。读取时 HEAD 为 `159a7252cd436f7ddbf2c26b29825e1e1299af35`；包含主代理正在实施的三核心新目录工作树。下述判断绑定文末文件指纹，不表示该 HEAD 单独包含所有所读内容。未运行应用或测试、未查询数据库、未联网；唯一新增文件为本文。

**结论：当前 `evaluate_history` 静态调用链把结束日可见的修订值用于较早日期的趋势计算，存在明确的 PUBLIC 回放前视路径。尚未执行反例，不能写成已复现 RED 或实际历史结果已受影响。** 最小公开反例只需一个旧观测的新 revision；无需改变趋势参数、新建真实来源认证或激活模型。

## 1. 证据链与确切责任边界

| 位置 | 当前行为 | 对本问题的含义 |
|---|---|---|
| [`evaluate_history`](../../src/pring_cycle/model_evaluation.py#L215)，L234–246 | 预加载后，仅按 `requested_end` 的中国日末对三核心分别调用 `metric_series(mode=PUBLIC, as_of=final_cutoff)`；未给结束日时使用 `date.max` | 整个窗口先选定一个结束时版本；无论是否修订，最初公开较晚的历史观测也可能由此进入早期输入 |
| 同文件 [L259](../../src/pring_cycle/model_evaluation.py#L259)–300 | 按统计日建立 `points_by_asset`，所有 `PricePoint` 取 `final_series` 的 `selected_value`，每资产仅计算一次趋势全序列 | 统计日属于早期不代表所选声明当时公开；之后截取前缀无法恢复旧 revision |
| 同文件 [L317](../../src/pring_cycle/model_evaluation.py#L317)–364 | 日循环读取上述预计算 `trend_by_day`，计算方向、阶段、确认延迟等 | 日循环没有再次查询该日 PUBLIC；较早状态与阶段可能随 `requested_end` 改变 |
| [`EvidenceRepository.metric_series`](../../src/pring_cycle/evidence.py#L804)，L819–865 | PUBLIC 使用 `public_available_at`，预加载按截止时间二分可见行，再调用正常选择器 | 仓库已有按日重新选择能力；不能把问题归于“缓存天然忽略时间” |
| [`_select_claim_rows`](../../src/pring_cycle/evidence.py#L1184)，L1192–1206 | 精确时间过滤后排序，每个 provider 取可见的最新声明 | 同 provider、同观测的较晚 PUBLIC revision 在结束日会替代旧值；早期截止查询仍能返回旧值 |
| [`evaluate_trend_history`](../../src/pring_cycle/domain/trend.py#L132)，L147–180 | 对收到的值计算滚动均线、斜率与连续确认 | 普通正值数据的趋势循环按价格前缀工作，但输入没有声明时间；领域算法无法纠正调用者已选入的未来 revision |

规格已要求 PUBLIC 逐 cutoff 选择且差异不含未来证据，见 [spec.md L142](spec.md#L142)；时间、修订与旧版本边界见 [L96](spec.md#L96)–98、[L124](spec.md#L124)–128。这里不需要新业务规则才能确定“晚公开修订不能改变较早目标日输入”。

影响可经公开上层传播：[`calibrate_model` L91](../../src/pring_cycle/model_evaluation.py#L91) 调用此函数；[`replay_models` L145](../../src/pring_cycle/model_evaluation.py#L145) 对候选和比较模型都调用它。二者同时使用同类错误并不能以差异为零证明无前视。此判断不意味着已有机器验收或生产回放实际出现了错误，仍需反例和真实 vintage 检查。

## 2. 最小公共纵向反例设计（未执行）

建议放在现有 `tests/models/test_model_evaluation_regressions.py`。该文件已有通过 `ModelRepository.create`、`create_candidate(certified_model_v0001_manifest())` 和真实 `EvidenceRepository.append_source_claim` 构造隔离 SQLite 的模式，见 [L89](../../tests/models/test_model_evaluation_regressions.py#L89)–123。复用构造方式，**不复用其 L170 的趋势 monkeypatch**；本例直接调用公开 `evaluate_history` 和真实趋势算法。

模型保持原 v1 的 `120/20/20/1.5/8` 参数，见 [`models.py L72`](../../src/pring_cycle/models.py#L72)–110。这里使用已有内置版本仅为了隔离证明公共软件行为；不解除 v3 禁用，不把 fixture 的 `certified` 标签移交新目录。当前新原件守卫明确跳过内置版本，见 [`evidence.py L245`](../../src/pring_cycle/evidence.py#L245)–258；新目录真实来源路径继续受原件、契约与认证约束。

固定构造如下：

1. 取从 `2026-01-05` 起的 149 个周一至周五日期，序号 `i=0..148`。这是**合成工作日历**，不是中国交易所日历。三核心各有这些日期的旧声明，值均为 `100.0+i`。
2. 每条声明：三个既有核心 metric_id；`metric-catalog-v0001`；`business_day`；`period_start=period_end=days[i]`；`dimensions={}`；`index_points`；`REPORTED_VALUE`；同一个 fixture provider；`certified/validated` 仅限测试。给每个发布独立 `release_event_id`，fixture `source_reference`；原声明 PUBLIC 为各日 `10:00+08:00`，fetched 为 `10:01`、available 为 `10:02`。这些是明确的合成时间，不能解读为真实官方发布制度。
3. 给 bond 的 `i=20`（`2026-02-02`）追加一条 revision：旧值 `120.0`，新值 `100000.0`，统计日与维度不变、provider 不变；新 `release_event_id` 与 revision 引用，PUBLIC=`2026-07-30T10:00:00+08:00`，fetched=`10:01`，available=`10:02`。它在 `i=148` 才公开。**不是改旧行，不复用旧发布事件冒充新的发布时间。**
4. 共 447 个观测、448 条声明，仅 1 个有修订观测。`StoredSourceClaim.observation_id` 应相同，`supersedes_claim_id` 指向旧 claim，`claim_count==2`。对应公开 fixture 范式见 [`test_point_in_time.py L301`](../../tests/evidence/test_point_in_time.py#L301)–332；身份和不可变事件检查见 [`evidence.py L1288`](../../src/pring_cycle/evidence.py#L1288)–1339。

定义 `D=2026-07-28=days[146]`，`E=2026-07-30=days[148]`；cutoff 都是该日中国日末。

| 公共观察/断言 | 独立期望 |
|---|---|
| `evidence.query(revised_observation, PUBLIC, D_end)` | 旧 claim，`120.0` |
| 同查询 `PUBLIC, E_end` | 新 claim，`100000.0` |
| `short = evaluate_history(db, "model-v0001", requested_start=D, requested_end=D)` | D 的核心状态为 `("bull", "bull", "bull")` |
| `long = evaluate_history(db, "model-v0001", requested_start=D, requested_end=E)` | **`long.core_states_by_day[D] == short.core_states_by_day[D]`**；D 仍为三项 bull |
| 同一天阶段 | `long.stages_by_day[D] == short.stages_by_day[D]`；三项 bull 对应既有 `stage_iii` |

当前源码下，最后两个相等断言预计失败：结束日版本使 `long` 在 D 的 bond 为 `None`，其余两项 bull。这个预计必须由主代理实际公开测试确认或否定；本文没有测试日志。

独立算术依据：未修订线性上行序列在 `i=139` 第一次满足 140 个价格；120 日当前均值 `179.5`、20 日前均值 `159.5`。直到 `i=146`，距离仍大于 31%，斜率为正；最近 20 个单日收益率范围小于 0.04 个百分点，因此 1.5 倍标准差远小于上述距离。`i=139..146` 是 8 次连续 bull，第一次稳定态在 D。修订将一个窗口内数值增加 `99880/120`：在 `i=139` 当前均值变为 `1011.833…`、此前均值 `991.833…`，距离负而斜率正；在 `i=140..146` 当前窗口已移出修订点，先前窗口仍含它，距离正而斜率负。两种情况均不满足方向信号，见 [`trend.py L185`](../../src/pring_cycle/domain/trend.py#L185)–192。这个单 revision 足以让早期首次稳定态消失，不依赖负数、冲突、多 provider 或改规则。

这是 **1 日对 3 日观察窗口 + 必要合成预热** 的软件反例，绝不是完成 120 个中国交易日的真实回放。真实来源、认证、历史 PUBLIC 仍需各自证据。

## 3. 修复的最窄边界与必要反例

优先修 `evaluate_history` 的值选择与每日结果构造，不重写数据库 revision 语义、趋势参数或原件采集：

- 每个待评价日 D，用既有 `metric_series(metric_id, PUBLIC, as_of=D_end, definition_version=模型绑定版本)` 重新选择可见声明，并限制统计期 `history_input_start <= period_end <= D`。按这个 D 的可见历史前缀计算 D 的趋势结果；较晚日期可合法使用此前已经公开的修订，较早日期结果不得被回写。不能只给最终版本再加 `public_at<=D` 过滤，否则会丢掉本可选的旧 revision。
- 预热日期和确认状态也必须服从其目标 cutoff；保留原隐藏预热、精确评价范围和计数规则。结束日系列最多用于发现候选日期，不能作为每日取值来源。某日完整性不足应保留既有不完整失败/缺口，不通过删除该日缩短回放区间获得通过。
- 仓库已有预加载增量重选及向过去查询时清空游标，见 [`evidence.py L845`](../../src/pring_cycle/evidence.py#L845)–867；已有缓存与非缓存 PUBLIC 修订一致性测试见 [`test_point_in_time.py L366`](../../tests/evidence/test_point_in_time.py#L366)–411。优先使用该 API；无需新增 vintage 表或改变原件 schema。先保证逐日正确，再在不改变 cutoff 的前提下处理长窗口性能。
- 当前 `evidence_hash` 只绑定最终选值与范围，见 [`model_evaluation.py L269`](../../src/pring_cycle/model_evaluation.py#L269)–286。修复后的验收指纹必须绑定实际每日选值路径，至少包含目标 cutoff、定义版本、所用观测/claim 身份及数值；否则“结束日最终值相同、期间发布时间不同”的两个版本仍可得到同一指纹。保持旧已存结果与旧 hash 原样，只为新执行生成新结果；不伪称旧验收已重新通过。

追加的最少边界验证：

| 变体 | 应保留的行为 |
|---|---|
| 将 revision 的 PUBLIC 移到 E 之后或设为未知 | D 与 E 的 PUBLIC 回放均继续使用旧声明；不能用 fetched/available 倒填 PUBLIC |
| revision PUBLIC 在 D 后，但 SYSTEM 更早或更晚 | PUBLIC 按自身时间；单独的 SYSTEM 查询按 available，不把两个时钟合并。已有公共二者不同的例子见 [`test_point_in_time.py L214`](../../tests/evidence/test_point_in_time.py#L214)–246 |
| 当日边界后一微秒的 revision | 当日不可见，次日才可见；复用仓库精确截止选择，不用字符串/SQLite 粗时间重新实现 |
| 原观测首次 PUBLIC 本身在 D 之后，且没有旧版本 | D 保持输入缺口，不能从 E 的完整系列回填 D；这不同于有旧 revision 可回退的情形 |
| 不含任何晚公开 revision 的正值历史 | 原稳定态、阶段与评价计数保持既有预期；原 warmup 用例的内部 mock 调用次数不是新实现的业务契约 |

`evaluate_history` 当前没有 SYSTEM 模式参数。本批只需修其明确的 PUBLIC 行为；不可悄悄改成 SYSTEM 规避缺失，也不必顺带新增一套 SYSTEM 回放接口。如未来显式加入 SYSTEM，应沿用 `available_at`，若另有 PUBLIC 上界则用仓库已有 `public_as_of` 组合重新选旧 revision，见 [`test_point_in_time.py L335`](../../tests/evidence/test_point_in_time.py#L335)–363。

`replay_models` 的比较模型 active 要求仍在 [L131](../../src/pring_cycle/model_evaluation.py#L131)–135，本例选择下层公开评价 seam，完全无需调用激活。原 `metric-catalog-v0003` 否定守卫仍见 [`source_contract_review.py L98`](../../src/pring_cycle/source_contract_review.py#L98)–102。本研究不放宽这些边界，也不授予来源认证。

## 4. 输入指纹与交付

以下为 `2026-09-08T15:40:06.847414+00:00` Windows 标准库读取的精确字节指纹；源码行号属于这一工作树快照。未把正在更新的实施状态文件作为必需输入。

| 输入（仓库根相对路径） | bytes | SHA-256 |
|---|---:|---|
| `src/pring_cycle/model_evaluation.py` | 39345 | `20b23474ea193ea8a4a3997a932bb7dc2620afeddda359a2d78361d903b82fa3` |
| `src/pring_cycle/domain/trend.py` | 8168 | `6b89112ca198fc7952d389d1b6f7a08677a666d0a9b373374296a66ed5d4f134` |
| `src/pring_cycle/evidence.py` | 58457 | `e2166a8e292f6ee5ac12173d8a28072245eac83837cad5b6d29ac395353b2963` |
| `src/pring_cycle/models.py` | 43191 | `685431543eddb886df7c0358f7cf35d15426e950c6972b8cc471101382362646` |
| `src/pring_cycle/source_contract_review.py` | 14620 | `89b47a2c5552609c62957c99db00f7e030fbe7ab15dae57db62399418844dd50` |
| `tests/models/test_model_evaluation_regressions.py` | 13400 | `06df61df878114c3550a663f81a8452804ed52047927389e3ea4d711619d91d6` |
| `tests/evidence/test_point_in_time.py` | 21659 | `5f01b109d7a706bdcd9451b89add33453b52e1229740d72a28cc5827b4fddd48` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |

唯一交付路径：`.scratch/pring-data-acquisition-repair/core-replay-revision-boundary.md`。最终文件 bytes/SHA 由交付消息提供，避免文件自含哈希循环。所有本地链接按本文件所在目录解析；仅做文件存在、行号范围和 SHA 校验，不执行示例或导入应用。
