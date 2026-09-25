Status: done
Type: task

# 02 — 仓单按仓库合计，差额不符整批拒收

规格“仓单”一节（用户故事 13–16），依据 ADR-0029。

- `fut_wsr` 多行按“日期＋品种＋仓库＋交易所”分组求和 `vol`、`vol_chg`、`pre_vol`（全空不产出）。
- 同一成员前一交易日合计存在时核对 `Σvol_chg` 与当日合计减前日合计；~~不符拒收~~ 不符只在回执中记注记（2026-09-25 用户修订）。响应内首日无前日合计，不核对，并在回执规范化结果中注明未核对的日期。
- 回执绑定、成员数（`current_member_count`）以合计后的成员计。

## Comments

- 2026-09-25 实施：真实数据核对后用户改为“差额对不上只记注记、不拒收”（见 ADR-0029 修订）。`_warrant_members` 按仓库求和（单位不一致 `tushare_warrant_unit_conflict`、字段部分缺失 `tushare_warrant_member_field_partial` 仍拒收），回执规范化结果带 `warrant_reconciliation`（`unchecked_dates`、`mismatches`），重解析时核对注记。原“重复行即拒收”的测试改为单位冲突与部分缺失两例。
