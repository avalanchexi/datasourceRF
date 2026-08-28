# Pring 周期驾驶舱 V1 point-in-time 证据模型

> 状态：已确认  
> 范围：领域实体、身份、时间、修订、时效、选源、查询和快照语义  
> 不在本决策中：数据库、ORM、表结构、索引与部署技术

## 1. 不变量

1. 系统同时支持**公开点时查询**和**系统点时查询**，两者不得隐式切换。
2. 来源给出的值先成为不可变的**来源声明**，再由版本化选源规则形成唯一的规范**证据观测**；多来源不能重复计票。
3. 上游修订、回填、页面替换、公式变化和重新选源都追加版本，不覆盖历史。
4. 环比、同比、累计、余额等分别是标量指标；页面卡片可以组合，存储和修订不能捆成一条宽表观测。
5. 发布计划不是实际发布，统计期不是发布时间，抓取成功也不是系统可用。
6. 获取失败不创建空观测；官方明确“不适用”或“未披露”是合法值状态。
7. 月季旧值可以继续展示，但保留统计期、发布时间、年龄和时效；沿用不产生每日新观测。
8. 报告和历史阶段只引用冻结的观测版本；后来到达的数据不能改写旧快照。

## 2. 两种点时查询

| 查询模式 | 回答的问题 | 进入条件 | 主要用途 |
| --- | --- | --- | --- |
| `public_as_of` | 市场在该时点按可靠公开信息理论上可以知道什么 | `public_available_at <= as_of` | 无前视回放、模型校准、研究 |
| `system_as_of` | 本系统在该时点已经取得并通过校验什么 | `available_at <= as_of` | 页面重现、证据包、报告重放、运行审计 |

生产查询必须显式传入 `as_of` 和模式，不提供隐式“最新”。当前驾驶舱默认使用 `system_as_of`；离线无前视校准默认使用 `public_as_of`。只有显式研究操作才能用今天已知的最新修订值重看历史。

所有真实时刻以UTC保存，并保留来源时区；边界为包含关系。统计期单独使用 `period_start`、`period_end`、`period_kind` 和参考日历，不让一个 `trade_date` 或 `month` 字符串同时承担统计期、发布时间和交易日语义。

`period_kind` 至少区分：

- `instant`：期末余额、当日收盘等时点值；
- `interval`：自然月、季度等区间值；
- `year_to_date`：年初至期末累计；
- `event`：政策行动等稀疏事件，另保存公告时点和生效时点。

## 3. 领域实体与身份

| 实体 | 职责 | 稳定身份/关键组成 |
| --- | --- | --- |
| `MetricDefinitionVersion` | 冻结标量含义、单位、频率、维度、来源优先级、容差、时效和角色 | `metric_id + definition_version` |
| `ReleaseExpectation` | 保存计划日程或历史节奏形成的预期发布窗口 | 指标/发布族、适用区间、期望规则版本 |
| `ReleaseEvent` | 表示一次真实上游发布 | 优先用官方发布ID；否则来源、规范URL、实际发布时间/首次发现共同识别 |
| `SourceArtifactVersion` | 保存一次页面、公告、文件或API响应版本及内容哈希 | 来源、上游对象身份、`content_hash` |
| `RetrievalAttempt` | 记录一次获取及分类结果 | 独立尝试ID；不承担经济值 |
| `SourceClaim` | 某个来源版本对一个标量经济事实的不可变声明 | `observation_id + provider + artifact_version + field_path` |
| `EvidenceObservation` | 由选源规则选出的规范标量事实 | 稳定 `observation_id` 加版本化 `observation_version_id` |
| `DerivedObservation` | 冻结公式对确切输入版本的计算结果 | 指标/公式版本、输入观测版本集合、as-of模式与截止点 |
| `ReportSnapshot` | 冻结一次报告使用的证据、规则、AI和输出清单 | 快照ID；同一报告日重跑产生新版本 |

### 3.1 统计观测身份

稳定 `observation_id` 由以下字段确定：

```text
metric_definition_version
period_kind
period_start
period_end
canonical_dimensions
```

来源、抓取时间、vintage和页面位置不改变经济事实身份。规范观测版本由稳定身份、选择规则版本和被选中的来源声明版本确定。证据角色引用稳定观测身份，同一观测承担多个角色时仍只计一次。

政策事件优先使用官方事件编号。没有官方编号时，使用事件类型、公告时点、来源和规范化上游身份；`announced_at` 与 `effective_at` 都属于事件内容，不能互相替代。

### 3.2 发布事件

不同指标不因属于同一个月份而合并成一个虚构事件。一份真实发布可以关联多条来源声明，例如同一份CPI发布包含总CPI、核心CPI环比和同比；同月稍后发布的工业增加值是另一个事件。

