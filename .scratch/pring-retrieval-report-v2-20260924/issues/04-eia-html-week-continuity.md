# 04: EIA HTML 周连续性：先诊断、再修复

**What to build:** 未配置 EIA key 时，EIA HTML 历史表不再因节假日等正常缺周被整表拒收；真实断档如实记为缺口。先保存真实历史表作为样本复现拒收，再改。

**Blocked by:** None (can start immediately)

**Status:** done

Spec: [spec.md](../spec.md)

- [x] 保存真实历史表样本，并记录首次运行拒收的成因
- [x] 以样本断言：节假日缺周照常取得 Brent/WTI，真实断档记为缺口
- [x] 经公开入口断言：未配置 EIA key 的完整运行中 EIA 不再列为拒收（样本无断档时）
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过（按 ADR-0025）

## Comments

- 2026-09-24 完成。诊断：首次真实运行被拒的 Brent 原件（sha256 `033cb814…`，Release Date 9/23/2026）自 1987 年起，1994–2002 年有 9 处整周无报价、整行省略；同日 WTI 表 1999 年有 3 处。解析器对整张表检查“相邻周差 7 天”，与请求窗口（2026-02-15 起）无关的早年缺周也使整表 `eia_history_week_continuity_invalid`。样本存于 `tests/fixtures/eia/`（Brent 为运行原件，WTI 为 2026-09-24 取得的同期发布表），成因记于其 README。
- 修复：`parse_eia_history_document` 只要求周次严格递增（倒序记 `eia_history_week_order_invalid`）；请求窗口内整周缺失的五天记为 `week_absent` 缺值单元（不产生明细，由时效如实记缺口），窗口外缺周不再影响。节假日单日空值原本就记为 `blank`。
- 测试：两份真实表在 2026-02-15～09-23 窗口取得 9/21 收盘（Brent 116.15、WTI 96.97）；窗口内删去 9/14 周则五天为 `week_absent`、前后日照常入库；原 `missing_week` 拒收例改为 `reversed_week`；完整运行（未配置 EIA key）两表均 `validated`、缺口清单无 EIA 拒收（修复前红）。受影响 48 例全过。
