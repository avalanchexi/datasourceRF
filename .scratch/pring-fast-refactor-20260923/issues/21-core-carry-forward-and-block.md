# 21: 核心沿用与 ≥2 期阻断

**What to build:** 三核心补全失败且只落后 1 期时，以上一交易日值计算、照常产出正式阶段，页面与报告醒目标注“核心沿用上一期”，沿用值不写成明细；落后 ≥2 期或冲突时阻断正式阶段（核心数据待处理），宏观、库存、缺口与报告照常发布。见票 07 第 3 条。

**Blocked by:** 18

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 经公开入口断言：落后 1 期 → 正式阶段产出且带核心沿用标注，明细表无沿用值
- [x] 落后 ≥2 期 → 正式阶段阻断，其余输出与报告照常
- [x] 来源冲突 → 阻断
- [x] 以既有三核心缺口反例为底改写，并新增“核心沿用”一例
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）
- [ ] 另加跑完整目录正例与三核心反例（涉及 Worker 编排/目录/来源），记录退出码与耗时

## Comments

- 2026-09-23 与 18 同一提交完成。三核心只落后上一交易日时，以上一收盘补齐目标日参与趋势计算（不写成声明），资产标 `carried_forward`、总览列 `core_carry_forward`、页面醒目“核心沿用上一期”、报告同列；落后 ≥2 期或冲突则阶段置空、`stage_reason=core_data_pending`，投影、宏观、库存、缺口清单与报告照常发布，运行 completed。删除 Worker 中“计划有核心缺期即 action_required”的提前返回。原隔离生命周期的三核心反例文件已随 15 删除，改由轻量的 `test_core_carry_forward.py`（沿用、落后两期、冲突三例）承担；另按新语义改写 `test_p0_gate`、`test_core_fixture_cli`、`test_worker_execution`、`test_projection_api`、`test_report_boundary` 中的旧阻断断言。
- 受影响 15 个文件 191 例全过；完整目录正例待 27。
