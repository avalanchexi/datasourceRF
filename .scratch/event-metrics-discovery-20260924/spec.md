Status: ready-for-agent
Type: spec
Date: 2026-09-24
Basis: 访谈决定已写入 [ADR-0028](../../docs/adr/0028-event-metrics-current-baseline-and-discovery.md) 与 CONTEXT.md（事件类指标、现行基准、追溯发现）；缺失排查见 [missing-items-investigation.md](../pring-retrieval-report-v2-20260924/missing-items-investigation.md)。

# 事件类指标的检索与现行基准（实施规格）

## Problem Statement

真实完整运行（run-1579de05ddf2f0d7f48f，目标 2026-09-23）中，公开市场操作利率（`CN_OMO_7D_RATE`）与降准（`CN_RRR_EVENT`）一直“未持有”。它们按事件类处理：没有持有值时缺口计划只记 `event_presence_unknown`，不建检索范围；已持有时缺口期取已持有的那期，也不会去查有没有新变化。而 9/23 的资讯里已有“操作利率1.40%”原句。

## Solution

- 公开市场操作利率：每轮与操作量同组，检索最新已发布交易日的公告；持有与否都查，查不到时沿用已持有值，不算缺失。
- 降准：登记降准资讯规则，每轮在本轮资讯里监测，未命中沿用现行基准、不算缺失，不走后续渠道。两者都生效至变更，不设有效期。从未持有时追溯发现：央行官网降准公告栏目为主、AI WebSearch 兜底，找到最近一次即停。

## Slices

- [01 公开市场操作利率随操作量逐日检索](issues/01-omo-rate-daily-with-amount.md)
- [02 降准：资讯监测、现行基准与追溯发现](issues/02-rrr-news-baseline-backtrack.md)
