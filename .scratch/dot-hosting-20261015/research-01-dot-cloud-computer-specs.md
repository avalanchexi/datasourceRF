# 取证：dot 云电脑的规格与对外访问（2026-10-15）

由 `codex exec -s read-only` 只查一手官方来源，未操作真实 dot 云电脑。解决 [票 01](issues/01-dot-cloud-computer-specs.md)。

调查日期：**2026-10-15**。已按顺序读取问题文件及已有取证，复用既有结论，仅补查官方文档；未修改任何文件、未操作实际 dot 云电脑。**『未查到』表示未找到明确官方说明，不等于不支持。** 下表中此类条目的链接是核查入口，不是“不支持”的证据。未采用第三方资料。

| 问题 | 结论 | 标注『官方/第三方/未查到』 | 出处 URL |
|---|---|---|---|
| 操作系统 | 未查到 dot 云电脑的操作系统、发行版、版本及 CPU 架构规格；不能把本地客户端支持的系统或 Codex Cloud 镜像当成 dot 的系统。 | 『未查到』 | [dot 云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps#use-the-cloud-computer) |
| 可运行、安装哪些软件 | 官方说明可在云电脑运行软件，并拥有独立的软件环境；已有取证说明安装软件可能需要批准。未查到完整软件兼容清单、管理员权限或系统包安装权限。 | 『官方』运行软件；其余『未查到』 | [Meet dots](https://learn.chatgpt.com/docs/dots)、[安全 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs) |
| 能否安装 Python 3.12、uv | 未查到对这两个软件及指定版本的明确支持说明；是否预装、能否自行安装、安装后能否保留，均待实测。 | 『未查到』 | [dot 云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps) |
| 磁盘容量 | 未查到 Pro 下 dot 云电脑的磁盘总量、可用量、配额或扩容规则。**Pro Library 的 100 GB 不能解释为云电脑磁盘容量。** | 『未查到』 | [dot 云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps)、[Library 配额](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt) |
| 单文件上传上限 | 普通 ChatGPT/GPT 对话附件有 **512 MB/文件**硬上限；文本与文档另有 200 万 token 限制，表格约 50 MB、图片 20 MB。**未查到 dot 云电脑直接传文件的独立上限或是否沿用这些规则。** | 『官方』普通附件；dot 直接传输『未查到』 | [Library 文件限制](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt)、[上传说明](https://help.openai.com/en/articles/8555545-uploading-files-and-audio-to-chatgpt) |
| 总上传大小、存储及频率上限 | 上传 FAQ 写明共享上传存储 **25 GB/用户、100 GB/组织**，上传频率最多 **80 文件/3 小时**，高峰期可能降低；Library 文档另列 **Pro 100 GB**。两页未充分解释这些配额的关系，不能合并成一个 dot 配额。未查到 dot 专属累计上传或单批总大小上限。 | 『官方』所列通用配额；dot 专属限制『未查到』 | [上传配额](https://help.openai.com/en/articles/8555545-uploading-files-and-audio-to-chatgpt)、[Pro Library 配额](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt) |
| 能否常驻后台进程 | 官方支持 dot 在用户设备关闭后继续工作、处理后台任务。**未查到任意用户进程可以持续运行、守护进程托管或连续运行时长的保证。** “always-on agent”不足以证明 Worker 永不停止。 | 『官方』后台任务；进程常驻『未查到』 | [Meet dots](https://learn.chatgpt.com/docs/dots)、[云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps) |
| 空闲或会话结束后，进程是否回收 | 未查到空闲超时、休眠、进程终止、重启或自动恢复的明确规则。任务跨对话继续，不足以证明同一个操作系统进程持续存活。 | 『未查到』 | [任务与记忆](https://learn.chatgpt.com/docs/dots/tasks-and-memory)、[云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps) |
| 空闲或会话结束后，文件是否回收 | 复用已有结论：云电脑**可跨使用时段保留状态**，有自己的文件、软件及浏览器会话。未查到持久化目录清单、临时目录清理规则、空闲回收时间及文件恢复保证。 | 『官方』状态保留；具体回收规则『未查到』 | [云电脑状态](https://learn.chatgpt.com/docs/dots/computers-and-apps#use-the-cloud-computer) |
| 能否开放端口、分享运行中的网页 | 未查到 dot 云电脑的入站端口、端口转发、公网 IP、预览 URL 或持续网页托管机制。官方提供查看云电脑及 **Take over** 接管；这不能证明可把 Dash 服务链接交给用户本地浏览器直接访问。 | 『未查到』端口及网页发布；『官方』接管电脑 | [云电脑查看与接管](https://learn.chatgpt.com/docs/dots/computers-and-apps#use-the-cloud-computer) |
| 时区设置 | 复用已有结论：周期任务可以明确指定时区。未查到云电脑操作系统及浏览器的默认时区、修改入口、修改权限和跨会话保留规则。 | 『官方』任务时区；系统及浏览器时区『未查到』 | [周期任务](https://learn.chatgpt.com/docs/dots/tasks-and-memory#recurring-tasks) |
| 联网能力 | 官方说明云浏览器可访问网站，部分网站可能阻挡云浏览器。Enterprise 文档还明确描述 dot 的代码和 shell 联网能力，但其管理员设置不能直接套用于个人 Pro。未查到 Pro 的完整出站协议、端口和代理规格。 | 『官方』浏览器及产品联网能力；Pro 详细规格『未查到』 | [网站访问](https://learn.chatgpt.com/docs/dots/computers-and-apps)、[云网络能力说明](https://help.openai.com/en/articles/20001554-manage-dots-in-chatgpt-workspaces) |
| 域名限制、`api.tushare.pro` | 未查到 Pro dot 云电脑的域名允许/拒绝清单、用户配置入口，或对 `api.tushare.pro` 的可达性保证。已有取证中的 Codex Cloud 域名配置能力属于另一执行环境，不能移用。 | 『未查到』 | [dot 云电脑说明](https://learn.chatgpt.com/docs/dots/computers-and-apps)、[Codex Cloud 网络配置，仅用于区分](https://learn.chatgpt.com/docs/environments/cloud-environments#connect-to-services) |
| 数据保留期限 | 复用已有结论：dot 上下文可随 dot 保留，删除 dot 可删除其上下文；其他位置的文件按相应位置管理。普通个人聊天通常保留至删除，删除后通常在 30 天内清除，有例外；Library 文件须单独删除。**未查到 dot 云磁盘保存多少天，以及删除/reset dot 后整盘数据的精确清除期限。** | 『官方』上下文及通用保留政策；云磁盘期限『未查到』 | [dot 隐私 FAQ](https://help.openai.com/en/articles/20001529-dots-privacy-security-and-safety-faqs)、[聊天与文件保留](https://help.openai.com/en/articles/8983778-chat-and-file-retention-in-chatgpt)、[Library 删除规则](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt) |

**对本项目的含义**

以下为结合项目需求的工程判断，不是 OpenAI 的产品承诺。

1. **常驻 Worker 的部署前提尚未证实。** dot 能持续推进任务，不足以保证 Worker 在空闲、会话结束和环境恢复期间连续运行；需验证进程存活、重启及任务补跑。
2. **约 4.6 GB SQLite 数据需要验证传输路径和实际磁盘余量。** 若作为单个普通对话附件上传，会超过 512 MB 上限；直接下载、分片传输及重组能否完成仍待验证。空间预算还要包含 WAL、依赖、临时文件和备份。[附件限制](https://help.openai.com/en/articles/20001052-using-library-to-manage-files-in-chatgpt)
3. **Dash 的 8050 端口需要单独验收。** 已有取证指出项目只监听 `127.0.0.1:8050`，并校验 Host/Origin；即使云内能打开，也不能据此确认用户本地浏览器可访问。
4. **TuShare 必须从 dot 云电脑内实际验证。** 需要覆盖项目实际使用的协议、DNS、连接、鉴权与 API 返回；浏览器能联网不能替代 Python 客户端调用验证。
5. **调度应继续显式使用 `Asia/Shanghai`。** 复用项目已有交易日历与幂等逻辑，核对系统、Python、浏览器和 dot 计划任务的时区是否一致。
6. **云电脑状态保留不足以替代数据库备份。** 在持久化范围、恢复行为和删除期限明确前，应保留独立可恢复副本。

**实测清单需要重点验证的点**

- **运行环境：**记录 OS、架构、用户权限；验证 Python 3.12、uv 安装、依赖同步及重新进入后的可用性。
- **磁盘与传输：**记录总量、可用量和配额；用测试文件验证附件与直接传输路径、单文件和累计限制，再验证约 4.6 GB 数据副本的传输校验与重组空间。
- **进程连续性：**用带时间戳心跳的测试进程，分别观察结束任务、关闭客户端、设备离线、空闲 1/8/24/72 小时后的存活情况；区分进程继续、暂停恢复与重新启动。
- **文件与 SQLite：**区分工作目录、用户目录及临时目录；检查跨会话文件校验值，并在数据库副本上验证 WAL、并发读写及中断恢复。
- **8050 访问：**分别验证云内浏览器和用户本地浏览器；检查平台是否提供转发/预览地址，以及认证、链接有效期、Host/Origin 和 Dash 回调是否正常。
- **TuShare 联网：**验证 `api.tushare.pro` 的 DNS、实际协议与端口、最小鉴权请求和持续调用；记录限制提示，避免在日志中输出 token。
- **时区：**核对系统时间、Python `zoneinfo`、浏览器时区和计划任务；验证 `Asia/Shanghai` 配置在恢复后是否保留。
- **保留与恢复：**记录空闲后文件和软件的保留情况，用可丢弃数据验证重置行为。**界面上不可见不能证明服务端已清除；后台清除期限仍需官方明确说明。**
