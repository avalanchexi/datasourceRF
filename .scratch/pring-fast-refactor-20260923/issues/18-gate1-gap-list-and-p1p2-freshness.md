# 18: 门①缺口清单与 P1/P2 时效处置

**What to build:** 运行枚举 120 交易日窗口内每个指标应有的明细与公式父输入，得出缺口清单，并在页面与报告按类别呈现（缺失、时效缺口、未配置时效、拒收）。投影层按票 04 处置 P1/P2：awaiting_release 沿用不算缺口；落后 1 期沿用并标时效缺口；≥2 期视为缺失、不参与计算。P1 缺失不阻断正式阶段。

**Blocked by:** 13, 17

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：缺口清单分类与内容正确，页面与报告一致
- [x] P1 在 awaiting_release、落后 1 期、落后 2 期三种情形下的沿用/缺失行为正确
- [x] 未配置时效的 P1/P2 显示缺口；P0 未配置时效阻断
- [x] P1 缺失时正式阶段仍产出
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 与 21 同一提交完成（两票在 p0/worker/reports 交织）。`freshness.gap_list` 从批次时效记录与门③拒收调用生成缺口清单（缺失 / 时效缺口 / 未配置时效 / 拒收），发布在 `cycle_overview.gap_list`，报告结构化上下文同源，页面总览与报告阅读器各有“缺口清单”分组。`period_status` 改为：awaiting_release 与落后 1 期视为可用（沿用），落后 ≥2 期或未配置才不参与计算。P0 未配置时效即 `p0_freshness_unconfigured` 阻断。新增 `test_gap_list.py` 5 例；同月库存两例恢复为 period_mismatch。
- 完整目录正例待 27 重建后运行，此票未跑。
