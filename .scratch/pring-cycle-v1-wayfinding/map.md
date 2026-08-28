Label: wayfinder:map
Status: resolved

# 找到 Pring 周期驾驶舱 V1 的可实施路线

## Destination

形成一份可以直接进入编码和验收的 V1 重构蓝图：关键产品、指标、数据源、模型、架构、Markdown 页面契约、运行方式和验收决策均已锁定，不再要求实现者补做产品决策。

## Notes

- 领域上下文以 [Pring 市场周期领域词汇](../../CONTEXT.md) 为准；每次工作先读取相关 ADR、总体规格和本地图。
- 每个 grilling 决策同时使用 `grilling` 与 `domain-modeling`；外部事实研究使用 `research`，且只查一手官方来源。
- 本地图只做决策和必要的决策前验证，不实施最终产品。
- 全程中文交互；不使用 `superpowers`。
- 旧项目 `/mnt/d/cursor/datasource` 只读；旧报告不是数据或真值。
- token、API key 和 `.env` 只允许程序在内存中读取，禁止输出、日志记录、写入仓库或交给 AI。
- V1 覆盖数据采集、严格 Pring 引擎、宏观证据、Web 驾驶舱、检索降级链和 Codex/Claude CLI 报告，但按里程碑实施。
- V1 在 WSL2 运行，通过 Windows 浏览器访问 localhost，不开放局域网；不做登录、多租户、资产配置或买卖建议。
- V1 页面和报告使用“120日证据窗口”：日频取最近120个交易日，月频和季频取该窗口覆盖月份或季度内已发布的观测及必要对比基线；派生计算可读取窗口前预热数据。来源认证前的更长核心价格历史只有在口径和质量通过验收后才能用于离线校准与初始化预热，不能生成认证前的正式版本回放。
- V1 债券核心使用 `000012.SH`；`000012CNY030.CSI` 与 `930916.CSI` 只确认，未来通过新模型版本迁移财富指数。
- V1 为 TuShare 缺失的政策行动、核心 CPI、工业增加值/利润/库存/产能、信用结构和官方在岸汇率接入官方可信来源；高频产业实物库存分批补充。
- 实现前冻结 V1 指标目录；新增指标进入后续模型版本。
- 当前只输出 Markdown 页面与只读投影契约；Web 视觉和交互原型待其他开发完成后单独设计。
- 早期`.scratch/pring-cycle-dashboard`规格与实现票先于本地图收口，必须先经`/to-spec`与`/to-tickets`重写，不得直接进入实现。
- 以手动完整运行为主；自动盘后运行默认关闭。宏观发布先更新结构化页面，完整报告只在手动触发或显式启用的盘后运行中生成。
- 检索遵循本地证据、TuShare、认证官方直连、Tavily、Exa、受限 AI WebSearch 的顺序；减少 WebSearch，Tavily 预算耗尽再用 Exa。

## Decisions so far

<!-- 决策只在对应已解决票中保存；本图只追加一行摘要和链接。 -->

