# 04: 信号清单

**What to build:** 宏观判断下方的信号清单，汇总三类转折信号，每条写支持的阶段转换、相对主结论的前进／后退／维持归组与信号成熟度（萌芽／成形／确认）：① 分化的关键指标（含贷款各成员），写哪个指标分化、少数成员指向；② 同源价格信号（相对动量、股市广度、商品篮子分项广度、同类观察与核心背离）按 v0016 冻结的价格信号转换对照表映射，标"同源，不参与投票"；③ 既有转折观察（30 日候选方向、资产候选状态）并入同一清单。清单随投影发布并在 ① 按前进／后退／维持分组显示；② 段"价格内部一致性（不计数）"等同源标签改为指向清单中对应条目。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 02；对照表以 01 用户确认版为准

**Status:** done

- [x] 单日汇总测试：分化指标与贷款分化进入清单并写少数成员方向；价格信号按对照表映射到正确转换；原转折观察并入；归组正确
- [x] 模型版本测试：价格信号转换对照表随 v0016 冻结
- [x] `dashboard_page` 断言清单分组与条目文本、② 同源标签的指向
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms04，分支 ms-04）

- 对照表：新模块 `macro_signals.py` 的 `table_v0001()` 按 signal-table.md 定稿冻结进 v0016 清单新字段 `macro_signal_rules`（R1–R5、R9–R11；B2、B4；K2、K4；四组同类观察；P1–P6、C1–C6 翻转映射；成形 5 个交易日、20 日转向、30 日候选、分化成形 2 期），`SignalRules.from_manifest` 按 v0015 价格一致性规则校验（价差对、广度与篮子读法、同类须为该核心观察接口、格名唯一），经 `ContextProjectionRules.macro_signals` 与 `ModelRules` 读入。v0015 不变。
- 构建：`DaySummaries._judge_macro`（目标日与补算日共用）在判断与主结论之后调用 `signal_list`，按主结论环形步数归组（前进／后退／维持／转换未定／资产转向（未映射阶段））。相对动量水平取已发布 `price_consistency` 的方向，转向由核心收盘价在前移 20 个交易日的 121 个交易日上重算（`price_consistency.relative_momentum`）；同类观察 30 日候选从观察接口已发布行的 120 日展示点读取（`domain.trend.candidate_direction`，与核心同一读法）；核心候选取单日汇总的 30 日候选与资产候选状态。分化：按少数成员方向改投该指标重判（贷款加入信用维投票），由 `rejudge` 回调走宏观判断自身规则。
- 成熟度：对照表信号连续交易日数从前一交易日最新发布的宏观判断块接续（新增 `ProjectionSetRepository.macro_judgement_on(day)`），萌芽不列、单独发布在 `sprouts`；当日两格指向同一转换即成形；目标阶段为当日价格阶段即确认。分化全部列出，同指标连续 2 个统计期分化为成形，否则萌芽。
- 校验：`macro_signals.validate` 接入投影校验（同 id 不重复、归组与步数自洽、对照表萌芽不得列入）；`relink` 更正上一确认阶段时 `regrouped` 按主结论重新归组（为票 03 的重选留口）。
- 页面：① 五维之下新增"信号清单"按组列出，每条 `id="signal-<格>"`；新板去掉"转折观察"行（已并入）。② "价格内部一致性（不计数）"改为"价格内部一致性（同源，不参与投票）"并链接清单中 R／B／K 条目；同类观察抽屉"用途"改为"同源，不参与投票"并链接本资产的 P 条目。旧投影不变。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms04`，`PYTHONPATH=src`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms04`，`PYTHONDONTWRITEBYTECODE=1`，`flock /tmp/pring-heavy.lock`。

- 新增 `tests/integration/test_macro_signals.py`（16 例：对照表冻结与 5 种拒收；PMI 分化与贷款分化；R2／R11 映射与成形、4 日萌芽不列；同类观察翻转 P1 成形、P3 未映射；核心 30 日候选 C1；清单自相矛盾拒发 4 例）与 `tests/web/test_macro_signal_board.py`（3 例：分组与条目文本、② 同源标签指向、旧投影保留）。
- 受影响测试：`python tools/check.py quick tests/web/*.py tests/integration/test_macro_signals.py tests/integration/test_macro_judgement.py tests/integration/test_confirmation_publish.py tests/integration/test_confirmation_projection.py tests/integration/test_confirmation_price_consistency.py tests/integration/test_confirmation_policy.py tests/integration/test_confirmation_inventory.py tests/integration/test_confirmation_bond_attribution.py tests/integration/test_day_summary.py tests/integration/test_backfill.py tests/domain/test_pring_stage.py tests/domain/test_trend_state.py tests/integration/test_model_version_switch.py tests/reports/test_noncanonical_reading.py tests/integration/test_display_projection.py` → 652 passed，481 秒。加 `regrouped` 后复跑 `test_macro_signals.py test_day_summary.py test_macro_signal_board.py` → 43 passed，76 秒。
- 两例冒烟：`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 2 passed，49 秒。
- ruff check／format、mypy（改动的源文件）通过。

### 偏离与取舍

- 成熟度用"前一交易日已发布块接续"的有状态计数（同原型），不从价格历史倒推：v0016 生效首日起计，前 4 个交易日只有"两格同指"或"确认"的对照表信号能入清单；前一交易日无汇总或无宏观块即从 1 重计，不跨缺失日累计。
- 分化信号只有萌芽／成形两级（同原型），不设"确认"；政策、库存维分化无改投重判，归"转换未定"。
- 分化条目 `transition.from` 取主结论阶段；对照表 R／B／K 取表内起点；P／C 取当日价格阶段（非典型时为空，文案写"翻转后为第 N 阶段／非典型组合"）。
- 股市广度（B）、商品篮子（K）的映射已实现，但 v0001 测试目录没有站上 90 日均线占比、分项贡献缺 sleeve 维度，单日汇总缝下未单独写用例（与 R 同一读法路径）。分化跨期成形也未单独写用例（需跨月补算窗口，代价高）。
- 票 03 尚未合入：并列时重判阶段为空，PMI 分化暂归"转换未定"；03 合入后应为第三阶段（倾向）、支持后退，页面测试只断言前缀与成熟度，合并时可收紧。合并 03 时 `rejudge` 回调须传 `cores=`（与 `_judge_macro` 同一核心状态）。
