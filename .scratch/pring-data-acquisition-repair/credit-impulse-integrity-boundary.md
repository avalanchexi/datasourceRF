# CN_CREDIT_IMPULSE 输入、父项窗口与原件完整性边界

2026-09-09；research 独立只读研究。只读当前源码、既存 JSON/HTML/制品，使用标准库做文件哈希、JSON 对照、HTML 单元格文本读取和独立 Decimal 算术；未调用应用、应用 parser、测试、SQL、网络或更改源码。本报告不是实际来源认证、模型创建或重放记录。源码快照见末表；主线此时另行实施与回归，结论只绑定下列输入。

**当前不能提供已通过认证的真实新目录信用脉冲正例。** 两项缺口必须分开：一是 `CN_GDP` 注册来源合同及父项完整性消费尚未接通；二是现存 GDP YTD 原件跨发布差分存在可复核的修订口径反例。已有手算 `-3.276124655980012` 证明指定数字的算术，不证明这些 GDP 父项可以按该口径认证。不可跳过 GDP、缩短公式窗口，或静默改用官方当季列后声称原口径已通过。依据：[规格实施 3、6–8](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:93)、[完整模型与固定重放窗口](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:124)、[来源认证定义](D:/cursor/datasourceRF/CONTEXT.md:256)。

## 1. GDP 原件已直接证明的两组反例

以下值直接读取保存的 NBS HTML 第一张表 GDP 行；本次没有运行现有 GDP parser。所列原件均重新读取并核对完整 SHA-256。单位为亿元。

|期次|当份公告的官方当季值|当份公告累计值|前一份公告累计值|跨公告差分|与官方当季值的差额|
|---|---:|---:|---:|---:|---:|
|2024 Q4|373726|1349084|2024 Q3：949746|399338|+25612|
|2025 Q4|387911|1401879|2025 Q3：1015036|386843|-1068|

2024 Q4 原件 `278383cce68511b7668d5ec7bd35fe7403ab9741636dbbf2585ca78689a0d716` 的 HTML 第 323、325 行分别给出当季、累计值；前季原件为 `0da0c7a1280c81f8cbef568bc70abf1c83e925eb02a28c491af872738dd5f761`。2025 Q4 原件 `9d9bc9ece5d52a9ba07d6d9ed01e0d865b4d72b385c1b2a9873501e2d5532765` 的第 354、356 行分别给出当季、累计值；前季原件为 `0f7c85e52242f3e1905d3313aa744028f51d48f60bcff899b712da400f135a5c`。各原件 URL、期次、旧解析结果可按 `results[].artifact_hash` 查阅[既存原件清单](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json)。完整文件的实际只读位置是 `\\wsl.localhost\Ubuntu-22.04\home\tywin\.local\share\pring-cycle\artifacts\sha256\<hash前两位>\<hash>`；本次未复制或改动它们。

这里不仅是推测“也许存在修订”：上述数值不等式已经成立。2026 Q2 [原公告](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13/60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915:711)还说明季度 GDP 有初步核算、最终核实与历史修订，年度最终核实后会调整季度数据；表下注释区分现价绝对额和不变价增长速度。**尚不能仅凭这些材料断定两个差额各自对应哪一次完整修订批次，更不能据此自行倒填修订 PUBLIC。** 需要补齐同一修订批次的相邻 YTD 基线及实际公布证据，或按明确决议采用公告直接季度列并版本化字段合同；这两条都不是本研究已执行的动作。

当前 `_parse_gdp` 在 Q2–Q4 取表第 2 数值列为 `nominal_ytd_level`，第 3 列为 `real_quarter_yoy`，只生成四产业合计 8 个标量；**未输出表中已经存在的 `nominal_quarterly_level`**。信用脉冲的 YTD 转季度函数只检查同年相邻季度并相减、过滤非正结果，没有修订批次比较，因而两组正差分不会被它识别为上述口径问题。依据：[GDP 解析列位](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:813)、[YTD 转季度](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:2250)。

## 2. 现在接通到哪里

