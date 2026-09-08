# 四缺口预实验：下载原文的独立核验

核验日：2026-09-08，Asia/Shanghai。依据[冻结设计](search-preexperiment-design.md)第3节逐候选审阅[既有 result.json](evidence-search-preexperiment-20260908-n4-v1/result.json)及其原件。**Tavily 命中所需 PBC 原始降准通知，来源锚点为 1/4；Exa 为 0/4。CNY030、BSE 及 PP 三个具体目标仍未补齐。** 这是 N=4 目的抽样的原文层结果，不是供应商总体命中率，也不是模型可用补齐率。

本轮没有网络、重试、生产数据库访问、应用/测试执行、来源认证或模型操作；没有修改计划、执行脚本、结果、收据及原件。唯一新增本报告。`result.json` 的 `original_validity=not_evaluated` 是采集阶段快照；以下是独立后续审阅，不回写该快照。所有模型指标保持 **N/A：本轮未评估**。

## 1. 实际材料与计数

8 个搜索臂记录是两供应商各4次，均 HTTP 200；两臂各有3个样本返回候选，PP 两臂均无候选。保留18个候选槽位：9个 `received`、3个 `failed`、5个域名不在冻结名单而 `not_attempted`、1个 `known_prior_candidate`。其中12次实际 GET 是9次200与3次北交所自指302。**完整且有实质正文/表格的材料为8份（5 PDF＋3 PBC HTML），另1份200是 CSI 前端壳页，不能算已取得数据正文。**

12次 GET 保存的响应体合计 **2,267,553 字节**；去重为 **10份、2,267,277 字节**。3次302共享同一138字节体，不能按1个哈希把失败请求分母缩成1。本轮逐份重新计算10份字节SHA，与收据一致；“10份”是本包的唯一响应体数，不表示10份此前从未取得的新证据。

PDF使用 `C:/Python313/python.exe -B`、pypdf 6.1.3提取全部10页，并以PyMuPDF 1.28.2在内存渲染两页并列图逐份目视核对。没有保存PNG或C盘临时文件。HTML按UTF-8原始行号定位；PDF下文的页码为1起，`P1:L9`等文本行号指本环境 `PdfReader(...).pages[n].extract_text().splitlines()` 的输出，版面定位同时给出。WSL dev-venv没有PDF库，未安装/改环境；实际文档核验使用既有Windows PDF库，没有导入项目应用。

## 2. 每个候选的结论

候选编号沿 `result.json` 的 `candidate_index`，从0起；“无原件”只表示本轮未读，不推断外部页面不存在或内容错误。每行收据链接保存完整 URL 和实际请求状态。具体原件 R1—R10 的字节、SHA及链接见第5节。

