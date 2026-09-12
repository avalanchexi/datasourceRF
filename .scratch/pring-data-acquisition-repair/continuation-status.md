## 票10软件验收534完成

票10软件切片已通过：[根核验534](verification-amount-acceptance-534.json)绑定321输入/4保护、最终源码与环境、实际终态及独立八文件补丁。530金额家族28项通过，532相关263项通过；531独立HEAD加本票增量203项通过，根类型95/独立92、Ruff/格式及两轴530/533通过。三个测试范围分别留证，不合计为默认全套。全池分子/分母、未知金额、覆盖排重、PUBLIC及原件恢复保持可复核；真实盘后补证、官方差额与来源认证仍开放。市场15项P1已有13项软件路径，下一步11真实月份合约输入→12商品两项；09全市场容量、M3–M6及最终默认全套继续推进，23延期。

# 修复项目当前执行入口

**2026-09-13 implement：M2窗口广度软件切片完成，继续10金额。** [票09](issues/09-breadth-window-metrics.md)两项新增软件条件已通过；37项窗口、263项相关及独立HEAD175项分别全通过，类型92/91、Ruff/格式与两轴498通过，保留一项判断性测试结构建议。[根核验500](verification-window-acceptance-500.json)绑定输入、环境、实际终态及八文件独立补丁，详见[09实施记录](implementation-09-registered-window-breadth.md)。市场15项P1已有12项软件路径；下一项10金额1项、11→12商品2项。[金额研究485](research-10-software-inputs-485.md)及499独立手算提供32.5%合成正例、全池分母与金额覆盖边界。真实历史输入/认证、全市场容量及M3–M6/最终默认全套继续开放，23延期。

**2026-09-09 最新验收：**LPR标准化消费、双点时日历和PUBLIC组件回放软件批已通过[默认全套](verification-context-normalized-full-22.txt)：**1053通过、0失败、3673.23秒**，原主会话95550实际退出码0。[关联回归](verification-context-normalized-targeted-22.txt)376通过、935.66秒；mypy92、Ruff、7文件格式和两轴复核通过，167冻结输入字节未变，90安装Python源最终匹配，4个受保护用户文件未变。[本批检查点](verification-context-normalized/checkpoint.json)绑定源码、终态和日志。下一步按[PMI/CPI消费研究](official-macro-normalized-next-step.md)及[跨统计期回退边界](official-macro-derived-selection-boundary.md)继续公开RED/GREEN；新PMI反例尚未执行。真实来源认证、业务规则、完整候选、120交易日重放、合格AI及真实切换仍未完成，不关闭整个修复项目。

顶部最新记录及其终态证据控制当前进展；下方各阶段快照保留记录时的“当前/正在执行”措辞，不代表那些旧进程现在仍在运行，也不覆盖后续结果。

**等待期间新增边界：**[PMI较早统计期回退](official-macro-derived-selection-boundary.md)明确：只过滤坏的七月父项，仍可能让六月在95天鲜度阈值内生成current派生，首组回归须同时防止跨版本和跨统计期回退。这是有源码依据的待执行反例，尚未修改应用或测试。默认全套95550最新刷新至47%，仍未终态；167冻结输入未变，辅助WSL错误与主测试进展分别留在[辅助记录](verification-context-normalized-helper-check-22.md)。

**本次PP补证：**[官方增量报告](pp-official-followup-20260909.md)完成6个逻辑查询、2次web搜索和1次新官方PDF的GET调用尝试；TLS握手超时，无HTTP响应或新原件。新增2022年历史月表索引不能认证2026目标日报的单位，目标日行情、仓单及历史映射继续缺证。报告9717字节、hash及10个本地引用已根代理独立核对；本轮不进入Tavily/Exa实验分母。

**本次官方增量：**[RRR事件全集补证](rrr-official-completeness-followup-20260909.md)4个逻辑查询、2次web调用，新增合格原件0；固定窗口全集、阶段性续止及前置最近状态继续缺证。报告与15本地引用、两份旧PBC原件已独立核验。2025原始PBC通知此前已找到，不再沿用较早“原通知未找到”的状态；未混入Tavily/Exa实测分母。

