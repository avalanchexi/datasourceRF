# 候选目录进入采集、选值和投影的边界

研究类型：research / 只读源码追踪。固定 HEAD：`1cd2c00fc4be1a4fa599d5e45f8ca18fe284c2d1`。工作树指纹采集于 **2026-09-07T19:55:51.668339+00:00**（中国时间 2026-09-08 03:55:51）。本报告包含未提交的 `candidate_admission.py`、`cli.py` 修改及准入契约、测试；不能将结论归为仅提交 HEAD 的能力。以下“会拒绝”均为源码控制流推断，本轮没有执行应用、数据库、网络、解析器或测试，未证明任何真实来源认证、实际目标日可用性、120 日回放或模型采纳。

## 1. 结论与实施边界

**完整定义可以随新候选保存；全局目录身份和实际消费仍未接通。** 本批准入最后只调用 `ModelRepository.create_candidate(manifest)`，完整定义和来源包进入模型 JSON；没有独立目录登记。通用查定义函数仍只认 v1、v2、被冻结隔离的 v3 和融资单项 `margin-financing-v0002`；真实新版本返回 `KeyError("unknown_metric_definition_version")`。模型 JSON 不可变不等于 `catalog_version → 唯一不可变定义集合` 已实现。证据：[src/pring_cycle/candidate_admission.py:67](../../src/pring_cycle/candidate_admission.py#L67)、[src/pring_cycle/models.py:271](../../src/pring_cycle/models.py#L271)、[src/pring_cycle/catalog.py:396](../../src/pring_cycle/catalog.py#L396)。

下游不是全部缺失：`ContextProjectionRules.from_manifest` 已解析完整 embedded definitions；证据仓库的双点时读查询可以按任意版本字符串筛选；上下文投影和回放已传入模型版本。最窄工作是先完成**与候选创建原子提交的目录登记和冲突拒绝**，再让一个已支持家族通过统一的版本定义解析边界走到真实仓库、模型选值及上下文投影。不能通过改旧 v3 门禁、改全局默认目录、先激活候选、把所有来源声明换版本或调整未定市场规则来完成。依据：[修复规格 97–105、124–125 行](spec.md#L97)、[票 19 验收](issues/19-immutable-candidate-catalog.md#L13)、[本批准入结果边界](candidate-admission-contract.md#L39)、[ADR0012](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md#L7)。

## 2. 按公开入口区分确切第一拒绝点

前提：给定真实新 `definition_version`，候选已存在，其他必填身份、时间和参数合法；不是把输入缺项导致的异常算作版本拒绝。

| 公开入口/场景 | 到达新版本消费之前的实际控制流 | 确切第一拒绝或限制 |
| --- | --- | --- |
| `model-source-certify --candidate-request-hash` | 验正式包/定义绑定→保存完整模型清单 | 本批可保存新目录字符串；不会自动登记到静态目录。[src/pring_cycle/candidate_admission.py:22](../../src/pring_cycle/candidate_admission.py#L22) |
| `run-submit --type targeted_refresh --model <未激活候选>` | 先查 active model | CLI 先 `run_model_is_not_active`；还没走目录解析。[src/pring_cycle/cli.py:421](../../src/pring_cycle/cli.py#L421) |
| `RunRepository.submit(targeted_refresh, model_version_id=候选)` 后由 `process_pending_run` 执行 | 提交 scope 已从模型内定义取优先级；Worker 对除报告外的命令校验 active | 无 active 时 `active_model_unavailable`，有其他 active 时 `model_version_not_active`。不能为了采集打开这个既有正式运行门。[src/pring_cycle/runs.py:1034](../../src/pring_cycle/runs.py#L1034)、[src/pring_cycle/worker.py:218](../../src/pring_cycle/worker.py#L218) |
| `model-source-refresh --model <新候选>` | `refresh_source_certified_candidate` 要求 candidate，随后硬限定 v3 | 新版先 `source_refresh_catalog_version_invalid`；若改成 v3 又会被其原有 `require_source_contract` 阻断。它也仍消费旧 smoke 包格式，不能只删版本条件便称接通。[src/pring_cycle/cli.py:400](../../src/pring_cycle/cli.py#L400)、[src/pring_cycle/source_certification.py:235](../../src/pring_cycle/source_certification.py#L235) |
| `evidence-ingest` 非 P0、非 certified 标量 JSON | CLI 用**默认 v2**查指标仅做 P0/认证写入限制，然后把输入版本原样交仓库 | 新版本在 `append_source_claims → _validate_claim → metric_definition` 首次被拒；若输入 P0 或 `certified`，CLI 更早拒绝，这是应保留的通用导入权限边界。[src/pring_cycle/cli.py:470](../../src/pring_cycle/cli.py#L470)、[src/pring_cycle/cli.py:836](../../src/pring_cycle/cli.py#L836)、[src/pring_cycle/evidence.py:269](../../src/pring_cycle/evidence.py#L269)、[src/pring_cycle/evidence.py:1126](../../src/pring_cycle/evidence.py#L1126) |
| 直接 `EvidenceRepository.append_source_claim(s)` | 每条先校验完整定义，再查 v3 负面门，再写事务 | `_validate_claim` 第一行查固定目录即 `unknown_metric_definition_version`，尚未写入来源声明。[src/pring_cycle/evidence.py:258](../../src/pring_cycle/evidence.py#L258) |
| `ingest_lpr_document / refresh_lpr_release`、官方 context 导入/刷新 | 获取原件并形成收据→`ingest_acquired_official_release` 构建 claims | 官方共同入库函数在给 claim 赋认证状态时先查固定目录，尚未到仓库 append；可能已有可追溯原件及收据。[src/pring_cycle/official_lpr.py:211](../../src/pring_cycle/official_lpr.py#L211)、[src/pring_cycle/official_lpr.py:280](../../src/pring_cycle/official_lpr.py#L280)、[src/pring_cycle/official_context.py:346](../../src/pring_cycle/official_context.py#L346) |
| `TushareContextAdapter.acquire_scalars / ingest_context_scalars` | 解析与收据→标量语义校验→固定目录 | 普通支持标量在 1203 行拒绝新版本；带自身版本的融资标量可先在 1191–1202 行因版本/候选契约不符拒绝，GDP 部分口径也有独立提前拒绝。不能把融资 v2 标量改标签当新已认证定义。[src/pring_cycle/tushare_context.py:1187](../../src/pring_cycle/tushare_context.py#L1187) |
| 核心历史 `refresh_core_history` | 收集真实核心响应与标准化制品之后查各核心定义 | 128 行查固定目录拒绝；原 PUBLIC 未知规则不因新版本解除。[src/pring_cycle/core_history.py:123](../../src/pring_cycle/core_history.py#L123) |
| EIA HTML、Treasury CSV | 请求合法性检查后，HTTP 前查目标定义 | 分别在 343 行、180 行拒绝；没有发送新源请求。EIA API 的标量导入在 243 行拒绝。[src/pring_cycle/eia_html.py:330](../../src/pring_cycle/eia_html.py#L330)、[src/pring_cycle/treasury_context.py:168](../../src/pring_cycle/treasury_context.py#L168)、[src/pring_cycle/eia_context.py:228](../../src/pring_cycle/eia_context.py#L228) |
| 单独 `select_retrieval_input` / `ModelInputSelector.select` | 构造器只取模型版本；select 才解析每个指标 | 87 行固定目录拒绝，早于遍历该指标序列；只改仓库入库仍不能补齐模型缺口。[src/pring_cycle/search_evidence.py:39](../../src/pring_cycle/search_evidence.py#L39) |
| 已通过运行门的定向检索 / 显式绑定 `RetrievalLedger.bind_run` | Worker 先为范围登记唯一缺口 | `bind_run` 64 行固定目录拒绝，早于 release gate、下载和选择；并非只有“下载后入库”待修。[src/pring_cycle/worker.py:450](../../src/pring_cycle/worker.py#L450)、[src/pring_cycle/retrieval_ledger.py:58](../../src/pring_cycle/retrieval_ledger.py#L58) |

因此不能用一个统一“第一错误”覆盖所有命令。候选实际刷新入口、正常任务入口和底层公开入库入口分别有上述先后关系。本轮没有运行这些反例；下一轮须由公开行为测试复现。

## 3. 全部直接定义解析调用，以及已可复用的消费部分

本轮对 `src/pring_cycle` 的 `metric_definition(...)` 调用全量检索，除函数定义本身，共 **12 个文件 / 15 个调用点**：

| 文件:行 | 所需定义信息与公开消费边界 |
| --- | --- |
| [src/pring_cycle/cli.py:840](../../src/pring_cycle/cli.py#L840) | `evidence-ingest` P0/认证限制，当前漏传输入版本；新入口应根据已登记版本解析，仍拒绝通用 CLI 自授 certified。 |
| [src/pring_cycle/evidence.py:1127](../../src/pring_cycle/evidence.py#L1127) | `append_source_claim(s)` 的单位、维度键、认证状态；写入前不可绕过。 |
| [src/pring_cycle/core_history.py:128](../../src/pring_cycle/core_history.py#L128) | 核心历史/日刷新：保存正确版本、单位与核心身份。 |
| [src/pring_cycle/official_context.py:364](../../src/pring_cycle/official_context.py#L364) | 官方正文及 LPR 的共同 claims 构造，不能仅改直接 HTTP 外壳。 |
| [src/pring_cycle/tushare_context.py:1203](../../src/pring_cycle/tushare_context.py#L1203) | TuShare 标量入库；`targeted_context.retrieve_tushare_context` 和日常上下文刷新都会到此。 |
| [src/pring_cycle/eia_context.py:243](../../src/pring_cycle/eia_context.py#L243) | EIA API 取得值进入仓库时的版本定义。 |
| [src/pring_cycle/eia_html.py:343](../../src/pring_cycle/eia_html.py#L343) | EIA 官方 HTML 请求前解析版本。 |
| [src/pring_cycle/treasury_context.py:180](../../src/pring_cycle/treasury_context.py#L180) | Treasury 两期限请求前解析版本及 percent 单位。 |
| [src/pring_cycle/search_evidence.py:87](../../src/pring_cycle/search_evidence.py#L87) | `ModelInputSelector` 认证与完整维度判断；本地命中、搜索候选补齐率、完整运行计划/采纳复用它。 |
| [src/pring_cycle/retrieval_ledger.py:64](../../src/pring_cycle/retrieval_ledger.py#L64)、[src/pring_cycle/retrieval_ledger.py:813](../../src/pring_cycle/retrieval_ledger.py#L813) | 新缺口身份、发布家族去重；旧重试记录的事件键读取同样按其历史模型版本解析，不能改成当前 active。 |
| [src/pring_cycle/search_discovery.py:50](../../src/pring_cycle/search_discovery.py#L50) | `build_search_query` 使用冻结名称与 source_codes，不能拿 v2 的名称/来源替代新定义构造搜索。 |
| [src/pring_cycle/worker.py:828](../../src/pring_cycle/worker.py#L828)、[src/pring_cycle/worker.py:1472](../../src/pring_cycle/worker.py#L1472) | 官方直连后认证分类；上下文抓取失败时按 P1/P2 决定是否阻断。 |

间接入口也要显式覆盖：历史 `refresh_source_history` 将给定版本传给官方/LPR 导入；`retrieve_tushare_context` 从运行模型取得版本；`verify_search_candidates` 给官方刷新及两种点时选择传同一版本；`FullRunRetrieval` 从模型内定义规划，但仍调用上述 Selector/Ledger。证据：[src/pring_cycle/source_history.py:301](../../src/pring_cycle/source_history.py#L301)、[src/pring_cycle/targeted_context.py:29](../../src/pring_cycle/targeted_context.py#L29)、[src/pring_cycle/search_evidence.py:137](../../src/pring_cycle/search_evidence.py#L137)、[src/pring_cycle/full_retrieval.py:144](../../src/pring_cycle/full_retrieval.py#L144)。

| 已有公开边界 | 当前可证明的能力；接入时应保持 |
| --- | --- |
| `ContextProjectionRules.from_manifest` | 解析 embedded 定义并校验目录版本一致；不用静态 `metric_definition`。这只解析结构与支持的公式版本，不证明认证事实。[src/pring_cycle/context_projection.py:121](../../src/pring_cycle/context_projection.py#L121) |
| `EvidenceRepository.query` | 按 observation ID 查 `public_available_at` 或 `available_at`，无静态目录查询；原始查询选出候选 claim 不等于模型可用。[src/pring_cycle/evidence.py:646](../../src/pring_cycle/evidence.py#L646)、[src/pring_cycle/evidence.py:1067](../../src/pring_cycle/evidence.py#L1067) |
| `metric_series / preload_metric_series / source_claim_vintages` | SQL/缓存按明确 `(metric_id, definition_version)` 分隔；新版本没有已存 claim 时为空。调用方必须传版本，不能以省略版本的全版本查询替代候选证据。[src/pring_cycle/evidence.py:319](../../src/pring_cycle/evidence.py#L319)、[src/pring_cycle/evidence.py:520](../../src/pring_cycle/evidence.py#L520)、[src/pring_cycle/evidence.py:687](../../src/pring_cycle/evidence.py#L687) |
| `build_context_projection` | 用清单内定义和该版本取序列，按认证/质量/鲜度形成事实或缺口；已具备直接消费新版本已存 claims 的结构。不是看到清单全就填值。[src/pring_cycle/context_projection.py:216](../../src/pring_cycle/context_projection.py#L216)、[src/pring_cycle/context_projection.py:1279](../../src/pring_cycle/context_projection.py#L1279) |
| `TargetBoundEvidenceRepository` | 对 SYSTEM 也施加目标中国日末 PUBLIC 上界；统计月末不等于公开时点。新目录不能绕过未知 PUBLIC。[src/pring_cycle/context_projection.py:548](../../src/pring_cycle/context_projection.py#L548) |
| `evaluate_history` / 上下文回放 / 模型的精确核心日历检查 | 读 embedded 定义、按候选版本读 PUBLIC 序列或 vintages，仍须输入/覆盖/预热门；无需为了支持版本字符串重写双点时 SQL。[src/pring_cycle/model_evaluation.py:206](../../src/pring_cycle/model_evaluation.py#L206)、[src/pring_cycle/model_evaluation.py:482](../../src/pring_cycle/model_evaluation.py#L482)、[src/pring_cycle/models.py:923](../../src/pring_cycle/models.py#L923) |
| Web `/api/v1/catalog` | 当前明确返回默认 v2，而非候选/active 的 embedded 定义。它不导致仓库拒绝，但不能将该页面返回当新目录的验收读取证据；后续若展示指定目录，应显式带版本并核对登记内容。本条不要求本轮改 UI。[src/pring_cycle/web.py:165](../../src/pring_cycle/web.py#L165) |

版本解析解决以后，**维度成员/字段语义并不会自动可执行**。`MetricDefinition.dimensions` 只有维度键；`REQUIRED_DIMENSION_MEMBERS` 仍冻结具体成员，解析器家族路由与派生公式也有支持集。例如静态估值成员仍叫 `price_earnings`，融资仍有既定两个 measure；这不是新候选可以任意声明新语义后自动通过的协议。下一纵向切片选已有明确的 LPR `1y / 5y_plus`，保持市场五家族业务选择另票收口。证据：[src/pring_cycle/catalog.py:22](../../src/pring_cycle/catalog.py#L22)、[src/pring_cycle/metric_contracts.py:16](../../src/pring_cycle/metric_contracts.py#L16)、[src/pring_cycle/search_evidence.py:88](../../src/pring_cycle/search_evidence.py#L88)、[未冻结业务规则边界](spec.md#L104)。

## 4. 真实接入前必须补齐目录唯一身份

现准入比较的是**单请求**里的每个定义版本与目录版本、正式包对完整定义和清单的 hash；`create_candidate` 只用 model ID 冲突检查。若两个正式审查请求分别绑定各自清单，但都声明同一新 catalog version，第二份更改某定义的名称、单位或维度，两者 model hash/ID 不同，现保存层没有跨模型比对目录集合的检查。这是静态可见缺件，**不是本轮已运行的双请求复现**。证据：[src/pring_cycle/candidate_admission.py:45](../../src/pring_cycle/candidate_admission.py#L45)、[src/pring_cycle/candidate_admission.py:69](../../src/pring_cycle/candidate_admission.py#L69)、[src/pring_cycle/context_projection.py:168](../../src/pring_cycle/context_projection.py#L168)、[src/pring_cycle/models.py:276](../../src/pring_cycle/models.py#L276)。

接入前的最小持久化契约建议如下：

1. 在指定 runtime 持久化 `catalog_version → 完整定义集合及其规范化内容 hash`。采用确定性、明确版本化的集合编码；同版本同内容幂等，同版本不同任何定义内容拒绝。不能只比较 metric IDs，也不能以“最新 model”覆盖。旧内置目录及融资局部目录不得被新登记遮蔽或改写。
2. **完成准入审查后，目录登记和候选保存共用一个事务提交。** 版本冲突、模型冲突或写入失败时，两者都不产生新状态；不能先登记“certified 目录”，随后模型创建失败留下可被采集解析器使用的半成品。唯一键/事务还须覆盖并发两个不同内容的同版本请求。
3. 多个模型可以引用同一已经登记且内容一致的目录，例如趋势规则不同；多个 catalog version 的观测可并存。来源声明身份已经含 `definition_version`，因此同版本异定义若不拒绝，未来会共享 observation 身份；这正是登记前置的必要性。[src/pring_cycle/evidence.py:1159](../../src/pring_cycle/evidence.py#L1159)。
4. 注册来源必须是新正式准入受信路径，不是任意 `ModelRepository.create_candidate` JSON、测试 helper 或 `certified` 字符串。版本不存在、目录 hash 不一致、绑定模型引用的定义不一致时拒绝；不自动扫描所有历史模型把任意 embedded 定义当已认证目录。
5. 解析器统一取得这个不可变定义集合：已有带 runtime/database 的仓库、adapter、Selector、Ledger 均可复用同一解析边界；需要模型语义时额外核对 bound model 的目录内容与登记一致。对纯解析函数仍保持无需数据库；对旧内置版本沿用旧定义和否定性审查。具体类名/表名不是本研究冻结的业务规则。
6. 审查、目录注册、取得原件、Source Claim 和模型采用分别留证。即使目录登记已带认证状态，缺 PUBLIC、错期/单位/维度、错 source identity 或原件/收据不全仍拒绝或保持候选/缺口。来源认证包本身不是逐次数据输入。

这条先决条件应与当前“模型清单不可变已实现”分开验收。原 v3 负面门 `source_contract_review.py` 的“没有已知否定不等于认证”语义必须保留：[src/pring_cycle/source_contract_review.py:73](../../src/pring_cycle/source_contract_review.py#L73)、[ADR0006](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md#L7)。

## 5. 下一条最窄公开 TDD 行为

建议交付范围：**原子登记已审查的新目录，并用现有 LPR 单家族公开导入/获取入口证明该目录可被仓库、模型输入选择和上下文投影共同消费。** 优先复用现有公开 `ingest_lpr_document` 或 `refresh_lpr_release` 的 `definition_version`，通过带 runtime 的统一解析边界读取登记目录；不为测试修改全局 map。没有必要在第一条中开放完整生产 Worker、接通全部家族、改旧 v3 刷新命令或运行真实网络。

一条正向纵向测试应完成：

1. 隔离 runtime 经**公开新准入命令**消费明确标识为合成的审查/包，生成全新版本候选；公开查询可见完整模型和登记目录。两个行为都成功才算第一步，candidate 不激活。
2. 给公开 LPR 导入/刷新入口提供已有 HTML fixture，传新 definition version。刷新只替换 HTTP transport；本地导入本身是明确的 `document_import`，不宣称发送 HTTP。应得到两个新版本 Source Claims、原件 hash、独立收据及实际接收/校验时刻，均可通过真实仓库公开读接口核对。
3. 采用 fixture 的独立期待 **1y=3.0%、5y_plus=3.5%**，统计期为 2026-08，行内公开时刻 2026-08-20 09:00 Asia/Shanghai。此 460 字节 fixture 仅是隔离软件测试输入，不是本轮新的官方认证原件。[既有 LPR fixture](../../tests/fixtures/chinamoney_lpr_20260820.html#L5)。控制接收、校验在公开时刻以后；PUBLIC 在公开前不可见/公开后可见，SYSTEM 在校验前不可见/校验后可见。
4. 用持久化候选的运行记录/范围调用公开 `select_retrieval_input`，选出恰好两个新版本 claim IDs；使用固定且已晚于校验的 cutoff，不能事后修改 scope cutoff。直接 `RunRepository.submit` 可以准备记录但不调用正式 Worker，不伪称定向任务已经执行完成。
5. 用候选 manifest 调用公开 `build_context_projection(..., target_business_date="2026-08-28", persist_derived=False)`，核对 LPR 两期限值、单位、来源、时间、claim 血缘及模型版本隔离；其他家族没有输入时保留缺口。候选、active 指针和既有投影历史均维持原状态。既有对应公开投影测试可复用结构，但本轮未执行：[LPR 投影测试](../../tests/integration/test_context_projection.py#L842)。

反向验收至少包含这些与同一行为直接相关的反例：

| 反例 | 必须观察到的结果 |
| --- | --- |
| 两个**各自重新正式审查**的请求使用同版本、不同定义集合 | 第二次准入冲突拒绝；第一份目录/候选字节不变，第二份候选和目录不落库。不能仅用旧 review hash 失配作为“目录冲突”测试。 |
| 候选保存失败或目录冲突 | 无独立“已认证可解析目录”残留；以真实仓库公开读取核对事务结果。并发相同版本/不同集合至多一份成功。 |
| 合法新版本已准入，但只改 validator 或 monkeypatch 全局 `metric_definition` | 不能算通过；必须由公开导入到真实仓库、再由真实 Selector 和 projection 可见独立期待值。 |
| 未登记任意版本、候选引用与目录 hash 不一致 | 明确拒绝，不回退 v2/v3，不借另一个候选的定义。 |
| 相同 metric/期次在旧版本有值，新版本没有值 | 新候选选择仍不完整，不跨版本复用旧 claim；成功入库后两个版本 observation IDs 不同，旧查询结果保持不变。 |
| 同一 LPR 值缺可靠公开时间，或仅有 1y 没有 5y_plus | 原始 SYSTEM 可按实际校验时间读到合法 claim，不代表 target-bound SYSTEM / PUBLIC 或完整模型输入可用；缺期限不能补0或复制另一期。 |
| 错单位、错维度、错官方身份，或普通 `evidence-ingest` 试图写 certified/P0 | 保留原拒绝；不因新目录注册授予通用导入权限。 |
| catalog version 或 embedded definition 使用旧 v3 | 继续拒绝准入/正式消费；历史只读能力保留。 |

本条通过只证明**一个家族和注册目录的纵向软件能力**。再按上表将其余 15 个静态调用点逐边界接入；定向刷新 Worker 保持 active 约束，候选采集需使用显式非激活入口。真实 `model-source-refresh` 的新协议分支还需明确源输入范围，不能拿旧 smoke 包解析器消费 v2 正式认证包。五家族规则、官方历史 PUBLIC 和全部 42 项 P1/13 项 P2 状态等仍服从原票，不在这里补授认证。

## 6. 本轮未做与剩余门槛

- 没有登记任何目录、候选、来源声明、认证或投影；没有执行公开反例、测请求成功率或获得新来源样本。报告中的 first-rejection 是静态追踪，下一批 RED/GREEN 才能改变“已复现”状态。
- 本批未提交准入入口是否能创建候选，已有测试只证明其合成契约范围；其测试不包含实际新版本采集/选择链。[准入合成正例](../../tests/models/test_candidate_admission.py#L363)。
- 来源首次 PUBLIC、修订 vintage、获取时刻仍由源和采集收据证明。共同官方入库保留跨版本物理原件历史检查，新注册不意味着旧 PUBLIC 可以迁移或未知值可补时刻。[src/pring_cycle/official_context.py:296](../../src/pring_cycle/official_context.py#L296)、[src/pring_cycle/tushare_context.py:1222](../../src/pring_cycle/tushare_context.py#L1222)。
- 应先复核下列输入指纹，再实施。后续源码或准入契约变化使本报告变为历史快照；不修改此报告来把旧静态结论伪装成新实现验证。唯一交付文件是本 MD，未另写脚本/JSON/日志。

## 7. 本次读取输入指纹

以下按读取时工作树精确字节计算 SHA256，路径相对于仓库根。源码行号按 UTF-8 文本行计；SHA 包含真实换行字节。本表共 38 个文件，是本报告复核输入，不代表逐文件全套测试。目录和模型事实来自源码，本轮未读取生产数据库。

| 输入路径 | bytes | SHA256 |
| --- | ---: | --- |
| [AGENTS.md](../../AGENTS.md) | 348 | `2017fb00f48480bf657af3e41fe00b27b3a9bddce63b734c9a471c898f4c81c0` |
| [CONTEXT.md](../../CONTEXT.md) | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| [docs/agents/domain.md](../../docs/agents/domain.md) | 904 | `dfb45dbbc2c1bf3f1bd8ad5c6db249b4f2c6cc6587da4ec63cf75f002c477e9c` |
| [docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md) | 725 | `acb0c307d24518d5e4551f457353535d5398d21c8bd0212c9f9445a82012cf8a` |
| [docs/adr/0012-atomic-model-versions-and-parallel-replay.md](../../docs/adr/0012-atomic-model-versions-and-parallel-replay.md) | 1277 | `172a1d28d5d67b7075930872032887fd0c4b5748903ed26a5a8760626681ef12` |
| [.scratch/pring-data-acquisition-repair/spec.md](spec.md) | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| [.scratch/pring-data-acquisition-repair/issues/19-immutable-candidate-catalog.md](issues/19-immutable-candidate-catalog.md) | 3443 | `5a873d6493b2b7d716944ca641cc2eb75f9093f249ef1db1f9b996c5a1cb4b57` |
| [.scratch/pring-data-acquisition-repair/candidate-admission-contract.md](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [src/pring_cycle/candidate_admission.py](../../src/pring_cycle/candidate_admission.py) | 13005 | `45dd80edd4b969a20c6af50f1de1863344d411d36a2d6558a06c6000df7b3e4f` |
| [src/pring_cycle/catalog.py](../../src/pring_cycle/catalog.py) | 25699 | `59fcac0c8279c4b1acfe7bac4eab1688088571745ef539fc41728c3acd0eb83a` |
| [src/pring_cycle/models.py](../../src/pring_cycle/models.py) | 42485 | `42db5dfc7c2ca42b9916b21ddbc2b04165f0bc082d5c78be354cf15020ba39b8` |
| [src/pring_cycle/source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 4706 | `ad377fafc71cbd26d8a3d06eaf71131c9111aecc436f84618032f11d70786e64` |
| [src/pring_cycle/evidence.py](../../src/pring_cycle/evidence.py) | 52119 | `21c287dd453c56ddde09fd630b7736f85c58c3830fc82f5864faae3ffa463436` |
| [src/pring_cycle/cli.py](../../src/pring_cycle/cli.py) | 38065 | `a4d8febe8e53e4206f13f9fdea130c87fd8eb85a5b360779a5d3a689d6161cfc` |
| [src/pring_cycle/official_context.py](../../src/pring_cycle/official_context.py) | 80084 | `b1cb854a431e0b5f488d2b1330177785713e28806a99f6a0e880c798a1203aaa` |
| [src/pring_cycle/official_lpr.py](../../src/pring_cycle/official_lpr.py) | 15707 | `2173c4ea5d3c16acd26fb58c9a9a04ae79e5519403be93bf8b46a94f22f290d1` |
| [src/pring_cycle/tushare_context.py](../../src/pring_cycle/tushare_context.py) | 68390 | `e48f670b8f25b596cb4612cfb6e1f587727d59cf98747e9ceacc80c6fa6cb2bd` |
| [src/pring_cycle/core_history.py](../../src/pring_cycle/core_history.py) | 7814 | `dce17e2d957ffe6a5d2175accd19e0fda207dad0a523d8516b44e8d3f09128bc` |
| [src/pring_cycle/source_history.py](../../src/pring_cycle/source_history.py) | 30359 | `2a0009db28e46bb9786a72f36e186857e2e6801134f5a90919e0af2a1ed7fa29` |
| [src/pring_cycle/treasury_context.py](../../src/pring_cycle/treasury_context.py) | 13090 | `0edc0376f9b9b4ab363e82249ef6513521d765ab33c373bc8df26160c960e585` |
| [src/pring_cycle/eia_context.py](../../src/pring_cycle/eia_context.py) | 16175 | `a209fe8653bb5be45cf9c14b882690d410fd945933d98be62248798b3fa976e8` |
| [src/pring_cycle/eia_html.py](../../src/pring_cycle/eia_html.py) | 18095 | `949e72e139a3110eca795be415c3c5e2dfac983a2a77ca0b1aeed3ad9d7389e9` |
| [src/pring_cycle/targeted_context.py](../../src/pring_cycle/targeted_context.py) | 5936 | `065a5342fc01694cd832c237122f706914a95a9a5a41febaea054a16fbdee25a` |
| [src/pring_cycle/search_evidence.py](../../src/pring_cycle/search_evidence.py) | 12778 | `06983dc3e978484487678e2225cc51128fae5562b4734588409f6ee4c8c5e75e` |
| [src/pring_cycle/retrieval_ledger.py](../../src/pring_cycle/retrieval_ledger.py) | 36141 | `bef67ec0bee12b86c9121ac7a65844a7c8ad5ad25cb3872872f8cdbf71d63eb1` |
| [src/pring_cycle/search_discovery.py](../../src/pring_cycle/search_discovery.py) | 11912 | `ddabc3bfed120e96d1e35c52fd489d9fca682a1fa61a30bf09c1db100b1c90d6` |
| [src/pring_cycle/worker.py](../../src/pring_cycle/worker.py) | 57660 | `3dbb9e0bf0ebf4323c3d8d8b0ffb9ad53acfc9ea8045d71e5f9fb86b5825ea5e` |
| [src/pring_cycle/runs.py](../../src/pring_cycle/runs.py) | 47771 | `3d07bc98ead76624dd7e73d43ef445a121d652c927df7d245c5353a66e721a98` |
| [src/pring_cycle/full_retrieval.py](../../src/pring_cycle/full_retrieval.py) | 26197 | `d82a803a0b9e0bfad3498c2e11685585f980744ca8c655f30f0398d630a04969` |
| [src/pring_cycle/model_evaluation.py](../../src/pring_cycle/model_evaluation.py) | 37660 | `d5c15ce03b0dd97385678d4df32a6623c8c06a1953f912cec688d14c1020c732` |
| [src/pring_cycle/context_projection.py](../../src/pring_cycle/context_projection.py) | 79215 | `c63731e2bdf78f81b8ac065a0eab7e15620a4ed0677ce81809c23e8a50642c06` |
| [src/pring_cycle/metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 2853 | `abb229c33919a3c7c6275e334404c34e73e3e137f2f9947acf3518c5d03bebd0` |
| [src/pring_cycle/source_families.py](../../src/pring_cycle/source_families.py) | 2487 | `420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e` |
| [src/pring_cycle/web.py](../../src/pring_cycle/web.py) | 25800 | `25c24fd6b9e121c1a3601d6f667f897e7eebba3554f58253bfd24660656eaa43` |
| [tests/models/test_candidate_admission.py](../../tests/models/test_candidate_admission.py) | 18298 | `cc0d45a1b55c8d3328521189d71dcf842bde1e1bf57a5af2ba1e83adad8d2028` |
| [tests/fixtures/chinamoney_lpr_20260820.html](../../tests/fixtures/chinamoney_lpr_20260820.html) | 460 | `0f5bbc368da1157eb84591003b6ecaf5d0b4494b5af526a4975d1e293355fe6e` |
| [tests/integration/test_context_projection.py](../../tests/integration/test_context_projection.py) | 58226 | `183001359f933b212b69e33705895dabc3054a459b93b8828ecf8934cfe8d2d2` |
| [src/pring_cycle/source_certification.py](../../src/pring_cycle/source_certification.py) | 15659 | `e585ce624de989ec6f9def5ff4f44130ebad22c449d6c8a1a2f0c9d64e44a963` |

## 8. 默认只读复核命令与交付名单

唯一交付：`.scratch/pring-data-acquisition-repair/candidate-catalog-consumption-boundary.md`。其最终 bytes/SHA 在交付消息给出，不在自身写入自引用 hash。

在仓库根的 Windows PowerShell 执行以下标准库脚本，只读本 MD、本地链接和输入文件；不导入项目、不连接 SQLite、不联网、不写文件。后续源码变更时指纹失败应作为历史快照差异保留，不据此重写旧报告。

```powershell
@'
from pathlib import Path
from urllib.parse import unquote
import hashlib, re
root = Path.cwd()
report = root / ".scratch/pring-data-acquisition-repair/candidate-catalog-consumption-boundary.md"
raw = report.read_bytes()
text = raw.decode("utf-8")
fingerprints = re.findall(r"^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M)
assert len(fingerprints) == 38
for target, count, digest in fingerprints:
    path = (report.parent / unquote(target.split("#", 1)[0])).resolve()
    data = path.read_bytes()
    assert (len(data), hashlib.sha256(data).hexdigest()) == (int(count), digest), str(path)
links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
for target in links:
    file_part, _, anchor = target.partition("#")
    path = (report.parent / unquote(file_part)).resolve()
    assert path.is_file(), str(path)
    if anchor.startswith("L") and anchor[1:].isdigit():
        assert 1 <= int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines())
print({"input_files": len(fingerprints), "local_links": len(links),
       "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest()})
'@ | C:/Python313/python.exe -B -
```

