# 旧项目回归场景与迁移边界

> 目的：把旧项目中已经暴露的行为级故障转成 V1 的负向回归案例，而不是把旧报告、旧测试期望或旧阶段结果当成真值。  
> 旧项目：`/mnt/d/cursor/datasource`，本次仅做静态只读检查；未运行旧流水线、旧测试、外部数据源或模型，也未读取、输出或保存任何 token、API key 或 `.env` 内容。  
> 冻结基线：[价格唯一决定正式阶段 ADR](../../../docs/adr/0001-price-only-formal-pring-stage.md)、[V1 指标目录](v1-metric-catalog.md)、[point-in-time 证据模型](point-in-time-evidence-model.md)、[120 日趋势状态机](../issues/06-calibrate-120d-trend-state-machine.md)。

## 1. 结论

旧项目最值得迁移的是失败样本和接口经验，不是 Stage1→Stage4 文件流水线，也不是旧分类器。V1 至少需要以下四层回归门：

1. **趋势层**：三类正式核心都能稳定进入牛、熊状态；缺失、初始化不足和冲突不能伪装成方向。
2. **阶段层**：只接受六个规范牛熊组合；任何不确定或非典型组合都输出 `current_stage=null`。
3. **证据层**：月季数据按真实公开时间和系统可用时间查询，修订不能重写历史；期货换月不能制造经济收益。
4. **运行层**：P0 核心失败必须阻断本次正式阶段，异常恢复、重放和报告生成都不能改变确定性结果。

旧项目存在可静态证明的严重分类缺陷：商品 Bullish 的理论最高综合分只有 `40×0.35 + 60×0.65 = 53`，却要求至少 70 分，因此商品牛市条件不可达。它同时把缺失数据赋予中性或偏高分、把 `Neutral` 先转换成 `False`，并用宏观、库存和货币状态再次改写正式阶段。这些行为与 V1 的冻结 ADR 直接冲突。

## 2. 旧行为的静态核验

| 旧行为 | 静态证据 | 影响 | V1 结论 |
| --- | --- | --- | --- |
| 商品 Bullish 不可达 | `pring_analyzer.py:108-115` 定义 35%/65% 权重和 70 分阈值；`:648-707` 基本面满分 60；`:780-827` 技术面满分 40；`:737-750` 直接加权 | 商品无法进入牛市，Stage III/IV/V 的可达性被破坏 | 商品核心直接由 NHII 的版本化价格趋势状态决定，不使用宏观评分“矫正”商品方向 |
| 缺失默认高分 | `pring_analyzer.py:817-827` 无商品行情返回 35/40、异常返回 30；`pring/scoring.py:6-140` 多项缺失返回各自权重的 50%；库存评分异常返回 30/60 | 数据越缺，反而越像中性或偏强的有效样本 | 缺失=`unavailable`，不计分、不插值成中性、不参与阶段 |
| `Neutral` 被折算成熊 | `pring_analyzer.py:1265-1288` 只有 `== Bullish` 才为 `True`，其余均为 `False`，且先查精确布尔组合 | 不确定方向被静默解释为价格下跌 | 趋势层只输出稳定 `bullish`、稳定 `bearish` 或无状态；无状态不得进入六阶段映射 |
| 全不确定映射 Stage VI | 三个 `Neutral` 先变为 `(False, False, False)`，命中 `pring_analyzer.py:1280`；`get_asset_signals()` 异常又会在 `:1123-1129` 生成三个 `Neutral` | 一次异常可以伪造全面熊市 | 三核心任一无效即 `current_stage=null`；三者全无效仍为空，并保存明确原因 |
| 非典型组合被近似到某阶段 | `pring_analyzer.py:1290-1323` 对无精确规则的组合做最高分近似 | `(牛,熊,牛)` 因字典顺序取 Stage I；`(熊,牛,熊)` 取 Stage II，且没有理论依据 | 两个非典型组合都必须为空；保留原始三资产状态和 `last_confirmed_stage` |
| 收益率被用作债券正式核心 | `pring_analyzer.py:1035-1049` 用 CN10Y 收益率变化生成债券方向；方向本身是“收益率下行=债券牛” | 若代理值、单位或价格被误当收益率，方向与 bp 变化会失真 | 正式核心只用 `000012.SH` 价格；收益率仅作反向确认，不得替代核心 |
| 宏观与货币改写阶段 | `_enforce_stage_consistency()` 在 `:1210-1250` 改写阶段；`_blend_stage_with_weights()` 在 `:1437-1458` 用库存 35%、货币 35%、资产 30% 重算阶段；`analyze_pring_stage()` 在 `:1604-1647` 实际调用这些路径 | 同一组三资产价格可因宏观输入不同而得到不同正式阶段 | 宏观、库存、通胀、政策只做观察、解释和确认；不得投票、否决或平移正式阶段 |
| 月季统计期可被当成可用时点 | `market_data_contract.py:181-227` 只有 `date/as_of_date/report_period`，没有独立发布时间、系统可用时间和 vintage；`extraction_apply.py:105-112` 把推断出的 `report_period` 填进 `as_of_date`；`:428-438` 又可写入 `date` | 报告可能在真实发布前看见月度或季度结果；后续修订也难以重放旧视角 | 强制区分统计期、`release_at`、`public_available_at`、`fetched_at`、`available_at` 和 vintage |
| 期货换月可制造假拐点 | `utils/yahoo_finance.py:29-65` 把 `CL=F/BZ=F/HG=F` 当主力映射；`providers/stage2_structured/yahoo_finance.py:24-103` 只保存通用 ticker 的 `regularMarketPrice`，没有实际合约月、结算价、换月事件或调整因子 | 合约切换价差会被当成经济涨跌，污染 30/120 日趋势和阶段转换 | NHII 核心使用官方指数收益链；任何期货链必须显式保存合约与换月调整，缺元数据则不可用于趋势 |

