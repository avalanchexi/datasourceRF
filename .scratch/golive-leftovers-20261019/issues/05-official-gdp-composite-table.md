# 05: 支持国家统计局"主要指标"综合发布表的 GDP 解析

**What to build:** 10-19 国家统计局发布的是"9 月份及前三季度主要指标数据"综合表（行名"一、国内生产总值（亿元）"、列序当季额／当季同比／累计额／累计同比、当季单元格带"（三季度）"），解析器只认 GDP 专表，报 `official_context_table_schema_mismatch`（调查第 5 节）。新增综合表契约，识别期次、列序与季度标注，统一输出规范化 GDP 行；GDP 三产业当季实际同比与信用脉冲的"官方当季名义值核验"共用此结果（原件 375,367 = 1,071,071 − 695,704，可恢复信用脉冲）。不用正文累计增速替代当季同比。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 解析测试：用已保存的 10-19 原件（或其最小化夹具）得四行正确数值；专表仍能解析
- [x] 集成测试：信用脉冲经官方当季值核验得出，不再 `incomparable_gdp_vintages`
- [x] 两例冒烟通过

## Comments

**2026-10-19 实施（ticket-gl05，分支 gl-05）**

改法：
- `official_context.py`：新增 `_gdp_table`／`_gdp_rows`／`_composite_gdp_rows`，专表与综合表统一输出每个总量一行（当季名义额、当季实际同比、累计名义额）。综合表按表头识别期次（`N月`／`1—N月`）与列序（绝对量、同比、绝对量、同比），当季单元格须带本季标注（如"（三季度）"）；行按位置取（投资分项下第一～三产业重名）。一季度综合表当季列为"…"时取 1—3月 列。解析、注册契约校验（综合表要求附注"国内生产总值及其分类项目增长速度按不变价计算"）与官方当季值核验共用此结果；不读正文累计增速。解析器版本仍为 v0004：专表输出不变。
- 官方当季值核验 `official_gdp_quarters_matching_baselines`：官方声明仍对照其自身原件（语义不变）；来自其他来源的所选累计值（新闻、单独补取的 TuShare 季度）对照截止前已入库的统计局同期原件，原件同时给出相同累计值与差分当季值即判同一版本。`EvidenceRepository.provider_acquisitions` 取某提供方某期声明背后的原件。`credit_impulse` 传入所选点、`definition_version`、`as_of`。
- 夹具 `tests/fixtures/official_period_fallback/nbs_gdp_composite_2026q3.html`：由失败回执 acquisition-b25d9d8b… 原件（raw 8818987a…）裁成 17 KB，表格逐格解析与原件一致；来源与裁剪写入同目录 README。

核验（正式库只读）：144 张已验证 nbs_gdp 官方回执在新代码下全部重建、规范化哈希一致；7 张曾因 `official_context_table_schema_mismatch` 被拒的综合表（2024-Q2／Q3／Q4、2026-Q1／Q2／Q3）现均可解析，数值与专表一致。正式库快照演练（scratchpad 内副本，已删除）：入库前信用脉冲 `incomparable_gdp_vintages`（2026-Q3）；按 Worker 方式扣留新闻已给的 5 个成员入库该原件后存入三产业当季实际同比 3 条，信用脉冲 `available`（22.60，GDP 窗口 2025-Q1～2026-Q3）。

测试（venv dev-venv-gl05，basetemp /tmp/pytest-gl05，flock /tmp/pring-heavy.lock）：
- 新增 `tests/integration/test_official_gdp_composite.py` 8 例：综合表四行、专表仍可解析、三种异形／他期表拒收；信用脉冲三例（无官方原件→不可比、综合表核验→available、累计值不符→不可比）。
- 受影响：`python tools/check.py quick` test_official_gdp_composite、test_gdp_semantics、test_official_gdp_fallback、test_official_listing_pages、adapters/test_official_listing_samples、adapters/test_official_context、test_receipt_counts、test_credit_impulse、test_worker_reviewed_context、test_derived_context_freshness、models/test_registered_model_inputs：合并前 407 passed（645.8 s）；合并 main（50af742，仅 cockpit 前端）后分两段复跑 160 passed（332.6 s）＋ 247 passed（299.6 s）。超出 180 s 目标，主要耗时 test_official_listing_pages（约 240 s）、test_registered_model_inputs（约 180 s），同时段有其他票测试并行。
- 两例冒烟：2 passed（50.7 s）。
- ruff check／format、mypy（改动的三个源文件）通过。

偏离：集成测试以"TuShare 单独补取 Q3"代替新闻声明（二者都不是官方原件，也都不与 Q2 同批），未走新闻解析链路；综合表不写现价口径，按统计局总量惯例视为现价，只校验不变价增速附注。

信用脉冲恢复：下次运行若仍从列表取到该综合表页（三产业当季同比缺口仍在，会再取），即可解析入库并经官方当季值核验恢复；若届时取到的是 10-20 的初步核算专表或 TuShare 给出含 Q2、Q3 的同批交付，同样恢复。
