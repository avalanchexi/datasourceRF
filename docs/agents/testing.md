# 测试执行

依据 [ADR-0025](../adr/0025-affected-tests-daily-full-suite-once.md)。继续实施时先读当前地图 `.scratch/pring-fast-refactor-20260923/map.md` 与所领的票。

## 日常反馈：只跑受影响测试

从仓库根目录显式选择受影响测试：

```bash
python tools/check.py quick tests/integration/test_worker_reviewed_context.py
```

此命令要求具体文件或 node ID，拒绝整个目录及 `HEAVY_FILES` 中的重型文件。目标 ≤3 分钟；超出如实记录，不删必要测试凑时限。返回码沿用 pytest，未选范围不计通过。选择依据是变更及其调用方：解析变更覆盖对应解析与获取；选值、时效、结构校验变更覆盖相应消费者；共享逻辑或影响不明时扩大范围。

## 切片收尾：端到端冒烟

每个实施切片收尾跑两例快速正例（目标合计 ≤1 分钟）：

- `tests/integration/test_core_history_refresh.py::test_manual_run_cannot_backdate_daily_core_availability`
- `tests/integration/test_worker_execution.py::test_worker_completes_a_valid_noncanonical_projection_and_report`

改动涉及 Worker 编排、指标目录或来源时，再显式加跑完整目录正例 `tests/integration/test_worker_registered_catalog.py`（登记并激活内置生效模型，官方 PPI 回退进入报告；2026-09-23 实测约 52 秒）与三核心反例 `tests/integration/test_core_carry_forward.py`（落后 1 期核心沿用、落后 ≥2 期与冲突阻断）。重型文件用显式 `python -m pytest <具体文件或 node>` 运行，记录退出码与耗时。

## 全套：只在真实运行前跑一次

到达地图终点、做真实完整运行之前，跑一次默认全套：

```bash
python tools/check.py full
```

全套包含全部耗时测试，只看通过与否并记录实际耗时，不产出或复用收据；其余时候不跑。

全套与真实完整运行开跑前，先跑 `python3 tools/clock_check.py`（约 65 秒），退出码 0 才开跑：墙钟回拨会让 `test_tushare_call_quota.py` 失败，并让真实运行拒收回执（`acquisition_time_invalid`）。两者都在 `flock /tmp/pring-heavy.lock` 下运行，并用 `tools/disk_guard.sh <pytest PID> <log> <GB下限> &` 守 C 盘（全套 12G、真实运行 20G）。

## 被删门禁的测试

随对应模块在同一切片删除或改写：模块整删时整删其专属测试文件；部分耦合的测试在修改其模块的切片内去掉认证、准入、回放、PUBLIC 发布时间断言与前置。两轴审查不再强制，用户需要时再跑。本 effort 不引入 pytest-xdist。

## 时间与磁盘

- 同一时刻只跑一个重型测试，性能测量排除竞争负载；保留机器日常使用余量。
- C 盘保护用 `tools/disk_guard.sh`（脚本头部写了守哪个进程）；放在会话临时目录的副本会随 WSL 重启丢失。
- 每个用例使用独立可变运行库。
- 计时随必跑验证采集，分别记录冷/热材料、准备/复制、测试和清理成本；同范围同身份才比较收益。
- `check.py` 每次运行把每个用例的 setup／call／teardown 写入计时文件（`-p tools.timings`，默认在系统临时目录，`--timings <路径>` 可指定），结束时打印前 30 用例、前 15 文件、前 50 与前 10% 占比，并给出计时文件路径。全套记录耗时时一并保留这份摘要，不必为排名另跑一轮。module 夹具的 setup 记在首个用例名下，看共享运行的成本以文件合计为准。
- 默认全套的磁盘峰值以 pytest basetemp 为主：每个用例的隔离运行库在整轮运行期间只增不减，2026-09-20 实测一轮峰值 **60.51 GiB**（中途 28G 只是过程值，勿按它估算）（随生命周期夹具删除预计明显下降，届时以实测为准）。开跑前按这个量级核 C 盘余量，不要只看起始值够不够。
- WSL 内删除只释放 VHD 内可复用块，**C 盘不会因此回升**（2026-09-20 实测删除 37G 后 C 盘仍为 2.44GiB）。要把空间还给 C 盘须压缩 VHD，而压缩需要 `wsl --shutdown`。因此磁盘保护触发后，先确认空间能否真正恢复再决定重跑，否则会在同一位置再次中止。
- 重型执行检查C盘实际余量，不能用WSL虚拟盘的逻辑空闲替代；用监督器定期记录进度与空间。可清理未使用的可再生成副本，保留失败证据与正式运行数据；WSL内删除只保证释放可复用块，不保证C盘立即缩小。
- 普通软件回归以外部HTTP/时钟替身保持离线；意外外网等待应在测试边界修正，不能以延长超时掩盖。
- 默认夹具下，TuShare 分钟限额的等待在测试中跳过（`tests/conftest.py`，模块级夹具同样适用），且只推进限额自己的时钟，不推进回执或其他业务时钟；要模拟"次日"等时间推进，用 `install_runtime_clock` 整体换时间轴。精确限频行为由 `test_tushare_call_quota.py` 的 timeline 专测（lookback 10）。

## 真实外部调用

普通回归一律离线（见上）。测试阶段取真实样本（如资讯规则要求的真实稿件）或做真实完整运行时，可以使用 TuShare 等真实额度，不必为节省额度压缩必要调用；但一律串行、不并发：一次一个请求，不写并行或批量循环，不在真实运行进行中另行调用同一接口。限额与账户共用情况见[本地运行说明](../development/local-runtime.md)“外部接口限频与并发”。

## 当前解释器的诊断方式

本机 Python 3.12.12 上，SQLite 连接创建/关闭与 `faulthandler.dump_traceback_later` 的原生 watchdog 组合可稳定触发 SIGSEGV。完整验证中的一次崩溃已由独立最小复现确认：开启原生计时器3/3崩溃，关闭计时器或普通Python线程采样各3/3完成30000次连接；原Worker场景更换诊断方式后通过。见[诊断与原始证据](../../.scratch/pring-data-acquisition-repair/diagnosis-verification-faulthandler-20260918.md)。

该环境保持 pytest 默认 `faulthandler_timeout=0`，长时验证用独立监督进程记录单调耗时、C盘空间、当前节点与退出码；需要线程栈时，由普通Python线程取得 `sys._current_frames()` 后记录文件、函数和行号，不输出局部变量。Python线程可能在GIL长期不释放时无法采样，资源上限和终态收尾仍由外部监督负责。解释器升级后需重新核验，不能把本机结果外推至所有Python版本。