| 臂 / 候选 | 实际对象与取得状态 | 原文判定 / 冻结样本命中 | 原件或收据 |
|---|---|---|---|
| BSE / Tavily 0 | `www.bse.cn/jygl_list/200013680.html`，既知失败业务指南，未重复GET | `known_prior_candidate`；没有目标日融资余额原件 | [回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-tavily-document-0.json) |
| BSE / Tavily 1 | 路径含 `2025-08-26/...pdf`；GET302自指，收到HTML | `transport_failed`；无统计日、数值、单位或发布证据；URL中的日期不替代原文身份 | R1；[回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-tavily-document-1.json) |
| BSE / Tavily 2 | 路径含 `2025-10-29/...pdf`；GET302自指，收到HTML | 同上；不能按扩展名当PDF | R1；[回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-tavily-document-2.json) |
| BSE / Exa 0 | `edu.bse.cn/neeqedu/bse/course/play.jspx?id=242`，未GET | `outside_frozen_host_allowlist`；内容/日期/数值未核，不算原文成功 | [回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-exa-document-0.json) |
| BSE / Exa 1 | `bond.bse.cn/cbb/login`，未GET | 同上；路径含login不能被表述为本轮已看到登录页 | [回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-exa-document-1.json) |
| BSE / Exa 2 | `www.bse.cn/qt/200025237.html`，GET302自指 | `transport_failed`；R1只有302提示，没有融资数据 | R1；[回执](evidence-search-preexperiment-20260908-n4-v1/bse-margin-20260828-exa-document-2.json) |
| CNY030 / Exa 0 | `930916factsheet.pdf`，200、2页 | `identity_or_period_mismatch`；中证10年期国债指数930916，2026-08-31资料；无CNY030/08-28点位。且与旧包同URL原件完全相同 | R2；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-exa-document-0.json) |
| CNY030 / Exa 1 | `931080factsheet.pdf`，200、2页 | `identity_or_period_mismatch`；中证30年期国债指数931080，2026-08-31资料；无目标点位 | R3；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-exa-document-1.json) |
| CNY030 / Exa 2 | `www.csindex.com.cn/main#/`，200、HTML前端壳 | `missing_field_or_unit`；原始HTML标题为空，主体为app容器/脚本，未取得目标代码、日期和点位行；未执行JS或补接口 | R4；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-exa-document-2.json) |
| CNY030 / Tavily 0 | `000012factsheet.pdf`，200、2页 | `identity_or_period_mismatch`；上证国债母指数000012，2026-08-31资料，不能替代全价派生000012CNY030 | R5；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-tavily-document-0.json) |
| CNY030 / Tavily 1 | `932200factsheet.pdf`，200、2页 | `identity_or_period_mismatch`；中证国债及政策性金融债0-3年指数932200，2026-08-31资料 | R6；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-tavily-document-1.json) |
| CNY030 / Tavily 2 | `H11077factsheet.pdf`，200、2页 | `identity_or_period_mismatch`；上证10年期国债指数H11077，2026-08-31资料 | R7；[回执](evidence-search-preexperiment-20260908-n4-v1/cny030-close-20260828-tavily-document-2.json) |
| RRR / Exa 0 | `wuhan.pbc.gov.cn/.../2025092212554653911/index.html`，未GET | `outside_frozen_host_allowlist`；不能因与www路径相似就把Tavily取得的原件追记到本候选/Exa | [回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-exa-document-0.json) |
| RRR / Exa 1 | PBC“国新办举行新闻发布会”实录，200 | `partial_source_evidence`；新增PBC宿主的原始发布会实录，明确降准0.5pp、两类机构5%→0%及阶段性，但没有5月15日生效日，不能独立满足冻结原通知样本 | R8；[回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-exa-document-1.json) |
| RRR / Exa 2 | PBC“2025年上半年中国货币政策大事记”，200 | `partial_source_evidence`；5月15日事件、两范围/幅度明示，但这是8月回顾，不是原始通知；不计原通知命中 | R9；[回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-exa-document-2.json) |
| RRR / Tavily 0 | PBC“中国人民银行决定下调金融机构存款准备金率”，200 | **`valid_source_anchor=true`**；原始通知明确2025-05-15生效、-0.5pp及-5pp、排除已执行5%机构；页头2025-05-07 10:00:00。符合本轮所找原件 | R10；[回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-tavily-document-0.json) |
| RRR / Tavily 1 | `wuhan.pbc.gov.cn`同上路径，未GET | `outside_frozen_host_allowlist`；不计额外原件或成功 | [回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-tavily-document-1.json) |
| RRR / Tavily 2 | `camlmac.pbc.gov.cn/zhengcehuobisi/.../c342653773544ff6bda66daf0c4f1afd/index.html`，未GET | `outside_frozen_host_allowlist`；内容未核，不能自动变更为www域再读 | [回执](evidence-search-preexperiment-20260908-n4-v1/rrr-pbc-notice-20250515-tavily-document-2.json) |

PP没有通过适配器的候选行：[Tavily搜索记录](evidence-search-preexperiment-20260908-n4-v1/pp-warrants-20260828-tavily-search.json)和[Exa搜索记录](evidence-search-preexperiment-20260908-n4-v1/pp-warrants-20260828-exa-search.json)对应 `candidate_sources=[]`、`status=not_found`。根代理后续读取搜索原件确认：两家实际上各返回3条 HTTP 链接，全部被既有 HTTPS 规则排除；完整原顺序、URL及拒绝理由见[逐结果筛选记录](evidence-search-preexperiment-20260908-n4-v1/provider-candidate-screening.json)。本包没有PP原表、单位或目标日实值可核；不能把适配器无候选解释为供应商空响应、仓单0或官方无数据。

## 3. 三份 PBC HTML 的字面证据与时间

### R10：此次真正补齐的原始通知