**2026-09-09 全套执行中：**当前LPR软件批[376项关联回归](verification-context-normalized-targeted-22.txt)全通过、935.66秒，主会话52702已实际退出0；167输入字节复核无变化，mypy92、Ruff及最终7文件格式检查通过，两轴剩余0。辅助WSL启动错误已由独立Ruff补验消除，不影响前一主回归。现在[默认全套](verification-context-normalized-full-22.txt)运行于主会话95550，尚无最终结果，[运行状态](verification-context-normalized/terminal.json)已登记；不得重启、提前生成检查点或提交。下一宏观入口研究[PMI/CPI消费与派生边界](official-macro-normalized-next-step.md)已根核55引用、两原件及8格字面值，新RED未执行。其他真实来源与模型最终门继续开放。

**2026-09-09 当前验证：**分支main，最近已提交批次仍为`bda795f`。LPR当前软件增量已接检索、上下文及PUBLIC回放的双制品/声明字段核验。上次21通过/2失败已定位为发布日历误将缺PUBLIC的SYSTEM记录判stale，修复后[29项通过](verification-context-normalized-lpr-green-10.txt)；回放坏制品漏报缺口也已公开RED后修复，[13项扩展通过](verification-context-normalized-lpr-replay-green-15.txt)，含后发坏修订不伤旧cutoff且不得回退旧值。新增真实归档原文与取得边界[7项通过](verification-context-normalized-lpr-positive-green-16.txt)。Spec复核发现的事件ID排序问题已修，[22项通过](verification-context-normalized-lpr-calendar-green-19.txt)，两轴剩余0。mypy92、Ruff及90安装源核对通过，167个输入已冻结；[9个关联测试文件](verification-context-normalized-targeted-22.txt)正在执行，主会话52702尚未验收终态。当前批全套未执行、未提交；其他家族、真实来源认证、完整候选、120日回放、合格AI与切换仍未完成。下方14项阶段及原失败记录仅保留各自历史，不覆盖当前代码。

**2026-09-09 正在续作：**前批已保存本地提交 `bda795f`（1031全套通过）。现从该提交继续[上下文标准化消费核验](implementation-19-context-normalized-consumption.md)，已复现并修复LPR制品损坏、哈希自洽但利率错配仍被检索选中，以及上下文继续标current的问题；[14项回归](verification-context-normalized-lpr-green-04.txt)通过、10.30秒、退出码0，mypy91和90安装源指纹通过，[两轴阶段复核](verification-context-normalized-review-01.md)新增问题各0。失败诊断引用继续可追溯，实际采用以model_input_observation_version_ids验收。选中声明字段/时间、PUBLIC回放、其他家族和派生边界仍开放，本批未提交；前批全绿不代替当前新代码验收。

**2026-09-09 当前进展：**[核心/仓单标准化消费](implementation-19-normalized-consumption.md)及[SQLite连接生命周期修复](implementation-database-connections.md)完成本批软件验收。修复后[默认全套](verification-connection-full-01.txt)为**1031通过、0失败、2975.70秒**，原主会话37371已正常退出，退出码0；[扩大关联回归](verification-connection-targeted-01.txt)257通过、625.54秒。应用及两个测试文件mypy92、Ruff/格式22文件、两轴复审0项；运行前后90安装Python源匹配，22个测试输入字节未变。[本批检查点](verification-connection/checkpoint.json)绑定源码、终态及完整日志，旧1022通过/6失败/1错误的原始记录保留。[CNY030增量研究](cny030-official-followup-20260909.md)完成4个逻辑搜索，新增目标实值0，正式认证缺口保持。下一步继续LPR/常规宏观/银行间标准化消费与RRR多收据核验，以及真实来源、模型及报告前置；实际完整候选、120中国交易日、合格AI及切换均未完成。