旧测试也把部分错误行为锁成了“正确结果”：

- `tests/test_stage3_logic.py:55-70,112-121` 期望缺债券或缺股票时返回 `Neutral`；
- `tests/test_stage3_logic.py:187-195` 明确期望库存与货币把 Stage I 改为 Stage III；
- `tests/test_stage3_guard.py:18-51` 把三个 `Neutral` 和一个有效阶段组合视为合法结果；
- `tests/fixtures/pring_golden/pring_result.json:1-25` 在债券 Bullish、股票 Bullish、商品 Neutral 时仍给出 Stage IV 和资产配置建议。

因此旧 golden 只能作为“必须被新版拒绝的反例”，不能作为新分类器的期望值。

## 3. V1 必须覆盖的回归案例

### 3.1 趋势和正式阶段

| ID | 给定 | V1 必须输出 | 首选测试层级 |
| --- | --- | --- | --- |
| `REG-TREND-001` 商品牛市可达 | NHII 连续收益、MA120 距离、MA120 20 日斜率均满足稳定牛市规则，并持续达到版本要求 | `commodity_state=bullish`；不得读取库存或通胀分数 | 趋势单元 + 真实历史重放 |
| `REG-TREND-002` 商品熊市可达 | 与上例对称的稳定熊市序列 | `commodity_state=bearish` | 趋势单元 + 真实历史重放 |
| `REG-TREND-003` 缺失不是中性分 | 商品、宏观或政策输入为空/异常 | 对应观测为 `unavailable`；无默认 35、30 或 50% 权重分 | 单元/属性测试 |
| `REG-TREND-004` 初始化不足 | 少于 MA120、预热或持续确认要求的价格历史 | 核心状态为空并给出 `insufficient_history`；不继承伪方向 | 单元测试 |
| `REG-STAGE-001` 六个规范组合 | 逐一输入 ADR 冻结的六个三资产牛熊组合 | 一一映射到 Stage I–VI，六阶段全部可达 | 表驱动单元测试 |
| `REG-STAGE-002` 单一不确定 | 任一核心状态为空，另两项任意 | `current_stage=null`，保留原始状态、原因和 `last_confirmed_stage` | 表驱动单元测试 |
| `REG-STAGE-003` 全不确定 | 三核心均为空，包括采集异常造成的全缺失 | `current_stage=null`，不得输出 Stage VI | 单元 + 故障注入 |
| `REG-STAGE-004` 非典型牛熊组合 | `(债牛,股熊,商牛)` 与 `(债熊,股牛,商熊)` | 两者均 `current_stage=null`，不得近似匹配或按字典顺序裁决 | 表驱动单元测试 |
| `REG-STAGE-005` 宏观不可改写 | 固定同一组三资产状态，穷举宽松/收紧、补库/去库、过热/衰退证据 | 正式阶段逐字节相同；只有观察、确认与解释字段变化 | 变形/属性测试 |
| `REG-STAGE-006` AI 和报告不可改写 | 确定性阶段已保存，CLI 返回冲突叙事、失败、超时或非法阶段 | 阶段记录不变；报告降级或失败独立记录 | 集成测试 |
| `REG-STAGE-007` 非相邻转换 | 前一确认阶段与新规范组合跨越多阶段 | 接受机械映射的跳跃/回退；不由“必须相邻”规则改写 | 状态机单元测试 |

