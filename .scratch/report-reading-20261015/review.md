# Codex CLI 只读复核（2026-10-15）

两轮均通过 `codex exec -s read-only -C /mnt/d/cursor/datasourceRF --skip-git-repo-check ... < /dev/null` 运行，未委派实施或测试。原始 stdout 位于 `/tmp/report-ticket01-review.log`、`/tmp/report-reading-review.log`。以下是主 agent 核实后的摘要，不把静态复核当作实测。

## 票 01

- 落盘异常会在记录 attempt 前截断后备链。已核实并修复：捕获存储异常，记录 `output_retention.status=failed` / `error_type`，原结果与后备链继续。验证：`test_output_storage_failure_does_not_suppress_cli_fallback`。
- 无快照的取消尝试不会被“按 report_snapshot 删除”覆盖。已核实并修复：通过审计里的 bundle_id 随过期输入删除，制品所有权同样随 bundle 过期。验证：`test_report_output_artifact_expires_with_report_input`。
- 复核未发现票 01 改变原有拒绝规则；原始输出规范化字节与 output_hash 相同。

## 票 02

- 其他 section 可能绕过固定段事实检查（例如合法固定段后另加“本轮正式阶段为 III。债券稳定状态为熊市。”）。已核实并修复：有新 basis 的非典型报告只接受唯一固定 section，其他 section 一律拒绝。验证：`test_extra_section_cannot_override_noncanonical_facts`。
- 无 basis 时同名 section 可被错误接收与展示。已核实并修复：校验要求 basis，首页还检查当前组合确为非典型且正式阶段为空。验证：`test_noncanonical_section_requires_worker_basis`，覆盖典型与核心未就绪输入。
- 复核确认两个非典型组合各有三项单资产差异、30 日方向与持续候选分离、首页按投影身份选择报告、无历史回填、取消审计与制品生命周期修复。

额外自查：事实前加“并非”也会改写含义，不能仅检查“原句包含于输出”；现要求事实块精确前缀，后续只接受已给定的观察句。验证：`test_invalid_reading_is_rejected_and_falls_back[negated_facts]`。
