Type: task
Status: claimed
Blocked by: 01

# 在 dot 云电脑上实测常驻与访问

## Question

dot 云电脑能否承载本项目的运行形态？由用户让 dot 按清单实测（清单在领取时依据“dot 云电脑的规格与对外访问”的结论给出）：装 Python 3.12 与 uv；起一个常驻进程（每分钟写一行时间戳）和一个简单网页；跨一夜后确认进程仍在、时间戳无断档；用户浏览器能否打开该网页；系统时区；可用磁盘；上传一个约 1 GB 的测试文件的方式与耗时。

只验证能力，不迁移真实运行库，不放 TuShare token。结论决定 ADR-0043 由 proposed 转 accepted，或转向独立云主机回退。

## 进度

- 2026-10-15 领取。实测清单见 [trial-02-checklist.md](../trial-02-checklist.md)：给 dot 的两段提示词（当天能力探测、次日 09:30 周期任务复查）、浏览器访问与上传测试步骤。比票面多测三项，均不需 token：数据源域名可达性（含无 token 的 TuShare 探测）、SQLite WAL、dot 周期任务能否准点触发并推送（供“每日运行由谁发起”使用）。上传测试文件已备在 `D:\dot-trial-20261015\`（1 GiB 随机数据，另有 3 个分片，sha256 见清单）。
- 等用户贴回报告 A、浏览器与上传结果、报告 B 后解决。
- 2026-10-15 清单追加“步 1b”（密钥入口与变量继承，只用假变量 `PRING_TRIAL_DUMMY`）与提示词 B 第 8 条，服务于[数据源密钥在云电脑上怎么交给应用](05-data-source-secrets-on-cloud-computer.md)。
