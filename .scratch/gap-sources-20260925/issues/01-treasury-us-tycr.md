Status: done
Type: task

# 01 — 美债按生效目录登记的 `us_tycr` 入库

规格“美债”一节（用户故事 11–12）。

- 注册来源校验：目录登记为 `us_tycr.y2/y10` 时按 TuShare 契约比对（provider `tushare`、`tushare:us_tycr:<字段>:<日期>`），只有目录本身登记财政部来源码时才走财政部 CSV 分支。
- 持有判定（投影、补缺证据）对 TuShare 声明以 `us_tycr` 原件重解析核对，财政部声明仍用 CSV 原件核对。
- 验收：生效目录完整运行中 2Y、10Y 持有，2s10s 利差派生，三项不在缺口清单。

## Comments

- 2026-09-25 实施：`source_contract_review` 按目录登记的来源码分派（`us_tycr` → `treasury_tushare`），新增 `parse_treasury_acquisition` 供持有判定重解析 `us_tycr` 原件；财政部 CSV 分支保留给登记财政部来源码的目录。主接缝 `tests/integration/test_gap_source_repairs.py::test_treasury_yields_are_held_from_tushare_us_tycr`。
