Status: done
Category: bug
Type: task

# 08（02b）— 相同定义：已持有日与入库查重

**What to build:** 按版本判断"已持有"的取数决策改为认相同定义版本组，换目录后不再把相同定义的已持有日当成缺日重取。

**Blocked by:** 07

**勿并行：** 07、09

## 验收

- [x] 广度已持有日、商品篮子已持有水平、郑商所仓单 `_held_totals`、核心补缺与目标交易日、信用脉冲输入（含 GDP 同次交付 `delivered_values`）、发布日历、来源入库前查重（`latest_source_claim`、`source_claim_vintages`、`claims_for_release_source`、`release_events_for_definition`）认相同定义版本组。
- [x] 回归：激活只改了信用脉冲的新目录后，已持有的广度、篮子、仓单日期不再重取；来源代码变化的指标（v0012→v0013 广度）仍重取。
- [x] 受影响测试、两例冒烟、`test_worker_registered_catalog.py`、`test_core_carry_forward.py` 通过；Codex 两轴审查无阻断。

## Comments

**2026-10-03 实施记录**（在 07、09 之后）

- **已持有日不需另改**：Worker 的广度已持有日、篮子已持有水平、核心补缺、目标交易日与郑商所 `_held_totals` 都经 `metric_series` 读取，票 07 已让它们看见相同定义的旧版本声明；本片加回归确认郑商所已持有日跨版本可见。
- **按版本精确过滤的入口**（`evidence.py`）：新增 `_defined_alike_clause`（单指标用版本组 `IN`；不指定指标时每指标算一次版本组，(指标, 版本) 对以 `json_each` 单参数传入，不受参数上限约束）；`delivered_values`（GDP 同次交付）、`latest_provider_claim`／`latest_source_claim`（入库查重）、`source_claim_vintages`、`release_events_for_definition` 改用它；`claims_for_release_source` 先按发布来源查出，再逐行 `defined_alike` 过滤。`release_events_for_definition` 指定版本时按统计期＋维度计观测数，未指定版本仍按存储编号。
- **入库查重语义**：同来源、同值、同显式发布时间且无新获取凭据时复用已有声明（可能盖旧版本戳），不写重复声明；带新凭据仍追加并建立链接。**修订链边界（只记录）**：跨版本首次追加的声明 `supersedes_claim_id` 可能为空（`_append_source_claim` 按存储编号找前驱）；读取按来源与时间取最新，不依赖此链，选值不受影响。
- **改写原测试**：`tests/adapters/test_tushare_context.py::test_candidate_context_same_value_can_move_to_a_new_definition_version` 与 `tests/adapters/test_eia_context.py::test_eia_same_value_can_be_reingested_under_a_new_definition_version` 要求同值在新目录版本下重入库产生新版本声明——PMI 与 EIA 价格在 v0001/v0002 定义相同，固化的是被 ADR-0036 取代的旧规则；改为同值复用原声明（`…_under_a_like_defined_version_keeps_its_claim`）。
- **测试**（`test_same_definition.py` 新增 5 例，共 25 例）：GDP 同次交付跨版本整体读出、入库查重／版本历史／按发布来源／发布事件找到旧版本声明（撤掉本片改动时前两例失败）、定义变化不读旧声明、郑商所已持有日跨版本、发布事件跨版本只计一个观测。
- **验证**（`PYTHONPATH=src` 直跑 pytest）：受影响 17 个文件（同定义、发布日历、每日重取、上下文回执、TuShare／保证金候选／EIA 适配器、Worker 复核上下文、信用脉冲、郑商所仓单、ECB、篮子、广度、核心沿用、完整目录正例、两例冒烟）247 例中 245 过、2 败（上述两个旧规则测试），改写与修正后相关 9 个文件 154 例全过。ruff、mypy 通过。
- **审查**（Codex 只读，两轮）：首轮 1 个阻断（发布日历跨版本重复计数），已修并补回归；采纳参数上限与扫描范围建议；二轮无阻断。**未覆盖、留给真实运行核对**：Worker 层"激活新目录后广度、篮子、仓单不再整窗重取"的行为（goal 真实运行验收第一项）。

