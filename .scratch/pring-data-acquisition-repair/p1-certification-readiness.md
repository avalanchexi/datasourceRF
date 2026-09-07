# 票 13：27 项 P1 的候选认证准备清单

研究日期：2026-09-07，Asia/Shanghai。固定对照目标日为 **2026-08-28**，已讨论重放区间为 **2026-03-09—2026-08-28**；本报告不把该目标称为研究日最新交易日。只读复用官方原件、旧研究和当前源码，没有联网、账户调用、应用导入、数据库查询/写入、来源认证或模型变更。

**可以先推进 18 项常规官方指标的候选认证材料整理；LPR、DR007、Shibor 另有使用边界核验，其中后两项历史 PUBLIC 未知；RRR 和仓单仍有实质外部证据缺件。4 项纯派生可准备公式及血缘材料，能否用于目标截点取决于父输入。** “可以准备”表示不必等其他家族补件才能整理材料，不表示已通过认证或全部历史完整。

范围依 [票 13](issues/13-remaining-p1-evidence.md)、[冻结规格](spec.md)、[官方抽样 ADR 0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) 和 [source_certification.py](../../src/pring_cycle/source_certification.py)：**20 项官方直取 + 3 项专需结构化交付锚定 + 4 项纯派生 = 27 项 P1**。部分官方直取也可由 TuShare 交付，属于渠道重叠，不能重复计数。`CN_GDP` 是信用脉冲的 P2 分母，单列依赖，不增加第 28 项 P1。

## 本轮核查的证据及统计边界

重新读取 [270 件历史清单](evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec) 指定的只读 CAS 文件，逐件 SHA256 匹配，**270 件、23,101,004 字节、0 缺件、0 摘要不符**。通过 Windows 标准库访问 `//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/`，未启动 WSL 命令或应用。历史 [288 次、13 个解析家族的检查](evidence-13/history-verification.json) 是先前执行结果，本轮只读其字段和期次，不声称重新运行当前应用解析器 288 次。

另复核 `evidence-13/`、`evidence-13-dr007-followup/`、四批 `evidence-13-rrr-*/` 中以完整 SHA 命名的 **45 个包内文件、9,044,451 字节**，全部匹配文件名。这是按目录计的文件数，含历史清单、失败空体及辅助入口，不是“45 份有效官方数值正文”；也与 270 件 CAS 有重叠，不能相加为独立样本。原件取得过程见 [原研究回执](evidence-13/receipts.json)、[旧件导入记录](evidence-13/imports.json)、[DR007 回执](evidence-13-dr007-followup/receipts.json) 与各 RRR 包回执。

数值和时间分别统计：

- 在 **23 项非纯派生 P1** 中，**21 项**已有固定对照期的代表性官方数值锚点；RRR 只有历史事件锚点且现行状态未知，仓单只有 5/8 品种锚点。这不是 21/23 个已认证家族，也不是逐历史值对账率。
- 19 项非 RRR 官方直取指标有已存历史发布页及其可见发布时间材料；这只支持相应页面/版本的时间核对，**不等于 19 项在每个重放截点均已 PUBLIC 合格**。DR007、Shibor、仓单没有本次目标日实际首次公开证据；RRR 有旧回顾时间及原发布会日期，但事件全集/最近前置状态未证。
- 4 项纯派生不要求独立官方输出原件；其中两项 PMI 差值与信用脉冲已有官方输入和独立算式，DR007 利差的数值算式成立但 PUBLIC 继承 DR007 缺件。不能把 4 次算式相符计为 4 份来源认证。
- 旧 [PUBLIC/SYSTEM 矩阵](evidence-13/legacy-read-matrix.json) 仍只是 `metric-catalog-v0003` 快照：旧 PUBLIC 含不可信时间，旧目标截点 SYSTEM 为 0 不能倒填。**本轮新增候选矩阵、新来源认证、模型采用、重放结果均为 0。**

以下时间除注明外按项目北京时间解释；NBS 页面只到分钟时保留分钟精度。页头能证明所存发布页标示的发布时间，不能排除后改页面或让修订数值继承旧时间。SYSTEM 必须使用将来正式取得并验证完成的真实时钟；本轮 hash 重验、复制或研究文件生成时刻均不能替代它。[双点时 ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)

## 27 行逐指标准备矩阵

