Status: ready-for-agent
Category: enhancement
Type: task

# 09：SOX 接入取数路径

**What to build:** `NASDAQ_SOX_INDEX` 有真实取数路径，运行能持有 SOX 收盘值。先查 TuShare 是否有 SOX；没有则从可信网站中选能按日期取收盘值的来源。**不用 ETF 代理，不用近似指数。**选定来源后**先停下回报主 agent，由用户确认**，再实施：补写 ADR-0029 的 SOX 一条或新增 ADR；SOX 由“受限授权、无取数路径”改为“有注册来源、不检索”；仍是 P2、不进模型。落实[来源票 02](02-sox-source.md) 的生产部分；口径见[规格](../spec.md)“SOX”各条。

**Blocked by:** None (can start immediately)；实施段需用户确认来源

**Status:** ready-for-agent

- [ ] TuShare 覆盖结论与可信网站候选（来源、按日期可取性、可信依据、样本应答）写入本票 Comments
- [ ] 用户确认来源（主 agent 转达）
- [ ] ADR 写明来源、可信依据与用户 2026-10-14 决定
- [ ] 对应接缝（`refresh_quote_source` 或 TuShare 行情适配器）上的测试：按日期持有收盘值；解析失败记来源失败与原因码
- [ ] SOX 期次按美股交易日；不进模型；目录不检索；受影响测试通过
