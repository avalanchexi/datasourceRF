# Worker 注册目录公开执行与合法测试前置

2026-09-09，research 只读研究。读取当前源码、CONTEXT、ADR0012、规格与既有 lifecycle/evaluation/Worker 测试；未运行应用、SQL、测试或网络，未修改源码或测试。唯一新增此报告。下述 RED/GREEN 为设计及源码推导，不能计为已执行测试；读取指纹列于末尾。

**两处缺少 `database_path` 是相互独立的 Worker 缺陷；但当前已注册候选测试夹具不具备合法 Worker 执行资格。** Worker 首先要求运行绑定当前 active 模型，新目录候选还必须通过真实机器校准与对当前 active 的精确 120 日重放。现有短夹具要么只完成注册，要么使用旧目录/替换机器验算，因此不能将其直接激活后冒充新目录公开正例。本报告给出正确生命周期与两个分支的最小测试设计，同时明确当前阻塞。

依据：[规格 Testing 2/3](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:133)、[CONTEXT 模型生命周期](D:/cursor/datasourceRF/CONTEXT.md:55)、[ADR0012](D:/cursor/datasourceRF/docs/adr/0012-atomic-model-versions-and-parallel-replay.md:7)。

## 1. 两处缺陷、入口与可观察结果

|分支|实际遗漏|到达条件|当前可推导结果|修复后必须保留的行为|
|---|---|---|---|---|
|官方定向刷新|`worker.py:837` 的 `metric_definition(metric_id, definition_version=...)` 未传 `paths.database`。|真实新目录 active；`targeted_refresh` 通过发布门和本地缺口判断，走默认官方 adapter；真实官方刷新已经解析、保存收据与声明。|查认证标签时报 `KeyError('unknown_metric_definition_version')`。已保存的原件/声明仍应保留，任务被外层标为需要处理，不能计为补齐。|使用登记目录真实认证状态；certified 时再经公开本地选值确认完整，未知/未认证保留候选，不能把已抓到网页直接当模型可用。|
|TuShare 上下文异常处理|`worker.py:1505` 查询 `.priority` 时未传数据库。|真实新目录 active 的 `manual_full`/`scheduled_full`；核心刷新已完成；某上下文 family 的实际获取/解析/入库抛 `TypeError` 或 `ValueError`。|先保存 `adapter_failed`/`validation_failed` 尝试，再在优先级查询产生 KeyError，覆盖原始异常。|P1 继续抛原来的错误并阻断；全部为 P2 的 family 记录失败后继续。不能一律吞错，也不能把 P2 失败升级成目录故障。|

源码依据：[官方刷新后检查](D:/cursor/datasourceRF/src/pring_cycle/worker.py:806)、[TuShare family 异常分支](D:/cursor/datasourceRF/src/pring_cycle/worker.py:1487)、[目录解析器](D:/cursor/datasourceRF/src/pring_cycle/catalog.py:397)。`metric_definition` 对内置版本查内存表，对其他版本只有收到数据库才查询注册表；否则直接抛上述 KeyError。这解释了为什么旧目录测试没有暴露问题。

外层 `process_pending_run` 捕获 LookupError（包含 KeyError），保存 `worker_failure:KeyError:'unknown_metric_definition_version'`。官方 `RetrievalLedger.trace_acquisition` 只将 OSError、TypeError、ValueError 转成 adapter 结果，不捕获 KeyError；它会越过正常 physical request 完成逻辑，再由 Worker 中断账本，不能误称 `official` 成功。[外层捕获](D:/cursor/datasourceRF/src/pring_cycle/worker.py:177)、[物理请求追踪](D:/cursor/datasourceRF/src/pring_cycle/retrieval_ledger.py:361)。

