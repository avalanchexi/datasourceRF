Status: done
Category: bug
Type: task

# 16：派生指标的"输入覆盖完整"按整个家族判断，与投影的计算状态不一致

## 现象（票 09 审查发现，2026-10-09）

run-8a3779cff80f6bd586a0 的最终计划中，`CN_CREDIT_IMPULSE` 的 `input_coverage_complete=false`，但同一运行的投影把信用脉冲算出来了：`status=available`，值为 22.924257。

计划写入时（`full_retrieval.py:936` 一带），对 `required_input_periods` 中的每个指标家族，要求该家族**所有**缺口期都 `complete`。社融存量同比 2025-07、08 缺失（票 14），而信用脉冲公式并不用存量同比，结果标志仍被拉成 false。基线运行 run-4ae95443a6c4a6e63eb3 同样是 false，所以这是既有问题，不是本批引入的。

影响：只影响运行审计中的这个标志，不影响投影计算。但读审计的人会误以为信用脉冲因输入不全而没有算出来。

## 建议

覆盖判断只看公式实际使用的成员与期次，或者把字段改名，表明它是家族级的粗判断。

## 验收草案

- [x] 替身：公式用到的成员齐全，同家族另有一个不用的成员缺期；断言标志为 true（或改名后语义一致）。

## Comments

### 2026-10-09 分流

按 goal-round2.md 预设决定实施。

### 2026-10-09 实施（暂停：两轮审查后仍有阻断，未提交）

**改了什么**（工作区未提交）：

- `full_run_requirements.formula_requirements` 为每个派生条目新增 `formula_inputs`：公式读取的每个输入、每个期次及所读成员（None 表示目录要求的全部成员）。信用脉冲取目标日 minimum 期次，口径按模块自身规则（`credit_impulse.minimum_members`：版本不许差分或窗口每期都直接持有→直接口径，否则累计口径，基期同为累计口径）；其他公式按计划锚点由各自读数推出期次，成员取 `lookback.FORMULA_MEMBERS`（PMI 两差值、库存近似），`inventory-ppi-common-month-v0002` 的 PPI 锚定在产成品库存月份（`lookback.FORMULA_ANCHORS`），`LOAN_YTD_FORMULA` 一月只读一月（常量从 `context_projection` 提出并在原处复用）。
- `input_coverage_complete`（字段不改名）不再看整个家族的缺口：最终评估用选择器按公式所读成员逐期核验（`full_retrieval.evaluate` 的 `held()`）；某输入没有任何期次、或无输入规则时为 false。
- 计划的 requirements、检索与直连取数不变（公式成员表只用于覆盖判定）。

**测试**：

- 验收替身 `tests/integration/test_lookback_declaration.py::test_a_formula_s_input_coverage_counts_the_members_and_periods_it_reads`：社融只给累计增量、GDP 只给总量名义累计值（社融存量、存量同比、GDP 分产业与实际增速缺），信用脉冲标志为 true；去掉公式窗口内 2026-03 的累计增量后为 false；PMI 只给生产、新订单、产成品库存（制造业 PMI 等缺），两个 PMI 差值标志为 true。旧实现下正例红（`assert False is True`），反例绿。两例约 210 秒。
- 新增 `tests/integration/test_credit_impulse.py::test_a_day_s_minimum_is_read_by_the_measure_its_rule_reads_it_by`（口径选择，4 例）。
- 受影响测试：`test_lookback_declaration.py`、`test_derived_context_freshness.py`、`test_credit_impulse.py`、`test_loan_ytd_year_boundary.py`、`test_inventory_period_alignment.py`、`test_full_run_retrieval.py::test_credit_formula_expands_required_history_in_full_run_plan`：142 passed，13:56。
- 冒烟两例：2 passed，2:35（同时有其他子代理在跑测试）。
- ruff check、ruff format --check、mypy 覆盖改动文件：通过。

**审查**：

