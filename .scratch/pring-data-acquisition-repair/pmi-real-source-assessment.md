# PMI 三项实际来源审查：现有七期证据的六轴结论

2026-09-09，Asia/Shanghai。仅评价 `nbs_pmi` 的 `CN_PMI_ACTIVITY`、`CN_PMI_INVENTORY`、`CN_PMI_PRICES`，以及下列 2026-01—2026-07 七个精确原件的**对应当月行**。本次复用既有 56 格逐值审计，没有重新逐值审计、扩大历史抓取、运行应用/SQL/测试或生成正式 accepted 包。

**这七期材料的 semantics、fields、history、time、permissions、usage 均为 supported，限本报告写明的官方直发统计数值、本地个人使用和具体保存版本。未发现这七份原件存在必须单列为 conflicting 的实际 NBS 数值修订或发布时间矛盾。** 七份页面的标题、统计月、可见页头和 PubDate 相互对应，可按既有规则支持所用当月行的可靠 PUBLIC；二月发布是 **2026-03-04 09:30**。国家统计局数据使用条款已有完整原件、真实 GET 收据和登记核验，PMI 七次真实 document_import 也已完成。现在的实质剩余工作是把这些已有材料在目标正式包中与新定义、完整清单、认证起日及实际登记引用绑定，并完成正式维护审查；不是再要求全档首发字节证明、重抓七个数值页或重新确认个人用途。