两处**可以在业务路径上单独触发**：定向刷新直接返回，不运行 `_refresh_context_sources`；普通 full run 的直接上下文刷新可先在 TuShare 错误分支结束，无需进入官方定向 adapter。前者不依赖后者修复，后者不依赖前者修复。不过“路径独立”不等于当前已经有可激活的新目录夹具，两者共享下一节的模型前置。[分流](D:/cursor/datasourceRF/src/pring_cycle/worker.py:285)。

## 2. 最小合法模型仍然是完整模型

真正注册目录只能经 `admit_source_certified_candidate`（CLI `model-source-certify`）验证请求和正式审查包，再原子创建候选及登记目录。普通 `ModelRepository.create_candidate` 不登记目录；给旧模型换一个新版本字符串不能满足这个测试。[公开准入](D:/cursor/datasourceRF/src/pring_cycle/candidate_admission.py:23)、[原子创建与登记](D:/cursor/datasourceRF/src/pring_cycle/models.py:288)。

当前准入要求：全部 61 项定义及原有角色/优先级；三核心、全部 P1 的合格认证及定义 hash 绑定；P2 若标 certified 也必须有审查覆盖；完整 8 个公式；120 日趋势窗与 120 交易日证据窗；固定时间/选择/候选天数/精确重放规则；当前 execution fingerprint；`calibration_range_start=2018-06-01`，认证重放不早于 2026-03-09。测试最小化应减少不相关外部请求和重复构建，不能删指标、删公式、改成两日趋势或降低激活规则。[准入约束](D:/cursor/datasourceRF/src/pring_cycle/candidate_admission.py:83)。

现有 `prepared_request` 是合适的**注册起点**：它明确使用 synthetic 审查包，保留完整清单，通过公开 CLI 创建新目录候选；但它把所有 P2 设为 `awaiting_source_certification`，且没有机器校准/重放/激活。不能把这个候选直接用于 Worker 正例。[夹具](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:57)。

公开构建链应完整执行如下步骤。这里只描述未来测试构建器，不执行其中任何命令：

1. **隔离 runtime 与 active 比较模型。** 在独立测试根调用 `initialize_runtime`；读取模型列表，公开为比较模型完成自身验收/激活。`model-v0001` 有历史 bootstrap 规则，现有 lifecycle 允许 `record_acceptance(..., CALIBRATION_BASELINE)` 后显式批准激活，但这仅证明该旧模型自身规则，不是新模型机器验收。若要宣称整个构建器经过真实校准，比较模型也走实际 `model-accept`。不得 SQL 写 active、patch `ModelRepository.active`，也不得占用特殊 `model-v0001` ID 给新目录免除重放；旧 manifest 同 ID 修改会被不可变门拒绝。[旧模型合法规则](D:/cursor/datasourceRF/tests/models/test_model_lifecycle.py:37)、[不可变存储](D:/cursor/datasourceRF/src/pring_cycle/models.py:303)。

2. **公开创建完整注册候选。** 用 CAS 保存明确标 synthetic 的来源证据、审查、package 和 request；保持所有定义及公式，调用 `model-source-certify`，读回 `model-reviewed-…`、manifest hash、注册目录版本及审查绑定。此时 active 仍为比较模型。合成审查只证明软件合同，绝不能作为真实官方认证交付。

3. **准备同版本的完整证据。** 通过真实 acquisition/parser/公开声明入口建立候选和比较模型的三核心 PUBLIC 历史及独立日历；满足固定长期校准和状态预热，再准备精确重放窗内所需 P1、受影响公式的所有父项，以及其 raw/normalized/acquisition 关联。单日原件、160 个当前核心 bar 或只标 certified 的裸声明都不能替代这里的证据。外部 transport 和时钟可控；应用 parser、仓库、规则选择、原件核验及投影保持真实。测试设定的 PUBLIC 必须明确是 synthetic 发布证据；真实 TuShare 历史刷新本身仍返回 PUBLIC 未知，不能借夹具倒填其真实历史。[核心刷新未知 PUBLIC](D:/cursor/datasourceRF/src/pring_cycle/core_history.py:129)、[测试规定](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:133)。

