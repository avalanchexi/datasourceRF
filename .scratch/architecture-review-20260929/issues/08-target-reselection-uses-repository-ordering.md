# 08: 目标日重选复用仓库的选值排序与冲突范围

**What to build:** 投影按目标日重选声明时（`_selected_among`，`context_projection.py:730`），与证据仓库选值（`evidence.py:1435`）使用同一排序（已认证优先，再按提供方）与同一冲突比较范围（只比较已认证、合格、已报告值的声明）。

**Blocked by:** 无

**勿并行：** 05、06、07、09、16、17、23、26、28、29、30（同改：上下文投影；证据仓库；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 2 差异 3（用户判定为遗漏，2026-09-29）。属选值，不进可采用声明模块。 规格：[spec.md](../spec.md)「三、可采用声明模块」。

## 现状

`_selected_among` 只按提供方名称排序，冲突比较纳入所有合格已报告值，不看 `certification_status`。真实库（2026-09-29）：`certified` 356192 条、`awaiting_source_certification` 8193 条（EIA、VIX、ECB 交叉汇率、`CN_MARGIN_BALANCE_SSE_SZSE`、CNY030、央行中间价等）、`not_applicable` 566 条（`tushare_news`、`ai_websearch:*`、媒体）。于是在投影中，资讯／媒体值可与 TuShare 值构成冲突，或仅凭提供方名称被选中；这与 ADR-0033"多个注册来源的已认证声明比较"不符。降准 `_official_days_whole` 的整份公告优先保留。

## 验收

- [x] 仓库与投影共用一个选值排序与冲突范围函数，不再各写一份。
- [x] 按 TDD 补用例：同一观测有已认证 TuShare 值与 `not_applicable` 资讯值、相差超过 0.5% → 投影不判冲突、选 TuShare；只有非认证声明时仍按提供方选出（现行为）。
- [x] 核对 `awaiting_source_certification` 的指标（EIA、VIX、ECB 等）在投影中仍能选出值，不因排序变化变空。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾两例快速冒烟通过。
- [x] 代码审查无阻断。

## Comments

**2026-10-01 实施记录**

- **改动**：`evidence.select_among(claims, tolerance=)` 抽出仓库的选值排序（已认证优先，再按提供方）与冲突范围（只比较已认证、合格、已报告的值），仓库的 `_select_claim_rows` 与投影的目标日重选 `_selected_among` 共用。降准整份公告优先（`_official_days_whole`）先筛公告提供方与成员，再调用同一重选，保留不变。
- **投影的行为变化（本票授权）**：已认证声明与资讯／媒体／AI、awaiting 声明混在一起时，已认证者优先，非认证值不再引起冲突。只有 awaiting 或 not_applicable 声明时仍按提供方选值，彼此差异不再报冲突，这与 ADR-0033 只比较已认证声明的口径一致。审查提醒的边界：awaiting 的官方来源并不优先于 not_applicable 的媒体（按提供方名称排）；排序不看质量与数值状态。两者都是仓库既有规则，投影现在与之一致。
- **测试**（先红后绿）：`test_context_projection.py::test_the_target_day_selects_as_the_repository_does` 共 6 组，覆盖：已认证 TuShare 与资讯相差 >0.5% 不判冲突且选 TuShare；已认证压过名称排序；只有非认证声明时按提供方选出；只有 awaiting 声明时照常选值；awaiting 与资讯混合；两个已认证来源相差 >0.5% 在目标日仍判冲突。改动前前两组失败。
- **验证**（`PYTHONPATH=src`）：涉及投影、冲突、EIA、VIX、ECB 与所有完整运行的测试文件，加 `tests/evidence`，共 882 例全过（44.4 分钟）。审查后补的 3 组单独跑，6 例全过。ruff、mypy 通过。
- **审查**（Codex 只读）：仓库侧行为不变；未发现阻断项。已按意见补 awaiting 与已认证冲突的用例。

