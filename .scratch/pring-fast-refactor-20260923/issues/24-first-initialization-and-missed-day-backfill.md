# 24: 首次初始化与漏跑补算

**What to build:** 库中无汇总时，首次运行拉取 120 交易日明细与公式回看，逐日算出窗口内每天的汇总并重建阶段史，只为目标交易日生成报告；日常运行自动补算窗口内漏跑交易日的汇总，各日只用公开可用时间不晚于该日的明细，不为补算日生成报告。见票 07 第 7、8 条。

**Blocked by:** 13, 23

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：空库首次运行后窗口内每个交易日都有汇总与阶段史，报告只有一份
- [x] 漏跑两日后运行，两日被补算且无报告
- [x] 补算日不使用在其之后才公开的明细（无前视）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [x] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-24 完成。Worker 在发布目标日汇总前调用 `_backfill_missed_days`：取本次运行已校验的 120 交易日窗口，凡目标日之前、尚无汇总（P0 评估）的交易日按先后逐日计算核心就绪（`_core_readiness(public_as_of=当日结束)`）与宏观/库存上下文（`build_context_projection(target_business_date=当日)`，本就按公开时间截在当日结束），发布该日投影（当前指针只前移，不会被旧日覆盖），不生成报告。空库即首次初始化（119 日 + 目标日），日常运行只补漏跑日。阶段史改为按目标日排序（同日多批次再按系统时点），补算日共享运行时点也能保持次序。
- 代价：首次初始化约 13 秒（119 日，主要是逐日读库连接），日常补算按漏跑天数线性增加；空库上的完整运行测试都会多出这一段。
- 新增 `test_backfill.py` 3 例（首次运行 120 日汇总且只有一份报告、漏跑两日被补且无报告、补算日看不到当日之后才公开的 7 月 CPI）。

- 2026-09-24 回填：完整目录正例与三核心反例已包含在终点全套（票 28）中一并运行。`check.py full` 退出码 0，1211 例通过，用时 4051.5 秒；其中完整目录正例 `test_worker_registered_catalog.py::test_full_worker_falls_back_to_official_ppi_and_exposes_delivery_in_report` 用时 125.6 秒，三核心反例（`test_core_carry_forward.py`、`test_core_official_fill.py`、`test_structural_rejection.py`）均通过。
