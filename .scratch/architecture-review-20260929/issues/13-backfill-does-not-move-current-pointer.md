# 13: 补算日不切换当前指针

**What to build:** 补算日的分析投影集只保存为历史集，不切换当前指针；只有目标日发布才切换。首次初始化或日常补算中途失败时，页面继续提供上一套完整投影（ADR-0008）。

**Blocked by:** 10

**勿并行：** 11、12、14（同改：单日汇总模块；逐区明细见 [README](../README.md)「串行约束」）

**Status:** done

来源：[架构评审](../README.md) 候选 3 差异（用户判定为遗漏，2026-09-29）。 规格：[spec.md](../spec.md)「四、单日汇总模块」。

## 现状

- `ProjectionSetRepository` 不区分目标日与补算日，只要新投影日期 ≥ 当前日期就切换指针（`projections.py:118`、`:130`）。首次初始化随补算逐日前移；运行在补算中途或目标日发布前失败（如 `worker.py:473` 模型切换）时，页面会停在某个补算日。
- 补算日投影集的缺口清单、发布日历、解释性警告为空。页面只读当前投影（`web.py:87`），本票完成后这些空项不会被展示，维持为空（用户决定，2026-09-29）。

## 验收

- [x] 补算日发布不改变当前指针；目标日发布按现行"日期不倒退"规则切换。
- [x] 按 TDD：首次初始化在目标日发布前失败 → 当前指针仍为运行前的投影（空库时仍为空）；成功后指向目标日；补算日投影集可按 id 读取。
- [x] `test_backfill.py:86`、`:106` 的最终指针断言通过。
- [x] 受影响测试经 `check.py quick` 通过；切片收尾冒烟通过。
- [x] 代码审查无阻断。

## Comments

- **实现**：
  - `ProjectionSetRepository.publish` 新增 `as_current`（默认 True）。为 False 时只保存集合、数据集与评估，不动当前指针。`P0ProjectionService.publish` 透传这个参数，`DaySummaries._summarize_day` 传 False。目标日仍按"日期不倒退"切换。
  - 按审查意见，发布改为按 id 幂等：已存的集合不再写入，`as_current` 时仍可按日期规则取得指针。此前同 id 的历史集再次发布，或晋升为当前集，会撞主键。
  - 指针切换与集合写入分成 `_take_current`、`_insert_set` 两个私有方法。
  - `last_confirmed_stage`、`stage_history`、`summarized_dates` 都直接查 `p0_assessment`，不依赖指针，补算的阶段传承不受影响。
- **可观察变化**：
  - 首次初始化期间，当前投影 API 返回不可用（空库），之后停在上一套完整投影，直到目标日发布。未绑定投影的独立报告任务在此期间读到旧目标投影。
  - Worker 完整运行按 `summarize_target` 返回的投影 id 关联报告与采用记录，不读指针，不受影响。
  - **只记录、不修**：阶段史 API 与页面阶段史直接读评估表，补算事件在目标日发布前就会出现。这是既有读取路径，票面没有提到。
- **测试**（先红后绿）：
  - `test_day_summary.py::test_only_the_target_day_moves_the_current_projection`：
    - 空库补算后仍无当前投影；
    - 已有较早目标日时，补算更晚的日子不动指针；
    - 目标日发布后才切换；
    - 补算集按日期可读回。
  - `test_a_stored_set_published_again_is_kept_once_and_may_take_the_pointer`：同一集合先两次存为历史，再以当前集发布，只存一份并取得指针。
  - `test_backfill.py` 最终指针断言（现为第 86 行；票面所说第 106 行已不存在）在回归网中。
- **验证**（`PYTHONPATH=src`）：涉及单日汇总、Worker、投影与所有完整运行的测试文件，加上原子投影、本地运行命令行与 `test_backfill.py`，共 822 例全过（45.6 分钟），其中包括两例冒烟。ruff、mypy 通过。
- **审查**（Codex 只读）：唯一阻断项（同 id 重复发布、历史集晋升的幂等性）已修；另建议补充目标日发布前注入异常的路径，现有用例以"只补算、不发布目标日"等价覆盖。
