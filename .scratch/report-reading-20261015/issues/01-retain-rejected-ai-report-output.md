Status: done
Category: bug
Type: task

# 01：留存被拒的 AI 报告输出并记录拒绝依据

**What to build:** AI 报告输出被事后检查拒绝时（`reports.py` `_validate_ai_document` 返回 `succeeded` 以外的结果），把被拒的文档正文按现有制品方式留存（制品库 `artifacts/sha256/`，与 `report_attempt.output_hash` 对应），并在 `report_attempt.process_audit_json` 里记录拒绝依据：哪条检查（`stage_mutation_rejected`、`conclusion_mutation_rejected` 的两个分支——conclusions 不一致 / `core_states` 不一致 / 正文复述确认度 / 复述价格 / 复述债券归因——等）、命中的 section 序号与标题。成功的输出已经留存，被拒的目前只有哈希。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `_validate_ai_document` 返回结果码之外还能给出命中位置（检查名、section 序号／标题、对 conclusions 不一致的给出第一处差异的键路径），现有调用方不变
- [x] 被拒输出按现有制品规则留存，`output_hash` 能在制品库里找到正文；留存受现有留存期规则约束（不新增永久制品）
- [x] `process_audit_json` 新增 `rejection` 字段记录依据；成功时不写
- [x] 两条 CLI 适配器路径（codex_cli、claude_code_cli）都覆盖；被拒后的后备链不变
- [x] 测试：以 `run-0eb95531…` 式的非典型组合输入构造一份改写了 conclusions 的 AI 输出，断言结果码、依据与留存
- [x] 不改任何检查的判定规则本身（误拒与否留待票 02 或后续用留存的正文定性）

## 背景

- `run-0eb9553118ba92a183b9`（2026-10-15，目标日 10-14，`noncanonical_combination`）：attempt 35 codex_cli 62 秒、attempt 36 claude_code_cli 51 秒，均 `conclusion_mutation_rejected`，`output_hash` 分别为 `1779e71c…`、`fd67759a…`，制品库无对应文件。
- `report_attempt` 历史 36 次：succeeded 30、timed_out 4、conclusion_mutation_rejected 2（即本次）。
- 检查代码：`src/pring_cycle/reports.py:1483-1525`；ADR-0027（AI 只解释、不改写结论）。

## Comments

### 2026-10-15 Codex 接续实施

实现已在 `report-reading-20261015` 集成分支完成，验收记录见 [acceptance.md](../acceptance.md)。原 `_validate_ai_document` 字符串返回接口保留，新增可选 `rejection` 输出；路径为零基 section 下标、标题、检查名与首差异键路径。所有已解析 CLI 文档按规范 JSON 保存，`output_hash` 为同一字节串的 SHA-256。输入 bundle 管理制品寿命，不新增永久留存。

独立 Codex 静态复核发现并修复：落盘异常不能截断后备链（记录 `output_retention`）；取消后无快照的尝试也必须随过期输入清理。正常落盘失败时保留哈希与失败记录，不谎称正文已保存。原 run-0eb95531 的丢失正文无法凭哈希恢复。

离线实施验收完成（2026-10-15）；正式环境安装与下一次正常新运行的关口 A 验收仍待执行，见 acceptance.md 交付边界。
