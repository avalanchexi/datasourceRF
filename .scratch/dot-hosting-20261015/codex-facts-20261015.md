# 取证：ChatGPT dots 的平台能力与本项目前提（2026-10-15）

由 `codex exec -s read-only` 联网核对，未实测。『未查到』不等于不支持。

截至 **2026-10-15**，已联网核对官方文档，并只读查看仓库说明，未修改任何文件。**dots 确于 2026-09-29 发布**。下文『官方』表示有官方资料支持；跨文档推导会明确注明；『未查到』不等于“不支持”。本次主要问题均有官方资料，无须用第三方报道代替。出处：[发布文章](https://openai.com/index/introducing-dots/)。

**1．本机执行：Windows、WSL2、客户端与离线**

| 问题 | 核查结果与出处 |
|---|---|
| 支持 Windows 吗？ | **『官方』支持 Windows 桌面客户端。** dot 可通过该客户端连接本机，创建本地 Work/Codex 任务。[dot 入门](https://help.openai.com/en/articles/20001530-getting-started-with-your-dot) |
| 能进入 WSL2 执行 shell/Python 吗？ | **『官方，组合推导』存在受支持的执行路径：dot → 本地 Codex 任务 → WSL2。** Windows 文档明确支持通过 `wsl` CLI 操作 WSL2，也可在设置中将 agent 切换到 WSL，重启应用生效。Python 需在对应环境安装。**未查到 dot 专门承诺该完整链路的兼容性说明，本次也未实测。** [Windows/WSL2 文档](https://learn.chatgpt.com/docs/windows/windows-app)、[dot 本机任务](https://learn.chatgpt.com/docs/dots/computers-and-apps) |
| 装什么客户端？ | **『官方』在目标电脑安装 ChatGPT 桌面应用**，进入 dot 的 Computers → Your computer → Allow access。仅连接 Codex 或开启 Work Sync，不会自动授权 dot。[连接步骤](https://learn.chatgpt.com/docs/dots/computers-and-apps#connect-your-computer) |
| 电脑离线怎么办？ | **『官方』本机任务要求电脑在线、ChatGPT 应用保持打开。** 离线时本机不可用，但连接授权不会自动撤销；dot 自己的云端工作仍可继续。不能据此认为本地文件、数据库和进程会自动搬到云端。[电脑连接与离线行为](https://learn.chatgpt.com/docs/dots/computers-and-apps) |

**2．能否周期执行？**

**『官方』可以，既支持保存的周期计划，也支持持续目标和部分事件触发。** 官方明确提供 recurring tasks，要求指定任务、时间、时区、通知条件及结果去向，并可在 Scheduled 中检查或修改。[任务与记忆](https://learn.chatgpt.com/docs/dots/tasks-and-memory#recurring-tasks)

因此可以要求“北京时间 09:30 后检查”。但 **『未查到』内建上交所交易日历、准点执行 SLA、漏跑补偿或严格一次执行保证**。工程上应让计划触发后查询项目交易日历，再由程序决定是否执行；“每个工作日”不能直接等同“每个交易日”。这是基于上述能力边界的判断。

**3．Codex 云环境：仓库、密钥、第三方 API**

| 问题 | 核查结果与出处 |
|---|---|
| 必须 GitHub 吗？ | **『官方』当前标准创建流程要求选择 GitHub 仓库并连接 GitHub**；GitLab、自托管 GitHub Enterprise Server 列为暂不支持。**『未查到』无需任何仓库即可创建该类环境的明确说明。** 这不代表 dot 自己的云电脑必须绑定仓库。[云环境创建与限制](https://learn.chatgpt.com/docs/environments/cloud-environments) |
| 私有仓库可以吗？ | **『官方』可以使用获授权的私有仓库。** GitHub App 必须获准访问该仓库，组织可能要求管理员批准；共享环境不替代个人仓库权限。[GitHub 私有仓库授权](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)、[Codex Cloud 权限](https://help.openai.com/en/articles/20001545-using-codex-cloud) |
| secrets/env 可以配置吗？ | **『官方』可以。新版提供直接环境变量及 Network secrets**；后者向程序提供占位值，由代理在允许的 HTTPS:443 请求中替换真实凭据，覆盖准备和任务阶段。[配置说明](https://learn.chatgpt.com/docs/environments/cloud-environments#environment-variables-and-secrets) |
| 可以调用第三方 API 吗？ | **『官方』可以配置联网和域名允许列表。** 可把 `api.tushare.pro` 作为所需主机配置；还需满足凭据、请求协议及服务方权限。**『未查到』OpenAI 对 TuShare 的专门兼容性保证，本次未实际调用。** [网络配置](https://learn.chatgpt.com/docs/environments/cloud-environments#connect-to-services) |

需特别区分：**『官方』旧版 Codex Cloud（Legacy）的 secrets 仅在 setup 阶段可用，agent 阶段会移除；普通环境变量贯穿任务。** 不能把这个旧规则套在新版 Network secrets 上。[Legacy 文档](https://learn.chatgpt.com/docs/environments/cloud-environment#environment-variables-and-secrets)

**4．自建服务、MCP 与公网 HTTPS**

**『官方』可以通过受支持的插件连接服务。** dot 使用账号已安装、启用并授权的插件；ChatGPT 支持将自建 MCP server 添加为插件。由这两份文档可推导自建服务的接入路径，但具体工具仍受账号、工作区和执行环境限制。[dot 插件接入](https://learn.chatgpt.com/docs/dots/computers-and-apps#connect-apps)、[自建 MCP 接入](https://developers.openai.com/plugins/deploy/connect-chatgpt)

**“自建插件一律必须公网 HTTPS”不准确：**

- **『官方』直接远程接入：**使用可访问的公网 HTTPS MCP 端点。
- **『官方』私有服务：**可用 **Secure MCP Tunnel**，在内网运行 `tunnel-client`，主动向 OpenAI 发起 HTTPS 连接；服务本身无须开放公网入站端口。需要 Platform tunnel 权限、运行密钥及工作区关联，客户端须持续在线。
- **『官方』公开提交插件目录：**仍要求稳定、公开可达的 HTTPS MCP 端点，Secure MCP Tunnel 不替代这一要求。

出处：[连接方式与提交区别](https://developers.openai.com/plugins/deploy/connect-chatgpt)、[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)。

**5．提交、文件、消息的审批模型**

**『官方』审批由用户指令、应用权限、自定义规则、自动审查及内置安全要求共同决定，并非每次写操作都必须点击批准。** 自定义规则可设置自动执行、明确要求时执行、每次询问或交还用户；规则不会授予本来没有的服务访问权，也不能覆盖内置要求。[dot 控制规则](https://learn.chatgpt.com/docs/dots/controls)

| 动作 | 结论 |
|---|---|
| 修改文件、Git commit、push、创建或合并 PR | **『未查到』dot 对这些动作逐项统一的“必批/免批”清单。** 应分别按授权范围、执行环境和 GitHub 权限判断；不能声称每次提交必批，也不能把允许改代码理解为允许发布或合并。[动作审查规则](https://learn.chatgpt.com/docs/dots/controls#how-action-review-works) |
| 发送消息 | **『官方』草拟不等于允许发送。** 明确范围的周期消息可预先批准；一次批准不授予无限期联系他人的权限。[安全 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs) |
| 永久删除、安装软件 | **『官方』可能需要每次批准。** [安全 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs) |
| 改密码、转账 | **『官方』需要用户接管并亲自完成。** [安全 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs) |
| 自发后台研究 | **『官方』研究工具只能读，不能直接发消息、修改应用或控制电脑。** 已授权的后台任务另按其授权执行。[后台研究边界](https://learn.chatgpt.com/docs/dots/tasks-and-memory#proactive-research) |

**6．数据、记忆，以及 Business 与 Pro**

**『官方』dot 云电脑有独立文件、软件和浏览器会话，并能跨使用时段保留状态。** 本机登录和数据不会自动继承过去。[云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps#use-the-cloud-computer)

**『官方』dot 的上下文可随 dot 长期保留，来源包括对话和插件。** 关闭 ChatGPT Memory 或断开插件不会清除已经获得的信息；目前不能逐条查看、修改或删除 dot 自身记忆，需要删除 dot。另存的文件、Codex 线程及 ChatGPT 对话须分别管理。[隐私 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs)

| 维度 | Business 工作区 | Pro 个人账号 |
|---|---|---|
| 模型训练 | **『官方』默认不用于训练。** | **『官方』由 “Improve the model for everyone” 控制，开启时符合条件的对话和工作可能用于训练。** |
| 对话保留 | **『官方』Business 隐私说明称工作区管理员可控制保留时间；删除后通常在 30 天内从系统移除，有法定或安全例外。** | **『官方』普通对话通常保留至用户删除；删除后通常在 30 天内移除，同样有例外。** |

训练出处：[dots 发布说明](https://openai.com/index/introducing-dots/)；Business 保留出处：[企业隐私页的 Business FAQ](https://openai.com/enterprise-privacy/)；个人对话出处：[聊天与文件保留政策](https://help.openai.com/en/articles/8983778-chat-and-file-retention-in-chatgpt)。

**『官方』主动研究及其私人笔记不直接用于训练，但进入符合条件的对话或任务后，会按数据设置处理。** “不训练”不等于“不存储”。[数据控制](https://learn.chatgpt.com/docs/dots/controls#manage-data-settings)

**『未查到』dot 专属云磁盘在 Pro/Business 下分别保存多少天，以及删除 dot 后整台云电脑数据的精确清除期限。** Codex Cloud 的“最后活动后最多七天恢复 VM 状态”是另一产品规则，不能套用到 dot 云电脑或记忆。[Codex VM 恢复规则](https://help.openai.com/en/articles/20001545-using-codex-cloud)

**结合本仓库：真正需要补齐的运行前提**

以下属于**仓库事实及工程推断**，不冒充 OpenAI 官方结论；未读取真实 token 或数据库内容。

| 仓库前提 | 对 dot 的实际影响 |
|---|---|
| **WSL2、uv、Python 3.12、原生 Linux 文件系统。** 虚拟环境采用 `--no-editable`，源码变化后须重装。[说明第 5 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:5) | 连接 Windows 不足以保证运行正确；必须选对 WSL 发行版、用户、虚拟环境及安装副本。WSL2 有官方执行路径，问题是配置与验证。 |
| **只监听 `127.0.0.1:8050`，校验 Host/Origin，没有局域网监听配置。** [第 121 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:121) | dot 云电脑的 localhost 指向它自己，不能直达本机服务。须走本地任务，或另外配置私有桥接；简单转发还可能碰到 Host/Origin 限制。 |
| **数据库与制品在 WSL 的 `${XDG_DATA_HOME:-$HOME/.local/share}/pring-cycle/`，并依赖 SQLite/WAL、迁移和初始化。** [第 57 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:57) | GitHub 克隆只取得源码，不会取得本机历史数据库、证据和报告。新云任务也不会自动共享这些运行状态。 |
| **仓库外 `secrets.env`、权限 `0600`，包括 `TUSHARE_TOKEN`。** [第 84 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:84) | dot 不会自动获得凭据；云环境支持 secrets，也仍需适配项目的文件读取方式。缺少凭据不阻止离线启动，但相关取数能力会禁用。 |
| **Web 与 Worker 是独立进程。** [第 109 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:109) | dot 云端常驻不能替代本地 Worker 常驻；电脑休眠、WSL 停止或本机不可达时，无法继续依赖本地运行库的工作。 |
| **项目已有交易日调度，默认关闭。** 启用后按上海时区在交易日 09:30–21:00 首次检查提交上一交易日任务，带幂等及日历缺口重试。[第 411 行起](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:411) | 无须让 dot 重新解释交易日和补跑规则。更合适的是调用、检查项目已有调度与运行状态，避免重复实现。 |
| **AI 搜索及报告依赖本机 CLI；报告先尝试已登录的 Codex/Claude Code，失败则生成确定性简版。** [搜索第 373 行](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:373)、[报告第 435 行](/mnt/d/cursor/datasourceRF/docs/development/local-runtime.md:435) | dot 订阅或云任务不会自动补齐 WSL 内 CLI 安装与登录；这些也需单独配置。 |

dot 支持周期任务和 Windows 本机连接，WSL2 可通过其委派的本地 Codex 路径使用，但尚未实测本项目。  
本项目的关键约束是本机持续在线、WSL 运行状态、localhost 服务、数据库与凭据，而非缺少定时能力。  
自建 MCP 可用公网 HTTPS 或私有 Tunnel；Business 默认不训练，但仍需管理数据保留。  
按现有文档判断，最贴合项目的方式是让本地 Worker 执行，让 dot 负责检查、协调和汇报。