4. **真实机器校准与保存。** 调 `model-accept --model <candidate>`，它实际执行 `calibrate_model` 并保存结果；或使用等价公开函数链 `calibrate_model → record_acceptance`。默认校准截至 2026-08-19，要求 1995 个评估日、2338 个输入日，输入首日 2017-01-03；结果还要匹配既定稳定性基准 `21/11/0/23` 并包含真实核心输出文档/hash。不能传一组硬编码通过数字，也不能用显式短窗口结果替代默认机器验收。[CLI](D:/cursor/datasourceRF/src/pring_cycle/cli.py:323)、[校准边界](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:121)、[验收保存规则](D:/cursor/datasourceRF/src/pring_cycle/models.py:339)。

5. **与当前 active 真实重放并保存。** 调 `model-replay --model <candidate> --compared-with <current-active> --start 2026-03-09 --end 2026-08-28`。公开 CLI 将真实 `replay_models` 结果传给 `record_replay`，保存日历、逐日核心/上下文输出、差异及 hash。不能自比、不能使用非 active 比较模型、不能缩窗；所有质量、回归与性能门仍执行。调用 `model-replay-show`/`replay_details` 核存档，不只看命令返回 passed。[公开重放](D:/cursor/datasourceRF/src/pring_cycle/cli.py:356)、[比较模型约束](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:206)。

6. **正式通过公开 activate。** 调 `model-activate --model <candidate> --confirm`，或等价 `activate(..., explicitly_approved=True)`。它重新计算机器校准并匹配已存结果，重新核当前证据下的重放、精确 120 日、当前 active 比较基线及来源合同，在事务中再检查 active 未变，最后写激活历史。任一失败就保持候选；不能 patch `_hardened_machine_*`。之后读取 `active()`、`activation_history()`、验收及重放详情，证明 Worker 的前置确实成立。[激活完整门禁](D:/cursor/datasourceRF/src/pring_cycle/models.py:472)、[重算校准](D:/cursor/datasourceRF/src/pring_cycle/models.py:1073)。

这套构建器可统一产生隔离的合法测试基线，再由不同用例使用独立实例；无需每个缺陷另造一套认证规则。缓存原始测试输入可以减少重复准备，但一个外部预置 `active` 数据库不能无构建记录地当成此链已通过。失败重放会使该候选不可激活，因此生命周期负例与正例必须隔离，不要在同一候选里先保存失败 replay 再期待它后来激活。[失败记录约束](D:/cursor/datasourceRF/src/pring_cycle/models.py:500)。

## 3. 当前公开构建链的实质阻塞

**所查现有测试没有一个“完整新注册目录→真实校准→真实 120 日重放→激活→Worker”的可直接复用正例。** 这不是说公开链不存在，而是输入与支持合同还不足，不能用既有短测试推导它已成功。

