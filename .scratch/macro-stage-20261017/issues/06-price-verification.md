# 06: 价格验证行与抽屉

**What to build:** ① 宏观判断下方一行"价格验证"：价格阶段（或非典型组合）、宏观判断阶段预期的三资产组合、一致或哪项资产偏离；行抽屉收"只差一项"的比较与确认度（预期表对价格阶段，仅有价格阶段时显示）。价格阶段规则不变（非典型时仍为空）。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 02

**Status:** done

- [x] 单日汇总测试：价格验证一致、单资产偏离、非典型组合三例
- [x] `dashboard_page` 断言价格验证行文本、抽屉内只差一项与确认度、无价格阶段时确认度不显示
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms06，分支 ms-06）

- 新模块 `macro_verification.py`：`verification`（纯函数）、`verified`（给块写入）、`restated`（参照更正后重算）、`validate`、`combination_of`、`TYPICAL`（六阶段典型组合，由 `derive_formal_stage` 反推，不动价格阶段规则）。
- 构建位置：`P0ProjectionService.publish` 在 `noncanonical_basis` 之后写 `macro_judgement.price_verification`（目标日与补算日同经此处，且在 05 的滞回与 04 的信号之后，读到的是最终主结论），计入投影身份；`relink` 在 `regrouped(with_reference(...))` 外再套 `restated`，03 让更正可改变倾向／弱的阶段，价格验证随之重算（未单写测试，同 02）。
- 投影校验：`validate_analytical_projection` 调 `macro_verification.validate`，要求价格验证与本集三核心、价格阶段、`noncanonical_basis.comparisons` 及主结论阶段逐字一致，否则 `projection_macro_judgement_invalid`；没有该字段的块（旧判断）放行。
- 页面：① 左栏在信号清单下只留一行"价格验证"（整行为抽屉触发）；原"价格阶段"与原因、只差一项、上次确认、核心沿用、判法各行收进抽屉；确认度（标题注明"对价格阶段第 N 阶段"）只在有价格阶段时进抽屉。新投影的右栏去掉确认度，kicker 改"旁注"，其余四行不变；旧投影左右栏原样。
- 合并 macro-stage 4fb29cf（含 03）：`macro_board.py` 导入冲突；把本票的组合文字并入 03 的 `_cores`（新增 `unread` 参数，价格验证写"不可用"，03 的兜底仍写"不明"）。

### 发布结构（给 09）

`cycle_overview.macro_judgement.price_verification`：`price_stage`（价格阶段或 None）、`reason`（价格阶段的 `stage_reason`）、`combination{bond,stock,commodity}`（bull／bear，不可用为 None）、`expected_stage`（主结论阶段，无阶段为 None）、`expected{...}`（该阶段典型三资产）、`deviations[]`（读到且不符的资产，按债股商顺序）、`verdict`（consistent／deviates／unavailable：有偏离即 deviates；无偏离但有核心不可用或主结论无阶段为 unavailable）、`comparisons[]`（非典型时即 `noncanonical_basis.comparisons`，否则空）。整句文案 `macro_board.verification_line(block)`，不依赖 dash。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms06`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms06`，`PYTHONDONTWRITEBYTECODE=1`，在 `flock /tmp/pring-heavy.lock` 下。

- 新测：`tests/integration/test_price_verification.py`（一致、典型单资产偏离、非典型＋只差一项、4 例篡改校验）7 例；`tests/web/test_price_verification_board.py`（偏离行与顺序、抽屉原因各行与确认度、一致、非典型抽屉只差一项且无确认度）4 例。改 02 的 `test_macro_judgement_board.py` 一处断言（价格阶段旧行 → 价格验证行）。
- 合并后受影响测试（`PYTHONPATH=src`）：`python tools/check.py quick tests/web/*.py tests/integration/test_macro_judgement.py tests/integration/test_macro_signals.py tests/integration/test_macro_fallback.py tests/integration/test_price_verification.py tests/integration/test_confirmation_publish.py tests/integration/test_day_summary.py tests/integration/test_backfill.py tests/integration/test_core_history_correction.py tests/domain/test_pring_stage.py tests/reports/test_noncanonical_reading.py tests/integration/test_display_projection.py tests/integration/test_model_version_switch.py tests/integration/test_confirmation_projection.py` → 417 passed，741 秒。
- 重装包副本后：两例冒烟＋本票新测 11 例 → 13 passed，73 秒。
- ruff check、mypy（src 全量）通过。

### 与票面／规格的偏离与取舍

- 抽屉内容多于票面：除只差一项与确认度外，02 暂留的原因、上次确认、核心沿用、判法各行一并收进抽屉（02 Comments 约定由本票收进价格验证行）。
- 右栏标题"旁注"为本票自拟（确认度移走后右栏只剩价格一致性、库存象限、债券归因、数据边界四行），待用户验收时确认用词。
- 板副标题"正式阶段 · 三核心 · 确认度 …"未改（02 也未改），留给 07 或 10 统一。
- 无价格阶段时抽屉不出现任何确认度文字（不写"不适用"）。
- 核心不可用时行写"暂无价格阶段（… 不可用）"，并注"X 不可用，未比对"；主结论无阶段时写"宏观判断无阶段，不比对"。这两种未写页面测试。

