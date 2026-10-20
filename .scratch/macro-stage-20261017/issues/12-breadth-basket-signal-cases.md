# 12: 股市广度、商品篮子背离信号的单日汇总层用例

**What to build:** 为 B2、B4（股市广度背离）与 K2、K4（商品篮子背离）补单日汇总缝上的行为用例：另建 v0006 指标目录的单日汇总夹具（含 `CN_EQ_ABOVE_MA90`、分项贡献 `formula_version／sleeve` 维度），核心与宏观数据都放在 v0006 上。依据决定 57、review-fixes-20261019.md F13。

**Blocked by:** 10（激活后做，不阻塞激活）

**Status:** done

- [x] 单日汇总测试：B2、B4、K2、K4 各按对照表映射到正确转换、成熟度与归组
- [x] 两例冒烟通过

## Comments

- 2026-10-20（ms-12）：`tests/integration/test_macro_signals.py` 末尾新增"catalog v0006 单日汇总"一节：夹具 `register_v0006`（model-v0016 换夹具名登记，catalog v0006 含 `CN_EQ_ABOVE_MA90` 与分项贡献 `formula_version／sleeve`），用例 2 个，均走 `DaySummaries.summarize_target`：
  - 第三阶段（三核心牛）：广度 38% → B2 Ⅳ→Ⅴ，较主结论Ⅲ前进 2，首日单格为萌芽、不进清单；篮子 3/7 分项下跌 → K4 Ⅱ→Ⅲ，维持 0，目标即当日价格阶段 → 确认、首日进清单。
  - 第一阶段（债牛·股熊·商熊）：广度 58% → B4 Ⅰ→Ⅱ，前进 1，与同日 R5（Ⅰ→Ⅱ，股票对债 −88.22pp、20 日 +10.60pp）两格同指 → 首日成形进清单；篮子仅原油上涨 → K2 Ⅴ→Ⅵ，环形后退 1，萌芽。
  - 两例都断言另两格不落格。
- 未发现生产代码与对照表不符，生产代码未改。变异核对：临时把 B2 目标改Ⅵ、B4 起点改Ⅵ、K2 去掉 `single_sleeve_rise`、K4 目标改Ⅳ，两例都失败；改回后通过。
- **偏离 1（宏观数据不在 v0006 上）**：票面要求"核心与宏观数据都放在 v0006 上"。v0006 是登记目录，取数时按登记来源契约逐条校验（LPR 须中国货币网、社融须人民银行、PMI／PPI／GDP 等须国家统计局，工业增加值累计须 `year_to_month`），汇总时 `ClaimAdoption` 还要按原件复核核心与官方宏观数据：没有原件的 claim 不予采用，核心报 `source_original_invalid`。核心改用 `refresh_core_history`＋假 TuShare 传输生成真实原件（时钟固定在目标日北京时间 19:00，早于截止）。官方宏观原件（货币网、统计局、人民银行页面，或 TuShare cn_ppi／cn_pmi／sf_month／cn_gdp 交付）要逐族构造，工作量与本票不相称，所以没有放宏观数据：判断按票 03 弱判断取参照阶段（即当日价格阶段 Ⅲ／Ⅰ），归组相对这个主结论计算。广度、分项贡献不在复核族内，直接写 claim。
- **偏离 2（成熟度只测首日）**：没有走 5 日连续成形，因为核心原件按抓取时刻可见，多日补算要分日抓取。三种成熟度（萌芽、两格同指成形、确认）用单日构造覆盖；5 日成形已有 R2 用例覆盖。
- 测试（venv `dev-venv-ms12`，basetemp `/tmp/pytest-ms12`，`PYTHONDONTWRITEBYTECODE=1`，flock `/tmp/pring-heavy.lock`）：`python tools/check.py quick tests/integration/test_macro_signals.py tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability tests/integration/test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 25 passed，135 s（新增两例各约 10–12 s）。main 头仍为 2f876b2，合并无变化。ruff check／format 通过；mypy 本文件只剩一条既有错误（原 451 行，现 467 行）。
