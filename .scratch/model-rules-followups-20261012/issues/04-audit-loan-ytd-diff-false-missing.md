Status: ready-for-agent
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

- [ ] 文档写明贷款年内差分只看最新锚定期
- [ ] `run-b7d59b63…` 上 08-14～09-11 的 189 格（21 天 × 9 成员）由“缺失”变为“原料不齐，无派生值”；贷款原有存在／重算一致的格不变；与票 03 合并后派生节“待开票”为 0
- [ ] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [ ] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 04.1–04.3 条。

- 实测：189 格 = 2026-08-14～09-11 共 21 天 × 9 成员；每格最新可见期 2026-07、缺 2026-06，体检退回到 2025-08。
- 订正：验收记录 `acceptance-20261012.md:252` 说“生产没有窗口截取”已过时——生产已有结果期次的窗口下界检查；所以按“只取最新锚定期”修，不按窗口截取。主 agent 已复核 `derived.py:830-840` 与文档 `:191`。
- 决定：按预设 `ready-for-agent`（体检线 C 第二票）。
