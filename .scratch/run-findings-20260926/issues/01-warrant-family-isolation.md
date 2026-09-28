Status: done（真实运行未达成最后一条验收，见 run-findings-20260928 票 02）
Category: bug
Type: task

# 01 — 一个品种的坏行让仓单家族八个品种的历史一起被拒

来源：gap-sources 票 09 遗留 1（真实完整运行 run-64209ab01ac75439cc8c，目标日 2026-09-24）。

## 原始发现

票 09 记为“PTA 一条负数行让 PTA 的 220 天历史被拒”。核实后的实际波及面更大：**八个品种的历史都被拒收**，不只 PTA。

## Comments

> *本段由 AI 在分流时生成。*

### 分流记录（2026-09-26）

**已核实（代码路径）：**

- 仓单家族在 Worker 取数阶段只调用一次 `acquire_scalars`，取数函数里按 `sorted(WARRANT_SYMBOLS)` 依次取八个品种（`worker.py` 的 `futures_warrants` 家族）。`TA` 排在最后，PTA 抛出 `tushare_warrant_quantity_negative` 时，前七个品种已取回的回执会跟着全部 `fail_validation`，并且都还没入库（`tushare_context.py` 中 `acquire_scalars` 的外层 `except`）。
- 运行库：本轮 `fut_wsr` 共 162 张回执，**全部**被拒，拒收码都是 `tushare_warrant_quantity_negative`。八个品种在 `source_claim` 里都只有 9/24 一天，这一天来自上一轮的单日补缺。其余七个品种的原件里没有负数行。详见 [Codex 调查](../research/codex-warrant-rejection.md) 第 1–2 条。
- 目标日还算持有，但 120 日窗口里八个品种各缺 119 天。仓单的历史序列事实上是空的。

**决定（2026-09-26 用户确认）：** `bug`，`ready-for-agent`。无论票 02 的 PTA 口径怎么定，这里都该修：每个品种各取各收，一个品种被拒不再连累其他品种。这张票和票 02 相互独立，可以先做。

## Agent Brief

**Category:** bug
**Summary:** 仓单家族按品种隔离取数与拒收

**Current behavior:**
Worker 取数阶段把八个仓单品种（`WARRANT_SYMBOLS`）放进同一次 `acquire_scalars`。任一品种的原件在 `_warrant_members` 校验时抛错（例如 `tushare_warrant_quantity_negative`），本轮全部 `fut_wsr` 回执都会被记为校验失败，八个品种都不入库。2026-09-24 那轮就是这样：162 张回执全部被拒，其中只有 PTA 的原件含负数行。

**Desired behavior:**
每个品种的取数、校验、入库，以及回执的成败都独立。一个品种被拒不影响其他品种入库。被拒品种的回执照旧记拒收码，缺口清单只让这一个品种（`CN_FUTURES_WARRANTS` 的 `symbol` 维度成员）缺数。

**Key interfaces:**
- Worker 取数阶段的 `futures_warrants` 家族：拆成按品种分开的取数单位，或者在家族内逐品种调用 `acquire_scalars`。实施者自选，但每个品种的回执集合都要单独提交或失败。
- 家族级的取数指标记录（`acquisition_metrics`）与失败记录（`record`）：粒度跟着改成品种，至少要让被拒品种可以追溯。
- 负数拒收规则（`tushare_warrant_quantity_negative`）本票不改。

**Acceptance criteria:**
- [x] 一个品种的应答含负数数量行时，其余品种的回执都是 `validated`/`accepted`，各自的仓单标量都能入库。
- [x] 被拒品种的回执仍然记 `tushare_warrant_quantity_negative`，而且只有该品种的回执被拒。
- [x] 八个品种都干净时，行为与现在相同（同样的回执数、同样的成员合计、同样的核对注记）。
- [ ] （待真实完整运行）真实完整运行后，CU、RB、PP、CF、RU、SP、SC 七个品种在 120 日窗口内都持有完整历史。

