# 08: ⑥ 宏观判断色带与阶段史

**What to build:** 阶段史自 v0016 生效日起逐日记宏观判断主结论（阶段＋把握程度），生效前空白不倒推，滞回过程不入阶段史；⑥ 色带新增"宏观判断"一行（阶段着色、深浅或标记区分把握程度），保留票 12 左右布局（左栏说明、色带、日数，右栏区间列表），区间列表可按宏观判断查看。规格 [../spec.md](../spec.md)（2026-10-19 修订），决定 [../decisions.md](../decisions.md)，ADR-0043（含修订）。

**Blocked by:** 03、05

**Status:** done

- [x] 单日汇总测试：阶段史逐日记主结论与把握程度；生效日前无记录；滞回期间记的是未替换的主结论
- [x] `dashboard_page` 断言 ⑥ 新行存在、把握程度可区分、布局不变
- [x] 两项冒烟通过

## Comments

### 2026-10-19 实施（ticket-ms08，分支 ms-08）

- **记录**：当日 assessment（`p0_assessment.document_json`）新增 `macro_conclusion{stage, confidence}`，取滞回后的主结论；无宏观判断的日子不写此键。`stage_history.display.days` 每行加 `macro`（阶段／`not_effective` 生效前／`no_stage` 无可取阶段／`unpublished`）与 `macro_confidence`，另有 `macro_counts`（键如 `stage_v:explicit`）；`counts` 与 `schema_version` 不变。展示只读各日自己的 assessment，不从别日、价格阶段或当前模型补推。
- **生效边界**：沿用 05 的口径——首个用含宏观规则的模型汇总的日子即生效首日（含补算日）。补齐：用 v0016 **更正**生效前的日子（其原汇总无 `macro_conclusion` 且模型不同）时不判宏观，不倒推。
- **校验**：`validate_analytical_projection` 新增 `projection_stage_history_macro_mismatch`——当日事件的 `macro_conclusion` 必须等于总览主结论的阶段与把握程度，无宏观判断时不得有记录。relink 更正上一确认阶段后按重述的主结论重写当日记录（有测试：无可取阶段 → 第三阶段·弱）。
- **⑥ 页面**：色带首行"宏观判断"（只在某日有主结论或无可取阶段时显示）；六个阶段固定配色、各行一致，倾向／弱为同色渐浅；生效前与无可取阶段为空格（悬停文字区分）；左栏加"宏观判断日数"、说明改写，等价表格首列加宏观判断。右栏区间列表加"正式阶段｜宏观判断"切换（`dashboard.js` 切换 `hidden`，无脚本时显示正式阶段），宏观区间按阶段＋把握程度合并。旧投影（无该字段或全部生效前）保持四行并提示"该投影生成时尚无宏观判断"。票 12 左右布局与抽屉位置不变。
- **测试**：新增 `tests/integration/test_macro_stage_history.py`（7 例：逐日主结论与生效前空白、滞回期间记未替换主结论、生效前日被更正仍不判、记录与主结论不符拒发 4 例、无可取阶段与 relink）与 `tests/web/test_macro_stage_history_board.py`（6 例）。受影响集 `python tools/check.py quick`（24 个文件：宏观 integration／web／报告、display_projection、day_summary、backfill、core_carry_forward、confirmation_publish、core_only_correction、core_history_correction、dashboard_contract、conclusion_board 等）首轮 262 过 3 败（922 秒，flock 下）：三例 v0001 更正测试的页面文字计数翻倍，原因是旧模型投影也显示了全空的宏观行与第二份区间抽屉；改为"有记录才显示"后三例复跑 3 过（301 秒），web＋新测＋两例冒烟复跑 81 过（96 秒）。源码 `ruff check`、`ruff format --check`、`mypy`（改动的 6 个源文件）通过。macro-stage 头 c7b110e 即本分支基点，合并为空操作。
- **偏离与留意**：①"宏观判断"行在 v0015 投影上不显示（全为生效前），不是票面字面的"新增一行"始终可见；② 页面仍沿用"正式阶段"字样（未改称"价格阶段"），留给 10 统一；③ 补算日若用 v0016 首次汇总（无既往汇总）仍会判宏观，这是 05 的生效首日口径，10 激活时如需按激活日划界须另定；④ 切换只靠前端脚本，未做浏览器验证，留给 10 的 Codex 浏览器验收；⑤ v0016 宏观投影的 ⑥ 区间抽屉有两套（正式阶段与宏观判断各一套），同一日的明细文字在页面里出现两次。
