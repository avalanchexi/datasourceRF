# CN_GDP 现有八字段注册合同与公开消费规格

2026-09-09，research 只读交付。只读当前源码、规格、审查夹具与已保存的 NBS 2026 Q1/Q2 原件，使用标准库核文件哈希并读取表格文字；没有运行应用、应用 parser、SQL、测试或网络，没有修改源码/测试。本文是交给 implement 的可执行边界，RED/GREEN 尚未执行。

**本切片可以接通 GDP 当前八字段的“新目录合同→真实原件导入→点时选值→候选上下文”。** 不新增 `nominal_quarterly_level`，不改为 12 字段，不修改信用脉冲公式或跨修订 YTD 差分规则。八字段完整、可选、可追溯，与多期 GDP 能否按同修订口径相减是两项独立验收；完成本切片不能关闭后者。依据：[规格实施 3、6–8](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:93)、[测试公开边界](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:133)、[来源认证定义](D:/cursor/datasourceRF/CONTEXT.md:256)。

## 1. 固定的字段与真实原件锚点

当前 [GDP parser](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:813) 对 `total / primary / secondary / tertiary` 四组，每组输出以下两个成员，共八个；继续使用 `official-context-parser-v0004` 的既有表示及 `asdict` 规范化。

|measure|单位|period_kind|period_start|period_end|来源列|
|---|---|---|---|---|---|
|`nominal_ytd_level`|`hundred_million_cny`|`year_to_quarter`|该年 01-01|该季度末日|Q1 第 1 个数值列；Q2–Q4 第 2 个数值列|
|`real_quarter_yoy`|`percent`|`quarter`|该季度首日|该季度末日|Q1 第 2 个数值列；Q2–Q4 第 3 个数值列|

每个成员的 dimensions 精确为 `{"aggregate": <四者之一>, "measure": <上表之一>}`。`source_field` 分别为 `gdp/pi/si/ti` 与相应 `_yoy`；`api_name=nbs_gdp`，provider 为 `国家统计局`，官网 host 为 `www.stats.gov.cn`。[家族身份已存在](D:/cursor/datasourceRF/src/pring_cycle/source_families.py:28)。

本次从完整 HTML 的 GDP/三产业行直接读出的独立期望值如下；不是由被测 parser 再算一遍作为期望。

|aggregate|2026 Q1 nominal_ytd_level|2026 Q1 real_quarter_yoy|2026 Q2 nominal_ytd_level|2026 Q2 real_quarter_yoy|
|---|---:|---:|---:|---:|
|total|334193|5.0|695704|4.3|
|primary|11941|3.8|31522|3.7|
|secondary|116135|4.9|250473|3.0|
|tertiary|206117|5.2|413709|5.1|

Q1 的两类 period_start 均为 2026-01-01，但 period_kind 和 measure 不同，不能合并。Q2 名义累计的 start 为 2026-01-01，季度同比的 start 为 2026-04-01，二者 end 都是 2026-06-30。选择完整性必须按同一个季度末日及八维成员识别，不要求八个 start 相同。

|原件|bytes|完整 SHA-256|原件 URL / 显式发布时间|
|---|---:|---|---|
|NBS 2026 Q1|238636|`61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18`|`https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html`；2026/04/17 09:30（上海）|
|NBS 2026 Q2|263170|`60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915`|`https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html`；2026/07/16 09:30（上海）|

两份 HTML 第 11 行 PubDate 和第 277 行可见文本均含上述时间；相应 UTC 为 Q1 `2026-04-17T01:30:00+00:00`、Q2 `2026-07-16T01:30:00+00:00`。Q2 可直接使用[现有测试原件](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-14/60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915:11)。Q1 本次读取实际位置为 `\\wsl.localhost\Ubuntu-22.04\home\tywin\.local\share\pring-cycle\artifacts\sha256\61\61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18`；其身份与旧解析记录见[历史原件清单](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json) 的对应 `artifact_hash`。若后续测试需要仓库相对 fixture，应先把该字节文件按 hash 固化到项目证据目录，不能使测试依赖某台机器的 WSL 私有路径；本研究没有复制文件。