**2026-09-09 本批原全套记录：**从已提交`3e1b7d3`继续的[核心与仓单标准化制品消费核验](implementation-19-normalized-consumption.md)完成公开RED/GREEN、21个新增用例、mypy91、Ruff/格式8文件和90安装Python源核对；两轴复审剩余0。原项目默认全套结果为**1022通过、6失败、1错误，2028.77秒**，见[完整失败日志](verification-normalized-full-01.txt)。失败涉及检索台账及仓单上下文，异常为文件句柄耗尽与SQLite无法打开数据库；该轮时连接释放根因尚待验证，后续修复见上方最新记录。标准化丢失/损坏、哈希正确但语义不符、多关联、显式目录及保守时间降级都按各自证据记录；LPR/常规宏观/银行间与RRR多收据边界继续开放。

**2026-09-09 更新：**从`6662bc2`继续的[上下文逐日快照与输入版本绑定](implementation-21-context-replay.md)已完成**432项关联回归、0失败、611.08秒**，包含19项新增用例；mypy92、Ruff/格式9文件通过，90安装Python源匹配，Spec/Standards剩余均0。[本批检查点](verification-context/checkpoint.json)绑定源码及日志。LPR同值新版本、较早仓单版本、必需字段/成员/范围、旧0019/0020迁移、逐日PUBLIC、失败保留及退出仓库不混入当前输入均已验证。下文旧“尚未执行上下文RED”只反映前一批历史状态。

**仍开放：**normalized消费完整性、新目录active Worker完整纵向、融资注册来源合同、真实来源与规则补证；实际完整候选/120中国交易日/合格AI/切换均未完成。业务规则与网络待答条件保持，不重复提问、不静默替换。

**下一软件入口：**[标准化制品消费边界](normalized-consumption-boundary.md)及[五类源码映射](normalized-consumption-source-map.md)，先经已有注册来源采集/选值公开入口复现，不以单独read_content函数会报错冒充实际模型已校验。RRR已有raw/normalized重解析链，其他家族需按实际调用路径分别核验；本研究未运行新的反例。

## 前批记录

**2026-09-09 更新：**阶段仍为 implement + research，本批从已提交的`0c33710`继续。[PUBLIC候选字段及保存查询](implementation-21-candidate-replay.md)已完成**342项关联回归、0失败、550.74秒**，包含34项新增候选用例；mypy89、Ruff/格式9文件及88安装源码核对通过，两轴复审均0。新旧规则天数、逐日差异、校准/回放明细CLI/API、证据版本失配、旧0019迁移及缺末日失败记录已接通。见[检查点](verification-candidate/checkpoint.json)。真实完整候选、120日验收、合格AI报告及切换仍未完成。

**下一软件切片：**[上下文逐日快照与输入版本绑定](context-replay-snapshot-boundary.md)静态定位显示上下文仍只保存差异数量，先通过公开反例核验是否会漏掉计数不变的P1版本变动；尚未执行其RED。normalized消费完整性和新目录active Worker完整纵向继续开放。业务规则、官方证据、真实检索模型资格和报告网络条件仍按下文处理。

**上一已提交的软件批：**`0c33710`的[三核心消费原件核验](implementation-19-core-original-consumption.md)修复选值/回放使用丢失或损坏原件的问题，已接共享Worker校验；328关联回归通过，530.37秒。其[候选字段研究](core-candidate-replay-boundary.md)已由上方本批实现推进，旧研究与旧日志保留历史状态，不以它们覆盖最新结果。

**实际检索与报告：**四困难缺口预实验的原文层补齐为 Tavily 1/4、Exa 0/4，模型可用率仍 N/A；不能外推总体命中率。9月9日[网络复查](evidence-18-connectivity-20260909/review.md)仍超时，真实合格 AI 输出为0。下文为各历史批次原记录，不能把旧“下一步”或旧全套通过当作当前整体完成。

最新搜索增量：新目录查询、缺口绑定及旧预算/缓存解析已修，213 项关联回归、6 项新增用例、mypy85/Ruff/84源码指纹和双轴复审通过，见[搜索检查点](verification-search-catalog/checkpoint.json)，提交7a7e384。真实四缺口配对预实验已完成8次搜索和12次GET，原文目标补齐Tavily1/4、Exa0/4，模型资格未评估；见[实测报告](search-preexperiment-report.md)。新取得PBC原通知两scope及页头时间已独立复核。