- `prepared_request` 将所有 P2 留待认证；`ContextReplayScope` 因候选来源包变化覆盖 P1/相关公式，`context_replay_gaps` 明确要求参与公式的 P2 也 certified。完整公式依赖 `CN_GDP`、`UST2Y_NOMINAL_YIELD`、`UST10Y_NOMINAL_YIELD`，所以默认请求即使注册成功，也会在真实 context replay 被阻断。不能拿“无关 P2 可缺”解释这些公式父项。[重放范围](D:/cursor/datasourceRF/src/pring_cycle/context_replay_scope.py:11)、[公式依赖认证](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:639)。
- 将上述 P2 仅改成 certified 并补 synthetic 审查，仍不会自动打通其输入合同。当前注册来源分派覆盖核心、若干官方家族、LPR、RRR、银行间、仓单，但未实现 GDP、上述 UST 或例如 `CN_EQ_CSI300` 的注册来源分支；它们不是当前 `official_source_members` 的支持成员，最终触发 `registered_source_contract_not_implemented:<metric>`。新目录完整重放要求这些声明/公式，不能通过裸写声明规避。[注册合同分派](D:/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:105)、[缺省拒绝](D:/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:211)。
- 真正机器校准不能借用 v1 常量。现有两项校准区间回归测试替换 `evaluate_history`，仅验证区间参数；短 candidate-history 用例明确 `accepted.passed=False`。旧 lifecycle 数字、返回假 HistoricalEvaluation 或手造机器元数据均不满足当前 activate 的重新计算。[参数测试](D:/cursor/datasourceRF/tests/models/test_model_evaluation_regressions.py:188)、[短历史的有限证明](D:/cursor/datasourceRF/tests/models/test_candidate_replay.py:221)。
- `test_hardened_activation_requires_current_baseline_and_exact_120_day_replay` 替换两项机器验算，只验证激活门的组合；`test_worker_completes_a_valid_noncanonical_projection_and_report` 使用旧目录 v1。这两者不能拼接成新目录已经合法生效。[激活组合测试](D:/cursor/datasourceRF/tests/models/test_model_replay_rollback.py:24)、[旧目录 Worker 正例](D:/cursor/datasourceRF/tests/integration/test_worker_execution.py:383)。

因此本轮能静态定位并设计两个缺陷的回归，却不能把一个受 active 门阻断的用例标成它们的真实 RED，也不能报 Worker 全链 GREEN。修复两处参数遗漏与补齐完整独立运行夹具是不同验收事项；不要为了缩小这次修复去降低生产模型验收条件。

## 4. 缺陷 A：官方定向刷新独立用例

前提为第 2 节合法 active 已构建。`RunRepository.submit(command_type="targeted_refresh", model_version_id=active_id, metric_ids=..., period=..., source_url=..., system_as_of=...) → process_pending_run → RunRepository.get/AcquisitionRepository/EvidenceRepository/select_retrieval_input` 是最小公开边界。必须使用默认 retrieval adapters（`retrieval_adapters=None`），仅替换 `official_context.urlopen` 外部 HTTP 响应；传入自定义 `official` 返回字符串会直接绕过有缺陷函数。[默认生产 adapter](D:/cursor/datasourceRF/src/pring_cycle/worker.py:637)、[现有 HTTP 替换先例](D:/cursor/datasourceRF/tests/integration/test_worker_execution.py:843)。

fixture 选择注册已支持的 NBS CPI 家族，使用一个重放结束后新发布的月度事件以保持原 acceptance/replay 不变：明确 synthetic 发布信息与真实形状的完整 HTML 响应。预先通过公开证据接口建立该期已有发布但部分所需成员缺失的状态，使发布门自然通过、本地选值不完整；不要先导入该期完整原件，否则 local 分支已经 verified，官方分支根本不会执行。补全响应应与已有成员身份、值、时间一致，或具备独立较晚修订时间，避免保守修订规则合法地把 PUBLIC 留空。选择器的 target/PUBLIC/SYSTEM cutoff 都必须晚于本次允许的取得和发布边界；不能为了让新收据可见修改已经冻结的历史 cutoff。[发布门](D:/cursor/datasourceRF/src/pring_cycle/worker.py:591)、[本地选值](D:/cursor/datasourceRF/src/pring_cycle/worker.py:759)。

RED 的用户可见断言应是“完整官方原件已形成有效新目录声明，但任务没能完成补齐”：

- 一个实际官方物理请求、正确 raw bytes/normalized hash、received/validated 时钟和期次；请求属于该 run，声明使用新目录版本。
- 当前缺陷下任务为 `action_required`，错误含 `worker_failure:KeyError:'unknown_metric_definition_version'`；该失败不能丢原件和已写声明。
- 修复后任务 completed，官方 ledger/attempt 成功，公开 selector complete 且选中声明可追到本次原件；`verified_evidence` checkpoint 与实际所选 ID 一致，而不是假 claim ID。