状态 **A**＝可先整理官方候选认证材料（18）；**B**＝数值材料可整理，时间或适用使用条款仍待核（3）；**C**＝外部事件/品种原件仍缺（2）；**D**＝派生材料准备，依赖父项（4）。所有状态均为研究分流，不是数据库认证标签。每行“原件”链接至准确字节文件；其拥有事实的官方 URL 见后面的来源索引。

| 序号 / 指标 | 来源家族及官方原件 | 字段、单位、期次与数值锚点 | 时间证据 / 实际状态 | 尚缺认证材料；最小下一动作 |
|---|---|---|---|---|
| 01 `CN_DR007` | CFETS 日报；[DR JSON](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d)、[字段表头](evidence-13-dr007-followup/b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96)，S01 | 唯一 `DR007`、`wghtdAvgRepoRate=1.3859%`，响应 `lastDate=2026-08-28`；TuShare `DR007.IB/weight` 对照 1/1 相符 | **B**；数值锚点已补，不再写“缺同期官方值”。响应生成 09-07、参数 `2200` 和旧 11:00 均不是历史首发；PUBLIC 未知 | 将官方字段/期次与已有交付原件挂入认证草案；核 CFETS/交付渠道用途范围，明确 PUBLIC 未知。需要历史 PUBLIC 才补关联发布/修订记录，不能用收盘 `1.3806%`、R007、FDR007 替代 |
| 02 `CN_OMO_7D_RATE` | PBC `pbc_omo_notice`；[原件](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a)，S02 | 7 天操作 `operation_rate_pct=1.4%`，08-28；131 公告中 121 份提取利率，政策有效期不能按无操作日制造事件 | **A**；08-28 09:20:30；历史公告期次 02-24—08-28。10 份只有金额，不等于 10 个政策利率为零 | 以已有公告整理有效期起点、变更和沿用依据；逐日可见性核日历/发布时间。附不含利率的零操作页反例，不从缺列推测降息 |
| 03 `CN_OMO_7D_AMOUNT` | PBC `pbc_omo_notice`；[原件](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a)，S02 | `injection=200` 亿元，08-28；同页隔夜 3330 亿元不并入 7 天。131 份日操作材料 | **A**；08-28 09:20:30；原件可以明确报告 0 操作，0 不等于缺值 | 先认证 7 天投放流量；若输出日净投放，另附到期台账或已认证交易日历/顺延规则及版本，不能直接套月净额 |
| 04 `CN_DR007_POLICY_SPREAD` | 派生；01 的 [DR 原件](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d) + 02 的 [OMO 原件](evidence-13/ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a) | `dr007-policy-spread-v0001`；(1.3859−1.4)×100＝**−1.41 bp**，08-28 | **D**；输入/输出定义认证门已修；历史 PUBLIC 不能因 OMO 时间已知而放行 DR007 | 准备父项版本与同日/政策有效期血缘；将错收盘得 −1.94 bp、缺父项和未知 PUBLIC 作为验收边界；父项未合格时保留不可用 |
| 05 `CN_SHIBOR_ON_1W_3M` | CFETS Shibor；[日值 JSON](evidence-13/365f18b1a160570e6d0762040bf6af670379be2946bec553593d2cbae3881f62)、[准则](evidence-13/043ae07820bc91ae91b00fd4468cc4f7938eb911ae2d1f75efc5237407c13ae9)，S03 | ON 1.3390、1W 1.3870、3M 1.4300，年利率 %；08-28，Act/360、T+0、4 位小数；旧交付 3/3 相符 | **B**；通常 11:00 日程有原文；JSON 观测日与响应 `head.ts` 不证明当日实际首发/更正，PUBLIC 未知 | 准备 3 期限完整性及 TuShare `on/1w/3m` 映射；核渠道用途记录与真实发布边界。不能借通常日程认证全部 167 日历史 |
| 06 `CN_LPR_1Y_5Y` | Chinamoney LPR；[原件](evidence-13/5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5)，S04 | `1y=3.0%`、`5y_plus=3.5%`；2026-08 报价在下次报价前有效；9 期 2025-12—2026-08 | **B**；08-20 09:00:00 可见，不因 `period_end=08-31` 延至月底。与 DR/Shibor 不同：本项已有所选发布页时间 | 可先整理 9 期真实发布/报价有效期及两成员；把 CFETS 原文与既有当地个人使用/来源合同证据对应核验，不能仅沿用旧认证包的一般使用标签 |
| 07 `CN_RRR_EVENT` | PBC 回顾 [原件](evidence-13/7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5)；CSRC 原实录 [原件](evidence-13-rrr-original-notices/d9dd4873a3005ca20a2985a36055f8b3a14f6d0b67977186351857cc4a011846)，S05 | 2025-05-15：排除已执行 5% 机构的 −0.5 pp；汽车金融/金融租赁合并可辨范围 −5 pp。CSRC 明示两类各从 5% 阶段性降至 0%，不能全市场相加 | **C**；PBC 回顾 2025-11-11 17:00:09；原实录 05-07 仅日期，可按既定规则准备 05-08 00:00 候选边界。现行状态/完整事件序列未知 | 多 scope 解析已修，但必须补 2025-10-01—2026-03-08 最近前置及 03-09—08-28 事件覆盖、阶段终止/延续。CSRC 域不同于 `pbc_rrr_notice` 的 PBC 域，保留真实来源另行适配/认证，不伪换 URL |
| 08 `CN_TOOL_LIQUIDITY_MONTHLY` | PBC `pbc_tool_liquidity_monthly`；[原件](evidence-13/10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0)，S06 | 工具 × 投放/回笼/净投放，亿元；07 月 7 天逆回购 47395−49890＝−2495，MLF 5000−4000＝1000；8 期 2025-12—2026-07 | **A**；08-04 17:00:00；所选页有 8 工具 × 3 measure，月值不展开成日操作 | 整理全部工具成员、报告值 0 与未报告的区别、修订 vintage；与 OMO 日账分开，先用原件手算净流量完成认证材料 |
| 09 `CN_FUTURES_WARRANTS` | SHFE/INE 仓单 [原件](evidence-13/aa7493a24425f6f95f9743bc8e53725deb0e2cbba10857d97443758eedef4e39)、TuShare [字段/上限](evidence-13/1ced6f1c14337be4d14684ab557c495381bc0594d652b6e67580ce746295284b)，S07 | 08-28；CU/RB/RU/SP 吨，SC 桶；5/8 品种，134 次同名明细数值一致，并非全行覆盖。PP/CF/TA 缺官方原表/适用单位 | **C**；业务日/期号不等于发布日期，PUBLIC 未知；1000 行阈值已修，仓库等现身份未证涵盖年度/等级/折算维度 | 按真实 PP、CF、TA 原表补品种/单位/维度；核 CU 未匹配、仓库/厂库/保税及总计边界、原请求关联。官方片段支持才加维度，不合计吨/桶/张/手；不称网站旧行情失败为仓单端点实测 |
| 10 `CN_PMI_ACTIVITY` | NBS `nbs_pmi`；[原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，S08 | 07 月制造业/生产/新订单/采购 49.2/49.9/48.5/49.4；官方表写 %，模型为扩散指数点；7 期 01—07 月 | **A**；07-31 09:30；4 成员需同月，后页历史表不可回填首发 | 以 7 份原发布整理成员、季调/扩散口径和截止选择；有 24 月旧 SYSTEM 值不代表 24 月 PUBLIC 原发布已证 |
| 11 `CN_PMI_INVENTORY` | NBS `nbs_pmi`；[原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，S08 | 07 月原材料 48.3、产成品 48.6，扩散指数点；7 期 | **A**；07-31 09:30；不是库存实物量或名义金额 | 准备两成员与活动同月核对，认证说明保留扩散口径；报告解释另验，不把该值替代 NBS 产成品存货 |
| 12 `CN_PMI_PRICES` | NBS `nbs_pmi`；[原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，S08 | 07 月购进价 53.2、出厂价 47.8，扩散指数点；7 期 | **A**；07-31 09:30；与 PPI 涨幅百分比不同 | 准备两成员与月期次/单位核对；拒绝把购进与出厂互换或把 53.2 当同比涨幅 |
| 13 `CN_ORDER_INVENTORY_SPREAD` | 派生；NBS [输入原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，S08 | `pmi-order-inventory-spread-v0001`；07 月 48.5−48.6＝**−0.1 指数点** | **D**；同一发布页两输入可关联；当前模型输入/输出认证门已修 | 准备同月两成员、公式及原件血缘；缺成员/错月不派生，修订形成新 vintage。数值复核与报告解释分别验收 |
| 14 `CN_PRODUCTION_ORDER_SPREAD` | 派生；NBS [输入原件](evidence-13/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6)，S08 | `pmi-production-order-spread-v0001`；07 月 49.9−48.5＝**1.4 指数点** | **D**；同一发布时间及期次；官方没有独立发布本项目这个派生指标 | 准备生产/订单的输入版本与公式认证；不得用不同月两个“最新值”相减，不能把派生结果冒作官方原值 |
| 15 `CN_CPI_HEADLINE` | NBS `nbs_core_cpi`；[原件](evidence-13/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49)，S09 | 07 月 MoM −0.1、YoY 0.5、累计平均 YoY 0.9，%；8 期 2025-12—2026-07 | **A**；08-09 09:30。旧 PUBLIC 仅到 06 月，原件存在与候选采用不同；01 月原发布只列 MoM/YoY | 先按原页日期建立新声明，保留旧错误版本；按实际列数列应有成员，01 月不静默补累计字段。核 2026 基期说明及官方可比口径 |
| 16 `CN_CORE_CPI` | NBS `nbs_core_cpi`；[原件](evidence-13/a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49)，S09 | 扣食品能源；07 月 MoM 0.3、YoY 0.9、累计平均 YoY 1.1，%；8 期 | **A**；08-09 09:30；先前 23 点的少 1 点定位于 2026-01 未单列累计平均列，不能仅凭 8×3 宣告采集丢值 | 认证草案逐期说明报告字段/非报告字段及 supersedes；需要累计成员时按明确派生规则另处理，不擅自制造官方值 |
| 17 `CN_PPI` | NBS `nbs_ppi`；[原件](evidence-13/b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09)，S10 | 出厂价总/生产资料/生活资料 × MoM/YoY/累计平均，%；07 月总项 −0.7/3.5/1.8；8 期 | **A**；08-09 09:30；01 月原表每类别仅 MoM/YoY，69≠72 的 3 字段不能直接认定丢行 | 附逐期列数和 2026 年启用 2025 基期的原页说明，先对原字段认证；价格调整库存必须与库存同月，不能用 PPI 购进指数替代出厂指数 |
| 18 `CN_INDUSTRIAL_VA` | NBS `nbs_industrial_value_added`；[原件](evidence-13/d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609)，S11 | 07 月当月实际 YoY 4.5、累计实际 YoY 5.3、季调 MoM 0.11，%；7 期，无单列 01 月 | **A**；08-17 **15:00**。01—02 月合并报告仅累计实际 YoY 6.3、02 月季调 MoM 0.83，不存在已证的独立 02 月实际 YoY | 整理合并期而非凑 8×3 字段；缺成员与不适用分别记录；原页 15:00 不换成日程常见 10:00，季调历史修订另留版本 |
| 19 `CN_INDUSTRIAL_FINANCE` | NBS `nbs_industrial_finance`；[原件](evidence-13/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986)，S12 | 01—07 月累计收入/成本/利润 809230.7/687861.5/45820.6 亿元；官方可比同比 6.5/5.9/17.6%；7 期 | **A**；08-27 09:30；6 成员，金额和官方可比同比不同身份 | 核同年累计及规上企业可比范围；不以不同年度金额直接算官方同比；修订金额和同比都保留版本，先从所选原件准备六成员认证 |
| 20 `CN_FINISHED_GOODS_INVENTORY` | NBS `nbs_industrial_finance`；[原件](evidence-13/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986)，S12 | 07 月末存货 **7.27 万亿元＝72700 亿元**；官方同比 10.8%；名义月末金额，7 期 | **A**；08-27 09:30；不等于累计收入、PMI 扩散指数或交易所仓单 | 准备金额 ×10000 换算/官方同比/期次认证；实际库存近似只是派生解释，不能代官方原值；现代码有错月拒绝分支，本轮不代运行其在途验收 |
| 21 `CN_INVENTORY_TURNOVER` | NBS `nbs_industrial_finance`；[原件](evidence-13/28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986)，S12 | 01—07 月产成品存货周转 **21.3 天**、同比增加 **0.6 天**；`days/official_yoy_change`，7 期 | **A**；08-27 09:30；`year_to_month`，与应收账款平均回收期不同 | 同原件整理统计期、天/同比天差及成本使用口径；不得把 0.6 当百分比，不用应收账款周转替代 |
| 22 `CN_CAPACITY_UTILIZATION` | NBS `nbs_capacity_utilization`；[原件](evidence-13/8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8)，S13 | 2026-Q2 当季 73.0%、同比 −1.0 pp、上半年累计 73.3%；3 期 2025-Q4—2026-Q2 | **A**；07-15 10:00；季度与累计成员不同 | 认证 3 成员和季度有效发布时间；重放沿用已公布季度，不插值/不制造 120 条季度记录 |
| 23 `CN_M1_M2` | PBC `pbc_money`；[原件](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef)，S14 | 07 月末 M1/M2 为 115.46/355.51 万亿元＝1154600/3555100 亿元；同比 4.0/7.7%；7 期 | **A**；08-14 16:30:05；余额/同比 4 成员，2025 年 M1 新口径及可比回溯需版本化 | 整理新口径脚注、余额换算与同比原文；旧 SYSTEM 多的 M0 不扩大本 P1 合同，后页回溯不直接变成旧首发 |
| 24 `CN_SF_TOTAL` | PBC `pbc_social_financing`；[原件](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef)，S14 | 07 月存量 4632700 亿元、存量 YoY 7.4%、累计增量 222500 亿元；51 篇 / 31 个月，2024-01—2026-07 | **A**；08-14 16:30:05；存量与增量可能分别公告，51 不是 51 个期次 | 按实际公告日期/版本绑定三 measure；当月流量需同年相邻 YTD 差分，不能用存量差；为信用脉冲挂接最小隐藏预热 |
| 25 `CN_SF_COMPONENTS` | PBC `pbc_social_financing`；[原件](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef)，S14 | 8 分项 × 存量/存量 YoY/累计增量，亿元/%；如政府债 1026800 / 14.1 / 77600；31 个月 | **A**；08-14 16:30:05；24 成员不等于全社融所有细项 | 按真实分项名和统计调整脚注整理；政府债/贷款核销等范围不可因合计差推补 0；对存量/累计分别建立时间与维度认证 |
| 26 `CN_LOAN_STRUCTURE` | PBC `pbc_loan_structure`；[原件](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef)，S14 | 借款人 × 期限 × YTD 增加，亿元；07 月企业中长期 53200、住户合计 −8271；9 成员，31 个月 | **A**；08-14 16:30:05；负增量是真值；当月流量派生不是贷款余额差 | 整理成员/负值/累计单位；月变动沿用 `loan-ytd-monthly-change-v0002`，1 月用自身 YTD，跨年/缺前月不得相减；来源和派生分别认证 |
| 27 `CN_CREDIT_IMPULSE` | 派生；SF [原件](evidence-13/933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef)、GDP [原件](evidence-13/60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915)，S14/S15；[逐输入算式](evidence-13/research-checks.json) | `credit-impulse-ytd-flow-v0002`；24 连续月流量、8 连续季现价 GDP；100×(338600/1437047−373800/1392784)＝**−3.276124655980012 pp** | **D**；SF/GDP 各版本公开后才可用，任一 PUBLIC 未知则结果未知；当前输入/输出定义认证与未知传播已修 | 准备窗口连续性、跨年/季度 YTD 差分、单位及修订血缘；GDP 是 P2 必要分母，单独认证但不扩为 28 P1。旧算式相符不代新候选计算/报告验收 |

## 三类容易误判的字段缺口

本轮进一步把“8 期但不到 8×成员数”的现象追到具体原件，而非仅引用旧库点数：

1. **2026-01 CPI/核心 CPI**原表只列环比和同比，旧解析各 2 个成员；每家族 8 期合计 23，而不是必然应有 24。不存在该原表的累计平均列时，不能静默补成官方数值。若业务需要 1 月累计同比，可以另行明确等同关系/派生记录，但不能把它写成原页报告字段。[官方发布](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962588.html)、[本地原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/f6/f65b52d3c2418f40a43e0991d041e0295e56941ca7d9bc9bad76e0d5d0cab964)
2. **2026-01 PPI**每类别仅环比、同比，3 类共 6；其他 7 期每期 9，共 69。原文还说明 2026 年启用 2025 年新基期及调查目录/企业/权数调整。原表完整性与跨基期可比口径分别核验，不把 `69<72` 单独当采集丢值证明。[官方发布](https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962587.html)、[本地原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/e7/e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943)
3. **2026-01—02 工业增加值**原文报告累计实际同比 6.3%，另有 02 月季调环比 0.83%；不是独立 02 月实际同比。先前 7 份、20 标量中少于 21 的字段须按合并期解释。[官方发布](https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html)、[本地原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/21/2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e)

另有 **10 份 OMO 只有金额**：06-03、06-04，以及 08-11、12、13、14、17、18、19、20。以 08-11 为例，原文明确 7 天操作量为零，表头仅“期限/投标量/中标量”，没有利率列；因此金额 0 可以是真实值，利率缺列不能变成政策利率 0 或新的利率事件。本轮逐例详读的是 08-11，10 份列表来自已有逐件解析记录，未将其他 9 份的正文语义自动概括为完全相同。[官方公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026081108552245312/index.html)、[本地原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/3a/3a06a019cbde41e74f2a90ff532d688d49b01242c69a80f8bb5afb9480a87c2a)

## 官方来源索引、特殊时间与用途边界

索引与上表精确原件一一对应，官方 URL 来自已保存回执/历史清单，本轮没有重新请求。

| 编号 | 拥有事实的官方来源 | 能证明与不能证明 |
|---|---|---|
| S01 | [CFETS 质押回购日报 JSON](https://www.chinamoney.com.cn/ags/ms/cm-u-dlrp/PrDlyBltn?lang=en&indexType=markInterBankVOList&searchDate=2026-08-28&publishedTime=2200)、[日报字段页面](https://www.chinamoney.com.cn/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html) | 加权利率%、唯一 DR007 与响应统计日；不以 URL 参数或生成时钟证明历史首发。[PBC 语义 PDF 原件](evidence-13/60ad3e29e905a9f405e70733cb1ddeffa41fdcc6b9dcbe962e462b2422a2d455)补存款类/利率债质押定义，图不能给目标日精确值 |
| S02 | [PBC 08-28 公开市场业务公告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html) | 7 天利率及当日投放；政策利率有效期、日净投放到期量另需材料，不混隔夜 |
| S03 | [CFETS Shibor 准则](https://www.chinamoney.com.cn/chinese/bkshibor/)、[08-28 历史 JSON](https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/ShiborHis?lang=cn&startDate=2026-08-28&endDate=2026-08-28) | 年利率报价、期限及常规发布日程；本次 JSON 无历史首发/更正版本时间 |
| S04 | [CFETS 08 月 LPR 公告](https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html) | 8 月报价和当月 20 日原页时间；不以月底观测字段阻止原本已公布报价 |
| S05 | [PBC 前三季度大事记](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html)、[CSRC 联合发布会原实录](https://www.csrc.gov.cn/csrc/c106311/c7555758/content.shtml)、[吉林官方转载](https://jr.jl.gov.cn/jrzx/zyjrxxzz/gj/202505/t20250512_3454788.html) | 实录 2025-05-07 日期、特定机构 5%→0% 和阶段性；[转载原件](evidence-13-rrr-original-notices/f1d24e69b5ef8bb4526534fa5cd32f0728a8ff0903b3ff5381d1acb03c06bf83)与回顾载 05-15 生效。实录后期 `PubDate`/生成 meta 及搜索时刻不作首次发布；阶段期限、后来事件不明 |
| S06 | [PBC 2026-07 工具流动性投放情况](https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026080416515912098/index.html) | 月度工具表、亿元；不是每日操作台账 |
| S07 | [SHFE 08-28 全品种仓单](https://www.shfe.com.cn/data/tradedata/future/stockdata/dailystock_20260828/ZH/all.html)、[TuShare 仓单文档](https://tushare.pro/document/2?doc_id=140) | 前者拥有官方数量与单位，后者只拥有交付 schema/1000 上限，不因此成为交易所官方数值源。统计日期不是实际发布日期 |
| S08 | [NBS 2026-07 PMI](https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html) | 三 PMI 家族同月表及扩散口径；差值是项目公式 |
| S09 | [NBS 2026-07 CPI](https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html) | headline/扣食品能源及各 measure；原页日期支持新时间声明准备，旧库选中版本另验 |
| S10 | [NBS 2026-07 PPI](https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965007.html) | 出厂价格涨幅，与工业生产者购进价格分开 |
| S11 | [NBS 2026-07 工业增加值](https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html) | 实际可比增长及季调环比；该页真实标示 15:00 |
| S12 | [NBS 2026-07 工业企业利润](https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html) | 三工业财务/库存家族的金额、官方同比和天数；不同统计范围金额不能重算“官方可比同比” |
| S13 | [NBS 2026-Q2 产能利用率](https://www.stats.gov.cn/sj/zxfb/202607/t20260715_1964130.html) | 当季、同比点差、累计；无需日频插值 |
| S14 | [PBC 2026-07 金融统计](https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html) | 货币、社融和贷款各成员；同页复用不重复计数。历史分文与统计口径脚注需随各期保留 |
| S15 | [NBS 2026-Q2 GDP 初步核算](https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html) | 上半年现价 GDP 695704 亿元、原页 07-16 09:30；4.3% 是当季实际同比，不能做名义金额分母 |

**CFETS 用途待核是具体条款对应工作，不是凭版权署名推断禁止。** 已存 [数据服务说明原件](evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50) 明确市场数据包括历史、基准、公告等，涉及复制/存储/使用/加工的书面许可要求；同时列明最终用户可从公共信息发布渠道或正式授权信息服务机构取得。两段应一起核对实际渠道和用途，不能只取其中一段概括“公开 GET 即全面许可”或“个人必然无权使用”。[CFETS 官方说明](https://www.chinamoney.com.cn/chinese/dssjfwgl/)

已有 [ADR 0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) 已接受 TuShare 本地个人、非商业、不可转让、未经许可不再分发的边界，不要求用户重复确认同一授权。本轮未读账户/私有许可材料，因此适用到 DR007/Shibor/LPR 的授权证据是否已存在仍为未知；下一动作是复用已有来源合同/授权记录、对应到该家族，而不是自动采购或推断用户缺许可。常规 NBS/PBC 官方材料也应在认证包写明来源、署名及使用范围，不以本报告代审批。

RRR 追加的 [六次目录/报告研究](rrr-followup.md)、[四篇公告](rrr-announcements-followup.md)、[两篇政策发布材料](rrr-policy-status-followup.md) 和 [原公告增量](rrr-original-notices-followup.md) 已分别留下原件：四篇公告正文均非 RRR；两篇会议材料未给明确降准事件或未调整声明；Q2 报告中超额准备金率不是法定准备金率。**“已读材料未见”不等于事件全集为空**。这项外补仍是范围完整性与阶段效力证据，不是重复下载已知旧文。

## GDP 分母与当前代码能证明到哪

`CN_GDP` 单列为 P2 输入：11 份、2023-Q4—2026-Q2，现价累计金额及各自原页发布时间已保存。信用脉冲需最终 8 个连续季度现价量；除第一季度直接用 YTD 外，同年累计作差，故保留更早季度边界属于必要预热。现价累计不换成实际同比，分母认证与 P1 计数分开。31 个月社融与 11 季 GDP 是既有原件覆盖，不自动等于所有 120 个截点均满足 24 月/8 季预热和版本可见性。[历史解析与原件定位](evidence-13/history-verification.json)、[信用脉冲输入和算式](evidence-13/research-checks.json)

只读代码核查得到以下有限状态：

- [tushare_context.py](../../src/pring_cycle/tushare_context.py) 的仓单阈值为 1000，满限分日、单日满限拒绝；已有 [实施及验证记录](implementation-13.md)。现保存身份仍为 symbol/warehouse/exchange/measure，年度、等级、折算等是否需加入必须由真实目标原表决定。阈值修复不等于 8 品种材料完整。
- [official_context.py](../../src/pring_cycle/official_context.py) 已按真实旧原件返回两个 RRR scope；未支持的范围尾句明确拒绝。[公开原件修复后结果](rrr-public-boundary-after.json) 和 [批次收据](verification-13-rrr-scope/final.json) 支持该实现进展。外层已拒绝错年份请求，不能把旧局部正则试算称作当前公开入口错年漏洞。[source_families.py](../../src/pring_cycle/source_families.py) 仍将 `pbc_rrr_notice` 绑定 `www.pbc.gov.cn`。
- [context_projection.py](../../src/pring_cycle/context_projection.py) 已检查派生输入/输出的当前模型定义认证；信用脉冲及净投放未知 PUBLIC 不向下游生成已知 PUBLIC，禁用公式不强索依赖。已有 [派生批次收据](verification-13-derived/final.json)。本轮未运行候选上下文或重做应用测试。
- 当前工作树的 `_real_inventory_proxy` 已可见名义库存/PPI `period_mismatch` 分支；这一文件可能处于父代理在途实现中，本报告只证明阅读时该分支存在，不代替该批次最终测试和审查结论。它也不是另一个 P1 指标来源认证。
- [source_certification.py](../../src/pring_cycle/source_certification.py) 仍可看到旧 v0003/旧来源包创建流程；函数名、旧 `certified` 标签和旧 smoke 已验证标签都不能跳过冻结规格的新目录、新包、新候选读取要求。本轮未调用这些函数。

阅读时关键源码 SHA256：`official_context.py=fae1b0310e6534b2d6ebd6a439614460f1ce4ecfdd4dcbd70361319736ad9d73`；`tushare_context.py=e48f670b8f25b596cb4612cfb6e1f587727d59cf98747e9ceacc80c6fa6cb2bd`；`context_projection.py=750db8aa3976c8ebe5369be9e4b72dffd2de628eff71178df2470eb3a695396d`。这是读时指纹，父代理后续合法修改不使本研究原件失效，也不表示本报告覆盖新源码。

## 最小推进顺序与完成门槛

1. **先做 A 组 18 项材料整理**：从已存原发布建立“字段/单位/实际期次/原页时间/原件/真实取得记录/修订版本/用途”的家族认证草案；PMI、工业财务和金融统计共享原件，复用而不重复认证计数。CPI 等旧时间错误追加新版本，不原地修改。具体少列已定位，先列真实应有字段再验覆盖。
2. **B 组按两条轴继续**：DR007/Shibor 的数值抽样可立即整理，历史 PUBLIC 仍未知；LPR 原页时间已有，先核来源用途对应和报价生效读取。适用授权和时间证据分开，UNKNOWN 不改写为 HTTP 失败。既有授权能解决的直接引用，不另造审批。
3. **C 组保留最小外补**：仓单补 PP/CF/TA 与身份/单位，RRR 补最近前置、窗口事件覆盖和阶段期限。任何合法范围替换必须另有明确决定，不能缩成 5 品种或单个 RRR scope 宣称通过。研究没有需要再次无限探测的理由。
4. **D 组按父项准备**：固定公式、手算、单位、完整窗口、PUBLIC/SYSTEM、修订 lineage 逐项关联；来源认证/定义认证/可见性/实际采用分别给结论。名义库存价格调整、贷款月变动、OMO 日净投放仍按原所属指标和上下文公式处理，不能悄加 P1 分母。
5. **真实验证另行执行**：以上材料经正式认证准备后，才形成新目录的 27 行真实候选矩阵，再执行已定 120 中国交易日 PUBLIC 重建、历史 SYSTEM 视角及当前目标日运行。统计应保留“已取得/字段有效/已认证/PUBLIC 可见/SYSTEM 可见/被采用”各栏，并单独核对报告解释；不以前四步文档完成代替后一步。

## 单文件交付及只读复核

**本轮精确新增文件名单只有 `.scratch/pring-data-acquisition-repair/p1-certification-readiness.md`。** 没有新增证据目录、脚本、原件、JSON、模型或认证。报告本地链接在交付时逐个 `is_file` 核验；27 行 ID 与源码中的 20 官方、3 非重叠结构化、4 派生集合独立比对，GDP 排除在 27 行之外。报告字节数和 SHA256 在交付消息提供，避免将自身摘要循环写入正文。

可使用 Windows 标准库只读核查精确文件、27 行、所有本地链接与摘要（不导入应用）：

```powershell
$p1Check = @'
import ast, hashlib, re
from pathlib import Path
from urllib.parse import unquote, urlsplit
p = Path('D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/p1-certification-readiness.md')
raw = p.read_bytes()
t = raw.decode('utf-8')
ids = re.findall(r'^\| \d{2} `(CN_[A-Z0-9_]+)`', t, re.M)
tree = ast.parse((p.parents[2] / 'src/pring_cycle/source_certification.py').read_text(encoding='utf-8'))
sets = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {'_OFFICIAL_DIRECT_P1', '_DERIVED_P1'}}
expected = sets['_OFFICIAL_DIRECT_P1'] | sets['_DERIVED_P1'] | {
    'CN_DR007', 'CN_SHIBOR_ON_1W_3M', 'CN_FUTURES_WARRANTS'}
assert len(ids) == len(set(ids)) == len(expected) == 27 and set(ids) == expected
assert 'CN_GDP' not in ids
links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', t.split('```powershell')[0])
local = [unquote(v.strip('<>').split('#', 1)[0]) for v in links
         if not urlsplit(v.strip('<>')).scheme and not v.startswith('#')]
for v in local:
    assert (p.parent / v).resolve().is_file(), v
print({'validation': 'passed', 'p1_rows': len(ids), 'local_links': len(local),
       'delivery_files': [str(p)], 'bytes': len(raw),
       'sha256': hashlib.sha256(raw).hexdigest()})
'@
$p1Check | C:/Python313/python.exe -B -
```

该复核不调用来源认证函数，不联网，也不把新 `certified` 状态写入模型；它只证明本报告范围、引用和交付摘要可复核。
