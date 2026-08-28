Type: grilling
Status: resolved
Blocked by: none

# 确定 WSL2 单机技术架构

## Question

在“WSL2 后端、Windows 浏览器访问 localhost、无登录、长报告异步生成”的边界内，选择什么 Python Web 框架、持久化方案、后台任务机制、调度方式、前端交付方式和本地启动/升级方式？决策必须保证核心分类无网络可测、无需 Redis 等不必要基础设施、应用在缺少外部凭据时仍可启动，并为后续视觉前端保留稳定 API 或只读投影。

## Answer

V1采用[《WSL2 单机技术架构》](../assets/wsl2-local-technical-architecture.md)：Python 3.12与`uv`锁定依赖；SQLite WAL保存唯一结构化真值，大对象进入内容寻址目录；FastAPI + Plotly Dash共用一个localhost Web进程，独立单Worker通过SQLite持久任务账本执行长任务，两个进程由systemd用户服务监督。页面通过`dcc.Interval`自适应轮询只读投影，不使用Redis、Celery、WebSocket、Node.js、Docker或Sites。

运行数据库、制品、密钥和日志位于WSL原生XDG目录；缺少外部凭据时系统降级启动。统一CLI承担初始化、诊断、服务、迁移、补跑和一次性白名单密钥迁移。后续[《本机无备份与主存储保留策略》](../assets/local-no-backup-and-retention-policy.md)取消了通用备份命令、升级前快照和恢复保证；升级失败允许空库重建。架构取舍记录在[ADR-0007](../../../docs/adr/0007-wsl2-sqlite-worker-and-dash-fastapi.md)，无备份取舍记录在[ADR-0011](../../../docs/adr/0011-no-runtime-backups.md)。

## Comments

### 2026-08-20 第一轮

- Q64 已确认：SQLite WAL 保存结构化证据、任务、阶段和快照；原始网页、搜索响应、AI报告等大对象保存到本地内容寻址目录，不引入第二个权威数据库。
- Q65 已确认：FastAPI Web 服务与后台 Worker 分进程；任务状态持久化到 SQLite，不引入 Redis/Celery，也不把长任务放进 Web 进程生命周期。
- Q66 已确认：systemd 管理 WSL2 内服务，Windows 任务计划程序负责定时唤起；错过的计划由持久任务账本在下次可用时补跑。
- Q67 已确认：本地 Python Web/API 基线采用 FastAPI 和版本化 REST 接口，核心分类保持无网络可测。
- Q63 待重述：用户明确希望使用 Codex 的 Sites 能力。官方文档显示 Sites 是独立托管环境，支持静态至全栈 JavaScript/TypeScript及D1/R2，但不能假定其可运行本地Python、访问localhost或承担任意后台服务。因此需先决定本地权威后端、Sites投影、同步及访问边界，再锁定运行与依赖管理。

### 2026-08-20 第二轮

- Q68 已确认：WSL2 是唯一权威后端，负责证据获取、SQLite、Pring识别、调度和AI CLI；Sites只保存并展示版本化只读投影，不成为证据或阶段的第二权威来源。
- Q69 已确认：Sites保持所有者私有，不开发项目级登录、账号或权限模块；OpenAI托管平台的所有者访问不属于本项目身份域。

### 2026-08-20 第三轮

- Q70 已确认：Sites采用TypeScript/React全栈形态和D1，只保存本地生成的版本化只读投影；站点运行时不接触TuShare、检索或AI CLI凭据。
- Q71 已确认：Sites是主要阅读界面；localhost保留精简的运行状态、故障诊断、手动刷新、同步状态和只读后备页面，不维护第二套完整视觉前端。
- Q72 已确认：单仓库双运行时，WSL2使用`uv + Python`，Sites使用`Node.js + npm + TypeScript`，不引入Docker。

### 2026-08-20 第四轮

