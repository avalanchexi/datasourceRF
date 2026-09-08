# Tavily / Exa 请求与原文层预实验设计

设计日期：2026-09-08，Asia/Shanghai。读取时 HEAD 为 `087b9a8250b11d3f72cde093c445baa61c755996`；本文绑定文末实际输入指纹，不替代主代理正在进行的代码验收。唯一交付为本 Markdown；本轮搜索、下载、秘密读取、应用执行、生产数据库访问和认证操作均为 0。

本设计固定 **4 个现存、跨家族的真实来源缺口**，进行 Tavily / Exa 双臂、每臂 4 个查询的请求与原文层预实验。它是目的抽样，偏向此前较难取得的官方材料，**N=4 不代表全部指标、全部缺口或供应商总体表现**。本轮 Exa 是配对臂，不报告生产串行降级的条件补缺率。不触发模型资格检查、来源声明入库、候选创建、投影或模型激活；模型可用补齐率、模型需求总体覆盖率和实际模型采纳率均为 **N/A：本轮未评估**。不能据此关闭[票20](issues/20-retrieval-paired-benchmark.md#L8)或降低其完整验收条件。

## 1. 固定范围与身份

- `experiment_id = search-preexperiment-20260908-n4-v1`；臂标识分别为该 ID 加 `/tavily`、`/exa`。
- 所有样本的 `target_business_date = 2026-08-28`，研究参照上界 `target_as_of = 2026-08-28T23:59:59.999999+08:00`。该上界定义所研究的目标，不是下载时钟，不表示已经执行 PUBLIC 查询或证明当时可知。
- `model_version_id = null`，`model_evaluation = not_evaluated`。本轮没有冒充可用完整候选。以[当前目录源码](../../src/pring_cycle/catalog.py#L226)的真实 metric_id、源身份及维度语义作为研究定位，并绑定源码指纹；不继承旧 v3 的认证标签，不创建生产 `gap_id`，不把下述研究 `sample_id` 当生产完整缺口身份。
- 4 项均为 P1，跨融资、债券指数、商品仓单、准备金事件家族。前三项 period 是目标业务日；RRR period 是真实待补的 **2025-05**，生效日是 **2025-05-15**，属于目标研究的前置事件证据。不得改成“2026-08-28 当日发生降准”，也不把前置事件样本通过解释成当日政策状态或 120 日事件全集通过。
- 查询不含旧供应商数值答案，执行后不改写关键词、日期、scope 或样本，不用搜索先成功的样本替换失败样本。每个臂使用完全相同的四条 UTF-8 查询正文。

| sample_id | metric_id / period | 研究定位与仍缺事实 | 现有缺口证据 |
|---|---|---|---|
| `bse-margin-20260828` | `CN_MARGIN_BALANCE` / `2026-08-28` | 正式指标的 `{measure: financing_balance, scope: SSE+SZSE+BSE}` 所缺 **BSE 组成证据**；本轮查北交所市场融资余额原值、单位、日期。`source_component.exchange_id=BSE` 是研究过滤条件，不把正式 scope 改成 BSE。 | [官方值仍未取得](margin-bse-followup.md#L5)、[字段及对照边界](margin-bse-followup.md#L41)、[浏览器无样本](margin-bse-browser-followup.md#L36)。真实汇总 scope 见[目录成员](../../src/pring_cycle/metric_contracts.py#L48)。 |
| `cny030-close-20260828` | `CN_BOND_FULL_PRICE_CNY030` / `2026-08-28` | `source_code=000012CNY030.CSI`；官方完整身份 `000012CNY030`，国债指数（全）/ Government Bond Index (Full)，缺目标日收盘点位与显示精度。`.CSI` 是交付方后缀。 | [最新仍无官方点位](cny030-official-next-boundary.md#L3)、[旧日线为空、导出仅表头](cny030-official-next-boundary.md#L15)、[最小官方锚点](cny030-official-next-boundary.md#L58)。 |
| `pp-warrants-20260828` | `CN_FUTURES_WARRANTS` / `2026-08-28` | 研究子集 `symbol=PP, exchange=DCE, measure=registered_receipts`；warehouse 或总计范围必须由原表明确。本轮找可对照的当日注册仓单原表和单位，不研究 PP 行情、连续合约或商品篮子。 | [PP 原件仍未取得](research-pp-followup.md#L5)、[目标仓单所缺字段](research-pp-followup.md#L21)。正式四维身份见[目录](../../src/pring_cycle/catalog.py#L598)。 |
| `rrr-pbc-notice-20250515` | `CN_RRR_EVENT` / `2025-05` | 官方 PBC 原始通知，事件日 `2025-05-15`，`measure=rrr_change`；需要区分排除已执行 5% 的金融机构与汽车金融/金融租赁公司范围。不是逐日持续利率，不要求每个未来事件都具有这两个 scope。 | [已得 CSRC/吉林，但 PBC 原通知仍缺](rrr-original-notices-followup.md#L3)、[现有域名边界](rrr-original-notices-followup.md#L34)、[未解决原通知及阶段性期限](rrr-original-notices-followup.md#L51)。 |

## 2. 机器可读的固定查询与候选域名

下面 JSON 是本设计唯一查询清单；执行脚本应保存实际使用清单及其 SHA256，与本文绑定。四条查询分别执行一次 Tavily 和一次 Exa。域名按解析后的 hostname **精确匹配**，不使用字符串包含判断；仅允许 HTTPS、无 URL 用户信息、默认端口。查询中的 `site:` 是两供应商共同的查询文本，不假设供应商必然严格执行它，因此下载前仍检查 allowlist。

```json
{
  "experiment_id": "search-preexperiment-20260908-n4-v1",
  "target_business_date": "2026-08-28",
  "target_as_of": "2026-08-28T23:59:59.999999+08:00",
  "model_version_id": null,
  "model_evaluation": "not_evaluated",
  "samples": [
    {
      "sample_id": "bse-margin-20260828",
      "metric_id": "CN_MARGIN_BALANCE",
      "period": "2026-08-28",
      "query": "site:bse.cn 2026-08-28 融资融券 融资余额",
      "allowed_hosts": ["www.bse.cn"],
      "source_component": {"exchange_id": "BSE", "measure": "financing_balance"}
    },
    {
      "sample_id": "cny030-close-20260828",
      "metric_id": "CN_BOND_FULL_PRICE_CNY030",
      "period": "2026-08-28",
      "query": "site:csindex.com.cn 000012CNY030 2026-08-28 国债指数 全价",
      "allowed_hosts": ["www.csindex.com.cn", "oss-ch.csindex.com.cn"],
      "source_component": {"official_code": "000012CNY030", "measure": "close"}
    },
    {
      "sample_id": "pp-warrants-20260828",
      "metric_id": "CN_FUTURES_WARRANTS",
      "period": "2026-08-28",
      "query": "site:dce.com.cn 2026-08-28 聚丙烯 PP 仓单日报",
      "allowed_hosts": ["www.dce.com.cn"],
      "source_component": {"symbol": "PP", "exchange": "DCE", "measure": "registered_receipts"}
    },
    {
      "sample_id": "rrr-pbc-notice-20250515",
      "metric_id": "CN_RRR_EVENT",
      "period": "2025-05",
      "query": "site:pbc.gov.cn 2025年5月15日 下调 金融机构 存款准备金率 汽车金融 金融租赁",
      "allowed_hosts": ["www.pbc.gov.cn"],
      "source_component": {"effective_date": "2025-05-15", "measure": "rrr_change"}
    }
  ]
}
```

域名依据为既有官方记录中的[北交所页面](https://www.bse.cn/disclosure/rzrq_trans_list.html)、[CSI 派生身份入口](https://www.csindex.com.cn/csindex-home/perf/get-derivative-index?indexCode=000012)、[CSI 已证官方静态文件宿主](research-06.md#L47)、[DCE 官方资料宿主](research-pp-followup.md#L13)、[PBC 已有事件原件宿主](remaining-p1-source-consumers.md#L125)。此处引用不是本次下载。未列域名的结果保留为 `outside_frozen_host_allowlist`，不自动扩大名单；CSRC 是有效官方实录宿主，但不满足本轮专找 PBC 原通知的子问题，并不因此被贬为非官方。

## 3. 四项原文有效判据

公共必要条件：实际获取且保存完整响应字节、请求 URL、状态、开始/接收时间、内容类型、SHA256、长度；响应可正常解释为官方正文/表格/附件，不是搜索摘要、空页、首页菜单、挑战页、登录提示或截断体。页头显示日期、正文统计/生效日期和本次取得时间分别记录；未知首发时刻保持未知。**缺首发时分秒不自动否定数值锚点，但不因此授予历史 PUBLIC。** 若正文完全没有可绑定的统计期或事件期，则不能判本样本有效。

| 样本 | 判 `valid_source_anchor=true` 所需原文 | 不通过及部分证据的处理 |
|---|---|---|
| BSE | 官方市场总量记录明确绑定 **2026-08-28**，能定位“融资余额”的字面数值及单位/单位栏，明确属于北交所而非其他市场。保留原精度；如需表示换算，只用原单位和十进制算术。 | 融资融券总余额、融券余量、融资买入额、个股明细合计、全市场减沪深残差不能替代融资余额。旧 TuShare 的 8,332,418,348 元仅为已存对照值，不作为搜索答案或强制通过数值。融资买入额若同页出现可保存，但不增加本实验分母；票05仍须另验它。 |
| CNY030 | 同一官方发布物明确给出完整 CNY030 身份、**2026-08-28**、收盘点位及实际小数表示；若使用另一交付代码，必须在本轮已保存或既有真实官方材料中有确定映射。单位为指数点，原件表头/说明足以识别。 | 母指数 `000012`、净价 H00012、利息 N00012、其他国债指数、仅身份表/方法/空日线或表头 XLSX 均不通过。不得以旧规范化 111.2608 为独立官方期望。映射还需新页面而本轮未保存时记 `identity_mapping_unresolved`，不猜代码。 |
| PP 仓单 | DCE 当日原表/文件明确绑定 **2026-08-28、PP/聚丙烯**，至少一个可定位的注册仓单当值、原单位，以及其仓库、厂库或总计范围；原表明确列出当值与前值/变化时分别标注。此处只验证该范围的来源锚点。 | 交割库存、仓库容量、仓单登记操作手册、旧年月报、其他品种、仅前值/变化均不能替代当值。吨、手、张等单位按源值保留，缺单位不默认为吨，不能跨单位汇总。明示 0 可以通过数值判据，空白/破折号不补 0。一个仓库/总计样本通过不代表全品种、多仓库集合或历史覆盖完成。 |
| RRR 原通知 | PBC 官方原始通知或原始公告正文明确为该 **2025-05-15 生效措施**，可辨两类范围及下调幅度：广范围 -0.5 个百分点（排除已执行 5% 的机构）；汽车金融/金融租赁公司 -5 个百分点。原文的发布日/时刻按实际栏位记录，原始通知身份须能区别事后回顾。 | 2025 年 11 月大事记、CSRC 实录、吉林转载是既有相关证据，不能当新得 PBC 原通知。只有某一范围、未明示生效日或仅讨论政策意向时保存相关段落并记 `partial_event_evidence`，不计完整本样本锚点。若原文与既有幅度不同，记录 `conflicting_event_evidence`，保留双方，不为吻合期望改值。调整后比例和阶段性截止日只有原文明示才记录；未写不猜，不把 -0.5 与 -5 相加或当持续利率。 |

统一结果至少分为：`valid_source_anchor`、`partial_source_evidence`、`identity_or_period_mismatch`、`missing_field_or_unit`、`conflicting_evidence`、`transport_failed`、`challenge_or_login`、`empty_or_truncated`、`outside_frozen_host_allowlist`、`known_prior_candidate`、`not_evaluated`。HTTP 200 和字段中出现关键词都不能直接生成有效锚点。

如正文/表格必须依赖 PDF、XLSX 等当前执行器未支持的解析方式，先保存原件并记 `content_review_pending`，可在本轮只读人工核验后补结果；不得为了凑结果用不支持的解析器强行通过。交给确定性家族解析器的片段继续最多 1,600 字符；完整原件另存。独立人工定位若超出该片段，应明确“人工原文核验”，不冒充生产解析通过。

## 4. 请求顺序、共享预算与停止条件

1. 执行前锁定本文 SHA、清单 SHA、脚本 SHA、实际 UTC 开始时间、两个臂 ID，以及主代理的脱敏凭据/预算检查回执。主代理已告知默认 runtime 中 `TAVILY_API_KEY` 与 `EXA_API_KEY` 均配置、旧生产库当天保守搜索消费为 0；这是**主代理的预检输入**，本设计没有读取秘密或重查生产库。预检不能冒充后来执行时额度仍未变化的保证。
2. 固定搜索顺序为 `BSE:Tavily→Exa`、`CNY030:Exa→Tavily`、`PP:Tavily→Exa`、`RRR:Exa→Tavily`，总计计划 8 个逻辑搜索/8 个物理 POST。两臂相互独立，不用前一臂发现的 URL 改写后一臂查询。顺序交替只降低明显顺序偏差，不宣称已消除时点/搜索引擎差异。
3. 复用真实 `search_discovery_adapter` 的请求契约：Tavily basic、`max_results=3`、关闭 answer/raw-content/images；Exa auto、`numResults=3`。两个渠道每样本各 1 次，**本实验自动搜索重试 0、关键词改写 0、AI 搜索 0**。真实超时/失败同样消耗已发请求，保留分母；不靠再建 run 恢复次数。[当前请求契约](../../src/pring_cycle/search_discovery.py#L189)
4. 先完成或如实停止全部计划搜索并冻结两臂候选表，再做官方原文读取。每个样本每臂最多保留供应商顺序的前 3 个有效 HTTPS 候选；拒绝项也留理由。摘要合计上限 1,800 字符，不能因为原文失败继续翻第 4 个候选。计划候选槽位最多 24，不等于一定会有 24 个 URL 或 GET。
5. 对候选只作公开 GET；最多 **24 个唯一候选 URL、每 URL 1 次**，禁止隐式重定向及自动重试，不追候选页的新链接、不猜 API/参数/附件地址、不启浏览器/账号/客户端。3xx 保存状态/Location后停止该 URL，不跟随。GET 超时与体积上限须在脚本执行前记录；建议采用现有有界研究惯例的 15 秒、4,000,001 字节拒绝哨兵，超过 4,000,000 字节只保留有界前缀并标截断，不计有效原文。
6. 已知原件与已证失败的**同一 URL**先离线识别，记 `known_prior_candidate` 并引用既有回执，本轮不重试，也不算新原文取得。参照[BSE 已失败路径](margin-bse-followup.md#L11)、[CNY030 已失败接口/文件](cny030-official-next-boundary.md#L19)、[PP 旧失败线索](research-pp-followup.md#L9)和[RRR 已有三份文档](rrr-original-notices-followup.md#L11)。不能只因同一域下曾失败就拒绝一个真正新 URL。
7. 两臂命中同一个新 URL 时，只进行一次物理 GET，第二引用记 `shared_url_reuse` 并关联同一下载回执。这是本轮预先确定的原文去重规则，不把复用算成第二次下载。候选发现按两臂各自响应统计；原文事实共用同次取得，故原文层不被宣称为两个独立网络可用性实验。没有任何一臂的发现/下载生成 SourceClaim 或修改另一臂初始缺口。
8. 预算同时受原有事件/运行/日限制约束：事件每渠道 1；运行 Tavily/Exa 8/4；全日 16/8。此实验计划 4/4，用**同一共享总账/预留**计入两臂及并发生产的当天总消费，不能各建隔离空账获得两份日额度。原文 GET 与搜索 POST分别计数，不拿 GET 当额外搜索预算，也不得利用 GET 切换搜索提供商接口。保留负缓存、402/403/429及未知完成状态的实际拒绝；预检失败、额度不足、中断或其他门禁出现时暂停剩余请求并保留未执行槽位，不补足次数或移到次日伪装同批完成。[预算与缓存原规格](spec.md#L112)

这是一项研究执行入口，不调用 `run-submit → Worker` 绕 active-model 检查，不修改旧 v3 guard；也不调用 `verify_search_candidates` 的入库/选择路径。单独调用搜索适配器时必须保留真实原始响应与请求回执，不能走没有 `paths/run_id` 却只留下 candidate URL 的无持久分支。主代理负责使有界脚本的研究记录/预算实现与这一边界一致；本设计不创建新的应用命令或模型对象。

## 5. 分母与交付结果契约

| 指标 | 本轮分母 / 分子 | 必须同时报告 |
|---|---|---|
| 搜索 HTTP 成功率（分臂） | 实际发出的搜索物理 POST / 其中 2xx 次数 | 计划 4、实际发出、未执行、未知完成、失败类别分别列；200但无候选仍是 HTTP 成功，不是原文成功。 |
| 候选发现率（分臂） | 实际发出搜索的唯一 sample 数 / 其中至少一个返回候选的 sample 数 | 保留全部前3候选、官方 allowlist 后数量、重复/旧候选数量；固定顺序不按结果挑选。 |
| 官方候选率（分臂） | 已保存候选 URL 数 / 其中符合冻结 host allowlist 数 | 它只评价身份筛选，不是数据有效。 |
| 原文 GET 成功率（全实验；按发现臂提供归因表） | 实际唯一 URL GET 数 / 其中完整、正常可读官方响应数 | shared_url_reuse、既有 URL 复用不增加物理 GET 分母；错误页/挑战/截断不计成功原文。另列 HTTP 2xx/GET，避免混义。 |
| 有效来源锚点率（分臂） | 实际搜索处理的唯一 sample 数 / 其中由该臂本次发现、并经本轮新原文核验满足第3节判据的 sample 数 | 每样本至多1；同 URL 共用回执可分别归因其发现臂，但总唯一样本/原件去重另列。既有可用材料的重新命中不计“本轮新补齐”。原文待人工复核时显示已通过/待核/拒绝，不把未核者计成功。 |
| 字段可核验情况 | 每份已读原文的应核字段、字面值、单位/期次、定位、通过/冲突/未知 | 不聚合不同家族标量为一个假定统一字段成功率；如报告数值必须给字段明细分母。 |
| 模型可用缺口补齐、模型需求总体覆盖、实际模型采纳 | **N/A：本轮未评估** | 不是“无搜索样本”，不是 0%，不是 certified/selected；本轮设计禁止进入这些环节。 |

上表“分母 / 分子”的顺序只是列出组成，报告百分率一律计算 **分子 ÷ 分母**。所有零分母用 N/A，保留原因；有请求而全部拒绝的请求/锚点层应为 0/n。耗时来自真实开始/结束时钟；Tavily credits、Exa `costDollars` 按实际返回依据分别记录，`billed_cost` 无账单则未知，不以 4 次请求推算实际金额。

执行交付应包含：冻结清单和本文指纹；8 个计划搜索槽位与各自真实状态；逐次搜索响应和脱敏回执；候选顺序/筛除原因；原文 GET/复用关联、精确原件和哈希；四样本逐条判据结果/字面定位/时间精度；分臂统计及全实验去重对照；默认只读复核。搜索原响应保留期沿用 30 日，长期审计记录不能把已过期指纹称为可读正文。[原件保留和分层统计](spec.md#L117)

搜索索引到新 URL、正常下载、找到字面值、通过字段检查与历史首次公开分别是不同事实。即便四项都找到锚点，剩余 120 日覆盖、正式来源审查及新候选资格仍由原票验收；未找到也不能证明数据不存在、必须采购或用户没有许可。

## 6. 本设计输入指纹

本表绑定设计实际读取的稳定输入；主代理后续实现变更不应倒改本文快照。本文没有内嵌自身哈希，最终 bytes/SHA256 在交付消息中给出。

| 输入 | bytes | SHA256 |
|---|---:|---|
| [spec.md](spec.md) | 27762 | `f5c32c407f216841b2afed0aaab3863868bdc394d9057207d25dbc9e9a561cc4` |
| [票20](issues/20-retrieval-paired-benchmark.md) | 2707 | `871e15c9ff7b5988f398de6b188d5cf4db159953bcca3c44dae4377aef99d32c` |
| [BSE HTTP研究](margin-bse-followup.md) | 9657 | `4b6690e908b3a92d71f502e94011f88b2bf634a423dd573cd9ddd9dfe5c58b62` |
| [BSE浏览器研究](margin-bse-browser-followup.md) | 7517 | `930f82d984c0008f1a410cd6629f8a21486c4cc1a556a2a3f2bbd785183db6a4` |
| [CNY030最新研究](cny030-official-next-boundary.md) | 14722 | `cd983bcbdc398ad03d41a5f8c3190d01b5d40c538d8cf8137263d14377890f6f` |
| [PP增量研究](research-pp-followup.md) | 4356 | `750b63e4b7e163c8b94660f687c1e13ba3aba3fd3700ee063744a72e2ad8d7bc` |
| [RRR原通知研究](rrr-original-notices-followup.md) | 9049 | `b0128252a6b8bedf89cc607368a1370f39c6daacd74b62dbaaffa43480c74c22` |
| [catalog.py](../../src/pring_cycle/catalog.py) | 25978 | `fe8dd4e21d563448c31af535f3886fc7fb053133de6346d5d9c4a627a91e7c5c` |
| [metric_contracts.py](../../src/pring_cycle/metric_contracts.py) | 9849 | `b94d7b0e1da8ca282c53a12779b5bf738d8bf380950189f6569453d8ce598f66` |
| [search_discovery.py](../../src/pring_cycle/search_discovery.py) | 12027 | `402f2cd11b9e0ef4298044c5605572f526c01453361fafd242e438f94d2feefa` |
