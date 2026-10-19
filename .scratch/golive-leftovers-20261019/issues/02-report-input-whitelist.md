# 02: 报告输入剔除嵌套溯源 ID

**What to build:** 10-19 报告输入比 10-16 大 48%，主要来自注册仓单嵌套的 389 个首末日 claim ID（调查第 1 节）。报告输入改为字段白名单或递归剔除溯源 ID，AI 仍能引用所需事实；报告解释校验不受影响。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 报告入口测试：输入不含嵌套 claim／observation ID，体积显著下降；必需事实字段仍在
- [x] 两例冒烟通过

## Comments

**2026-10-20 实施（ticket-gl02，分支 gl-02，提交 3bbf8f6，合并 main 0ad71c9 后 5ee9690）**

做法：通用递归剔除，不做逐字段白名单。`ReportInput.create`（`src/pring_cycle/reports.py`）对 `conclusions` 与 `results` 递归去掉键名以 `claim_id(s)`、`observation_id(s)`、`observation_version_id(s)`、`snapshot_id`、`assessment_id`、`attempt_id` 结尾的字段（任意深度、任意前缀，如 `first_claim_ids`、`selected_claim_ids`、`input_observation_version_ids`、`derived_observation_id`、`evidence_snapshot_id`）。`metric_id`／`core_metric_id` 等代码保留（中文名映射与解释校验要用），顶层 `bundle_id`／`projection_set_id`／`model_version_id` 不在 results 内、不受影响；`gap_list` 不发给 AI，未动。macro-stage 的 `_macro_results` 同样经 `ReportInput.create`，合入后自动受益、无冲突点（其 signals 的 `id` 不是溯源 ID，保留）。`_inventory_notes` 原先只删顶层 `observation_version_ids` 的专用过滤改为直接取值，由通用剔除负责。

测试（新增／加强）：
- `tests/reports/test_report_boundary.py::test_the_report_input_carries_the_facts_without_their_evidence_identifiers`：嵌套多层的溯源 ID 输入与手写无 ID 的结果给出相同 `prompt_document()`；确定性骨架也不含 ID。先红后绿。
- `tests/integration/test_confirmation_inventory.py::test_the_inventory_page_and_the_report_carry_the_quadrant_and_the_warrant_note`：仓单各品种首末值、变化率仍在，`first_claim_ids`／`last_claim_ids` 不在，报告输入中无任何仓单 claim ID。旧代码下红、新代码绿。

受影响测试（`dev-venv-gl02`，`--basetemp=/tmp/pytest-gl02`，`flock /tmp/pring-heavy.lock`，`python tools/check.py quick …`）：
- 合并 main 前：reports 三文件＋web 两文件＋confirmation_inventory 148 passed（45 s）；confirmation_bond_attribution／cumulative_quarterly／policy／price_consistency／publish 312 passed（392 s）；model_version_switch／retention／source_contract_quarantine 23 passed（279 s）。ruff check／format、mypy reports.py 通过。
- 合并 main（0ad71c9，只带入 04 的定向指数改动，与报告无关）后复跑：reports 三文件＋web 两文件＋confirmation_inventory＋cumulative_quarterly 189 passed（49 s）。
- 两例冒烟：`test_manual_run_cannot_backdate_daily_core_availability`、`test_worker_completes_a_valid_noncanonical_projection_and_report` 2 passed（51 s）。

10-19 投影体积（只读打开正式库 `mode=ro`，内存中由 `projection-554b0640f5f9d167fb6a` 构造报告输入，未写库、未调 CLI）：

| 内容 | 改前 | 改后 | 10-16 参照 |
|---|---:|---:|---:|
| `report_input`（紧凑 JSON，去 `gap_list`） | 88,650 | 62,275 | 60,950 |
| 其中注册仓单 | 29,378 | 3,003 | 3,003 |
| 完整提示词（`CliReportAdapter` 实际发送） | 91,805 | 65,430 | 61,913 |

完整提示词 −26,375 字节（−28.7%）；除 389 个仓单 claim ID 外其余内容逐字段相同（仅 `bundle_id` 随内容哈希变化）。

偏离／提醒：
- 改后完整提示词 65,430 字节，只比 65,536 字节管道容量少 106 字节；stdin 续写缺陷已由票 01 修复，故不再致命，但若 01 未生效，再长一点的输入仍会复现超时。剩余大头是 `confirmation.key_indicators`（约 44 KB），属内容本身，本票未动。
- 同一投影的 `bundle_id` 因输入变化而与改前不同；已存储的旧 bundle 不受影响。