- [核验关键缺口的官方数据源、字段与可用时点](issues/01-verify-official-gap-sources.md) — PBOC/NBS官方直连可覆盖主要政策、核心CPI、工业与信用缺口；16:30在岸收盘价须授权，短历史和口径变化必须显式治理。
- [冻结 V1 指标目录与证据角色](issues/02-freeze-v1-metric-catalog.md) — 采用120日证据窗口和有限角色白名单，冻结中国核心/确认/宏观指标及纽约金、伦敦金、原油、美债、VIX、SOX国际环境口径。
- [认证三类核心资产的历史覆盖与连续性](issues/03-certify-core-asset-history.md) — 三核心数值历史完整覆盖120日、240日预热与2006年以来共同样本；股票和债券通过，NHII仍须完成全历史无生猪语义认证，后备仅进入认证流程而不运行时切换。
- [确定 point-in-time 证据模型与修订语义](issues/04-decide-point-in-time-evidence-model.md) — 采用公开/系统双as-of与追加式vintage，冻结来源声明、规范观测、发布事件、时效、冲突、查询及不可变报告快照语义。
- [确定 WSL2 单机技术架构](issues/05-decide-local-technical-architecture.md) — 采用WSL原生XDG状态、SQLite WAL与内容寻址制品、FastAPI + Dash单Web进程、SQLite任务账本与独立单Worker；不用Redis、Celery、WebSocket、Node、Docker或Sites。
- [核验 NHII 全历史成分与方法版本](issues/13-certify-nhii-historical-constituents.md) — 官方权重链证明NHII全区间无生猪；当前窗口通过，严格校准从2018-06-01起，早期仅作敏感性且不触发后备。
- [校准 120 日趋势状态机与稳定性门槛](issues/06-calibrate-120d-trend-state-machine.md) — 暂定采用1.5σ波动噪声带、8日持续与20日均线斜率；冲突保留原状态，30日和12M独立，实际测试后的调整必须版本化。
- [验证检索降级链的预算与缓存参数](issues/07-validate-retrieval-budgets.md) — 按发布事件串行执行Tavily→Exa→受限AI；冻结单事件1/1/1、单运行8/4/1、每日16/8/2预算，P2禁用AI，并采用负缓存、联合发布合并和报告AI硬隔离。
- [定义 Markdown 页面与只读投影契约](issues/08-define-markdown-page-contracts.md) — 分域数据集组成原子分析投影集，报告/运行状态独立关联版本；冻结共同包络、资产扩展、宏观与库存独立状态、历史空档、故障语义和证据追溯，不涉及视觉设计。
- [验证双 AI CLI 的证据报告协议](issues/09-prototype-ai-report-contract.md) — Ubuntu实测证明Codex/Claude可消费共同证据协议；冻结CLI-only认证、默认Codex单次替代、300秒超时、确定性事实骨架、降级完成和不可变快照边界。
- [定义刷新编排、幂等与故障恢复模型](issues/10-decide-refresh-and-recovery-model.md) — 采用手动完整运行优先、默认关闭自动盘后、SQLite持久父运行与显式恢复；冻结P0门槛、幂等租约、深搜、重试、投影先行和报告日限额。
- [提取旧项目回归场景与迁移边界](issues/11-extract-legacy-regression-cases.md) — 只读审计冻结35个行为级回归案例；只迁移接口与运行语义，明确禁止迁移旧Stage流水线、评分/近似分类、宏观改写、代理核心和旧报告真值。
- [确定本地备份、恢复与保留上限](issues/14-decide-local-backup-retention.md) — V1主动不备份运行数据且不保证RPO/RTO；GitHub只管源码，主存储按7/14/30天及20/10/5GiB水位清理降级，权威血缘和被引用证据长期保留。
- [确定模型版本升级、历史重算与可比性边界](issues/15-decide-model-version-migration.md) — 模型采用原子不可变清单与认证后并行回放，发布历史永不覆盖；候选显式验收后生效，来源认证前历史仅作校准/预热，上一生效版本保证30个中国交易日内可逻辑回退。
- [锁定 V1 实施顺序与验收计划](issues/12-lock-implementation-and-acceptance-plan.md) — 采用七个逐步可运行里程碑与逐门验收，冻结P0/P1/P2、35项回归、性能资源、文档、真实演练和无强制绕过的单向系统切换条件。

## Not yet specified

- 无。前端视觉系统与交互细节已明确排除在本地图之外，应作为独立后续工作。

## Out of scope

- 登录、权限、账号、多租户以及公网或局域网部署。
- 资产配置权重、买卖建议、收益承诺和让 AI 改写正式阶段。
- 用旧报告作为正确标签，或逐文件复制旧项目流水线。
- V1 指标目录冻结后的临时新增指标；应进入后续模型版本。
- 当前阶段制作高保真 Web 视觉或交互原型；用户已决定在其他开发完成后单独设计。
- 十年全市场广度回填；V1只输出最近120个交易日的广度历史，并保留计算所需预热数据。