**定向刷新成功不会发布新的分析投影。** `_execute_retrieval_run` 仅记录 verified_evidence 后完成；要核“模型真实采纳与结论”，随后另提交合法 full run、使用已具备的 P0/P1 输入，读取其 `projection_set_id`、evidence snapshot、模型采纳 ID 及报告绑定。这一步不能拿手动 `build_context_projection` 或 targeted completed 代替。[定向完成边界](D:/cursor/datasourceRF/src/pring_cycle/worker.py:563)、[完整任务投影路径](D:/cursor/datasourceRF/src/pring_cycle/worker.py:336)。

## 5. 缺陷 B：TuShare 异常优先级独立用例

仍从合法 active 副本提交 full run，保持实际 `_refresh_core_sources`、`_refresh_context_sources`、P0 readiness、FullRunRetrieval 和投影执行。配置测试 token，只替换 `source_adapters.build_opener` 与 `tushare_context.build_opener` 的外部 HTTP transport，按请求的 API/参数返回 fixture bytes。核心 calendar/三核心 bar 必须是真实成功形状并覆盖请求日历；让核心网络失败会在上下文前停止，不能算命中本缺陷。[全量刷新顺序](D:/cursor/datasourceRF/src/pring_cycle/worker.py:296)、[核心刷新](D:/cursor/datasourceRF/src/pring_cycle/worker.py:1541)。

最小 P1 反例可令第一个上下文 `market_indices` 请求返回 `{"code":-1,"msg":"fixture_source_schema_failed"}`。真实 TuShare parser 抛 `ValueError("tushare_source_failed")`，捕获分支先保存 validation_failed，随后当前代码错误地查询未带数据库的目录。[真实错误响应解析](D:/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1084)。当前任务错误为 KeyError；修复后仍应 action_required，但保留原来的 `worker_failure:ValueError:tushare_source_failed`，不发布新投影。只断言“action_required”会让修复前后都绿，必须断言原始错误与持久失败原件/attempt 的归因。

P2 正例另用 `CN_GDP` 的 `cn_gdp` 请求返回同类失败 bytes，确保其他 family 不先产生 TypeError/ValueError。可让非目标上下文请求按设计抛 OSError（该分支独立记录并继续），同时预置合法、当前仍可用的 P0/P1 证据；不能给它们全部空成功响应，因为 `ingest_context_scalars` 会对空 scalars 抛 ValueError，提前触发 P1 分支。后续 treasury/transmission 同样必须可控，不能在它们上再次产生有类型的校验错误。[family 顺序与 OSError 分支](D:/cursor/datasourceRF/src/pring_cycle/worker.py:1381)、[空输入拒绝](D:/cursor/datasourceRF/src/pring_cycle/tushare_context.py:1138)。

P2 的 RED 是已存 GDP validation_failed 被 KeyError 中断；GREEN 要证明程序继续到后续 family/最终读取，并在其余完整输入下正常完成投影，GDP 失败仍在运维证据中可见，不静默填值。它证明“本次 P2 获取失败可以保留已有合格输入或明确缺失状态”，不代表未认证 GDP 已成为信用脉冲合格父项。若其它前置不能达到 complete，就先报告实际停止点，不能把“后续 attempt 存在”称为完整 Worker 成功。

两个 case 均读取 `RunRepository.get/step_history/full_retrieval_plan`、对应 acquisition 原件/规范化、`EvidenceRepository` 的声明/attempt，以及 `ProjectionSetRepository.current/get`；completed 后检查 model_version、目标日、system cutoff、输入 ID、报告 snapshot 与 projection 绑定。`report_adapters=()` 可避免真实 CLI 调用，此时报告是已标注的确定性降级产物，不计为 AI 成功。时钟采用现有共享前进 UTC fixture，不替换应用结果或验证函数。[公开运行读取](D:/cursor/datasourceRF/src/pring_cycle/runs.py:296)、[时钟 fixture](D:/cursor/datasourceRF/tests/conftest.py:43)、[报告生成边界](D:/cursor/datasourceRF/src/pring_cycle/worker.py:1574)。

