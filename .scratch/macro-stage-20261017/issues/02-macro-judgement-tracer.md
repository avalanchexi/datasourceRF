# 02: 宏观判断贯通（明确路径）

**What to build:** 第一条贯通全层的切片：维度方向（分化指标按主要成员方向投票；信用维只由社融与 M1/M2 投票，贷款不进分母；信用、增长、物价附高低位；政策按 120 日内动作三态，"无动作"中性）、Pring 六阶段特征表与"唯一最高且 ≥3 → 明确"的选取写入新模型版本 v0016 清单（登记不激活，v0015 不变）；单日汇总在宏观与库存上下文之后计算并随分析投影集发布宏观判断块（主结论、把握程度、吻合维数、相对上一确认阶段的环形步数与前进／后退／不变、五维方向与依据、各阶段得分）；① 标题改为"宏观判断：第 N 阶段（明确，5 维中 k 维吻合）· 相对上次确认第 M 阶段 前进／后退／不变"，正文按货币周期、经济周期、库存周期三组列五维。旧投影无宏观字段时 ① 保持现状并提示"该投影生成时尚无宏观判断"，不补算。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 01（特征表与参数定稿）；合并上线任务（golive-20261019）验收后基于 main 建集成分支 `macro-stage`

**Status:** done

- [x] 单日汇总测试：10-15 型数据得第五阶段 4/5、明确、相对第三阶段前进两步；分化指标按主要成员投票；贷款不进信用维分母；政策"无动作"为中性
- [x] 模型版本测试：v0016 含特征表、门槛与高低位指标；未显式同意不生效；v0015 清单不变
- [x] `dashboard_page` 断言 ① 标题格式、三组五维顺序、旧投影提示
- [x] 价格阶段规则与既有"宏观无投票权"测试仍通过；两项冒烟通过

## Comments

### 2026-10-19 实施进展（ticket-ms02，分支 ms-02）

- 阶段 1：新增 `macro_judgement.py` 规则（特征表、门槛 3、投票指标、高低位指标、政策三项、库存象限）与 `model_v0016_manifest()`（v0015 深拷贝＋`macro_judgement_rules`，`effective_model_manifest` 仍为 v0015）；`ContextProjectionRules.macro_judgement` 解析校验。模型版本测试 2 例通过。
- 阶段 2：单日汇总共用步骤 `DaySummaries._judge_macro`（目标日与补算日同一规则，在上下文与上一确认阶段已知后、发布前执行），`P0ProjectionService.publish(macro_judgement=...)` 写入 `cycle_overview.macro_judgement` 并计入投影身份；`p0.stated_last_confirmed` 抽出供两处共用。单日汇总测试 4 例通过（10-15 型第五阶段 4/5 明确、前进 2 步；PMI 分化按主成员投票；贷款不投票、无动作中性；旧模型不发布）。
- 阶段 3：投影校验 `macro_judgement.validate`（五维顺序与分组、得分范围、明确须唯一最高、主结论步数按环形自洽）；`relink` 更正上一确认阶段时用 `with_reference` 同步主结论参照与步数（未另写测试）。① 新结论板移入 `macro_board.py`（标题、三组五维、其下保留价格阶段与原各行），旧投影保留原板并提示"该投影生成时尚无宏观判断"。受影响测试 548 例通过（470 秒）。
- 阶段 4（收尾）：`macro-stage` 头仍为 914614d，本分支即基于它，合并无新内容；重装包副本（`uv sync --reinstall-package pring-cycle`）后复跑。

### 测试记录（2026-10-19）

环境：`~/.local/share/pring-cycle/dev-venv-ms02`，`PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms02`，`PYTHONDONTWRITEBYTECODE=1`。

- 受影响测试（`PYTHONPATH=src`）：`python tools/check.py quick tests/web/*.py tests/integration/test_macro_judgement.py tests/integration/test_confirmation_publish.py tests/integration/test_confirmation_projection.py tests/integration/test_confirmation_policy.py tests/integration/test_confirmation_inventory.py tests/integration/test_confirmation_bond_attribution.py tests/integration/test_day_summary.py tests/integration/test_backfill.py tests/domain/test_pring_stage.py tests/integration/test_model_version_switch.py tests/reports/test_noncanonical_reading.py tests/integration/test_display_projection.py` → 548 passed，470 秒。
- 安装副本复跑：`python tools/check.py quick tests/integration/test_macro_judgement.py tests/web/test_macro_judgement_board.py tests/domain/test_pring_stage.py` → 25 passed，24 秒。
- 两例冒烟：`test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report` → 2 passed，57 秒。

### 与票面／规格的偏离与取舍

- 政策维：成员历史不完整（基准或某日公告缺）不增加动作；其他主要成员读到"无动作"即记中性；三项都读不到才"不明"。原型对全部读不到也记中性，这里收紧以免"未知当方向"。LPR 5 年期等辅助成员的下调同样计入。
- 指标"读法明确"：主要成员证据为当期且方向已知即投票，不要求回看期完整（与原型回测一致）；确认度在有价格阶段时会因回看缺月判"未确认"，两处口径不同，票 10 对照时留意。
- 非明确情形（并列、已知维或最高分不足 3）本票只发布 `stage: None`，标题写"宏观判断：未达明确判断（…）"，由票 03 兜底替换。
- 标题在"前进／后退"后附步数（"前进 2 步"），无上一确认阶段写"无上一确认阶段"（决定 48）。
- ① 新板在五维之下暂保留"价格阶段"与原各行（原因、只差一项、上次确认、转折观察、核心沿用、判法），待票 06 收进价格验证行；板副标题与"判法"一行未改。
- 阶段史 assessment 未记宏观判断（票 08）；`relink` 同步参照的改动未单独写测试（完整运行级用例代价高）。
- 测试夹具用内置 v0001 目录加 v0016 宏观规则登记独立模型，未在测试中登记真实 `model-v0016`。
