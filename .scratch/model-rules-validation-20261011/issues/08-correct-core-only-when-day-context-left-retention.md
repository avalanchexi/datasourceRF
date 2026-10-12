# 08: 更正日的上下文明细已超出留存时，只更正核心与阶段

**What to build:** 票 07 在真实运行 `run-97250978e4b59b1a8d6e`（目标日 2026-10-09）中只更正了 34 天（08-14～10-08）；04-13～08-13 的 85 天各报 `backfill_day_failed:ValueError`（`projection_context_evidence_outside_visible_window`），仍是 `model-v0012` 的旧汇总、三核心“历史不足”。原因：更正日按该日公开截止整日重算时，宏观上下文（如 `CN_LOAN_STRUCTURE`）在该日可见的期次已超出留存，库里只剩为同比留存的更早期次（2025-08，公开于 2025-09-12），早于该日可见窗口，校验拒绝。后果：85 天未更正、上一确认阶段因此触发回溯；以后每次运行都重试并失败，约多耗 13 分钟。按 2026-10-12 用户决定：**更正日只重算三核心状态与正式阶段**；该日的宏观／库存上下文与确认度，在所需明细已超出留存（可见窗口校验不通过）时标“未重算（明细已超出留存）”，而不是整日失败；仍无法更正的日子（例如核心本身也不足）记“无法更正”及原因，**之后的运行不再重试**。依据：票 07、[spec](../spec.md) Further Notes 的票 07 决定、ADR-0034、ADR-0040。

**Blocked by:** 07（已完成）

**Status:** done

- [x] 完整运行接缝上先红后绿：窗口内旧口径日子的上下文明细已超出留存（复现：只留更早期次、可见窗口校验会拒绝）时，运行后这些日子各有更正版本，三核心不再“历史不足”、正式阶段按新核心历史重算；上下文与确认度标“未重算（明细已超出留存）”；运行照常完成
- [x] 上下文明细仍在留存内的更正日，行为与票 07 相同（整日重算，含上下文与确认度）
- [x] 无法更正的日子记“无法更正”及原因；再跑一次不再重试这些日子（幂等，耗时不再增加）；口径版本未变时也不重算
- [x] 确认度隔离与时点口径不变：未重算上下文的更正日不产生确认度，不借用其他日子的明细；外部调用 0 次新增
- [x] 页面与阶段历史对“只更正核心”的日子有可见标注；`summary_corrections` 分别计“整日更正、只更正核心、无法更正”天数
- [x] 在真实库**副本**上实测：`run-97250978…` 之后再跑一次同目标日的完整运行，85 天全部得到更正（或逐日给出无法更正原因），再跑一次耗时不再含重试
- [x] 受影响测试、两例冒烟、重型两例、ruff、mypy 通过；Codex 两轴审查无阻断

## 主要模块

`src/pring_cycle/day_summary.py`（更正分支与 `_backfill`）、`src/pring_cycle/p0.py`（评估文档：更正范围标记）、`src/pring_cycle/projections.py`（`summary_corrections` 计数）、`src/pring_cycle/dashboard.py`（标注）、上下文可见窗口校验（`projection_context_evidence_outside_visible_window` 抛出处）。

## Comments

### 2026-10-12 发现与用户决定

- 发现：票 06 收尾验收第一次真实运行（`run-97250978e4b59b1a8d6e`，34 分 16 秒，回执 152、失败 0）。`summary_corrections=34`；85 天失败，building_projection 共 22 分钟（每失败一天约 6～15 秒）。票 06 子代理已在库副本上复现报错与原因（见上）。回溯被触发：1 年、核心请求 3 次、日历 1 次，找到 `stage_iii`，阶段日 2026-04-10——很可能因早期 85 天未更正。
- 票 07 实施时的“明细可得性”核查只看了近期日子，没有覆盖窗口前部的上下文期次。
- 用户决定（2026-10-12）：选“只更正核心并重验”——即本票做法；修好后再做一次真实运行（目标日 2026-10-09）完成票 06 验收。

### 2026-10-12 主 agent 补充（根因与判据）

- 根因（票 06 记录第六节遗留 1）：`context_projection.py:447` 把无窗口下界的仓库交给 `_derived_market_context_rows`，`:2323` 直接取 `ordered[-1]`，窗口外期次进入 `credit.evidence`，被 `projections.py:647` 拒绝；正常目标日也可能触发。本票一并修复：派生行只读可见窗口内。
- “明细已超出留存”的判据：被更正的原评估所引用的上下文冻结输入中，任一已不在库 → 只更正三核心与正式阶段，上下文与确认度标“未重算（明细已超出留存）”；全部仍在 → 同票 07 整日重算。


