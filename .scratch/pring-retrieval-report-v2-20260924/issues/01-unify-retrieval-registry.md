# 01: 预重构：统一检索登记处

**What to build:** 把分散的检索登记（官方解析器家族、LPR、中证核心、P2 宽松主机）收到同一登记处，并提供“可检索缺口”判定（指标属于登记解析器家族或登记了宽松主机）。对外行为不变，为后续各票铺路。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 各来源的主机、指标集与解析入口从同一登记处读取，原有调用方改用它
- [x] 提供“可检索缺口”判定，派生指标与 NHII 判为不可检索
- [x] 现有测试不改断言即全部通过（行为不变）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。新增 `retrieval_registry.py`：`RETRIEVAL_FAMILIES` 按家族登记发布机构、主机（含路径前缀）、指标集与解析器类型（`official_context`/`lpr`/`csindex`/`lenient`），覆盖 14 个官方家族、LPR、中证核心与三项 P2 宽松主机。`source_families.OFFICIAL_CONTEXT_FAMILIES`、`search_evidence.LENIENT_HOSTS`、`official_lpr`/`official_core` 的主机常量改为它的视图；候选校验与 Worker 官方直连按 `parser_for_scope` 分派。`is_searchable_gap()` 供票 05 接入，派生指标、TuShare 计算指标与 NHII 判为不可检索。
- 新增 `tests/retrieval/test_retrieval_registry.py`；受影响 51 例（严格路径、P2 宽松、中证补缺、LPR、官方回退、搜索证据）与两例快速冒烟全过，现有断言未改。`check.py quick` 用时 256 秒，超出 180 秒目标，主要为既有集成用例建库成本。