|环节|已接事实|仍缺的边界|
|---|---|---|
|真实社融获取|A18 原交付含 51 个 `pbc_social_financing` 收据，JSON 状态均为 `captured`；其中本计算需要的 25 个 YTD 原件及各自规范化文件已重新核哈希，规范化 total/YTD 数值与研究输入逐个相等。|这些是 2026-09-09 本次 SYSTEM 获取；该包声明 source claims、注册目录、模型等领域计数全部为 0，不意味着历史 SYSTEM、正式认证或模型采纳。|
|GDP 原件|历史清单有 11 份 NBS GDP 原件，2023 Q4–2026 Q2；本次重核计算实际需要的 9 份完整原件。|历史 JSON 的 GDP 标量 `definition_version=null`、`acquisition_ids=[]`。未见本次 A18 中 GDP 的 capture/新目录声明链；不能把历史解析 JSON 当本次规范化收据。|
|新目录注册合同|`official_source_members` 已定义社融 total 的 `stock_end`、`stock_yoy`、`ytd_increment`；官方最新必需成员检查要求存量和 YTD。|没有 GDP 成员分支；注册合同的备用表也没有 `CN_GDP`，最终抛出 `registered_source_contract_not_implemented:CN_GDP`。社融 `monthly_increment` 同样不是目前官方注册合同允许的 total 成员。|
|官方原件消费|`official_claims_matching_acquisitions` 从声明关联读取原件和规范化，按 family/period/provider/parser/source URL 重建完整发布，再核规范化哈希与选中标量。|`OFFICIAL_CONTEXT_INTEGRITY_METRICS` 没有 GDP；信用脉冲自身没有调用该核验。仅让 GDP 可以入库仍不等于整窗父项已被核验。|
|信用脉冲公式|24 月社融、8 季名义 GDP；可选直接月/季值，v2 支持社融 YTD，GDP 支持 YTD；保存实际父声明身份和派生追溯。|先按 `_certified_point` 过滤再选末窗；所选父项没有原件完整性核验，也没有 GDP 修订基线合同。|
|模型与 PUBLIC|公式依赖含 `CN_SF_TOTAL`、`CN_GDP`；依赖未认证时移除公式，返回 `uncertified_model_dependencies`；PUBLIC 与 SYSTEM 分别按仓库规则选值。|不能把测试中直接标 certified 的旧目录 GDP 当真实合格来源。认证、时间可见、原件可追溯和数值口径是独立条件。|

获取事实来源：[A18 原收据](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-a18-import-20260909/receipts.json)、[GDP 历史材料](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json)。源码依据：[社融官方成员](D:/cursor/datasourceRF/src/pring_cycle/metric_contracts.py:153)、[GDP 注册合同缺口](D:/cursor/datasourceRF/src/pring_cycle/source_contract_review.py:211)、[官方完整性指标集合](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:93)、[完整发布重建](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:259)、[逐关联核验](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:293)、[公式依赖门禁](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:340)、[信用脉冲消费](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:1979)。

TuShare 的 `cn_gdp` 路径只保留四项名义累计水平，并把争议同比字段记为 `gdp_yoy_period_semantics_unverified`；没有可靠 PUBLIC 则为空。官方 `real_quarter_yoy` 与该接口历史同比列不能互相改名使用，信用脉冲分母也不能用实际同比代替名义水平。依据：[TuShare GDP](D:/cursor/datasourceRF/src/pring_cycle/tushare_context.py:507)、[真实原件语义测试](D:/cursor/datasourceRF/tests/integration/test_gdp_semantics.py:25)。

## 3. 可以复现的算术正例，以及其证明范围

固定原件研究输入下，社融输出窗口是 **2024-08–2026-07 的 24 个月**；GDP 输出窗口是 **2024 Q3–2026 Q2 的 8 个季度**。采用当前 YTD 路径时，实际父项是 **25 个社融 YTD 标量（2024-07–2026-07）+9 个 GDP YTD 标量（2024 Q2–2026 Q2）=34 个**；不是仅 32 个输出期次。第一笔 2024-08 社融须有 2024-07 基线，第一笔 2024 Q3 GDP 须有 Q2 基线；1 月/Q1 直接取当年 YTD，不跨年相减。代码已有检索需求的额外基线计数，保持它：[需求计数](D:/cursor/datasourceRF/src/pring_cycle/full_run_requirements.py:120)、[父项选择](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:2070)、[月度 YTD 差分](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:2282)。