## 6. 读取快照

根目录为 `D:/cursor/datasourceRF`。以下 hash 绑定本次实际读取，不将其它会话后来变化算成本报告已审结果。

|输入|bytes|SHA-256|
|---|---:|---|
|`CONTEXT.md`|20103|`f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102`|
|`docs/adr/0012-atomic-model-versions-and-parallel-replay.md`|1277|`172a1d28d5d67b7075930872032887fd0c4b5748903ed26a5a8760626681ef12`|
|`.scratch/pring-data-acquisition-repair/spec.md`|27762|`f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4`|
|`src/pring_cycle/worker.py`|58810|`34a9a9e332872269852a22d7b8f0798a6cb8ab610fd09a9644b4f6739732d96b`|
|`src/pring_cycle/catalog.py`|25978|`fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c`|
|`src/pring_cycle/catalog_registry.py`|4349|`e94a5417a900c111514addb5b3c3b320c3eb0ac723543fca9b116934bcd57ecc`|
|`src/pring_cycle/candidate_admission.py`|13193|`681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4`|
|`src/pring_cycle/models.py`|53941|`21baa442ee10700a817f807647cd299a46bcab8d5061eedde7c9759c6782e8fa`|
|`src/pring_cycle/model_evaluation.py`|49636|`ece7dee6598b18582cf1b35bd4fd518738a7597119d231e6a62be37cc328e2e3`|
|`src/pring_cycle/context_replay_scope.py`|3580|`588b5fc7e823334b1fdcc1d01e03a6659d10c652f96c7aeaccc288e1c762cb10`|
|`src/pring_cycle/source_contract_review.py`|14630|`c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772`|
|`src/pring_cycle/tushare_context.py`|78830|`ea66afd3b57969fbd2bcf76889e0bfb7e92037bd1ee12e931b4d14dde2b340a4`|
|`src/pring_cycle/core_history.py`|7944|`bca200e5d2bdaab71fe3f819e7d0183f6b27bd3b13e2acae17ed64b879764d13`|
|`src/pring_cycle/runs.py`|47927|`ac2855a5ff75004084edd2ce9accb0acc1174884994f20d4001e186a3e0f5ef6`|
|`src/pring_cycle/cli.py`|39097|`5ddf9fc308266294ecc1cc9e3f1cf3bc6b332cdbe6730a48f4bd09b06722cfe3`|
|`src/pring_cycle/retrieval_ledger.py`|36990|`22690a9c726d2c6de01acdfdace4ca1c2bbbaa6e6b96146cce782f4730634cee`|
|`tests/models/test_candidate_admission.py`|282975|`83d252daa085baec090ad6a107cdd428a17d3d5d9ee8a99aff153e270575cdef`|
|`tests/models/test_model_lifecycle.py`|26290|`78e0952d9749c91756bc9d45a53752e3c488301da3ed619071d6f0d5d09ab5ec`|
|`tests/models/test_model_evaluation_regressions.py`|23867|`657f9647c19efd6e058c6545bf9c6121120864f36dc154a341eb43bd18ef6b98`|
|`tests/models/test_model_replay_rollback.py`|13076|`bacc35356c6074aeb88701cb8ae54a3b06c97363a22ad1dff6ae99b2549de6a4`|
|`tests/models/test_candidate_replay.py`|38061|`f09a7ddd70cc00c506d7734f51214870ff531d859eecf5a9f88a1fac4eb99d8a`|
|`tests/integration/test_worker_execution.py`|36825|`d9f485be66763f1a4e8bcd00b9b0243abad19e02a7dff6fd94cd7aed719d7905`|
|`tests/conftest.py`|2066|`d93f92709ba2f4e46be5d78f96083102e75f61e206df5d86399acac13605a33c`|
