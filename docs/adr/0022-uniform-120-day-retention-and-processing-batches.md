---
status: accepted（2026-09-25 修订：报告正文同为 120 交易日；2026-10-02 修订：公式回看入库，派生观测的父声明随其保留，措辞待确认）
---

# 明细、汇总与加工批次统一只留 120 个交易日

2026-09-23 用户选择：来源声明与原件（明细）、派生观测／投影集／阶段史／报告快照（汇总）、加工批次记录，**都只保留以最近成功运行目标交易日为终点的 120 个交易日**，在成功运行末尾物理删除超期部分；公式回看超出窗口的数据每次运行从注册来源重新取得，与其他明细一样入库、参与计算，在成功运行末尾随超期部分清理（2026-10-02 按实际订正，原写“只用于计算、不入库”）。一次手动完整运行即一个加工批次（批次 id = 运行 id），每条明细和汇总挂批次 id 以便排查，批次记录不在页面展示。来源修订与同日重跑都按普通批次追加，计算取最新；取消 `public_as_of` / `system_as_of` 双时点。模型版本简化为版本号＋显式切换生效指针，无回放、无验收、无回退保证窗口；老日期不支持用新模型回放。

取舍：不可变 vintage、双时点与并行版本回放服务的是长期历史重现与无前视校准，而它们的存储、夹具与认证成本正是开发周期被拖慢的主因。接受的代价是：超过 120 个交易日的阶段史、报告与投影不再可见，旧判断无法用新模型重算，也无法重现某一天的历史页面。细节见[留存与批次](../../.scratch/pring-fast-refactor-20260923/issues/06-detail-retention-and-processing-batch.md)。

本 ADR 取代 [ADR-0006](0006-dual-as-of-and-immutable-evidence-vintages.md) 与 [ADR-0012](0012-atomic-model-versions-and-parallel-replay.md)。[ADR-0008](0008-atomic-analytical-projection-sets.md) 的原子发布继续有效。

**2026-09-25 修订（用户选择，验收发现 [06](../../.scratch/acceptance-findings-20260925/issues/06-report-body-30-day-clear.md)）**：报告正文与其他汇总一样保留 120 个交易日，删除维护清理中“30 天后清空报告正文”的规则。事件指标现行基准的窗口外保留例外仍见 [ADR-0028](0028-event-metrics-current-baseline-and-discovery.md)。

**2026-10-02 修订（[架构评审](../../.scratch/architecture-review-20260929/README.md)票 [29](../../.scratch/architecture-review-20260929/issues/29-retain-derived-parents.md)，措辞待确认）**：公式回看入库并在成功运行末尾清理，正文已按实际订正。留存清理新增第二个窗口外例外：仍在留存期内的派生观测，保留它计算所用的父来源声明及其原件关联，使派生血缘可以回读；派生观测过期删除后，它的父声明照常随窗口清理。第一个例外仍是事件指标的现行基准（[ADR-0028](0028-event-metrics-current-baseline-and-discovery.md)）。