预期发布窗口只用于轮询和时效判断。实际页面没有可靠发布时间时，`release_at` 保持空值，不从URL或计划日程猜测。

## 4. 时间字段

| 字段 | 含义 | 规则 |
| --- | --- | --- |
| `release_at` | 上游明确标示的实际发布时间 | 没有可靠值时为空 |
| `public_available_at` | 公开点时可使用的保守时间 | 有准确时间时等于可靠发布时间；只有发布日期时取下一本地日00:00；无可靠日期时为空 |
| `fetched_at` | 某次请求取得响应的时间 | 每次获取尝试独立保存 |
| `available_at` | 本系统首次取得且通过全部校验的时间 | 重复抓取不改写；新内容形成新vintage |
| `computed_at` | 派生观测完成计算的时间 | 不替代输入的公开或系统可用时间 |
| `report_cutoff` | 报告允许使用证据的截止时点 | 快照内冻结 |

历史回填若没有可靠公开日期，不能进入更早的 `public_as_of` 校准，只能从实际 `available_at` 进入 `system_as_of`。只有发布日期而没有时刻时从次日00:00开始使用，以避免日内前视。

## 5. 值状态与修订

### 5.1 合法值状态

| `value_state` | 含义 | 是否可形成来源声明 |
| --- | --- | --- |
| `reported_value` | 官方明确给出标量值 | 是 |
| `not_applicable` | 制度或口径下字段不适用，例如新MLF机制没有统一中标利率 | 是 |
| `not_disclosed` | 发布存在但该值没有披露 | 是，必须保留来源依据 |
| 尚未发布/请求失败/无权限/限频/解析失败 | 没有合格经济声明 | 否；只形成获取尝试 |

禁止以数值0替代任何非数值状态。

### 5.2 追加式vintage

- 同一页面或API结果内容变化时生成新的 `SourceArtifactVersion` 和来源声明vintage；旧版本保留。
- 新版本指向被替代版本；官方撤回使用 `retracted`，不得物理删除。
- 当前页面选择截止点内最新已验证版本；历史点时查询只选择当时已可得的版本。
- 发布前回填和发布日期前回溯值必须保留 `backcast` 标识。

### 5.3 派生观测

每条派生观测至少绑定：

```text
derived_metric_definition_version
formula_version
exact_input_observation_version_ids
as_of_mode
as_of_cutoff
computed_at
```

输入被修订或公式变化时生成新的派生版本。信用脉冲、订单－库存差和趋势状态都不得在查询时静默重算并覆盖旧结果。

## 6. 状态分层

三类状态必须分开，避免一个 `status` 同时表示数据未发布、来源失败和数值冲突。

### 6.1 获取尝试

```text
succeeded
not_yet_released
permission_denied
rate_limited
source_failed
validation_failed
unsupported_code
```

### 6.2 来源声明

```text
validated
superseded
retracted
```

校验失败的解析候选不升级为来源声明。

### 6.3 规范观测选择

```text
selected
conflicted
unavailable
```

选择状态由as-of截止点、指标定义版本、认证状态、来源优先级、语义一致性、容差和时效共同计算，而不是通过覆盖一列“当前状态”破坏历史。

## 7. 选源与冲突

每个 `MetricDefinitionVersion` 冻结：主来源、有序后备来源、语义/单位/时间口径要求、容差和冲突策略。

1. 不同语义、单位或时间口径的值不能互为后备。
2. 后备来源必须已完成来源认证；相似代理不能静默补值。
3. 多来源值不平均，也不进行多数投票。
4. 认证主源有效且其他来源在容差内时，主源成为规范观测，其他声明只作血缘和确认。
5. 超出容差时保留全部声明和冲突：
   - P0：`conflicted`，不产生新的核心状态或正式阶段；
   - P1：显示冲突，不形成当前转折观察或宏观确认；
   - P2：显示主源值及冲突警告，只作背景。

## 8. 发布时效

时效根据每个指标独立的预期发布窗口和宽限期计算：

| 状态 | 含义 | 展示 |
| --- | --- | --- |
| `current` | 截止点下最新应发布期已取得，或下一期尚未进入窗口 | 展示最新观测及真实统计期 |
| `awaiting_release` | 已进入预期窗口但尚无新观测，仍在宽限期 | 展示上一期、年龄和等待状态 |
| `stale` | 超过窗口与宽限期仍无新观测 | 继续展示上一期并警告 |

`source_failed` 是获取状态，不是时效状态；一次失败不证明官方已经发布，也不改变已有观测。

### 8.1 默认宽限规则

