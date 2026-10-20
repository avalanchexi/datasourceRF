# 宏观后续批次上线步骤（等用户确认）

范围：集成分支 `macro-followups`（宏观 11–16、三轮审查修复、ms-rf4 文案），并入 main 后重装正式环境。无数据库迁移、无模型版本变更（仍为 model-v0016）、无报告 schema／prompt 版本变更。

前提：全套通过（`full/`）；ms-rf4 合入后受影响测试通过。

1. 选无运行时段（避开 09:30），确认常驻 Worker 空闲；按 `~/.local/share/pring-cycle/worker-resident.meta` 的 PID 停常驻 Worker；按 PID 停 8069 驾驶舱（不用 `pgrep -f` 匹配命令行）。
2. 备份正式库：sqlite backup API → `~/.local/share/pring-cycle/backups/pring-cycle-before-macro-followups-20261020.sqlite3`。
3. `macro-followups` 并入 main（main 有新提交则先合入并复跑受影响测试）。
4. 重装正式 `dev-venv`（`uv sync --extra dev --no-editable`），核对安装副本与 HEAD 逐文件一致；`pring-cycle init` 确认 schema 不变（0039）。
5. 重启常驻 Worker（`start-worker-resident.sh`）与 8069 驾驶舱（新代码），8069 这次写 PID 文件。
6. 补生成 10-19 AI 报告（当前投影 projection-59421326，v0016）：`pring-cycle report-generate --request-id repair-report-20261019-macro-01 --json`，确认 codex_cli 或 claude_code_cli 成功、不再退模板 → 通过则关宏观 10。
7. Codex 浏览器复核 8069：⑥ 宏观区间抽屉逐日写宏观信息（D2）、② 债券归因抽屉"价格阶段"、⑦ 完整度"计划期数"与门禁列说明、报告区为 AI 解读。

注意：已发布投影（10-19 projection-59421326）不回填，⑦ 计数与宏观区间抽屉的滞回状态要到下一次运行发布（10-21 09:30，目标日 10-20）才按新规则显示；在那之前宏观抽屉写"滞回状态未记录"，⑦ 仍是 4 期其他缺失。
