Status: done
Category: enhancement
Type: task

# 05：体检第一层“已入库后被清理”按指标聚合，掩盖成员差别

## 现象

一个指标只要还有任一成员留存，就不再列“整期被清理”（`tools/quality/acquisition.py:1072`、`:1096`），例如工业财务 2026-03 选中的营收同比已清理而利润同比仍在。影响较小。

## 来源

验收记录遗留 4（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

体检线：只把第一层“已入库后被清理”的**清理明细**改为成员级（指标 × 期次 × 成员），另列“成员数／指标期次数”；最新应有期、发布延迟、超宽限统计等仍按指标期次口径，不做第一层大范围重排（`DelayRow` 不成员化）。清理证据匹配（`StorageHistory._stored_by`，`acquisition.py:968`）要按维度匹配。先改文档再改脚本。

## 主要模块

`tools/quality/acquisition.py`（`:968`、`:1072-1099`、`AbsentRow` 与附表）、`docs/development/data-quality-audit.md`。

## 验收

- [x] 文档写明清理明细按成员列出
- [x] `run-b7d59b63…` 上清理明细为 14 条成员、6 个指标期次（新增工业财务 5、产成品存货 1、工业增加值 2、M1/M2 3、社融存量 1；原周转展开为 2）；最新应有期、超宽限 80 期等其余统计不变
- [x] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [x] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 05.1–05.4 条。

- 属实：`acquisition.py:1072` 的 `stored` 只以期次为键，`:1099` 只在整个指标期次无声明时才判清理。
- 实测：成员级会新增 12 条（见“验收”），比票面所说“营收同比”一条多；发布早于窗口首日 04-13 的期次不计入。改动局限于清理明细，不牵涉第一层大范围重排。
- 决定：按预设 `ready-for-agent`（影响小，体检线 C 第三票）。

### 2026-10-12 实施进展

- 领取（fub-05，worktree 分支 `worktree-agent-a0ef7582e543600c3`，基于 bcf2e33）。基线 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/05/before.md` 已跑，与票 04 的 `after-b7d5.md` 除耗时外逐字相同。
- 文档已改：`docs/development/data-quality-audit.md`“现已无声明的期次”后新增“清理明细按成员列出”（成员定义、判据①②的成员版、成员不明、成员数／指标期次数、不变的部分），局限末条改写。下一步改脚本。
- 脚本已改（`tools/quality/acquisition.py`），对账 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/05/after.md`：清理明细 14 个成员、6 个指标期次，与分流取证逐条相符；ruff 通过。下一步 Codex 两轴审查。
- Codex 两轴审查第 1 轮已发起，输出 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/05/review-{standards,spec}-1.txt`。标准轴、规格轴第 1 轮均“阻断：无”。

### 2026-10-12 实施

**改了什么**

- 文档 `docs/development/data-quality-audit.md`（第一层“现已无声明的期次”）：新增“清理明细按成员列出”。成员为按键排序的维度 JSON（声明取 `dimensions_json`，回执标量取 `dimensions`，计划取 `members` 去掉“指标:”前缀）；成员被判为已入库后被清理的条件：该成员该期无截止前入库的同定义声明，且满足 ①（计划需求行列有该成员、不在 `missing_members`，且该行选中声明至少一条已不在库）或 ②（回执已接受标量含该成员该期）；认不出成员时记“成员不明”；另列“成员数／指标期次数”。期次三类划分、“现已无声明的期次”计数、最新应有期、超宽限表与“首次入库”仍按指标期次（`DelayRow` 不成员化）。局限末条改写。
- 脚本 `tools/quality/acquisition.py`：`StorageHistory._stored_by` 改为同时返回回执所含成员（按维度匹配）；新增 `StorageHistory.purged`、`_left`、`_receipt_proof`，以及 `PurgedRow`、`_dimensions_key`、`_plan_member`。`low_frequency` 对窗口内发布的每个期次（仍有声明的，或整期判为已清理的）列出被清理成员；`classify` 的期次级判定与依据文字不变。结论两条范围各追加“按成员计已入库后被清理 N 个成员、M 个指标期次（其中 K 期仍有其他成员的声明）”；明细表加“成员”栏，清理逐成员一行，另两类成员栏记“整期”。

**对账**（`run-b7d59b63bedca39d9d2e`，前 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/05/before.md`，后 `after.md`，报告差异 `change.diff`）。逐项差异：

1. 结论两条（目录全部、仅模型用到）：句末追加“；按成员计已入库后被清理 14 个成员、6 个指标期次（其中 5 期仍有其他成员的声明）”。原有数字（日频格数、低频 18 项、超宽限 80 期、其中已入库后被清理 1 个、现已无声明的期次 3 个＝清理 1／不在需求内 2／未取到 0）不变。
2. 明细表说明句：改为“现已无声明的期次与已被清理的成员”，并写明 14 个成员、6 个指标期次，另两类逐期列出。
3. 明细表：加“成员”栏；核心 CPI 2026-04、2026-05 两行内容不变，只多“整期”；周转 2026-03 原一行展开为 `days`、`official_yoy_change` 两行；新增 12 行：工业财务 2026-03 的 revenue/ytd_level、revenue/official_yoy、cost/ytd_level、cost/official_yoy、profit/ytd_level（5），产成品存货 nominal_end_level（1），工业增加值 mom_seasonally_adjusted、ytd_real_yoy（2），M1/M2 的 m1/balance、m2/balance、m2/yoy（3），社融 stock_end（1）。合计 14 条、6 个指标期次，与分流取证 05.2–05.3 逐条相符；发布早于窗口首日的工业财务 2026-02、PMI 2026-03 未混入。按计划证据（①）能认出的是营收同比、社融存量、周转同比变化 3 条，其余只有回执证据（②），同取证“仅核计划只能新增 2 条”。
4. 末行耗时 34.2 → 17.7 秒。

其余内容逐字相同（含最新应有期表、超宽限 80 期表及周转 2026-03 那行“已入库后被清理，见下表”）。

**审查**：Codex 标准轴、规格轴各一轮，均“阻断：无”（`/home/tywin/.claude/jobs/cd7879cd/tmp/fub/05/review-standards-1.txt`、`review-spec-1.txt`）。规格轴用只读 SQLite 抽核：14 个成员现均无声明，5 个期次仍有同定义其他成员声明，计划“选中 1 条缺 1 条”“选中 3 条缺 1 条”属实。规格轴唯一建议是把差异逐项解释写进票面，即上面的“对账”。ruff check／format --check 通过。

**遗留**：无新增。回执标量不带目录版本，成员是否同定义仍按文档局限处理（异定义的回执成员可能被列为已清理，本运行未出现）。