运行条件已恢复：C盘已观测到约12.8GB可用，WSL可启动。原0x80070070失败记录保留。[RRR来源入库切片](implementation-19-rrr-source.md)已完成178项关联、最终8项针对回归、mypy85/Ruff/格式及84源码核对；下一步动态RRR公告成员选择与仓单消费者。正式来源认证、业务规则、真实模型资格检索、报告、120日重放和切换仍开放。

核对时间：2026-09-08。阶段为 **implement中的来源候选接入与认证补证**；grill-with-docs、to-spec、to-tickets已完成发布，不需要重做规划或重发已提出的问题。规格及票是范围依据，本文是续作索引。

## 已实际完成的本轮交付

从 `656eaa03` 继续：[LPR逐期审查准备](lpr-review-preparation.md)已形成可机器复核输入：9真实原件、18值、7段报价状态、固定窗口120目标日映射，并核对9个实际CAS引用；一次生成和一次只读复算通过。此为预期覆盖，不是模型PUBLIC查询或正式重放；声明/认证/采用仍0。用途依据另见[LPR核验](lpr-usage-evidence-review.md)，不凭通用个人非商业边界替代具体渠道条款。

从 `0679a475` 继续：[目录登记与 LPR 消费](implementation-19-catalog.md)代码批已验收：**819全套通过、0失败、852.83秒**；13新增、126关联、最后5项来源检查和34迁移/生命周期检查通过。第一轮817通过/2个旧测试兼容失败已修，应用源码未因这两处旧测试改变，失败日志与现场保留。84个安装Python文件前后匹配，mypy85、Ruff、两轴复审0；扩大检查的29条旧类型诊断与基点逐条一致。见[最终收据](verification-catalog/final.json)。

实际来源材料另有进展：[LPR认证矩阵](lpr-certification-gap-matrix.md)已根核13输入/9真实原件/18值/39引用；在全新隔离库完成9份document_import收据，18导出hash及真实时钟再次独立核验，声明/认证/新目录/真实候选/生产写入均0。见[收据](evidence-lpr-import-20260908/receipts.json)。这补了本次取得记录，未恢复历史SYSTEM或完成PUBLIC认证。

从 `1cd2c00` 继续：[票19正式包准入](implementation-19-admission.md)代码批完成：**806 全套/63 关联/50 新增通过，0 失败，860.32 秒**；mypy 83、Ruff/格式及双轴复审 0，82 个安装 Python 文件核对。请求/正式包/审查/登记原件的哈希与定义、规则、执行绑定均在候选写库前校验；坏包拒绝、合成幂等创建以及既有 active/发布投影保留已验收。[最终收据](verification-admission/final.json)。实际生产认证、新生产目录/候选、真实网络、激活/切换均 0。

**当前立即续作：**宏观消费者已保存为`0452aca`检查点；接着完成[DR007/Shibor新目录消费](implementation-19-interbank-consumption.md)：12新增用例、156关联回归通过（244.16秒），84安装源码匹配，mypy85/Ruff及双轴复审0剩余。TuShare公共标量入口的数据库目录解析、两项provider/单位/期限/日期与API字段已绑定；未知PUBLIC仍无法进入历史目标日模型。见[银行间检查点](verification-interbank/checkpoint.json)。下一步RRR公告成员契约、仓单多仓库选择及搜索新目录解析；请求/原文层配对预实验可独立定位，不能充当模型可用率。

上一宏观批856项全套为**855通过/1次CLI初始化60秒超时，3229.99秒**；同代码/同60秒上限单例6.20秒复测通过，不能称856一次全绿。174项时钟关联全通过，103个函数显式测试时钟已复审；见[原检查点](verification-official-consumer/checkpoint.json)。全量最终门待后续统一清除。测试使用独立D盘ext4，生产路径未变；完整票19、真实认证、检索配对、报告、120日重放和切换仍开放。

