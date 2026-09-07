# 票13增量：2026-08-28 DR007官方值已取得，真实公开时间仍未知

研究日期2026-09-07；按research独立有界补证，使用Windows `C:\Python313\python.exe -B`，只写本报告及`evidence-13-dr007-followup/`。没有WSL、账户/密钥、POST、数据库、应用运行、认证或模型变更。先读[研究13](research-13.md)及[票13](issues/13-remaining-p1-evidence.md)，未重复旧失败路径。

**本次补齐官方目标日值：`DR007`、2026-08-28、`wghtdAvgRepoRate=1.3859`、单位%。它与旧TuShare `repo_daily/weight`样本1/1相符。真实首次公开时间没有补齐，`release_at/public_available_at`继续为null。** 这解除的是同期官方数值样本缺件，不是票13、来源认证或120日重放通过。

## 1. 已尝试路径与本次新入口

旧`evidence-13/receipts.json`共15次GET，其中10次与本次排查相关，完整URL、状态、时间和原件在[旧尝试清单](evidence-13-dr007-followup/prior-attempts.json)。相关旧路径如下，均未重复请求：

| 旧路径 | 已有结果与本次处理 |
|---|---|
| `https://www.shibor.org/chinese/bkshibor/` | 超时、无响应原件；不重复，也不把Shibor变成DR007 |
| `https://www.chinamoney.com.cn/chinese/bkfrr/` | 200，FR/FDR定盘说明；不能证明DR007全天加权日值 |
| `https://www.chinamoney.com.cn/chinese/dssjfwgl/` | 200，CFETS数据服务/使用说明；复用旧结论 |
| `/english/bmkshb/`、`/chinese/bkshibor/` | 200，Shibor说明；其11:00不能给DR007定时 |
| `/r/cms/chinese/chinamoney/html/shibor/shibor-his-cn.html` | 200，Shibor历史片段；不是DR007 |
| `/r/cms/chinese/chinamoney/assets/js/cm-basic.js` | 200，已保存URL配置；本次按SHA复用，不重复下载 |
| `/ags/ms/cm-u-bk-shibor/ShiborHis?...2026-08-28...` | 200，旧Shibor日值；不替代DR007 |
| TuShare `document/2?doc_id=256` | 200，回购字段文档；旧交付取`DR007.IB/weight` |
| PBC `2023112817393565251.pdf` | 200，DR007语义锚点；无目标日精确值 |