独立 Decimal 重算已有输入，结果完全相等：

```text
current_12m_SF = 338600
prior_12m_SF   = 373800
current_4q_GDP = 1437047
prior_4q_GDP   = 1392784
100 * (338600/1437047 - 373800/1392784)
= -3.276124655980011793722369680 percentage_points
```

来源是[研究检查 JSON](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13/research-checks.json) 的 `credit_impulse_from_official_raw_records`。本次独立加总 24 项 `monthly_inputs[].value` 和 8 项 `quarterly_inputs[].value`，并从其 `sources` 去重，分别得到 25 与 9 个父项；没有调用公式实现。这是**可复现算术正例**，且同时是第 1 节所揭示的真实口径反例，不能用该数值作为“真实模型已正确输出”的验收结论。

仅为量化差异，8 份相应 GDP 公告的直接当季列依次为 `332910, 373726, 318758, 341778, 354500, 387911, 334193, 361511`，其两年分母合计分别为 `1367172`、`1438115`；保留相同 SF 数字时得到 `-3.796400402336842243748242280` 个百分点。**这不是建议采用值，也不是已认证替代输入。** 它仅证明默默改列会改变结果，而且仍需核清每份公告及后续修订在各 cutoff 的适用版本。

合法的新目录集成正例应在 GDP 合同和修订基线已解决后，经公开入口注册独立测试目录/候选模型、用原件导入生成本次真实关联，再调用 `build_context_projection` 的 PUBLIC 与 SYSTEM 模式，并断言输出值、单位、24/8 输出期次、真实父 ID、派生 trace 与模型采纳 ID。测试可以像现有准入夹具一样明确声明合成审查包，但必须覆盖 GDP 的定义绑定与来源审查，不能通过 monkeypatch 认证或换回内置目录绕过门禁。**目前完整真实经济口径正例未具备，本文没有执行或冒报该正例。** 依据：[公开准入先例](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:57)、[真实原件→新目录→选值→投影先例](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:3317)、[测试规格](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/spec.md:133)。

## 4. 最小错误父项 RED 路径

以下是建议交给 implement 的公开边界测试顺序，不是本轮已运行的结果。源码可证事实与预期失败分开列出。

1. **先暴露 GDP 注册缺口。** 沿用新目录公开准入夹具，保留其完整公式与 P1，明确增加 GDP 测试审查及定义绑定后，用原件 `60b12f…` 调用 `ingest_official_context_document(family="nbs_gdp", expected_period="2026-Q2", definition_version=新目录)`。期望按冻结合同保留 GDP 名义水平/实际季度同比及收据；当前注册分派没有 GDP，按源码应失败于 `registered_source_contract_not_implemented:CN_GDP`。这是前置 RED；不要捕获该错误后手工补 certified 声明冒充 GREEN。仅调用 capture 是允许的原件获取动作，但不完成这个入库合同正例。

2. **先建立可信正例，再损坏必需的旧基线。** 在 GDP 合同及同修订输入解决后的完整正例副本中，仅损坏 2024-07 社融 YTD 父项关联的 `raw` 或 `normalized` 内容，其他 33 个父项、所有最新卡片保持合格。随后经公开投影入口读取：信用脉冲须没有可采纳的当前结论，错误父项与其派生结果不得进入 `model_input_observation_version_ids`。当前 `_credit_impulse_proxy` 不核该制品，预期会暴露漏检；这尚未执行。对 2024 Q2 GDP 基线做同等反例，以免仅修社融。要断言实际采用父项而不是把所有历史/诊断 ID 都删掉：`context.observation_version_ids` 允许保留审计痕迹，现有测试也这样区分。[先例](D:/cursor/datasourceRF/tests/models/test_candidate_admission.py:3381)、[模型采纳集合](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:515)。

3. **窗口尾端无效不得静默退到旧窗。** 另建足够早期历史的副本，仅令本 cutoff 已可见的最新社融 2026-07 或 GDP 2026 Q2 选中声明质量无效/认证不足，保留旧完整窗口。当前源码先 `_certified_point` 过滤，再 `[-24:]`/`[-8:]`，有选择较旧完整窗口的路径；应报告本次所需末期不可用，不能让旧窗冒充该目标期结论。与之配对的正确例必须保留：cutoff 真在最新公告 PUBLIC 之前时，选择当时已发布的上一窗属于正常点时选择，不应被误杀。[过滤与选窗](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:2003)。

