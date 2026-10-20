Label: wayfinder:map
Status: open

# 找到把 Pring Cycle 迁到 ChatGPT dot 上运行的路线

## Destination

形成一份可以直接交给 `/to-spec` 的迁移方案：运行宿主经实测确认，驾驶舱访问、调度分工、看护规则、本机前提的改写、数据迁移与切换步骤均已决定，实施者不再需要补做决策。地图内不做真正的迁移。

## Notes

- 已定决策见 [访谈记录](interview.md) 与 [ADR-0043](../../docs/adr/0043-production-moves-to-chatgpt-dot.md)；平台事实见 [取证](codex-facts-20261015.md)。每次工作先读这三份和本地图。
- 全程中文交互。
- research 票用 `codex exec -s read-only` 解决（见 `docs/agents/codex-delegation.md`），不开 Claude 子代理；结论写成本目录下的文件，由票链接，不开 `research/` 分支。
- grilling 票同时使用 `grilling` 与 `domain-modeling`。
- TuShare 调用一律串行、不高并发；token 只放 dot 的密钥或环境变量，禁止输出、记日志、写入仓库或交给 AI。
- 缺口归零批次（`.scratch/recurring-input-gaps-residuals-20261014/`）在本机验收完成前不切换；地图可以先走。
- 实测（task 票）可以在地图内做，但只验证能力，不迁移真实运行库。

## Decisions so far

<!-- 决策只在对应已解决票中保存；本图只追加一行摘要和链接。 -->

- [dot 云电脑的规格与对外访问](issues/01-dot-cloud-computer-specs.md)：官方只确认能运行软件、保留状态、后台与周期任务；常驻进程、端口访问、磁盘、OS、TuShare 可达性均未查到，全交实测；附件 512 MB/文件，数据不能整包上传
- [看护清单](issues/04-watch-checklist.md)：交易日 9:30 起一次看护任务跟到运行结束，异常即提醒、否则推摘要，体检每交易日一次；dot 暂时可执行全部项目命令（覆盖访谈 Q9）
- [数据源密钥在云电脑上怎么交给应用](issues/05-data-source-secrets-on-cloud-computer.md)：应用改为环境变量优先、文件兜底；首选平台入口，没有时用户经接管亲手写 0600 文件；迁移包排除 `secrets.env`，dot 禁止读取或输出密钥

## Not yet specified

- **驾驶舱怎么访问**：取决于实测能否从浏览器打开 dot 云电脑上的网页；现行只绑定 `127.0.0.1:8050` 并校验 Host/Origin，可能需要改绑定、隧道，或改为不看驾驶舱、只看报告。
- **本机前提的改写**：`--no-editable` 安装与“部署 main”的重装重启流程；Codex CLI 在云电脑上的登录与续期；`Asia/Shanghai` 时区与原生 Linux 文件系统。
- **数据迁移渠道**：约 4.6 GB（运行库 2.8 GB＋制品 1.8 GB）如何传进云电脑、如何校验完整；取决于规格与实测结果。
- **切换步骤的细节**：访谈 Q12 已定骨架，具体命令序列、对比口径与失败回滚待前面各项定下后再写。
- **回退到独立云主机**：只有实测不通时才展开，包括主机选型与 dot 的管理通道（SSH 或自建 MCP）。

## Out of scope

- 让 dot 改代码或开 PR（开发代理）：访谈 Q9 排除。
- 在 ChatGPT 里经插件或 MCP 问答阶段判断：访谈 Q1 未选。
- 公开发布插件。
- 本机与 dot 并行运行：访谈 Q7 排除。
