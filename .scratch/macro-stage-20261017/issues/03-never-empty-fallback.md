# 03: 永不为空的兜底

**What to build:** 宏观判断在任何一天都给出阶段：最高分并列 → 取 Pring 环形顺序上离上一确认阶段步数最少者（步数相同取前进方向），标"倾向"，① 写出并列的另一阶段与双方得分；已知维度 <3 或最高分 <3 → 在与当前三资产组合差异资产数最少的典型阶段中（价格组合典型时即价格阶段本身）取离上一确认阶段最近者，标"弱"，写明缺哪些维度；三核心不可用时取上一确认阶段（弱）。"不明"维度写明缺什么。"倾向""弱"永不显示为"明确"。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 02

**Status:** done

- [x] 单日汇总测试：并列前进一例、后退一例、步数相同取前进一例；证据不足在非典型组合（债牛·股熊·商牛，上一确认第三阶段 → 第三阶段（弱））与典型组合各一例；三核心不可用一例；所有用例主结论非空
- [x] `dashboard_page` 断言"倾向"时并列阶段与得分可见、"弱"时缺失维度说明可见
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms03，分支 ms-03）

- 选取（`macro_judgement.judge`）：先判证据不足（已知维 <3 或最高分 <3 → 弱），再判并列（→ 倾向，`nearest` 取环形步数最少者，等距取前进），否则唯一最高 → 明确；低分并列因此只会是"弱"。`raw` 新增 `fallback`（`source` combination／reference、`combination`、`differences`、`candidates`）与 `threshold`；`matched` 一律为所取阶段的得分（无阶段时为最高分）。
- 弱兜底：单日汇总 `_judge_macro` 在价格阶段原因为典型或非典型组合时传入当日三核心状态，取与之差异资产数最少的典型阶段（典型组合时差 0 即价格阶段本身），再取离上一确认阶段最近者；核心不可用或待补（`core_state_unavailable`／`core_data_pending`）时取上一确认阶段。典型组合表由 `derive_formal_stage` 推出，不另抄 ADR-0001 映射，不改 `single_asset_differences`。
- 校验（`validate`）：basis 与把握程度一一对应；明确须唯一最高且达门槛，倾向须达门槛且 `tied` 等于全部最高分阶段，弱须不足门槛且 `fallback` 与其组合重算一致；非明确阶段须等于按 `reference_stage` 重取的结果。"倾向""弱"因此不能被改成"明确"发布。
- 只更正上一确认阶段（`relink` → `with_reference`）：倾向与弱按新参照从同一并列集／候选重取阶段，不重新评分；`hysteresis` 为 None 时主结论即重取后的原始判断。
- ①（`macro_board`）：标题下加一行依据——倾向写"倾向第 X 阶段（与第 Y 阶段…并列，各 k 维）：取离上次确认第 M 阶段最近者"；弱写"弱判断：已知 k 维，缺…，不足 3 维；退回价格组合推断：…与…各差 n 项，取离上次确认第 M 阶段最近者"（或"价格组合典型…取价格阶段""三核心不可用，取上一确认阶段"）。"不明"维写明缺什么：多数决维"明确者不足半数（a/b）：已读票；缺当期读数：…／方向未读出：…"，库存"库存象限缺当期读数"。`wording.CORE_ASSET_NAMES` 新增。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms03`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms03`，`PYTHONDONTWRITEBYTECODE=1`。

- 新增 `tests/integration/test_macro_fallback.py` 16 例（并列前进 II→III、后退 I→VI、等距取前进 IV→V；非典型债牛·股熊·商牛、上一确认第三阶段 → 第三阶段（弱）；典型组合 → 价格阶段（弱）；三核心待补 → 上一确认阶段（弱）；更正上一确认阶段后弱判断重取；并列与弱各篡改用例 4／5 例被校验拒绝）、`tests/web/test_macro_fallback_board.py` 3 例。并列三例共用一个宏观夹具（10-15 型、PPI 改为年内低位上行 → III、V、VI 各 3 分），只换三核心组合。
- 受影响测试（`PYTHONPATH=src`，flock）：`python tools/check.py quick tests/web/*.py tests/integration/test_macro_judgement.py tests/integration/test_macro_fallback.py tests/integration/test_confirmation_publish.py tests/integration/test_confirmation_projection.py tests/integration/test_confirmation_policy.py tests/integration/test_confirmation_inventory.py tests/integration/test_confirmation_bond_attribution.py tests/integration/test_day_summary.py tests/integration/test_backfill.py tests/domain/test_pring_stage.py tests/integration/test_model_version_switch.py tests/reports/test_noncanonical_reading.py tests/integration/test_display_projection.py` → 568 passed，513 秒。
- 两例冒烟（`PYTHONPATH=src`）→ 2 passed，46 秒。
- 重装包副本（`uv sync --reinstall-package pring-cycle`）后不设 `PYTHONPATH` 复跑本票与 02 的四个宏观文件＋两例冒烟 → 36 passed，133 秒。
- `ruff check src/pring_cycle/`、`mypy`（包）通过。
- 收尾时 `macro-stage` 头仍为 fa7c0c2（04 未合入），本分支即基于它，无需合并。

### 与票面／规格的偏离与取舍

- **三核心不可用且无上一确认阶段**：无可取阶段，发布 `stage`／`confidence` 为 None（`fallback.source` reference、`candidates` 空），标题写"宏观判断：无可取阶段（证据不足、三核心不可用且无上一确认阶段）"；不默认第一阶段（代码地图"未查实"一条）。这是"永不为空"唯一的例外，需用户确认是否接受。
- **并列或非典型兜底而无上一确认阶段**：取候选中 Pring 顺序首个（与原型 `nearest` 一致），页面写"无上一确认阶段，按 Pring 顺序取首个"，仍标倾向／弱并列出全部候选。
- "三核心不可用"按价格阶段原因判：`core_data_pending`（核心待补，即使状态可读）也算不可用，不用部分核心比对（原型对部分核心"仅比已知核心"，票面未要求）。
- `raw.matched` 在弱判断时为所取阶段得分，可低于最高分（例：非典型例取第三阶段 2/2）；标题仍写"k 维中 m 维吻合"。
- 02 的"未达明确判断（…）"标题已删除。

### 给后续票的接口

- **05 滞回**：`judge(rules, confirmation, reference=…, cores=…)` 的 `raw` 已永不为空（除上面一种例外），`raw.confidence` ∈ explicit／tendency／weak；决定 44 的"弱不顶替更强结论"可直接读 `raw.confidence` 与前一日 `conclusion.confidence`。`conclusion(raw, reference)` 不变；滞回保持时 `with_reference` 只重述主结论步数（`hysteresis` 非 None 分支），原始判断仍按新参照重取——05 若需滞回状态随更正重算，在该分支补。校验 `_raw_consistent` 只约束 `raw`，主结论只校验步数与吻合数，05 的主结论可与原始判断不同。
- **08 阶段史**：每日应记 `conclusion.stage` 与 `conclusion.confidence`；二者可同为 None（上面的例外），色带需有"无可取阶段"的空格表示。`raw.basis`／`raw.fallback.source` 可用于标注弱判断来源，但阶段史只记主结论。