- Q73 已确认：源码可留在`/mnt/d`，但SQLite、任务账本、内容仓库和运行状态位于WSL2原生文件系统的应用数据目录，不能把WAL数据库放在Windows挂载盘。
- Q74 已确认：Sites同步通过独立`ProjectionPublisher`接缝；新增兼容性原型完成所有者私有Site的机器认证、签名推送、D1事务、大小和限额验收前，不启用自动同步，也不暴露本地FastAPI。
- Q75 已确认：SQLite使用SQLAlchemy 2和Alembic；Pydantic负责边界校验，不把API模型当成持久化模型。
- Q76 已确认：采用单仓库，Python核心包与`apps/api`、`apps/worker`、`apps/site`和版本化`contracts`分层；具体目录名可在实施时等价调整，但边界不可合并。
- Q77 已确认：应用拥有SQLite持久任务账本与单Worker循环；systemd只监督进程，Windows任务计划程序只负责唤起，不采用Celery、Redis、APScheduler或cron脚本流水线。

### 2026-08-20 范围修正

- 用户决定V1暂时放弃Codex Sites，未来如重新启用必须作为新决策重新认证，不沿用本票中的临时假设。
- 第二、三轮中关于Sites作为私有主要阅读界面、TypeScript/React、D1和双运行时的Q68–Q72结论被本次范围修正取代，不进入V1架构。
- 第四轮Q74所述Sites兼容性原型不再创建；V1不实现`ProjectionPublisher`、机器推送、D1同步或Sites密钥。
- WSL2是V1唯一权威运行环境，localhost是唯一Web交付面；项目只保留与具体前端无关的版本化只读投影契约。
- Q72重开：V1是否需要Node构建链以及localhost前端交付方式，须按本地Web边界重新决定。

### 2026-08-21 第五轮（部分确认）

- Q84按用户要求完成当前轻量前端调研，结论见[《Pring周期驾驶舱本地前端方案调研》](../../../docs/research/local-dashboard-frontend-options.md)；方案待用户最终选择。
- Q85 已确认：Worker承担证据、阶段、报告和投影等业务写入；Web只读并允许短事务追加任务请求，不运行长写事务。
- Q86 已确认：外部凭据缺失时应用仍启动；适配器标记禁用，历史与无网络模型可用，缺失P0时不产生新正式阶段。
- Q87 调整为从只读旧项目`/mnt/d/cursor/datasource`安全迁移配置与密钥；已仅核实旧项目存在`.env`和`.env.example`及相关键名位置，未读取、输出或复制任何值。迁移白名单、目标位置与一次性语义仍待确认。
- Q88 已确认：V1暂不需要公网，FastAPI仅绑定`127.0.0.1`，不开放局域网、反向代理或公网隧道。
- Q89 已确认：统一项目CLI管理初始化、诊断、启动、停止、状态、迁移与备份；升级显式执行并在迁移前备份，不自动联网升级。

### 2026-08-21 Dash方向调整

- 用户选择尝试Plotly Dash，不冻结此前推荐的Jinja2/htmx页面层。
- 补查官方文档确认Dash 4.2已原生支持FastAPI后端、已有FastAPI服务器、多页路由、低频轮询和pytest测试；因此原型不需要Flask/WSGI桥接，也不改变Q67的FastAPI决定。
- Dash只承担页面和图表交互：回调读取只读投影、追加短任务命令并轮询SQLite任务账本；禁止使用Dash后台回调、DiskCache、Celery或Redis运行采集和AI任务。
- Q84当时曾重述为先做Dash原型；该建议已被下一轮“原型延后到当前Wayfinder全部结束后”取代，因此不在本地图创建原型票。

### 2026-08-21 第六轮