从`a569fd7`继续：[历史smoke收据补齐](implementation-history-receipts.md)完成，756全套/70关联/15新增通过，全套938.86秒，双轴复审0，Ruff/mypy82及81安装源指纹一致。目录/正文、线程owner、目标日、禁止自动重定向、错误体有界前缀和browser原包装转换血缘均验收。与03已修的history导入分别留证，不恢复过去SYSTEM或授予历史PUBLIC。

最新从`ca278071`继续：[官方解析修复](implementation-official-parsing.md)完成：产能非Q1缺累计列及重复工业行拒绝，M1/M2原始十进制金额先换算再输出，收据版本v0004。**741全套通过、0失败、977.15秒**，57关联、16新增、Ruff/mypy84、双轴0，81安装Python文件前后匹配。[最终收据](verification-official-parsing/final.json)。

贷款279格、社融837格、OMO252格已逐值及原件/字段/单位/期次根复核。原1858标量现在全部检查：**1856严格相符、1旧M2尾差、1产能Q1累计复用映射待确认**，未检查0。M2尾差在当前v4真实原件回归已修；旧准备包保持原样。数值一致不代表首发时间、实际获取时间、来源认证或模型采用通过。

**最新材料：**[A18新不可变准备包](p1-official-preparation-v2.md)已生成并第二次只读复算通过：250原件20069217字节，268调用、1858标量。1857新值严格符合原文字面、1Q1复用映射待定；唯一M2数值差异显式保留，旧包未改变。11审计hash、全原件与身份根复核、双轴审查0。研究验证时钟不冒充取得，认证/模型/网络操作均0。

**前批续作入口（已由上方准入代码批推进）：**按正式来源合同前置推进票19；不能绕过旧v3认证阻断。业务规则、外部源缺件、真实检索配对、AI网络与120日重放仍开放。

前批[OMO无效流量修复](implementation-omo-invalid-flow.md)已提交ca278071：725全套、75关联、9新增、双轴0；已知坏流量不会被当0或跳过以回退旧净额。完全无记录、空到期集合及台账日历完整性仍需证据。

最新从`375950b`继续：[贷款一月累计差分修复](implementation-loan-ytd-year-boundary.md)完成，一月自身、单父项、零/负值、缺月拒绝与余额版跨年保留。**716全套通过、0失败、782.66秒**，59关联、14新增、Ruff/mypy84、两轴审查0，81安装Python文件一致。[最终收据](verification-loan-ytd/final.json)。贷款跨年不再列代码待修。

[PPI69格](p1-ppi-full-value-audit.md)与[PMI56格](p1-pmi-full-value-audit.md)逐值、原件、字段、单位与期次根复核全部通过。累计独立核对从上批62增至183个不同标量，原1858个中另1675待审；旧准备包不改写，公开时间/认证不因此通过。

上批[OMO已有不合格投放被当0](omo-missing-flow-boundary.md)的2项RED及28引用/11指纹研究保留历史状态；该窄缺陷已由上面的725项代码批修复，不再以旧RED判定当前代码。完全无行、空到期集合与日历/台账完整性仍单独待证。

最新批次从`68c87ea`继续：[派生鲜度修复](implementation-derived-freshness.md)完成旧终止期不冒充current，保留值/血缘并排除当前解释及模型采纳。**702全套通过、0失败、758.10秒**，63关联、20新增、Ruff/mypy84、两轴审查0，81安装Python文件一致。[最终收据](verification-derived-freshness/final.json)。这是既有阈值一致性修复，官方源日历/认证仍未完成。

[CPI两指标完整逐值核对](p1-cpi-full-value-audit.md)：8原件、46格相符、0冲突，根代理逐格/源码行/单位/期次复核通过。原1858标量中独立核对从18扩大为62（本次46与旧锚点重合2），另1796未逐格审计。旧准备包保持不变。[P2鲜度证据边界](p2-freshness-evidence-boundary.md)明确当前源观察不能倒灌历史资格，根代理5原件/14链接复核通过。

上批发现的[贷款YTD一月跨年反例](loan-ytd-year-boundary.md)当时2失败，不属于702默认套件覆盖；已由本次716项批次修复，不再以旧RED判定当前代码。