4. **原件完整不代表 YTD 基线可比。** 用第 1 节的 2024 Q3/Q4 两份完整原件保留各自真实发行身份，以 `1349084-949746=399338` 对照同公告 Q4 `373726`。在注册修订基线规则前，这应保持未认证/不可用于该季度差分；不得让“都有官方原件且数值都正”成为 GREEN 条件。2025 Q3/Q4 为第二独立反例。这里首先要明确合同能表达修订适用；现有代码尚无该判定，不能只加一个特例数值断言。

5. **只检查实际所选父项。** 在已解决口径的完整正例中增加较早、不参加该 24/8 输出窗及额外基线的坏原件，当前信用脉冲应仍能输出。配对检查一个早期但必需的基线坏原件应阻断；避免为了补漏而把全部可见历史都设为计算前置。

6. **PUBLIC、SYSTEM 与修订分别验收。** 同一修订前后 cutoff 选择不同的不可变声明，派生 ID/trace 随实际父项变化；旧结果仍可重现。公开时间无法证明的新增修订保持 `public_available_at=None`，不能因今天重新导入回填旧公告时间。SYSTEM 用实际 received/validated 边界，PUBLIC 用有证据的发布边界；一个父项 PUBLIC 未知时，不能产生 PUBLIC 合格输出。代码已有保守修订处理和 derived PUBLIC 汇总，测试应保持这些行为。[修订追加与未知时间](D:/cursor/datasourceRF/src/pring_cycle/official_context.py:428)、[派生父项及时间](D:/cursor/datasourceRF/src/pring_cycle/context_projection.py:2133)、[点时定义](D:/cursor/datasourceRF/CONTEXT.md:158)。

上述路径必须保持完整公式。`prepared_request` 默认把全部 P2 留在 `awaiting_source_certification`，不能不改其 GDP 测试绑定就期待信用脉冲成功；也不能为了得到 GREEN 去移除 GDP 依赖或把公式删出模型。正式来源认证与这种隔离的合成合同测试仍分别交付。

## 5. 现有公开测试和重放的有限证明

|既有测试/入口|已经描述的断言|不能据此证明|
|---|---|---|
|[旧目录信用脉冲](D:/cursor/datasourceRF/tests/integration/test_context_projection.py:1050)|24 个人工月度社融 + 8 个人工季度 GDP，输出 6 个百分点及精确父 ID；另有 YTD/缺月例。|使用旧目录并 patch 定义认证，没有真实获取制品，不是新注册目录全链路。|
|[YTD 算术测试](D:/cursor/datasourceRF/tests/integration/test_context_projection.py:1243)|YTD 月度/季度差分、缺月、父 ID。|没有真实 GDP 修订跨公告不等式，不能证明年度不同 vintage 的可比性。|
|[依赖认证测试](D:/cursor/datasourceRF/tests/integration/test_context_model_certification.py:355)|SF/GDP/派生定义任一未认证时拒绝；PUBLIC 未知的 SYSTEM 结果不编造 PUBLIC。|没有官方原件及新 GDP 注册合同。|
|[时效测试](D:/cursor/datasourceRF/tests/integration/test_derived_context_freshness.py:187)|根据末期判陈旧，旧预热父项本身不造成陈旧。|不是实际父项 raw/normalized 完整性核验。|
|[GDP 语义测试](D:/cursor/datasourceRF/tests/integration/test_gdp_semantics.py:92)|真实 NBS Q2 原件的季度同比列与 TuShare 累计语义分开；旧目录候选未认证时不展示合格值。|没有多期真实 GDP 注册、修订基线和 34 父项信用脉冲正例。|

当前 `record_context_replay` 会在 PUBLIC cutoff 调用投影，并检查受影响公式存在 available/current 的文档及非空父 ID；`_context_selection_gaps` 的官方制品核验主要看当期维度集合，GDP 尚不在官方核验集合，不能代替信用脉冲的整窗实际父项核验。源码依据：[逐 cutoff 重放](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:804)、[输入门禁](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:1092)。预热配置含 730 自然日，但这不是证明固定 120 个交易日各 cutoff 都有 24 月/8 季及必要差分基线的验收结果；要逐 cutoff 验证实际窗口，保持规格固定的 2026-03-09–2026-08-28 区间。[覆盖检查](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:1048)、[730 日配置](D:/cursor/datasourceRF/src/pring_cycle/model_evaluation.py:1277)、[预热与证据窗口定义](D:/cursor/datasourceRF/CONTEXT.md:119)。

