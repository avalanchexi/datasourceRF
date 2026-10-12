Status: done
Category: bug
Type: task

# 01：08-14～10-08 的 34 个整日更正日“上一确认阶段”为空

## 现象

第一次真实运行（`run-97250978…`）时这 34 天已整日更正，当时前 85 天尚未更正、没有阶段，所以它们的 `last_confirmed_stage` 为空；第二次运行补正了前 85 天（stage_iii 67 天），但这 34 天已是 `core-history-v0002` 口径，`_backfill` 只更正口径不同的日子（`src/pring_cycle/day_summary.py:357-362`，读码推断），之后不会再更正。阶段历史页这 34 天显示“上一确认 尚无”；目标日不受影响。

## 来源

[验收记录](../model-rules-validation-20261011/acceptance-20261012.md) 遗留 8（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

方案 B：对“上一确认阶段”所依赖的正式阶段历史已被后续更正改变的历史日，追加一个**只更正 `last_confirmed_stage`** 的版本：保留原核心、宏观、库存、确认度和证据引用，不重算核心与上下文，外部调用 0，旧评估、投影、报告保留，页面不现场计算。不借用 `core_history_basis` 升级（会选中 119 天并可能走整日重算，见取证 5.1–5.2）。窗口开头 10 天（04-13～04-24）为空属正确空值，不在本票范围。

## 主要模块

`day_summary.py`（补算后检查历史依赖）、`projections.py`（查询依赖、追加版本；新投影的总览与阶段史事件同步）、`p0.py`（更正原因／范围）、`worker.py`（计数）、`dashboard.py`（显示更正原因）；规格与领域文档相应补写。

## 验收

- [x] 先有一条稳定变红的测试：某历史日的上一确认阶段依赖的更早日后来被更正出正式阶段，`_backfill` 后该日仍为空
- [x] 修复后对这类日子只追加一个更正版本（带 `corrects` 与专用原因），核心、上下文、证据引用逐字不变；外部调用 0
- [x] 应有值与已存值相同的日子不追加版本；同一口径下重复运行不再追加（幂等）
- [x] 新投影的阶段史事件与总览同步更新；阶段历史页显示更正后的上一确认阶段
- [x] 旧评估、投影、报告保留
- [x] 受影响测试、两例冒烟、重型两例（涉及 Worker 编排）、ruff、mypy 通过；Codex 两轴审查无阻断
- [ ] 收尾验收（票 09）在真实库上核对：08-14～10-08 的 34 天变为 stage_iii，其余 86 天不变

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-01-08.md](../triage-codex-01-08.md)（快照为 10-12 16:18 的运行库备份）。

- 现象仍在（实测）：窗口 120 天中 `last_confirmed_stage` 为空 44 天，其中 34 天（08-14～10-08，均为第一次运行的 `core-history-v0002` 评估）应为 stage_iii；04-13～04-24 的 10 天为空是正确的（此前无正式阶段）。
- 根因：`day_summary.py:355-369` 只在 `core_history_basis` 不同且不在“无法更正”名单时更正已有汇总；上一确认阶段取自此前各日最新评估的 `current_stage`（`day_summary.py:483`、`:547`，`projections.py:346`、`:356`），已发布字段不会随更早日的后续更正联动。主 agent 已复核 `day_summary.py:345-372`。
- 影响面：阶段历史页逐日显示“上一确认 尚无”（`dashboard.py:670`、`:690`、`:1850`、`:1871`）；目标日评估、总览、报告不受影响；回溯未被误触发（第二次运行 `core_lookback` 0 行）。
- 决定：按预设 `ready-for-agent`，取方案 B（另设标记，不借用口径版本号）。理由：借用 basis 升级会选中 119 天、可能整日重算并使旧 basis 的“无法更正”记录失效，改动更大；方案 B 不改选值规则，只是“已汇总不再重算”的一个预设已批准的例外。

### 2026-10-12 进展（实施子代理 fub-01）

- 16:38 已领取；红测试 `tests/integration/test_day_summary.py::test_a_day_whose_last_confirmed_stage_was_formed_later_is_relinked_on_it_alone` 稳定变红（3/3，`assert None == 'stage_iii'`）。触发口径取“无正式阶段的历史日：已存上一确认阶段 ≠ 当前阶段历史应有值”，不区分历史变化来自更正还是失败日后补（真实库 34 天即前 85 天第一次失败/未更正、第二次补出所致），已告知主 agent。
- 17:05 实现完成（p0.relink、day_summary._relink、projections 平局规则、worker 计数 last_confirmed_relinks、dashboard 更正说明）；新增 3 例测试均通过（day_summary 2 例、core_history_correction 1 例 38s）。下一步：受影响测试。
- 17:35 受影响测试第一轮 173 passed/1 failed（test_core_only_correction 无法更正日被补正，与票 08“保持原样”冲突）→ 限定只补正最新汇总在本次运行口径上的日子；复跑三文件 29 passed（333s）。日志 /home/tywin/.claude/jobs/cd7879cd/tmp/fub/t01-affected{,-2}.log。下一步：冒烟、重型两例。
- 17:50 冒烟两例 2 passed（39.6s）；重型两例（registered_catalog＋core_carry_forward）4 passed（334s），日志 /home/tywin/.claude/jobs/cd7879cd/tmp/fub/t01-heavy.log；ruff/mypy 通过。Codex 两轴审查第 1 轮进行中（t01-review-{std,spec}-1.md）。
- 18:30 两轴第 1 轮：规格轴无阻断；标准轴 2 阻断（carries 嵌套链页面漏说明、续跑计数少记）＋3 建议。已修：carries 保持一层；计数改在投影链接后由 _record_relinks 写入，续跑已链接分支亦写入；采纳 FailedDay 迭代器、ADR 措辞；补反向/链式测试与续跑计数测试，62 passed（371s）。进行第 2 轮定向复审。

