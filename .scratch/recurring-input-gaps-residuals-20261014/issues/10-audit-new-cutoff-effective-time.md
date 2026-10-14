Status: ready-for-agent
Category: enhancement
Type: task

# 10：体检内置新口径生效时刻

**What to build:** 体检派生层内置新口径生效时刻 `2026-10-14T03:40:33Z`（做法同现有 ADR-0036 生效时刻，以运行受理时刻判新旧）：生效前的运行按“该日结束”读，生效后按运行截止读，不再误报“库中期次晚于独立判断”。口径文档同步。守体检线规程。落实[来源票 05](05-audit-new-cutoff-effective-time.md)；见[规格](../spec.md)“体检的新口径生效时刻”。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 实跑对账 `run-0a8dabc2e820321b84e1`：结论与已存报告一致（差异只来自留存清理时逐项说明）
- [ ] 实跑对账 `run-25ac18e4e3d329e1ea07`：派生层无“库中期次晚于独立判断”误报
- [ ] `docs/development/data-quality-audit.md` 写明生效时刻与新旧口径