## 6. 本次逐文件核验的真实输入

SF 原件均在 [A18 交付目录](D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-a18-import-20260909/receipts.json) 同层以 hash 命名。每行还按相同 raw hash/period 唯一匹配一个 `receipt`，其规范化制品读回、SHA 匹配且 total/YTD 值相等；具体 acquisition ID、normalized hash 和三段真实时钟保留在该不可变 receipts JSON，未在本报告重造关联。

|社融 YTD 期次|值：亿元|完整原件 SHA-256|
|---|---:|---|
|2024-07|188700|`52d2fe8fc26763cb262dabcce6c0256a3524dfccfd6bfa69d80a910c6c3f517b`|
|2024-08|219000|`7a24c20e66130c21640827fa9706a58b36eb8988a70b7b2309a1f10285d3d1c2`|
|2024-09|256600|`a0b08ead70f5096c3e33b9ff8c566202402a6c5edf65e00b3be2e2b685637a6e`|
|2024-10|270600|`6ad6b1f062b5265472fba83df260cf294a5981679814e0861fc406206dffca70`|
|2024-11|294000|`7e1844487f0a3983ec2b1419ed365ed2c345f4ad3c3b7b7886228ad24741b1b2`|
|2024-12|322600|`8081e0f66935a2ce9efcfea3504265858c456bbd5acc903e364c267ce9e964b5`|
|2025-01|70600|`6329aac34d9a1c717acac7e68bb32e0a2344b3e479aa37276a8cf427c65f23ca`|
|2025-02|92900|`c44f44897b31e643dd88ca7f3751d47bdb83ad0e32e0b28943adc84a163479fd`|
|2025-03|151800|`040b29b2bb7f97ebf35446c0251849f6317ab9489f675c37b8786a394b632a3b`|
|2025-04|163400|`f4272816156a6e0282a504b2a242fe2c310f6e61739b50306154945a8755a1ae`|
|2025-05|186300|`3d3053aa2cb4a4b3ad929d39e3d4dcce6947b7f5bfbecc70bf8e840447b24711`|
|2025-06|228300|`813ecda471daf222f8d6075543368c0e6414a332a6ef3841b20c9b38518c8181`|
|2025-07|239900|`16f76863da7b4ce6fb4c4680fa16b43dce8700260a0b6b872b10890c12f08a83`|
|2025-08|265600|`3952fda9138d5347905f8c826c73da65823d825b3ae72480624d806dc9d3af42`|
|2025-09|300900|`b3c5ecfe4fb6599279e3401b3ce0ef25dc5745a8f77cff7e84c9a14e1a4cd157`|
|2025-10|309000|`72d75cc14f8c6e7649d2deaec386b6b8252aeb8232a0e3586cdcffc365b3778a`|
|2025-11|333900|`86dac86009ce1615c6cec1293dbf036603fbd6fdf0f52417e1fb9fcb0902089f`|
|2025-12|356000|`47761677bcf626cfe3ab7ab444940e9c0bdcb4326621edfe7e4e54192ee0bb33`|
|2026-01|72200|`e5e5bcd61b540d1c7c4e4d68c2a6350bf090bb37c381fec2a9de359487705ad0`|
|2026-02|96000|`377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc`|
|2026-03|148300|`0d50495161d327868abe90f1a3d084249145fd63318ce0f7eaaafd00da830abb`|
|2026-04|154500|`4434210d0447e96bcbeab8f02d6ac0436fb76a28e41a66f4f133ff46d8b1182e`|
|2026-05|174800|`8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769`|
|2026-06|208400|`9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168`|
|2026-07|222500|`933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef`|

最小旧基线 RED 的社融收据为 `acquisition-9b253d26a75e46128c8ae037bffc7ca7`，其 raw 为首行 hash，normalized 为 `8de2c8bb72f354e8943b7c465f8fd3bca5dcee11c3884e6b7274b5f37f2fca75`；只应在隔离测试副本构造损坏，不改此原交付。

