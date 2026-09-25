Status: done
Type: task

# 14 — 报告正文与其他数据一样保留 120 个交易日

依据 ADR-0022 修订（2026-09-25，验收发现 [06](../../acceptance-findings-20260925/issues/06-report-body-30-day-clear.md)）。删除 `maintenance.py` 中 30 天后清空 `report_snapshot` 正文的规则及其测试；报告随 120 交易日留存清理删除。

## Comments
- 2026-09-25 实施：删除 `MaintenanceRepository.cleanup` 中把 30 天前报告正文置空的语句与 `CleanupResult.expired_report_bodies`；报告随 120 交易日留存清理删除。已被清空的旧快照仍按“正文已过保留期”显示。