### 2026-10-12 实施

**改了什么**

- `p0.py`：新增原因 `stage_history_changed`、范围 `last_confirmed_stage`；`SummaryCorrection.carries` 记下被更正汇总自身的更正说明（链保持一层）；`P0ProjectionService.relink()` 复制原评估与原投影（核心、宏观、库存、确认度、证据快照逐字不变，不取数、不重算），只改 `last_confirmed_stage`，总览同步、阶段史事件按当日重建；阶段历史已给出阶段时新投影不再携带原投影的回溯结果；以 `as_current=False` 追加，旧评估与投影不动。
- `day_summary.py`：`_backfill` 补算/更正循环之后执行 `_relink`：按日序读一次阶段历史，对窗口内目标日前、当天无正式阶段、**最新汇总在本次运行核心历史口径上**、已存值≠应有值的日子追加只更正版本；失败按 `FailedDay` 报告。不借用 `core_history_basis` 升级。模块文档改写“失败日后补不级联”的说明。
- `projections.py`：最新版本排序加平局规则 `_NEWER_FIRST`：同一截止时间下被更正者让位（`stage_history` 与 `last_confirmed_stage` 共用）。
- `worker.py`：`_record_relinks` 在投影链接后（及 `published_projection` 续跑分支）把本批次补正日写入计划 `last_confirmed_relinks`（从已存评估读出）。
- `dashboard.py`：阶段历史页对补正版本显示“更正版本（更早日的阶段历史已变，只更正上一确认阶段，核心、上下文与确认度沿用原汇总；原汇总：…）”。
- 文档：`CONTEXT.md`“单日汇总”、ADR-0040 后果、`model-rules-validation-20261011/spec.md` Further Notes。

**口径取舍（已告知主 agent，规格轴审查认定未越出批准范围）**：触发不区分“更正”还是“失败日后补”（真实库 34 天即此机制）；只补正最新汇总在本次运行口径上的日子——无法更正日（票 08）保持原样，口径不同的日子随整日更正一并得到，运行口径为空时不补正。

**测试**：新增 `test_day_summary.py` 2 例（红测试；同截止平局＋反向＋链式）、`test_core_history_correction.py` 2 例（Worker 级补正与计数、链接后中断续跑计数）、`test_dashboard_contract.py` 1 例。受影响测试首轮 173 passed／1 failed（无法更正日被补正 → 加口径限定）；修后复跑 29 passed（333s）、62 passed（371s）、152 passed（394s）；冒烟两例 2 passed（39.6s，复跑含于 152 例中）；重型两例 4 passed（334s，修后复跑 297s）。ruff check / format --check、mypy 通过。日志在 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/t01-*.log`。

**审查**：规格轴第 1 轮无阻断（快照推演：恰好补正 08-14～10-08 的 34 天为 stage_iii，前 85 天 core_only 不被选中，其余 86 天不变）；标准轴第 1 轮 2 阻断（carries 嵌套链页面漏说明；续跑后计数少记）均已修，第 2 轮定向复审无阻断。采纳的建议：`_relink` 返回 `Iterator[FailedDay]`；ADR 措辞改为“新投影不再携带原投影的回溯结果，原投影保持不变”；补 core_only 文案页面用例、续跑用例断言已链接。未采纳：每个补正日重读阶段历史的成本（窗口 120 天、数百行评估，可忽略，且重读保证新投影阶段史含刚追加的补正，复审接受）；“检查点前中断、续跑新增补正”的长场景用例（检查点前中断时计数尚未写入，续跑后从已存评估读出，逻辑已由读码确认，复审为建议）。审查输出 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/t01-review-*.txt`。

**遗留**

- 最后一项验收（真实库 34 天变为 stage_iii、其余 86 天不变）留待收尾票 09；快照推演已对上。
- 体检脚本 `tools/quality/derived.py` `_core_only()` 只看 `corrects.scope`：将来若有“只更正核心”的日子被补正（范围变为 `last_confirmed_stage`，原范围在 `carries`），体检会把它报为标记不全。本次真实库的 34 天均为整日更正，不受影响；建议体检线后续同时读 `corrects.carries.scope`。