- 第一轮（标准、规格）均有阻断：缺口交集法查不到目录外的公式成员、信用脉冲直接／累计口径混用、给公式读数加 members 会改变旧目录的计划要求、库存 PPI 期次、贷款一月、公式期次不在缺口中等。已全部改为上面的做法。
- 第二轮：上述修复确认成立；"投影取最新共同期／计划按锚点"的差异两轴都接受为时效范畴（非阻断）。仍有阻断：
  1. 库存锚点误用于旧版本 → 已改为只对 `inventory-ppi-common-month-v0002` 生效（未再复审）。
  2. `omo_net_injection` 实际还读到期量（v0001 同日投放＋到期；v0002 显式到期量，否则一周前的历史投放与交易日依据），而声明与目录只有当日 `injection`，标志可能偏宽。
  3. `loan_monthly_change` 的存量版本（`loan-stock-monthly-change-v0001`）读 `stock_end`，内置目录无贷款成员契约，选择器判 `dimension_contract_unavailable`，标志恒为 false。

**需要决定**（2、3 超出信用脉冲这条现象，属于"其他公式各自实际读什么"的精度问题）：

- 方案 A（推荐）：本票按现状收尾——信用脉冲与 PMI 差值已按实际成员与期次判定；OMO 与贷款存量版本的精确读法记为遗留，另开票。理由：贷款存量版本旧标志同样为 false，不是退化；OMO 旧标志同样不看到期量，但它要求计划内所有日子的投放齐全，现在只看当日，对 v0002 读一周前投放的情形比旧标志宽（需在遗留票里一并处理）。v0015 使用 v0002 的 OMO 与累计口径贷款。
- 方案 B：本票内补齐 OMO 两个版本（到期量或一周前投放的替代读法）与贷款存量版本（按版本选 `stock_end`／`ytd_increment` 成员）的覆盖规则，再做一次复审。

### 2026-10-09 用户决定与实施（收尾）

**用户决定**：本票内补齐 OMO；贷款存量版本另开票 [18](18-loan-stock-v0001-coverage-flag.md)（needs-triage，与旧行为一致，不阻塞验收）。

**实施**：

- `omo_net_injection` 按版本判定（`full_run_requirements._repo_inputs`）：`REPO_SAME_DAY_FORMULA`（v0001）读锚点日的投放与到期量；`REPO_CALENDAR_FORMULA`（v0002）读锚点日投放，当日到期量已持有则读它，否则读到期日落在锚点日的那些交易日（加七天、顺延，复用改为公开的 `context_projection.repo_maturity_trading_day`）的投放。是否持有由选择器按成员逐期核验（`full_retrieval._held`），计划与最终评估都用它。两个版本号从 `context_projection` 提为常量并在原处复用。消除了相对旧标志的退化：旧标志要求计划内全部 OMO 日期齐全，现在要求公式实际读的那几天齐全，并补上到期量。
- 库存近似的 PPI 锚定只对 `inventory-ppi-common-month-v0002` 生效（`FORMULA_ANCHORS` 改按公式版本键控）。
- v0002 的交易日依据（核心股票当日价格）未纳入：它本身是计划的 P0 要求。

**测试**：

- 新增 `test_lookback_declaration.py::test_the_repo_net_injection_s_coverage_counts_what_its_version_reads`（5 例，约 2 秒）：v0002 只有当日投放→false，加一周前投放→true，加当日到期量→true；v0001 缺到期量→false，有到期量→true。实现前"只有当日投放"与"v0001 缺到期量"两例按旧逻辑判 true，红。
- 受影响测试（`test_lookback_declaration.py`、`test_derived_context_freshness.py`、`test_credit_impulse.py`、`test_loan_ytd_year_boundary.py`、`test_inventory_period_alignment.py`、`test_omo_invalid_flow.py`、`test_full_run_retrieval.py::test_credit_formula_expands_required_history_in_full_run_plan`）：156 passed，10:47。
- 冒烟两例：2 passed，2:26。
- ruff check、ruff format --check、mypy 覆盖改动文件：通过。

**审查**：定向复审（只验库存锚点按版本、OMO 两版本规则与 `_held` 接线）：两项修复成立，阻断：无。复审注明 OMO 节假日顺延与真实选择器链路由读码核实、未单独测试。

**遗留（非阻断）**：`lookback.FORMULA_MEMBERS` 的维度与 `context_projection` 字面量重复，改投影时须同步；信用脉冲口径选择规则在 `minimum_requirements` 与 `minimum_members` 两处维护；投影取最新共同期／候选日与计划锚点的差异属时效范畴（两轴接受）；贷款存量版本见票 18。