官方搜索发现[质押式回购每日速递入口](https://www.chinamoney.com.cn/chinese/mtdexdaily/?tab=4)。新取得的[入口原件](evidence-13-dr007-followup/e678ff47ec2de3537b05f631b4917c3ba0e53a9eac29f566865e998c40bd3f6a)明确引用`/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html`；新[日报片段](evidence-13-dr007-followup/b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96)给出字段、查询与导出地址。

该片段的历史查询使用`BK_URL + cm-u-dlrp/PrDlyBltn`，存款类机构表参数为`lang=en`、`indexType=markInterBankVOList`、`searchDate`和`publishedTime`；官方页面自身用POST读取。本次受GET边界约束，将同一已公开只读查询参数作为GET，接口实际接受并返回目标日JSON。没有使用凭证、挑战处理、签名生成或访问控制绕过。导出Excel是页面明确的GET链接；本次该独立导出端点返回403空体，查询端点随后返回200，不能把403泛化为整个来源必须登录或付费。

## 2. 四次GET及精确原件

所有新URL均不在指定旧GET清单中。达到4次上限后停止，没有重试、扩大日期或下载其他指标。请求起止、HTTP头及完整URL见[逐次回执](evidence-13-dr007-followup/receipts.json)。

| 次数 | 官方GET | 结果 | 字节数 | SHA256 |
|---|---|---|---:|---|
| 1 | `https://www.chinamoney.com.cn/chinese/mtdexdaily/?tab=4` | 200，官方入口 | 18064 | `e678ff47ec2de3537b05f631b4917c3ba0e53a9eac29f566865e998c40bd3f6a` |
| 2 | `https://www.chinamoney.com.cn/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html` | 200，表头及查询协议 | 10948 | `b3a07aac8d979104bd53b5c6f7ad0bd50dfe78e26f723307c644bdb130cb6c96` |
| 3 | `https://www.chinamoney.com.cn/dqs/rest/cm-u-dlrp/PrDlyBltnExcel?lang=cn&searchDate=2026-08-28&publishedTime=2200` | 403，空响应；非Excel、非行情证据 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 4 | `https://www.chinamoney.com.cn/ags/ms/cm-u-dlrp/PrDlyBltn?lang=en&indexType=markInterBankVOList&searchDate=2026-08-28&publishedTime=2200` | 200，有效目标日JSON | 1425 | `d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d` |

共4份响应体制品30,437字节，其中1份为403的零字节体。它的SHA只能校验“确实保存了空响应”，不能当有效原文。HTTP成功3/4；真正包含目标日值的响应1份。文档成功与数值补齐分别统计，不将75%请求成功率写成认证命中率。本次web搜索1次、2个查询，仅作官方入口发现，另记[发现说明](evidence-13-dr007-followup/web-discovery.json)；未调用Tavily/Exa。

## 3. 官方值、单位、期次和旧交付对照

[官方JSON](https://www.chinamoney.com.cn/ags/ms/cm-u-dlrp/PrDlyBltn?lang=en&indexType=markInterBankVOList&searchDate=2026-08-28&publishedTime=2200)的`head.rep_code=200`，`data.lastDate=2026-08-28`，返回6个DR期限品种，仅一行`instrmntCd=DR007`。不是由请求URL中的日期猜测响应期次。完整原文在[目标日JSON字节](evidence-13-dr007-followup/d0a4ce808d3e022625c97a22b774d0387b2108f56f584c6b626c7effc9a0978d)。

| 官方字段 | 原值 | 官方片段表头及含义 |
|---|---:|---|
| `instrmntCd` | DR007 | 品种；须精确匹配，不能只找字符串“007” |
| `wghtdAvgRepoRate` | **1.3859** | **加权利率(%)，本次目标字段** |
| `openRepoRate` | 1.3700 | 开盘利率(%)；非全天加权 |
| `clsngRepoRate` | 1.3806 | 收盘利率(%)；非全天加权 |
| `wghtdAvgRepoDebtRate` | 1.3859 | 加权平均利率(利率债)(%)；本行相等不能证明所有产品/历史字段可互换 |
| `avgPrd` | 5.76 | 平均回购期限(天)；不是将DR007身份改为5.76天报价 |
| `dlNo` | 275 | 成交笔数(笔) |
| `trdVol` | 1420.8644 | 成交量(亿元)；与TuShare金额字段不可不经单位核对直接比较 |

表头字段名和单位来自[官方HTML片段](https://www.chinamoney.com.cn/r/cms/chinese/chinamoney/html/currency/daily-pledged-repo.html)。PBC原有[语义原件](evidence-13/60ad3e29e905a9f405e70733cb1ddeffa41fdcc6b9dcbe962e462b2422a2d455)已将DR007定义为银行间存款类机构以利率债质押的7天加权平均回购利率；本次新增JSON补齐精确目标日值，未重新抓取或篡改语义PDF。[PBC报告](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4883187/1f14dbe28ec4408cbf45cee06f86808a/2023112817393565251.pdf)

[旧只读诊断](evidence-13/readonly-checks.json)中的`CN_DR007`，期次08-28、单位`percent`、provider=tushare、`source_reference=tushare:repo_daily:weight:2026-08-28`，值1.3859。使用十进制与本次官方字段比较相等，**1个目标字段、1次匹配**。这是一份旧仓库读取快照与新官方原件的对照；没有在本次读取数据库，也没有替旧认证标签背书。

若仍使用已证08-28七天政策利率1.4%，独立算术为`(1.3859-1.4)*100=-1.41bp`。若误用收盘字段则得到-1.94bp，可作为后续公共任务边界的确定拒绝反例。该算术不解决父项可见时间或来源认证，不能直接宣称正式Pring解释已通过。期次、全部字段、旧声明快照及比较结果见[来源检查](evidence-13-dr007-followup/source-inspection.json)。

## 4. 真实公开时间仍然缺什么

| 已见字段/文本 | 能证明 | 不能证明 |
|---|---|---|
| `data.lastDate=2026-08-28` | 观测统计日 | 当天的实际首次公开时刻 |
| `head.tstext=2026-09-07 17:49:01`、`head.ts` | 本次响应生成信息；与本次HTTP/取得时钟相符 | 8月28日历史发布或修订时间 |
| `PR_PUBLISHED_TIME=2200` | 旧官方JS给日报查询使用的配置值；本次接口接受该参数 | 目标日确实22:00首次发布，或22:00是无延迟的历史固定日程 |
| HTML/JS的HTTP Last-Modified | 当前保存的网页/配置版本元数据 | 每条历史利率的真实发布时间 |
| 第4次响应收到2026-09-07T09:49:02.036536+00:00 | 本次研究已取得这份官方响应 | 8月28日生产SYSTEM已知；后来生产导入也不能复用它倒填首次校验时间 |
| 旧声明11:00 | 旧数据已写入的时间内容 | DR007的官方实际发布依据；Shibor的11:00不适用 |
| 历史发行人合约17:00条款 | 该合约约定的基准选择方式 | 2026-08-28官方原始发布记录 |

本次JSON没有逐行发布日期、发布时刻或历史修订vintage。固定15:30没有依据；11:00、17:00、22:00也不能因某处出现而自动填入。**`release_at`和`public_available_at`均保持null。** 日期字段缺的是“可靠发布日期”，不是仅缺小时；不能把统计日当发布日期后套次日00:00保守规则。

已知当前公开响应在研究取得时存在，只能支撑本次快照的取得事实。未来正式获取/导入须保留自己的真实收到及校验完成记录，按[双点时ADR](../../docs/adr/0006-dual-as-of-and-immutable-evidence-vintages.md)区分PUBLIC与SYSTEM，追加来源声明与版本。旧11:00声明不能原地改写成本次取得时间。

## 5. 仍需通过的门槛与具体下一步

1. **数值/语义证据进入正式认证材料。** 本报告可支持`DR007.IB/weight`家族的字段、单位、期次、目标日官方值复核；还需正式认证流程核对适用使用边界、原件关联和新不可变目录。本次没有授予认证。
2. **历史公开边界。** 需要能明确关联08-28这条日值的真实发布记录或可靠发布日期/版本说明；若仍无记录，PUBLIC保持未知，不能用取得日志或参数配置补造。
3. **历史交付与重放。** 本次响应`startDate=2026-08-24`、`endDate=2026-09-06`，只查了08-28。它既不证明此前历史不能取得，也不证明此公开接口能覆盖120日。沿用已接受的TuShare历史交付加官方家族抽样策略，不扩大成每个历史日强制第二来源；实际候选矩阵和120中国交易日点时结果仍须验收。[官方抽样ADR](../../docs/adr/0013-tushare-delivery-with-official-sampling.md)
4. **拒绝反例。** 错用R007/FDR007/Shibor、收盘或开盘字段、目标日回退、重复DR007行、缺加权字段、403空体、未知公开时间提前可见时均不能入为有效目标证据。`publishedTime`只是请求参数；后续解析应检查响应统计日与目标一致，不能仅看HTTP200。

本次没有新增业务口径选择，也没有默默替换指标。DR007样本缺值已取得实际进展；发布时间、认证和模型可用性继续明确待验，不能把这些待验记录当通过。

## 6. 交付与独立离线复核

精确新增路径见[交付清单](evidence-13-dr007-followup/delivery-files.txt)，所有原件/报告/脚本等摘要见[校验结果](evidence-13-dr007-followup/delivery-verification.json)。旧研究13 SHA仍为`dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1`；旧报告、原件和校验文档均未写入。

[标准库校验脚本](evidence-13-dr007-followup/verify_delivery.py)从新JSON与HTML重新识别目标日、唯一DR007、字段单位及加权值，重新读取旧声明并十进制比较，验证4次响应体SHA/长度/状态、旧配置和语义PDF、来源检查、全部交付摘要和本地链接。默认只读，无网络、WSL、第三方包、应用导入或DB：

```powershell
C:/Python313/python.exe -B D:/cursor/datasourceRF/.scratch/pring-data-acquisition-repair/evidence-13-dr007-followup/verify_delivery.py
```

成功输出应为`validation=passed`、4次GET、3个200、1个403、30,437字节、官方DR007=1.3859、`public_available_at=null`。该通过只指研究包可复核，不是源认证或模型发布通过。清单列出校验文件自身，校验文件不循环存自身哈希；两个显式写参数仅用于生成本任务交付JSON。