| 发布类型 | 进入 `stale` 的默认条件 |
| --- | --- |
| 中国日线 | 下一中国交易日预计完成时间仍无新值 |
| T+1数据 | 对应交易日后的第二个中国交易日仍无值 |
| 有官方日程的月/季数据 | 预期发布窗口结束后1个工作日仍无值 |
| 无固定日期的央行月度数据 | 指标独立历史发布窗口结束后2个工作日仍无值 |
| 国际日频 | 超过一个完整来源市场交易日仍无值 |
| 稀疏政策事件 | 没有新事件不算过期；独立监控来源扫描健康 |

个别指标只有在指标目录明确记录理由时才能覆盖默认值。

### 8.2 过期后的作用

- P0：保留上一确认阶段，不生成新的当前阶段。
- P1：旧值继续展示，但不承担当前转折观察或宏观确认。
- P2：旧值带警告展示，只作为历史背景。

## 9. 当前视图、回放与报告快照

### 9.1 默认视图

- 当前驾驶舱：`system_as_of`截止点内最新已验证vintage。
- 无前视校准：每个历史时点按 `public_as_of` 选择当时可得vintage。
- 最新修订回看：仅显式研究模式允许，不能替代历史报告或正式校准记录。

### 9.2 报告快照

快照至少固定：

```text
report_cutoff
as_of_mode
selected_observation_version_ids
source_claim_and_vintage_ids
release_event_ids
freshness_quality_and_conflicts
metric_definition_versions
formula_and_model_versions
evidence_bundle_hash
ai_adapter_model_and_prompt_versions
report_content_hash
```

截止点后到达、修订或认证的数据不修改旧快照。手动重跑形成新的快照ID和版本，即使报告业务日期相同也不能覆盖。

完整自然语言Markdown保留30天并保持不可变；结构化快照清单、阶段结果、观测血缘、规则版本和内容哈希长期保留。

## 10. 最小查询契约

所有生产查询必须显式声明 `as_of`、`as_of_mode=public|system` 和修订策略；禁止隐式读取“最新表”。V1至少需要：

```text
select_observations(metric_ids, period_range, as_of, as_of_mode, revision_mode)
list_release_events(time_range, as_of, as_of_mode)
explain_observation(observation_version_id)
get_report_snapshot(snapshot_id)
```

`select_observations` 返回值至少包含：稳定观测ID、观测版本ID、标量值状态、统计期、选中来源声明、时效、质量、选源状态、冲突摘要和血缘ID。

`revision_mode` 默认是 `as_of`；`latest_revised` 只允许显式研究用途。页面、模型和报告模块只能通过该契约读证据，不能直接联接底层来源表。

## 11. 验收场景

1. 核心CPI 09:30发布、09:36通过系统校验：09:33的 `public_as_of` 可见，`system_as_of` 不可见；09:36后两者可见。
2. 月度指标尚未进入下一发布窗口：上一期仍为 `current`；进入窗口后为 `awaiting_release`；超过宽限期为 `stale`，但不复制新观测。
3. 历史页面只有发布日期：从下一本地日00:00进入公开回放；没有可靠日期则不能进入更早公开回放。
4. 工业增加值季调环比修订：首发和修订vintage都可查询，旧报告仍指向首发版本。
5. 主源与认证后备源超出容差：两条来源声明都保留，P0规范观测为 `conflicted`，不生成新阶段。
6. 2025年3月后MLF没有统一中标利率：保存 `not_applicable`，不得当成0、尚未发布或源失败。
7. 商品核心超过时效：`current_stage`为空，保留 `last_confirmed_stage`。
8. 报告截止后补到一条P1数据：驾驶舱可更新，但旧报告不变；手动重跑产生新快照版本。
9. 同一核心CPI观测同时承担物价压力和宏观确认角色：只保存并计数一次。

## 12. 与既有决策的关系

- [V1指标目录](v1-metric-catalog.md)中的发布规则、时效、证据角色和来源认证状态由本模型承载。
- [核心资产历史验收](core-asset-history-certification.md)发现的回填、前收调整和不同完成日必须作为vintage、质量与共同截止点处理。
- [ADR：正式阶段只由核心价格决定](../../../docs/adr/0001-price-only-formal-pring-stage.md)要求P0缺失、过期或冲突时不生成新阶段。
- [ADR：AI只解释不分类](../../../docs/adr/0003-ai-explains-but-does-not-classify.md)要求报告只读取冻结证据快照。
- [ADR：深模块](../../../docs/adr/0004-deep-modules-over-stage-file-pipeline.md)要求页面、模型和报告通过上述查询契约访问证据，而不是传递可变大JSON或直接读取来源表。
