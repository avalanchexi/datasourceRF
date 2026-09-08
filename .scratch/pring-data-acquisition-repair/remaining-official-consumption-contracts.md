# 其余 16 项 A18 官方指标的新目录消费契约

2026-09-08，研究基点 HEAD `395dde73b93169d78374bb72a763641144c98dca`。结论绑定文末工作树文件指纹，包含当前 LPR/CPI 注册目录消费实现；没有把父代理正在运行的全套结果当作本研究验证。本轮只读源码、固定 preparation-v2 和已有逐值审计，用 Windows 标准库统计身份与核对选定原件 SHA；未联网、运行应用/测试、访问数据库、认证或改写旧包。唯一交付为本文。

**下一批可以围绕同一个公开入库—点时查询—选择—投影链路批量接通，但不能只增加 16 个白名单项。** 现有 10 个官方家族解析器已经覆盖材料；新目录的 certified 声明目前全部被来源消费守卫拒绝，其中 9 项另缺模型选择所需成员契约。混合单位和混合期次必须按成员绑定。Q1 产能累计的源格复用仍待定，不随批量接通放行。

范围按 [A18 前置研究](a18-certification-next-boundary.md) 与 [新准备说明](p1-official-preparation-v2.md) 收敛：A18 是 18 个指标，LPR 不在这 18 个内；本轮排除 CPI 总体、核心两项，剩 **16 指标 / 10 家族 / 260 条既有解析记录 / 242 唯一原件 / 18,218,406 原始字节 / 1812 个准备标量**。其中 1811 个有已完成的独立字面核验承接，1 个 Q1 产能累计源映射待定。不是本轮重跑 260 次解析，也没有重审 1812 格；不是 61 项注册目录全部可用或来源认证通过。

## 当前消费状态和首个拒绝点

