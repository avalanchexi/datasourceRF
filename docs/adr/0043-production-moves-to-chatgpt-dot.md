---
status: proposed
---

# 生产运行迁到 ChatGPT dot 云电脑，本机只作开发环境

2026-10-15，用户在“把项目迁到 dot 上运行”访谈中作出决定（Q1、Q7、Q10，见 [访谈记录](../../.scratch/dot-hosting-20261015/interview.md)）。状态为 proposed：dot 云电脑能否常驻 Worker、能否访问驾驶舱尚未实测，实测通过后改为 accepted。

## 决定

- Worker、运行库、制品与驾驶舱整体迁到用户 ChatGPT Pro 账号下 dot 的云电脑，由 dot 托管与看护；本机切换后不再承担生产运行，也不并行。
- 源码经私有 GitHub 仓库传到云电脑；运行库与制品走仓库之外的渠道迁移；数据源密钥（含 TuShare token）不经对话传递，首选平台的环境变量或密钥入口，没有入口时由用户亲手写仓库外 0600 文件（见[数据源密钥票](../../.scratch/dot-hosting-20261015/issues/05-data-source-secrets-on-cloud-computer.md)）。
- dot 托管与看护；暂时可执行项目全部命令，包括运行恢复（见[看护清单](../../.scratch/dot-hosting-20261015/issues/04-watch-checklist.md)）。改代码与部署时机仍由用户决定。
- 实测不通时，退到独立云主机运行，由 dot 经 SSH 或自建 MCP 管理。

## 考虑过的方案

- **本机继续运行，dot 连接电脑管理**：改动最小，但本机须常开、ChatGPT 桌面应用常驻，不符合“上 dot”的目标。
- **独立云主机**：可靠且能力明确，但多一台机器和一份运维；保留为回退。

## 后果

- 运行状态、凭据与历史数据离开本机，受 OpenAI 的保留与训练设置约束（Pro 需手动关闭训练开关；dot 记忆不能逐条删除）。
- 现有“只绑定 `127.0.0.1`”“`--no-editable` 安装”“报告调用本机已登录 CLI”等本机前提，需要在云电脑上重新成立或改写。