### 3.2 债券方向、关键核心门和代理边界

| ID | 给定 | V1 必须输出 | 首选测试层级 |
| --- | --- | --- | --- |
| `REG-BOND-001` 价格方向 | `000012.SH` 构造稳定上涨与稳定下跌两组价格序列 | 价格涨=债券牛，价格跌=债券熊 | 趋势单元测试 |
| `REG-BOND-002` 收益率反向确认 | 债券价格上涨且可信收益率下降；以及价格下跌且收益率上升 | 确认为一致；收益率方向与债券价格方向相反 | 领域单元测试 |
| `REG-BOND-003` 收益率冲突不替代 | 正式价格牛、收益率确认却显示上行或缺失 | 正式债券状态仍由价格决定，标记确认冲突/缺失 | 集成测试 |
| `REG-BOND-004` ETF 价格不得当收益率 | 输入类似 `141.00` 的债券 ETF 价格或 `yield_proxy` 身份 | 拒绝写入收益率观测，不计算 `141%` 或巨幅 bp 变化 | 适配器契约测试 |
| `REG-CORE-001` P0 缺失优先于总完整度 | 非核心 P1/P2 全部存在，但任一三核心缺失、陈旧、冲突或身份不符 | 正式阶段阻断；总体完整率不能放行 | 门控集成测试 |
| `REG-CORE-002` 核心身份不可互换 | 用沪深300替代中证全指、用收益率/ETF替代国债价格、用 NHCI 或外盘商品替代 NHII | 返回 `metric_identity_mismatch` 或认证缺失；不能完成目标任务 | 适配器 + 门控测试 |
| `REG-CORE-003` 任务与结果身份分离 | 请求在岸即期却返回中间价，或请求一种指数却返回另一指数 | 结果只能作为独立观测；原任务继续缺失/检索，不能被误清除 | 适配器集成测试 |

`REG-BOND-004` 来自旧项目已经发生过的事故模式：`utils/yahoo_finance.py:64-65,89-92` 曾把 `CN10Y/CN10Y_CDB` 映射成 ETF 代理；价格点位若沿收益率字段流入，会产生百分比和 bp 灾难。旧项目后续增加了禁止 ETF 回退的测试，这个“单位与 metric identity 必须绑定”的边界应迁移，但 ETF 转换代码本身不得迁移。

### 3.3 point-in-time、修订和发布周期

| ID | 给定 | V1 必须输出 | 首选测试层级 |
| --- | --- | --- | --- |
| `REG-PIT-001` 月度发布前不可见 | 统计期为 2026-06、`public_available_at=2026-07-15 10:00`；查询时点为 7 月 14 日 | 不返回该观测；如已有上一期且仍在时效规则内，页面显示上一期并标明未发布/数据龄 | 仓储 point-in-time 查询测试 |
| `REG-PIT-002` 公开与系统可用分离 | 已公开于 10:00，但本系统 `available_at=10:05` | public-as-of 在 10:02 可证明已公开，system-as-of 在 10:02 不得假装已采到；10:05 后才可进入本系统结果 | 仓储测试 |
| `REG-PIT-003` 季度数据同规则 | 季度统计期早于真实发布日期数周 | 发布前不前视；发布日期不从季度末或 `report_period` 推断 | 仓储测试 |
| `REG-PIT-004` 修订不改历史 | 8 月发布的修订值更正 6 月数据；重放 7 月报告 | 7 月报告和其证据 snapshot 保持原 vintage；当前页面可显示新版并关联 supersedes | 追加式账本/快照测试 |
| `REG-PIT-005` 同期多次发布 | 同一统计期有初值、复核值或不同公开时刻 | 每次形成独立发布事件和 vintage，查询按 as-of 选当时可见版本 | 仓储测试 |
| `REG-PIT-006` 120 日窗口频率语义 | 报告日向前 120 个中国交易日，期间包含月度和季度发布 | 日频取 120 个交易日；月季频取该交易日窗口内**已发布**观测及必要基线，不要求伪造 120 条值 | 查询/投影集成测试 |
| `REG-PIT-007` 未发布沿用上一期 | 本月数据预计会发布但截至运行时尚无新事件，上一期仍符合对应时效要求 | 展示上一期、统计期、数据龄和预计发布窗口；不得把上一期日期改成当期 | 投影测试 |

