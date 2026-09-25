---
status: accepted
---

# 保留运行恢复

2026-09-25 用户选择（验收发现 [05](../../.scratch/acceptance-findings-20260925/issues/05-run-resume-after-adr-0024.md)）。[ADR-0024](0024-interrupted-runs-restart-as-new-batches.md) 取消了检查点恢复，但 `run-resume` 一直保留，2026-09-25 真实完整运行正是在 `publishing_projection` 失败后用它恢复完成：从头重跑约 20 分钟（检索占大头），恢复只要约 1 分钟。

决定：保留 `run-resume`（`RunRepository.resume` 与 Worker 的检查点复用），仍须用户显式发起并确认外部调用；启动项目不自动恢复，中断的运行在用户未恢复前按失败显示。从头重跑仍是默认做法。

取舍：恢复链是 Worker 中较复杂的部分，但它在检索耗时远大于其余步骤的现状下能省下一次完整重跑，且代码已存在、已被真实运行验证。

本 ADR 部分取代 ADR-0024 中“取消检查点恢复”一句；“窗口内漏跑日自动补算”与 ADR-0024 其余部分继续有效。
