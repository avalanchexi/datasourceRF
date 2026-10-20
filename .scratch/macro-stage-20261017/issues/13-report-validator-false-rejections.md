# 13: 报告宏观陈述校验误拒真实 AI 输出

**What to build:** v0016 首个正式运行（run-3ebbe323，目标日 10-19）的 AI 报告，codex 与 claude 两份输出都被 `macro_stated_stage` 误拒、退回确定性模板。两份输出对阶段、得分、把握程度的陈述都正确，是校验把合法提法归错了 subject。修复后，这两份真实输出应全部通过，真正改写主结论、得分或把握程度的输出仍被拒。根因、两份原文与离线复现见 `../investigations/report-rejection-20261020.md`。

三处误判：
1. 得分前缀缺"各得"："第三阶段、第四阶段、第五阶段各得 3 维"中的第四、第五阶段被归为主结论。
2. 否定的把握程度："不能解释为明确结论""不是明确的结论"被当作肯定的"明确"。
3. 条件推演的作用域："如果 PMI 改按少数方向计票……判断会变为第五阶段，把握程度为明确（5 维中 4 维吻合），对应第三阶段向第五阶段转换"中，阶段、把握程度和转换端点应按 `rejudged` 核对，而不是主结论。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 两份真实输出（artifacts 中 sha256 cefc2e68…、2e134d3a…，配冻结 bundle-612f01b4 的宏观块）固化为离线回归样本：整份文档通过校验，`confidence_told=True`
- [x] 上面三类真实句子各有整句正例
- [x] 反例仍拒收："各得 4 维"→ `macro_stated_score`；"宏观判断为第四阶段，把握程度为倾向"→ `macro_stated_stage`；"宏观判断为第三阶段，把握程度为明确"→ `macro_stated_confidence`；条件分句里写与 `rejudged` 不符的阶段或把握程度 → 拒收
- [x] 不靠扩大 `allowed["conclusion"]` 或"句中有否定词就跳过整句"来放行
- [x] 两例冒烟通过

## Comments

- 2026-10-20（ms-13）：回归样本 `tests/fixtures/report_input/rejected-readings-20261019.json`（冻结 bundle-612f01b4b419587fd525 整份 `document_json`，加 codex／claude 两份被拒原文，从正式库 `mode=ro`、正式 artifacts 只读拷贝）；用例在新文件 `tests/reports/test_real_macro_readings.py`，测试口径为 `ReportService.generate`＋`FakeAdapter` 看 `process_audit.rejection.check`（与 `test_macro_report.py` 同一口径，不依赖重型夹具）。两份整份输出均被采用（倾向结论须有肯定陈述才过，所以采用即 `confidence_told=True`）。
- 修复（`src/pring_cycle/reports.py`）：
  1. `_FOLLOWING` 得分前缀加 `各得`，仍逐阶段对 `macro.scores`。
  2. 新增 `_DENIED_CONFIDENCE`：把握程度词紧前是"不是／并非／不能解释为／不应视为……"时读作否定：判断的把握程度恰是该词才拒（`把握程度不是倾向` → `macro_stated_confidence`），否定不算告知（`宏观判断为第三阶段，不是明确的结论` → `macro_confidence_unstated`）。只看紧前的否定，不是整句跳过。
  3. 条件作用域：`如果／假如／倘若／假设／一旦／若` 起到"主结论／当前／目前／现在／当下／实际"之前（无则至句末），其间 conclusion 类标记改读为 signal（按 `allowed["signal"]` 核阶段与转换端点），绑在标记上的把握程度词改绑作用域内最近的阶段，按 `rejudged` 的（阶段，把握程度）核对。作用域后的现时陈述仍按主结论核对（`目前宏观判断为第五阶段` → `macro_stated_stage`，`当前把握程度为明确` → `macro_stated_confidence`）。`allowed["conclusion"]` 未扩大。
- **偏离（第四处误判，票面未列）**：三处修好后，claude 输出整份仍被 `restates_confirmation` 拒于 `sections[3]`（确认度说明）："……包括 PMI、PPI、CPI、社融、DR007 和库存象限，没有任何一项记为支持或反证"——否定与"记为"之间隔了"任何一项"，读成库存象限"记为支持"。为满足"整份通过"把 `_NEGATION` 加上可选的 `任何一?项|一项`，配整句正例与两个反例（改成"没有任何一项记为不适用"、"库存象限记为支持"均拒）。`_NEGATION` 也用于确认度计数与相对动量的否定读取，相关测试全过。
- 条件反例里"变为第四阶段"阶段本身能过（`allowed["signal"]` 含各重判的并列阶段），靠（第四阶段，明确）不在 `rejudged` 而拒于 `macro_stated_confidence`；"变为第六阶段""向第六阶段转换"拒于 `macro_stated_stage`。条件推演指的是哪一条信号不做区分，仍按全部信号的并集核对。
- 测试（venv `dev-venv-ms13`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms13`，`PYTHONDONTWRITEBYTECODE=1`）：
  - 受影响（flock `/tmp/pring-heavy.lock`）：`python tools/check.py quick tests/reports/test_cli_protocol.py tests/reports/test_macro_report.py tests/reports/test_noncanonical_reading.py tests/reports/test_real_macro_readings.py tests/reports/test_report_boundary.py tests/integration/test_confirmation_bond_attribution.py tests/integration/test_confirmation_price_consistency.py tests/integration/test_confirmation_publish.py` → 合并前 321 passed（317 s），合并 macro-followups cd25885 后 321 passed（281 s）；超 3 分钟目标，主要是 `test_macro_report.py`／确认度发布的模块夹具。新文件单跑 20 passed，约 2 s。
  - 冒烟：`python tools/check.py quick tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability tests/integration/test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 2 passed（74 s；锁被其他子代理长时占用，两例非重型文件，未加锁直接跑）。
  - `ruff check`／`ruff format --check`／`mypy`（reports.py 与新测试文件）通过；`find src tools -name __pycache__` 为空。