发布周期不是固定日历日期，也不能用“每月都会发布”推断值已经可见。预计发布日历只用于延迟检索和提示；P0 若无法证明真实公开时点，必须 fail-closed。旧 `release_calendar.py` 的延迟思想可参考，但其 fail-open 行为不能迁移。

### 3.4 期货换月与收益连续性

| ID | 给定 | V1 必须输出 | 首选测试层级 |
| --- | --- | --- | --- |
| `REG-FUT-001` 零经济收益换月 | 旧合约结算 100，新合约因价差从 110 接续；已知换月调整后经济收益为 0 | 调整收益为 0，30/120 日累计收益和趋势不产生跳变 | 序列单元测试 |
| `REG-FUT-002` 换月元数据缺失 | 通用 `CL=F/GC=F` 价格跳变，但没有实际 `contract_month`、结算口径、roll event、adjustment factor | 该跳变不能进入可认证趋势；标记 `roll_metadata_missing` | 适配器契约测试 |
| `REG-FUT-003` 活跃月身份 | COMEX GC 的活跃月发生切换 | 保存实际合约月、官方结算、切换时间和调整链；页面可追溯到每段合约 | 适配器 + 仓储测试 |
| `REG-FUT-004` NHII 核心不受通用前月污染 | Yahoo/搜索返回的外盘前月与 NHII 同日方向冲突 | NHII 价格状态不变；外盘只作为独立国际 P2 环境证据 | 集成测试 |

### 3.5 故障、重放与报告

| ID | 给定 | V1 必须输出 | 首选测试层级 |
| --- | --- | --- | --- |
| `REG-RUN-001` 事务中断 | Worker 在同批 claim/evidence 未提交前被杀死 | 半批数据不可见；恢复后可幂等重跑 | SQLite 故障注入 |
| `REG-RUN-002` 重复手动触发 | 同一逻辑运行被重复点击或重启恢复 | 使用稳定幂等键/租约，不生成两个权威结果；尝试记录仍可审计 | 编排集成测试 |
| `REG-RUN-003` 陈旧租约回收 | 电脑重启后留下未完成租约 | 能区分活动、死亡和陈旧 owner；只由明确恢复流程接管 | 编排测试 |
| `REG-RUN-004` 离线确定性重放 | 固定原始观测、vintage、日历和规则版本 | 趋势、阶段、投影的结构化结果逐字节或规范化后一致，不联网 | 端到端回放 |
| `REG-RUN-005` CLI 不可用 | Codex/Claude CLI 版本变化、登录失效、超时或配额耗尽 | 结构化驾驶舱仍成功；报告标记降级/失败，不调用 API key 路径 | 子进程适配器测试 |
| `REG-RUN-006` 截止时仍缺 P0 | 人工完整运行在截止时缺关键核心 | 保持运行可恢复/可手动重试，不发布新正式阶段或伪报告 | 编排验收 |

## 4. 旧项目暴露的真实数据与契约缺口

这些缺口不是用旧报告补值的理由，而是 V1 适配器、认证票和失败状态的输入：

1. **正式核心不一致**：旧股票信号用 `000300`，旧债券用 CN10Y 收益率，旧商品用 WTI、Brent、COMEX 铜、现货金和 GSG；都不是冻结的 `000985.CSI`、`000012.SH`、`NHII.NH` 三核心。
2. **收益率代理污染**：CN10Y/CDB 曾存在 ETF 代理路径，价格与收益率单位没有被 metric identity 从入口到存储全程绑定。
3. **期货不是可审计连续链**：通用 Yahoo 前月 ticker 缺实际合约、结算和换月元数据；当前旧工具甚至已整体禁用 Yahoo 外部接口，说明该路径不可作为认证来源。
4. **宏观只有统计期，没有双 as-of**：月季观测缺真实公开时点、系统可用时点与追加 vintage，无法做严格 point-in-time 回放。
5. **结构化来源能力不完整**：旧项目历史根因报告记录过目标身份与返回身份不一致、来源 URL/日期权威在写回时丢失、只拿到 current value 却缺精确比较窗口、缺精确交易日 provider 等问题。
6. **关键数据会正确地拿不到**：旧项目对 RB 指定交易日、官方存准率完整口径、CN10Y_CDB 精确日期等曾出现 fail-closed 结果；V1 必须保留“没有可信值”这一合法结果，不能用估计或近似阶段填平。
7. **整体完整率掩盖 P0**：旧分类器把 `Neutral` 计作第三层有效，随后与宏观、货币层取平均；非核心覆盖率可能掩盖正式核心失败。
8. **历史模块存在大量不可达代码**：旧审计 `optimization/20260610_refactor_plan/audit/AUDIT_RESULTS.md` 记录过 24 个 unreachable 模块。它是迁移排除线索，不是当前代码覆盖真值；任何旧模块都不能因“文件存在”就迁移。

