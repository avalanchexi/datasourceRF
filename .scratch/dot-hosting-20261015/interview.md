# 访谈记录：把项目迁到 ChatGPT dot 上运行（2026-10-15）

取证见 [codex-facts-20261015.md](codex-facts-20261015.md)。用户逐题确认（“全部确认”）。

| 题 | 决定 |
|---|---|
| Q1 终点 | 项目整体在 dot 上运行、由 dot 管理（D：托管运行） |
| Q2 订阅 | ChatGPT Pro（200 美元档） |
| Q3 TuShare token | 随应用上 dot，只放在 dot 的密钥/环境变量里；不进 git、不写入任何文件；调用仍串行、不高并发（“不写入任何文件”已由[数据源密钥票](issues/05-data-source-secrets-on-cloud-computer.md)收窄：没有平台入口时允许用户亲手写 0600 文件） |
| Q4 数据出本机 | 全部数据都在 dot 上 |
| Q5 源码上 GitHub | 可以，私有仓库 |
| Q6 历史数据迁移 | 整库迁移：运行库（约 2.8 GB）与制品 `artifacts/`（约 1.8 GB）；`backups/`（约 8 GB）与各 dev-venv 不迁。迁移前停本机 Worker、确认 WAL 已合并再打包；传输渠道待实测 |
| Q7 本机角色 | 切换后立即停用生产运行，本机只作开发环境，不并行 |
| Q8 仓库范围 | 全部上 GitHub（含 `.scratch/`、`output/`），`.gitignore` 照旧生效：库、日志、`.env`/`secrets.env`、`artifacts/` 不进 git，走 Q6 的迁移渠道 |
| Q9 dot 管到哪一步 | 只托管与看护：保证 Worker 在跑、异常提醒、核心数据待处理时问用户；运行恢复（`--confirm-external-calls`）与改代码不交给 dot（运行恢复一项已由[看护清单](issues/04-watch-checklist.md)改为暂时不设限） |
| Q10 应用跑在哪 | 终点是 dot 云电脑跑全部（Worker、数据库、驾驶舱）。先实测常驻进程、跨日存活与浏览器访问驾驶舱；不通则退到独立云主机、由 dot 经 SSH 或自建 MCP 管理（ADR-0043） |
| Q11 代码上线路径 | 本机提交并 push → 用户对 dot 说“部署 main” → dot `git pull`、`uv sync` 重装、重启 Worker 与驾驶舱并报告；不自动部署 |
| Q12 切换当天验证 | 本机最后一次运行完成 → 迁移 → dot 上跑 `pring-cycle test` 与数据质量体检 → 对同一目标交易日手动完整运行，与本机结果对比，一致后才开启自动盘后运行 |
| Q13 AI 报告 | dot 云电脑只登录 Codex CLI；不放 Claude 凭据；失败走确定性简版 |
| Q14 提醒与训练 | 看护提醒走 ChatGPT 推送，不另接 Slack/邮件；用户在 Pro 设置里关闭 “Improve the model for everyone” |

## 尚未看清（交给 wayfinder）

- dot 云电脑能否常驻 Worker、能否让用户浏览器访问驾驶舱（现只绑定 `127.0.0.1:8050` 并校验 Host/Origin）
- 几 GB 数据传进 dot 云电脑的渠道；云电脑磁盘容量与保留期限（官方未查到）
- dot 周期任务与项目自有交易日调度如何分工（避免两套调度）
- 云电脑上的运行环境：Python 3.12、uv、原生 Linux 文件系统、时区 `Asia/Shanghai`
- 回退到独立云主机时的选型与 dot 的管理通道

## 词汇表

本次没有新增领域术语：dot、云电脑、部署都是运行宿主层面的实现概念，不进 `GLOSSARY.md`。