- Q84 已调整确认：计划采用Plotly Dash作为本地页面层；原型、页面外观和视觉交互设计推迟到当前Wayfinder全部完成后单独进行，不在当前地图新增原型票。
- Q90 已确认：旧项目只迁移新项目白名单需要的`TUSHARE_TOKEN`、`TAVILY_API_KEY`和`EXA_API_KEY`；不迁移DeepSeek、旧Stage参数或其他未声明键。Codex CLI与Claude Code CLI继续使用各自认证。
- Q91 已确认：由一次性项目命令从只读旧`.env`解析白名单，原子写入仓库外WSL配置目录并设置`0600`；命令、日志、错误和报告均不得回显值，迁移后新项目不再依赖旧文件。
- Q92 已确认：Dash 4.2使用原生FastAPI后端，与版本化REST API共用同一进程和端口，不另起Flask/WSGI或第二Web服务。
- Q93 当时选择WebSocket；该选择已在第七轮重开并由第八轮的自适应轮询最终结论撤销。
- Q94 已确认延后：Dash原型和视觉设计待Wayfinder全部结束后作为单独工作开展，本票只冻结技术接缝。

### 2026-08-21 第七轮（部分确认）

- 用户重新质疑Q93/Q95：在盘后与低频数据、单用户和长报告场景中，WebSocket并非必要；若为跨进程推送引入Redis，会增加服务、持久性、恢复、升级和测试边界。Redis最多替换通知通道，不能替换SQLite中的证据、任务、阶段和快照真值。Q93与Q95重开。
- Q96 已确认且独立于传输方式：页面任何时候都从SQLite中的最新完整只读投影恢复，通知或轮询结果不是真值。
- Q97 已确认：Dash回调只能查询只读投影，或用幂等键追加短任务命令；不得直接采集、分类或运行AI CLI。
- Q98 调整确认：页面视觉在当前Wayfinder结束后使用Open Design单独设计；当前不启动设计流程。最终Dash CSS、图标、字体与其他静态资源仍锁定版本并本地提供，不依赖运行时CDN。
- Q99 已确认：AI Markdown禁止原始HTML和脚本，只渲染安全Markdown及经过验证的来源链接。

### 2026-08-21 第八轮

- Q93/Q95 最终确认：撤销WebSocket，不引入Redis或通知Outbox。Dash通过`dcc.Interval`自适应轮询SQLite只读投影：有活动任务时默认30秒，无活动任务时默认5分钟或暂停，重新打开页面立即读取，另提供手动刷新。
- Redis不进入V1。它不能替代SQLite的证据、任务、阶段与快照真值；为低频单用户页面单独引入Pub/Sub或Streams不具备足够收益。

### 2026-08-21 第九轮

- Q100 已确认：Python 3.12，由`uv`固定解释器与依赖并提交`uv.lock`；V1不引入Node.js。
- Q101 已确认：配置、数据、状态和缓存遵循XDG目录并位于WSL原生文件系统，仓库不保存运行状态。
- Q102 已确认：`pring-web.service`与`pring-worker.service`使用systemd用户服务并启用linger；Windows任务计划程序只唤醒WSL并调用持久账本补跑入口。
- Q103 已确认：升级人工显式执行，迁移前预检并创建一致性备份；失败恢复匹配版本的代码和数据库备份，不依赖Alembic降级。
- Q104 已确认：本地轮转JSONL日志以`run_id/job_id`关联并强制脱敏；证据审计仍在SQLite，密钥永不进入日志。
- Domain Modeling复核未发现需要新增的业务术语；SQLite、Dash、systemd与XDG属于本票技术实现，不写入`CONTEXT.md`。

### 2026-08-24 备份范围修正

- 后续“确定本地备份、恢复与保留上限”决策推翻Q89和Q103中的备份部分：V1不提供通用备份命令，不建立日常、Windows侧、升级前、密钥或其他运行数据副本。
- GitHub只管理源码与静态定义；SQLite、内容寻址制品、报告、日志和密钥不进入仓库。数据损坏或迁移失败时允许空库重建，RPO/RTO均不保证。
- Q89关于统一CLI管理初始化、诊断、启动、停止、状态和迁移以及“不自动联网升级”的其余部分继续有效；Q103关于人工显式升级、预检和前向迁移的其余部分继续有效。
