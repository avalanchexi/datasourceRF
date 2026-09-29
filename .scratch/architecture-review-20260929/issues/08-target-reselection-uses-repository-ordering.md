# 08: 目标日重选复用仓库的选值排序与冲突范围

**What to build:** 投影按目标日重选声明时（`_selected_among`，`context_projection.py:730`），与证据仓库选值（`evidence.py:1435`）使用同一排序（已认证优先，再按提供方）与同一冲突比较范围（只比较已认证、合格、已报告值的声明）。

**Blocked by:** 无

**勿并行：** 05、06、07、09、16、17、23、26、28、29、30（同改：上下文投影；证据仓库；逐区明细见 [README](../README.md)「串行约束」）

**Status:** ready-for-agent

来源：[架构评审](../README.md) 候选 2 差异 3（用户判定为遗漏，2026-09-29）。属选值，不进可采用声明模块。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状

`_selected_among` 只按提供方名称排序，冲突比较纳入所有合格已报告值，不看 `certification_status`。真实库（2026-09-29）：`certified` 356192 条、`awaiting_source_certification` 8193 条（EIA、VIX、ECB 交叉汇率、`CN_MARGIN_BALANCE_SSE_SZSE`、CNY030、央行中间价等）、`not_applicable` 566 条（`tushare_news`、`ai_websearch:*`、媒体）。于是在投影中，资讯／媒体值可与 TuShare 值构成冲突，或仅凭提供方名称被选中；这与 ADR-0033"多个注册来源的已认证声明比较"不符。降准 `_official_days_whole` 的整份公告优先保留。

## 验收

- [ ] 仓库与投影共用一个选值排序与冲突范围函数，不再各写一份。
- [ ] 按 TDD 补用例：同一观测有已认证 TuShare 值与 `not_applicable` 资讯值、相差超过 0.5% → 投影不判冲突、选 TuShare；只有非认证声明时仍按提供方选出（现行为）。
- [ ] 核对 `awaiting_source_certification` 的指标（EIA、VIX、ECB 等）在投影中仍能选出值，不因排序变化变空。
- [ ] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过。
- [ ] 代码审查无阻断。
