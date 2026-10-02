Status: needs-triage
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