这里的 supported 是本次证据评估，**不是**已写入的 `certification_status=certified`，也不是全部 P1、当前模型输出或固定 120 交易日回放已通过。规格明确区分可靠公开时间、认证资格与目标点时可见性，不增加逐历史观测双来源对账要求。[spec 实施 6—8、13](spec.md#L96)、[CONTEXT 六轴](../../CONTEXT.md#L255)、[正式准入契约](candidate-admission-contract.md#L9)

## 六轴与适用范围

| 审查轴 | 结论 | 已有一手依据与可支持的 finding | 具体剩余项 |
| --- | --- | --- | --- |
| semantics | **supported** | 各月 NBS 页面正文署名国家统计局服务业调查中心、中国物流与采购联合会；制造业表 1/2 与附注给出扩散指数、季调、调查方法。三组分别反映活动、库存及价格调查指数水平，不能解释成实物数量、名义库存金额或价格同比涨幅。 | 无本范围来源语义缺件；将准确语义写入被审新定义。 |
| fields | **supported** | 既有独立审计：活动 4×7=28、库存 2×7=14、价格 2×7=14，合计 56/56 字段、维度、单位和统计月边界相符，0 冲突。v2 继承该审计；本次核对七份 raw/normalized 与实际收据身份，没有重做 56 格审计。 | 无本范围缺格；正式包绑定全部八成员，不能仅给 headline 或锚点。 |
| history | **supported** | 七个连续统计月各有本月发布原件；只用各自当月行，保留季调语义、具体字节及版本。对 2026-03-09—2026-08-28 既定观察窗，期初已有二月值，一月可作必要前期参照，期末有七月值。 | 全部模型的 120 日逐 cutoff 验收尚未完成，属模型验收；当前三项与现有 PMI 同月差值公式没有“每项 120 个月”缺件。更早 TuShare 历史不能自动变成已证 PUBLIC。 |
| time | **supported** | 七页 L11 PubDate=L277 可见时间，标题/所用行属于对应统计月；有实际分钟级日期时间，不能以月末日程替换。按既有 Asia/Shanghai 解释；本次逐页检查无具体修订通知或时间矛盾。A18 收据另证明本次取得及校验时刻。 | 正式 finding 明确分钟精度与具体版本。若今后某份确实发现无新发布时间的数值/语义修订，仅该新 vintage PUBLIC 保持未知，保留旧版；不把“不能绝对排除任何修订”扩成七期共同阻断。 |
| permissions | **supported** | NBS 官方《服务条款》第三节允许下载和使用其发布的统计数据；本地已有 GET 200 原件与收据。对象是 NBS 直发 PMI 统计数值，正文与来源栏身份可核。 | 复用条款原件在目标包所用 runtime 的实际登记引用。未发现本范围需另购许可或账户授权的事实；不以版权页脚推定禁止。 |
| usage | **supported** | 本任务既定本地个人、非商业使用，取官方统计数值保存、计算和引用；条款要求准确使用及显著标注 NBS 与网址，正文联合署名同时保留。 | 将用途与署名写入 finding/报告来源。条款的第三方作品、署名文章转载、网站图形/程序等例外保留；本 finding 不授予商业分发或整篇署名文章再版许可。 |

semantics/fields 依据为[既有独立逐值审计](p1-pmi-full-value-audit.md#L5)、[精确八字段映射](p1-pmi-full-value-audit.md#L57)及下列原件正文 L332、附注 R01—R03 L1200 / R04—R07 L1201。permissions/usage 的直接依据见[已存完整 NBS 条款 L284](evidence-cpi-import-20260908/fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe#L284)，不是凭 CPI 报告中的概述授信。

全部八成员仍为 `measure=level`、`unit=diffusion_index_points`、`period_kind=month`：活动为 manufacturing/production/new_orders/purchase_volume，库存为 raw_materials/finished_goods，价格为 purchase_prices/output_prices。原表“单位：%”是扩散指数标度，保留 49.2 等原数，不除以 100。正式认证不能把八个成员计成八个独立指标，也不能把同一 HTML 的重复表计成两个来源。[原表映射与季调解释](p1-pmi-full-value-audit.md#L57)

## 七份原件、页面时间及版本判断

以下七文件均读取原始 UTF-8 字节并核对 SHA/长度，合计 **2,894,481 bytes**。原件均位于已交付的 A18 目录，毋须依赖个人旧 CAS 路径。本次新增检查为页头、标题、正文/附注身份、明显更正标记及收据连接；既有 56 格结果单独复用。

| 统计期 / 官方出处 | PubDate = 可见页头；Asia/Shanghai | 精确原件 | bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| [2026-01](https://www.stats.gov.cn/sj/zxfb/202601/t20260131_1962416.html) | 2026/01/31 09:30 | [R01](evidence-a18-import-20260909/6ef53006136e5a396533fe406f620e1799e7b0bc4246b380fb18e6294edab423#L277) | 399277 | `6ef53006136e5a396533fe406f620e1799e7b0bc4246b380fb18e6294edab423` |
| [2026-02](https://www.stats.gov.cn/sj/zxfb/202603/t20260304_1962699.html) | 2026/03/04 09:30 | [R02](evidence-a18-import-20260909/2d5629a61b4ed28718746b3b2559505ba4162612891f5352604a7c1f2a9075ba#L277) | 406069 | `2d5629a61b4ed28718746b3b2559505ba4162612891f5352604a7c1f2a9075ba` |
| [2026-03](https://www.stats.gov.cn/sj/zxfb/202603/t20260331_1962889.html) | 2026/03/31 09:30 | [R03](evidence-a18-import-20260909/31fc72c16f315e6da565e3cc2fac132d8b3a883878e84e302bbe68b2aad1acfa#L277) | 422725 | `31fc72c16f315e6da565e3cc2fac132d8b3a883878e84e302bbe68b2aad1acfa` |
| [2026-04](https://www.stats.gov.cn/sj/zxfb/202604/t20260430_1963473.html) | 2026/04/30 09:30 | [R04](evidence-a18-import-20260909/83ee41d92e01359a9397413cc26b6db9088d1d61e05db19a7eae147b946b4aa0#L277) | 422339 | `83ee41d92e01359a9397413cc26b6db9088d1d61e05db19a7eae147b946b4aa0` |
| [2026-05](https://www.stats.gov.cn/sj/zxfb/202605/t20260531_1963824.html) | 2026/05/31 09:30 | [R05](evidence-a18-import-20260909/1b0658de10a52ac891f491ef1e6f7120da9b16a25e7d73ca1005dcb8148bcbf3#L277) | 422319 | `1b0658de10a52ac891f491ef1e6f7120da9b16a25e7d73ca1005dcb8148bcbf3` |
| [2026-06](https://www.stats.gov.cn/sj/zxfb/202606/t20260630_1964032.html) | 2026/06/30 09:30 | [R06](evidence-a18-import-20260909/f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c#L277) | 422863 | `f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c` |
| [2026-07](https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html) | 2026/07/31 09:30 | [R07](evidence-a18-import-20260909/fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6#L277) | 398889 | `fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6` |

每页 L8 标题为对应年月“中国采购经理指数运行情况”，L284 来源栏为国家统计局，L332 正文明确制造业统计月。两处时间来自**同一页面**，只能证明内部一致，不能算双源。之所以 time supported，是官方身份、对应发布正文、所用当月行、页头时间及未发现具体反证合在一起；不是看到任意页头就无条件升级。既有规则已明确“原页时间可证明这份来源声明所引用页面的公开时间”，并单独处理实际修订。[研究13时间边界](research-13.md#L42)

七页没有明写时区或秒数；采用项目既有 `Asia/Shanghai` 是规则解释，分钟补 `:00` 是现有时间序列化，不声称官方提供了独立秒级证据。[当前时间解析](../../src/pring_cycle/official_context.py#L2085)与[既有双点时约定](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md#L7)不要求为每个 NBS 页面重复取得官方时区声明。仅有日期者才从下一本地日进入 PUBLIC；七页已有分钟时间，不应无依据全部降为“无可靠日期”。[spec 实施6](spec.md#L96)

| 具体检查对象 | 结论 | 对正式审查的影响 |
| --- | --- | --- |
| 七页自己的 PubDate、可见时间与所用当前统计月 | **supported**；7/7 时间字面一致，标题与所用月一致。 | 使用各自实证时间；二月不能写成 02-28，URL 的三月不能把统计期变成三月。 |
| 当前所读七份原件的更正/修订信息 | **未发现具体 conflicting 项**。正文/附注表明季调，但本次检查未见修订、修正、更正或另一个更新时刻说明。 | 这是对已读版本的有限判断，不证明永无修订。无实际反证不构成额外缺件。未来具体无时间修订需新 vintage/未知 PUBLIC；现有处理也保留此门。[修订守卫](../../src/pring_cycle/official_context.py#L428) |
| 后期页里的早期历史行 | **incomplete**，未审其首发版本与独立时间，且不在本次 56 格使用范围。 | 不回填早期首发；也不因未使用历史行缺证而否定当前月。 |
| 旧 TuShare 24 个月 SYSTEM 值及时间 | **incomplete**，不是本次 NBS 时间认证的替代物。旧七月样本值相符，但 TuShare `release_at=null`，PUBLIC 被记为 08-31 03:14:42.411073 UTC；NBS 是 07-31 01:30 UTC。 | 该晚时间不能当 NBS 官方发布或证明 NBS 数值修订；旧渠道时间不继承到新 NBS 声明。旧系统记录保留，不能用旧 certified 标签充当新审查。 |

最后一项据[旧查询快照的活动](evidence-13/legacy-read-matrix.json#L4582)、[库存](evidence-13/legacy-read-matrix.json#L4974)、[价格](evidence-13/legacy-read-matrix.json#L5216)：各自七月 NBS 样本均引用 R07 同一 raw hash，`supersedes_claim_id=null`，公开时间与本次 R07 一致。旧查询快照只提供该样本，不据此宣称检查过全部旧库修订。旧 TuShare 与 NBS 的交付时间不同、或页面有季调说明，本身都不构成已证的当月数值更正。

## A18 已有取得收据，未生成来源声明或认证

[原 A18 收据](evidence-a18-import-20260909/receipts.json)内 PMI 对应准备结果索引 **78、85、99、130、160、188、218**，七项全部 `status=captured`、`state=validated`、`scalar_count=8`、`matches_preparation_fields=true`。均为国家统计局、`api_name=document_import`、`official-context-parser-v0004`；parameters 固定 nbs_pmi/统计月/原 URL/v2 preparation hash。每个 normalized 都是 3,568 bytes，下表文件名等于逐件复核的完整 SHA，合计 24,976 bytes；各自顶层公开时间与上表一致。

| 统计期 / 收据定位 | acquisition_id | received_at UTC | validated_at UTC | 已存 normalized（文件名=SHA-256） |
| --- | --- | --- | --- | --- |
| [2026-01 / 78](evidence-a18-import-20260909/receipts.json#L2546) | `acquisition-fb546806418840c5aa92ac70175c24db` | 2026-09-09 07:47:40.978572 | 2026-09-09 07:47:41.035387 | [N01](evidence-a18-import-20260909/e839e9a1111462f66b93e9212c86f84687a63ad20f658733f6ead9903cafee22) |
| [2026-02 / 85](evidence-a18-import-20260909/receipts.json#L2770) | `acquisition-876dab12a41241d192f05e48ee45d556` | 2026-09-09 07:47:41.572220 | 2026-09-09 07:47:41.672618 | [N02](evidence-a18-import-20260909/bc8d020ad28a134041d9af5f198a1b7a6c1127eb5e3b845c6e0dff80670195f0) |
| [2026-03 / 99](evidence-a18-import-20260909/receipts.json#L3218) | `acquisition-369e7dc9f1cb48029bbcbde5640c0365` | 2026-09-09 07:47:43.374747 | 2026-09-09 07:47:43.444650 | [N03](evidence-a18-import-20260909/3484a302dc510aa3f386d7d90f434e876aca6b0fe92516a6bebcb4f7aac926f4) |
| [2026-04 / 130](evidence-a18-import-20260909/receipts.json#L4210) | `acquisition-3508371a464e403185c3c735fd897bf2` | 2026-09-09 07:47:46.719342 | 2026-09-09 07:47:46.870336 | [N04](evidence-a18-import-20260909/56be8dcca208015251d8d76da7d3809c6c81a74457283cff63d840e81a0ef3a5) |
| [2026-05 / 160](evidence-a18-import-20260909/receipts.json#L5170) | `acquisition-c093bba79476493f890a1862b779c769` | 2026-09-09 07:47:52.724193 | 2026-09-09 07:47:52.874469 | [N05](evidence-a18-import-20260909/65906421cc38a7a0deb9712def1ad8323952ff77556b7541b97cb30c74ab7e47) |
| [2026-06 / 188](evidence-a18-import-20260909/receipts.json#L6066) | `acquisition-785c811d7f3341849c3719410b95e97a` | 2026-09-09 07:47:58.923764 | 2026-09-09 07:47:59.078203 | [N06](evidence-a18-import-20260909/b4ee6b2cf5ac8cf0dc590e90842e41c219873255f3b00e0a8b50dfeb79b6222b) |
| [2026-07 / 218](evidence-a18-import-20260909/receipts.json#L7026) | `acquisition-e2230476d8a046e099bcef5c9ecb2978` | 2026-09-09 07:48:05.324939 | 2026-09-09 07:48:05.507743 | [N07](evidence-a18-import-20260909/323d7abe5f4bd5623b52ba9c70c17938a86dd753bf470cb453df1ba5d9ddbfe6) |

本次确认这七项 started≤received≤validated，各原件 SHA 与准备包及审计引用一致。上述时刻是 **2026-09-09 的真实本次导入**，不是原始 HTTP 首次取得、不是 2026 年上半年的历史 SYSTEM。当前导入包还没有来源声明；未来声明系统可用时间仍须服从公开入库与实际校验时钟，不能仅抄表把未执行入库称作已可用。[系统校验规则](../../src/pring_cycle/acquisition.py#L241)、[公开声明链](../../src/pring_cycle/official_context.py#L455)、[spec 收据与双时间](spec.md#L93)

原 A18 总批的两个失败是贷款 index22 与 OMO index223，均不涉及 PMI。[原批交付核验](evidence-a18-import-20260909/delivery-verification.json)、[追加恢复收据](evidence-a18-import-recovery-20260909-01/recovery.json)、[合并核验](evidence-a18-import-recovery-20260909-01/combined-verification.json)已把 268 个请求位置选出 268 份合格取得收据，保留旧失败，域表来源声明/模型均为 0。Q1 产能映射 pending 属另一家族，既不阻断这七次 capture，也不能被 PMI supported 顺带解决。

## NBS 使用条款已真实保存，可直接复用

七个 PMI 页脚指向同一个[国家统计局服务条款](https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html)：R01—R03 L3230，R04—R07 L3232。本次在仓库找到并实际读取完整原件，**不再沿用早期 CPI 研究“raw_saved=false”的过时准备状态**。

| 已有材料 | bytes | SHA-256 |
| --- | ---: | --- |
| [NBS 服务条款完整原件](evidence-cpi-import-20260908/fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe) | 127670 | `fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe` |
| [条款请求规范化记录](evidence-cpi-import-20260908/0f568d8de53b16c8351b999a72b02c91689e3cb8fd1397db17f46dc5f1ec78c8) | 328 | `0f568d8de53b16c8351b999a72b02c91689e3cb8fd1397db17f46dc5f1ec78c8` |

[CPI 取得包收据](evidence-cpi-import-20260908/receipts.json#L1099)中 `acquisition-282e8ca009d24cd485cf168683c58e00` 已记录 `official_http_get`、GET 200、最终 URL 与上面相同、`text/html`、`state=validated`。其真实 UTC 链为 started `2026-09-07 22:02:32.133692` → received `22:02:32.721262` → validated `22:02:32.754616`，当批 `network_attempts=1`。这些是**已有请求**，本轮新网络请求为 **0**，没有用网页搜索替代原文。

条款正文 L284（L298 重复）的第三节直接支持国家统计局发布统计数据的下载、使用和准确解释；第一节要求引用注明国家统计局网站与网址。第二节另列第三方内容、特别授权、图形/程序等例外和署名文章转载要求。本任务取 NBS 正式发布的统计数值作本地分析，保留来源和正文联合署名，适用第三节的数据使用依据；不把对数据的使用评估扩大成整篇署名文章免费再版、转授他人或商业再分发许可。项目已有个人非商业范围亦不应被误说成只要点击公开网址就拥有所有后续用途。[实际条款](evidence-cpi-import-20260908/fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe#L284)、[ADR0013 既定项目范围](../../docs/adr/0013-tushare-delivery-with-official-sampling.md#L9)

既有[只读核验结果](verification-cpi-consumer/import-verification.json)确认九份 validated 收据、十八制品、条款 HTTP 200；[对应核验源码](verification-cpi-consumer/verify_import.py#L35)检查每份原件以 `<acquisition_id>:raw` 登记，normalized 以 `<acquisition_id>:normalized` 登记。本轮读取这些保存结果和源码，**没有重新运行 SQL**。条款及 PMI 的旧隔离库登记不是目标新包数据库自动已有同名 URL 引用的证明：正式包可复用内容与收据，但必须在其所用 runtime 确认实际 `artifact_hash + source_reference` 关联。缺的是目标绑定操作，已不缺条款正文、真实取得收据或个人用途正面依据。[准入引用检查](../../src/pring_cycle/candidate_admission.py#L237)

## 固定观察窗与最小后续动作

对于既定 **2026-03-09—2026-08-28** 区间，PMI 所需可见月份顺序可以直接由上述可靠发布事实列出：3月9日至3月30日用二月，3月31日发布后用三月，4月30日发布后用四月，5月31日发布后用五月，6月30日发布后用六月，7月31日发布后至8月28日用七月。每个切换仍按真实 cutoff 判断；不存在把未发布的八月 PMI 当成8月28日必需值的理由。这是来源覆盖与待验收期望，不是本轮执行了中国交易日日历或完成120日重放。[固定区间约束](spec.md#L125)

一月是观察窗前已公开、可供前期参照的已存输入；只有具体输出需要时才作为隐藏输入，不改可见窗。当前三项 PMI 原始方向以 50 为阈值；现有 PMI 订单减库存、生产减订单公式读取同月成员，没有 24 月回归或 120 月滚动公式要求。[PMI 方向规则](../../src/pring_cycle/context_projection.py#L1703)、[同月差值输入](../../src/pring_cycle/context_projection.py#L938)。不能为降低缺件删掉既有完整模型的其他公式/P1，也不能把别的家族24月/8季预热要求套到这三项。本报告不为更晚目标日保证七月仍合时，也没有抓取8月以扩展本题。

| 后续状态 | 具体工作 | 是否阻止本范围正式包已完成的宣称 |
| --- | --- | --- |
| 已具备 | 七份官方当月原件、56格既有独立审计、v2结果、七份真实导入收据、七份 normalized、逐页可靠分钟时间；NBS条款原件与真实GET收据。 | 不再以这些内容“仍缺”阻断，也不重复抓取。 |
| **incomplete：正式绑定与维护审查** | 选定三项完整新定义、目标完整61项 manifest、认证起日，按实际哈希绑定六轴 findings 与已登记证据引用；选用 runtime 中的原件/收据关联需真实可读。保留全部 P1、公式和起止窗口。 | **是。** 当前只有可复用的实质审查结论，尚未生成/接受该 subject 的不可变正式包。 |
| **incomplete：新声明及模型验收** | 公开入库形成真实新版本声明，分别验证 PUBLIC 与实际 SYSTEM；验收期次切换、完整成员和父项采用，随后随完整候选执行固定120日重放及报告。 | 阻止模型完成或切换的宣称；不能反过来声称来源正文/用途仍缺，也不必先激活模型才能整理来源包。 |
| 当前 **0 项 NBS conflicting** | 若后续发现明确的无新时间修订、截断、错误当前月或时间自相矛盾，只单列具体原件、版本及所需更正证据。 | 目前没有可以据实填写的这类 PMI 硬阻断；不凭假设造缺件。 |

正式包必须由受信维护流程提供实际六项 finding/evidence、完整 subject hash、reviewer/真实 reviewed_at，机器检查其引用而不替代来源判断；本文件不包含 accepted 审查 JSON，不授予模型认证。[准入契约六轴和证据要求](candidate-admission-contract.md#L31)、[机器检查边界](../../src/pring_cycle/candidate_admission.py#L225)

## 输入指纹与本轮交付边界

上面七份 raw、七份 normalized、条款 raw/normalized 均已物理读取核哈希。下列是另外21个被引用文件的输入快照；旧审计和回执维持原样。唯一新增交付文件为 `.scratch/pring-data-acquisition-repair/pmi-real-source-assessment.md`。

| 输入 | bytes | SHA-256 |
| --- | ---: | --- |
| [p1-pmi-full-value-audit.md](p1-pmi-full-value-audit.md) | 21325 | `02901b12706b0101be06a4c5b74873cd46322fbefb9b6507dbbe7c8bfe3de7ef` |
| [p1-official-preparation-v2.md](p1-official-preparation-v2.md) | 2841 | `6623bd19acee525d3a2a18eec7749e908bf28e17b52e6f6012c92f4a7291b688` |
| [evidence-13-preparation-v2/preparation.json](evidence-13-preparation-v2/preparation.json) | 3189072 | `92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034` |
| [evidence-a18-import-20260909/receipts.json](evidence-a18-import-20260909/receipts.json) | 433467 | `199e384c879ebbb7a7fc19278529e89492dc8deecb075be990abd56afffc3b6c` |
| [evidence-a18-import-20260909/delivery-verification.json](evidence-a18-import-20260909/delivery-verification.json) | 1934 | `3d56fbc2e2094249355a63b70ab03dec1d8032d47505fde2cfb945577965fb48` |
| [evidence-a18-import-recovery-20260909-01/recovery.json](evidence-a18-import-recovery-20260909-01/recovery.json) | 3958 | `c37aed82e86198f3362cf6c79b63878f1aecd92c649170329f510930c617c4d8` |
| [evidence-a18-import-recovery-20260909-01/combined-verification.json](evidence-a18-import-recovery-20260909-01/combined-verification.json) | 1085 | `cb0768f5e8406e689958cba854122f5e8430775e950e47ad9c184bdfd3a12276` |
| [evidence-cpi-import-20260908/receipts.json](evidence-cpi-import-20260908/receipts.json) | 44462 | `f52846aa489ccb15a67d76573f5dffd54158a80edc1f99fb98e240e3557f2763` |
| [verification-cpi-consumer/import-verification.json](verification-cpi-consumer/import-verification.json) | 247 | `905dd1ba840ae5c15e0a1ccfba4dabfabd623066c249bc5bcddec2c84c9a07f5` |
| [verification-cpi-consumer/verify_import.py](verification-cpi-consumer/verify_import.py) | 3679 | `0d56ba6253ecb80c9aa6a74375838f42cb1749c32596884fabf1a2f72191c0e5` |
| [candidate-admission-contract.md](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [spec.md](spec.md) | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| [research-13.md](research-13.md) | 31765 | `dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1` |
| [evidence-13/legacy-read-matrix.json](evidence-13/legacy-read-matrix.json) | 463940 | `740f094e922ae40ddc21098f86629df8ffcaf416c8dc4595def22f93ba5c8b46` |
| [CONTEXT.md](../../CONTEXT.md) | 20103 | `f0cdf13436e1dd178b86ac6181de916757c3ef59edb7024ec6e980f151e5a102` |
| [双点时 ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md) | 725 | `acb0c307d24518d5e4551f457353535d5398d21c8bd0212c9f9445a82012cf8a` |
| [渠道及用途 ADR](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) | 1089 | `8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b` |
| [context_projection.py](../../src/pring_cycle/context_projection.py) | 87349 | `4f2d4080a857118b693ac1e114a9d086062a879f4e9f87d5a3759383bcfbd568` |
| [official_context.py](../../src/pring_cycle/official_context.py) | 84300 | `fb0a54664e8582a2c00ee00b790a7d4d9cb6cda162c69e6dfc3f077bf9f56b11` |
| [candidate_admission.py](../../src/pring_cycle/candidate_admission.py) | 13193 | `681d108eaba822cb538dd828e459e74c64e8909c415f9d3a8f83f17135673bc4` |
| [acquisition.py](../../src/pring_cycle/acquisition.py) | 14584 | `ed81eef2b153417009c0beb356be64bbe8fd164a9f3ea0d6eafe9cdc66ad69f8` |

本轮仅用标准库读取材料/JSON/HTML及计算指纹，未导入任何应用模块或调用 parser；未使用网络、SQL、应用与测试进程。最终本地链接、原件、normalized 和以上输入哈希逐项核对，交付 bytes/hash 由完成消息提供，避免文件自包含摘要循环。
