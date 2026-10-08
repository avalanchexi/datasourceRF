Status: ready-for-agent
Category: bug
Type: task

# 06 — TuShare CPI/PPI 交付含一月累计值时整次被拒（票 30 核对项，已证实）

## 原始发现

- [架构评审票 30](../../architecture-review-20260929/issues/30-shrink-fetch-ranges.md) Comments 列为真实运行核对项：`official_source_members` 规定 PPI 一月无 `cumulative_average_yoy`，适配器不过滤，交付含一月 `ppi_accu` 时 `registered_official_source_identity_mismatch`，CPI 与 PPI 一起被拒。
- 本次运行证实：直取阶段 `cn_cpi`（202601–202609，24 行）与 `cn_ppi`（202601–202609，72 行）均 `rejected`／`registered_official_source_identity_mismatch`。补缺阶段单月 `cn_ppi` 202608 被接受（9 行）；`cn_cpi` 202608 单月返回 0 行。

## 影响

- 每次窗口首日在一月或更早时，TuShare 的整批 CPI/PPI 都被拒，靠补缺单月重取和官方来源兜底，多耗调用；本次缺口清单未出现 CPI/PPI 缺项。

## 待决定

- 修复方向（建议）：适配器按登记成员过滤一月不存在的累计值，或解析时只拒该成员而不是整次交付。

### 2026-10-08 分流（见 [lookback-fetch-gaps 分流报告](../../lookback-fetch-gaps-20261008/triage-20261008.md)）

- 根因属实：PPI 一月契约只有 mom/yoy（`metric_contracts.py:158`），适配器照常产生累计字段（`tushare_context.py:593`），统一入库报错把 CPI、PPI 两份回执一起拒收（`:413`）。实测本轮两接口各返回 20 个原始月份，规范化为 CPI 60、PPI 180 个标量，均被拒；PPI 一月的 3 个累计字段确实非空。
- **订正触发条件**：不是"窗口首日在一月"，而是"实际交付包含任一年一月的非空累计字段"——本轮窗口始于 04-09，实际请求却始于 202501。
- 修复：按登记契约过滤一月不支持的 PPI 累计成员，原件复核重建结果保持一致；不扩大为通用逐成员容错。约 1–3 模块。需新增一月累计非空、跨年多月、CPI 连带保留的替身。
- 无需用户决定。纳入 lookback-fetch-gaps 一批实施（排第 2）。
