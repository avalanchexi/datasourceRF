# 15 请求账本与预算恢复：实施记录

Execution: completed

固定审查基线：`074771022daf5552f6d47899ba5c8aac0b1d385e`。本票只推进定向检索账本、预算与恢复；候选下载认证入库由 16 接续，完整运行缺口计划由 17 接续，实际 Tavily / Exa 配对测量由 20 接续。

已接入真实 RunRepository 提交、Worker、HTTP transport、采集收据及运行读模型。当前定向接口请求整个指标家族，维度逐项以 `*` 明确表示所有成员；不表示每个成员已经取得。模型、定义、期次、目标日和 as-of 均冻结在 gap 身份中。发布预算键使用定义的发布家族与期次，不使用调用方可变标签，也不宣称已证明历史实际发布时间。

## 验证进度

仅替换 HTTP transport、时钟和进程存活边界；测试使用隔离的 WSL 原生运行目录，不调用真实账户。

- 请求前预留及原件读回：RED 缺少账本，GREEN 1。
- KeyboardInterrupt 与显式恢复：RED 仍显示 running，GREEN 2。
- 手动深搜日上限、调用方标签绕过：RED 实际发出 17 次及同事件 2 次，GREEN 4。
- 格式错误/500/429/403 的收据、跨日负缓存、Tavily 积分/Exa 估算：RED 未完成请求或缺元数据，GREEN 10。
- 30 日响应过期：RED 缺 raw_status，GREEN 单用例通过。
- 失效 Worker 租约恢复：RED 请求仍 reserved，GREEN 单用例通过。
- 同发布的新冻结 gap 复用归因：RED 缺 reused_request_id，GREEN 单用例通过。
- 官方 HTTP 校验失败仍关联请求/原件：修正测试 URL 后 RED 请求未登记，GREEN 单用例通过。
- 跨日保留运行上限 8/4、P2 24 小时缓存并在 Exa 后停止：当前文件合计 **17 passed in 22.19s**。
- 中间类型检查：72 个源文件通过；最终检查、双路审查和全套回归仍待完成。

## 费用来源

[Tavily Search 官方文档](https://docs.tavily.com/documentation/api-reference/endpoint/search) 的 `include_usage=true` 与 `usage.credits` 支持保存实际返回的用量积分；不由预算次数推算美元。[Exa Search 官方文档](https://exa.ai/docs/reference/search) 明确 `costDollars` 是估算分解，账单另按 usage counters 计算。因此保存 provider_estimate 标识，`billed_cost` 保持未知。

当前仍在收口迁移兼容性、保留期与审计细节；不得以本记录宣称本票完成或来源认证/模型重放通过。

## 初审与增量修复

Standards 初审 4 项、Spec 初审 6 项，分别记录，未混为统一排序：

- Standards：SCHEMA_HEAD 健康回归；落原件后中断缺保留截止；巨大费用整数溢出；官方短重试被关闭。
- Spec：手动深搜第二次被挡；官方 HTTP 429 丢 Retry-After；旧当日预算及有效缓存被忽略；中断原件永不过期且官方原件被误标过期；候选请求5条超过3；默认重定向多发未登记请求。

已实现并通过公开边界回归：

- 手动深搜按原冻结 `refresh-orchestration-and-recovery-model.md` §7.2 的明确例外，事件 2/2/1，继续日16/8/2；搜索不自动扩词。
- 官方 HTTPError 保留状态及 Retry-After。幂等官方传输恢复本次 Worker attempt 内最多两次短重试，每次分别登记；缓存跨显式恢复继续约束。
- 旧未关联物理请求的已扣请求仍计入日预算；旧手动已尝试记录保守纳入限额。新尝试关联 physical_request_id，避免旧/新账本双计。历史未追踪记录不被伪装为有原件的真实物理请求，费用仍未知。
- 旧有效负缓存继续阻止外部请求。搜索原件期限统一按收据 received_at 起30日，覆盖 unknown_completion；官方响应不适用搜索过期策略。
- Tavily/Exa 请求各最多3个候选；巨大/无效费用保留未知，不阻断账本完成。拒绝自动重定向，保存302原件，避免账本外第二请求。
- 新迁移与 SCHEMA_HEAD 对齐。现有 CLI 初始化/诊断用例先失败后随相关套件通过。

2026-09-06 本轮相关检查：`test_retrieval_ledger.py`、`test_search_discovery.py`、`test_cascade.py`、`test_local_runtime_cli.py` 合计 **47 passed in 59.00s**；mypy **73** 源文件通过，Ruff通过。增量双路复核、最终全套和提交仍未完成。

## 第二轮复核与迁移兼容性

- 旧普通重试即使未再次扣逻辑预算，已尝试结果仍保守占用物理请求额度；恢复旧运行时按已存尝试补足运行限额。旧尝试不是精确HTTP或账单证明，不制造原件或费用。
- 旧请求和负缓存按原运行绑定模型的目录恢复 `release_event_family + period`。v2社融总量与分项的预算、缓存继承均通过真实Worker回归。
- 官方提供商错误缓存按URL主机隔离；统计局限频后中国货币网仍请求，统计局其他发布继续受缓存约束。
- 请求预留与完成后的下一可试时间共用一套决策。手动深搜还有一次时可立即再试；运行额度耗尽或P2排除AI时，时间为空，且此永久门禁优先于日预算到期。
- 新增/扩充回归：旧日预算2例 GREEN；来源隔离、旧家族共享预算/缓存、跨日旧运行限额等合计7例 GREEN；最终一次Tavily/Exa响应完成当下时间为空2例先RED后GREEN。

第二轮相关套件合计 **53 passed in 73.00s**，mypy73、Ruff通过。最后两项下一可试时间补充断言在该套件之后通过；最终全套回归与最后双路确认待记录。

## 最终验收

2026-09-07 最终全套 **487 passed in 198.17s**。mypy73源文件、Ruff及暂存diff检查通过。Spec与Standards双轴复核均0项；最后测试时钟增量也分别确认未削弱验收。

首次全套486通过、1项失败；[保留失败记录](verification-15/first-full.json)证明WSL墙钟回拨约2秒使测试的“事后查询”早于刚存入的available_at，隔离库仍有各核心160条声明且run完成。原样单项复跑通过；随后仅测试在采集、历史写入、Worker时钟边界统一monotonic时钟，保留全部原断言。初次时钟注入只覆盖采集层导致时间不一致，再补完整时钟边界及datetime类型兼容后单项1通过；提前启动的一次全套已立即中止，未计为通过。最终全套结果来自完成该测试修正后的完整运行。

本票完成仅代表定向请求账本、预算、缓存、原件保留和恢复行为通过。真实缺口搜索下载/认证/选值由16继续；生产Tavily/Exa命中率、120日PUBLIC重放、模型生效和切换仍未验收。