最新批次从`ad86bd0`继续：[P2来源时间元数据](implementation-14-p2-source-timing.md)完成任务归属获取记录→读取投影→页面详情，**682全套通过、0失败、742.99秒**，69针对、Ruff/mypy82、两轴审查0，81安装Python文件一致。[最终收据](verification-14-p2-source-timing/final.json)。该项不再列代码待修；源日历鲜度、来源认证仍不是本批已完成内容。

[18项常规官方来源准备](p1-official-preparation.md)已形成可复算8文件包：250唯一原件、268家族调用、1858标量；18独立代表性期望、5专项和根代理默认只读重跑通过。旧包生成时另1840标量未逐格独立审计，最新CPI增量见上文，旧包不改写。27项全家族的新认证及模型采用矩阵仍待外部缺件，不能把此准备包记为已创建候选或已完成120日重放。

前批`ad86bd0`：[库存报告期校验](implementation-13-inventory-period.md)完成，**680全套通过、0失败、795.31秒**，60针对、Ruff、mypy82、双审查0，81安装Python文件与工作区一致。[最终收据](verification-13-inventory-period/final.json)。当时P2元数据RED与测试设置错误保留，真实缺陷由本次682项批次修复。

[P1准备清单](p1-certification-readiness.md)完成27项分流和68链接根复核：18项常规官方材料可先整理，3项另核时间/用途、2项外补、4派生依父项。部分1月CPI/PPI少列和工业VA合并期源自原表，不直接判采集缺失。没有新来源认证或候选模型采用。北交所[浏览器补证](margin-bse-browser-followup.md)1次导航超时，有效样本0、实际HTTP请求数未知，原阻塞不变。

历史代码批次从`ba596eb`继续：[RRR范围解析修复](implementation-13-rrr-scope.md)完成同日两个机构范围分别输出、完整分句校验和收据版本更新；真实原件修复前后一项/两项分别保存。**677全套通过、0失败、748.11秒**，66针对测试、Ruff、mypy82、两轴复审通过。[最终收据](verification-13-rrr-scope/final.json)。当时发现的库存错期由上面的680项批次修复，旧RRR收据保留其历史状态。

最新代码批次从`9199a5b`继续：[派生认证修复](implementation-13-derived-eligibility.md)完成7公式模型内输入/输出认证守门、未认证日历排除及任一输入PUBLIC未知的传播；关闭公式也不再引入其依赖。**664项全套通过、0失败、768.46秒**，57项针对测试、Ruff、mypy82与双轴复审通过；[最终收据](verification-13-derived/final.json)。其后工作从[RRR双范围解析RED](rrr-scope-repair-boundary.md)继续：真实2025原件的定向-5pp目前未输出。这个已知后续缺陷不在前一代码批次的默认测试范围内，不能因全套通过而标已修。

新增RRR四批研究共14次官方GET、4,384,725字节；[回顾与目录](rrr-followup.md)、[四篇公告](rrr-announcements-followup.md)、[两篇政策材料](rrr-policy-status-followup.md)、[原公告补证](rrr-original-notices-followup.md)均经根代理只读校验。原始发布会明确特定机构5%降至0%与2025-05-07日期，但精确时刻、阶段期限、区间事件全集和最近前置状态仍未证明；CSRC/吉林域不能冒充PBC认证域。不计入Tavily/Exa配对检索分母。公开解析入口已证实拒绝2025原件的2026请求，局部regex的错年试算不能再当确定生产缺陷。

应用基点为`9aaf5263132e2e3596ca4f71f18b109ef20a8c7f`：Treasury官方CSV候选入口/CLI、原件和真实SYSTEM关联、缺值/修订/来源最新期次等行为完成；27项针对测试、**639项全套、0失败、800.47秒**，Ruff、mypy81、Spec/Standards复审均通过。[实施记录](implementation-14-treasury.md)、[最终收据](verification-14-treasury/final.json)。前批EIA为`abbeb01`、612项全套通过；磁盘故障失败日志与恢复结果分别保留，不能只引用旧失败或旧成功。