### 2026-10-12 第二次接手（mr-08c）进展

- 10:55 核对现状：第一轮阻断②已修（`_CORE_COMPUTED`：核心理由不在 validated／carried_forward／transition_pending 即记“无法更正”，测试用核心冲突的就绪结果覆盖）；阻断①部分修复——判据已含展示声明、前期比较输入（`direction_input_…`）、派生原料（`input_…`、`trading_calendar_…`），但未含确认度输入（确认度成员与仓单的 `observation_version_ids`、价格一致性读的 `model_input_observation_version_ids`）。在新复制的真实库副本上核对：04-13～08-13 共 85 天的原评估都引用已不在库的 GDP 前期比较输入（另含更早日子的 M1、PMI、社融等），08-14～10-08 扩大键集合并排除派生观测自身编号后全部仍在库——判据与数据一致。判据只读原评估的分析数据集，不依赖 evidence_snapshot。
- 11:00 补齐阻断①：`_CITING_KEYS` 增加 `selected_claim_id`、`observation_version_ids`（确认度成员、仓单）、`model_input_observation_version_ids`（价格一致性等），并扣除文档中派生行自身的 `derived_observation_id`（补算不落派生观测，其编号不在库不算超出留存）。先红后绿：新增单日汇总接缝用例 `test_a_correction_day_whose_confirmation_read_a_claim_now_gone_corrects_its_cores_only`（只被确认度读到的 PMI 声明移出后，改前判为 whole_day——红；改后 core_only——绿），同时断言未删声明时两天判为“仍在库”（派生编号不误判）。`test_core_only_correction.py` 4 passed（127 秒）。下一步：重装 venv、受影响测试。
- 11:05 重装 venv；ruff check／format --check（改动文件）、mypy（132 文件）通过。新复制真实库（sqlite backup API，原件 mtime 未变）到 `tmp/mr-08c/rt/`，迁移至 0037，离线完整运行两次已在后台开跑（`fullrun-1.log`、`fullrun-2.log`）；之后跑受影响测试与 Codex 第二轮审查（提示词 `tmp/mr-08c/common.txt`）。
- 11:27 副本完整运行（最终代码，离线回放 run-97250978 的 TuShare 原始应答，外部连接全部拦截，未应答 0）：第一次 `run-52a99631…` completed，468.6 秒，更正 85 天全部只更正核心（04-13～08-13）、整日 0、无法更正 0、补算失败 0，未触发回溯；第二次 `run-e7f75819…` completed，429.2 秒，更正 0、失败 0，不再重试。运行后窗口 120 天无核心“历史不足”，stage_iii 67 天（04-27～08-03），核心理由 validated 338／transition_pending 22。副本已删除，真实库 mtime 未变。
- 11:28 受影响测试已开跑（`tmp/mr-08c/affected.log`，约 40 分钟）；Codex 第二轮两轴审查已并行发出（`tmp/mr-08c/review-spec-2.md`、`review-standards-2.md`）。之后：冒烟两例、重型两例。
- 11:38 Codex 第二轮：两轴均确认 A（漏收输入）、B（只更正核心分支的核心不可计算）已修，副本完整运行证据成立；新报两项阻断——①顶层 `model_input_observation_version_ids` 会把核心行自身的引用重新收入检查集合（核心旧声明被清理时误判 core_only）；②整日更正分支缺同样的核心可计算检查（会把 core_data_pending 计为整日更正）。非阻断：CONTEXT.md 判据表述偏窄；构建层窗口测试未移到接缝。正在修①②（均属 A／B 修复不完整），修完回报主 agent，不提交。
- 11:44 修第二轮两项阻断（先红后绿）：①`context_details_held` 把核心行自身引用与上下文引用分开收集，顶层 `model_input_observation_version_ids` 只计未被核心行引用的（价格一致性等），上下文行（如 OMO 交易日历）引用的核心声明仍计入；新用例 `test_a_core_s_own_claims_gone_are_no_context_detail_left_retention`（目标日商品核心行为 current 时移出其自身声明：改前判“不在库”红、改后绿）。②核心可计算检查 `_computed` 用于所有更正日（整日更正分支同样记“无法更正”）；扩展 `test_a_correction_day_that_cannot_be_corrected…` 加一个上下文齐全的日子（改前 53≠54 红）。CONTEXT.md 判据表述同步。真实库副本核对：新旧判据在 04-13、07-15、08-13、08-14、10-08 的引用集合完全相同，分类不变（85 只更正核心／34 齐全），前次副本完整运行结论不受影响。受影响测试先前一轮（旧代码，46% 无失败）已中止，改后重跑。
- 12:22 最终代码检查全部通过：受影响测试 777 passed（31 分 29 秒，`tmp/mr-08c/affected.log`）；冒烟两例 2 passed（24.7 秒）；重型两例 4 passed（4 分 47 秒）；ruff、mypy 通过。已回报主 agent，等用户是否批准第三轮定向复审（只确认第二轮①②修复），未提交。
- 13:31 第三轮定向复审经用户 2026-10-12 批准（只确认第二轮①②修复与 CONTEXT.md 判据同步，不再找新问题），已发出（`tmp/mr-08c/review-targeted-3.md`）。
- 13:37 第三轮定向复审（经用户 2026-10-12 批准）结论：①②③均成立，阻断：无（`tmp/mr-08c/review-targeted-3.md`）。下一步：补完整运行入口用例在当前代码上的先红后绿记录，最终代码上副本两次完整运行复测。
- 13:43 完整运行入口用例 `test_a_correction_day_whose_context_left_retention_corrects_its_cores_only` 在当前代码上补红绿：临时把只更正核心分支的条件改为恒假（回到票 07 整日重算）→ 红（scope whole_day≠core_only，`tmp/mr-08c/red-fullrun-seam.log`）；恢复原文件（cmp 一致）→ 绿（48 秒，`green-fullrun-seam.log`）。（第三轮复审提示词发出时尚未有此记录。）下一步：最终代码副本复测。
- 13:44 最终代码副本复测开跑：venv 重装，新复制真实库（backup API，原件 mtime 未变）迁移至 0037，后台两次完整运行（`tmp/mr-08c/fullrun-final-1.log`、`fullrun-final-2.log`）。
- 14:00 最终代码副本复测完成：第一次 `run-a01e830a…` completed，494.5 秒，更正 85 天全部只更正核心（04-13～08-13），整日 0、无法更正 0、补算失败 0，未触发回溯；第二次 `run-efc1cf1d…` completed，491.3 秒，更正 0、失败 0，不再重试。两次未应答 0、外部连接全部拦截。运行后窗口 120 天无核心“历史不足”，stage_iii 67 天（04-27～08-03），`uncorrectable_day` 0 行。副本已删除，真实库 mtime 未变。

