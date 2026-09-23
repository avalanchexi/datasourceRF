## Agent skills

### Issue tracker

任务与规格使用 `.scratch/` 下的本地 Markdown 文件跟踪。参见 `docs/agents/issue-tracker.md`。

### Triage labels

任务分流使用五个默认状态标签。参见 `docs/agents/triage-labels.md`。

### Domain docs

项目采用单一领域上下文结构。参见 `docs/agents/domain.md`。

### Codex delegation

耗 token 的只读调查默认交由 Codex CLI 执行，不消耗 Claude Code 额度；仅通过 `codex exec` 命令行调用，不走 MCP、wrapper skill 或其他间接路径。Claude Code 专注于分析与调度。参见 `docs/agents/codex-delegation.md`。

### Test execution

实施任务、选择受影响测试、运行切片收尾冒烟或终点前全套时，读取 `docs/agents/testing.md`（依据 ADR-0025）。
