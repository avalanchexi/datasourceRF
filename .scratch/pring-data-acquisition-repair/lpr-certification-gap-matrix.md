# LPR 真实来源认证缺口矩阵

范围仅 `CN_LPR_1Y_5Y / CHINAMONEY_LPR`。研究日：2026-09-08（Asia/Shanghai）；本地输入指纹记录于 2026-09-07T20:34:43.405938+00:00。读取时 HEAD 为 `0679a4758316bbeb520da9d79aafeb7572f5c6ce`；父代理并行实施目录消费，本报告不评价其最新代码是否通过，也不重述旧版本拒绝点。

**9 期真实官方公告的两期限数值、统计月、页头时间和报价有效期已具备可复核材料。尚不能据此宣告新目录认证完成：需要正式审查把用途范围、可证明的发布版本边界及新取得/校验收据落实到本家族，随后生成与完整候选定义绑定的正式包。** 研究记录、旧 `certified` 标签和 460 字节测试 fixture 均不能替代这些材料。范围依据：[研究 13：LPR 样本](research-13.md#L29)、[正式审查边界](candidate-admission-contract.md#L9)。

## 1. 已有 9 期公告：独立回原文核对 18 个数值

本轮没有运行应用解析器。直接用 Windows 标准库读取已保存原件，逐件复核 SHA256、字节长度，去除 HTML 标签并解码字符实体后定位原始正文。**9 个不同原件 / 9 期 / 18 个标量全部在正文明确出现：每期 1y=3.0%，5y_plus=3.5%；冲突 0、无法定位 0。** 这与旧解析记录一致，但新完成的是独立字面核对，不能把旧 9 次解析成功称为本轮重跑。九件合计 **92,717 字节**；没有复制或改写 CAS。

每份原件页头均在第 60 行，精度为分钟；正文都写报价在下一次发布之前有效。八件从现有 WSL CAS 只读读取，8 月原件使用已归档的 D 盘副本。下面链接中的 `#L60` 是原始 UTF-8 文本行号，正文行另列。

| 统计月 | 官方 URL | 页头字面时间 | 1y / 5y_plus (%) | 正文行 | 原件 / bytes / SHA256 |
| --- | --- | --- | --- | ---: | --- |
| 2025-12 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20251222/3256124.html) | 2025-12-22 09:00 | 3.0 / 3.5 | 78 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/29/29b9ad8e5c806acc7acf3a7e7990ef5e69182ccd806d74ef1b677968b2b0cb7e#L60)；9457；`29b9ad8e5c806acc7acf3a7e7990ef5e69182ccd806d74ef1b677968b2b0cb7e` |
| 2026-01 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260120/3271248.html) | 2026-01-20 09:00 | 3.0 / 3.5 | 78 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/56/56990bedd9bc26a666ffed41e48be8ae506f97088f353d04a31877aa5acdc0e7#L60)；12912；`56990bedd9bc26a666ffed41e48be8ae506f97088f353d04a31877aa5acdc0e7` |
| 2026-02 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260224/3285699.html) | 2026-02-24 09:00 | 3.0 / 3.5 | 75 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/75/750bfc2dcf52891998816f824b2e28606153347e1cbb9c500c4d5cb7334029f3#L60)；9038；`750bfc2dcf52891998816f824b2e28606153347e1cbb9c500c4d5cb7334029f3` |
| 2026-03 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260320/3301473.html) | 2026-03-20 09:00 | 3.0 / 3.5 | 75 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/25/25b64b21f0df5075f8d83cb98c3ca44791910a27c30df272926d3d6f6be673eb#L60)；9487；`25b64b21f0df5075f8d83cb98c3ca44791910a27c30df272926d3d6f6be673eb` |
| 2026-04 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260420/3318431.html) | 2026-04-20 09:00 | 3.0 / 3.5 | 77 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/ee/eead5d88656bfcc10df6eb250457df9a60820a0681be230dc6c046107cd3f780#L60)；11000；`eead5d88656bfcc10df6eb250457df9a60820a0681be230dc6c046107cd3f780` |
| 2026-05 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260520/3343089.html) | 2026-05-20 09:00 | 3.0 / 3.5 | 77 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/c3/c39c33680a18f172d9e875758962732e4ef6fcd6feebcc7f9aba8b7ef3c1b9ad#L60)；9941；`c39c33680a18f172d9e875758962732e4ef6fcd6feebcc7f9aba8b7ef3c1b9ad` |
| 2026-06 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260622/3361525.html) | 2026-06-22 09:00 | 3.0 / 3.5 | 77 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/7a/7a1cdcfb620910e1adaca66688375457925436d477dcf624bb8a3bb7e746357f#L60)；9941；`7a1cdcfb620910e1adaca66688375457925436d477dcf624bb8a3bb7e746357f` |
| 2026-07 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260720/3379021.html) | 2026-07-20 09:00 | 3.0 / 3.5 | 77 | [原件](//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256/40/40285435bd15e5e93edd0399301b52fa5b52aac3af4ad61d98477df13f22d2f4#L60)；9941；`40285435bd15e5e93edd0399301b52fa5b52aac3af4ad61d98477df13f22d2f4` |
| 2026-08 | [该期官方公告](https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html) | 2026-08-20 09:00 | 3.0 / 3.5 | 77 | [原件](evidence-13/5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5#L60)；11000；`5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5` |

核对入口清单是 [历史原件清单](evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec)，旧解析结果是 [history-verification.json](evidence-13/history-verification.json)。清单只定位原件，不承担独立数值期望。

对讨论中的 **2026-03-09—2026-08-28** 区间：2 月 24 日公告是起点前可延续的报价基线，3—8 月六次月度公告在窗口内；2025-12 和 2026-01 是额外前置材料。LPR 不要求 120 次月报价，也不能按 `period_end=08-31` 把 8 月 20 日已经公布的报价推迟至月底。实际切换使用各公告时间；“每月20日”计划不能替代 2 月24日、6月22日等真实公告日期。9 份原件本身**不能证明该区间不存在其他更正/补充公告**。

## 2. 单家族可执行缺口矩阵

“已具备”是证据范围；“待补”明确下一材料或动作，不代表本研究授予认证。

| 审查项 | 已具备的可证事实 | 仍不能宣称什么 | 最小补齐材料/动作 |
| --- | --- | --- | --- |
| 真实身份与语义 | 九份正文均有人民银行授权全国银行间同业拆借中心公布语句、LPR 名称及两个期限。它是贷款定价参考的报价利率，不能当央行投放金额或任意政策利率。新增基准页 GET 01 第437行再次确认定义。 | 旧研究标题“官方来源认证”或默认目录 `certified` 不是新正式审查。 | 把本家族的实际提供方、来源代码、1y/5y_plus、报价语义与拟登记完整定义逐项对应，形成 `semantics` 审查及原件引用。原件已够准备，无需重抓9份。 |
| 字段、单位和数值 | 每期两个字面值均为 3.0/3.5，单位 %，18/18 可定位；不得除以100后仍标 percent，两个期限不得互换。 | 一份 8 月样本不能单独证明整个历史输入已齐。 | 使用上表逐期两成员对照形成 `fields` 记录；入库后公开读取应保存两个独立 claim 和同一次 release event，不变成一个宽表或每天复制观测。 |
| 统计期与有效期 | 公告月份与正文日期一致，正文明确在下一次 LPR 发布前有效。2月报价可作为3月9日起的基线。 | 月度观测结束日期不是公开日期；持续有效不意味着新月份已发布。 | 用已证公告实际时间建立7段所需报价状态（2月基线+3—8月），在中国目标日截点验证切换；缺实际公告时保持上一期/缺口状态，不按计划造新值。 |
| 常规发布规则 | GET 01 第441行：每月20日遇节假日顺延，9时前报价，去极值平均并按0.05%步长取整，9时公布；公众可从拆借中心和人民银行网站查询。 | 常规9时规则不是每一历史正文版本的首发时间；HTTP Date/Last-Modified 也不是。 | 将此作为 `release_rule` 的官方依据；正式包若引用本次新基准页，需在正式受控采集中保存/登记原件。本MD只有调研回执，未新增CAS。实际各期时间继续引用上表原页。 |
| 时区与时间精度 | 项目既有定义及 parser 采用 `Asia/Shanghai`；九页仅写 `YYYY-MM-DD 09:00`。[既有时区定义](../../docs/research/lpr-official-source.md#L11)、[时间转换源码](../../src/pring_cycle/official_lpr.py#L145)。 | 页头没有独立秒级证据，不能说 `:00` 秒经官方单独证实；本次基准页也未看到单列 GMT+8 字段。 | 正式 time finding 写清分钟精度和既有源时区依据；不把无时区字串解释为 UTC，不另凭此新增用户业务审批。 |
| 历史首次发布/修订版本 | 九份官方页面带与当期一致的页头发布时间，可作为该页面的来源时间证据；已保存正文可追溯。 | **页头分钟时间 ≠ 已证明这些精确字节是当时首次发布的版本。** 目前没有每次更正的公告/原始首发归档全集，不能借未来抓取结果倒填首发版本。 | 对真实选用的每份原件形成时间审查：记录首次可证来源时间、是否发现修订及其依据。若发现改值但无新发布时间，需原始首发存档/正式更正公告或有时间证明的来源归档才能补齐该历史 PUBLIC；否则新 vintage 的 PUBLIC 保持未知。没有发现修订不等于证明没有修订；也不一概抹掉已存在的官方页头时间，更不要求每条历史值另加第二来源。 |
| 系统取得/校验时刻 | 8 月副本有 [导入记录](evidence-13/imports.json#L10)：2026-09-06T16:16:32.035780+00:00 从旧CAS复制。旧研究明确其余历史原件缺逐次 transport receipt 的边界。[回执/导入边界](research-13.md#L17)。 | 复制时刻不是原始HTTP取得时刻；页头不是 SYSTEM available_at；旧18条源查询不是新目录18条已取得事实。 | 可立即将现有9份原件走新**document_import**获取/校验收据，记本次实际时钟、raw hash、解析版本与新claims；若要重现过去SYSTEM，只能补当时真实取得/校验记录，找不到保持未知，不能重导后倒填。 |
| 使用范围（permissions / usage） | CFETS数据服务说明原件第656–658行含明确数据范围/书面许可条款，也列公共信息发布渠道或正式授权信息商为正规取得渠道；GET 02与旧原件精确一致。 | 不能只凭公开GET说自动化存储/加工/分发全获许可；也不能忽略“公共发布渠道”段落而断言个人必然无权。未读取用户账户/合同，不知道是否已有适用许可。 | 先复用既有可读授权/来源合同记录，逐项对应**LPR公告、个人本机、非商业、持久化、计算/报告、是否对外分发**。若现有记录不能解释官方两段的适用边界，具体缺件是涵盖上述用途的官方公开条款或已有书面许可/说明；可由维护者明确使用哪条已授权渠道。不要自动申请许可、采购或用TuShare一般边界替代直连CFETS授权。 |
| 新正式来源包 | 本家族已有可读原件可供六项正式审查引用；准入契约要求完整定义 hash、manifest hash、certified_from、review hash及六项 finding/evidence。[正式包字段](candidate-admission-contract.md#L19)。 | 没有形成/读取到本次新完整定义对应的正式 accepted review；不是把本矩阵放进包或复制旧标签即可通过。LPR包也不会独自满足45个必需标量来源的覆盖。 | 待上述用途和time finding据实收口后，由受信维护流程生成本家族 review/package，并将原件hash关联真实source_reference登记；再按整份候选清单绑定。认证起点若为3月9日，必须说明2月基线如何在起点已可知。 |
| 真实新目录消费验收 | 既有公开测试覆盖两期限、重复取得、缺新公开时间修订和通用CLI禁止自授认证；父代理正在修新注册目录消费。 | 本轮未运行这些测试、未审查父代理最终实现、未查询生产；fixture测试通过不代表9份真实原件已进入候选并被采用。 | 新目录能力就绪后，以真实9原件的18值走受控导入，再核PUBLIC/SYSTEM及目标日投影；正式认证与目标日可用性分别出结果，缺件不靠改时间或改版本名修复。 |

其中使用条款的一手来源是 [CFETS 数据服务说明](https://www.chinamoney.com.cn/chinese/dssjfwgl/)及[已存原件 656–658 行](evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50#L656)。这不是法律结论，而是明确条款与实际用途尚需对应的认证缺件。已接受的 [ADR0013](../../docs/adr/0013-tushare-delivery-with-official-sampling.md#L7) 允许本地个人非商业的 TuShare 交付并进行官方抽样；不要求用户再次确认相同授权，也不自动把此授权扩大到另一直接提供方。

## 3. 下一票按最小依赖执行

1. **不等新网页即可完成：**把本表9个原件和18个字面值、两成员、实际月度公布日期及有效期归入 LPR `semantics / fields / history` 草案；复用已接受 `Asia/Shanghai` 定义，准确标注分钟精度。已存原件和对应URL足以进入这一步。
2. **先补具体使用对应：**查已有授权材料能否覆盖CFETS直连LPR公告本地存储和分析；有即引用，不再问同一许可。没有可核验记录时，待补的不是“同意研究”，而是适用上述用途的来源条款/许可依据。PBOC官网可查询是本次官方说明明确列出的替代入口，但本轮没有取得其对应9期原件或用途依据，不能擅自切换host并沿用现有认证。
3. **将历史时间分成两类交付：**页头/正文相符的来源日期证据可以立即整理；“原件首次版本”与旧SYSTEM时刻不足之处保持准确未知。只有实际修订或首次版本问题需要新增原始存档/更正公告，不能拿常规9时或研究日时钟补齐。
4. **软件接入完成后走真实材料验收：**先以现有原件产生新document_import收据及18条新版本声明，原件校验完成后记录SYSTEM可用时间；再按正式 time finding 测PUBLIC，核3月9日基线、3月20日/8月20日切换和固定8月28日目标。没有PUBLIC合格材料的点仍缺，不能凭数值一致判重放合格。此项由后续执行完成，本报告没有修改应用或数据库。

建议保留的公开反例已有可定位测试：[两期限解析](../../tests/adapters/test_chinamoney_lpr.py#L23)、[重复取得保留原可用时间](../../tests/adapters/test_chinamoney_lpr.py#L163)、[修订无新发布时间](../../tests/adapters/test_chinamoney_lpr.py#L203)、[通用CLI不能自授认证](../../tests/e2e/test_lpr_release_cli.py#L54)。测试材料 [460字节fixture](../../tests/fixtures/chinamoney_lpr_20260820.html) 与上表8月**11,000字节真实原件**严格区分。旧 [说明中smoke/refresh文字](../../docs/research/lpr-official-source.md#L32) 是历史文档，不能代替当前逐请求收据和新正式包验收。

## 4. 本轮实际网络回执

**新GET尝试2次，收到HTTP 200为2次，访问失败0次；无重定向跟随、无重试、无账户/密钥、无后台枚举。2份响应合计110,712字节，读取上限各1,000,001字节，均未截断。** 两次均为已知官方说明入口，不是新增LPR历史数值样本；新增历史数值样本0、授予认证0、生产写入0。达到本任务目的后停止，未凑满4页上限。

本报告按单文件交付限制保存URL、真实访问时钟、状态、内容摘要及精确响应hash；没有把新响应另存CAS或伪称已经可作正式包artifact。GET02与旧已存原件hash一致，可直接复核；GET01的hash只描述本次内存响应，正式证据引用前仍需保存/登记原始字节。响应Date、Last-Modified均只作HTTP元数据，不作任何历史LPR首发时间。

| 回执 | GET 01 | GET 02 |
| --- | --- | --- |
| URL/最终URL | https://www.chinamoney.com.cn/chinese/bklpr/ | https://www.chinamoney.com.cn/chinese/dssjfwgl/ |
| 请求开始UTC | 2026-09-07T20:33:13.289835+00:00 | 2026-09-07T20:33:13.592380+00:00 |
| 接收完成UTC | 2026-09-07T20:33:13.587080+00:00 | 2026-09-07T20:33:13.899448+00:00 |
| HTTP / 类型 / bytes | 200 / text/html / 21308 | 200 / text/html / 89404 |
| SHA256 | `673c0cc2f6c5a494f67fbc1d033617551f1382ad4527847a4ed1b6cb11e4e0ca` | `1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50` |
| Last-Modified | Sun, 23 Aug 2026 01:00:03 GMT | Fri, 14 Aug 2026 01:21:40 GMT |
| 内容定位 | 原响应437行：两个品种/贷款定价参考；441行：20日顺延、9时报价公布规则、两个官网查询入口 | 原响应656–658行：数据范围、书面许可限制、正规取得渠道；与旧原件完全一致 |
| 可证明/不可证明 | [基准规则说明](https://www.chinamoney.com.cn/chinese/bklpr/)，不证明任一月首发字节和用户许可 | [当前条款说明](https://www.chinamoney.com.cn/chinese/dssjfwgl/)，不证明实际用户合同是否存在 |

## 5. 输入指纹与只读复核

上表9原件已逐件读到，CAS路径和SHA即其校验身份；以下只列本家族实际引用的13个本地文档/源码/回执输入，不复扫全项目。父代理可能继续修改代码，届时源码指纹应作为本轮读取快照，不能用旧报告声称新代码已验证。对任意原件重算SHA只证明字节完整，不证明原始HTTP取得或历史首发。

| 输入路径 | bytes | SHA256 |
| --- | ---: | --- |
| [.scratch/pring-data-acquisition-repair/research-13.md](research-13.md) | 31765 | `dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1` |
| [.scratch/pring-data-acquisition-repair/candidate-admission-contract.md](candidate-admission-contract.md) | 4937 | `649b65963e52f1f1dc2a217dd513427ba0f1d7084c062f1266df56c15ff551fc` |
| [.scratch/pring-data-acquisition-repair/evidence-13/imports.json](evidence-13/imports.json) | 5145 | `07da00c64b09c728052b2c2ab5ff7156df6e403714f28653e86d4b9c9855b875` |
| [.scratch/pring-data-acquisition-repair/evidence-13/receipts.json](evidence-13/receipts.json) | 11329 | `edb8fa76f4254b96867d3c55bcd58b1ba432a5d8f71cedbd5c372773663c37c9` |
| [.scratch/pring-data-acquisition-repair/evidence-13/history-verification.json](evidence-13/history-verification.json) | 1622488 | `65a153a43ee952ff40640f5faa86c83539f832d1075fbb652b5dc539c656d977` |
| [.scratch/pring-data-acquisition-repair/evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec](evidence-13/69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec) | 94304 | `69f29104d4152da5082013214ae6817634a9a268dd9f9859aa85cda985417eec` |
| [.scratch/pring-data-acquisition-repair/evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50](evidence-13/1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50) | 89404 | `1732c0c0fe89a07456d80ffdaef80aa483fba7b3af7de903a6e2767a288ccf50` |
| [docs/research/lpr-official-source.md](../../docs/research/lpr-official-source.md) | 1695 | `13ad855518f1abd38dd3dc8c26e4da8e412b9945cf272817c38de65a9fedd0dd` |
| [docs/adr/0013-tushare-delivery-with-official-sampling.md](../../docs/adr/0013-tushare-delivery-with-official-sampling.md) | 1089 | `8580553c46299947b55e1dfef8718e43c121019a60e54b4f9b91f466ef4cac4b` |
| [src/pring_cycle/official_lpr.py](../../src/pring_cycle/official_lpr.py) | 15707 | `2173c4ea5d3c16acd26fb58c9a9a04ae79e5519403be93bf8b46a94f22f290d1` |
| [tests/adapters/test_chinamoney_lpr.py](../../tests/adapters/test_chinamoney_lpr.py) | 8068 | `d242469191e1908af601c13216da20635f185b4105d106ebd1438813d0119d66` |
| [tests/e2e/test_lpr_release_cli.py](../../tests/e2e/test_lpr_release_cli.py) | 4509 | `418b78316f1689d93b6aa97560b3f48e87b98dba2a0bdd312e2cc84ca371012c` |
| [tests/fixtures/chinamoney_lpr_20260820.html](../../tests/fixtures/chinamoney_lpr_20260820.html) | 460 | `0f5bbc368da1157eb84591003b6ecaf5d0b4494b5af526a4975d1e293355fe6e` |

唯一新增交付文件：`.scratch/pring-data-acquisition-repair/lpr-certification-gap-matrix.md`。没有写入其他原件、JSON、日志、代码、生产库或认证。

Windows仓库根可执行以下默认只读标准库复核；它不导入项目、不连接数据库、不联网、不写文件。检查本地引用及行号、13输入指纹与9原件hash/长度，并打印本MD bytes/SHA。

```powershell
@'
from pathlib import Path
from urllib.parse import unquote
import re, hashlib
report = Path(".scratch/pring-data-acquisition-repair/lpr-certification-gap-matrix.md")
raw = report.read_bytes()
text = raw.decode("utf-8")
def local(target):
    p = unquote(target.split("#", 1)[0])
    return Path(p) if p.startswith("//wsl.localhost/") else report.parent / p
links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
local_links = [t for t in links if not t.startswith(("https://", "http://"))]
for target in local_links:
    path = local(target)
    assert path.is_file(), str(path)
    anchor = target.partition("#")[2]
    if anchor.startswith("L") and anchor[1:].isdigit():
        assert 1 <= int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines())
inputs = re.findall(r"^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M)
originals = re.findall(r"\[\u539f\u4ef6\]\(([^)]+)\)\uff1b(\d+)\uff1b`([0-9a-f]{64})`", text)
assert len(inputs) == 13 and len(originals) == 9
for target, count, sha in [*inputs, *originals]:
    content = local(target).read_bytes()
    assert (len(content), hashlib.sha256(content).hexdigest()) == (int(count), sha), target
print({"inputs": len(inputs), "originals": len(originals),
       "local_links": len(local_links), "bytes": len(raw),
       "sha256": hashlib.sha256(raw).hexdigest()})
'@ | C:/Python313/python.exe -B -
```

