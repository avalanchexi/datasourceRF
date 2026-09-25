Status: done
Type: task
Blocked by: 11, 12

# 13 — 删除审阅输入路径与 v0001 旧计算

依据 ADR-0030（用户确认 v0001 一并删除）。

- 删除 v0002 的官方参考价比例调整链、成交额覆盖规则校验、审阅材料（成员池、窗口输入、成交额输入、期货时段证据）载入与对应来源契约分支。
- 删除 v0001 统一广度与收盘价篮子计算，以及 Worker 中的调用。
- 连同只为它们存在的测试一起删或改写；内置旧目录（v0001–v0003）不再计算这 7 项，缺口清单如实显示。

## Comments

- 2026-09-25 实施：删除 `market_breadth.py`、`market_amount.py`、`commodity_basket.py`、`futures_inputs.py`（合约解析并入 `basket.py`）、`futures_input_reads.py`；删除适配器的 `market_breadth_inputs`、`_reviewed_*`、`market_breadth`、`commodity_basket`、`acquire_futures_inputs` 与 `acquire_scalars` 里的审阅分支；删除 `require_commodity_results`、检索输入选择中的广度/篮子复核家族、来源契约中的 v0002 分支。删测试：`test_registered_commodity.py`、`test_commodity_basket.py`、`test_futures_inputs.py`、`test_market_breadth_inputs.py`、`test_registered_model_inputs.py` 尾部广度段、`test_tushare_context.py` 两例；仍有效的规则（换月、同到期歧义、合约身份、成员范围、响应字段歧义）移到 `test_basket.py`/`test_breadth.py`。内置旧目录与 v0004 不再计算这 7 项。
