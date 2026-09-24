# 02: 交易日历不再列入缺口

**What to build:** 交易日历作为运维证据，不参与时效判定，完整运行的缺口清单里不再出现 P0 交易日历缺失。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：完整运行后缺口清单不含交易日历
- [x] 批次时效记录不再为交易日历判定状态
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。`freshness.NOT_ASSESSED` 加入 `CN_TRADE_CALENDAR`（与发布日程、来源可用性同列），批次时效不再为它判定状态；缺口清单的结构拒收分组同样跳过运维证据。交易日历是否可用仍由独立的日历门禁（`p0_required_calendar_unavailable`）判断，未改。
- `test_gap_list.py` 新增经完整运行断言：缺口清单与 `batch_freshness` 均不含交易日历（先红后绿）。受影响 31 例（缺口清单、时效契约、日历门禁）与两例快速冒烟全过，用时 340 秒。
