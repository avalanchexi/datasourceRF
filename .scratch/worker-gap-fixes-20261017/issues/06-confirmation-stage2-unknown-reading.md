# 06: 确认度第二阶段报错

**What to build:** 价格阶段为第二阶段、贷款少增且动量未知时，确认度缺失诊断抛 `AttributeError: 'MemberReading' object has no attribute 'action'`（决定 6，Codex 内存探针）。先在单日汇总测试缝写会失败的回归测试，再修为按规则记"未确认"；不改预期表与模型版本。规格 [../spec.md](../spec.md)，根因 [../investigation.md](../investigation.md)，决定 [../decisions.md](../decisions.md)。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 回归测试先红后绿
- [x] 该情形下贷款确认关系为未确认并写明缺什么
- [x] 两项必跑冒烟通过

## Comments

### 2026-10-17 实施

- **根因**：`confirmation.py` 的 `_unknown_readings` 为写明"缺哪种读法"，对 `_READINGS` 全部名字逐一调用 `main.reading(name)`；普通成员读法没有 `action`（政策动作）与 `quadrant`（库存象限）属性，于是抛 `AttributeError`。凡主成员某读法未知且有单元格命中，都会走到这条路径，此前从无测试覆盖（第二阶段贷款"少增"的单元格要读动量，而贷款只读 t、t-1、t-12、t-13，动量必然未知，最先触发）。
- **修复**：只询问该单元格条件实际读到的名字，未知者列入缺失；不改预期表、不改模型版本。
- **回归测试**（单日汇总测试缝，ADR-0034）：`tests/integration/test_day_summary.py::test_stage_ii_loans_less_with_their_momentum_not_known_are_unconfirmed_and_say_so`——债股升、商品跌得第二阶段，贷款当月增量较去年同月少增；断言贷款关系 `unconfirmed`，`missing` 为 `borrower=enterprise,measure=ytd_increment,tenor=long_term:unknown_momentum`。修前红（`AttributeError: 'MemberReading' object has no attribute 'action'`），修后绿。
- **测试与耗时**：`test_day_summary.py` 与 `test_confirmation_*.py` 共 527 passed（708 s，超出 ≤3 分钟目标，含并行代理负载）；两项必跑冒烟 2 passed（45 s）。改动文件 `ruff check`、`ruff format --check` 通过；`mypy` 对 `confirmation.py` 与新增测试行无新报错（`test_day_summary.py` 既有报错不变；新增导入使 mypy 跟进的测试模块变多，总数随之上升，均为既有报错）。
- **遗留（领域观察，回报主 agent）**：贷款只读 t、t-1、t-12、t-13（ADR-0035），动量永远未知；因此第二阶段贷款"少增"时两个单元格（少增且扩大／少增且收窄）都无法判定，按规则恒记"未确认：缺动量"，只有"多增"能判为支持。这是预期表与回看深度的组合结果，不在本票范围（不改预期表与模型版本）；如需让第二阶段贷款可判，应另开模型规则票。
