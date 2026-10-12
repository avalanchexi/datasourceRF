Status: ready-for-agent
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

- [ ] 文档先写明回溯与只更正核心日的核对规则
- [ ] `run-97250978e4b59b1a8d6e`（触发了回溯）上第三层（一）的两条误报消失，回溯一致性检查通过
- [ ] `run-b7d59b63…` 上 85 个只更正核心日计为“未重算（按设计）”，派生节“待开票”由 8 项降为 1 项（贷款，归票 04）
- [ ] 对 `run-b7d59b63bedca39d9d2e` 改动前后各实跑一次体检：除改动节与耗时外逐字相同，差异逐项解释，记入票面
- [ ] 改动文件通过 `ruff check`、`ruff format --check`；只用标准库、不导入生产代码；Codex 两轴审查无阻断

## Comments

### 2026-10-12 分流

Codex 只读取证全文：[triage-codex-03-04-05-07.md](../triage-codex-03-04-05-07.md) 第 03.1–03.5 条。

- (a) 实测：第一次运行总览 `last_confirmed_stage=stage_iii`、评估为 NULL、阶段史正式事件 0；回溯文档 `status=found`、阶段日 2026-04-10。体检 `output_consistency.py:159`、`:168` 期望评估与总览相同，故误报 2 条。
- (b) 实测：“待开票 8 项”是 8 个公式，共 1430 个缺失格，其中只更正核心的 85 天贡献 1241 格，其余 189 格是贷款（票 04）。识别字段：`corrects.scope=core_only`、`reason=core_history_basis_changed`，macro、inventory 均为 `not_recomputed`（`details_past_retention`）。
- 决定：按预设 `ready-for-agent`（体检线 C 首票）。
