# 13: 时效登记表、应有期判定与目标交易日自动决定

**What to build:** 运行按启动时点自动决定目标交易日（三核心登记更新时点已过的最近上交所交易日）；每个“指标 × 注册来源”按代码常量登记表判定 current / awaiting_release / stale / 未配置时效，公开可用时间 = min(推算发布时点, 首次取得时间)，结果写入批次。本票只记录、不处置。见票 04。

**Blocked by:** 12

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 登记表字段：频率、发布滞后（交易日）、更新时点（上海时间）、宽限（交易日，默认日 1、周/月/季 7，可按来源覆盖）、依据；派生指标取输入中最差状态
- [x] 推算发布时点在无预告时按统计期末后第 N 个交易日 + 更新时点；交易日一律按上交所日历
- [x] 事件类（降准）有最近事件即 current；OMO 按日频
- [x] 经公开入口、以时钟替身参数化断言：周一 16:00 → 上周五、周二 10:00 → 周一；日/周/月/季/事件各自的 current、awaiting_release、stale 边界；未登记来源为“未配置时效”
- [x] 取代 `evidence_max_age_days` 的固定天数判定（旧判定不再参与新运行）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-23 完成：新增 `freshness.py`（59 项目录的登记表、应有期判定、派生取最差、min 公开时间、按启动时点决定目标交易日、批次记录）与迁移 0023 `batch_freshness`；Worker 在评估计划后写入批次；`run-submit` 省略 `--target-date` 时自动决定（本地日历 → TuShare `trade_cal` → 工作日）。投影、Worker P1 覆盖与检索选择器的固定天数判定改用登记表。`tests/integration/test_freshness_contract.py` 20 passed / 17.9 秒；`test_derived_context_freshness.py` 的社融/GDP 例按新契约把截止时点移到 07-20。登记滞后多为官方日程归纳（研究 02），TuShare 宏观入库时点未证实。