### 2026-10-12 实施

**接手经过**：mr-08 实施根因修复与首版判据；mr-08b 改判据、做第一轮两轴审查与补算接缝副本实测；两者都因 API 连接中断（ECONNRESET）失效。mr-08c 第二次接手，补齐第一轮阻断，做第二、三轮审查、副本完整运行与收尾。

**改了什么**（迁移 0037）

- 根因：`context_projection._derived_market_context_rows` 新增 `visible_start`。贷款月度变化、OMO 净投放、DR007 利差、美债利差、PMI 两个利差等派生行，终止期早于该日可见窗口时不出行（原料仍可早于窗口，如前月）；该指标照常显示窗口内的普通行或缺口行。目标日与补算日走同一路径。
- 判据：`ProjectionSetRepository.context_details_held`，读被更正原评估的 macro／inventory 分析数据集。
  - 收集上下文行引用的来源声明：展示的（`claim_id`、`claim_ids`、`selected_claim_id`）、派生原料与交易日历（`input_…`、`trading_calendar_…`）、前期比较（`direction_input_…`）、确认度成员与仓单（`observation_version_ids`）。
  - 顶层 `model_input_observation_version_ids` 只计未被核心行引用的（价格一致性的广度、篮子仅在此处出现）。
  - 扣除派生行自身的 `derived_observation_id`；三核心行自身的引用不算上下文明细。
  - 任一不在 `source_claim` → 只更正核心；全部在库 → 同票 07 整日重算。
- 判据替代及理由：主 agent 给的字面判据是“原评估引用的上下文冻结输入任一不在库”。
  - 冻结快照成员含补算不落库的派生编号与核心价格，按字面几乎每天都“缺失”。
  - 因此改为按原评估分析数据集里实际引用的来源声明判断，不依赖 evidence_snapshot，与“所需明细已超出留存”同义。
  - 第一轮规格轴指出只看展示行 `claim_id` 不等价，已扩大到比较、派生原料与确认度输入；第二轮又收窄掉核心行自身引用。