## 5. 可以迁移的接口经验

下表的“迁移”只指重建相同或更严格的行为契约，不授权复制旧 Stage 管线或旧 schema。

| 旧经验 | 可迁移语义 | V1 必须加强的边界 |
| --- | --- | --- |
| `StructuredResult` | provider、规范指标身份、payload、source URL/tier、诊断作为适配器统一结果 | 增加明确 metric identity、单位、venue/session、双 as-of、vintage、内容哈希；结果身份不能从任务 key 猜测 |
| 预写 Pydantic 验证 | 数据先过类型与结构边界再进入权威存储 | 禁止环境变量绕过生产验证；领域不变量不能只靠宽 JSON schema |
| 运行锁的 owner/token 与陈旧检查 | 单写者、租约所有权、compare-before-release、崩溃恢复 | 按已冻结架构落到 SQLite 持久租约，不复制按日目录锁文件 |
| SQLite 追加式 ledger | claim/evidence/gate 追加、纠错用 supersede、未完成事务不成为 current | 使用 V1 的双 as-of、模型版本和不可变报告语义重新设计；不盲拷旧 9 表 schema |
| 内容寻址证据与原子写 | 保存准确字节身份；中断不留下权威半文件 | 原始证据脱敏、大小上限、来源许可和保留策略必须进入契约 |
| 离线 replay fixture | 固定外部响应，断言未录制查询失败，避免测试联网 | fixture 只保存清洗后的来源形状和失败形状；oracle 是 V1 ADR，不是旧 stage/golden |
| 来源 URL 与 source tier | 每个关键声明可追溯；手工证据必须有明确 URL | 不因 URL 文本或 task key 推断官方身份；HTTPS、域名、页面身份和字段语义分别验证 |
| 来源冲突检测 | 同指标多候选时显式发现冲突 | 不直接按权重丢弃其他候选；保存全部 candidate、选择理由和 point-in-time 决策 |
| 发布日历与负缓存 | 未到预计窗口时避免重复检索，节约 Tavily/Exa/AI 预算 | 日历只是调度提示，不能证明已发布；未知或解析失败对 P0 fail-closed |
| 历史根因冻结 | 已失败运行不回写成“通过”，修复后用新实际日期产生新证据 | V1 报告与运行 snapshot 一经发布不可变，恢复形成新 attempt/vintage |

## 6. 绝不迁移的旧代码和语义

以下内容列为明确禁止项：

- Stage1→Stage2→Stage2.5→Stage3→Stage4 的大 JSON 文件接力、按日目录作为权威数据库，以及跨阶段反复 coercion/merge；
- `PringAnalyzer` 的商品技术分/库存分加权、阶段近似匹配、宏观一致性改写、货币/DR007 阶段平移和资产配置生成；
- `Neutral` 既表示缺失、异常、横盘又能进入布尔映射和完整率的三态枚举用法；
- 任何缺失默认 35/40、30/60、50% 权重分或异常默认中性的路径；
- 旧 `000300` 股票核心、CN10Y 收益率核心、ETF 收益率代理、Yahoo 通用前月 ticker 和 WTI/Brent/铜/黄金/GSG 混合商品核心；
- 运行时代理切换、估算值或人工值进入 P0 正式核心；认证后备只能通过新模型版本整体切换；
- 宏观 `report_period/as_of_date/date` 混用、覆盖式更新和无法区分修订 vintage 的宽模型；
- `source_conflicts` 选出一个 winner 后丢失其余候选的覆盖语义；
- `release_calendar` 对未知配置 fail-open 并继续把预计日当可用性的语义；
- 旧报告里的阶段文字、置信度、资产配置比例、推荐、focus assets，以及任何历史报告最终阶段标签；
- `optimization/20260705_pring_signature_lab/signature_engine.py` 的概率模板、softmax、prior 和“总要选一个阶段”的最近模板分类器；它证明旧模型可达性问题，但仍违反非典型组合必须为空的 ADR；
- 旧 DeepSeek/模型 API 路径、读取或注入模型 API key 的代码；V1 只允许调用已登录的本机 Codex/Claude CLI；
- `archive/`、`optimization/` 和静态审计判为不可达的模块，除非后来有独立 V1 规格和测试重新证明其必要性；
- 旧 golden 的最终阶段和报告 prose 作为新版正确性 oracle。

