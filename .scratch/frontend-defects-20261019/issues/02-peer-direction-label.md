# 02: 同类观察"方向"列改为"较上期方向"并写比较日期

**What to build:** 同类观察表与 ③ 海外卡的"方向"实为最新一期对上一可用期，与"近 5 日"口径不同（调查第 1 节：40 行全部符合代码，18 行符号相反）。列名改"较上期方向"，悬停与抽屉写出比较的两个日期；美债 10 年减 2 年利差卡的方向当前表示"大于零"，改为与其他卡一致的较上期方向（或在该卡改写为"正值／倒挂"，不得再写"上升"）。不改"近 5 日"口径。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 页面测试：列名、比较日期出现在悬停／抽屉；利差卡方向语义正确
- [x] 投影或渲染测试覆盖利差方向（渲染测试）
- [x] 两例冒烟通过

## Comments

- 2026-10-19 ticket-fd02（分支 `fd-02`）：只改页面（`cockpit.py`），不改投影。同类观察表列名"方向"→"较上期方向"；③ 海外卡方向前加"较上期"；悬停 `title` 写"较上期：上期 → 本期（非近 5 日）"，抽屉字段改"较上期方向 ↓ 下降（上期 → 本期）"。上期日期取自行内 `display.points` 中 `selected_claim_id` 等于 `direction_input_observation_version_ids` 的那一点（即后端方向比较所用的上一可用期），故**正式库现有投影立即生效**，不必等下次运行；找不到时写"上期日期未提供"；无方向输入的行（按正负记方向的派生行等）保留"方向"原样，不冒称较上期。
- 美债 10 年减 2 年利差：卡面改写"正值（未倒挂）／倒挂／零"（按 `value` 正负，悬停"按利差正负，不是较上期方向"），抽屉字段"利差正负 正值（10 年高于 2 年）"；不再出现"上升／下降"。选了票面的第二种做法（页面改写），未改后端派生记录的 `direction`，以免与票 03 在 `_difference_row`／派生利差处冲突。
- 新测试（先红后绿）：`tests/web/test_asset_cards.py::test_the_direction_compares_the_previous_period_not_the_5_day_window`、`::test_a_direction_whose_previous_period_is_not_among_the_points_says_so`；`tests/web/test_overseas_cards.py::test_a_card_says_its_direction_is_against_the_previous_period_and_names_both_dates`、`::test_the_treasury_spread_reads_its_sign_as_positive_or_inverted_never_as_rising`；改写两处旧断言（列名与抽屉字段）。
- 测试：`python tools/check.py quick tests/web/test_*.py` 182 passed（31.1s）；两例冒烟 `flock /tmp/pring-heavy.lock python -m pytest …test_manual_run_cannot_backdate_daily_core_availability …test_worker_completes_a_valid_noncanonical_projection_and_report` 2 passed（45.9s，另等锁约 3 分钟）；ruff、ruff format、mypy 通过。合并 main（c653c24）无新提交，结果即合并后结果。
- 正式投影核对（只读取正式库当前投影 `projection-554b0640f5f9d167fb6a` 的数据集，在内存中渲染，未复制库、未起站）：同类观察 40 行全部解析出上期日期（股票、商品 10-16 → 10-19，债券、两融 10-15 → 10-16，原油 10-13 → 10-14）；海外卡 16:30 收盘价为 10-14 → 10-19（上一可用期不是上一交易日的实例）；利差卡显示"正值（未倒挂）"。
- **偏离**：未做浏览器自查（改动只是文字与 `title`，最长新增"较上期 "四字），留给集成票 04 一并看 390 宽下海外卡是否换行。

