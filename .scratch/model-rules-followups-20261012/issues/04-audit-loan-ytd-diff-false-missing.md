Status: done
Category: bug
Type: task

# 04：体检贷款年内差分 189 项“缺失”为误报

## 现象

`tools/quality/derived.py` 的 `_newest_complete` 在 2026-07 缺 2026-06 原料时退回原料齐全的 2025-08；生产只看最新一期、前一期不连续就不出值（08-14～09-11，21 天 × 9 成员）。体检应只取最新锚定期，或按当日可见窗口截取（与票 08 根因同源）。

## 来源

验收记录遗留 3（模型规则补全批次，2026-10-12 收尾汇总）。

## 做法（分流决定）

体检线：贷款年内差分配置（`tools/quality/derived.py:837`）启用 `newest_anchor_only=True`，只取最新锚定期、不往旧完整期回退，与生产一致（`src/pring_cycle/context_projection.py:2353` 只取 `ordered[-1]`，`:2362` 前一期不连续即跳过）。**先修订体检文档** `docs/development/data-quality-audit.md:191`：现行文字只给实际库存近似开了“不往前回退”的例外，贷款要同样写明（依据 `.scratch/pring-data-acquisition-repair/research-13.md:178` 与生产行为）。不改为“按当日可见窗口截取”：生产已有结果期次的窗口下界检查（`context_projection.py:1993`、`:2355`），而截取原料会误删合法的窗口前差分基期。

## 主要模块

`tools/quality/derived.py`、`docs/development/data-quality-audit.md`。

## 验收

- [x] 文档写明贷款年内差分只看最新锚定期
- [x] `run-b7d59b63…` 上 08-14～09-11 的 189 格（21 天 × 9 成员）由“缺失”变为“原料不齐，无派生值”；贷款原有存在／重算一致的格不变；与票 03 合并后派生节“待开票”为 0
- [x] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [x] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 04.1–04.3 条。

- 实测：189 格 = 2026-08-14～09-11 共 21 天 × 9 成员；每格最新可见期 2026-07、缺 2026-06，体检退回到 2025-08。
- 订正：验收记录 `acceptance-20261012.md:252` 说“生产没有窗口截取”已过时——生产已有结果期次的窗口下界检查；所以按“只取最新锚定期”修，不按窗口截取。主 agent 已复核 `derived.py:830-840` 与文档 `:191`。
- 决定：按预设 `ready-for-agent`（体检线 C 第二票）。

### 2026-10-12 实施进展

- 17:05 领取；基线 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/04/before-b7d5.md` 已跑（55.5 秒），与票 03 改后报告 `fub/03/after2-b7d5.md` 除耗时外逐字相同。
- 17:10 文档已改：`docs/development/data-quality-audit.md:191` 写明贷款年内差分只看最新一期、不回退、上一期可早于窗口。
- 17:14 脚本已改（`tools/quality/derived.py` 贷款配置加 `newest_anchor_only=True`）；改后实跑 `fub/04/after-b7d5.md`，差异 `fub/04/change.diff`：仅派生节 4 处与耗时。
- 17:25 Codex 两轴审查第 1 轮：标准轴、规格轴均“阻断：无”（`fub/04/review-standards-1.txt`、`review-spec-1.txt`）。

### 2026-10-12 实施

**改了什么**

- `docs/development/data-quality-audit.md:191`（派生数据“存在性”表）：原先只给实际库存近似写了“不往前回退”，现改为两个公式都只试锚定指标当时可见的最新一期；贷款年内差分每个成员只看最新一期，与上一期须是同年连续月份（1 月直接取累计值），上一期缺失就不出值；依据 `research-13.md:178`“同年连续YTD”与生产行为（`context_projection.py:2353` 只取最新、`:2362` 前一期不连续即跳过，取自分流取证）。另写明差分所需的上一期可以早于窗口、原料不按当日可见窗口截取（分流决定）。`:209` 段末补本票实测。
- `tools/quality/derived.py:842`：贷款配置 `loan-ytd-monthly-change-v0002` 启用既有开关 `newest_anchor_only=True`。目标日派生观测、窗口内各日投影、“已修复、历史保留”的严格读取重判都经同一 `_judge`／`_newest_complete`，一并生效；重算公式本身未改。

**对账**（`run-b7d59b63bedca39d9d2e`，输出在 `/home/tywin/.claude/jobs/cd7879cd/tmp/fub/04/`）

- 基线 `before-b7d5.md` 与票 03 改后报告 `fub/03/after2-b7d5.md` 除耗时外逐字相同。
- `before-b7d5.md` → `after-b7d5.md` 共 5 处差异（`change.diff`），其余逐字相同：
  1. 派生节结论：待开票 1 项 → 0 项。
  2. 派生节分流：删去“loan-ytd-monthly-change-v0002 逐日核对有 189 处问题……待开票”一条。
  3. 逐项结论表第 3 行：“重算一致（9/9）（有问题）” → “重算一致（9/9）”，存在 9 不变。
  4. 逐日表贷款行：“缺失 189” → “原料不齐，无派生值 189”，问题样例列变为“—”；天×成员 1080、未重算（按设计）765、存在 126、重算一致 126 均不变。
  5. 耗时 55.5 → 28.3 秒（不计）。
- 189 格即 08-14～09-11 共 21 天 × 9 成员（分流取证 04.1：每格最新可见期 2026-07、缺 2026-06，旧逻辑退回 2025-08）；改后计数守恒，全数转入“原料不齐，无派生值”。

**审查**：Codex 标准轴、规格轴各一轮，均无阻断。规格轴建议把差异逐项写进票面，已按上条补齐。

**遗留**：无。说明：生产代码只在复核分流取证时阅读了 `context_projection.py:2345-2370`，脚本改动只是启用既有开关，没有照搬生产逻辑。