**Out of scope:**
- PTA 负数行怎么处理、郑商所品种是否改走官网日报：见票 02。
- 仓单成员合计与差额注记规则（ADR-0029）。

- 2026-09-26 实施（TDD）：
  - **Worker 取数阶段：** 仓单家族拆成 8 个取数单位 `futures_warrants:<品种>`，各自一次 `acquire_scalars`；取数记录带 `family` 与 `symbol`。
  - **补缺单日重取（`targeted_context`）也按品种逐个取数**（第一轮复审指出期望行为没有豁免这条路径）。每个品种的账本请求各自结束，最后照原方式报出第一个失败；非仓单家族行为不变。
  - **缺口清单：** 拆开后会出现“部分品种持有目标日”的情况，于是暴露出一个回退，由第一轮复审指出：若 CU 失败、其余成功，仓单会被当作已持有，从缺口清单里消失。现在的做法有两点。
    - 时效判定对仓单改为“8 个品种的 `registered_receipts` 都有值的最新一天”才算持有，内置目录版本不变。
    - 取数失败原因按“指标＋`symbol`”取最后一次，一个品种的失败不会被后面品种的成功覆盖。第二轮复审发现，第一版按 `family` 分组会让 EIA 这类“接口→页面”的替补家族残留旧失败，已改为只按 `symbol` 分组，其他指标行为不变。
  - **测试：**
    - 新增 `tests/integration/test_warrant_symbol_isolation.py`，共 4 例：PTA 负数时其余 7 个品种持有 157 个工作日；只有 PTA 的回执被拒；CU 取数失败时仓单以 `fetch_failed` 列入缺口清单；补缺单日重取同样逐品种隔离。补缺那例用直通账本替身隔开检索账本，账本集成由 `test_search_evidence` 的补缺用例覆盖。
    - `test_search_evidence.py::test_targeted_warrants_records_each_of_eight_deliveries[3]` 原先断言“PP 重试耗尽后其余品种不取、0 个值入库”，这正是本票要改的捆绑行为，已改为“其余 7 个品种照取，入库 24 个值”。
  - **验证：**
    - 受影响测试（13 个文件）125 例：124 例通过，1 例即上述旧断言。改完断言后再跑相关的 8 个文件，31 例通过，用时 9 分 20 秒（超过 3 分钟目标，含多份整轮运行夹具）。
    - 冒烟 2 例 91 秒，完整目录正例 148 秒，三核心反例 193 秒，全部通过。C 盘 67G。
    - 审查走 Codex 两轮。
  - **未改（记录在此）：**
    - 投影在某天缺一个品种时，会把当天所有品种的行标为 `source_failed`。这是原有的“缺成员即整天不完整”策略，各品种的历史覆盖仍分别计算。
    - 补缺路径里被拒回执没有写 `rejection_reason`，这是原有的记录方式（原因码只在回执处于 `received` 状态时写入）。
  - 最后一条验收准则要等下一次真实完整运行，建议与票 02 做完后一起跑。

### 真实运行验收（2026-09-28）

> *本段由 AI 在验收时生成。*

真实完整运行 `run-dc0bb2d9db7068bf552d`，目标日 2026-09-24（9/25 中秋休市，9/26–27 周末），代码 `18899cf`，北京时间 12:58 开始，用时 57 分钟，状态 `completed`，1171 张回执。缺口清单与分流见 [run-findings-20260928](../../run-findings-20260928/README.md)。

- 隔离成立：6 个 TuShare 品种各自入库，没有整族被拒。
- **最后一条验收未达成**：120 日窗口（4/03–9/24）内 CF 120/120（已改由郑商所供数），CU 110/120，PP、RB、RU、SC、SP 各 119/120。
- 缺的日期来自 62 张失败的 `fut_wsr` 回执：20 张 `acquisition_time_invalid`（WSL 时钟跳变，见 20260928 票 01），42 张没有收到应答（按品种逐日请求约 720 次，疑似触发限频，见 20260928 票 02）。
