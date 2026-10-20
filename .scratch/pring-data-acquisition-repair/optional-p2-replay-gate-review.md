# 可选 P2 是否被新模型回放与激活误设为硬门

2026-09-10；research，只读一手规格、源码、现有测试及已存 Treasury CSV。未运行应用、WSL、pytest、SQL 或网络，未改应用、测试、数据库、旧证据。本文件中的反例是**可执行设计和静态推导，尚未实际运行 RED**；不以旧研究文档为规则决定。

## 结论

**存在明确冲突。** 在本修复项目要求的“完整 61 项目录、全部 8 个公式、新来源认证包”的公开准入路径中，现行代码把 UST 两个纯 P2 父项及可选利差的可用性提升为整个新模型的回放硬门。未认证 UST 被认证预检挡住；即使定义已认证，逐行 PUBLIC 未知仍被证据覆盖门挡住。后续公式可用性与持久输出校验还有同类约束。失败进入持久回放后，激活门正确拒绝该候选。因此要修的是**机器验收对“必需输入”的错误分类**，不是放开 activate、伪造时间或删除完整公式。

这一结论有范围条件：并非每个任意新 model ID 都必然触发。若候选与比较对象的定义签名、来源包和公式均不触发上下文变化，scope 可以不要求上下文回放；但当前正式修复准入要求新目录及与新 manifest 绑定的包，包变化把全部 P1/P2 纳入 changed，完整 8 公式随之进入受影响范围。不能借相同包、删公式、换成残缺模型规避本项目验收。源码依据：[范围生成](../../src/pring_cycle/context_replay_scope.py#L41)、[完整准入合同](../../src/pring_cycle/candidate_admission.py#L96)、[包绑定 fixture](../../tests/models/test_candidate_admission.py#L59)。

**CN_GDP 不能按纯可选 P2 放行。** 它的目录优先级仍是 P2，但它是 P1 指标 CN_CREDIT_IMPULSE 的必需分母父项。应按 P1 派生结果的依赖闭包要求其认证、PUBLIC、窗口与原件完整性；不需要把 GDP 改成 P1，也不能把 GDP 八字段正确获取当成跨修订 YTD 可相减的证明。

## 1. 规格决定了什么

| 一手依据 | 本题约束 |
|---|---|
| [spec 问题边界](spec.md#L16)、[实施 17](spec.md#L107) | 禁止通过把可选背景指标全部设为必需完成修复；P2 缺口不得新增核心/P1 硬门。措辞覆盖未获可靠来源的公开渠道，不能缩读成“只有付费 P2 才可缺”。 |
| [票 14 验收](issues/14-p2-availability.md#L15) | 13 项 P2 分类及诚实状态；未认证、未授权、未发布、源失败、陈旧分别显示。明确允许受限渠道仍暂缺时完成状态交付。 |
| [spec 实施 33](spec.md#L123) | AI 解释成功另行验收；合法降级运行仍合法。这里同样要求区分“功能/解释未完成”与“新增整个系统硬门”，不能由“最终要补齐来源”推导所有运行必须等齐可选值。 |
| [spec 实施 34–35](spec.md#L124) | 全定义、来源、规则、公式和执行指纹必须绑定；固定 120 中国交易日及必要预热，不删公式、不缩窗。本条要求完整身份和真实结果，不要求每个可选公式每个 cutoff 都有数值。 |
| [CONTEXT 正式阶段](../../CONTEXT.md#L7)、[P1 认证完成](../../CONTEXT.md#L263) | 三核心决定阶段；42 项 P1 完成具有独立要求，可选 P2 缺口不等于 P1 完成失败。 |
| [CONTEXT P2](../../CONTEXT.md#L267) | P2 实值进入正式投影仍要来源认证；“可不阻断”不等于“未认证实值可采用”。 |
| [ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md#L7)、[CONTEXT 可认证回放区间](../../CONTEXT.md#L71) | 保留不可变模型、认证区间、质量/回归/稳定性验收、显式批准和发布历史。ADR 没有把可选背景值全部可用列为认证区间的新增定义。其通用“来源认证”应与上述明确 P2 例外共同解释。 |

[Testing 2–6/11](spec.md#L133)要求真实公开链路、逐 cutoff、证据与差异；UST 缺口也应作为可读结果接受比较。允许缺口绝不允许把缺口写成 available/current、伪造数值/父项 ID，或跳过整个上下文回放。

## 2. GDP 与 UST 的依赖事实

| 项目 | 目录身份与公式依赖 | 适用验收 |
|---|---|---|
| CN_CREDIT_IMPULSE | [P1 列表](../../src/pring_cycle/catalog.py#L88)；[credit_impulse 父项](../../src/pring_cycle/context_replay_scope.py#L10)为 CN_SF_TOTAL、CN_GDP。 | P1 结果不能被透明缺口冒充完成；其 GDP 父项必须满足相同目标点时的输入条件。 |
| CN_GDP | [P2 列表](../../src/pring_cycle/catalog.py#L90)；当前公式读取 nominal_quarterly_level，或允许版本的 nominal_ytd_level，再构成滚动分母，见[实际公式](../../src/pring_cycle/context_projection.py#L2000)。 | P2 身份不变，但纳入 P1 依赖闭包；不得简单“所有 P2 都从门禁删除”。本研究不裁决或改写 GDP 经济公式、修订版本、8 字段合同。 |
| UST2Y/UST10Y | 同属 [P2 列表](../../src/pring_cycle/catalog.py#L99)；唯一现有公式依赖是 ust_2s10s_spread，见[完整 8 公式输入表](../../src/pring_cycle/context_replay_scope.py#L10)。 | 没有通向 P1 或核心阶段的依赖边；可选父项暂缺仅使背景利差 unavailable。 |
| UST_2S10S_SPREAD | P2 输出；[投影公式绑定](../../src/pring_cycle/context_projection.py#L339)与[同日差值计算](../../src/pring_cycle/context_projection.py#L905)。 | 公式保留原版本和同日两父项规则；有合格父项时正常计算，无合格父项时保留缺口和原因，不能补零、恢复坏最新之前的旧利差或暗用代理。 |

当前 Treasury CSV 的日期列不是逐行首次发布证明。[采集及消费协议](../../src/pring_cycle/treasury_context.py#L211)明确拒绝来源声明自行填写的 release_at/public_available_at；[真实原件](evidence-14-treasury-followup/a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5#L2)中 2026-09-04 的 2Y/10Y 为 4.37%/4.78%。[现有公开软件测试](../../tests/models/test_candidate_admission.py#L898)只允许真实新 SYSTEM 下 41bp 背景输出，历史目标 PUBLIC 仍缺口。本研究不会把这个 SYSTEM 正例改造成历史 PUBLIC 正例。

## 3. 现行阻断链及确切条件

1. **范围把公式身份与必需性混在一起。** [ContextReplayScope.from_manifests 60–76](../../src/pring_cycle/context_replay_scope.py#L60)在包变化时令 changed 包含全部相关 P1/P2；任何父项变化令对应公式进入 formulas；required 则无区别加入所有这些公式的 inputs。此处没有查看公式输出是否纯 P2，也没有核心/P1 依赖闭包。
2. **未认证 UST 立即成为全局认证缺口。** [context_replay_gaps 650–664](../../src/pring_cycle/model_evaluation.py#L650)对任何“P2 且在 formula_inputs 内”的指标要求 certified。UST2Y/10Y 与 GDP 因而被同等处理。完整候选把 GDP 单独合法审为 certified、其他 P2 保持 awaiting 时，静态预期返回 `candidate_context_sources_uncertified:UST10Y_NOMINAL_YIELD,UST2Y_NOMINAL_YIELD`。
3. **认证标签不能解决缺 PUBLIC，但缺口仍被错误升级。** [scope.source_metrics](../../src/pring_cycle/context_replay_scope.py#L83)纳入所有 changed/input 中已 certified 的 P2。[evaluate_context_replay 覆盖扫描](../../src/pring_cycle/model_evaluation.py#L723)和[覆盖合法输入过滤](../../src/pring_cycle/model_evaluation.py#L1004)要求 PUBLIC 非空；UST 只有未知时间时形成 `candidate_context_evidence_missing:UST…`。[755–777](../../src/pring_cycle/model_evaluation.py#L755)遇任何 gaps 即 evaluated_cutoffs=0，不产生完整逐日缺口投影。
4. **仅移除预检仍不够。** [逐 cutoff 选择](../../src/pring_cycle/model_evaluation.py#L811)对所有已认证 scope.source_metrics 追加缺口；[公式输出验收](../../src/pring_cycle/model_evaluation.py#L889)对所有受影响候选公式要求 available/current 和非空血缘。诚实的 UST unavailable 因而再次触发 `candidate_context_formula_output_missing:ust_2s10s_spread`。
5. **持久输出还有同一分类。** [validate_context_output](../../src/pring_cycle/model_outputs.py#L425)按 scope 严格核 source_metrics/formula_keys，不能从保存文档偷偷删除 UST。[输入验证 546–555](../../src/pring_cycle/model_outputs.py#L546)将“整份输出 recorded 且定义 certified”的每一来源都视为 required；认证 UST 但 PUBLIC 无输入时，即使 evaluator 不报错，保存仍拒绝空数组。其后[最新值/成员核验](../../src/pring_cycle/model_outputs.py#L616)也复用此 required 条件。
6. **错误缺口进入了真实激活门。** [replay_models](../../src/pring_cycle/model_evaluation.py#L245)原样收 context gaps，并于[323](../../src/pring_cycle/model_evaluation.py#L323)令 quality_passed=False。[CLI model-replay](../../src/pring_cycle/cli.py#L356)把机器结果交给[record_replay](../../src/pring_cycle/models.py#L646)，它合并持久上下文 gaps，passed 必须无 gaps。[activate 472–558](../../src/pring_cycle/models.py#L472)要求机器校准、当前生效基线的精确 120 日机器回放，并拒绝任何已有失败回放。**activate 本身不需要增加 P2 特判或绕过；应让上游机器验收按正确的必需性生成结果。**

范围差异不能混淆：候选仍可经公开来源准入创建；[candidate_admission 113–121](../../src/pring_cycle/candidate_admission.py#L113)允许 P2 awaiting，认证 P2 才要求额外包绑定；[174–185](../../src/pring_cycle/candidate_admission.py#L174)又强制全部 8 公式。这恰好证明“合法可选候选在后续回放被卡”，不是候选创建不受支持。

旧测试 [test_v6_unlicensed_p2_gaps_do_not_block_p1_certification_replay](../../tests/models/test_model_lifecycle.py#L106)不能证明 UST 可选性正确。它用的 v6 目录[预置已认证 P2 集合](../../src/pring_cycle/catalog.py#L211)包含 GDP、UST2Y、UST10Y、UST spread，因而根本没有覆盖“UST awaiting + 全 8 公式”。它只验证其他未认证 P2 不触发这一父项规则。

## 4. 可立即开始的公开 RED 与完整验收路径

以下均为待运行设计；首个测试不需要网络、完整历史数据或更改公式，因此可先实施，不应等待 Treasury PUBLIC 凭空齐备。

### RED A：真实公开准入后的错误认证门

复用 [admitted_gdp_manifest](../../tests/models/test_candidate_admission.py#L131)，它调用完整 prepared_request，经 source-certified 请求绑定 GDP 合成审查、公开 CLI submit，返回实际登记候选 manifest；原测试模型的 P1/核心、全 8 公式、120 窗口和执行指纹完整，其他 P2 awaiting。只用它证明软件分类，不授予真实 GDP 认证。

在同一隔离 runtime 中以 ModelRepository 读回当前 active 比较 manifest，再调用公开 `context_replay_gaps(candidate, comparison)`：

- 独立断言候选有 61 定义、42 P1；UST2Y、UST10Y、UST spread 仍 P2 awaiting；GDP certified；8 公式全部仍在。
- **新规格期望 `gaps == ()`；现行静态推导为仅 UST2Y/10Y 的 uncertified 错误。** 这证明错误分类，不声称该候选已有 P1 历史值或整体已可激活。
- 配对负例另建完整候选，GDP 仍 awaiting，保留 credit_impulse；期望 gaps 含 CN_GDP，且不含 UST。不得在已登记 manifest 内原地改状态。

此入口与[现有 context_replay_gaps 公共测试](../../tests/models/test_model_lifecycle.py#L114)一致。完整来源准入已由 fixture 自身满足，不 mock scope/evaluator/仓库内部模块。

### RED B：未知 PUBLIC 的覆盖门和真实不可用投影

沿 [Treasury 原件公开采集测试](../../tests/models/test_candidate_admission.py#L898)保留 raw、normalized、实际 capture 时钟；给“定义已审，但该批逐行 PUBLIC 未知”的独立合成候选绑定精确 GDP/UST 审查，然后公开追加关联同一收据的合成 reviewed claims，PUBLIC 坚持为空。不能仅改 awaiting 为 certified 后跳过审查绑定。

调用 `evaluate_context_replay(..., requested_start="2026-03-09", requested_end="2026-08-28", replay_days=固定120日)`。第一步可直接断言 UST 缺 PUBLIC 不出现在**阻断性** gaps，并单列诊断；P1/GDP 证据仍缺时，它们的硬缺口必须继续存在，因此该初步反例不能把整体 `passed` 设为真。所有必需父项及 P1 的真实或明确合成完整窗口备妥后，再期望 120 个逐 cutoff 文档、UST value=None、无伪造 PUBLIC/采用 ID，并保存缺口原因。

### GREEN：持久回放、激活、正式运行均保留机器门

沿 [model-replay CLI 与保存读取先例](../../tests/models/test_candidate_replay.py#L255)验证 `model-replay → model-replay-show / replay_details → activate`。该旧先例只演示公开接口，**其 legacy 短窗和 CALIBRATION_BASELINE 不能复制成新目录的验收替代**。

新正例要先以公开准入建立独立完整候选与合法比较基线，再具备其本身的核心校准、P1/GDP 父项原件/规范化/历史 PUBLIC、预热、精确 120 日历和当前 active 比较。调用真实 CLI 机器计算与记录；读回不可变核心及上下文输出，再带显式 fixture 批准激活。隔离软件 fixture 可使用受控外部 transport/时钟，不能手写 passed、直接改 active 表、删除失败回放或 patch 掉完整性/认证门。正式用户模型仍须其真实数据与批准，不能借 fixture 通过。

必留配对反例：

- 缺 GDP/错误父项/信用脉冲窗口不全仍阻断 P1 完成和模型回放；UST 缺口同在时不能掩盖该失败。
- 未认证 UST 候选实值、伪造 PUBLIC、坏原件/normalized 均不得进入 adopted IDs；可选性只允许 unavailable，不允许不合格 available。
- 可选 P2 有值时，继续按公式、同日期、单位、血缘和最新版本计算；值或缺口状态变化必须出现在回放差异与保存输出中。
- 保存文档删 UST 公式身份、删缺口行、将缺口标 current、伪造父项、少一天或改模型 hash 仍拒绝。不能将整份 context_output 改成 not_applicable。
- 旧失败、旧 manifest、旧投影和旧回放文档不重写；修复后使用绑定新执行指纹的候选，按现有不可变规则重新验收。

## 5. 最小修复边界

1. **在现有共享 scope 中分开两种集合。** 完整比较范围继续保留所有受影响定义、8 公式及可选 P2；另从核心/P1 输出出发求公式父项依赖闭包，确定必需 sources/formulas。根据现有固定映射，credit_impulse 及 CN_GDP 属必需，ust_2s10s_spread 与两个 UST 父项不属必需。可增加明确的公式输出身份映射，但不能仅凭名字写“跳过 UST”，也不能全量排除 P2。
2. **统一应用同一必需性。** context_replay_gaps、coverage、逐 cutoff selection、公式可用性和 model_outputs recorded 输入完整性都以该闭包决定是否阻断。完整输出仍保留 optional 状态及诊断；字段/身份/时间/原件验证继续作用于每个实际被采用的数值。缺数据、合法暂缺与结构欺骗不能混成一种“忽略错误”。
3. **逐 cutoff 如实记录可选输出。** 未认证或未知 PUBLIC 时 UST 行 value=None、不可采用；利差保持原公式身份并明确依赖不可用原因。现有[投影依赖门](../../src/pring_cycle/context_projection.py#L339)已经在不可用父项时停止计算，[gap 行](../../src/pring_cycle/context_projection.py#L1629)已经保留 null/缺口；应补足机器回放对这种诚实状态的验收，不从 manifest 删公式来达成。持久 source snapshot 对 optional 可为空，但依旧核 schema、版本、点时和诊断一致性；不以 `status=recorded` 自动要求每个 certified P2 非空。
4. **模型治理保持原样。** 当前 active 比较、机器校准、完整 120 日、必需 P1/GDP 输入、执行指纹、不可变文档、质量/回归/性能、显式批准均不放宽。根据[实施 34](spec.md#L124)，结果规则改变必须由新候选与当前执行指纹承载；若持久文档形状变更，需在现有版本协议下保持旧记录可读，不原地解释旧结果为新结果。
5. **关闭条件是行为通过，不是研究结论。** 本研究只确认冲突与修复范围。实际来源认证、信用脉冲历史经济口径、真实 Treasury PUBLIC、完整历史数据与最终真实切换分别继续开放；可选 UST 暂缺不应成为新增门禁，GDP/P1 的真实阻塞仍不能豁免。

## 6. 输入指纹与本地引用核验

所有下表 SHA-256 为本轮读取的实际文件字节；路径相对仓库根目录。源码和测试是当前未提交工作树快照，不等同于基点版本或测试已通过。本文件交付时使用标准库只读核对全部表项 bytes/hash，以及 Markdown 本地链接目标存在和 #L 行号范围；结果见交付回复。唯一写入为本文件。

| 输入 | bytes | SHA-256 |
|---|---:|---|
| `CONTEXT.md` | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| `docs/adr/0012-atomic-model-versions-and-parallel-replay.md` | 1277 | `172a1d28d5d67b7075930872032887fd0c4b5748903ed26a5a8760626681ef12` |
| `.scratch/pring-data-acquisition-repair/spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| `.scratch/pring-data-acquisition-repair/issues/14-p2-availability.md` | 8447 | `251fbe33ef4e360283bddb90cdce7bc7bf2e8455c712e9e8c4277a01e4dabc15` |
| `src/pring_cycle/context_replay_scope.py` | 3580 | `588b5fc7e823334b1fdcc1d01e03a6659d10c652f96c7aeaccc288e1c762cb10` |
| `src/pring_cycle/model_evaluation.py` | 50145 | `cf0417f1101b3f43df9784d858ea5d497f2d10659b9dfe2206acc97d6f028bba` |
| `src/pring_cycle/models.py` | 53941 | `21baa442ee10700a817f807647cd299a46bcab8d5061eedde7c9759c6782e8fa` |
| `src/pring_cycle/model_outputs.py` | 26725 | `f25ad15e92c3a760222ea2fdfad586b2979fb20fe878d990be09c60b37d5c5eb` |
| `src/pring_cycle/context_projection.py` | 88193 | `44c89b740c4c90c5e488ec6aac2fc39aa917034db7d15aa8bc5b50b11b559528` |
| `src/pring_cycle/catalog.py` | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| `src/pring_cycle/candidate_admission.py` | 13193 | `681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4` |
| `src/pring_cycle/cli.py` | 39097 | `5ddf9fc308266294ecc1cc9e3f1cf3bc6b332cdbe6730a48f4bd09b06722cfe3` |
| `src/pring_cycle/treasury_context.py` | 18109 | `041baa8ee9f3dd3444e1f0fe3d7de4acc54b0192d696c79de484996028b75c93` |
| `tests/models/test_model_lifecycle.py` | 26290 | `78e0952d9749c91756bc9d45a53752e3c488301da3ed619071d6f0d5d09ab5ec` |
| `tests/models/test_candidate_replay.py` | 38061 | `f09a7ddd70cc00c506d7734f51214870ff531d859eecf5a9f88a1fac4eb99d8a` |
| `tests/models/test_candidate_admission.py` | 332393 | `51dae08979d7d63e4042460ad1fc82ebb68e19be3cfa05f1b56045b033b01ade` |
| `.scratch/pring-data-acquisition-repair/evidence-14-treasury-followup/a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5` | 13961 | `a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5` |