官方URL：[中国人民银行决定下调金融机构存款准备金率](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554653911/index.html)。R10源码第3/16/265行分别为标题元数据/可见标题；第293行可见发布时间为 **`2025-05-07 10:00:00`**。第319行为原通知正文，关键原文为：

> 自2025年5月15日起，下调金融机构存款准备金率0.5个百分点（不含已执行5%存款准备金率的金融机构），下调汽车金融公司和金融租赁公司存款准备金率5个百分点。

| 字段 | 由本原件直接支持的值 | 原文定位 / 边界 |
|---|---|---|
| 事件生效日 | `2025-05-15` | L319“自2025年5月15日起” |
| 广范围 | 金融机构，排除已执行5%的机构 | L319括号限定；不能称全部机构统一降至同一利率 |
| 广范围调整 | 下调0.5个百分点，即事件变化`-0.5 percentage_points` | L319字面数值与“下调”共同决定符号；不是-0.5%相对变动 |
| 定向范围 | 汽车金融公司、金融租赁公司 | L319分别列明；可关联既有组合scope，但本核验不注册维度 |
| 定向调整 | 下调5个百分点，即事件变化`-5 percentage_points` | L319；两个范围不相加成全国-5.5pp |
| 页头声明发布时间 | `2025-05-07 10:00:00`，秒精度 | L293；L18 `PubDate=2025-05-07`与日期一致 |
| 本次实际接收 | `2026-09-08 05:50:13.265004+00:00` | 逐次收据；不倒填为2025年系统取得 |
| 本次捕获校验完成 | `2026-09-08 05:50:13.372569+00:00` | 仅pilot文档捕获/正常化时间，不是正式来源认证或模型可用时间 |
| 调整后比例 / 阶段性终点 | 本通知未披露 | 不能由其他段落的样式数字、0%或其他工具期限补齐；5%→0%及“阶段性”见R8另件，终点仍未知 |

该URL路径含 `20250922…`，L4 `createDate=2026-06-26 18:00:48`；这些不是本页所声明的发布时刻。应保留三者的原始差异，**不能用URL或页面生成时间覆盖可靠可见页头**。本HTML没有显式时区字段；将页头解释为 `Asia/Shanghai` 来自项目既有规则，不能说是本页提供了UTC偏移。

R10补齐了此前未取得的 **PBC原始宿主＋通知正文＋生效日/范围/降幅＋页头秒精度发布时间证据**。当前捕获字节不单独证明其在2025-05-07每个字符已完全如此、此后未修订或当天首次发布事件已被独立存档；应区分页头声明时间与历史字节版本证据，而不是因缺全历史快照就把页头时间一律判无效。本轮不执行PUBLIC资格赋值或正式review accepted。

### R8：PBC 宿主的原始联合发布会实录