Q2 同一表另有当季名义额及累计同比列，但本切片不增加输出。特别是 total/secondary/tertiary 累计同比 `4.7/3.9/5.2` 不能替代季度同比 `4.3/3.0/5.1`。NBS 原件名义额按公告整数保留，不能拿 TuShare `31521.8/250472.9/413709.2` 替换为“更精确值”。现有 [GDP 语义测试](D:/cursor/datasourceRF/tests/integration/test_gdp_semantics.py:25)已分别保留 NBS 季度同比与 TuShare 仅名义累计、拒绝其争议同比映射。

## 2. 最小实现边界

|位置|必要动作|验收边界|
|---|---|---|
|`metric_contracts.official_source_members`|增加 `CN_GDP`，返回四 aggregate × 上述两类 `OfficialMember(dimensions, unit, period_kind)`。|任何合法季度均为精确 8 成员；Q1 不减少、不复制新季度字段。|
|`required_dimension_members`|沿用非内置目录调用 `official_source_members` 的现有通路，GDP 不加例外删成员。|新目录 GDP 的目标季度要求全部 8 维成员；旧目录保持既有行为。不要把 GDP 全局塞进只针对旧目录的 required map，从而改变旧版本解释。|
|`require_registered_source_contract`|复用现有通用官方分支；GDP 的 family 映射已在 `OFFICIAL_CONTEXT_FAMILY_BY_METRIC` 中。|核 frozen 定义结构、NBS provider、精确维度/单位/period_kind、规范季度首尾；不另开白名单绕过通用校验。|
|`OFFICIAL_CONTEXT_INTEGRITY_METRICS`|加入 `CN_GDP`。|新目录 selector、上下文和 PUBLIC replay 的当前输入核验自动使用既有原件/规范化校验；内置目录仍按版本边界保持原行为。|
|现有 parser、公式、模型定义|保持 8 字段及原公式版本。|不加入 `nominal_quarterly_level`、不改变信用脉冲选窗/差分，不改 GDP 优先级为 P1，也不修改冻结 v3。|

源码依据：[成员与新目录 required 分派](D:/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:96)、[required_dimension_members](D:/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:222)、[通用官方合同](D:/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:153)、[完整性集合](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:93)。当前 GDP 没有成员分支，因而 certified 新目录声明最终报 `registered_source_contract_not_implemented:CN_GDP`；这正是第一个要用公开导入触发的 RED。

通用合同已经检查：`source_codes/dimensions/unit/frequency/release_event_family/release_rule/release_timezone` 与既定支持定义一致，allowed_units 集合一致；provider 与 family 匹配；member 单位和 period_kind 匹配；季度末月为 3 的倍数、末日正确，季度首日/年初正确。GDP 现有定义的主 unit 是 `scalar`，实际 allowed_units 是 `hundred_million_cny` 与 `percent`；不要为方便注册把整个指标改成单一货币单位或百分比。逐标量使用上表精确单位。[目录字段](D:/cursor/datasourceRF/src/pring_cycle/catalog.py:435)、[GDP 允许单位](D:/cursor/datasourceRF/src/pring_cycle/catalog.py:501)。

本切片只支持官方 NBS 八字段新目录合同。通用 provider 检查应继续拒绝把同名 `cn_gdp` TuShare 四字段输入作为该官方合同成员；不恢复已拒绝的 TuShare 同比语义。source_reference 的 URL、hash、家族和原件内容一致性由公开消费时的 `official_claims_matching_acquisitions` 验证，不能把一个看似正确的字符串当已有原件。[声明与原件核验](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:293)。

## 3. 合法为 P2 GDP 增加合成审查

本测试只需要**已注册候选**，不执行 Worker 或 activate。公开 `select_retrieval_input` 与 `build_context_projection` 能针对绑定候选的登记目录做输入验收；它们不表示候选可以发布生产投影。来源认证、长期校准、120 日重放和生效门仍完整保留。[选择器绑定检查](D:/cursor/datasourceRF/src/pring_cycle/search_evidence.py:56)、[登记目录与模型绑定](D:/cursor/datasourceRF/src/pring_cycle/catalog_registry.py:109)。

