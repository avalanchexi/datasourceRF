Status: done
Category: enhancement
Type: task

# 10：体检内置新口径生效时刻

**What to build:** 体检派生层内置新口径生效时刻 `2026-10-14T03:40:33Z`（做法同现有 ADR-0036 生效时刻，以运行受理时刻判新旧）：生效前的运行按“该日结束”读，生效后按运行截止读，不再误报“库中期次晚于独立判断”。口径文档同步。守体检线规程。落实[来源票 05](05-audit-new-cutoff-effective-time.md)；见[规格](../spec.md)“体检的新口径生效时刻”。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 实跑对账 `run-0a8dabc2e820321b84e1`：结论与已存报告一致（差异只来自留存清理时逐项说明）
- [x] 实跑对账 `run-25ac18e4e3d329e1ea07`：派生层无“库中期次晚于独立判断”误报
- [x] `docs/development/data-quality-audit.md` 写明生效时刻与新旧口径

## Comments

- 2026-10-14 实施（体检线）：`tools/quality/derived.py` 新增 `NEW_CUTOFF_IN_EFFECT = "2026-10-14T03:40:33+00:00"`。逐日核对窗口内其他日子时，若该日投影是生成运行自己的目标日，且该运行受理不早于此时刻，按该运行冻结截止读（规则同目标日）；生效前运行的目标日投影、补算日、找不到生成运行的投影，照旧按该日结束读。只用标准库、不导入生产代码、数据库只读。
- 对账（详见 [audit-reconcile-ticket10.md](../audit-reconcile-ticket10.md)；报告 [0a8dabc2](../audit-run-0a8dabc2-ticket10.md)、[25ac18e4](../audit-run-25ac18e4-ticket10.md)）：
  - `run-25ac18e4…`：与已存报告逐字一致，派生层“库中期次晚于独立判断”0 处。
  - `run-0a8dabc2…`：改动前后实跑逐字一致；与已存 ticket04 报告的差异全部来自 `run-25ac18e4…` 完成后留存删除 2026-04-14（窗口首日）的明细与投影，已逐项说明（第一层 04-14 由已持有转未取到、派生层 9 项待开票、核心追溯断链 420→423、三核心 04-14 未解释）。这与上一批验收遗留 9 相符。
  - 代码路径冒烟：在临时副本里把生效时刻提前，确认新分支会命中 10-12 投影，结论不变；临时副本未提交。
- 口径文档：`docs/development/data-quality-audit.md` 的“公开截止”新增生效时刻一条；派生数据的“原料”与“新旧口径的区分”（替换原“局限”段）同步改写。
- 遗留：真正的生效后场景，要等票 13 收尾运行后的体检实证（届时 10-13 投影按 `run-25ac18e4…` 冻结截止读）。
