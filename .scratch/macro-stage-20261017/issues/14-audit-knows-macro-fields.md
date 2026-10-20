# 14: 数据质量体检认识 v0016 的宏观结论字段

**What to build:** `tools/quality/audit.py` 的输出一致性检查，对 v0016 投影报出唯一一例不一致，原因是预期结论字典里没有 v0016 新增的 `macro_stage`、`macro_confidence`（投影实际为 `stage_iii`／`tendency`，与报告一致）。体检应对 v0016 投影核对这两个字段，并对 v0015 及更早的投影照旧通过。依据：`../investigations/audit-run-3ebbe323.md` 第 5 节。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 对 run-3ebbe323（v0016）体检，输出一致性无误报（原 58/59 → 59/59）；`macro_stage`、`macro_confidence` 与投影不一致时报不一致
- [x] 对 v0015 运行（如 run-153de306）体检结果不变
- [x] 体检相关测试通过

## Comments

- 2026-10-20 实施（ticket-ms14，分支 ms-14，基于 macro-followups 并已合并其最新头 74cdb38）：
  - **改动**：`tools/quality/output_consistency.py` 的“结构化结论……与投影相同”检查，在冻结清单含 `macro_judgement_rules`（model-v0016 起）时，期望另含 `macro_stage`、`macro_confidence`，取自投影 `cycle_overview.macro_judgement.conclusion` 的 `stage`、`confidence`；投影缺该块时两键期望为空值。以冻结清单而非投影是否有该块为开关，投影漏发宏观判断也能被查出。更早模型不期望这两个键。`docs/development/data-quality-audit.md`“报告与投影”补一条。
  - **测试**（新增 `tests/maintenance/test_quality_output_consistency.py`，接缝为该层公开入口 `output_consistency.section(run)`，内存 SQLite 只建本层读到的表）：v0016 报告与投影一致 → 一致；报告 `macro_stage` 不同 → 不一致并指出该键；v0015 无宏观判断 → 一致。改动前 2 失败 1 通过（红灯原因为“多出的键：macro_confidence、macro_stage”），改动后 3 通过。
  - **命令与结果**：`PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS=--basetemp=/tmp/pytest-ms14 flock /tmp/pring-heavy.lock python tools/check.py quick tests/maintenance/test_quality_output_consistency.py <两例冒烟>`（venv `dev-venv-ms14`，合并后复跑）：5 passed，75.05 s，退出码 0。`ruff check`／`ruff format --check` 通过。
  - **正式库体检**（只读，`mode=ro`；新旧脚本各跑一次，输出在 `/tmp/pytest-ms14/audit/`）：
    - run-3ebbe323（v0016）：第三层（一）由 59 项一致 58 变为 **一致 59、不一致 0**；与旧脚本输出的差异只有该检查一行、结论一行与耗时行。
    - run-153de306（v0015）：与旧脚本输出除耗时行外逐字相同（仍为 60 项一致 59，那一项是既有的贷款成员 `unknown`／`not_compared`，与本票无关）。
  - **偏离**：检查名仍为“结构化结论（确认度适用、维度计数、关键指标关系）”，未加“宏观判断”字样，为保持 v0015 输出逐字不变；体检原无自动化测试，本票首次为该层加测试。
- 2026-10-20（ms-rf2b，第二轮审查 S6）：负例参数化，补 `macro_confidence` 不一致（`explicit` 对投影 `tendency`）报不一致；见 `../review-fixes-20261020-r2.md` S6。
