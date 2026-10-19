# 01: 修复 CLI 大提示词写不完 stdin 导致超时

**What to build:** 报告生成调用 Codex／Claude Code CLI 时，提示词超过管道容量（64KB）就会在首次 0.5 秒轮询超时后停止续写 stdin，CLI 收不到 EOF，空输出直到 300 秒超时（调查第 1 节，已用本地假子进程复现：91,805 字节只送出 65,536）。改为完整写入并正确关闭 stdin（如独立 I/O 线程做一次 communicate，主线程负责截止与取消），审计里记录已发送字节数；保持现有超时、取消、输出校验行为不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 回归测试：用本地假子进程（启动后延迟读 stdin）喂 >64KB 提示词，能完整送达并正常完成；原有超时与取消用例仍通过
- [ ] `process_audit_json` 记录已发送字节数
- [ ] 两例冒烟通过
- [ ] 回报中给出上线后补生成 10-19 报告的命令（`pring-cycle report-generate --request-id <新 id> --json`，不加 `--deterministic-only`），由集成票执行