| 实际新交付 | 取得与核验结果 | 仍不代表 |
|---|---|---|
| Treasury公开CLI | 1个真实GET、10个来源日、20条候选值；原件/标准化/血缘/SYSTEM独立复核通过 | 来源认证、历史PUBLIC、模型采纳 |
| DR007官方目标样本 | 2026-08-28加权利率1.3859%，旧交付1/1匹配；4GET中3个200、1个403空体 | 本次响应时钟或2200参数能证明历史发布时间 |
| VIX官方增量材料 | 新3GET全部200；CLOSE核对、早期OPEN异常及使用条款分开记录 | 全字段无异常、历史PUBLIC或持续生产使用范围已认证 |
| 北交所增量入口 | 新2GET均自指302；有效目标样本0，原件/失败交付复核通过 | 融资官方样本已补齐或来源认证通过 |
| 报告CLI网络复查 | Windows代理HEAD403；WSL直接超时、loopback代理连接拒绝 | 真实AI输出成功；本次新生成尝试0 |

以上官方GET和研究请求不计入Tavily/Exa分母。真实配对样本与模型可用补齐率仍 **N/A**，不能把HTTP成功或待认证候选数填成命中率。历史公开时间未知继续为未知；本轮无来源认证授予、生产写入、模型激活或真实切换。

## 逐票前沿

- 01/02/03/15/16/17：Execution已完成，分别保留原实施与验收记录。
- 04/05/06/07/08/11：仍blocked。分别缺核心公开版本、北交所官方样本、CNY030等官方点位/精度/历史、估值语义与字段、历史股票池/事件、PP等官方行情与合约身份。09/10/12继续等待历史输入和所属规则；453,571个盘后未知成员日不能补0。
- 13：仓单1000行饱和缺陷已修；DR007同期官方值已补。正式27项候选矩阵、仓单PP/CF/TA单位与样本、RRR事件/时间、新认证仍待验。
- 14：GDP/状态透明化、EIA和Treasury候选接入已完成代码批；13项P2来源认证、源日历/鲜度及适用使用范围尚未整票完成。
- 18：协议及语义核查入口已修；真实合格CLI输出与逐段解释验收仍缺，WSL网络条件未解除。
- 19/20/21/22：新不可变目录及候选模型、真实配对检索、固定120日PUBLIC重放、当前真实运行/切换依原阻塞边推进。不得在前置未过时创建“已认证”结果。

## 续作顺序与不可省略的外部条件

1. 从[研究13](research-13.md)、[DR007增量](dr007-followup.md)及[研究14](research-14.md)继续逐家族的正式认证材料和候选矩阵；优先复用已保存原件，只有新官方入口证据才继续有界获取。北交所见[本次失败边界](margin-bse-followup.md)，不重复已知403/自指302或猜后台地址。
2. [业务规则草案](business-decisions-draft.md)仍needs-info，涵盖07/08/09/10/12；此前已提问，尚无对具体选项的答复。可以继续独立缺陷/证据工作，但不能将草案当已冻结定义或静默换指标、缩范围、移基日。
3. [WSL网络复查](evidence-18-recovery/review.md)后，仍需一个实际可达且已授权使用的CLI网络路径。原问题保持待答；不改系统代理监听、不改走直接API、不以Windows无认证HEAD替代CLI验收。
4. 前置成立后创建新不可变目录/候选模型，再做同一分层缺口的Tavily/Exa对照及生产串行降级。分别统计请求、有效原文、模型可用补齐、时间和费用。
5. 固定重放窗口为 **2026-03-09至2026-08-28，恰好120个中国交易日**，包括独立的必要预热和PUBLIC/SYSTEM核验。美国来源127/129行、fixture窗口、旧模型输出均不能替代。再验收当前目标日模型与报告，最后按正式清单真实切换。

开发运行继续使用Ubuntu-22.04中已锁定的非editable Python环境及native临时目录。不要重跑已完成真实采集脚本复用旧演练目录；不要在WSL未安装新源码时把测试当工作区验证。代码基点81个Python文件的指纹保存在本批目录，旧79/80文件指纹只服务其各自历史批次。

本轮没有接管dashboard.css、dashboard.js及玻璃样式任务等其他工作区改动；提交时仍需精确列出归属文件。
