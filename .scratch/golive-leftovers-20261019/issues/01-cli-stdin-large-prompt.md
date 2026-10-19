# 01: 修复 CLI 大提示词写不完 stdin 导致超时

**What to build:** 报告生成调用 Codex／Claude Code CLI 时，提示词超过管道容量（64KB）就会在首次 0.5 秒轮询超时后停止续写 stdin，CLI 收不到 EOF，空输出直到 300 秒超时（调查第 1 节，已用本地假子进程复现：91,805 字节只送出 65,536）。改为完整写入并正确关闭 stdin（如独立 I/O 线程做一次 communicate，主线程负责截止与取消），审计里记录已发送字节数；保持现有超时、取消、输出校验行为不变。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 回归测试：用本地假子进程（启动后延迟读 stdin）喂 >64KB 提示词，能完整送达并正常完成；原有超时与取消用例仍通过
- [x] `process_audit_json` 记录已发送字节数
- [x] 两例冒烟通过
- [x] 回报中给出上线后补生成 10-19 报告的命令（`pring-cycle report-generate --request-id <新 id> --json`，不加 `--deterministic-only`），由集成票执行

## Comments

- 2026-10-19 ticket-gl01（分支 `gl-01`）：`cli_process._communicate_with_limits` 改为独立写线程（按 1024 字符分块写入并 flush，写完关闭 stdin 送 EOF）＋两个读线程（stdout／stderr 读到 EOF），主线程只负责截止与取消；终止时先 SIGTERM 等 5 秒、再 SIGKILL，输出取读线程已收内容。超时、取消、版本探测共用截止与进程组清理的行为不变。
- 审计新增 `prompt_bytes_sent`（UTF-8 字节，与 `prompt_bytes` 同口径）；超时或取消时为实际送达量，便于直接判断是否卡在管道容量。
- 根因确认：新回归 `tests/reports/test_cli_protocol.py::test_a_prompt_larger_than_the_pipe_reaches_a_cli_that_reads_stdin_late`（假 CLI 启动后 0.75 秒才读 stdin，提示词约 12 万字节）在修复前 10 秒超时退为 `completed_degraded`，修复后正常完成且 `prompt_bytes_sent == prompt_bytes`。
- 测试：`python tools/check.py quick tests/reports/test_cli_protocol.py tests/reports/test_report_boundary.py tests/integration/test_ai_websearch.py tests/reports/test_noncanonical_reading.py tests/integration/test_report_input.py` → 108 passed（50.5 秒）；两例冒烟（`flock /tmp/pring-heavy.lock python -m pytest …`）2 passed（47.8 秒）；ruff、ruff format、mypy（cli_process.py）通过。main 头仍为 fbd20f8，无需再合并复跑。
- 偏离：未单设"已发送字节数"专测，并入上述回归断言；`prompt_bytes_sent` 只在生成阶段记录，版本探测不记（其输入为空）。
- 补生成 10-19 报告（由集成票在安装本修复后执行，先确认 `current_projection` 仍是目标日 10-19 的投影）：`~/.local/share/pring-cycle/dev-venv/bin/pring-cycle report-generate --request-id repair-report-20261019-stdin-01 --json`（不加 `--deterministic-only`）。