以现有 `prepared_request` 为起点，在独立测试 runtime 内做以下明确操作：

1. 保留完整 manifest、全部 P0/P1 定义、所有 8 个公式及既有趋势/时间/重放规则。只将其中 `CN_GDP` 定义的 `certification_status` 从 awaiting 改为 certified；它仍是 P2，其他 P2 继续按原状态，不假称它们已认证。
2. 在 synthetic package 的 `definition_bindings` 中新增 `CN_GDP: hash(修改后的完整 GDP 定义)`。保留原 P1/核心绑定。六项 `semantics/fields/history/time/permissions/usage` 审查仍齐全，finding 明确“隔离软件合同测试，不认证真实历史来源或信用脉冲跨修订口径”；引用的 fixture 制品必须真实可读并登记 source_reference，不能用不存在的 hash。
3. 修改 GDP 定义会改变完整 manifest hash，因此重算 package 的 `manifest_hash`；再重算 review 的 `subject_hash`（package 去除 `schema_version/review_hash` 的内容），保存新 review、package、request。原制品不覆盖。若采用独立 GDP-only package，原 P1 package 的 manifest_hash/review 也必须重新绑定，不能只追加一个 GDP 包而保留旧 manifest hash。
4. 调公开 `admit_source_certified_candidate` 或 CLI `model-source-certify`；读回新的 candidate 与注册目录。不要调用私有 `_register_admitted_catalog`、修改数据库或 patch `metric_definition`。

依据：[prepared_request](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:57)、[P2 certified 必须纳入覆盖](D:/cursor/datasourceRF/src/pring_cycle/candidate_admission.py:108)、[审查 subject/证据验证](D:/cursor/datasourceRF/src/pring_cycle/candidate_admission.py:196)。现有 [bind_synthetic_review](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:5029)可重算 manifest/subject/review 链，但**不会替你新增 GDP definition binding**；调用前必须完成第 2 步。

最小准入负例：只把 GDP 改 certified、正确更新 manifest/package/review hash，却遗漏 GDP definition binding；公开准入应报 `certification_coverage_missing:CN_GDP`。错误 hash 则应由 manifest/subject/definition 对应门拒绝。这个反例明确证明不是“P2 标一下 certified 就合格”。每个 variant 用新隔离 runtime 或独立目录版本，不能覆写同版本定义。

## 4. 最小公开 RED → GREEN 链

**A. 注册成功后的首个真实原件 RED。** 完成上节 synthetic 准入，读实际新目录版本；用 NBS Q2 完整原字节调用 `ingest_official_context_document(paths, raw, family="nbs_gdp", source_url=真实 URL, expected_period="2026-Q2", definition_version=新版本, fetched_at=受控真实取得时钟, clock=同一时钟)`。不激活候选、不调用 Worker。当前公开 ingest 会先 capture，再因新目录 GDP 来源合同未实现而无法成功保存合格声明；预期错误为 `registered_source_contract_not_implemented:CN_GDP`。失败获取原件/收据保留，不能手工补声明冒充成功。[公开导入](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:347)。

**B. 按八字段合同接通后的 GREEN。** 相同公开入口导入 Q1 和 Q2，在独立成功用例读取：

