Status: done
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

## Comments

### 2026-10-08 实施

- **改动**：`tushare_context.py` 新增 `_official_ppi_members`，按登记契约 `official_source_members("CN_PPI", period_end)` 过滤每个 PPI 标量；取数 `prices()` 与原件复核 `parse_ppi_acquisition` 共用它，所以入库与重建一致（只去掉一月的三个 `ppi*_accu`，其他结构／身份错误仍整次拒收，未做通用逐成员容错）。CPI 不变：其身份契约本就接受一月累计，"一月完整性不要求累计"不等于拒收来源实际给出的累计。
- **测试**：新增 `test_worker_reviewed_context.py::test_a_january_ppi_cumulative_field_refuses_neither_ppi_nor_cpi`（登记 CPI／PPI 双来源目录；202512–202602 跨年三个月、一月累计全部非空；断言 CPI、PPI 回执均 `accepted`，三数分别为 3/9/9 与 3/24/24，PPI 三类别成员集合不含一月累计，`tushare_claims_matching_acquisitions` 以 `parse_ppi_acquisition` 复核全部选中声明成立）。修前红（`registered_official_source_identity_mismatch`），修后绿。`test_worker_registered_catalog.py` 的 `macro_rows` 去掉"一月 PPI 累计置空"的替身绕行，改为如实交付非空值。
- **验证**：受影响 7 个文件 127 passed（113s）；冒烟两例 2 passed（39s）；重型 `test_worker_registered_catalog.py` 2 passed（407s）、`test_core_carry_forward.py` 2 passed（39s），逐个串行；`ruff check`／`ruff format --check` 通过；`mypy` 改动前后同为 43 条既有错误，新增行无报错。采纳审查意见后 `test_worker_reviewed_context.py` 16 passed（35s）。
- **审查**（Codex 两轴，各一轮）：标准轴 阻断：无；规格轴 阻断：无。采纳：成员集合断言纳入三个类别。不采纳：规格轴指出过滤无目录版本条件，内置旧目录今后也少存一月三个 PPI 累计标量——不改，因为旧目录没有 PPI 必需成员清单，原件复核也跳过该分支，而一月累计本非官方成员（官方解析在一月同样不产出该列，`official_context.py` `_parse_ppi` 列不足四列时不取累计）；`prices()` 本身不带目录版本，按版本分叉反而让同一原件两种读法。
- **残余**：重型测试未单独证明补缺单月入口；该入口经 `targeted_context` 调用同一 `prices()`（规格轴读码核对）。