官方URL：[国新办举行新闻发布会，介绍“一揽子金融政策支持稳市场稳预期”](https://www.pbc.gov.cn/hanglingdao/128697/128734/128874/2025111717153324219/index.html)。可见页头L330为 **`2025-05-07 19:35:13`**；L18 PubDate为同日，L4 createDate为 **2026-03-19 19:44:29**，URL路径含20251117。真实时间各保留自身身份。

- L353称发布会于2025-05-07上午9时举行。“会议开始时间”不是该网页19:35:13的发布时间，不替代通知10:00:00。
- L366原文：“降低存款准备金率0.5个百分点，预计将向市场提供长期流动性约1万亿元。”约1万亿元是预计长期流动性，不是精确到账额。
- L367：“阶段性将汽车金融公司、金融租赁公司的存款准备金率从目前的5%调降为0%。”调整前/后是百分比，变化为-5个百分点；0%是源值，不是缺值。L406再次确认。
- 正文没有5月15日生效日，本文件不能独立满足冻结样本的全部字段；但这次确实取得PBC域的实录，已经解决“只有CSRC宿主实录”的部分来源追溯问题。阶段性结束日期/续期规则仍未明确。

本次接收 `2026-09-08 05:50:12.650580+00:00`。如果以后与R10一起审阅，必须保留两份原件与各自日期，不能把R8全文当作R10的一个版本，也不能将后见组合追记成Exa独立命中了原通知。

### R9：更早的上半年回顾，仍然是回顾

官方URL：[2025年上半年中国货币政策大事记](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125963/26885e06c8e744918ad3c47ab7c80ac1/index.html)。标题L3/286明确其文种；页头L326为 **`2025-08-15 18:00:00`**，L18 PubDate同日；L4 createDate为 **2025-12-10 15:33:38**。

L370：“5月15日，中国人民银行下调金融机构存款准备金率0.5个百分点（不含已执行5%存款准备金率的金融机构），下调汽车金融公司和金融租赁公司存款准备金率5个百分点。”该事件的2025年份由全文标题确定。它补充了比此前11月大事记更早的官方回顾材料，支持两范围/生效日/降幅，但不能把8月页头倒填为5月原始通知时间，不满足冻结原通知样本。

本次接收 `2026-09-08 05:50:12.988959+00:00`。本件不提供2026窗口的事件全集、无事件声明或阶段性措施延续状态。

## 4. 五份 CSI PDF 的身份、日期与单位

五份均2页，页眉都明确 **2026年8月31日**，不是2026-08-28。目视核对第1页“全称/指数代码/发布日期/基日/基值/货币”及第2页衍生代码表。五份全文提取中 `CNY030`、`000012CNY030`、`2026-08-28`、`20260828`、`2026年8月28日`均为0次；这一辅助检查与可见身份/日期不匹配一致，结论不是仅靠关键词搜索。

| 原件 / 官方URL | 第1页真实身份与资料日期 | “发布日期”栏 / 基日（均为指数身份） | 第2页衍生身份 | PDF CreationDate=ModDate（+08:00） | 本样本判断 |
|---|---|---|---|---|---|
| R2 / [930916](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/930916factsheet.pdf) | 中证10年期国债指数 / 930916；2026-08-31 | 2016-12-05 / 2008-12-31 | 净价H20916；利息再投资N30916 | 2026-09-02 20:53:35 | 非CNY030；没有目标日逐日点位 |
| R3 / [931080](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/931080factsheet.pdf) | 中证30年期国债指数 / 931080；2026-08-31 | 2023-12-19 / 2010-12-31 | 净价931080CNY040；利息再投资931080CNY050 | 2026-09-02 20:24:23 | 非CNY030；不能将30年国债当全价派生 |
| R5 / [000012](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000012factsheet.pdf) | 上证国债指数 / 000012；2026-08-31 | 2003-01-02 / 2002-12-31 | 净价H00012；利息再投资N00012 | 2026-09-02 20:36:21 | 母指数，不是000012CNY030；图线不能重建08-28精确收盘 |
| R6 / [932200](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/932200factsheet.pdf) | 中证国债及政策性金融债0-3年指数 / 932200；2026-08-31 | 2023-10-10 / 2007-12-31 | 净价932200CNY040；利息再投资932200CNY050 | 2026-09-02 20:58:22 | 纳入政策性金融债的另一个系列；非CNY030 |
| R7 / [H11077](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/H11077factsheet.pdf) | 上证10年期国债指数 / H11077；2026-08-31 | 2013-03-07 / 2008-12-31 | 净价H01077；利息再投资N11077 | 2026-09-02 20:24:28 | 7—10年上交所国债系列；非CNY030 |

共同原文锚点：各文件P1:L9为名称/代码，P1:L14及第2页页眉为资料日期；发布日期值分别在R2/R3/R6的P1:L24、R5的P1:L22、R7的P1:L21。pypdf将表格标签与值分离，故这里用目视定位确认其对应关系，未把表内“发布日期”误当该PDF本次公开日。页眉是资料截至/版本日期，PDF创建/修改时间是文件元数据，本次接收时间又是另一个时钟；**三者都不能凭自身证明2026-08-28 CNY030数值何时首次公开**。

五份表中基值均100、货币人民币；收益率/票息/到期收益率/权重为百分比，总市值/总票面价值以亿元计，剩余期限以年计。它们不是CNY030的点位字段。R2的99.9处于“总市值（亿元）”，R3的255.40处于“凸性”；不能把这些数字或曲线刻度拿来补目标收盘值。本轮没有给CNY030推定显示精度或容差。

R2的下载URL和字节与[旧evidence-06原件](evidence-06/7a17f27cd40d266cc20fa38c57c668fc5433e42a018d4c3789a03f03ab4572a3.pdf)完全一致，旧[research-06第47—50行](research-06.md#L47)已有该宿主文件。冻结设计提出已知同URL不重试，本次执行的 `known_prior_candidates` 清单没有纳入它，实际再次GET。**这项执行偏差如实保留为1次真实请求/既有原件再取得，不计新来源锚点；不修改计划或删掉分母。** 它不影响CNY030目标仍未命中的结论。

## 5. 精确原件与取得回执

原件号对应第2节；以下SHA均由本轮从本地字节重新计算。对R1列出三个接收时刻，其他为单次接收UTC。每个时间来自同一原件的逐次捕获收据，不来自文件mtime。

| 原件 | 本地路径 | bytes | SHA256 | 接收时间UTC |
|---|---|---:|---|---|
| R1：3次BSE 302体 | [raw](evidence-search-preexperiment-20260908-n4-v1/753e0dd54f28c4f7009b9c0b18a68aed175416bd8b7d134858264586eaac56f0) | 138 | `753e0dd54f28c4f7009b9c0b18a68aed175416bd8b7d134858264586eaac56f0` | 2026-09-08 05:50:07.876841 / 05:50:08.072348 / 05:50:08.199290 |
| R2：930916 PDF | [raw](evidence-search-preexperiment-20260908-n4-v1/7a17f27cd40d266cc20fa38c57c668fc5433e42a018d4c3789a03f03ab4572a3) | 424852 | `7a17f27cd40d266cc20fa38c57c668fc5433e42a018d4c3789a03f03ab4572a3` | 2026-09-08 05:50:09.081114 |
| R3：931080 PDF | [raw](evidence-search-preexperiment-20260908-n4-v1/2ebbb79e89c57620ba765b869dad63932cb909489ce173db1fc4c522c4224893) | 426643 | `2ebbb79e89c57620ba765b869dad63932cb909489ce173db1fc4c522c4224893` | 2026-09-08 05:50:10.085190 |
| R4：CSI壳页 | [raw](evidence-search-preexperiment-20260908-n4-v1/ff777bff43a6f422eea09213df1fdcb8e121bca1cebed57b98d3fe4e50384f19) | 19697 | `ff777bff43a6f422eea09213df1fdcb8e121bca1cebed57b98d3fe4e50384f19` | 2026-09-08 05:50:10.449235 |
| R5：000012 PDF | [raw](evidence-search-preexperiment-20260908-n4-v1/14a82215156890adfa3d819e71128444f7b4903bde26c1cd7c585214b747c43b) | 421982 | `14a82215156890adfa3d819e71128444f7b4903bde26c1cd7c585214b747c43b` | 2026-09-08 05:50:10.920395 |
| R6：932200 PDF | [raw](evidence-search-preexperiment-20260908-n4-v1/c6ecf35cac9ab39754f934c7908722afc53ba0f7e5bbad607fa6a6a694e41fa7) | 421342 | `c6ecf35cac9ab39754f934c7908722afc53ba0f7e5bbad607fa6a6a694e41fa7` | 2026-09-08 05:50:11.420742 |
| R7：H11077 PDF | [raw](evidence-search-preexperiment-20260908-n4-v1/4ad377d14af081d938ba71251e9a3511712aced836e64c40ede7ba3d5fdf4892) | 419176 | `4ad377d14af081d938ba71251e9a3511712aced836e64c40ede7ba3d5fdf4892` | 2026-09-08 05:50:12.286372 |
| R8：PBC发布会 | [raw](evidence-search-preexperiment-20260908-n4-v1/f5c16c8269c89ebdad984252b18065e3e92e93e6e006b9faa7e45b1155429eba) | 78264 | `f5c16c8269c89ebdad984252b18065e3e92e93e6e006b9faa7e45b1155429eba` | 2026-09-08 05:50:12.650580 |
| R9：PBC上半年大事记 | [raw](evidence-search-preexperiment-20260908-n4-v1/7aa34fd1ecca558f5702bd5d72c794a36602e5f0c587aedd7170c44a6988728f) | 31702 | `7aa34fd1ecca558f5702bd5d72c794a36602e5f0c587aedd7170c44a6988728f` | 2026-09-08 05:50:12.988959 |
| R10：PBC原始通知 | [raw](evidence-search-preexperiment-20260908-n4-v1/27d57bb20481abc714ea45c9d99dd532652df8ee92c263b1a15cc222c256a3d9) | 23481 | `27d57bb20481abc714ea45c9d99dd532652df8ee92c263b1a15cc222c256a3d9` | 2026-09-08 05:50:13.265004 |

## 6. 可报告的分层结果与剩余事实

| 指标 | Tavily | Exa | 分母边界 |
|---|---:|---:|---|
| 搜索HTTP 200 | 4/4 | 4/4 | 实际搜索POST，不是原文GET；本报告依据已捕获的执行记录，不重发搜索 |
| 返回至少一个候选的样本 | 3/4 | 3/4 | PP无候选仍留在4个实际搜索样本中 |
| 冻结域名匹配候选 | 7/9 | 6/9 | Tavily含1个旧URL；身份符合不等于内容有效 |
| 原文GET HTTP 200 | 4/6 | 5/6 | 未GET的域名拒绝/旧URL不进物理GET分母；3个302各计1 |
| 取得有实质正文/表格的原文 | 4/6 | 4/6 | Exa的CSI壳页不计正文；这个率不要求满足目标身份 |
| 新原文满足具体样本判据 | **1/4** | **0/4** | Tavily只有RRR原通知；每臂4个实际搜索的唯一研究样本，不是9个URL |
| 有价值但不足本样本的PBC材料 | 0份 | 2份 | 发布会实录、上半年回顾分别保留，不升级为完整原通知命中 |
| 模型可用补齐 / 需求总体覆盖 / 实际模型采纳 | N/A | N/A | **本轮未评估**，不能写成模型命中25%或0% |

跨臂合并只是4个研究缺口中有1个获得新来源锚点，不称模型需求覆盖25%。9个200下载中有1份满足具体样本判据也不能代替唯一缺口分母。现有 `validated` 收据只说明pilot文档捕获正常化完成，其内含 `manual_review_pending`；不能继承为认证标签。

本次实际改变了下一步：RRR来源准备现在可以使用R10的PBC原通知及R8的PBC实录，按原文形状分别核对正式适配器、范围/时间语义与审查材料。无需再把“未找到PBC原通知”列为未解事实。仍未证明的是阶段性终点/此后状态、2026窗口完整事件序列、历史字节修订边界以及正式认证/模型消费。BSE目标日融资余额、CNY030目标日点位、PP目标日仓单/单位仍缺；本轮没有换日期、代码、范围或交易所填补。

## 7. 输入指纹与本地完整性边界

| 输入 | bytes | SHA256 |
|---|---:|---|
| [冻结设计](search-preexperiment-design.md) | 20277 | `00bbd80e73199783e6da7baabd1f0d73e91b786e3270290523595537decff7f8` |
| [执行结果](evidence-search-preexperiment-20260908-n4-v1/result.json) | 28390 | `a6ac630685d4a841fbf181495f62812d4f926ed9a9eed32d928a7491160a130a` |
| [执行清单](evidence-search-preexperiment-20260908-n4-v1/plan.json) | 5318 | `119c21080fa67df66bdb7e05264ef7c730a4fece92ef5f6039a442d8ea85d11d` |
| [冻结记录](evidence-search-preexperiment-20260908-n4-v1/frozen.json) | 48300 | `bc03e6b2e37287d4a6de741eefaf992b721dc5c000e65e90fec7ebd508fdd063` |
| [旧指数研究](research-06.md) | 36738 | `955e25954a1a305d2b4aed42ea9de565a48164eb2785d92a9a686c0fd8fe43dc` |

本轮重新核验以上输入、18份候选记录与result中对应项一致、10个唯一原件SHA/长度、R2旧原件相等性及本报告本地链接。没有重新核验搜索API的8份原始响应字节（result注明它们保存在隔离runtime CAS）；搜索状态统计明确来自已有执行记录，不能把本报告的10份官方响应体SHA当8份搜索响应SHA。完整请求账本/费用/共享预算合规由主代理执行归档核对，本报告不替代该审查。

唯一交付路径 `.scratch/pring-data-acquisition-repair/search-preexperiment-document-review.md`；最终bytes/SHA在交付消息中提供。本文没有伪造官方原件、覆盖已有未知状态或授予任何certification。
