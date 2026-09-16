# 第5步执行清单（待命，2026-09-16 编写）

真实 120 日回放与真实切换的完整执行顺序、留证要求与中止规则。**当前三项前置均未满足，不得开始**；本清单待前置解除后按序执行，切换那一步在执行前交用户确认。

## 开始前必须全部满足

| # | 前置 | 当前状态 | 由谁解除 |
|---|---|---|---|
| 1 | 票13 三项历史原件（DR007 历史首次公开时间、PP/CF/TA 仓单单位、存准率历史事件） | **缺**；问卷第 3 项未答复 | 用户决定：授权有界抓取 / 直接提供 / 明确不做 |
| 2 | 票19 真实完整候选（含 42 项 P1 来源认证） | **无**，10 项未勾；依赖前置 1 | 前置 1 解除后由实施推进 |
| 3 | 市场来源认证合同官方语义复核 | **未通过**；`docs/operations/direct-cutover.md` 明确"当前没有可供用户确认的就绪切换清单"，认证/激活/正式写入/切换均被拦截 | 依 `docs/research/market-source-semantic-review-2026-09-05.md` 完成样本与修正 |
| 4 | C 盘可用空间 ≥ 10GB | **约 5.3GB** | 用户执行 `D:\cursor\wsl-sparse-reclaim.ps1`（管理员，回收约 190GB，断开全部 WSL 会话） |

已就绪的部分：回放区间已用官方交易日历核定为 2026-03-09 至 2026-08-28 共 120 交易日（见 [日历记录](verification-21-real-calendar-20260916.md)）；出口、令牌、codex 登录均可用（见 [连通性记录](verification-connectivity-20260916.md)）。

## 执行顺序（任一步失败即停止并留证）

1. **真实来源 smoke**：`pring-cycle source-smoke --target-date YYYY-MM-DD --json`，校验交易日历、中证全指、上证国债指数、NHII 的真实身份、连续性与规范化哈希。需本机 `TUSHARE_TOKEN`，失败不得用 fixture 替代。
2. **上下文 smoke**：`context-source-smoke`，对本次实际使用的每个 P1 官方 HTML schema family 执行 `official-context-smoke`。EIA 属 P2：当前密钥 403，走无密钥页面入口（见 [票14 记录](implementation-14-eia-html-fallback.md)），不阻塞 P0/P1 门。
3. **统一验收**：`pring-cycle acceptance --runtime-root <正式> --json`，35 项回归、故障注入、确定性与性能硬门。套件耗时是目标不是硬门（见 [计时切片](implementation-22-timing-slice.md)）。
4. **fixture 恢复演练**：`pring-cycle rehearse-fixture-recovery --json`。
5. **真实完整运行与报告**，随后启动本机 Dashboard，再执行 `pring-cycle rehearse-real --target-date YYYY-MM-DD --dashboard-port 8877 --source-smoke-hash …（每个必需家族一个）--json`。
6. **真实 120 日回放**：固定区间 2026-03-09..2026-08-28，逐 cutoff 只用当时可知证据与对应 vintage，绑定所选声明版本与派生父项；SYSTEM 另做旧发布重现，旧制品哈希不变。
7. **构建切换清单**：`pring-cycle cutover-manifest --acceptance-hash … --fixture-rehearsal-hash … --real-rehearsal-hash … --legacy-system-read-only-stopped --suite-total-seconds <整批实测> --json`。只有 `status=ready` 才可继续。
8. **交用户确认后**再执行不可逆的一次性切换：`pring-cycle cutover-record --manifest-hash … --confirm DIRECT_CUTOVER_TO_PRING_V1 --json`。无 `force`、无等价绕过；同一清单幂等，换清单会被拒绝。

## 留证与中止规则

- 每步保留：实际命令、退出码、终态、耗时、制品哈希、前后指纹；失败样本一并保留，不以重试抹去。
- 资源守护：可用内存 <1.5GB 或 C 盘 <3GB **连续两次采样**即终止并保留现场（单点阈值曾在 2026-09-16 误杀一次长任务）。
- 一次只跑一个重型本地任务；冻结输入期间不并行修改、安装或校准。
- 切换后首次故障只在 V1 内修复或显式恢复，不得恢复旧系统运行。

## 不可做的事

不得用合成材料回放冒充真实回放；不得在认证未通过时创建"已认证"结果；不得改目录版本字符串、重盖 smoke 指纹或确认词绕过复核阻塞。