## 7. Fixture 提取边界

后续实施可以从旧项目**人工筛选并脱敏**以下材料作为 fixture 形状参考：

- provider 的成功、空响应、权限不足、日期不符、解析失败、身份不符和来源冲突形状；
- 造成 ETF 价格/收益率混淆、任务/结果身份混淆、current-only 缺比较基线的最小字段集合；
- 期货换月前后原始结算、合约月和调整信息的合成样本；
- 月季发布、系统晚到和后续修订的合成时间线；
- 事务中断、重复触发、陈旧租约和 CLI 超时的合成事件。

不得复制：真实 token、cookie、个人路径、未获许可的证据正文、旧报告全文、旧输出目录、旧缓存、旧日志，或旧 golden 的阶段标签。fixture 应在 V1 仓库中重新命名为规范 metric identity，并附 `fixture_purpose`、来源类别、脱敏说明和对应 `REG-*` ID。

## 8. 对实施验收计划的输入

11 号票完成的定义是“回归目录与迁移边界已冻结”，不是“这些测试已经实现”。后续 12 号实施计划必须满足：

1. 每个 `REG-*` 都分配到具体里程碑、测试文件和验收门；
2. `REG-STAGE-001..007` 在任何 Web、AI、网络适配器接入前先以纯函数测试通过；
3. `REG-PIT-*` 在页面投影和历史回放前以 SQLite point-in-time 查询测试通过；
4. `REG-FUT-*` 在任何期货数据进入可视化或解释前通过；
5. P0 采集、身份、单位、时效或冲突失败时，端到端验收必须证明 `current_stage=null`；
6. 至少保留一组“旧项目会错误通过、新项目必须拒绝”的 characterization fixture；
7. 切换新系统前，确定性离线重放、真实数据影子运行、故障恢复和 CLI 降级均需有独立证据；旧报告不参与准确率打分。

## 9. 旧项目只读证据索引

以下路径均相对于 `/mnt/d/cursor/datasource`：

- `src/datasource/calculators/pring_analyzer.py`：商品评分、三资产信号、Neutral 布尔化、近似阶段、宏观/货币改写；
- `src/datasource/calculators/pring/scoring.py`：宏观与货币缺失按中性计分；
- `src/datasource/models/market_data_contract.py`：旧宽模型及统计期/as-of 字段；
- `src/datasource/engines/stage2/extraction_apply.py`：统计期推断和写回日期；
- `src/datasource/utils/yahoo_finance.py`、`src/datasource/providers/stage2_structured/yahoo_finance.py`：ETF 代理与通用前月缺换月身份；
- `src/datasource/providers/stage2_structured/base.py`：可参考的结构化结果边界；
- `src/datasource/utils/run_lock.py`、`src/datasource/utils/json_io.py`：可参考的租约所有权与原子落盘经验；
- `src/datasource/ontology/ledger.py`、`src/datasource/ontology/repository.py`：追加式 claim/evidence、同批事务和未完成 run 隔离；
- `tests/test_ledger_crash_recovery.py`、`tests/test_ledger_append_only.py`：崩溃和不可变语义测试经验；
- `tests/test_stage2_replay_harness.py`、`tests/fixtures/stage2_replay/`：离线录制/重放经验；
- `tests/test_stage3_logic.py`、`tests/test_stage3_guard.py`、`tests/fixtures/pring_golden/pring_result.json`：需要反转为负向回归的旧期望；
- `docs/verification/report-run-v2/20260729-root-cause-analysis.md`：身份错配、权威字段丢失、provider 能力缺口与冻结失败运行；
- `optimization/20260610_refactor_plan/audit/AUDIT_RESULTS.md`：旧模块可达性审计；
- `optimization/20260705_pring_signature_lab/signature_engine.py`：可达性修复尝试，但分类语义禁止迁移。

