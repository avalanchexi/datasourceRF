# 上下文标准化制品消费核验

**本批最终软件验收：**默认全套1053通过、0失败、3673.23秒，原会话95550实际退出0；376关联回归通过、935.66秒。167输入前后字节相同，最终90安装Python源一致；mypy92、Ruff/7文件格式及双轴审查剩余0。见[最终检查点](verification-context-normalized/checkpoint.json)、[终态](verification-context-normalized/terminal.json)与[全套原日志](verification-context-normalized-full-22.txt)。下文各阶段的“尚未完成/正在运行”和失败输出均保留其历史状态；本次最终通过只覆盖LPR软件增量，不覆盖仍开放的其他家族、真实认证及完整模型最终门。

**全套等待期间的独立补证：**[PP官方增量](pp-official-followup-20260909.md)6个逻辑查询、2次web搜索、1次新官方PDF的GET调用尝试在TLS阶段超时；没有HTTP响应、新原件或2026-08-28有效样本。根代理核对报告9717字节/hash及10本地引用，2022历史月表索引不授予2026日报单位认证。本轮与Tavily/Exa实验分母隔离。默认全套95550仍运行时未编辑应用/测试；167冻结输入再核对无变化，测试卷约24GB可用、WSL可用内存约5GB，未发现资源耗尽证据。

2026-09-09；从本地提交 `bda795f566f60205fc443f3854a8e2eb1b13b76c` 继续。前批核心/仓单与连接生命周期默认全套1031通过，只证明该提交。当前工作沿用票19和规格已确认的公开采集、来源声明、检索选值、上下文及点时回放入口；业务规则和来源认证条件不变。

下一组边界依据[已有源码与原件研究](normalized-context-next-seams.md)：LPR、常规官方宏观、DR007/Shibor，以及RRR全部关联收据。只验证展示行不足以保护派生指标和回放输入，后续必须分别观察实际消费结果。

第一条反例通过公开候选准入及LPR导入，先确认PUBLIC检索完整，再损坏该次取得的标准化制品，要求检索返回不完整且不采用原声明。测试只使用隔离运行库与合成来源认证合同，不代表正式来源认证。[RED](verification-context-normalized-lpr-red-01.txt)已确认：损坏后仍返回complete=True及两个声明，1失败、4.30秒、退出码1。检索入口接入已有按精确声明关联的双制品读取后，[GREEN及正常消费](verification-context-normalized-lpr-green-01.txt)2通过、5.16秒、退出码0。

第二个[语义RED](verification-context-normalized-lpr-semantics-red-01.txt)保留正确原件，公开capture生成哈希自洽但1年利率改为3.1的标准化收据，再关联同一声明；检索仍完整，1失败、3.88秒。加入逐原件重新解析整份LPR公告并校验标准化哈希后，[三项回归](verification-context-normalized-lpr-green-02.txt)3通过、5.94秒、退出码0。

第三个[上下文RED](verification-context-normalized-lpr-context-red-01.txt)确认损坏后仍显示current，1失败、5.09秒。上下文接入共用的整收据校验后，[green-03](verification-context-normalized-lpr-green-03.txt)为3通过/1失败、12.02秒：source_failed断言已通过，剩余失败是测试将`observation_version_ids`错误当作实际模型采用列表。源码及既有RRR/仓单公开用例表明，该字段保存包括失败展示在内的审计引用；实际采用是`macro.model_input_observation_version_ids`。因此修正测试观察字段并保留失败声明的诊断引用，不删除追溯链以迎合错误断言。原green-03失败原样保留，不算新增生产缺陷。

[修正字段后的回归](verification-context-normalized-lpr-green-04.txt)最终**14通过、10.30秒、退出码0**，包含3个新增消费场景、正常新目录消费及10个既有LPR适配器用例。[mypy](verification-context-normalized-mypy-01.txt)应用及candidate测试91文件通过，[安装指纹](verification-context-normalized-fingerprint-01.json)90个Python源码相符。Ruff通过；一次格式检查要求补调用的尾逗号，已由formatter修正。[两轴阶段复核](verification-context-normalized-review-01.md)当前新增问题各0，未将下述尚未完成范围当作已验收。

当前仍需验证选中声明的经济字段和时间降级、更多合法版本及PUBLIC回放；常规官方宏观、银行间、RRR全部收据与派生消费尚未完成。本批未提交，前批1031全套不能作为本批最终验收。既有研究中要求所有无效声明均移出`observation_version_ids`的泛化表述由本次字段核对纠正：失败诊断引用保留，必须排除的是实际模型采用、派生父项及其结果；不能删除失败血缘来让测试通过。

## 2026-09-09 字段与时间增量及最新断点

后续逐项复现声明值、统计期、来源引用和已知发布时间与原件不符但仍被检索采用的问题，见`verification-context-normalized-lpr-claim-red-01.txt`、`verification-context-normalized-lpr-period-red-02.txt`、`verification-context-normalized-lpr-reference-red-01.txt`及`verification-context-normalized-lpr-time-red-01.txt`。`lpr-period-red-01`的基线断言本身有误，不计为生产RED。共用校验现在接收实际选中点，核对值/期限、月份起止、provider/单位、原件URL与hash引用，以及已知发布时间；双时间均未知的保守修订不凭校验补出PUBLIC资格。前三次逐步回归分别15通过/22.66秒、6通过/15.71秒、7通过/9.98秒，均实际退出码0。

