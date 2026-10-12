Status: done
Category: bug
Type: task

# 03：体检未覆盖“回溯得出”与“只更正核心”日

## 现象

(a) 第三层（一）`tools/quality/output_consistency.py:159`、`:168` 要求评估的 `last_confirmed_stage` 与总览相同，未按票 02 的回溯规则核对（本次第二次运行未触发回溯，未复现）；(b) 派生节把只更正核心日的“无派生值”算作缺失，报出“待开票 8 项”（`tools/quality/derived.py`）。体检口径文档与脚本需加入回溯与只更正核心的规则。

## 来源

验收记录遗留 2、9（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

体检线：先改体检文档 `docs/development/data-quality-audit.md`，再改脚本。
1. **回溯**：第三层（一）把“评估值”与“展示值”分开核对。评估的上一确认阶段按“当前阶段，否则窗口内阶段史最近正式评估”核对；总览优先取该值，只有它为空且 `last_confirmed_lookback.status=found` 时才取回溯阶段。同时核对总览与阶段史两份回溯文档一致、阶段日在搜索范围内且早于窗口；回溯失败或未找到时不得凭空给阶段。规则依据 spec.md `:56-57`、ADR-0040 `:16`、`:30`。
2. **只更正核心日**：派生节识别 `corrects.scope=core_only`（同一投影的 macro、inventory 均为 `context_status=not_recomputed`），这类日计为“未重算（按设计）”，不算缺失；须交叉验证两项标记，不能只凭空文档豁免。

## 主要模块

`tools/quality/output_consistency.py`（`:159`、`:168`、`:180`）、`tools/quality/derived.py`（`:1216-1239`、`:1028`、`:1162`）、`docs/development/data-quality-audit.md`（`:400` 等）。

## 验收

- [x] 文档先写明回溯与只更正核心日的核对规则
- [x] `run-97250978e4b59b1a8d6e`（触发了回溯）上第三层（一）的两条误报消失，回溯一致性检查通过
- [x] `run-b7d59b63…` 上 85 个只更正核心日计为“未重算（按设计）”，派生节“待开票”由 8 项降为 1 项（贷款，归票 04）
- [x] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [x] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 03.1–03.5 条。

- (a) 实测：第一次运行总览 `last_confirmed_stage=stage_iii`、评估为 NULL、阶段史正式事件 0；回溯文档 `status=found`、阶段日 2026-04-10。体检 `output_consistency.py:159`、`:168` 期望评估与总览相同，故误报 2 条。
- (b) 实测：“待开票 8 项”是 8 个公式，共 1430 个缺失格，其中只更正核心的 85 天贡献 1241 格，其余 189 格是贷款（票 04）。识别字段：`corrects.scope=core_only`、`reason=core_history_basis_changed`，macro、inventory 均为 `not_recomputed`（`details_past_retention`）。
- 决定：按预设 `ready-for-agent`（体检线 C 首票）。

### 2026-10-12 实施进展（fub-03）

- 16:38 领取；基线实跑完成：`/home/tywin/.claude/jobs/cd7879cd/tmp/fub/03/before-b7d5.md`（66 秒）、`before-9725.md`（27 秒）。
- 16:55 文档已改：`docs/development/data-quality-audit.md` 第三层（一）“上一确认阶段”拆为评估值、展示值、回溯文档三条；派生节新增“只更正核心的日子”（三条同时满足才认定）。
- 17:20 脚本已改（`tools/quality/output_consistency.py`、`tools/quality/derived.py`），ruff 通过；改后实跑 `after-b7d5.md`、`after-9725.md`（同目录），差异符合预期；接着做 Codex 两轴审查。
- 17:30 Codex 两轴审查第 1 轮已启动，输出 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/03/review-{standards,spec}-1.txt`。
- 18:00 第 1 轮审查：标准轴阻断 2（回溯 stage 非字符串时 TypeError；派生节对非对象文档 .get 中断），规格轴阻断 1（评估值缺窗口下界）；均已修，并按建议改为日期解析校验、not_found/failed 以 null 判空；文档同步；复跑 `after2-*.md` 仅检查名与耗时变化。下一步定向复审。
- 18:25 定向复审：阻断无；按其建议把日期校验收紧为 `date.fromisoformat(v).isoformat() == v`，复跑 9725 仅耗时变化。

### 2026-10-12 实施

**改了什么**

- 文档 `docs/development/data-quality-audit.md`（先于脚本）：
  - 第三层（一）“上一确认阶段”拆为评估值、展示值、回溯文档三条。评估值为当前阶段，否则取窗口首日至目标日之间阶段史中最近的正式评估；展示值优先取评估值，评估值为空且回溯 `status=found` 时取回溯阶段。回溯文档须总览与阶段史相同；found 时阶段属于 `stage_mapping`、日期有效、阶段日在搜索范围内且早于窗口首日、无 failure；not_found／failed 时 stage、stage_date 为 null，failed 须有 failure。回溯是否找对、年数与请求次数不核对。附实测。
  - 派生节新增“只更正核心的日子”：须 `corrects.scope=core_only`、macro 与 inventory 均为 `context_status=not_recomputed`、无派生节点，三条同时满足才计“未重算（按设计）”。只满足一部分的（含文档不是对象的），照常判断，并列为“只更正核心的标记不一致”。附局限与实测。
- `tools/quality/output_consistency.py`：
  - “p0 last_confirmed_stage 与总览相同”改为“评估的上一确认阶段”，直接核对 P0；
  - 新增 `_lookback_checks`（2 项常驻，有回溯文档时再加 2 项）和结论行 `_lookback_note`。
- `tools/quality/derived.py`：
  - 新增 `_core_only` 与 `NOT_RECOMPUTED`；
  - 逐日核对认定只更正核心的日子后，逐公式、逐成员计为未重算，不再判断；
  - 逐日表增加“只更正核心的日子”一行，标记不一致的日子进入分流。

**对账**（输出在 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/03/`；before 为改动前，after2 为最终版，after3 为最后一次 9725 复跑）

