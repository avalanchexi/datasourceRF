Status: done
Type: task

# 05 — ADR-0024 已取消检查点恢复，`run-resume` 仍在

**发现：** 逐票核对旧 `pring-cycle-dashboard` 票 18 时（Codex 只读核对，已人工核实）。ADR-0024（accepted，2026-09-23）：“取消检查点恢复——运行中断即判失败，用户重新启动时作为新的加工批次从头运行”。但 `cli.py:334` 仍有 `run-resume`（`RunRepository.resume`，带 `confirm_external_calls`），Worker 仍复用检查点；2026-09-25 真实运行正是用 `run-resume` 在 `publishing_projection` 失败后恢复完成。

**待决定：** 按 ADR 删除恢复链（CLI、`RunRepository.resume`、Worker 检查点复用及测试），还是修订 ADR-0024 承认保留。实际运行刚受益于恢复（检索约 20 分钟，恢复后约 1 分钟），这一点应纳入考量。

## Comments
- 2026-09-25 用户决定保留 `run-resume`，见 [ADR-0031](../../../docs/adr/0031-keep-run-resume.md)（部分取代 ADR-0024）；代码不改，CONTEXT.md“运行中断”已同步。
