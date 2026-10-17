# 15: 验收后调整的集成验收

**What to build:** 票 11–14 合入 `cockpit-layout` 后，整体验证并交用户逐段确认（规格 [../spec-adjust-20261017.md](../spec-adjust-20261017.md)）：全套测试；按 `docs/agents/codex-delegation.md` 第五节由 Codex 在 1440/908/390 宽、明暗两主题下截图并实测（② 三卡底边差、⑥ 两栏对齐、各限高、无横向溢出）；8067（10-14）、8068（10-15）预览换成新代码；`acceptance.md` 追加本轮清单。

**Blocked by:** 11、12、13、14

**Status:** ready-for-human

- [x] 全套测试通过（或失败逐条说明并处理）；两项必跑冒烟通过（全套 2694 passed；冒烟 2 passed）
- [ ] Codex 截图与实测数值记入 acceptance.md，主 agent 抽查关键截图
- [x] 8067、8068 已换新代码并可访问（dev-venv-cl15，PID 1365489、1365491）
- [x] acceptance.md 有本轮逐段确认清单，等用户勾选

## Comments

### 2026-10-17 实施

**审查修复**（提交 0e6dcd4，TDD 先红后绿，测试缝 `dashboard_page`）：
1. 家数近 120 日：投影点列只有 120 个交易日，起点不在点列时写"—（点列只含 120 个交易日，无法算 120 日家数差）"（`wording.REASON_LABELS["count_window_outside_points"]`），近 5 日家数差不变；`change_cell`、`_change_text` 的原因先查 `REASONS` 再查 `reason_label`。
2. 非典型组合：确定性模板分支补"阶段变化：非典型组合，暂无正式阶段"；⑥ `HISTORY_LABELS["noncanonical_combination"]` 改为同一文案，区间列表、日数汇总、区间抽屉、色带悬停一起变。改写 `test_stage_history_intervals.py` 三例旧"非典型组合"断言，新增 `test_reading_wording.py` 模板分支一例、`test_asset_cards.py` 近 120 日一例。
3. 控制判断改用 `wording.noncanonical_stage_change(change, reason)`，`stage_change_label` 共用。
4. `report.css` 请求表、逐项表合并选择器。

**验收**：详见 [acceptance.md](../acceptance.md) 第二轮。全套 2694 passed（4774 秒）；Codex 在改前 8067/8068 与改后 8115/8116/8117 上明暗 × 1440/908/390（⑥ 加 1200）实测并截图 105 张（`screenshots/adjust-20261017/`）：② 1440 三卡底边差与各段顶边差 0、观察框 318；⑥ 1440/1200 两栏顶底差 0；抽屉 83/82 个全部开合通过；无横向溢出、无控制台错误。之后 8067、8068 按 PID 换成 dev-venv-cl15，临时站已停。

**如实记录**：
- 全套的 `disk_guard.sh` 因缺执行权限没起来（脚本用 `tools/disk_guard.sh` 直接调用）；C 盘 53G → 41G，未触下限。下次用 `bash tools/disk_guard.sh`。
- 票 11 验收框"908 宽底边齐平"与规格"<1000px 堆叠"矛盾，已由主 agent 问用户；908 实测为三卡堆叠，本票未改断点与该框。
- 10-15 AI 正文仍有"阶段变化记为缺口"、`stage_iii` 等，属 B 批次 05。
- "主 agent 抽查关键截图"一框留给主 agent 勾。