- 只更正核心：`day_summary._summarize_day` 不调用上下文计算。宏观与库存文档用默认文档，加 `context_status=not_recomputed`、`not_recomputed_reason=details_past_retention`；无确认度、不借用其他日子的明细；`corrects.scope=core_only`（整日为 `whole_day`）。
- 无法更正：所有更正日在发布前经 `_computed` 检查。某核心理由不在 validated／carried_forward／transition_pending，或只更正核心也出错（KeyError／LookupError／TypeError／ValueError），即记入新表 `uncorrectable_day`。该表主键为日期＋核心历史口径，只追加，随留存按日期清理；日子保留原汇总，同一口径之后的运行不再尝试。整日重算的其他错误仍按失败日处理、下次重试（同票 07）。
- 运行计划 `summary_corrections` 增加 `whole_day`、`core_only`、`uncorrectable`（含逐日原因）；旧字段 `corrected_days`、`count` 保留。阶段历史页对只更正核心的行标“只更正核心与正式阶段，上下文与确认度未重算：明细已超出留存”。
- 文档：`CONTEXT.md` 单日汇总条按用户决定补充并注明出处。

**为何最终是 85 天全部只更正核心，而不是早先的 63／22**：mr-08b 的补算接缝实测（整日 22 天：07-15～08-13；只核心 63 天：04-13～07-14）用的是只看展示行 `claim_id` 的窄判据。按第一轮审查扩大到前期比较输入后，07-15～08-13 的原评估都引用了已不在库的 GDP 前期比较声明（4 条），这些日子的上下文无法按原样重算，应只更正核心。副本核对：04-13～08-13 共 85 天各有已不在库的引用；08-14～10-08 共 34 天（已由 run-97250978 整日更正）在最终判据下全部在库。

**测试**（先红后绿）

- `tests/integration/test_core_only_correction.py`（新增 5 例）：
  - 完整运行入口：一月声明移出后，以一月为展示或前期比较输入的日子只更正核心，其余整日；核心不再“历史不足”、正式阶段按新历史重算；上下文未读取、标未重算、无确认度、不借用三月明细；三类计数、页面标注；第三次运行更正 0、请求数不增。当前代码上把只更正核心分支临时改为恒假得红（scope whole_day≠core_only），恢复后绿。
  - 无法更正：核心冲突的就绪结果（只核心日与一个上下文齐全的整日日都包括在内）记“无法更正”及原因、保留原汇总、第三次不再尝试；改前整日日被计为更正（53≠54）为红。
  - 其他错误仍为失败日、下次重试。
  - 单日汇总接缝：只被确认度读到的 PMI 声明移出 → 只更正核心（改前 whole_day 为红）；未移出时判为在库（派生编号不误判）。
  - 核心行自身声明移出（目标日商品核心行为 current，其声明进入汇总列表）仍判在库（改前判不在库为红）。
- `test_context_projection.py`：贷款期次早于窗口时不出派生行（根因构建层回归）。
- 随行为调整：`test_core_history_correction.py`、`test_day_summary.py` 的 `summary_corrections`／`corrects` 断言加三类与 `scope`；`test_database_lifetime.py` 的 schema 头改为 0037。

**审查**

- 第一轮（mr-08b）：阻断三类——判据不等价、核心不可计算被计为成功、副本实测不是完整运行。
- 第二轮：两轴确认上述已修；新报两项阻断（汇总列表带回核心行引用；整日分支缺核心可计算检查），均已先红后绿修复。非阻断：CONTEXT.md 表述（已同步）；构建层窗口测试未移到接缝（保留为根因回归）。
- 第三轮定向复审经用户 2026-10-12 批准，只确认上两项与文档同步：均成立，阻断：无。

**测试与耗时**（最终代码，重装 dev-venv 后）：受影响测试 777 passed（31 分 29 秒）；冒烟两例 2 passed（24.7 秒）；重型两例 4 passed（4 分 47 秒）；ruff check／format --check（改动文件）、mypy 通过。

**副本完整运行**（最终代码，离线回放，外部调用 0）：见上方 14:00 记录。85 天全部只更正核心，第一次 494.5 秒，第二次 491.3 秒且不再重试；真实首跑 run-97250978 用了 34 分 16 秒，其中约 22 分钟耗在 85 天逐日失败上。

**对第二次真实运行（票 06）的预期**：85 天只更正核心，更正部分约 8 分钟，不再触发回溯（上一确认阶段由新口径历史给出）；之后的运行更正 0 天。