- 每次 observation_count/claim_ids 精确为 8；两个 period 共 16 个不同期次/维度标量，数值、source_field、单位、period_kind、首尾日逐项匹配第 1 节独立期望。
- 原件 hash/bytes 与输入完全相等；每次各有本次 `document_import` 收据，参数 family/URL/period 正确，parser v0004，started ≤ received ≤ validated；raw/normalized 分别可读。声明 acquisition_id 指向该份原件，fetched/available 遵守真实取得/校验完成边界。历史 JSON 中的 `definition_version=null`、`acquisition_ids=[]` 不能充当这些新关联。
- `EvidenceRepository.metric_series(...definition_version=新版本)` 的 PUBLIC 查询：Q1 发布前无其值，发布后有八项；Q2 发布前不能提前出现 Q2，发布后出现八项。SYSTEM 在本次取得/校验前不可见、完成后可见。历史 PUBLIC 与本次 SYSTEM 是两套时间，不能将控制时钟回填为 4 月/7 月取得。
- 建立绑定候选的 `RunRepository.submit(command_type="targeted_refresh", metric_ids=("CN_GDP",), period="2026-Q2", model_version_id=candidate_id, ...)` 记录，仅调用公开 `select_retrieval_input(paths, run, mode=PUBLIC/SYSTEM)`。目标日与 cutoff 覆盖 Q2 的真实发布时间及本次取得边界；返回 complete、精确 8 个 Q2 选中 ID，不把 Q1 补成 Q2 的缺失成员，不执行 `process_pending_run`。
- 用完整 candidate manifest 调 `build_context_projection`；Q2 的八项 GDP 行位于 `macro.international_context`（当前 P2 展示区），以各自真实单位和期次展示，role 继续为 `context_only_never_formal_stage`。公开模型输入集合包含有效选中 GDP ID，可追到本次原件；本测试只有 Q1/Q2 GDP，不足以形成信用脉冲 8 季窗口，不能断言它已有效。

沿用现有 [真实官方原件→候选选择/上下文先例](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:3484)，但保留完整候选清单和本次 GDP 的 P2 审查；不沿用 [旧 GDP 测试](D:/cursor/datasourceRF/tests/integration/test_gdp_semantics.py:92)中 model-v0001 awaiting 候选的结果作为新目录 certified 成功证据。

## 5. 必需的负例与消费边界

|反例|公开入口与应有结果|
|---|---|
|Q2 用了累计同比列|真实 Q2 原件独立断言 total=4.3、secondary=3.0、tertiary=5.1；4.7/3.9/5.2 不得被当成季度同比。|
|错误 provider、aggregate、measure、unit 或 period_kind|通过公开声明入口提交变体；通用注册来源合同拒绝。`nominal_quarterly_level`、`real_ytd_yoy`、第五个 aggregate 均不在本合同。|
|错误季度边界|同声明内容仅把 Q2 nominal start 改成 04-01、quarter-yoy start 改为 01-01、end 改为 06-29 或非季度末月，均拒绝；Q1 两类 start 相同仍允许。|
|缺一个成员/一成员 invalid|新隔离 case 通过公开 capture/证据入口构造不完整声明集合，或者追加真实可见的质量无效版本；selector complete=false，不能用上一季度该维度凑数。不得删除既有不可变声明造缺口。|
|raw 或 normalized 文件损坏/缺失|仅在隔离 case 的新取得制品副本制造故障。公开 selector 不得将坏来源列为合格；上下文相应 GDP 行不能保持 current/available 或进入实际模型采纳集合。已存审计值、旧声明及 diagnosis ID 可保留，不能把“值仍可读”误当漏检。|
|正确数字配错误/缺失 acquisition 关联|消费核验拒绝；每个所选 claim 必须有可核查的关联，所有所关联官方收据均须匹配原件、规范化、身份和选中标量。仅有 source_reference 字符串不够。|
|更新原件数值却沿用旧发布日期|公开 ingest 追加新版本，保留旧版本；无独立较晚公开证据的新修订 PUBLIC 仍未知。SYSTEM 可按实际新取得看候选，不能倒填历史公开。|
|未认证 GDP 定义|保留原 prepared_request 的 awaiting 状态，官方原件仍可作为候选保存；不可被 selector 当合格，界面保持 awaiting，不因八字段解析通过自动授认证。|

原件消费已存在的机制：[完整官方 acquisition 重建](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:259)、[声明与每个关联核对](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:293)、[selector 八成员及原件门](D:/cursor/datasourceRF/src/pring_cycle/search_evidence.py:123)、[上下文 source_failed 与模型采纳过滤](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:1396)、[模型实际输入集合](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:516)、[修订时间保守处理](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:428)。

`EvidenceRepository.metric_series` 是证据/点时读取接口；raw 在入库后被破坏不要求历史声明从仓库消失，真正合格消费由 selector/context 的完整性门决定。类似地，上下文逐字段可展示局部诊断值，整个 GDP 是否八成员补齐以 selector 的 complete 及同季度 required 检查验收，不因存在七行就标完整。