新增合法发布日期精度、未知公开时间、同发布时间修订、新发布时间修订及重复取得5个场景后，[最新定向验证](verification-context-normalized-lpr-green-08.txt)为**21通过、2失败、41.00秒**，会话21016结束、退出码1。7个损坏或错配场景全部通过；`unknown_public`和`same_time_revision`在上下文`status == current`断言失败，尚需核对发布状态与测试预期，不能预先把这两项写成产品缺陷或改动资格规则。此次没有修改应用或测试源码。

[安装核对](verification-context-normalized-fingerprint-08.json)90个Python源相符；[本次终态](verification-context-normalized-terminal-08.json)绑定4个源码/测试文件及验证记录。旧run-inputs、mypy和两轴review-01只证明此前14项阶段。下一步先诊断两项状态断言，随后继续PUBLIC回放、其他家族与派生边界；当前代码批尚未通过最终验收或提交，不代表真实来源认证或完整候选建立。

## 双点时日历与公开回放修复

上节两项状态失败经[定向诊断](verification-context-normalized-lpr-status-red-09.txt)再次复现：均为SYSTEM下`stale`，不是制品`source_failed`或来源冲突。发布日历的`_released_observation`先丢弃PUBLIC为空的事件，再由同时要求两时间的判断推导stale，导致已取得且校验的合法记录退出实际采用。依规格6/8及ADR0006，现保留可空的真实PUBLIC字段，按明确的模式分别用PUBLIC或SYSTEM可用时间判断。没有把取得时间写成公开时间。修复后[29项回归](verification-context-normalized-lpr-green-10.txt)通过、31.47秒、退出码0。

公开组件回放经候选与对照各自的合成来源合同入库，先验证两侧正常采用，再只损坏候选制品。[首次](verification-context-normalized-lpr-replay-red-11.txt)失败是测试误用不存在的返回字段；[第二次](verification-context-normalized-lpr-replay-red-12.txt)改变利率但沿用原发布时间，依法产生未知PUBLIC，不能当作已通过正常基线。两次均不算生产RED。修正为同值、不同原件hash的合法交付后，[真正RED](verification-context-normalized-lpr-replay-red-13.txt)1失败、6.57秒：候选标准化损坏后回放仍返回空gaps。

`evaluate_context_replay`的选值门现调用同一LPR全关联校验；[首组6项](verification-context-normalized-lpr-replay-green-14.txt)通过、23.96秒。随后原件/标准化×丢失/损坏×当前/后发修订8个组合，连同5个合法时间场景，[13项扩展](verification-context-normalized-lpr-replay-green-15.txt)通过、45.13秒。旧cutoff不被尚未公开的坏修订污染，新cutoff明确报告candidate_context_selection_invalid；坏新值保留诊断而不回退旧值，对照侧仍可采用。该公开组件测试只改内存manifest副本的组件范围，不改存储的正式包，也不宣称完整模型通过。

正常消费另增加已有2026-08官方原件`5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5`，字节hash独立重核、字面期望为1年3.0/5年以上3.5；测试取得时钟和准入合同仍是合成，不倒填生产SYSTEM或授予真实认证。仅日期场景同时验证SYSTEM取得前不可用、取得后实际采用，以及PUBLIC次日本地00:00边界。[7项正例](verification-context-normalized-lpr-positive-green-16.txt)通过、22.99秒。

Spec复核随后指出日历原按事件ID倒序，`unresolved-publication:*`会盖过后来已有可靠时间的新修订。新增首发→未知时间修订→恢复可靠新发布时间的三次导入及四个双轨查询，[RED](verification-context-normalized-lpr-calendar-red-18.txt)1失败、4.57秒；日历按月份、对应模式时间、取得时间和稳定事件身份排序后，[22项回归](verification-context-normalized-lpr-calendar-green-19.txt)通过、21.50秒。PUBLIC仍排除未知，SYSTEM使用最新取得事件；两轴复审剩余0。

当前七个源码/测试文件的Ruff通过，mypy应用及两测试共92文件通过，90安装Python源相符。mypy-21的两项测试注解诊断及格式失败记录保留，已修后见mypy-22及format-22；无业务规则变更。[167个输入](verification-context-normalized-run-inputs-22.json)已冻结，开始9文件关联回归，主会话52702；结果以实际终态为准。当前全套及本批提交尚未完成。常规官方宏观、DR007/Shibor、RRR全部关联收据、真实来源和完整模型的原验收范围继续开放。

9文件[关联回归终态](verification-context-normalized-targeted-22.txt)为**376通过、935.66秒**，主会话52702退出码0；随后独立重核167输入，全部字节未变。七文件最终格式和辅助checkpoint脚本Ruff均通过；其间辅助WSL错误单独保留在helper-check-22，不当作主测试失败。默认全套现以新目录`official-context-normalized-full-22`运行，会话95550尚未终止，真实状态见[terminal.json](verification-context-normalized/terminal.json)。只有该运行正常结束且输入/安装源码再核对一致后，才可执行新finalize.py；不要使用旧批的finalize脚本。

[下一宏观研究](official-macro-normalized-next-step.md)已根代理独立复核55本地链接、15目标文件、两真实原件hash及PMI八个字面值；派生入口确实重新读series，必须同时守住原始采用与两条派生。没有执行新的PMI反例，没有编辑被冻结的源码/测试或给予来源认证。

默认全套运行期间另完成[RRR事件全集有界补证](rrr-official-completeness-followup-20260909.md)：4逻辑查询、2次web调用，新open/GET/原件0，未补到固定窗口全集、阶段性续止或窗口前最近状态。根代理重核报告9753字节及hash、15本地引用、两份旧PBC原件的hash/字节和原通知日期/范围正文。2025原始通知已由较早预实验找到，不能继续沿用旧“原通知未找到”；本次没有将该旧材料冒充新的全集证据，也没有改变Tavily/Exa分母、认证或模型状态。