- `run-b7d59b63bedca39d9d2e`，`before-b7d5.md` 与 `after2-b7d5.md` 比对，只有以下差异：
  1. 派生节结论：“待开票”8 → 1。
  2. 问题与分流：8 条 → 1 条，只剩贷款 `loan-ytd-monthly-change-v0002` 的 189 处（2026-08-14～09-11，归票 04）。
  3. 逐项结论：7 个公式去掉“（有问题）”。
  4. 窗口内逐日表：
     - 7 个公式各有 85 格计为“未重算（按设计）”，贷款 9 个成员共 765 格；
     - 合计 1360 格，其中原“缺失”1241 格、原“原料不齐，无派生值”119 格（63+13+13+29+1）；
     - 存在 35 格、重算一致 35 格不变。
  5. 逐日表新增一行：“只更正核心的日子 85 天：2026-04-13～2026-08-13”，`corrects.reason=core_history_basis_changed`，`not_recomputed_reason=details_past_retention`。
  6. 第三层（一）检查由 59 项增至 60 项，全部一致：
     - 新增结论行“未触发回溯”；
     - 删去“p0 last_confirmed_stage 与总览相同”，原检查改名为“评估的上一确认阶段（窗口内）”，并新增两项：回溯文档两份相同（均为 null）、展示值（stage_iii）。
  7. 报告末尾的耗时。
- 其余各节逐字相同，包括第三层（二）中 08-14～10-08 共 34 日的差异（属票 01）。
- `run-97250978e4b59b1a8d6e`，`before-9725.md` 与 `after2-9725.md`、`after3-9725.md` 比对：
  - 第三层（一）由“59 项、不一致 2”变为“62 项全部一致”，两条误报（P0 与总览相同、上一确认阶段）消失；
  - 新增 4 项检查（回溯文档两份相同、展示值、来源与状态、found 的阶段与日期）和回溯结论行（found，stage_iii，阶段日 2026-04-10，搜索 2025-04-14～2026-04-10，1 年，核心 3 次、日历 1 次）；
  - 派生节不变：这次运行的 85 天未得到更正，没有只更正核心的日子；
  - 其余仅耗时不同。
- 分支用假数据探针验证过（`probe3.py`）：回溯只有一侧、阶段在窗口内或超出搜索范围、阶段不在映射中、stage 为非字符串、无效日期、not_found 却给阶段（含 0）、failed 无原因、非法 status／source；只更正核心缺一项标记、仍有派生值、文档为 null 或数组。以上各种情况都能报出，报告不会中断。

**审查**：Codex 第 1 轮，标准轴阻断 2 项（非字符串阶段导致 TypeError；非对象文档导致 AttributeError），规格轴阻断 1 项（评估值缺窗口下界），均已修。定向复审阻断无，其日期格式建议也已落实。输出见同目录 `review-standards-1.txt`、`review-spec-1.txt`、`review-fix-2.txt`。ruff check、ruff format --check 均通过；只用标准库，未导入生产代码。

**遗留**：无本票遗留。贷款 189 格归票 04。
