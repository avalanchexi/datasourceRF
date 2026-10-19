# 03: ③ 美债利差补展示序列，人民币两卡写明缺哪几天

**What to build:** 美债 10 年减 2 年利差的派生记录没有 `display`／`change_5`（调查第 2 节，两条输入窗口齐全，应得 −12 基点）：为派生利差生成展示点列与近 5 日。人民币中间价、16:30 收盘价的"—"是窗口缺观测（现行规则正确），卡面改为写明缺哪几天（如"近 5 日 —（缺 10-15）"），不放宽窗口规则、不补取数据。改动在投影层，下一次真实运行后生效。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 投影测试：利差 display 点列与 change_5 正确；人民币卡 change_5.reason 带缺失日期
- [x] 页面测试：缺日说明可见
- [x] 两例冒烟通过

## Comments

**2026-10-19 实施（ticket-fd03，分支 fd-03，基于 main 50af742，已含 fd-02）**

改法：
- `display_projection.py`：`context_display` 拆出共用的 `_display`；新增 `difference_display`，按两条输入在同一交易日都有效的点算 `(左 − 右) × 倍数`，点列每点带 `input_claim_ids`（两条输入的 claim），`selected_claim_id` 为空；窗口缺观测时 `change_5`／`change_120` 除 `reason=window_session_missing` 外新增 `missing_dates`（窗口内缺的交易日）。
- `context_projection.py`：新增 `_treasury_spread_display`，取美债 10 年、2 年序列（同展示循环的采纳复核剔除），在美债市场日历上生成利差 display；只挂在有 `derived_observation_id` 的派生利差行上；点列与两窗口的输入 claim 并入 `display_inputs`，随投影冻结。
- `cockpit.py`：新增 `missing_note`；`change_cell` 在缺日时写"—（缺 10-15）"（超过 5 天截为"等 N 日"），抽屉 `_change_text` 写"—（窗口缺少实际交易日观测：缺 10-15）"。窗口规则未放宽，未补取数。

测试（venv dev-venv-fd03，basetemp /tmp/pytest-fd03）：
- 新增 `tests/integration/test_derived_context_freshness.py::test_treasury_spread_shows_its_own_points_and_five_day_change`（120 点、近 5 日 −5 基点、近 120 日 −120 基点、4 个输入 claim 已冻结）；`tests/integration/test_context_projection.py::test_a_five_day_window_short_of_sessions_names_the_missing_days`（中间价缺 08-26、08-27）；`tests/web/test_overseas_cards.py` 两例（缺日说明在卡面与抽屉可见；利差卡显示近 5 日 −12.00 基点与走势）。均先红后绿。
- `python tools/check.py quick` test_display_projection、test_context_projection、test_derived_context_freshness、test_day_summary、tests/models/test_registered_model_inputs 与 tests/web 全部 20 个文件：443 passed，280.5 s（与另一子代理重型测试并行，超 3 分钟目标）。
- 加跑 test_acquisition_outcome、test_gap_source_repairs：29 passed，171.6 s。
- 两例冒烟：2 passed，54.8 s。
- ruff check、ruff format、mypy（144 文件）通过。

偏离：
- 票面写"change_5.reason 带缺失日期"；为不破坏按 `reason` 代码映射中文的读者，`reason` 仍为 `window_session_missing`，缺失日期放在同一 change 的新字段 `missing_dates`。
- `test_full_run_retrieval.py` 未跑：其中唯一相关断言针对三核心 `core_display`（未改动），文件较重，单独运行 10 分钟未完。
- 下一次真实运行后生效；正式库旧投影不变。
