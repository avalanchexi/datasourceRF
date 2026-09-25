# 05: 现行基准不受 120 天留存与可见窗口限制

**What to build:** 事件类指标（`CN_RRR_EVENT`、`CN_OMO_7D_RATE`，即“生效至变更”指标）每个成员最近一次的值：留存清理（`retention.py`）不删除，投影可见窗口（`context_projection.TargetBoundEvidenceRepository`）不隐去；更早的历史值照常清理（ADR-0028 修订，部分取代 ADR-0022）。

**Blocked by:** —

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 留存：窗口外的最近一次降准保留（含命中原话），更早一次与普通旧明细照常删除
- [x] 投影：可见窗口起点晚于最近一次降准时，政策动作卡片仍以它为现行基准（`current`）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments
- 2026-09-25 完成：`EFFECTIVE_UNTIL_CHANGED_METRICS` 纳入 `CN_RRR_EVENT`；留存清理跳过这类指标每个成员最近一期的明细（及其命中原话）；`TargetBoundEvidenceRepository` 在可见窗口外仍保留每个成员最近一点。旧测试 `test_event_history_outside_the_visible_window_is_not_a_missing_source` 按 ADR-0028 修订改为现行基准显示。受影响 337 例（12 分钟）通过（含改写的一例）。