|GDP 期次|当份公告 YTD：亿元|当份公告当季：亿元|bytes|完整原件 SHA-256|
|---|---:|---:|---:|---|
|2024 Q2|616836|320537|261785|`d33f512e347eea7d13cbcac6f1fde4b5d37446150f3c867f4322389f2dbb6a26`|
|2024 Q3|949746|332910|295437|`0da0c7a1280c81f8cbef568bc70abf1c83e925eb02a28c491af872738dd5f761`|
|2024 Q4|1349084|373726|295304|`278383cce68511b7668d5ec7bd35fe7403ab9741636dbbf2585ca78689a0d716`|
|2025 Q1|318758|318758|236490|`4d38107d8ac9c1c063aaf016584817fea51c8ad9ca64f8857eb73af2b550875e`|
|2025 Q2|660536|341778|261934|`9a770677d59a781751b4d7c0070c250a4fa53210afccdda5efac0a12ce156f64`|
|2025 Q3|1015036|354500|262370|`0f7c85e52242f3e1905d3313aa744028f51d48f60bcff899b712da400f135a5c`|
|2025 Q4|1401879|387911|267383|`9d9bc9ece5d52a9ba07d6d9ed01e0d865b4d72b385c1b2a9873501e2d5532765`|
|2026 Q1|334193|334193|238636|`61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18`|
|2026 Q2|695704|361511|263170|`60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915`|

## 7. 读取输入指纹

以下相对路径以 `D:/cursor/datasourceRF` 为根。SHA 为本次读到的文件内容；不以旧 HEAD 代替未提交源码指纹。原件 34 个 hash 已在上表列全。

|输入|bytes|SHA-256|
|---|---:|---|
|`CONTEXT.md`|20103|`f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102`|
|`.scratch/pring-data-acquisition-repair/spec.md`|27762|`f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4`|
|`src/pring_cycle/context_projection.py`|87349|`4f2d4080a857118b693ac1e114a9d086062a879f4e9f87d5a3759383bcfbd568`|
|`src/pring_cycle/tushare_context.py`|78830|`ea66afd3b57969fbd2bcf76889e0bfb7e92037bd1ee12e931b4d14dde2b340a4`|
|`src/pring_cycle/official_context.py`|84300|`fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11`|
|`src/pring_cycle/source_contract_review.py`|14630|`c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772`|
|`src/pring_cycle/metric_contracts.py`|9849|`b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66`|
|`src/pring_cycle/model_evaluation.py`|49636|`ece7dee6598b18582cf1b35bd4fd518738a7597119d231e6a62be37cc328e2e3`|
|`src/pring_cycle/full_run_requirements.py`|7478|`eea86ff5a7f0a5628eaa90ad75e015c134d5c466f17a52375ee05a0c8164eefa`|
|`tests/integration/test_context_projection.py`|59768|`82e2c192745e43088a120bc831c67090b9f920cd4ad361e60ce8b4027e2e2a19`|
|`tests/integration/test_context_model_certification.py`|20067|`53c48ee832afd465e2b4dc659e603d83e4b8005d9d8aaffb05d5efcd9ea03cee`|
|`tests/integration/test_gdp_semantics.py`|10456|`76fae51ea96014cbc7f31cb82e4d332e447d531240d374514df714e73d9096a7`|
|`tests/integration/test_derived_context_freshness.py`|10393|`ca7045fcb14d7425a4ec248eba574a513e9644dc28ec6f8abfb86277f0c2fd7f`|
|`tests/models/test_candidate_admission.py`|275479|`e8751132db00ea99689f69710c6f8d0a8afdbc726bcc4f8f083297a6b3a74829`|
|`.scratch/pring-data-acquisition-repair/evidence-13/research-checks.json`|85434|`921c7b9de8e5bb75cdadc5809257f5f0fc9e089265c96af0489047f5055922ed`|
|`.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json`|1622488|`65a153a43ee952ff40640f5faa86c83539f832d1075fbb652b5dc539c656d977`|
|`.scratch/pring-data-acquisition-repair/evidence-a18-import-20260909/receipts.json`|433467|`199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c`|
