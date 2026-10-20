# 其余常规官方宏观：公开消费资格的下一切片

2026-09-09，只读工作树研究；读取时 HEAD 为 `99c495a217b66d4bca9d6ceae4688ee69d4382bb`，包含当前未提交 PMI 合并修复。未运行应用、测试、WSL 或网络；以下反例均为待 RED 的静态设计，不是已复现缺陷，也不是正式来源认证或真实模型回放。

基数沿用[准备包 v2](p1-official-preparation-v2.md#L7)：250 原件、11 家族、18 指标、268 次解析、1858 标量；**1857 格严格相符，另 1 格 Q1 产能累计 73.6 映射待定**。扣除 CPI 两指标、PMI 三指标，本报告涉及 **9 家族、13 指标**，不重新审计全表。现成[九组公开测试参数](../../tests/models/test_candidate_admission.py#L2792)复用 7 份独立原件，预期导入合计 91 条声明；这是测试参数统计，不是本轮执行结果。

## 当前入口及实际边界

1. 官方原件导入公开入口为 [`ingest_official_context_document`](../../src/pring_cycle/official_context.py#L335)，HTTP 入口为 [`refresh_official_context_document`](../../src/pring_cycle/official_context.py#L502)。前者保存 `document_import` 回执，后者使用 `official_http_get`；均产生完整 `ParsedOfficialContextRelease`，随后经 [`ingest_acquired_official_release`](../../src/pring_cycle/official_context.py#L375)逐标量声明并关联 acquisition。原件重核已经有 [`source_claim_acquisitions_many`](../../src/pring_cycle/evidence.py#L303)：关联回执必须 validated，raw 和 normalized 均可读且 hash 正确，任一关联失败则该 claim 的可用原件集合为空。
2. 可复用 [`parse_official_acquisition`](../../src/pring_cycle/official_context.py#L247)及 [`official_claims_matching_acquisitions`](../../src/pring_cycle/official_context.py#L281)：按回执的 family/URL/period/received_at 重解析 raw，并重建**整篇公告** normalized hash，再匹配所选 claim 的 URL+raw hash、顶层发布时间、指标/维度/值/期次。每次调用按 acquisition ID 缓存解析，允许一篇原文产多指标；它是取值资格检查，不能赋予 certification。
3. **当前实际启用范围仅 `nbs_pmi`、`nbs_core_cpi`**，见[常量](../../src/pring_cycle/official_context.py#L93)。[`ModelInputSelector.select`](../../src/pring_cycle/search_evidence.py#L122)、上下文 [`_metric_rows`](../../src/pring_cycle/context_projection.py#L1353)、PUBLIC 回放 [`_context_selection_gaps`](../../src/pring_cycle/model_evaluation.py#L1188)都依赖该常量且跳过内置旧目录。余下九家族已能走新目录字段守卫和公共导入，但目前没有因此自动执行上述消费重核。
4. Worker 可按 source_url 与指标集合选择[官方家族](../../src/pring_cycle/worker.py#L664)，再[刷新并本地重选](../../src/pring_cycle/worker.py#L806)。独立静态阻断：此函数 L836–840 调 `metric_definition(..., definition_version=...)` **未传 database_path**，而[目录查询](../../src/pring_cycle/catalog.py#L409)对非内置版本仅在提供 DB 路径时解析登记定义，否则抛 `unknown_metric_definition_version`。现成九组测试直接导入后调用 selector，未覆盖这段刷新后检查。应先从公开 targeted-refresh/Worker 运行接口复现；只能 mock 官方 HTTP，不能 mock 掉目录查询或整个 refresh 来得到假绿。

## 可直接复用的原件与独立期望

表中 A–G 的精确字节/hash 在末表。所有值都来自已审原表/段落，不以本轮应用解析生成期望；括号为该公开测试期望导入声明数。

| 现成参数 / family | 原件、统计期 | 最少独立断言及来源 |
|---|---|---|
| ppi / `nbs_ppi` | A，2026-07（9） | `CN_PPI` headline/yoy=`3.5 percent`；[已审格 62](p1-ppi-full-value-audit.md#L140)。原件当前实际数字在 L352，L351 是该单元格起始标签。 |
| industrial-va / `nbs_industrial_value_added` | B，2026-07（3） | `CN_INDUSTRIAL_VA` current_month_real_yoy=`4.5 percent`；[已审格 18](p1-industrial-va-full-value-audit.md#L89)。 |
| industrial-finance / `nbs_industrial_finance` | C，2026-07（10） | 营收 revenue/ytd_level=`809230.7` 亿元；库存 nominal_end_level=`72700` 亿元；周转 official_yoy_change=`0.6 days`，是同比增加天数。[格 61–70](p1-industrial-finance-full-value-audit.md#L156)。 |
| capacity-q2 / `nbs_capacity_utilization` | D，2026-Q2（3） | all_industry/yoy_change=`-1.0 percentage_points`，不是环比下降 0.6；[原表独立定位](p1-capacity-utilization-full-value-audit.md#L48)。Q1 待定字段不纳此正例。 |
| money / `pbc_money` | E，2026-07（4） | `CN_M1_M2` m1/balance：原文 `115.46 万亿元` → `1154600 hundred_million_cny`；[独立格 25](p1-money-full-value-audit.md#L90)。只准备 M1/M2，原页出现 M0 不自动扩目录。 |
| social-financing / `pbc_social_financing` | E，2026-07（27） | `CN_SF_TOTAL` stock_end `463.27 万亿元` → `4632700`；`CN_SF_COMPONENTS` government_bonds/ytd_increment `7.76 万亿元` → `77600`。[总量和分项原表](p1-social-financing-full-value-audit.md#L1375)。 |
| loans / `pbc_loan_structure` | E，2026-07（9） | enterprise/long_term/ytd_increment `5.32 万亿元` → `53200` 亿元；[已审 EL 格](p1-loan-structure-full-value-audit.md#L773)。累计增量不可直接当七月单月。 |
| tools / `pbc_tool_liquidity_monthly` | F，2026-07（24） | `7天期逆回购` net_injection=`-2495` 亿元；原表同时列投放 47395、回笼 49890，[独立三格](p1-tool-liquidity-full-value-audit.md#L205)。使用源表净额，不把负数拒绝。 |
| omo / `pbc_omo_notice` | G，2026-08-28（2） | `CN_OMO_7D_AMOUNT` injection=`200` 亿元；`CN_OMO_7D_RATE` `{}`=`1.40 percent`；[原表 T16R2](p1-omo-full-value-audit.md#L178)。 |

直接正例已断言 PUBLIC/SYSTEM 的值、单位、source_reference 和检索 complete；上下文仅断言导入 IDs 属于 `context.observation_version_ids`，[见测试尾部](../../tests/models/test_candidate_admission.py#L2958)。**此集合包含诊断证据，不能代替实际采用验收。**新增反例应检查 `macro.model_input_observation_version_ids`、行状态、派生父项及回放 gaps；失效声明仍可保留在诊断字段。[实际采用与诊断分开组装](../../src/pring_cycle/context_projection.py#L514)。

## 派生父项与跨期选择

| 消费路径 | 当前只读定位 | 下一最窄资格边界 |
|---|---|---|
| PPI、工业/产能、M1/M2、工具月表的直接方向/证据；前期方向输入 | `_metric_rows` [当前及前期](../../src/pring_cycle/context_projection.py#L1421) | 常量扩展后复用现有 incomplete_source_claims；当前行不能靠剔除坏值改取旧期，前期损坏则不参与方向及方向父项 ID。 |
| 实际库存近似值（库存÷PPI） | [`_real_inventory_proxy`](../../src/pring_cycle/context_projection.py#L1820)只从两个 status=current 行取值，要求同一期 | 已经消费投影状态，无需再写另一套 raw 解析；扩展父项校验后验证任一父项失效时无 available 派生值、无采用 ID。保持“近似、非官方统计”标签。 |
| OMO 净投放 | [`_derived_market_context_rows`](../../src/pring_cycle/context_projection.py#L691)对 reported_amount_points 仅用 `_certified_point` 分有效/无效，再计算当日或交易日到期；[v2 无效到期处理](../../src/pring_cycle/context_projection.py#L761) | 将原件资格失败也纳入现有 invalid_amount_points/periods 和 invalid_maturity_dates，不能先丢失输入再把到期额当 0。只更新符合本批资格的来源；冻结 v1 同日公式、v2 交易日日历语义不变。 |
| DR007−7 天政策利率 | [L820–849](../../src/pring_cycle/context_projection.py#L820)经 `_latest_certified_point`；该函数[先过滤认证质量再取最后一条](../../src/pring_cycle/context_projection.py#L1301) | 对 OMO 利率先确定 cutoff 下最后一个实际已公开事件，再核其原件；坏事件不能回退前一事件。合法无利率列日则仍可采用此前有效事件，不能硬要求每日新利率。DR007 属银行间解析器，不能用官方宏观 helper 误验其 normalized。 |
| 贷款累计→月增 | [L954–1003](../../src/pring_cycle/context_projection.py#L954)从 series 直接过滤 `_certified_point`，每 borrower/tenor 排序取最后两期 | 先确定该成员当前期及所需比较期，再验证二者原件；最新期失败不能退回较早两个月形成 current。保留一月直接取当年累计、其他月份要求相邻期的[既有跨年反例](../../tests/integration/test_loan_ytd_year_boundary.py#L16)。 |
| 信用脉冲 | [`_credit_impulse_proxy`](../../src/pring_cycle/context_projection.py#L1925)直接取社融月增/YTD、GDP 季度/YTD，仅 `_certified_point`；要求 24 月及 8 季并处理前置累计 | 社融实际用到的全部窗口及累计差分前置父项均需重核，不能仅验卡片最新一期。剔除失败后不能另找更旧的完整窗口。GDP 另有新目录阻断，见下文；不能用无原件合成 GDP 来宣布真实新目录公式已通。 |

`_certified_point`[仅检查选中状态、reported value、certified、validated](../../src/pring_cycle/context_projection.py#L2144)，未读取 CAS。PMI 的 `_certified_points_by_period` 已有[最新期失效不回退](../../src/pring_cycle/context_projection.py#L1253)处理，但其附加资格条件明确限定 PMI；不能据此声称上表其他父项已覆盖。

PUBLIC 回放[逐中国目标日日末选择并构造上下文](../../src/pring_cycle/model_evaluation.py#L802)，直接门检查 latest validation_points，而派生可能采用更早窗口。扩常量能覆盖直接门，不能代替派生父项接通。`_context_source_snapshot`[保留覆盖/派生所需的历史声明](../../src/pring_cycle/model_evaluation.py#L919)是诊断输入快照，不应全删。[`formula_requirements`](../../src/pring_cycle/full_run_requirements.py#L91)已有 24 月/8 季及必要前置计数，也不能把足够条数当原件资格通过。

## 下一轮公开 RED 顺序与合法差异

1. **公开 Worker 切片**：新登记目录＋PPI A 的真实 HTTP 响应 fixture，从 Run 提交/Worker 公开执行入口走官方刷新，断言最终本地 selection；定位上述 DB 路径遗漏。不能因声明已入库就认为 Worker 成功。
2. **九参数原件失效切片**：复用已有导入正例，先验证实际采用，再分别使 raw/normalized 缺失、内容 hash 不符；追加“错误 normalized 与其自身 hash 一致、但不匹配 raw 重解析”的反例。检索应 incomplete，直接卡片 source_failed，不含坏父项的模型采用列表；同一 E 原文分别按 money/social/loans 导入时应按各自 family 回执核验，不要求它们的 normalized 相同。独立数值锚点沿上表，不重新生成全表。
3. **合法形状与跨期反例**：复用[缺列正例](../../tests/models/test_candidate_admission.py#L2987)、[社融双公告](../../tests/models/test_candidate_admission.py#L3278)、[OMO 真零无利率列](../../tests/models/test_candidate_admission.py#L3115)，再分别损坏其中一个所需原件。社融 2024-01 两页为 18＋9 条声明，检索已预期 17→26 个成员、仅两页齐全后 complete；不能要求每份公告都包含全部 27 标量。OMO 无操作利率是未披露，金额 0 是已披露，两者不能合并为“都缺失”或“都补零”。PPI 一月仅 6 格；工业增加值 1—2 月合并期是 YTD 6.3、二月环比 0.83，不添加一月或二月单月同比。
4. **派生及 PUBLIC 回放**：先做 PPI＋库存、OMO 当前/到期父项、贷款两期这三个小切片；分别破坏旧比较期、最新期和同统计期后续修订。再按[现成 PMI 公开回放结构](../../tests/models/test_candidate_admission.py#L2435)扩至 PPI/贷款/OMO，断言 target cutoff 前后的声明版本、gaps 和实际父项 IDs；只有旧期损坏时也不能继续输出使用该旧值的方向/派生。信用脉冲沿[现有持久化及原始输入版本测试](../../tests/integration/test_context_projection.py#L1050)设计窗口反例，但该测试是旧目录隔离 fixture，不能当新目录官方 GDP 正例。先保持其现有兼容语义，再为已接通的官方父项增加资格。

必须保留的归一化差异：

- 一份官方回执 normalized 是完整 release 对象（family/provider/release_event_id/period/release_at/public_available_at/source_url/scalars），不是 LPR 数组，也不是 TuShare 同 API 多日请求联合输出。按 family+acquisition 重解析；共享缓存只复用解析事实，不能跨 cutoff 缓存选中版本或永久复用“文件有效”。
- [仅日期原页](../../src/pring_cycle/official_context.py#L208)顶层 PUBLIC 依既定保守规则到次日本地日，而 scalars 用 release_at 构造，可能仍是 null；[同时间或无新时间修订](../../src/pring_cycle/official_context.py#L416)入库后可清空 claim release/public 并改为 unresolved event。不能把整个 claim JSON 与采集 normalized 生硬比较；当前 helper 允许双空时间，但任何新增非空时间必须与源证一致。PUBLIC 未知的修订仍仅在合适的 SYSTEM 查询中可见。
- `definition_version`、certification、available_at 是入库/目录事实，[由回执及目录构造](../../src/pring_cycle/official_context.py#L442)，不要求它们在采集 normalized 中同值。TargetBound 查询[连 SYSTEM 也施加目标日日末 PUBLIC 上界](../../src/pring_cycle/context_projection.py#L589)，不得为了让未知 PUBLIC 正例通过而移除此限制。
- 数值单位必须按已冻结成员逐项保留：[PPI、工业与产能](../../src/pring_cycle/metric_contracts.py#L105)的 percent/percentage_points/days、month/year_to_month/quarter/year_to_quarter 不混；[M1/M2、社融、贷款及工具](../../src/pring_cycle/metric_contracts.py#L147)的余额/累计/同比不混。用原表营收 809230.7 亿元，不拿正文舍入 80.92 万亿元替换。M1 历史可比口径与 Decimal 缩放修复沿已审规格，不新增全系统 Decimal 改造。Q1 ytd_rate 继续被[现有明确守卫](../../src/pring_cycle/source_contract_review.py#L205)拒绝，不能为了全绿静默删字段/认可复用。

## GDP、USDCNY、RRR 的分界

[`source_families`](../../src/pring_cycle/source_families.py#L28)及[官方 parser 分派](../../src/pring_cycle/official_context.py#L639)确有 `nbs_gdp`；`pbc_usdcny_central_parity` 也列于[官方家族](../../src/pring_cycle/source_families.py#L68)。但 `official_source_members` 无 GDP/USDCNY 分支，[新目录其余明确 contracts](../../src/pring_cycle/source_contract_review.py#L211)也不含二者，因此新目录入库会走 `registered_source_contract_not_implemented` 分支；此为静态调用判断。GDP 不计 A18 18 项，作为信用脉冲分母单列；USDCNY 不以 P1 原件缺件范围擅增本批。TuShare 定向路径另外支持[季度 GDP 和部分月度宏观 API](../../src/pring_cycle/targeted_context.py#L43)，不代表它们满足新目录指定的官方 provider，更不能套用官方 release normalized 检查。

RRR 共享官方导入器，却在消费阶段走 [`select_published_rrr_events`](../../src/pring_cycle/published_events.py#L17)→[`source_claim_publication`](../../src/pring_cycle/evidence.py#L353)的整篇公告 raw+normalized、scope/measure 完整性检查；[回放也保留整段可见事件后再选成员](../../src/pring_cycle/model_evaluation.py#L1116)。它不是固定日度矩阵，本报告不改其公告/生效日或持续率语义。内置旧目录兼容、新目录正式认证、active 门及真实 120 日证据仍按[修复规格](spec.md#L103)独立验收。

## 本次只读原件校验

文件名即完整 SHA256；以下 11 份均已用 Windows 标准库重新计算，hash 与文件名完全一致。总字节数在末尾机器自检摘要中记录。原件取得时间仍归各自旧回执；本轮读取时钟不回填其历史获取或公开时间。

| 键 | 精确本地原件（链接末段为 SHA256） | bytes |
|---|---|---:|
| A | [b3232612](evidence-13/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09#L352) | 251797 |
| B | [d8a9cc43](evidence-13/d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609#L357) | 393331 |
| C | [28388ca9](evidence-13/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986#L365) | 494713 |
| D | [8d1eadce](evidence-13/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8#L359) | 168665 |
| E | [933f3546](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef#L359) | 44692 |
| F | [10ed3fb5](evidence-13/10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0#L395) | 44678 |
| G | [ee19f9d0](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a#L362) | 31000 |
| 一月 PPI | [e7e65eb8](evidence-official-consumer-edge/e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943) | 218312 |
| 1—2 月工业 | [2115d7cc](evidence-official-consumer-edge/2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e) | 282785 |
| 社融存量公告 | [42312d60](evidence-official-consumer-social/42312d6054e2df029dfeeba68c7c60fc4bc45934cb72bdd739c143e1c9f02243) | 28469 |
| 社融增量公告 | [d0ae83ce](evidence-official-consumer-social/d0ae83ced9ad510a057a853f51b185e729ed81c9cd5e958fa988c7b10a676d9d) | 27795 |


## 输入快照指纹与交付自检

以下为本轮实际引用/承接输入的 bytes 和 SHA256；原件 11 份已在上表单列。仅绑定当前读取的工作树，不把此前报告的静态问题冒称当前行为。哈希时钟 `2026-09-09T03:16:09.360073+00:00`。

| 路径（相对本文） | bytes | SHA256 |
|---|---:|---|
| `../../src/pring_cycle/catalog.py` | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| `../../src/pring_cycle/context_projection.py` | 84130 | `38943a1398869e5e29bd3ac139908cd27f913fb6405b8218001c02e2ef8660a2` |
| `../../src/pring_cycle/evidence.py` | 60796 | `d27332e14065b179f510c6253e06088f376341349657b598bc692070d9c35ec2` |
| `../../src/pring_cycle/full_run_requirements.py` | 7478 | `eea86ff5a7f0a5628eaa90ad75e015c134d5c466f17a52375ee05a0c8164eefa` |
| `../../src/pring_cycle/metric_contracts.py` | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| `../../src/pring_cycle/model_evaluation.py` | 49072 | `2beb799b373e3e834ea1ad92e466a7b537229ec2ffb49940f7039ed5336684c8` |
| `../../src/pring_cycle/official_context.py` | 84003 | `dd351727e0e41df2e7616cd2ebeb2b18271ce23cf90b5987c784eb48ae2888af` |
| `../../src/pring_cycle/published_events.py` | 4171 | `b3463f972b2b500c7a867e865acfc45968360b9bd636cd7fd574631d203c7c62` |
| `../../src/pring_cycle/search_evidence.py` | 18220 | `81a6b6fdcb4482de7ae33d075eb0990fab9a7b2f1f8b51635d8153f0a0814bcb` |
| `../../src/pring_cycle/source_contract_review.py` | 14630 | `c26ee6a06e25dc7b9b3c4c102bc9ce3e780dbc538760ef9318409d28f5ab9772` |
| `../../src/pring_cycle/source_families.py` | 2487 | `420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e` |
| `../../src/pring_cycle/targeted_context.py` | 6396 | `3601a81cd1b505c38f4762cf2c885ee2214851ec8b5f3dd523eb35b124a5cdeb` |
| `../../src/pring_cycle/worker.py` | 58810 | `34a9a9e332872269852a22d7b8f0798a6cb8ab610fd09a9644b4f6739732d96b` |
| `../../tests/integration/test_context_projection.py` | 59768 | `82e2c192745e43088a120bc831c67090b9f920cd4ad361e60ce8b4027e2e2a19` |
| `../../tests/integration/test_loan_ytd_year_boundary.py` | 7018 | `f8e6a62df8980bf6e1e7b761c27009a98d2bf9460c91f2180e3e184b8a2941ac` |
| `../../tests/models/test_candidate_admission.py` | 231772 | `e03a3230e9f004faf8a51bf0bfe2b1cbd8627d10de3b245315b120990fcee0a9` |
| `evidence-13-preparation-v2/preparation.json` | 3189072 | `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034` |
| `official-macro-normalized-next-step.md` | 14931 | `b30913ac8be775e8201f7a7ff10dc427c09abe6378c809749075d0699bb8d39d` |
| `p1-capacity-utilization-full-value-audit.md` | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| `p1-industrial-finance-full-value-audit.md` | 24950 | `f14f4f98f8050386a7f9f9f0f3e4d84c75b56c6dffa743d8b47c6e2ed1d3ab7d` |
| `p1-industrial-va-full-value-audit.md` | 16362 | `ef2e599944f049fab8a7bcce34aede93ac29dd2c33c5cd0a2541faf4d0984406` |
| `p1-loan-structure-full-value-audit.md` | 66620 | `2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae` |
| `p1-money-full-value-audit.md` | 16643 | `44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda` |
| `p1-official-preparation-v2.md` | 2841 | `6623bd19acee525d3a2a18eec7749e908bf28e17b52e6f6012c92f4a7291b688` |
| `p1-omo-full-value-audit.md` | 81481 | `d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e` |
| `p1-ppi-full-value-audit.md` | 21333 | `b8228fb7eee93ca00363419b909bc3c23b0346117e22a3699cdaf374a88be8d1` |
| `p1-social-financing-full-value-audit.md` | 147300 | `a649d2b86df819fa2682c46997a0cec0fd4021c8d702225ddc6ff3a920cb7437` |
| `p1-tool-liquidity-full-value-audit.md` | 25421 | `13a84f6fcd6ee23827c9d4700d3b4af999a5a2ec40455729bdbf432c44b08fbb` |
| `spec.md` | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |

自检：72 个本地 Markdown 链接均存在，涉及 38 个不同文件；所有行号均在实际文件范围内；11 份已存原件共 1,986,237 bytes，11/11 SHA256 与文件名相符。另读取旧宏观边界与 v2 准备 JSON 的指纹如上。网络、应用、测试请求均 0。唯一新增文件为 `official-macro-remaining-consumers.md`；未生成新原件包、未修改旧文件。本文最终字节数与 SHA256 由交付消息给出，避免自引用哈希。