| 层 | 当前已经支持 | 确切不足及下一步验证 |
|---|---|---|
| 目录身份 | [catalog.py L397](../../src/pring_cycle/catalog.py#L397) 传 database_path 时可解析已登记新版本；[catalog_registry.py L49、L71、L108](../../src/pring_cycle/catalog_registry.py#L49) 保证同版本定义集合唯一、绑定准入模型并校验清单 | 无需恢复旧“新版本必然 unknown”的结论，也不得重写 v3。一个新版本能登记，不表示其 61 项来源均认证 |
| 原件到候选声明 | [official_context.py L279–374](../../src/pring_cycle/official_context.py#L279) 共用 acquired 原件、真实回执和数据库定义；10 家族均有公开 parser dispatch | `awaiting_source_certification` 且单位/维度合格的候选可存。只有 `certified` 声明才触发下列新目录来源守卫；不能把“待认证可存”称为模型可用 |
| certified 入库 | [evidence.py L1133–1159](../../src/pring_cycle/evidence.py#L1133) 先核目录、单位集合、维度键、认证状态；L1148 调来源守卫 | [source_contract_review.py L110–116](../../src/pring_cycle/source_contract_review.py#L110) 只列 LPR/CPI；本轮 16 项均报 `registered_source_contract_not_implemented:<metric_id>`。若定义的单位/维度先错，会更早报 `evidence_unit_mismatch`/`evidence_dimensions_mismatch`。这是源码确定分支，本轮没有执行 RED |
| PUBLIC/SYSTEM 基础查询 | [evidence.py L653、L694](../../src/pring_cycle/evidence.py#L653) 用观测身份/definition_version 和对应时钟筛选，不另硬编码这 16 项 | 必须验证新旧版本隔离；`public_available_at=None` 不进入 PUBLIC。待认证声明不因可查而成为 certified 值 |
| 模型输入选择 | [search_evidence.py L40–135](../../src/pring_cycle/search_evidence.py#L40) 已解析新目录并绑定目标日、来源认证及质量 | 有维度却没有 required members 时明确 `dimension_contract_unavailable`。目前 6 项有显式成员要求，OMO rate 空维度可用 `{}`，其余 9 项没有；见下表。因此仅扩大入库守卫会出现“入库成功、选择失败” |
| 工作者/模型验收 | [worker.py L1093–1144](../../src/pring_cycle/worker.py#L1093)、[model_evaluation.py L830–897](../../src/pring_cycle/model_evaluation.py#L830) 已调用同一 `required_dimension_members` | 两处将无成员契约转为 `()`，没有像 selector 一样明确拒绝，可能只检查已存在的行。下一批至少用“合法缺列”和“应有成员缺失”同一组公开反例验证，避免三方判定不同 |
| 上下文投影 | [context_projection.py L29–78、L161–269](../../src/pring_cycle/context_projection.py#L29) 全部 16 项已在政策/信用/生产/价格/库存分组；定义由 embedded manifest 读取 | 没有发现另一个专门禁止本轮 16 项新版本的投影名单。仍需从实际入库值走投影验证字段、维度和状态，不能只测 manifest validator。L258 的投影要求完整相关目录，不能只造 16 项残缺清单求绿 |

守卫现签名只有 definition/provider/period_kind/dimensions，没有 claim.unit，也没有 period_start/end 或 source_field。单纯把混合单位整体放入 `allowed_units`，无法阻止“货币余额以 percent 入库”或“周转天数同比被当 percent”。下一批应在现有声明验证边界实现**成员—单位—期次绑定**，可以最窄传入必要字段，不需要全系统数值类型或证据表重构。source_field 是 parser 标量字段，尚非 SourceClaimInput 的持久字段；不要在测试中假定该字段已直接存入 claim，原文追溯仍需 source_reference/CAS 与 acquisition 关联。

## 16 项目录字段

下表是供新定义采用并逐项验证的**现存 v3 结构基线**（不继承旧 certified 标签），不是本研究冻结新目录。字段来自 [catalog.py L121–159、L235–251、L341–380、L435–618](../../src/pring_cycle/catalog.py#L121) 和 [source_families.py](../../src/pring_cycle/source_families.py)。`source_codes` 按现值保留，不能为整齐而发明 `PBC_MONEY_*`/`NBS_PMI_*` 代码。全部 release_rule=`source_schedule_required`，release_timezone=`Asia/Shanghai`；这不是固定发布时间。

缩写仅为表格紧凑：A=`hundred_million_cny`；P=`percent`；D=`days`；PP=`percentage_points`；DI=`diffusion_index_points`。`unit ; allowed_units` 顺序为目录原结构，须在实现/测试中使用完整字符串。NBS provider 精确为 `国家统计局`、域 `www.stats.gov.cn`；PBC provider 为 `中国人民银行`、域 `www.pbc.gov.cn`。frequency 是发布频率，不能替代具体 period_kind。

| # / metric_id | provider | source_codes（单元素 tuple） | unit ; allowed_units | frequency | release_event_family | dimensions 键顺序 | selector 当前要求 |
|---|---|---|---|---|---|---|---|
| 1 `CN_PMI_ACTIVITY` | NBS | `CN_PMI_ACTIVITY` | DI ; (DI) | monthly | nbs_pmi | (series,measure) | 4 成员已有 |
| 2 `CN_PMI_INVENTORY` | NBS | `CN_PMI_INVENTORY` | DI ; (DI) | monthly | nbs_pmi | (series,measure) | 2 成员已有 |
| 3 `CN_PMI_PRICES` | NBS | `CN_PMI_PRICES` | DI ; (DI) | monthly | nbs_pmi | (series,measure) | 2 成员已有 |
| 4 `CN_PPI` | NBS | `CN_PPI` | P ; (P) | monthly | nbs_ppi | (measure,category) | **缺** |
| 5 `CN_INDUSTRIAL_VA` | NBS | `NBS_INDUSTRIAL_VA_HTML_V1` | P ; (P) | monthly | nbs_industrial_value_added | (measure) | **缺** |
| 6 `CN_INDUSTRIAL_FINANCE` | NBS | `NBS_INDUSTRIAL_FINANCE_HTML_V1` | A ; (A,P) | monthly | nbs_industrial_finance | (item,measure) | **缺** |
| 7 `CN_FINISHED_GOODS_INVENTORY` | NBS | `NBS_INDUSTRIAL_FINANCE_HTML_V1` | A ; (A,P) | monthly | nbs_industrial_finance | (measure) | **缺** |
| 8 `CN_INVENTORY_TURNOVER` | NBS | `NBS_INDUSTRIAL_FINANCE_HTML_V1` | D ; (D,P) | monthly | nbs_industrial_finance | (measure) | **缺** |
| 9 `CN_CAPACITY_UTILIZATION` | NBS | `NBS_CAPACITY_UTILIZATION_HTML_V1` | P ; (P,PP) | quarterly | nbs_capacity_utilization | (industry,measure) | **缺**；Q1 映射待定 |
| 10 `CN_M1_M2` | PBC | `CN_M1_M2` | A ; (A,P) | monthly | pbc_money | (aggregate,measure) | 4 成员已有 |
| 11 `CN_SF_TOTAL` | PBC | `CN_SF_TOTAL` | A ; (A,P) | monthly | pbc_social_financing | (measure) | 2 最低成员已有；非全部 3 字段 |
| 12 `CN_SF_COMPONENTS` | PBC | `PBC_SOCIAL_FINANCING_HTML_V1` | A ; (A,P) | monthly | pbc_social_financing | (component,measure) | **缺** |
| 13 `CN_LOAN_STRUCTURE` | PBC | `PBC_LOAN_STRUCTURE_HTML_V1` | A ; (A,P) | monthly | pbc_loan_structure | (borrower,tenor,measure) | **缺** |
| 14 `CN_TOOL_LIQUIDITY_MONTHLY` | PBC | `PBC_TOOL_LIQUIDITY_HTML_V1` | A ; (A) | monthly | pbc_tool_liquidity_monthly | (tool,measure) | **缺** |
| 15 `CN_OMO_7D_AMOUNT` | PBC | `PBC_OMO_NOTICE_HTML_V1` | A ; (A) | daily | pbc_omo_notice | (measure) | injection 已有 |
| 16 `CN_OMO_7D_RATE` | PBC | `PBC_OMO_NOTICE_HTML_V1` | P ; (P) | daily | pbc_omo_notice | () | 空维度 `{}`；有效频率 event |

默认 `metric_definition(metric_id)` 取 v2，不等于此基线：PMI 三项/PPI/M1-M2 的 v2 release family 是 metric_id 小写；工业 VA 的 v2 allowed unit 是 scalar，v3 才修为 percent；多项财务的 v2 `unit=scalar` 而 allowed_units 已有 A/P，v3 主单位取 allowed_units[0]。复制 CPI 的“与默认 v2 全字段相等”写法会误拒正确新定义。应明确版本化结构，保留 v3 固定哈希与旧 guard，不修改旧定义以迎合新路径。[对应目录构造](../../src/pring_cycle/catalog.py#L271)、[v3 覆盖](../../src/pring_cycle/catalog.py#L341)、[v2 family 回退](../../src/pring_cycle/catalog.py#L661)。

上表 turnover 的 P、loan 的 P 是旧目录可容纳单位，**不是本批真实字段得到的单位证据**。本批两个 turnover 成员均只准 D；九个贷款成员均只准 A。保留目录结构兼容时也应逐成员拒绝错误单位；若另建更窄 allowed_units，需要显式新定义差异，不静默改旧集合。

## 成员、源字段和真实期次形状

以下是已有原件范围的准确成员集合；`×` 仅在明示的组内表示笛卡尔积。month 区间为该月首末日，year_to_month 为当年 01-01 至该月末；quarter 为当季首末日，year_to_quarter 为年初至当季末。月度累计百分比有的源契约仍标 month，不能把所有名字含 cumulative 的字段统一改成 year_to_month。

| 指标/家族 | 已审成员和 source_field | 每成员单位 / period_kind | 合法省略及范围 |
|---|---|---|---|
| PMI 活动 | series=`manufacturing,production,new_orders,purchase_volume`，measure=`level`；字段分别 `manufacturing_pmi,production,new_orders,purchase_volume` | DI / month | 4 格；headline 不是任一分项替身 |
| PMI 库存 | series=`raw_materials,finished_goods`，measure=`level`；字段同 series | DI / month | 2 格；不是原始库存金额 |
| PMI 价格 | series=`purchase_prices,output_prices`，measure=`level`；字段同 series | DI / month | 2 格；不是价格同比。三项合计每期 8 格，7 期 56 格 |
| PPI | category=`headline,means_of_production,consumer_goods` × measure=`mom,yoy,cumulative_average_yoy`；字段前缀 `ppi,ppi_mp,ppi_cg` 分别接 `_mom,_yoy,_accu` | P / month，含累计同比列 | 2026-01 三类均只有 mom/yoy，共 6 格；其他已存月份 9 格，8 期 69 格。没有基数 100 的 level；不补造 January accu |
| 工业增加值 | measure=`current_month_real_yoy,mom_seasonally_adjusted,ytd_real_yoy`；分别 `industrial_va_yoy_real_pct,industrial_va_mom_sa_pct,industrial_va_ytd_yoy_real_pct` | 前两项 P / month；末项 P / year_to_month | 2026-02 只有后两项（累计 1–2 月 + 2 月季调环比）；Jan 原明确免报单月。2025-12、2026-02–07，共 20 格；不能造 Feb 单月同比 |
| 工业财务 | item=`revenue,cost,profit` × measure=`ytd_level,official_yoy`；`industrial_{item}_ytd_100m` / `industrial_{item}_ytd_yoy_pct` | ytd_level A、official_yoy P；都 year_to_month | 每期 6 格；1 月免报，1–2 月合并。同比为官方可比口径，不能拿两年展示金额机械相除替代 |
| 产成品库存 | measure=`nominal_end_level,official_yoy`；`finished_goods_inventory_100m,finished_goods_inventory_yoy_pct` | A/P / month | 月末余额及其官方同比，不是累计收入；原文万亿元×10000归亿元。7 期 14 格 |
| 库存周转 | measure=`days,official_yoy_change`；`finished_goods_turnover_days,finished_goods_turnover_days_yoy_change` | 两项均 D / year_to_month | 月末指标使用累计数据，同比变化也是天数；7 期 14 格。不是百分比变化。三项工业财务共 70 格 |
| 产能 | industry=`all_industry`，measure=`quarter_rate,yoy_change,ytd_rate`；`industrial_capacity_utilization_pct,industrial_capacity_utilization_yoy_change_pp,industrial_capacity_utilization_ytd_pct` | quarter_rate P / quarter；yoy_change PP / quarter；ytd_rate P / year_to_quarter | 2025-Q4/2026-Q1/Q2；9 准备身份但仅 8 独立原格。Q1 无累计列，当前 parser L1168 回用 quarter_rate；本研究不冻结其映射，不将其作为独立官方字段放行 |
| M1/M2 | aggregate=`m1,m2` × measure=`balance,yoy`；字段 `m1,m2` 与 `m1_yoy,m2_yoy` | balance A、yoy P；均 month | 2026-01–07，28 格；M0 未在本家族输出，不扩大成 M0 已接。M1 新口径和回溯同比按原公告保留，不能用旧 M1 序列静默拼接 |
| 社融总量 | measure=`stock_end,stock_yoy,ytd_increment`；`stock_end_trillion,stock_yoy_pct,ytd_increment_100m` | stock_end A、stock_yoy P / month；ytd_increment A / year_to_month | 字段后缀 trillion 是源字段名，规范数值已是亿元。31 期 93 格。现有模型最低 required 仅 stock_end+ytd_increment；stock_yoy 可存/可投影不等于其已为最低必需 |
| 社融组成 | 8 个 component 见下文 × 社融三个 measure/字段 | 同总量逐 measure 绑定 | 31 期 744 格；前 20 月两份存量/增量公告，后 11 月合并。一份只有存量的公告是合法部分文档，不能强迫单页给完所有 24 格；同一期双公告补齐后再判断完整 |
| 贷款结构 | 9 个 borrower/tenor 配对见下文，measure=`ytd_increment`、字段 `ytd_increment_100m` | A / year_to_month | 2024-01–2026-07 共 279 格；1月仍是YTD。49个减少为真实负值，不取绝对值；金融统计人民币贷款与社融实体经济人民币贷款范围不同 |
| 月度工具 | 8 个 tool 原名见下文 × measure=`injection,withdrawal,net_injection`；对应 `_100m` 字段 | A / month | 8 期192格；19负值、28真0；RRR行24个 `-` 不产生第九工具数值。源净额已有字面，相减只做核验；不能替代每日到期账 |
| OMO 金额 | measure=`injection`；`injection_100m` | A / business_day；start=end=操作日 | 131篇/131金额，10真零有明确正文和中标量0。原件样本没有 maturity 列；fixture parser 支持 maturity 不等于本范围已提供或认证此字段 |
| OMO 利率 | dimensions=`{}`；`operation_rate_pct` | P / business_day | 121篇有利率；另外10篇无此列，不补0也不制造前日值。`evidence_frequency` 已把声明 daily 转 event 有效直到变更；这是一条先前事件的选择语义，不是当日又有一条来源声明 |

社融 component 精确集合：`renminbi_loans`、`foreign_currency_loans_rmb`、`entrusted_loans`、`trust_loans`、`undiscounted_bank_acceptances`、`corporate_bonds`、`government_bonds`、`nonfinancial_enterprise_equity`。

贷款合法配对：`household × {total,short_term,long_term}`；`enterprise × {total,short_term,long_term,bill_financing}`；`(nonbank_financial,total)`；`(all_rmb_loans,total)`。不是任意 borrower×tenor 的全组合。

tool 精确原名：`常备借贷便利（SLF）`、`中期借贷便利（MLF）`、`抵押补充贷款（PSL）`、`其他结构性货币政策工具`、`7天期逆回购`、`其他期限逆回购`、`公开市场国债买卖`、`中央国库现金管理`。集合仅约束本批已审材料，不把未来官方新工具行任意映射到“其他”或删除。未来新增成员须显式处理。

上述源码实现位置：[PMI/PPI L626–702](../../src/pring_cycle/official_context.py#L626)、[工业 VA L758–872](../../src/pring_cycle/official_context.py#L758)、[工业财务 L979–1118](../../src/pring_cycle/official_context.py#L979)、[产能 L1121–1208](../../src/pring_cycle/official_context.py#L1121)、[OMO L1211–1325](../../src/pring_cycle/official_context.py#L1211)、[工具 L1423–1490](../../src/pring_cycle/official_context.py#L1423)、[社融 L1552–1669](../../src/pring_cycle/official_context.py#L1552)、[贷款 L1710–1761](../../src/pring_cycle/official_context.py#L1710)、[货币 L1764–1809](../../src/pring_cycle/official_context.py#L1764)。模型既有最低成员及 OMO 频率例外见 [metric_contracts.py L5–90](../../src/pring_cycle/metric_contracts.py#L5)。

## 最窄公开纵向切片与独立期望

建议先以 **PMI 三项/同一原件/8格** 做公开 RED→GREEN：注册新的已审查目录（测试内审查材料与真实来源认证分开），调用正式 `evidence-ingest` 的官方文档路径或 `ingest_official_context_document`，从 acquired receipt→claim 查询 PUBLIC/SYSTEM→`ModelInputSelector.select`→`build_context_projection` 检查三项值、身份、版本、选中 claim/CAS 引用。只 mock 外部 transport/测试时钟，不 mock EvidenceRepository 或 selector。当前首个预期 RED 是 registered_source_contract_not_implemented；通过后按同一测试骨架参数化其余家族，无需为16项重复16轮完整全套。

扩大首轮矩阵只需以下 **8份不同原件、10次家族导入、16项指标**。按旧准备形状会产出99个标量（8+9+3+10+3+4+27+9+24+2），这一数字是结构分母，不是本轮新入库或逐值重审。共享金融报告需分别调用 money/social_financing/loan_structure，不能仅解析一次就假设三家族都入库。下面16个数值锚点来自已有独立原表审计的明确期望；其余格完整期望可直接引用各审计表，不从 parser 输出反向生成。

| 原件代号 / 家族 | 统计期 | 最少独立断言（完整身份见上表） | 原件定位及已有审计 |
|---|---|---|---|
| R1 / PMI | 2026-07 | ACTIVITY new_orders=48.5 DI；INVENTORY finished_goods=48.6 DI；PRICES purchase_prices=53.2 DI | 原 HTML T1 R16 C4 L544、T2 R15 C7 L822、C5 L818；[PMI 审计 L121–128](p1-pmi-full-value-audit.md#L121) 另有全部8格 |
| R2 / PPI | 2026-07 | headline/yoy=3.5 P | T1 R2 C3 L351；[PPI 审计 L139–147](p1-ppi-full-value-audit.md#L139) 9格含总体mom=-0.7、累计1.8 |
| R3 / 工业 VA | 2026-07 | current_month_real_yoy=4.5 P | T1 R3 C3 L357；[VA 审计 L89–91](p1-industrial-va-full-value-audit.md#L89) 另 ytd=5.3、季调mom=0.11 |
| R4 / 工业财务 | 2026-07 | FINANCE revenue/ytd_level=809230.7 A；INVENTORY nominal_end_level=72700 A；TURNOVER days=21.3 D | T1 R3 C2 L365；L332“7.27万亿元”；T2 R4 C8 L567；[财务审计 L156–165](p1-industrial-finance-full-value-audit.md#L156)，另同比变化0.6天 |
| R5 / 产能 | 2026-Q2 | all_industry/quarter_rate=73.0 P | 总行L357；[产能审计 L47–49](p1-capacity-utilization-full-value-audit.md#L47)，另季度同比-1.0 PP、上半年率73.3 P；不要用Q1作无条件全3成员正例 |
| R6 / 货币 | 2026-07 | m1/balance=1154600 A（原115.46万亿元） | L359；[货币审计 L90–93](p1-money-full-value-audit.md#L90)，另M1同比4、M2余额3555100、同比7.7 |
| R6 / 社融 | 2026-07 | TOTAL stock_end=4632700 A（463.27万亿元）；COMPONENTS government_bonds/ytd_increment=77600 A（7.76万亿元） | 存量L354、增量L357；[社融审计 L1368–1383](p1-social-financing-full-value-audit.md#L1368)，含27格；委托贷款YTD=-810是真负值 |
| R6 / 贷款 | 2026-07 | enterprise/long_term/ytd_increment=53200 A（增加5.32万亿元） | P14/L366；[贷款审计 L756–776](p1-loan-structure-full-value-audit.md#L756) 含全部9配对；全人民币贷款103800与社融人民币贷款101700不同 |
| R7 / 工具 | 2026-07 | tool=7天期逆回购/net_injection=-2495 A | T16 R7 C5 L397；[工具审计 L199–210](p1-tool-liquidity-full-value-audit.md#L199) 24格，SLF投放0与RRR的`-`明确不同 |
| R8 / OMO | 2026-08-28 | AMOUNT injection=200 A；RATE {}=1.40 P | T16 R2 C4 L364、C2 L362；[OMO 审计 L178、L197](p1-omo-full-value-audit.md#L178)。同页隔夜3330不加入7天金额 |

还需同一批公开反例（不是重新审全历史）：

- **来源/定义负例**：错误 provider、source_codes、release family、维度成员、单位、每成员 period_kind 均拒绝；仅正确结构但 awaiting 状态仍不能成为模型采用。unknown 新版本、同版本不同定义集合、新旧版本隔离维持既有拒绝。不得借关闭 v3 guard 得绿。
- **合法缺列**：R9 PPI 2026-01 只6格，不能要求9；R10工业 VA 2026-02 只有累计6.3和季调环比0.83（T1 R3 C3 L350 / T2 R15 C2 L922），拒绝捏造单月同比。财务1月免报与2月累计同理。另一普通月份删除一个应有成员必须未完成，不能跟合法免报混同。
- **精确金额/单位**：R11 2026-02 M2 原349.22万亿元→3492200亿元，旧尾差已在v2准备修复；不能把原文数349.22直接标成亿元。周转同比变化0.6天不得标percent；产能-1.0是百分点；社融stock_end_trillion字段的规范单位是亿元。
- **拆页完整性**：社融旧20月一份存量公告先合法存储，selector所需stock_end+ytd_increment尚未齐；同月增量公告到达后才满足最低要求。保持各自发布时间、receipt和原件，不能把第二页字节/时间归给第一页。stock_yoy是否加入最低模型必需是明确的契约差异，本研究不自动扩大旧两成员规则。
- **真零、缺公告和事件沿用**：R12 2026-06-03 金额0有原文，利率列不存在。金额输出0、当日利率声明数0；事件利率沿用只能引用此前合格事件。`ModelInputSelector.select` 当前按scope.period匹配，不实现event跨期沿用；worker/evaluation的event鲜度例外不能被当作该selector已通过。若生产目标日scope要求同时补当日rate，下一条测试需揭示此差异，不能伪造每日利率行。
- **Q1产能**：R13 2026-Q1仅73.6%和-0.5个百分点两个独立源格；parser现生成的ytd=73.6仍未有冻结映射决策。先验证Q2三列纵向支持，不等于Q1也通过。不能自动删累计维度缩范围，也不能把同区间相等当第三原格。
- **双时钟/修订**：用原页有依据的PUBLIC事件和测试内真实导入/完成时钟分别验证前后cutoff；导入不能倒填历史SYSTEM。新raw若改变已报告数值且没有新公开时间，不继承旧PUBLIC。所有目标日查询还受中国目标日23:59:59.999999的PUBLIC上界，不只period_end<=target；见 [TargetBoundEvidenceRepository L565](../../src/pring_cycle/context_projection.py#L565)。

## 时间、认证和尚未冻结边界

这16项已有字面值和页面时间证据，不再笼统列为“没有官方样本”。页面可见发布时间可作为正式审查的输入；NBS分钟精度不应凭空提升为已证明的秒级首发，PBC可见秒数也不等于当前字节从未修订。旧页createDate迁站/生成时间不能代替页头，晚于页头不自动证明数值修订。不能因缺少每个历史首发字节归档就一律否定可靠原页时间，亦不能把取得时间反推为历史公开。

当前准备包的 acquisition_time/认证/采用仍是未完成状态。新正式document_import可建立新的真实SYSTEM回执；它不恢复旧系统在2026年3–8月何时取得。已经实施的其他家族真实导入或正式审查不自动覆盖本轮16项；本研究没有查生产库判断其最新导入状态，也没有重复提出个人使用批准要求。用途范围沿用已批准的本机个人分析边界，逐来源正式审查绑定既有适用条款即可，不把普通版权署名泛化成采购硬门。

仍需明确的最小规则只有实际影响本批消费的内容：Q1产能源格复用如何在新目录标识；本批尚缺的9项required members按上述真实期次如何定义；社融stock_yoy是否维持“可展示、非最低必需”；月度工具未来新成员如何显式处理。前三类源缺列事实已有证据，不能当成任意选择来填0；未冻结映射不能由研究替用户选择。M1口径、贷款/社融统计范围、金额单位、PP与P之别都是源事实，不是可自由替换的规则。

完成这批软件消费验收，只说明这些正式契约可进入新目录的证据链和模型消费者。真实来源正式review、独立回执/时间资格、120交易日点时重放、模型结论及真实切换仍按既定规格独立验收；注册61项与上述99格测试均不替代这些工作。

## 输入指纹与可复核原件

下列指纹为本轮实际只读输入；源码指纹约束本报告行号，后续实现改变源码时应保留此历史快照含义。审计报告的逐格结论是继承依据，本轮只重新核选定13份原件的字节/摘要，不谎称重核242原件或1812格。

| Input | Local path | bytes | SHA-256 |
|---|---|---:|---|
| input | [source_contract_review.py](../../src/pring_cycle/source_contract_review.py) | 6786 | `1da750b5baf7647ce73792f9d8c9870033c9bb77577c91c218baaf832758cbc4` |
| input | [metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 3698 | `9e3d3771f347c61da916e062c34ec5ed24ba55e96b58e832a544fc25f5d56367` |
| input | [official_context.py](../../src/pring_cycle/official_context.py) | 80147 | `0e6f57ea5770e3d35b2dbbd3255a8df9e1237296f2c6b97c1d6e2d54dbc20252` |
| input | [catalog.py](../../src/pring_cycle/catalog.py) | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| input | [source_families.py](../../src/pring_cycle/source_families.py) | 2487 | `420a241b90fc0ff63cafe5e9119f15a375e90617834cae2698e403ccbcaa5f6e` |
| input | [catalog_registry.py](../../src/pring_cycle/catalog_registry.py) | 4293 | `41ddb91573330a206e388b9b32665e511a286a22a6eb1eeff674803dabda0544` |
| input | [evidence.py](../../src/pring_cycle/evidence.py) | 52720 | `521be419643959c3f91dd68238f87975191cc04a448ec3874fc05ed6b0c1cf96` |
| input | [search_evidence.py](../../src/pring_cycle/search_evidence.py) | 13103 | `a4d7a64bb5269b36fd91843bebd28f3797fd74f691898fa45da099f789de3af5` |
| input | [context_projection.py](../../src/pring_cycle/context_projection.py) | 79269 | `82695481771001ab7680908055c58810d2a062a2120a67b5cf81089075f7f7fc` |
| input | [worker.py](../../src/pring_cycle/worker.py) | 57797 | `61c6a25ee6ee5cd34a09f879c1d82a9db41bfef866f8e20bd5331d1c3b00a24f` |
| input | [model_evaluation.py](../../src/pring_cycle/model_evaluation.py) | 37782 | `62a7ae6aea408b346f093d34d83be9255084e7319c8754e37ae68c8b130d9ded` |
| input | [a18-certification-next-boundary.md](a18-certification-next-boundary.md) | 27280 | `86e15e4c5ee601d2c06783a951ae588d559545510ed328b24c8e095125d26b35` |
| input | [p1-official-preparation-v2.md](p1-official-preparation-v2.md) | 2841 | `6623bd19acee525d3a2a18eec7749e908bf28e17b52e6f6012c92f4a7291b688` |
| input | [preparation.json](evidence-13-preparation-v2/preparation.json) | 3189072 | `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034` |
| input | [p1-pmi-full-value-audit.md](p1-pmi-full-value-audit.md) | 21325 | `02901b12706b0101be06a4c5b74873cd46322fbefb9b6507dbbe7c8bfe3de7ef` |
| input | [p1-ppi-full-value-audit.md](p1-ppi-full-value-audit.md) | 21333 | `b8228fb7eee93ca00363419b909bc3c23b0346117e22a3699cdaf374a88be8d1` |
| input | [p1-industrial-va-full-value-audit.md](p1-industrial-va-full-value-audit.md) | 16362 | `ef2e599944f049fab8a7bcce34aede93ac29dd2c33c5cd0a2541faf4d0984406` |
| input | [p1-industrial-finance-full-value-audit.md](p1-industrial-finance-full-value-audit.md) | 24950 | `f14f4f98f8050386a7f9f9f0f3e4d84c75b56c6dffa743d8b47c6e2ed1d3ab7d` |
| input | [p1-capacity-utilization-full-value-audit.md](p1-capacity-utilization-full-value-audit.md) | 13203 | `5cce581124ccb722782eb94e6aef5a48bd36faa78d4396ec41568f49feeeb9ed` |
| input | [p1-money-full-value-audit.md](p1-money-full-value-audit.md) | 16643 | `44ea8fbc4d0c649343068b987921ea47463f5b8e5067fd39aec09f314cec5eda` |
| input | [p1-social-financing-full-value-audit.md](p1-social-financing-full-value-audit.md) | 147300 | `a649d2b86df819fa2682c46997a0cec0fd4021c8d702225ddc6ff3a920cb7437` |
| input | [p1-loan-structure-full-value-audit.md](p1-loan-structure-full-value-audit.md) | 66620 | `2d4d1b4a3e1966cbfeccb0f6892ed31937f941edc7a75d09609424a2e767dcae` |
| input | [p1-tool-liquidity-full-value-audit.md](p1-tool-liquidity-full-value-audit.md) | 25421 | `13a84f6fcd6ee23827c9d4700d3b4af999a5a2ec40455729bdbf432c44b08fbb` |
| input | [p1-omo-full-value-audit.md](p1-omo-full-value-audit.md) | 81481 | `d1af0e4bd294fedede1aaa32be505c88a013965c36be2d4d297f5f8b616c617e` |

| Raw / saved official URL (not requested) | Local path | bytes | SHA-256 |
|---|---|---:|---|
| R1 2026-07 [nbs_pmi](https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html) | [raw](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6) | 398889 | `fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6` |
| R2 2026-07 [nbs_ppi](https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965007.html) | [raw](evidence-13/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09) | 251797 | `b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09` |
| R3 2026-07 [nbs_industrial_value_added](https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html) | [raw](evidence-13/d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609) | 393331 | `d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609` |
| R4 2026-07 [nbs_industrial_finance](https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html) | [raw](evidence-13/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986) | 494713 | `28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986` |
| R5 2026-Q2 [nbs_capacity_utilization](https://www.stats.gov.cn/sj/zxfb/202607/t20260715_1964130.html) | [raw](evidence-13/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8) | 168665 | `8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8` |
| R6 2026-07 [pbc_money](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html) | [raw](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef) | 44692 | `933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef` |
| R7 2026-07 [pbc_tool_liquidity_monthly](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026080416515912098/index.html) | [raw](evidence-13/10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0) | 44678 | `10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0` |
| R8 2026-08-28 [pbc_omo_notice](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html) | [raw](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a) | 31000 | `ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a` |
| R9 2026-01 [nbs_ppi](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962587.html) | [raw](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/e7/e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943) | 218312 | `e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943` |
| R10 2026-02 [nbs_industrial_value_added](https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html) | [raw](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/21/2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e) | 282785 | `2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e` |
| R11 2026-02 [pbc_money](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026031317020260950/index.html) | [raw](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/37/377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc) | 44639 | `377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc` |
| R12 2026-06-03 [pbc_omo_notice](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026060308521286488/index.html) | [raw](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/63/632b1709e4c27aac9b2fd9135394f11efb530321c8a1960577f8a0a562ec65b0) | 29677 | `632b1709e4c27aac9b2fd9135394f11efb530321c8a1960577f8a0a562ec65b0` |
| R13 2026-Q1 [nbs_capacity_utilization](https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html) | [raw](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/0c/0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a) | 128195 | `0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a` |

唯一新增交付路径：`.scratch/pring-data-acquisition-repair/remaining-official-consumption-contracts.md`。最终本文件bytes/SHA和本地链接检查结果由交付消息给出，避免自引用。网络请求0、应用/测试执行0、数据库/认证/模型写入0。

Input fingerprint observation UTC: `2026-09-07T22:46:35.426066+00:00`. Selected raw files: 13; exact bytes: 2531373.
