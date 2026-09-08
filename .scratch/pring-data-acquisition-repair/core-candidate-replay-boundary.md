# 逐日 PUBLIC 候选字段与持续天数：下一软件切片

2026-09-09，只读 research。基点 `dd744ff334f7cae23b092e994d3599b351c188c9`；所读工作树包含主线正在回归的核心原件核验，指纹见文末。只读取源码、规格和已有测试；未运行应用或测试，未联网、写数据库或修改票状态。**本文给出静态缺口和待执行反例，不是已复现结果，也不是票21真实120日回放完成。**

票01已经修好当前投影/API/页面/报告的 v0002 候选天数；其 [验收17–21行](issues/01-candidate-duration.md#L17) 和 [完成记录40行](issues/01-candidate-duration.md#L40) 没有宣布历史回放完成。票21仍要求 [逐 cutoff 候选字段](issues/21-public-replay-120d.md#L6)、[逐日候选持续验收](issues/21-public-replay-120d.md#L18) 和 [可归因且版本绑定的差异](issues/21-public-replay-120d.md#L21)。当前差距是**回放输出与验收链尚未接通候选字段**，无需重新选择候选业务规则。

## 1. 不是单个 dataclass 缺字段

| 必须经过的边界 | 当前源码事实 | 最窄需要接通的内容 |
|---|---|---|
| 单点领域计算 | [`TrendResult` L37–49](../../src/pring_cycle/domain/trend.py#L37) 有 `candidate_state`、真实 `candidate_days`、旧 `persistence_days`；[L96–128](../../src/pring_cycle/domain/trend.py#L96) 已正确重置/确认 | 复用现有连续计数，不改方向算法 |
| 历史领域计算 | [`TrendHistoryPoint` L53–56](../../src/pring_cycle/domain/trend.py#L53) 仅 date/stable/distance；`evaluate_trend_history` [L143–180](../../src/pring_cycle/domain/trend.py#L143) 算了候选方向与天数，却没有返回 | 在每个历史点保留该时点的真实候选方向/连续天数，包括未稳定、确认当日和中断后的零；不能只在序列末尾添加一次 |
| 模型规则加载 | [`model_evaluation._rules` L466–479](../../src/pring_cycle/model_evaluation.py#L466) 没有读取 `candidate_duration_rule_version`，会保留 `TrendRules` 的 v0001 默认值；对照 Worker [L989–1004](../../src/pring_cycle/worker.py#L989) 和 fixture [L235](../../src/pring_cycle/core_fixture.py#L235) 已加载 | 缺省仅用于旧清单；新清单显式 v0002 必须传到输出解释；显式不支持版本应拒绝，不能静默降到 v1 |
| PUBLIC 分段评价 | [`evaluate_history` L351–418](../../src/pring_cycle/model_evaluation.py#L351) 用逐 cutoff 前缀与分段趋势，仅提取 stable 状态及阶段；[`HistoricalEvaluation` L49–60](../../src/pring_cycle/model_evaluation.py#L49) 无逐日候选字段 | 候选方向/天数要和 stable 同一天、同一 PUBLIC vintage、同一分段输出；只输出评价窗口内的日行，隐藏预热仍用于计数 |
| 平行比较 | [`replay_models` L183–217](../../src/pring_cycle/model_evaluation.py#L183) 只比较 stage/core/context；`ParallelReplayEvaluation` [L64–75](../../src/pring_cycle/model_evaluation.py#L64) 也无候选输出 | 增加按日、按资产的候选方向与显示天数差异；缺字段/漏日与合法非零差异分开 |
| 校准结果与验收保存 | [`calibrate_model` L113–126](../../src/pring_cycle/model_evaluation.py#L113) 只返回4个稳定性总数和输入元数据；[`record_acceptance` L327–359](../../src/pring_cycle/models.py#L327) 固定白名单，会丢弃额外候选字段 | 将新输出文档的 schema、hash、覆盖分母和规则版本写入新结果，并参与 result_hash；只有上层加字典键不够 |
| 回放持久化和 CLI | [`ReplayResult` L57–69](../../src/pring_cycle/models.py#L57)、[`record_replay` L547–652](../../src/pring_cycle/models.py#L547) 仅保存汇总；CLI [L356–381](../../src/pring_cycle/cli.py#L356) 手动逐字段转发后输出 asdict | 明细引用/指纹和候选差异要穿过 record API、表存储、返回结构及 CLI，不能内存可见但落库丢失 |
| 重新验算的机器门 | [`_hardened_machine_acceptance_matches` L841–857](../../src/pring_cycle/models.py#L841) 重建固定白名单 hash；[`_hardened_machine_replay_matches` L894–905](../../src/pring_cycle/models.py#L894) 只核3类差异和日历；activate 的 [L429–476](../../src/pring_cycle/models.py#L429) 也固定查询/转发字段 | 新格式机器结果必须核候选文档指纹与覆盖，不允许旧“未记录候选”的 passed 记录充当本项已验收；更新所有转发点，保留旧记录 |
| 用户事后读取 | API [`/api/v1/models` L237–239](../../src/pring_cycle/web.py#L237) 只列模型；[`/api/v1/stage-history` L241–245](../../src/pring_cycle/web.py#L241) 读取发布历史；CLI只有执行时汇总 | 增加只读的已保存回放明细读取入口。不能让用户为了查看结果重跑，也不能往 stage-history/current projection 填候选回放 |

当前 `evaluate_history` 已有逐日输入 hash（[L326–344](../../src/pring_cycle/model_evaluation.py#L326)），这并不能证明候选输出已被记录。相同输入、不同输出语义可以得到不同显示；本切片需同时绑定模型/规则与输出。新目录准入本来就要求 v0002，见 [`candidate_admission.py L128–133`](../../src/pring_cycle/candidate_admission.py#L128)，因此回放漏读该键是实际软件边界，不是需要用户另作规则选择。

## 2. 推荐一个最小持久输出契约

建议使用**追加的回放明细文档**，存内容寻址制品并由 `model_replay` 的新可空引用字段关联；校准验收通过同一格式的输出指纹关联其结果。现有表已有 result JSON/可扩展回放列，见 [`models.py L1015–1048`](../../src/pring_cycle/models.py#L1015)。不改旧 JSON、旧 hash、旧模型清单或旧投影。

最小文档包含：明确的新 `schema_version`；模型ID与manifest hash；PUBLIC模式；真实评价起止、calendar hash；已有逐 cutoff 输入路径 hash；每个模型的 duration rule版本；每个评价日的 cutoff；三资产各自 `stable_state`、`candidate_state`、`actual_candidate_days`、按该模型输出语义得到的 `candidate_days`、独立 `confirmation_threshold_days`；阶段；两侧逐字段差异。文件由纯计算结果确定性生成，固定日序/资产序，hash不含耗时或写入时钟；执行时钟作为关联元数据保存。

`actual_candidate_days` 为算法内部真实待确认连续天数；`candidate_days` 则用于保持已发布模型的显示语义。两者分开可直接解释旧版差异，不把 v1 的门槛值伪称真实连续计数。统一输出映射复用/小幅调整 [`TrendRules.candidate_days_for_output` L27–33](../../src/pring_cycle/domain/trend.py#L27)，不要在 replay/Worker/fixture 三处各重写一次版本分支。

| 时点 | 真实候选状态/天数 | v0001 的 `candidate_days` | v0002 的 `candidate_days` |
|---|---|---:|---:|
| 还没有稳定态，候选第7天 | 对应方向 / 7 | 7 | 7 |
| 已稳定 bull，出现 bear 候选第7天 | bear / 7 | 8（既有 `persistence_days` 语义） | 7 |
| 第8个相反信号确认 bear 的当日 | None / 0；stable=bear | 8 | 0 |
| 稳定态后没有新候选，或信号中断 | None / 0 | 8 | 0 |

确认阈值若配置为8，一直独立写为8；不能在第8天确认完成后仍把 v2 的“待确认候选持续”写成8。`candidate_state=None ⇒ candidate_days=0` 是 v2 输出不变量，不能用它把 v1 原样输出判成损坏。缺少新版明细的旧记录应标 `not_recorded/未评估`，不能通过补默认0伪装成完整零差异。

覆盖分母固定为“实际评价日 × 三资产”，每格均有结构化结果；合法无候选是明确 None/0，漏行或漏字段是未完成。隐藏预热不计入评价分母。候选方向差异与天数差异分别按 `(day, asset)` 计数，保留对应逐字段明细；旧v1与新v2合法差异应标注规则版本。**差异非零不自动导致回归失败**，更不能新增“必须零差异”门槛；质量门要求结构、覆盖、输入/输出身份正确，独立固定反例验证算法正确。规格对此已有约束，[spec L99](spec.md#L99)、[L142](spec.md#L142)。

CLI建议延续 `model-replay` 执行入口并返回 replay ID、摘要、明细 hash；再提供一个按 replay ID 的只读详情命令和对应 GET API，通过仓库读取原文档并核 hash。名称可按项目命名确定，不需要新增一套页面。旧无明细的 replay 仍可读摘要并明确未记录。API不是 `/stage-history` 的复用，因为候选回算与发布历史是不同对象。

## 3. 最短公开反例与独立期望（全部待执行）

**第一条纵向 RED：真实 `SourceClaimInput → EvidenceRepository → evaluate_history`，核末日候选输出。**

在隔离临时 SQLite 使用已有 v1 catalog 的 fixture模型，复制清单为独立 fixture model ID，将规则设为 MA2/slope1/volatility1/noise0/persistence8、duration v0002；这是已有 [票01集成测试 L100–109](../../tests/integration/test_candidate_duration.py#L100) 采用的可手算配置，不改正式模型规则。该公开评价接口不要求激活候选，不要用 fake `HistoricalEvaluation` 或 monkeypatch 趋势/仓库结果。

三核心各有18个合成工作日 `d0..d17`，证据维度 `{}`、`business_day`、`index_points`，PUBLIC/fetched/available 均显式合成且每日期满足所需截止；用正确 TuShare metric/API/code 引用。债/商品价 `100+i`，股票价为 `[100..110] + [100,99,98,97,96,95,94]`。真实 PUBLIC声明写入方式可复用 [现有回放回归的修订例](../../tests/models/test_model_evaluation_regressions.py#L404)；新目录原件守卫的纵向回归继续保留，本最小例的内置 fixture 不冒充新来源认证。

对 `requested_start=d17, requested_end=d17`，独立期望：股票 `stable=bull,candidate=bear,actual_days=7,display_days=7`；债与商品均 `stable=bull,candidate=None,actual/display=0`；Stage III。当前公开 `HistoricalEvaluation` 根本没有这些逐日字段，因此应在输出契约断言失败；这是静态预测，尚无本轮RED日志。仅测试 `TrendHistoryPoint` 新增属性存在不能替代这一公开纵向。

单日领域期望已有独立注释与数据，见 [`test_trend_state.py L55–100`](../../tests/domain/test_trend_state.py#L55)。应把这些期望扩到历史日行和持久结果，而不是以 `evaluate_trend(prefix)` 的计算值作为所有期望。其 [L103–120](../../tests/domain/test_trend_state.py#L103) 前缀一致性测试可保留为补充，但当前只比 stable/distance，也不是独立正确性证明。

| 完整短序列（共享前缀 `[100..110]`） | 末日独立期望（v2） | 为什么 |
|---|---|---|
| 不加尾部 | stable=bull，None/0 | 前缀有8个上行确认信号，之后没有待确认候选 |
| 加 `[100,99,98,97,96,95,94]` | stable=bull，bear/7 | 7个连续相反信号，未达到8 |
| 再加 `93` | stable=bear，None/0 | 第8个确认完成；pending计数清零 |
| 加 `[100,99,100]` | stable=bull，None/0 | 末两日MA均99.5，斜率零使信号中断 |
| 加 `[100,99,100,98]` | stable=bull，bear/1 | 中断后重新开始，不延续此前2天 |
| 加 `[100,99,100,101]` | stable=bull，None/0 | 新信号与既有stable方向相同，不保持旧bear候选 |
| 加 `[100,99,98,97,96,95,94,93,94,95]` | stable=bear，bull/1 | 93确认；94使MA持平中断；95开始新的bull候选 |

7→8 行的 stable 变化仍按既定三核心映射。若本例股票转bear而债/商品仍bull，`bull,bear,bull` 是非典型组合，阶段应为空；不能为候选字段验收硬配 Stage IV。

**后续 revision 反例：** 上述股票 i15（原96）追加为100，但 PUBLIC 在 E=d18 才可见，原值和旧声明保留；d18当日原始价93。D=d17 的短回放和延长到 E 的回放，D 都必须维持 bear/7。E按新可见前缀计算：i15变成bull信号、清掉bear候选，i16/i17/i18分别为bear第1/2/3天，故 E 为 `stable=bull,candidate=bear,actual/display=3`；不能沿用未修订前的7再加1确认。既有 [PUBLIC分段 L351–358](../../src/pring_cycle/model_evaluation.py#L351) 必须同时保留这些日候选，不能把修订后前缀中重算出的D=2覆盖此前D=7。revision在E之后或PUBLIC未知的变体，应继续在E正常确认bear、候选None/0。

保存第一次明细后再追加revision，旧明细bytes/hash应保持，新的输入路径与输出文档可不同。明细任意改一格候选天数、漏掉一个资产日行或只改规则版本，应使hash/结构/机器再验算发现不匹配；不能仅核差异总数相等。只改变 duration v1/v2、价格和趋势参数相同的比较，stable/stage差异可以为0而候选显示差异非0，这正是当前三个汇总计数不能覆盖的情况。

最终公开联通应为：`main(["model-replay", ...])` 在合法隔离比较基线下真实计算 → `record_replay` 持久保存 → 新只读仓库/CLI/API按 replay ID 读回同一明细/指纹。生命周期fixture可参考 [票01 L110–125](../../tests/integration/test_candidate_duration.py#L110)，但不得为本次候选输出反例预先手填一条 passed replay 代替被测执行；更不能解除实际 active门。`model-accept` 也必须能读到绑定后的新输出摘要，未知候选审查不能再被固定白名单消掉。

## 4. 本切片的完成边界

上述规则装载、历史逐日输出、PUBLIC分段、差异/结构验收、追加保存与只读读取全部接通，才可称“候选字段回放软件已覆盖”。仅字段出现、内部算法测试通过、当前页面显示7或保存总差异数都不足。旧模型/旧结果保持原样；新格式缺件不标通过，真实来源/原件/时间/认证守卫和合法比较基线要求不变。

范围限定于资产待确认 `candidate_state`、持续天数和独立确认门槛。`candidate_30d` 是独立观察轨道，不能当作该字段的替代品，也不在本切片重做12月代理或其他P1。仍未具备的真实候选与来源PUBLIC历史继续按票19/21保留，合成18日或147日反例都不等于2026-03-09至08-28精确120个中国交易日的真实回放。

## 5. 输入指纹与本文件验证

采样时间 `2026-09-08T17:03:50.895906+00:00`（中国09-09 01:03）。票01/21按本轮读取快照引用；它们的后续状态更新不追改本报告。

| 输入（仓库根相对路径） | bytes | SHA-256 |
|---|---:|---|
| `src/pring_cycle/domain/trend.py` | 8168 | `6b89112ca198fc7952d389d1b6f7a08677a666d0a9b373374296a66ed5d4f134` |
| `src/pring_cycle/model_evaluation.py` | 42229 | `80d85bc012cd5efbd5c551b5678cec064ae55db03127544d617c7a704bb9cbba` |
| `src/pring_cycle/models.py` | 43191 | `685431543eddb886df7c0358f7cf35d15426e950c6972b8cc471101382362646` |
| `src/pring_cycle/cli.py` | 38065 | `a4d8febe8e53e4206f13f9fdea130c87fd8eb85a5b360779a5d3a689d6161cfc` |
| `src/pring_cycle/web.py` | 25800 | `25c24fd6b9e121c1a3601d6f667f897e7eebba3554f58253bfd24660656eaa43` |
| `src/pring_cycle/worker.py` | 58810 | `34a9a9e332872269852a22d7b8f0798a6cb8ab610fd09a9644b4f6739732d96b` |
| `src/pring_cycle/core_fixture.py` | 10710 | `753866e32817a3b4237d4610f5f81bb20aa9e544caf57820f6fcf90853786f83` |
| `src/pring_cycle/candidate_admission.py` | 13193 | `681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4` |
| `tests/integration/test_candidate_duration.py` | 9299 | `5ff95fade3383a594b3bc6860d8a7d75f5ca63777d7ee704a8d22ce5f474b46d` |
| `tests/domain/test_trend_state.py` | 4237 | `5f4e9a41ad4e3713bdf44b3345ed7ac0647085142ab9141a43b63f08830a94d7` |
| `tests/models/test_model_evaluation_regressions.py` | 23867 | `657f9647c19efd6e058c6545bf9c6121120864f36dc154a341eb43bd18ef6b98` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/issues/01-candidate-duration.md` | 2655 | `7ea531f36a605eeadc9f7cfee3915badb5f2da2231a70d66608fe841c368ba29` |
| `.scratch/pring-data-acquisition-repair/issues/21-public-replay-120d.md` | 4345 | `839811ba9a331433fdc4cd9a396596dd5d467c7c8e62c535edaaf8afa7139c16` |

唯一交付 `.scratch/pring-data-acquisition-repair/core-candidate-replay-boundary.md`。本文精确bytes/SHA另在交付消息给出，避免自含哈希循环。下面的链接校验只使用Windows标准库，不导入应用。

本文件本地链接校验结果：38个链接全部可定位，覆盖14个文件；所有行号均在实际源码/文档范围内。14份输入的精确bytes/SHA均与上表一致；本轮未执行任何测试，未授予候选字段验收或来源认证。