把 GDP 加入完整性集合，也会接通 `model_evaluation._context_selection_gaps` 对最新 GDP 八成员及其原件的 PUBLIC 核验，且它以 `period_end` 归并，不会因 Q2 两种 start 不同误判。但全模型 `evaluate_context_replay` 仍需要所有其他 P1/公式输入；本切片的 PUBLIC selector 正例不能冒充完整 120 日重放，也不能裁掉其他 manifest 指标只为让 replay 绿。[同季度 required 检查](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:1163)、[官方原件核验](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:1189)。

## 6. 不得混入本次完成结论的事项

本切片通过后只能说：**Q1/Q2 两份真实原件在经 synthetic 审查的独立新目录中，按当前八字段合同正确保存、完整选值、展示和追溯；PUBLIC/修订/坏原件边界通过对应软件测试。** 不产生真实 GDP 来源认证，不创建 active 模型，不输出已经验收的信用脉冲结论。

GDP 跨修订 YTD 差分仍是明确阻塞。已核实的 2024 Q4 跨公告差分为 399338，而该公告当季值为 373726；2025 Q4 分别为 386843 与 387911。当前八字段 parser 均可正确取得它们各自的 YTD，仍不意味着两份公告属于可相减的同一修订口径。本报告不静默采用当季列；完整反例与原件 hash 见[信用脉冲原件边界报告](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/credit-impulse-integrity-boundary.md:9)，原始公式仍见[信用脉冲实现](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:1979)。

另有整窗信用脉冲父项完整性问题：当前函数自行筛选认证声明后取 24 月/8 季，并未消费 GDP/SF 的全部实际父项原件门。加入 GDP 全局集合会保护普通选择和上下文 GDP 行，**不会自动修复信用脉冲内部取数**。本研究不扩大到该公式；后续必须独立验收实际所选窗口、额外 YTD 基线与修订身份，不能借本切片把此前阻塞关闭。

## 7. 读取输入指纹

相对路径以 `D:/cursor/datasourceRF` 为根；两份原件指纹已列于第 1 节。

|输入|bytes|SHA-256|
|---|---:|---|
|`CONTEXT.md`|20103|`f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102`|
|`.scratch/pring-data-acquisition-repair/spec.md`|27762|`f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4`|
|`src/pring_cycle/catalog.py`|25978|`fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c`|
|`src/pring_cycle/metric_contracts.py`|9849|`b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66`|
|`src/pring_cycle/source_families.py`|2487|`420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e`|
|`src/pring_cycle/source_contract_review.py`|14630|`c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772`|
|`src/pring_cycle/official_context.py`|84300|`fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11`|
|`src/pring_cycle/search_evidence.py`|18966|`ff00c5d77aedd0559df66260730008cd1f6d1f1e05b37de42d65379b7a31a12a`|
|`src/pring_cycle/context_projection.py`|87349|`4f2d4080a857118b693ac1e114a9d086062a879f4e9f87d5a3759383bcfbd568`|
|`src/pring_cycle/model_evaluation.py`|49636|`ece7dee6598b18582cf1b35bd4fd518738a7597119d231e6a62be37cc328e2e3`|
|`src/pring_cycle/candidate_admission.py`|13193|`681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4`|
|`src/pring_cycle/catalog_registry.py`|4349|`e94a5417a900c111514addb5b3c3b320c3eb0ac723543fca9b116934bcd57ecc`|
|`tests/integration/test_gdp_semantics.py`|10456|`76fae51ea96014cbc7f31cb82e4d332e447d531240d374514df714e73d9096a7`|
|`tests/models/test_candidate_admission.py`|283112|`fbc34a2f0b95877c72fa5942d53659416c559053f8b48553e09beb8148d27189`|
|`.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json`|1622488|`65a153a43ee952ff40640f5faa86c83539f832d1075fbb652b5dc539c656d977`|
|`.scratch/pring-data-acquisition-repair/credit-impulse-integrity-boundary.md`|23526|`757b60ef1e86073004753bb9183fee084bb9ba6e48cdf61208c44dc1cb6aedff`|
